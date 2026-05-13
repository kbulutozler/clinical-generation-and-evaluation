#!/usr/bin/env python3
"""Static verifier for the GEPA pipeline files."""

from __future__ import annotations

import json
import py_compile
from pathlib import Path


REQUIRED = [
    Path("gepa/run_gepa_pipeline.py"),
    Path("gepa/servers/check_vllm_servers.py"),
    Path("gepa/servers/vllm_model_flags.py"),
    Path("gepa/plot_gepa_run.py"),
    Path("gepa/prepare_gepa_prompts.py"),
    Path("gepa/servers/start_vllm_servers.sh"),
    Path("gepa/servers/stop_vllm_servers.sh"),
    Path("gepa/prompts/evaluator_prompt_template.json"),
    Path("gepa/prompts/generation_seed_prompt.txt"),
    Path("gepa/config.yaml"),
    Path("gepa/README.md"),
    Path("gepa/docs/RUNBOOK.md"),
]


def main() -> None:
    passed = 0
    for path in REQUIRED:
        if not path.exists():
            raise SystemExit(f"Missing required file: {path}")
        passed += 1

    for path in (
        Path("gepa/run_gepa_pipeline.py"),
        Path("gepa/servers/check_vllm_servers.py"),
        Path("gepa/servers/vllm_model_flags.py"),
        Path("gepa/plot_gepa_run.py"),
        Path("gepa/prepare_gepa_prompts.py"),
    ):
        py_compile.compile(str(path), doraise=True)
        passed += 1

    prompt = json.loads(Path("gepa/prompts/evaluator_prompt_template.json").read_text())
    rendered = prompt["messages"][1]["content"].format(
        source="dialogue",
        target="reference",
        generated_target="generated",
    )
    if "dialogue" not in rendered or "generated" not in rendered:
        raise SystemExit("Evaluator template placeholders did not render.")
    passed += 1

    import yaml

    gepa_config = yaml.safe_load(Path("gepa/config.yaml").read_text())
    if gepa_config["data"]["dataset"] != "gepa":
        raise SystemExit("GEPA config should use prepared prompts dataset: gepa")
    passed += 1

    runbook = Path("gepa/docs/RUNBOOK.md").read_text()
    for token in (
        "sinteractive -p ai",
        "--gpus-per-node=2",
        "gepa/servers/start_vllm_servers.sh",
        "gepa/run_gepa_pipeline.py",
        "traces/rollouts.jsonl",
        "gepa/prepare_gepa_prompts.py",
        "--gepa-config gepa/config.yaml",
        "vllm_model_flags.py --serve-plan",
        "config_snapshot",
    ):
        if token not in runbook:
            raise SystemExit(f"Runbook missing token: {token}")
    passed += 1

    readme = Path("gepa/README.md").read_text()
    for token in ("prepare_gepa_prompts.py", "run_gepa_pipeline.py", "config.yaml", "plot_gepa_run.py"):
        if token not in readme:
            raise SystemExit(f"README missing token: {token}")
    passed += 1

    print(passed)


if __name__ == "__main__":
    main()
