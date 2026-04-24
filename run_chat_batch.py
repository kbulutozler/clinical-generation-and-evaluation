import json
import sys
import time
from datetime import datetime
from pathlib import Path

from vllm import LLM, SamplingParams

from utils import load_config, get_model_config, extract_thinking

CONFIG_PATH = Path("configs/config.yaml")
OUTPUTS_DIR = Path("outputs")


def fmt_time(seconds):
    m = int(seconds) // 60
    s = int(seconds) % 60
    return f"{m}m {s}s"


def main():
    if len(sys.argv) not in (2, 3):
        print("Usage: python3 run_chat_batch.py <prompts_dir> [encounter_id]")
        sys.exit(1)

    prompts_dir = Path(sys.argv[1])
    encounter_id_filter = sys.argv[2] if len(sys.argv) == 3 else None

    if encounter_id_filter:
        target = prompts_dir / f"{encounter_id_filter}.json"
        if not target.exists():
            print(f"No file found for encounter_id '{encounter_id_filter}' in {prompts_dir}")
            sys.exit(1)
        prompt_files = [target]
    else:
        prompt_files = sorted(prompts_dir.glob("*.json"))

    if not prompt_files:
        print(f"No JSON files found in {prompts_dir}")
        sys.exit(1)

    config = load_config(CONFIG_PATH)
    model = get_model_config(config)
    enable_thinking = config.get("active_model_thinking", False)

    payloads = [json.loads(f.read_text()) for f in prompt_files]
    all_messages = [p["messages"] for p in payloads]

    gen = model["generation"]["thinking" if enable_thinking else "non_thinking"]

    load_start = time.time()
    llm_kwargs = dict(
        model=model["path"],
        dtype=model["load"]["dtype"],
        tensor_parallel_size=model["load"]["tensor_parallel_size"],
        gpu_memory_utilization=model["load"]["gpu_memory_utilization"],
        max_model_len=model["load"]["max_model_len"],
        enforce_eager=model["load"].get("enforce_eager", False),
    )
    if "max_cudagraph_capture_size" in model["load"]:
        llm_kwargs["max_cudagraph_capture_size"] = model["load"]["max_cudagraph_capture_size"]
    llm = LLM(**llm_kwargs)
    load_time = fmt_time(time.time() - load_start)

    sampling_params = SamplingParams(
        temperature=gen["temperature"],
        top_p=gen["top_p"],
        top_k=gen["top_k"],
        min_p=gen["min_p"],
        presence_penalty=gen["presence_penalty"],
        repetition_penalty=gen["repetition_penalty"],
        max_tokens=gen["max_tokens"],
    )

    infer_start = time.time()
    outputs = llm.chat(all_messages, sampling_params,
                       chat_template_kwargs={"enable_thinking": enable_thinking})
    infer_time = fmt_time(time.time() - infer_start)

    date = datetime.now().strftime("%Y%m%d")
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    model_short = model["modelname"]
    dataset_name = prompts_dir.parent.name
    exp_name = prompts_dir.name
    exp_dir = OUTPUTS_DIR / date / model_short / dataset_name / exp_name
    exp_dir.mkdir(parents=True, exist_ok=True)

    batch_metadata = {
        "timestamp": timestamp,
        "model": model["name"],
        "thinking": enable_thinking,
        "load": model["load"],
        "generation": gen,
        "num_prompts": len(prompt_files),
        "model_load_time": load_time,
        "inference_time": infer_time,
    }
    (exp_dir / "_batch_metadata.json").write_text(json.dumps(batch_metadata, indent=2))

    for i, (payload, output) in enumerate(zip(payloads, outputs)):
        enc_id = payload["encounter_id"]
        output_text, thinking_text = extract_thinking(output.outputs[0].text or "")

        if not output_text:
            print(f"[WARN] {enc_id}: empty response from model — skipping")
            continue

        out_dir = exp_dir / enc_id
        out_dir.mkdir(parents=True, exist_ok=True)

        (out_dir / "output.txt").write_text(output_text)
        if thinking_text:
            (out_dir / "thinking.txt").write_text(thinking_text)
        (out_dir / "sourcedoc.txt").write_text(payload["messages"][-1]["content"])
        target = payload.get("target", "")
        if target:
            (out_dir / "sourcetarget.txt").write_text(target)

        print(f"[{i+1}/{len(prompt_files)}] {enc_id}")

    print(f"Done. Outputs saved to {exp_dir}")


if __name__ == "__main__":
    main()
