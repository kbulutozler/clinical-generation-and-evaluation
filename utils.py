from pathlib import Path
import yaml


def load_config(path: Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def get_local_dataset_path(config: dict, dataset: str) -> Path:
    """Resolve the local dataset path used for prompt building."""
    paths = config["datasets"][dataset]
    if "local" not in paths:
        raise ValueError(f"Missing local dataset path in configs/config.yaml under datasets.{dataset}")
    return Path(paths["local"]).expanduser()


def get_named_model_config(config: dict, name: str) -> dict:
    """Return a named model's config with name injected."""
    if name not in config["models"]:
        available = ", ".join(sorted(config["models"]))
        raise ValueError(f"Unknown model '{name}'. Available models: {available}")
    model_cfg = config["models"][name]
    return {"name": name, **model_cfg}


def get_model_config(config: dict, name: str | None = None) -> dict:
    """Return the active or overridden generation model config."""
    return get_named_model_config(config, name or config["active_model"])


def get_eval_model_config(config: dict, name: str | None = None) -> dict:
    """Return the active or overridden evaluator model config."""
    return get_named_model_config(config, name or config["active_eval_model"])


def build_llm_kwargs(model_cfg: dict) -> dict:
    """Build vLLM LLM kwargs from a model config."""
    load_cfg = model_cfg["load"]
    llm_kwargs = {
        "model": model_cfg["path"],
        "dtype": load_cfg["dtype"],
        "tensor_parallel_size": load_cfg["tensor_parallel_size"],
        "gpu_memory_utilization": load_cfg["gpu_memory_utilization"],
        "max_model_len": load_cfg["max_model_len"],
    }
    optional_load_keys = (
        "max_cudagraph_capture_size",
        "max_num_seqs",
        "kv_cache_dtype",
        "calculate_kv_scales",
        "enforce_eager",
    )
    llm_kwargs.update({
        key: load_cfg[key]
        for key in optional_load_keys
        if key in load_cfg and load_cfg[key] is not None
    })
    return llm_kwargs


def extract_thinking(output_text: str):
    """Split thinking traces from model output when known delimiters are present."""
    if "</think>" in output_text:
        thinking_text, output_text = output_text.split("</think>", 1)
        thinking_text = thinking_text.replace("<think>", "").strip()
        return output_text.strip(), thinking_text.strip()

    gemma_start = "<|channel>thought"
    gemma_end = "<channel|>"
    if output_text.startswith(gemma_start) and gemma_end in output_text:
        thinking_text, output_text = output_text[len(gemma_start):].split(gemma_end, 1)
        return output_text.strip(), thinking_text.strip()

    return output_text, ""
