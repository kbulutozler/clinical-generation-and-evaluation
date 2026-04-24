from pathlib import Path
import yaml


def load_config(path: Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def get_dataset_path(config: dict, dataset: str, machine: str) -> Path:
    """Resolve dataset path for the given machine (anvil, aces, local)."""
    paths = config["datasets"][dataset]
    if machine not in paths:
        raise ValueError(f"Unknown dataset path for machine '{machine}' — add a path entry to configs/config.yaml under datasets.{dataset}")
    return Path(paths[machine]).expanduser()


def get_model_config(config: dict) -> dict:
    """Return the active model's config with name injected."""
    name = config["active_model"]
    model_cfg = config["models"][name]
    return {"name": name, **model_cfg}


def extract_thinking(output_text: str):
    """Split output on </think>: everything before is thinking, everything after is response."""
    if "</think>" in output_text:
        thinking_text, output_text = output_text.split("</think>", 1)
        thinking_text = thinking_text.replace("<think>", "").strip()
        output_text = output_text.strip()
    else:
        thinking_text = ""
    return output_text, thinking_text
