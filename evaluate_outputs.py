import json
import sys
import time
import argparse
from datetime import datetime
from pathlib import Path

from utils import load_config, build_llm_kwargs, extract_thinking

CONFIG_PATH = Path("configs/config.yaml")
FINAL_OUTPUTS_DIR = Path("outputs") / "final"


def fmt_time(seconds):
    m = int(seconds) // 60
    s = int(seconds) % 60
    return f"{m}m {s}s"


def discover_generation_outputs(dataset_dir):
    entries = []
    for output_path in sorted(dataset_dir.glob("*/*/*/output.txt")):
        leaf_dir = output_path.parent
        try:
            encounter_id, modelname, testsplit_nshot = leaf_dir.relative_to(dataset_dir).parts
        except ValueError:
            continue
        entries.append({
            "encounter_id": encounter_id,
            "modelname": modelname,
            "testsplit_nshot": testsplit_nshot,
            "leaf_dir": leaf_dir,
            "output_path": output_path,
        })
    return sorted(entries, key=lambda item: (item["encounter_id"], item["modelname"], item["testsplit_nshot"]))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset", help="Dataset name under outputs/final (e.g. aci_bench)")
    parser.add_argument("eval_prompt_template", help="Evaluation prompt template JSON")
    args = parser.parse_args()

    dataset_dir = FINAL_OUTPUTS_DIR / args.dataset
    eval_prompt_path = Path(args.eval_prompt_template)

    if not eval_prompt_path.exists():
        print(f"Eval prompt template not found: {eval_prompt_path}")
        sys.exit(1)
    if not dataset_dir.exists():
        print(f"Final dataset output directory not found: {dataset_dir}")
        sys.exit(1)

    eval_prompt = json.loads(eval_prompt_path.read_text())
    system_prompt = eval_prompt["messages"][0]["content"]
    user_template = eval_prompt["messages"][1]["content"]

    config = load_config(CONFIG_PATH)
    eval_model_name = config["active_eval_model"]
    eval_model_cfg = config["models"][eval_model_name]
    eval_model_short = eval_model_cfg["modelname"]
    enable_thinking = config.get("active_model_thinking", False)
    gen = eval_model_cfg["generation"]["thinking" if enable_thinking else "non_thinking"]

    entries = discover_generation_outputs(dataset_dir)

    if not entries:
        print(f"No generation outputs found under {dataset_dir}")
        sys.exit(1)

    all_messages = []
    valid_entries = []
    for entry in entries:
        leaf_dir = entry["leaf_dir"]
        sourcedoc_path = leaf_dir / "sourcedoc.txt"
        sourcetarget_path = leaf_dir / "sourcetarget.txt"
        output_path = entry["output_path"]

        if not sourcedoc_path.exists() or not sourcetarget_path.exists() or not output_path.exists():
            rel_leaf = leaf_dir.relative_to(dataset_dir)
            print(f"[WARN] {rel_leaf}: missing required files; skipping")
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
        valid_entries.append(entry)

    if not valid_entries:
        print("No valid generation outputs to evaluate.")
        sys.exit(1)

    from vllm import LLM, SamplingParams

    llm_kwargs = build_llm_kwargs(eval_model_cfg)
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

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    batch_metadata = {
        "timestamp": timestamp,
        "eval_model": eval_model_name,
        "eval_modelname": eval_model_short,
        "dataset": args.dataset,
        "base_dir": str(FINAL_OUTPUTS_DIR),
        "eval_prompt": str(eval_prompt_path),
        "thinking": enable_thinking,
        "load": eval_model_cfg["load"],
        "generation": gen,
        "num_evaluated": len(valid_entries),
        "evaluated_outputs": [
            str(entry["leaf_dir"].relative_to(FINAL_OUTPUTS_DIR))
            for entry in valid_entries
        ],
        "model_load_time": load_time,
        "inference_time": infer_time,
    }
    eval_batch_dir = dataset_dir / "evals" / eval_model_short
    eval_batch_dir.mkdir(parents=True, exist_ok=True)
    (eval_batch_dir / "_eval_batch_metadata.json").write_text(json.dumps(batch_metadata, indent=2))

    for i, (entry, output) in enumerate(zip(valid_entries, outputs)):
        output_text, thinking_text = extract_thinking(output.outputs[0].text or "")

        eval_dir = entry["leaf_dir"] / "evals" / eval_model_short
        eval_dir.mkdir(parents=True, exist_ok=True)
        if thinking_text:
            (eval_dir / "eval_thinking.txt").write_text(thinking_text)
        (eval_dir / "eval_output.txt").write_text(output_text)

        label = f"{entry['encounter_id']} {entry['modelname']} {entry['testsplit_nshot']}"
        print(f"[{i+1}/{len(valid_entries)}] {label}")

    print(f"Done. Evaluated {len(valid_entries)} generation outputs.")
    print(f"Model load: {load_time} | Inference: {infer_time}")


if __name__ == "__main__":
    main()
