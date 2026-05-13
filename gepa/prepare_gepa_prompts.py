#!/usr/bin/env python3
"""
Prepare GEPA prompt JSON files from the original ACI-Bench repo.

Writes:
  prompts/<out_dataset>/<encounter_id>/<split>/prompt.json

Each prompt.json uses "{seed_prompt}" as the system message placeholder.
The default seed text for `run_gepa_pipeline.py` is `gepa/prompts/generation_seed_prompt.txt` (see `gepa/config.yaml`).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml


SEED_PROMPT_PLACEHOLDER = "{seed_prompt}"


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open() as handle:
        return yaml.safe_load(handle)


def aci_bench_dataset_root(config: dict[str, Any]) -> Path:
    datasets = config.get("datasets") or {}
    aci = datasets.get("aci_bench") or {}
    root = aci.get("local")
    if not root:
        raise SystemExit("Missing configs/config.yaml datasets.aci_bench.local.")
    return Path(str(root)).expanduser()


def load_rows(dataset_root: Path, split: str) -> list[dict[str, Any]]:
    path = dataset_root / "data" / "challenge_data_json" / f"{split}_full.json"
    if not path.exists():
        raise SystemExit(f"ACI-Bench file not found: {path}")
    payload = json.loads(path.read_text())
    rows = payload.get("data")
    if not isinstance(rows, list):
        raise SystemExit(f"Unexpected ACI-Bench schema at {path}: expected {{'data': [...]}}.")
    return rows


def row_to_encounter_id(file_field: str) -> str:
    return str(file_field).split("-", 1)[0]


def write_prompt_json(out_path: Path, encounter_id: str, dialogue: str, target: str) -> None:
    payload = {
        "encounter_id": encounter_id,
        "messages": [
            {"role": "system", "content": SEED_PROMPT_PLACEHOLDER},
            {"role": "user", "content": dialogue},
        ],
        "target": target,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/config.yaml")
    parser.add_argument("--out-dataset", default="gepa", help="Folder name under prompts/ (default: gepa)")
    args = parser.parse_args()

    config = load_yaml(Path(args.config))
    dataset_root = aci_bench_dataset_root(config)
    out_base = Path("prompts") / args.out_dataset

    written = 0
    for split in ("train", "valid"):
        rows = load_rows(dataset_root, split)

        for row in rows:
            if not isinstance(row, dict):
                continue
            encounter_id = row_to_encounter_id(str(row.get("file", "")))
            dialogue = str(row.get("src") or "").strip()
            target = str(row.get("tgt") or "").strip()
            if not encounter_id or not dialogue or not target:
                continue

            out_path = out_base / encounter_id / split / "prompt.json"
            write_prompt_json(out_path, encounter_id, dialogue, target)
            written += 1

    print(f"Wrote {written} prompt.json files under {out_base}")


if __name__ == "__main__":
    main()
