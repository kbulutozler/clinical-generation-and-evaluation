#!/usr/bin/env python3
"""GEPA prompt-optimization pipeline for ACI-Bench generation.

Pipeline flow
─────────────
  CLI / config
    load_gepa_defaults    read gepa/config.yaml strictly (exit if missing/invalid)
    build_arg_parser      construct the argparse parser from those defaults
    validate_gepa_args    sanity-check parsed args before any I/O

  Data loading
    resolve_encounter_ids sample or accept explicit train/val encounter lists
    load_prompt_examples  read prompts/gepa/<id>/<split>/prompt.json → Example objects
    load_seed_candidate   read the initial seed system prompt from file

  Preflight
    check_openai_server   verify the expected model is loaded on each vLLM server

  GEPA optimization loop  (driven by optimize_anything)
    evaluator()           closure passed to optimize_anything as the metric function
      call_generation     substitute candidate prompt into messages_template, call vLLM
      call_evaluator      format eval prompt, call vLLM, parse + score the JSON response
        finalize_eval     normalize error items, compute manual rubric score, attach metadata
    make_reflection_lm    closure passed to optimize_anything as the reflector LM

  Final pass  (after optimize_anything returns the best candidate)
    run_final_pass        rerun generation + eval with the best prompt on every example

  Output
    write_json            mkdir -p then write indented JSON
    append_jsonl          mkdir -p then append one line to a JSONL trace file

  Helpers
    _http_json            single HTTP helper shared by chat_completion and check_openai_server
    extract_thinking      strip <think>/Gemma thought tokens from vLLM output
    model_generation      look up generation params for a model key from config
    parse_json_object     parse JSON from LLM output, tolerating markdown fences
    normalize_error_item  validate and normalise one hallucination or omission item
    candidate_to_prompt   extract a prompt string from a str-or-dict GEPA candidate
    resolve_candidate_prompt  return (prompt_str, {hash}) for a candidate
    short_hash            12-char SHA-256 prefix used to fingerprint prompt candidates
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import random
import re
import shutil
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


SEED_PROMPT_PLACEHOLDER = "{seed_prompt}"
GEPA_OBJECTIVE = (
    "Improve the system prompt for generating complete, clinically accurate ACI-Bench notes. "
    "The optimized prompt must reduce hallucinated clinical facts and preserve explicit plan details."
)
GEPA_BACKGROUND = (
    "The generation prompt must produce a clinical note from a doctor-patient dialogue. "
    "The evaluator lists hallucinations and omissions, and code computes the score from that list. "
    "Do not optimize the evaluator prompt; optimize only the generation system prompt. "
    "Prior audit finding: verbose standard-note prompts caused Qwen to fabricate normal vitals, labs, "
    "neuro/abdomen exams, unrelated referrals, and unsupported social/family history. They also caused "
    "truncation before Assessment and Plan. Good prompts should tell the generator to omit unsupported "
    "sections/findings, avoid normal-template filler, preserve exact doses/referrals/follow-up, and "
    "prioritize completing Assessment and Plan over optional detail."
)
DEDUCTIONS = {
    ("hallucinations", "major"): 0.25,
    ("hallucinations", "minor"): 0.05,
    ("omissions", "major"): 0.10,
    ("omissions", "minor"): 0.02,
}
ALLOWED_HALLUCINATION_TYPES = {"fabrication", "negation", "causality", "contextual"}
ALLOWED_OMISSION_TYPES = {"current_issues", "pmfs", "plan"}
ALLOWED_SEVERITIES = {"major", "minor"}


@dataclass
class Example:
    encounter_id: str
    messages_template: list[dict[str, str]]
    target: str

    @property
    def source(self) -> str:
        """Dialogue content — the last user-role message in the template."""
        for msg in reversed(self.messages_template):
            if msg.get("role") == "user":
                return msg["content"]
        raise ValueError(f"No user message found in messages_template for {self.encounter_id}")


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------

def load_yaml(path: Path) -> dict[str, Any]:
    with path.open() as fh:
        return yaml.safe_load(fh)


def _http_json(url: str, data: dict[str, Any] | None = None, timeout: int = 30) -> dict[str, Any]:
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body)
    req.add_header("Authorization", "Bearer EMPTY")
    if body is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"HTTP {exc.code} from {url}: {exc.read().decode('utf-8', errors='replace')}") from exc


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2))


def _unique_openai_preflight_targets(
    args: argparse.Namespace,
) -> list[tuple[str, str, tuple[str, ...]]]:
    """Deduplicate (url, model) pairs so shared evaluator/reflector hits /models once."""
    order = ("generation", "evaluator", "reflector")
    buckets: dict[tuple[str, str], list[str]] = {}
    for role in order:
        url = getattr(args, f"{role}_url").rstrip("/")
        model = getattr(args, f"{role}_model")
        buckets.setdefault((url, model), []).append(role)
    return [(u, m, tuple(rs)) for (u, m), rs in buckets.items()]


def _build_serve_plan_for_gepa_yaml(gepa_yaml: Path) -> dict[str, Any]:
    script = Path(__file__).resolve().parent / "servers" / "vllm_model_flags.py"
    spec = importlib.util.spec_from_file_location("_gepa_vmf", script)
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load vllm_model_flags helper")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    cfg = mod.load_yaml(str(gepa_yaml))
    return mod.build_serve_plan(cfg)


def write_run_config_snapshot(
    run_dir: Path,
    args: argparse.Namespace,
    repo_config: dict[str, Any],
) -> None:
    """Copy effective YAML + CLI + model registry slice + derived serve plan for reproducibility."""
    snap = run_dir / "config_snapshot"
    snap.mkdir(parents=True, exist_ok=True)
    gepa_yaml = Path(args.gepa_config).expanduser().resolve()
    if gepa_yaml.is_file():
        shutil.copy2(gepa_yaml, snap / "gepa_config.yaml")
    cli_dump = {k: (str(v) if isinstance(v, Path) else v) for k, v in vars(args).items() if not k.startswith("_")}
    write_json(snap / "resolved_cli.json", cli_dump)
    subset = {
        k: repo_config["models"][k]
        for k in (args.generation_model, args.evaluator_model, args.reflector_model)
        if k in repo_config.get("models", {})
    }
    write_json(snap / "models_registry_subset.json", subset)
    try:
        write_json(snap / "serve_plan.json", _build_serve_plan_for_gepa_yaml(gepa_yaml))
    except (OSError, ValueError, KeyError, RuntimeError) as exc:
        write_json(snap / "serve_plan_error.json", {"type": type(exc).__name__, "error": str(exc)})


def append_jsonl(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as fh:
        fh.write(json.dumps(payload) + "\n")


# ---------------------------------------------------------------------------
# vLLM / OpenAI helpers
# ---------------------------------------------------------------------------

def check_openai_server(base_url: str, expected_model: str, timeout: int = 30) -> None:
    payload = _http_json(f"{base_url.rstrip('/')}/models", timeout=timeout)
    model_ids = {item.get("id") for item in (payload.get("data") or []) if isinstance(item, dict)}
    if expected_model not in model_ids:
        raise RuntimeError(
            f"Server {base_url} reachable but {expected_model} not in /models. "
            f"Found: {sorted(m for m in model_ids if m)}"
        )


def chat_completion(
    base_url: str,
    model: str,
    messages: list[dict[str, str]],
    generation: dict[str, Any],
    timeout: int = 900,
) -> str:
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": generation.get("temperature", 0.0),
        "top_p": generation.get("top_p", 1.0),
    }
    for key in ("max_tokens", "top_k", "min_p", "presence_penalty", "repetition_penalty"):
        if generation.get(key) is not None:
            payload[key] = generation[key]
    resp = _http_json(f"{base_url.rstrip('/')}/chat/completions", data=payload, timeout=timeout)
    return resp["choices"][0]["message"].get("content") or ""


def extract_thinking(text: str) -> tuple[str, str]:
    if "</think>" in text:
        thinking, text = text.split("</think>", 1)
        return text.strip(), thinking.replace("<think>", "").strip()
    if text.startswith("<|channel>thought") and "<channel|>" in text:
        thinking, text = text[len("<|channel>thought"):].split("<channel|>", 1)
        return text.strip(), thinking.strip()
    return text.strip(), ""


def model_generation(config: dict[str, Any], model_key: str) -> dict[str, Any]:
    mode = "thinking" if config.get("active_model_thinking", False) else "non_thinking"
    return config["models"][model_key]["generation"][mode]


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def load_seed_candidate(args: argparse.Namespace) -> str:
    if not args.seed_prompt:
        return "You are a clinical documentation specialist. Given a doctor-patient conversation, write a comprehensive clinical note."
    path = Path(args.seed_prompt)
    if not path.exists():
        raise FileNotFoundError(f"Seed prompt file not found: {path}")
    return path.read_text().strip()


def available_prompt_encounter_ids(prompt_root: Path, split: str) -> list[str]:
    return sorted({p.parts[-3] for p in prompt_root.glob(f"*/{split}/prompt.json")})


def load_prompt_examples(prompt_root: Path, split: str, encounter_ids: list[str]) -> list[Example]:
    examples = []
    for eid in encounter_ids:
        p = prompt_root / eid / split / "prompt.json"
        if not p.exists():
            raise FileNotFoundError(f"Prompt not found: {p}")
        payload = json.loads(p.read_text())
        examples.append(Example(
            encounter_id=payload["encounter_id"],
            messages_template=payload["messages"],
            target=payload["target"],
        ))
    return examples


def resolve_encounter_ids(
    args: argparse.Namespace, prompt_root: Path
) -> tuple[list[str], list[str] | None, dict[str, Any] | None]:
    """Return (train_ids, val_ids, sampling_metadata)."""
    if args.train_n is not None or args.val_n is not None:
        if args.train_encounter_ids is not None or args.val_encounter_ids is not None:
            raise SystemExit("Do not mix --train-n/--val-n with --train-encounter-ids/--val-encounter-ids.")
        train_n, val_n = args.train_n, args.val_n
        if not train_n or train_n <= 0:
            raise SystemExit("--train-n must be > 0.")
        if not val_n or val_n <= 0:
            raise SystemExit("--val-n must be > 0.")
        rng = random.Random(args.sampling_seed)
        train_pool = available_prompt_encounter_ids(prompt_root, args.train_split)
        val_pool = available_prompt_encounter_ids(prompt_root, args.val_split)
        for pool, n, label in [(train_pool, train_n, "train"), (val_pool, val_n, "val")]:
            if not pool:
                raise SystemExit(f"No prompts found under {prompt_root} for {label} split.")
            if n > len(pool):
                raise SystemExit(f"Requested {label}_n={n}, but only {len(pool)} prompts available.")
        train_ids = rng.sample(train_pool, train_n)
        val_ids = rng.sample(val_pool, val_n)
        if overlap := set(train_ids) & set(val_ids):
            raise SystemExit(f"Unexpected overlap between train/val encounter ids: {sorted(overlap)}")
        return train_ids, val_ids, {
            "mode": "random_without_replacement",
            "train_pool": len(train_pool), "val_pool": len(val_pool),
            "train_n": train_n, "val_n": val_n, "seed": args.sampling_seed,
            "prompt_train_split": args.train_split, "prompt_val_split": args.val_split,
        }
    train_ids = args.train_encounter_ids or args.encounter_ids
    val_ids = args.val_encounter_ids
    if val_ids is not None:
        if overlap := set(train_ids) & set(val_ids):
            raise SystemExit(f"Train/val encounter ids overlap: {sorted(overlap)}")
    return train_ids, val_ids, None


# ---------------------------------------------------------------------------
# Eval scoring
# ---------------------------------------------------------------------------

def parse_json_object(text: str) -> dict[str, Any]:
    cleaned = re.sub(r"^```(?:json)?\s*", "", text.strip())
    cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))


def clamp_score(value: Any) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


def normalize_error_item(item: Any, category: str, index: int) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        return None
    allowed_types = ALLOWED_HALLUCINATION_TYPES if category == "hallucinations" else ALLOWED_OMISSION_TYPES
    if item.get("type") not in allowed_types or item.get("severity") not in ALLOWED_SEVERITIES:
        return None
    normalized = dict(item)
    normalized["index"] = index
    if category == "hallucinations":
        evidence = normalized.get("text_in_note") or normalized.get("evidence_in_generated_note")
        if not str(evidence or "").strip():
            return None
        normalized["text_in_note"] = str(evidence).strip()
    else:
        evidence = (normalized.get("text_in_dialogue") or normalized.get("evidence_in_dialogue")
                    or normalized.get("ground_truth_quote"))
        if not str(evidence or "").strip():
            return None
        normalized["text_in_dialogue"] = str(evidence).strip()
    normalized["explanation"] = str(normalized.get("explanation") or "").strip()
    normalized["evidence_status"] = "primary_evaluator_listed"
    return normalized


def finalize_eval(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize error items, compute manual rubric score, and attach scoring metadata."""
    ev = dict(raw)
    for category in ("hallucinations", "omissions"):
        ev[category] = [
            item for i, raw_item in enumerate(ev.get(category) or [])
            if (item := normalize_error_item(raw_item, category, i)) is not None
        ]
    ev["normalization"] = {
        "hallucinations_kept": len(ev["hallucinations"]),
        "omissions_kept": len(ev["omissions"]),
        "allowed_hallucination_types": sorted(ALLOWED_HALLUCINATION_TYPES),
        "allowed_omission_types": sorted(ALLOWED_OMISSION_TYPES),
        "allowed_severities": sorted(ALLOWED_SEVERITIES),
    }
    manual_score = 1.0
    for item in ev["hallucinations"]:
        manual_score -= DEDUCTIONS.get(("hallucinations", item.get("severity")), 0.0)
    for item in ev["omissions"]:
        manual_score -= DEDUCTIONS.get(("omissions", item.get("severity")), 0.0)
    manual_score = max(0.0, min(1.0, round(manual_score, 10)))
    reported = ev.get("score")
    ev["reported_score"] = reported
    ev["manual_score"] = manual_score
    ev["score"] = manual_score
    ev["score_diff"] = manual_score - float(reported) if isinstance(reported, (int, float)) else None
    ev["score_source"] = "manual_rubric_from_listed_errors"
    return ev


# ---------------------------------------------------------------------------
# Pipeline callables
# ---------------------------------------------------------------------------

def call_generation(candidate_prompt: str, example: Example, args: argparse.Namespace, gen_cfg: dict[str, Any]) -> str:
    if args.mock:
        return (
            "CHIEF COMPLAINT\nUpper respiratory symptoms.\n\n"
            "ASSESSMENT AND PLAN\nViral upper respiratory syndrome. COVID test, Robitussin, "
            "ibuprofen or Tylenol as needed. Increase metformin to 1000 mg twice daily. "
            "Continue lisinopril 20 mg daily. Follow up in 4 months."
        )
    messages = [
        {"role": msg["role"], "content": msg["content"].replace(SEED_PROMPT_PLACEHOLDER, candidate_prompt)}
        for msg in example.messages_template
    ]
    output, _ = extract_thinking(chat_completion(args.generation_url, args.generation_model, messages, gen_cfg))
    return output


def call_evaluator(generated_target: str, example: Example, args: argparse.Namespace, eval_cfg: dict[str, Any]) -> dict[str, Any]:
    if args.mock:
        return finalize_eval({
            "hallucinations": [],
            "omissions": [{
                "type": "current_issues", "severity": "minor",
                "text_in_dialogue": "Patient reported exertional dyspnea while carrying soil.",
                "explanation": "The mock note compresses current symptoms.",
            }],
            "score": 0.98,
        })
    eval_prompt = json.loads(Path(args.eval_prompt).read_text())
    user_content = eval_prompt["messages"][1]["content"].format(
        source=example.source, target=example.target, generated_target=generated_target,
    )
    raw, _ = extract_thinking(chat_completion(
        args.evaluator_url, args.evaluator_model,
        [{"role": "system", "content": eval_prompt["messages"][0]["content"]},
         {"role": "user", "content": user_content}],
        eval_cfg,
    ))
    try:
        return finalize_eval(parse_json_object(raw))
    except json.JSONDecodeError:
        return finalize_eval({"hallucinations": [], "omissions": [], "score": 0.0, "raw_evaluator_response": raw})


def make_reflection_lm(args: argparse.Namespace, reflect_cfg: dict[str, Any]):
    def reflection_lm(prompt_or_messages: str | list[dict[str, Any]]) -> str:
        if args.mock:
            return (
                "```text\n"
                "You are a clinical documentation specialist. Given a doctor-patient conversation, "
                "write a concise clinical note using only dialogue-supported facts. Omit unsupported "
                "normal findings, vitals, labs, social history, family history, and exam sections. "
                "Preserve stated medications, doses, referrals, follow-up timing, and patient instructions. "
                "Complete Assessment and Plan before optional detail.\n"
                "```"
            )
        messages = [{"role": "user", "content": prompt_or_messages}] if isinstance(prompt_or_messages, str) else prompt_or_messages
        output, _ = extract_thinking(chat_completion(args.reflector_url, args.reflector_model, messages, reflect_cfg))
        return output
    return reflection_lm


def short_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:12]


def candidate_to_prompt(candidate: Any) -> str:
    if isinstance(candidate, str):
        return candidate
    if isinstance(candidate, dict):
        for key in ("prompt", "system_prompt", "candidate"):
            if key in candidate:
                return str(candidate[key])
    return str(candidate)


def resolve_candidate_prompt(candidate: Any) -> tuple[str, dict[str, Any]]:
    prompt = candidate_to_prompt(candidate)
    return prompt, {"candidate_prompt_hash": short_hash(prompt)}


def run_final_pass(
    examples: list[Example],
    split: str,
    best_candidate: Any,
    args: argparse.Namespace,
    gen_cfg: dict[str, Any],
    eval_cfg: dict[str, Any],
    run_dir: Path,
) -> list[dict[str, Any]]:
    outputs = []
    for example in examples:
        best_prompt, meta = resolve_candidate_prompt(best_candidate)
        generated_target = call_generation(best_prompt, example, args, gen_cfg)
        eval_json = call_evaluator(generated_target, example, args, eval_cfg)
        payload = {
            "encounter_id": example.encounter_id,
            "split": split,
            "score": clamp_score(eval_json.get("score")),
            "candidate_prompt_hash": meta["candidate_prompt_hash"],
            "generated_target": generated_target,
            "evaluation": eval_json,
        }
        write_json(run_dir / "final_outputs" / f"{example.encounter_id}.json", payload)
        outputs.append(payload)
    return outputs


# ---------------------------------------------------------------------------
# Config / CLI
# ---------------------------------------------------------------------------

def load_gepa_defaults(path: Path) -> dict[str, Any]:
    """Load CLI defaults strictly from ``gepa/config.yaml`` (no model/URL fallbacks)."""
    if not path.is_file():
        raise SystemExit(f"GEPA config must be an existing file: {path}")
    try:
        cfg = load_yaml(path)
    except (OSError, yaml.YAMLError) as exc:
        raise SystemExit(f"Failed to read or parse GEPA config {path}: {exc}") from exc
    if not isinstance(cfg, dict):
        raise SystemExit(f"GEPA config must be a YAML mapping at {path}")

    def require(section: str, key: str) -> Any:
        sub = cfg.get(section)
        if not isinstance(sub, dict):
            raise SystemExit(f"GEPA config {path}: missing or invalid [{section}] section (expected mapping).")
        if key not in sub:
            raise SystemExit(f"GEPA config {path}: missing required key [{section}].{key}")
        val = sub[key]
        if val is None:
            raise SystemExit(f"GEPA config {path}: [{section}].{key} is null")
        if isinstance(val, str) and not val.strip():
            raise SystemExit(f"GEPA config {path}: [{section}].{key} is empty")
        return val

    mapping = [
        ("data", "dataset", "dataset"),
        ("data", "train_split", "train_split"),
        ("data", "val_split", "val_split"),
        ("data", "train_n", "train_n"),
        ("data", "val_n", "val_n"),
        ("data", "sampling_seed", "sampling_seed"),
        ("models", "generation_model", "generation_model"),
        ("models", "evaluator_model", "evaluator_model"),
        ("models", "reflector_model", "reflector_model"),
        ("endpoints", "generation_url", "generation_url"),
        ("endpoints", "evaluator_url", "evaluator_url"),
        ("endpoints", "reflector_url", "reflector_url"),
        ("gepa", "max_metric_calls", "max_metric_calls"),
        ("gepa", "reflection_minibatch_size", "reflection_minibatch_size"),
        ("gepa", "candidate_selection_strategy", "candidate_selection_strategy"),
        ("gepa", "frontier_type", "frontier_type"),
        ("gepa", "engine_seed", "engine_seed"),
        ("paths", "repo_config", "config"),
        ("paths", "eval_prompt", "eval_prompt"),
        ("paths", "seed_prompt", "seed_prompt"),
        ("paths", "run_dir", "run_dir"),
    ]
    defaults: dict[str, Any] = {}
    for section, cfg_key, def_key in mapping:
        defaults[def_key] = require(section, cfg_key)
    for int_key in ("train_n", "val_n", "sampling_seed", "max_metric_calls", "reflection_minibatch_size", "engine_seed"):
        v = defaults[int_key]
        if not isinstance(v, int):
            raise SystemExit(f"GEPA config {path}: {int_key!r} must be an integer (got {type(v).__name__}).")
    return defaults


def build_arg_parser(defaults: dict[str, Any], gepa_config_path: str) -> argparse.ArgumentParser:
    p = argparse.ArgumentParser()
    p.add_argument("--gepa-config", default=gepa_config_path)
    p.add_argument("--dataset", default=defaults["dataset"])
    p.add_argument("--train-split", default=defaults["train_split"],
                   help="Training prompts: prompts/<dataset>/<encounter>/<train_split>/prompt.json.")
    p.add_argument("--val-split", default=defaults["val_split"],
                   help="Validation prompts: prompts/<dataset>/<encounter>/<val_split>/prompt.json.")
    p.add_argument("--encounter-ids", nargs="+", default=["D2N088"],
                   help="Legacy: encounters for both train and val. Prefer --train-encounter-ids/--val-encounter-ids.")
    p.add_argument("--train-encounter-ids", nargs="+", default=None,
                   help="Encounters for GEPA feedback/proposals. Falls back to --encounter-ids if omitted.")
    p.add_argument("--val-encounter-ids", nargs="+", default=None,
                   help="Held-out encounters for GEPA selection. Omit to run without a valset.")
    p.add_argument("--train-n", type=int, default=defaults["train_n"],
                   help="Random training encounters sampled from prompts/<dataset>/*/<train-split>/.")
    p.add_argument("--val-n", type=int, default=defaults["val_n"],
                   help="Random validation encounters sampled from prompts/<dataset>/*/<val-split>/.")
    p.add_argument("--sampling-seed", type=int, default=defaults["sampling_seed"])
    p.add_argument("--engine-seed", type=int, default=defaults["engine_seed"],
                   help="Random seed for GEPA engine (candidate selection, minibatch sampling).")
    p.add_argument("--config", default=defaults["config"])
    p.add_argument("--eval-prompt", default=defaults["eval_prompt"])
    p.add_argument("--run-dir", default=defaults["run_dir"])
    p.add_argument("--generation-url", default=defaults["generation_url"])
    p.add_argument("--evaluator-url", default=defaults["evaluator_url"])
    p.add_argument("--reflector-url", default=defaults["reflector_url"])
    p.add_argument("--generation-model", default=defaults["generation_model"])
    p.add_argument("--evaluator-model", default=defaults["evaluator_model"])
    p.add_argument("--reflector-model", default=defaults["reflector_model"])
    p.add_argument("--seed-prompt", default=defaults["seed_prompt"],
                   help="Path to seed system prompt file. Pass empty string to use the prompt JSON system message.")
    p.add_argument("--max-metric-calls", type=int, default=defaults["max_metric_calls"])
    p.add_argument("--reflection-minibatch-size", type=int, default=defaults["reflection_minibatch_size"])
    p.add_argument("--candidate-selection-strategy",
                   choices=["pareto", "current_best", "epsilon_greedy", "top_k_pareto"],
                   default=defaults["candidate_selection_strategy"],
                   help="GEPA candidate selection strategy.")
    p.add_argument("--frontier-type",
                   choices=["instance", "objective", "hybrid", "cartesian"],
                   default=defaults["frontier_type"],
                   help="How GEPA tracks Pareto frontiers across examples/objectives.")
    p.add_argument("--mock", action="store_true")
    return p


def validate_gepa_args(args: argparse.Namespace) -> None:
    if args.dataset != "gepa":
        raise SystemExit("GEPA runner expects prepared prompts under prompts/gepa; set dataset: gepa in gepa/config.yaml.")
    for flag, val in [("--train-n", args.train_n), ("--val-n", args.val_n),
                      ("--max-metric-calls", args.max_metric_calls),
                      ("--reflection-minibatch-size", args.reflection_minibatch_size)]:
        if val is not None and val <= 0:
            raise SystemExit(f"{flag} must be > 0.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    bootstrap = argparse.ArgumentParser(add_help=False)
    bootstrap.add_argument("--gepa-config", default="gepa/config.yaml")
    bootstrap_args, _ = bootstrap.parse_known_args()
    defaults = load_gepa_defaults(Path(bootstrap_args.gepa_config))
    args = build_arg_parser(defaults, bootstrap_args.gepa_config).parse_args()
    validate_gepa_args(args)

    config = load_yaml(Path(args.config))
    for model_key in (args.generation_model, args.evaluator_model, args.reflector_model):
        if model_key not in config["models"]:
            raise SystemExit(f"Model key not found in {args.config}: {model_key}")

    prompt_root = Path("prompts") / args.dataset
    train_ids, val_ids, sampling = resolve_encounter_ids(args, prompt_root)
    seed_candidate = load_seed_candidate(args)
    train_examples = load_prompt_examples(prompt_root, args.train_split, train_ids)
    val_examples = load_prompt_examples(prompt_root, args.val_split, val_ids) if val_ids else None

    gen_cfg = model_generation(config, args.generation_model)
    eval_cfg = model_generation(config, args.evaluator_model)
    reflect_cfg = model_generation(config, args.reflector_model)
    run_dir = Path(args.run_dir) / time.strftime("%Y%m%d-%H%M%S")
    run_dir.mkdir(parents=True, exist_ok=True)
    write_run_config_snapshot(run_dir, args, config)
    trace_dir = run_dir / "traces"
    trace_jsonl = trace_dir / "rollouts.jsonl"
    eval_call_count = 0

    print("GEPA starting...")
    print(f"  run_dir:  {run_dir}")
    print(f"  dataset:  {args.dataset}  train={len(train_examples)}  val={len(val_examples) if val_examples else 0}")
    if sampling:
        print(f"  sampling: {sampling}")
    print(f"  max_metric_calls={args.max_metric_calls}  minibatch={args.reflection_minibatch_size}")
    print(f"  strategy={args.candidate_selection_strategy}  frontier={args.frontier_type}")
    print(f"  generation: {args.generation_url}  model={args.generation_model}")
    print(f"  evaluator:  {args.evaluator_url}  model={args.evaluator_model}")
    print(f"  reflector:  {args.reflector_url}  model={args.reflector_model}")

    if not args.mock:
        print("  preflight: checking /models on all servers...")
        for url, model, roles in _unique_openai_preflight_targets(args):
            check_openai_server(url, model)
            print(f"    ok ({', '.join(roles)}) -> {url} ({model})")
        print("  preflight: OK")

    def evaluator(candidate: Any, example: Example | None = None, **_: Any) -> tuple[float, dict[str, Any]]:
        nonlocal eval_call_count
        if example is None:
            raise ValueError("GEPA did not provide an evaluation example.")
        started_at = time.time()
        eval_call_count += 1
        candidate_prompt, meta = resolve_candidate_prompt(candidate)
        generated_target = call_generation(candidate_prompt, example, args, gen_cfg)
        eval_json = call_evaluator(generated_target, example, args, eval_cfg)
        score = clamp_score(eval_json.get("score"))
        prompt_hash = meta["candidate_prompt_hash"]
        trace = {
            "call_index": eval_call_count,
            "elapsed_seconds": round(time.time() - started_at, 3),
            "encounter_id": example.encounter_id,
            "candidate_prompt_hash": prompt_hash,
            "candidate_prompt": candidate_prompt,
            "generated_target": generated_target,
            "evaluation": eval_json,
            "manual_score": score,
            "reported_score": eval_json.get("reported_score"),
            "score_source": eval_json.get("score_source"),
        }
        write_json(trace_dir / f"rollout_{eval_call_count:04d}_{example.encounter_id}_{prompt_hash}.json", trace)
        append_jsonl(trace_jsonl, trace)
        if eval_call_count == 1 or eval_call_count % 5 == 0:
            print(f"  metric_calls={eval_call_count}/{args.max_metric_calls} encounter={example.encounter_id} score={score:.3f} candidate={prompt_hash}")
        return score, {"encounter_id": example.encounter_id, "score": score, "generated_target": generated_target, "evaluation": eval_json}

    from gepa.optimize_anything import EngineConfig, GEPAConfig, MergeConfig, RefinerConfig, ReflectionConfig, optimize_anything

    result = optimize_anything(
        seed_candidate=seed_candidate,
        evaluator=evaluator,
        dataset=train_examples,
        valset=val_examples,
        objective=GEPA_OBJECTIVE,
        background=GEPA_BACKGROUND,
        config=GEPAConfig(
            engine=EngineConfig(
                run_dir=str(run_dir / "gepa_state"),
                seed=args.engine_seed,
                max_metric_calls=args.max_metric_calls,
                candidate_selection_strategy=args.candidate_selection_strategy,
                frontier_type=args.frontier_type,
                parallel=False, max_workers=1, capture_stdio=True,
                display_progress_bar=False,
            ),
            reflection=ReflectionConfig(
                reflection_lm=make_reflection_lm(args, reflect_cfg),
                reflection_minibatch_size=args.reflection_minibatch_size,
            ),
            merge=MergeConfig(max_merge_invocations=5),
            refiner=RefinerConfig(),
        ),
    )
    best_candidate = getattr(result, "best_candidate", seed_candidate)
    metric_calls = getattr(result, "total_metric_calls", None)

    final_outputs = run_final_pass(train_examples, "train", best_candidate, args, gen_cfg, eval_cfg, run_dir)
    if val_examples:
        final_outputs += run_final_pass(val_examples, "val", best_candidate, args, gen_cfg, eval_cfg, run_dir)

    best_candidate_text = candidate_to_prompt(best_candidate)
    write_json(run_dir / "summary.json", {
        "dataset": args.dataset,
        "train_split": args.train_split,
        "val_split": args.val_split,
        "gepa_config": args.gepa_config,
        "config_snapshot_dir": "config_snapshot",
        "encounter_ids": args.encounter_ids,
        "train_encounter_ids": train_ids,
        "val_encounter_ids": val_ids,
        "sampling": sampling,
        "models": {
            "generation": args.generation_model,
            "evaluator": args.evaluator_model,
            "reflector": args.reflector_model,
        },
        "seed_prompt_path": str(Path(args.seed_prompt)) if args.seed_prompt else None,
        "candidate_selection_strategy": args.candidate_selection_strategy,
        "frontier_type": args.frontier_type,
        "metric_calls": metric_calls,
        "optimization": {
            "mode": "mock-gepa" if args.mock else "gepa",
            "run_dir": getattr(result, "run_dir", None),
            "total_metric_calls": metric_calls,
            "trace_dir": str(trace_dir),
            "trace_jsonl": str(trace_jsonl),
            "num_trace_records": eval_call_count,
        },
        "final_outputs": final_outputs,
    })
    (run_dir / "best_candidate.txt").write_text(best_candidate_text)
    (run_dir / "best_generation_system_prompt.txt").write_text(best_candidate_text)
    print(f"GEPA pipeline complete: {run_dir}")
    print(len(final_outputs))


if __name__ == "__main__":
    main()
