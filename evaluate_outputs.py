import json
import sys
import time
from datetime import datetime
from pathlib import Path

from vllm import LLM, SamplingParams

from utils import load_config, extract_thinking

CONFIG_PATH = Path("configs/config.yaml")


def fmt_time(seconds):
    m = int(seconds) // 60
    s = int(seconds) % 60
    return f"{m}m {s}s"


def main():
    if len(sys.argv) != 3:
        print("Usage: python3 evaluate_outputs.py <exp_dir> <eval_prompt_template>")
        print("  e.g. python3 evaluate_outputs.py outputs/20260423/Qwen3.5-4B/aci_bench/clinicalnlp_taskB_test1_0shot prompts/evaluation/eval_prompt_template.json")
        sys.exit(1)

    exp_dir = Path(sys.argv[1])
    eval_prompt_path = Path(sys.argv[2])

    if not eval_prompt_path.exists():
        print(f"Eval prompt template not found: {eval_prompt_path}")
        sys.exit(1)

    eval_prompt = json.loads(eval_prompt_path.read_text())
    system_prompt = eval_prompt["messages"][0]["content"]
    user_template = eval_prompt["messages"][1]["content"]

    enc_dirs = sorted([d for d in exp_dir.iterdir() if d.is_dir()])

    if not enc_dirs:
        print(f"No encounter directories found in {exp_dir}")
        sys.exit(1)

    config = load_config(CONFIG_PATH)
    eval_model_name = config["active_eval_model"]
    eval_model_cfg = config["models"][eval_model_name]
    enable_thinking = config.get("active_model_thinking", False)
    gen = eval_model_cfg["generation"]["thinking" if enable_thinking else "non_thinking"]

    # build messages for all encounters
    all_messages = []
    valid_dirs = []
    for enc_dir in enc_dirs:
        sourcedoc_path = enc_dir / "sourcedoc.txt"
        sourcetarget_path = enc_dir / "sourcetarget.txt"
        output_path = enc_dir / "output.txt"

        if not sourcedoc_path.exists() or not sourcetarget_path.exists() or not output_path.exists():
            print(f"[WARN] {enc_dir.name}: missing required files — skipping")
            continue

        user_content = user_template.format(
            sourcedoc=sourcedoc_path.read_text().strip(),
            sourcetarget=sourcetarget_path.read_text().strip(),
            generated_note=output_path.read_text().strip(),
        )
        all_messages.append([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ])
        valid_dirs.append(enc_dir)

    if not valid_dirs:
        print("No valid encounters to evaluate.")
        sys.exit(1)

    load_start = time.time()
    llm_kwargs = dict(
        model=eval_model_cfg["path"],
        dtype=eval_model_cfg["load"]["dtype"],
        tensor_parallel_size=eval_model_cfg["load"]["tensor_parallel_size"],
        gpu_memory_utilization=eval_model_cfg["load"]["gpu_memory_utilization"],
        max_model_len=eval_model_cfg["load"]["max_model_len"],
        enforce_eager=eval_model_cfg["load"].get("enforce_eager", False),
    )
    if "max_cudagraph_capture_size" in eval_model_cfg["load"]:
        llm_kwargs["max_cudagraph_capture_size"] = eval_model_cfg["load"]["max_cudagraph_capture_size"]
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

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    batch_metadata = {
        "timestamp": timestamp,
        "eval_model": eval_model_name,
        "eval_prompt": str(eval_prompt_path),
        "thinking": enable_thinking,
        "load": eval_model_cfg["load"],
        "generation": gen,
        "num_evaluated": len(valid_dirs),
        "model_load_time": load_time,
        "inference_time": infer_time,
    }
    (exp_dir / "_eval_batch_metadata.json").write_text(json.dumps(batch_metadata, indent=2))

    for i, (enc_dir, output) in enumerate(zip(valid_dirs, outputs)):
        output_text, thinking_text = extract_thinking(output.outputs[0].text or "")

        if thinking_text:
            (enc_dir / "eval_thinking.txt").write_text(thinking_text)
        (enc_dir / "eval_output.txt").write_text(output_text)

        print(f"[{i+1}/{len(valid_dirs)}] {enc_dir.name}")

    print(f"Done. Evaluated {len(valid_dirs)} encounters.")
    print(f"Model load: {load_time} | Inference: {infer_time}")


if __name__ == "__main__":
    main()
