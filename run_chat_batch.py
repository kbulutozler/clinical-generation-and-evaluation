import argparse
import json
import time
from datetime import datetime
from pathlib import Path

from utils import load_config, get_model_config, build_llm_kwargs, extract_thinking

CONFIG_PATH = Path("configs/config.yaml")
OUTPUTS_DIR = Path("outputs")


def fmt_time(seconds):
    m = int(seconds) // 60
    s = int(seconds) % 60
    return f"{m}m {s}s"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset", help="Dataset name under prompts/ (e.g. aci_bench)")
    parser.add_argument("testsplit_nshot", help="Prompt split directory name")
    parser.add_argument("encounter_id", nargs="?", help="Optional encounter_id to run")
    parser.add_argument(
        "--model",
        default=None,
        help="Optional model key from configs/config.yaml; overrides active_model",
    )
    args = parser.parse_args()

    dataset_name = args.dataset
    exp_name = args.testsplit_nshot
    encounter_id_filter = args.encounter_id
    prompts_root = Path("prompts") / dataset_name

    if encounter_id_filter:
        target = prompts_root / encounter_id_filter / exp_name / "prompt.json"
        if not target.exists():
            print(f"No prompt found for encounter_id '{encounter_id_filter}' at {target}")
            sys.exit(1)
        prompt_files = [target]
    else:
        prompt_files = sorted(prompts_root.glob(f"*/{exp_name}/prompt.json"))

    if not prompt_files:
        print(f"No prompt files found under {prompts_root} for {exp_name}")
        raise SystemExit(1)

    config = load_config(CONFIG_PATH)
    try:
        model = get_model_config(config, args.model)
    except ValueError as exc:
        parser.error(str(exc))
    enable_thinking = config.get("active_model_thinking", False)

    payloads = [json.loads(f.read_text()) for f in prompt_files]
    all_messages = [p["messages"] for p in payloads]

    gen = model["generation"]["thinking" if enable_thinking else "non_thinking"]

    from vllm import LLM, SamplingParams

    llm_kwargs = build_llm_kwargs(model)
    load_start = time.time()
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

    timestamp = datetime.now().strftime("%Y%m%d")
    model_short = model["modelname"]
    run_dir = OUTPUTS_DIR / timestamp / dataset_name
    metadata_dir = run_dir / "_batch_metadata" / model_short
    metadata_dir.mkdir(parents=True, exist_ok=True)

    batch_metadata = {
        "timestamp": timestamp,
        "model": model["name"],
        "modelname": model_short,
        "model_override": args.model,
        "dataset": dataset_name,
        "testsplit_nshot": exp_name,
        "thinking": enable_thinking,
        "load": model["load"],
        "generation": gen,
        "num_prompts": len(prompt_files),
        "prompt_files": [str(path) for path in prompt_files],
        "model_load_time": load_time,
        "inference_time": infer_time,
    }
    (metadata_dir / f"{exp_name}.json").write_text(json.dumps(batch_metadata, indent=2))

    for i, (payload, output) in enumerate(zip(payloads, outputs)):
        enc_id = payload["encounter_id"]
        output_text, thinking_text = extract_thinking(output.outputs[0].text or "")

        if not output_text:
            print(f"[WARN] {enc_id}: empty response from model — skipping")
            continue

        out_dir = run_dir / enc_id / model_short / exp_name
        out_dir.mkdir(parents=True, exist_ok=True)

        (out_dir / "output.txt").write_text(output_text)
        if thinking_text:
            (out_dir / "thinking.txt").write_text(thinking_text)
        (out_dir / "sourcedoc.txt").write_text(payload["messages"][-1]["content"])
        target = payload.get("target", "")
        if target:
            (out_dir / "sourcetarget.txt").write_text(target)

        print(f"[{i+1}/{len(prompt_files)}] {enc_id}")

    print(f"Done. Outputs saved to {run_dir}")


if __name__ == "__main__":
    main()
