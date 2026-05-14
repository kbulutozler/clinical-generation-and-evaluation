#!/usr/bin/env python3
"""
Read vLLM load flags and generation params from configs/config.yaml.

Usage (one model):
  python3 gepa/servers/vllm_model_flags.py Qwen/Qwen3.5-2B --load
  # → ["--dtype","bfloat16","--max-model-len","32768",...]

  python3 gepa/servers/vllm_model_flags.py google/gemma-4-31B-it --generation
  # → {"temperature":1.0,"top_p":0.95,...}  (JSON object)

Usage (all GEPA models at once, for config generation):
  python3 gepa/servers/vllm_model_flags.py all --load
  # → {"Qwen/Qwen3.5-2B":["--dtype","bfloat16",...],"google/gemma-4-31B-it":[...]}

Serve plan (bind host/port + one process per distinct HF model on that bind):
  python3 gepa/servers/vllm_model_flags.py --serve-plan [path/to/gepa/config.yaml]
  # → {"listeners":[{"host":"127.0.0.1","port":8010,"model":"...","roles":["generation"],"primary_role":"generation"}, ...]}

Environment: reads gepa/config.yaml for model assignments and
configs/config.yaml for per-model load/generation sections.
"""

import json
import sys
from pathlib import Path
from urllib.parse import urlparse

import yaml


ROLES_ORDER = ("generation", "evaluator", "reflector")


def load_yaml(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def resolve_config_paths() -> tuple[str, str]:
    """Return (gepa_config, main_config) absolute paths."""
    repo_root = Path(__file__).resolve().parents[2]
    gepa_cfg = repo_root / "gepa" / "config.yaml"
    main_cfg = repo_root / "configs" / "config.yaml"
    return str(gepa_cfg), str(main_cfg)


def get_gepa_models(gepa_cfg: dict) -> dict[str, str]:
    """Return {role: huggingface_path} for the GEPA pipeline."""
    return {
        "generation": gepa_cfg["models"]["generation_model"],
        "evaluator": gepa_cfg["models"]["evaluator_model"],
        "reflector": gepa_cfg["models"]["reflector_model"],
    }


def openai_base_url_to_bind(openai_base: str) -> tuple[str, int]:
    """Return (host, port) for vLLM --host/--port from an OpenAI base URL (…/v1)."""
    u = urlparse(openai_base.strip().rstrip("/"))
    if not u.scheme or not u.hostname:
        raise ValueError(f"Invalid OpenAI base URL (need scheme + host): {openai_base!r}")
    if u.port is None:
        raise ValueError(
            f"OpenAI base URL must include an explicit port (got {openai_base!r}). "
            "Example: http://127.0.0.1:8010/v1"
        )
    return u.hostname, u.port


def build_serve_plan(gepa_cfg: dict | None = None) -> dict:
    """One vLLM process per distinct (host, port, model); roles list who shares it."""
    if gepa_cfg is None:
        gepa_cfg_path, _ = resolve_config_paths()
        gepa_cfg = load_yaml(gepa_cfg_path)
    models = get_gepa_models(gepa_cfg)
    ep = gepa_cfg["endpoints"]
    buckets: dict[tuple[str, int, str], list[str]] = {}
    for role in ROLES_ORDER:
        base = ep[f"{role}_url"]
        host, port = openai_base_url_to_bind(base)
        model = models[role]
        key = (host, port, model)
        buckets.setdefault(key, []).append(role)
    listeners: list[dict] = []
    for (host, port, model), roles in sorted(buckets.items(), key=lambda item: (item[0][1], item[0][0])):
        roles_sorted = sorted(roles, key=lambda r: ROLES_ORDER.index(r))
        listeners.append(
            {
                "host": host,
                "port": port,
                "model": model,
                "roles": roles_sorted,
                "primary_role": roles_sorted[0],
            }
        )
    return {"listeners": listeners}


def load_to_flags(load_cfg: dict) -> list[str]:
    """Convert a model's load section to a flat list of vLLM serve flags.

    null/None values are skipped (use the default).
    Boolean values are passed as flags with no value (e.g. --enforce-eager).
    All other keys use snake_case -> kebab-case conversion.
    """
    flags: list[str] = []
    for key, val in load_cfg.items():
        if val is None:
            continue
        flag_name = key.replace("_", "-")
        flags.append(f"--{flag_name}")
        if not isinstance(val, bool):
            flags.append(str(val))
        # boolean True: flag already added, no value needed
    return flags


def main():
    # Special mode: print GEPA model assignments from gepa/config.yaml
    if len(sys.argv) >= 2 and sys.argv[1] == "--models":
        gepa_cfg_path, _ = resolve_config_paths()
        gepa_cfg = load_yaml(gepa_cfg_path)
        models = get_gepa_models(gepa_cfg)
        print(json.dumps(models))
        return

    if len(sys.argv) >= 2 and sys.argv[1] == "--serve-plan":
        gepa_cfg_path, _ = resolve_config_paths()
        if len(sys.argv) >= 3 and not str(sys.argv[2]).startswith("-"):
            gepa_cfg_path = str(Path(sys.argv[2]).expanduser())
        print(json.dumps(build_serve_plan(load_yaml(gepa_cfg_path))))
        return

    if len(sys.argv) < 3:
        print("Usage: vllm_model_flags.py <model_path|all> --load|--generation", file=sys.stderr)
        print("       vllm_model_flags.py --models", file=sys.stderr)
        print("       vllm_model_flags.py --serve-plan [gepa/config.yaml]", file=sys.stderr)
        sys.exit(1)

    model_arg = sys.argv[1]
    mode = sys.argv[2]

    gepa_cfg_path, main_cfg_path = resolve_config_paths()
    main_cfg = load_yaml(main_cfg_path)

    if model_arg == "all":
        gepa_cfg = load_yaml(gepa_cfg_path)
        models = get_gepa_models(gepa_cfg)
        unique_models = list(set(models.values()))
        result = {}
        for m in unique_models:
            if mode == "--load":
                result[m] = load_to_flags(main_cfg["models"].get(m, {}).get("load", {}))
            elif mode == "--generation":
                result[m] = main_cfg["models"].get(m, {}).get("generation", {})
        print(json.dumps(result))
    else:
        model_cfg = main_cfg["models"].get(model_arg, {})
        if mode == "--load":
            flags = load_to_flags(model_cfg.get("load", {}))
            print(json.dumps(flags))
        elif mode == "--generation":
            print(json.dumps(model_cfg.get("generation", {})))


if __name__ == "__main__":
    main()
