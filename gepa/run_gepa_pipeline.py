#!/usr/bin/env python3
"""Minimal GEPA prompt-optimization pipeline for ACI-Bench generation."""

from __future__ import annotations

import argparse
import json
import re
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml


DEFAULT_GENERATION_MODEL = "Qwen/Qwen3.5-2B"
DEFAULT_EVALUATOR_MODEL = "google/gemma-4-E4B-it"
DEFAULT_REFLECTOR_MODEL = "google/gemma-4-26B-A4B-it"


@dataclass
class Example:
    encounter_id: str
    sourcedoc: str
    sourcetarget: str
    original_system_prompt: str


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open() as handle:
        return yaml.safe_load(handle)


def load_prompt_examples(prompt_root: Path, split: str, encounter_ids: list[str]) -> list[Example]:
    examples: list[Example] = []
    for encounter_id in encounter_ids:
        prompt_path = prompt_root / encounter_id / split / "prompt.json"
        if not prompt_path.exists():
            raise FileNotFoundError(f"Prompt not found: {prompt_path}")
        payload = json.loads(prompt_path.read_text())
        messages = payload["messages"]
        examples.append(
            Example(
                encounter_id=payload["encounter_id"],
                original_system_prompt=messages[0]["content"],
                sourcedoc=messages[-1]["content"],
                sourcetarget=payload["target"],
            )
        )
    return examples


def model_generation(config: dict[str, Any], model_key: str) -> dict[str, Any]:
    active_thinking = "thinking" if config.get("active_model_thinking", False) else "non_thinking"
    return config["models"][model_key]["generation"][active_thinking]


def post_json(base_url: str, path: str, payload: dict[str, Any], timeout: int = 900) -> dict[str, Any]:
    url = f"{base_url.rstrip('/')}/{path.lstrip('/')}"
    request = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"))
    request.add_header("Content-Type", "application/json")
    request.add_header("Authorization", "Bearer EMPTY")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} from {url}: {body}") from exc


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
    if generation.get("max_tokens") is not None:
        payload["max_tokens"] = generation["max_tokens"]
    if generation.get("top_k") is not None:
        payload["top_k"] = generation["top_k"]
    if generation.get("min_p") is not None:
        payload["min_p"] = generation["min_p"]
    if generation.get("presence_penalty") is not None:
        payload["presence_penalty"] = generation["presence_penalty"]
    if generation.get("repetition_penalty") is not None:
        payload["repetition_penalty"] = generation["repetition_penalty"]

    response = post_json(base_url, "/chat/completions", payload, timeout=timeout)
    return response["choices"][0]["message"].get("content") or ""


def extract_thinking(output_text: str) -> tuple[str, str]:
    if "</think>" in output_text:
        thinking_text, output_text = output_text.split("</think>", 1)
        return output_text.strip(), thinking_text.replace("<think>", "").strip()

    gemma_start = "<|channel>thought"
    gemma_end = "<channel|>"
    if output_text.startswith(gemma_start) and gemma_end in output_text:
        thinking_text, output_text = output_text[len(gemma_start):].split(gemma_end, 1)
        return output_text.strip(), thinking_text.strip()

    return output_text.strip(), ""


def parse_json_object(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
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
        score = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, score))


def summarize_eval(eval_json: dict[str, Any]) -> str:
    hallucinations = eval_json.get("hallucinations") or []
    omissions = eval_json.get("omissions") or []
    feedback = eval_json.get("feedback_for_reflector") or ""
    return (
        f"score={clamp_score(eval_json.get('score')):.3f}; "
        f"hallucinations={len(hallucinations)}; omissions={len(omissions)}; "
        f"feedback={feedback}"
    )


def call_generation(candidate_prompt: str, example: Example, args: argparse.Namespace, gen_cfg: dict[str, Any]) -> str:
    if args.mock:
        return (
            "CHIEF COMPLAINT\nUpper respiratory symptoms.\n\n"
            "ASSESSMENT AND PLAN\nViral upper respiratory syndrome. COVID test, Robitussin, "
            "ibuprofen or Tylenol as needed. Increase metformin to 1000 mg twice daily. "
            "Continue lisinopril 20 mg daily. Follow up in 4 months."
        )
    messages = [
        {"role": "system", "content": candidate_prompt},
        {"role": "user", "content": example.sourcedoc},
    ]
    output = chat_completion(args.generation_url, args.generation_model, messages, gen_cfg)
    output_text, _ = extract_thinking(output)
    return output_text


def call_evaluator(generated_note: str, example: Example, args: argparse.Namespace, eval_cfg: dict[str, Any]) -> dict[str, Any]:
    if args.mock:
        return {
            "hallucinations": [],
            "omissions": [],
            "score": 0.75,
            "feedback_for_reflector": "Preserve medications, testing, and follow-up in structured sections.",
        }

    eval_prompt = json.loads(Path(args.eval_prompt).read_text())
    system_prompt = eval_prompt["messages"][0]["content"]
    user_template = eval_prompt["messages"][1]["content"]
    user_content = user_template.format(
        sourcedoc=example.sourcedoc,
        sourcetarget=example.sourcetarget,
        generated_note=generated_note,
    )
    raw_eval = chat_completion(
        args.evaluator_url,
        args.evaluator_model,
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        eval_cfg,
    )
    eval_text, _ = extract_thinking(raw_eval)
    return parse_json_object(eval_text)


def make_reflection_lm(args: argparse.Namespace, reflect_cfg: dict[str, Any]):
    def reflection_lm(prompt_or_messages: str | list[dict[str, Any]]) -> str:
        if isinstance(prompt_or_messages, str):
            messages = [{"role": "user", "content": prompt_or_messages}]
        else:
            messages = prompt_or_messages
        output = chat_completion(args.reflector_url, args.reflector_model, messages, reflect_cfg)
        output_text, _ = extract_thinking(output)
        return output_text

    return reflection_lm


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2))


def candidate_to_prompt(candidate: Any) -> str:
    if isinstance(candidate, str):
        return candidate
    if isinstance(candidate, dict):
        for key in ("prompt", "system_prompt", "candidate"):
            if key in candidate:
                return str(candidate[key])
    return str(candidate)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="aci_bench")
    parser.add_argument("--split", default="clinicalnlp_taskB_test1_0shot")
    parser.add_argument("--encounter-ids", nargs="+", default=["D2N088"])
    parser.add_argument("--config", default="configs/config.yaml")
    parser.add_argument("--eval-prompt", default="gepa/evaluator_prompt_template.json")
    parser.add_argument("--run-dir", default="outputs/gepa_smoke")
    parser.add_argument("--generation-url", default="http://127.0.0.1:8010/v1")
    parser.add_argument("--evaluator-url", default="http://127.0.0.1:8011/v1")
    parser.add_argument("--reflector-url", default="http://127.0.0.1:8012/v1")
    parser.add_argument("--generation-model", default=DEFAULT_GENERATION_MODEL)
    parser.add_argument("--evaluator-model", default=DEFAULT_EVALUATOR_MODEL)
    parser.add_argument("--reflector-model", default=DEFAULT_REFLECTOR_MODEL)
    parser.add_argument("--max-metric-calls", type=int, default=3)
    parser.add_argument("--reflection-minibatch-size", type=int, default=1)
    parser.add_argument("--mock", action="store_true")
    args = parser.parse_args()

    config = load_yaml(Path(args.config))
    for model_key in (args.generation_model, args.evaluator_model, args.reflector_model):
        if model_key not in config["models"]:
            raise SystemExit(f"Model key not found in {args.config}: {model_key}")

    examples = load_prompt_examples(Path("prompts") / args.dataset, args.split, args.encounter_ids)
    gen_cfg = model_generation(config, args.generation_model)
    eval_cfg = model_generation(config, args.evaluator_model)
    reflect_cfg = model_generation(config, args.reflector_model)
    run_dir = Path(args.run_dir) / time.strftime("%Y%m%d-%H%M%S")
    run_dir.mkdir(parents=True, exist_ok=True)

    seed_prompt = examples[0].original_system_prompt

    def evaluator(candidate: Any, example_data: Example) -> tuple[float, dict[str, Any]]:
        candidate_prompt = candidate_to_prompt(candidate)
        generated_note = call_generation(candidate_prompt, example_data, args, gen_cfg)
        eval_json = call_evaluator(generated_note, example_data, args, eval_cfg)
        score = clamp_score(eval_json.get("score"))
        side_info = {
            "encounter_id": example_data.encounter_id,
            "score": score,
            "generated_note": generated_note,
            "evaluation": eval_json,
            "reflector_feedback": summarize_eval(eval_json),
        }
        try:
            import gepa.optimize_anything as oa

            oa.log(side_info["reflector_feedback"])
        except Exception:
            pass
        return score, side_info

    if args.mock:
        best_candidate = seed_prompt
        metric_calls = len(examples)
        mock_scores = [evaluator(seed_prompt, example)[0] for example in examples]
        optimization_summary = {"mode": "mock", "scores": mock_scores}
    else:
        from gepa.optimize_anything import EngineConfig, GEPAConfig, ReflectionConfig, optimize_anything

        result = optimize_anything(
            seed_candidate=seed_prompt,
            evaluator=evaluator,
            dataset=examples,
            objective="Improve the system prompt for generating complete, clinically accurate ACI-Bench notes.",
            background=(
                "The generation prompt must produce a comprehensive clinical note from a doctor-patient "
                "dialogue. The evaluator checks hallucinations, omissions, and clinical completeness. "
                "Do not optimize the evaluator prompt; optimize only the generation system prompt."
            ),
            config=GEPAConfig(
                engine=EngineConfig(
                    run_dir=str(run_dir / "gepa_state"),
                    max_metric_calls=args.max_metric_calls,
                    parallel=False,
                    max_workers=1,
                    capture_stdio=True,
                    display_progress_bar=True,
                ),
                reflection=ReflectionConfig(
                    reflection_lm=make_reflection_lm(args, reflect_cfg),
                    reflection_minibatch_size=args.reflection_minibatch_size,
                ),
            ),
        )
        best_candidate = getattr(result, "best_candidate", seed_prompt)
        metric_calls = getattr(result, "total_metric_calls", None)
        optimization_summary = {
            "mode": "gepa",
            "run_dir": getattr(result, "run_dir", None),
            "total_metric_calls": metric_calls,
        }

    best_prompt = candidate_to_prompt(best_candidate)
    final_outputs = []
    for example in examples:
        generated_note = call_generation(best_prompt, example, args, gen_cfg)
        eval_json = call_evaluator(generated_note, example, args, eval_cfg)
        final_outputs.append(
            {
                "encounter_id": example.encounter_id,
                "score": clamp_score(eval_json.get("score")),
                "generated_note": generated_note,
                "evaluation": eval_json,
            }
        )

    write_json(
        run_dir / "summary.json",
        {
            "dataset": args.dataset,
            "split": args.split,
            "encounter_ids": args.encounter_ids,
            "models": {
                "generation": args.generation_model,
                "evaluator": args.evaluator_model,
                "reflector": args.reflector_model,
            },
            "metric_calls": metric_calls,
            "optimization": optimization_summary,
            "final_outputs": final_outputs,
        },
    )
    (run_dir / "best_generation_system_prompt.txt").write_text(best_prompt)
    print(f"GEPA pipeline complete: {run_dir}")
    print(len(final_outputs))


if __name__ == "__main__":
    main()
