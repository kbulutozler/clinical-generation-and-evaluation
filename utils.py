from pathlib import Path
import yaml


def load_config(path: Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def read_prompt(path: Path) -> str:
    return path.read_text().strip()
