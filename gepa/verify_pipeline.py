#!/usr/bin/env python3
"""Static verifier for the GEPA pipeline files."""

from __future__ import annotations

import json
import py_compile
from pathlib import Path


REQUIRED = [
    Path("gepa/run_gepa_pipeline.py"),
    Path("gepa/check_vllm_servers.py"),
    Path("gepa/start_vllm_servers.sh"),
    Path("gepa/stop_vllm_servers.sh"),
    Path("gepa/evaluator_prompt_template.json"),
    Path("gepa/RUNBOOK.md"),
]


def main() -> None:
    passed = 0
    for path in REQUIRED:
        if not path.exists():
            raise SystemExit(f"Missing required file: {path}")
        passed += 1

    for path in (Path("gepa/run_gepa_pipeline.py"), Path("gepa/check_vllm_servers.py")):
        py_compile.compile(str(path), doraise=True)
        passed += 1

    prompt = json.loads(Path("gepa/evaluator_prompt_template.json").read_text())
    rendered = prompt["messages"][1]["content"].format(
        sourcedoc="dialogue",
        sourcetarget="reference",
        generated_note="generated",
    )
    if "dialogue" not in rendered or "generated" not in rendered:
        raise SystemExit("Evaluator template placeholders did not render.")
    passed += 1

    runbook = Path("gepa/RUNBOOK.md").read_text()
    for token in (
        "sinteractive -p ai",
        "--gpus-per-node=2",
        "gepa/start_vllm_servers.sh",
        "gepa/run_gepa_pipeline.py",
        "Qwen/Qwen3.5-2B",
        "google/gemma-4-E4B-it",
        "google/gemma-4-26B-A4B-it",
    ):
        if token not in runbook:
            raise SystemExit(f"Runbook missing token: {token}")
    passed += 1

    print(passed)


if __name__ == "__main__":
    main()
