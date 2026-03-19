import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

from vllm import LLM, SamplingParams

from utils import load_config, read_prompt

CONFIG_PATH = Path("configs/config.yaml")
PROMPTS_DIR = Path("prompts")
OUTPUTS_DIR = Path("outputs")
JOB_SLURM_PATH = Path("job.slurm")


def main():
    if len(sys.argv) != 2:
        print("Usage: python run.py <prompt_filename>")
        sys.exit(1)

    prompt_name = sys.argv[1]
    if not prompt_name.endswith(".txt"):
        prompt_name += ".txt"

    config = load_config(CONFIG_PATH)
    prompt = read_prompt(PROMPTS_DIR / prompt_name)

    llm = LLM(
        model=config["model"]["path"],
        dtype=config["load"]["dtype"],
        tensor_parallel_size=config["load"]["tensor_parallel_size"],
        gpu_memory_utilization=config["load"]["gpu_memory_utilization"],
        max_model_len=config["load"]["max_model_len"],
    )

    sampling_params = SamplingParams(
        temperature=config["generation"]["temperature"],
        top_p=config["generation"]["top_p"],
        max_tokens=config["generation"]["max_tokens"],
    )

    outputs = llm.generate([prompt], sampling_params)
    output_text = outputs[0].outputs[0].text

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    prompt_stem = Path(prompt_name).stem
    out_dir = OUTPUTS_DIR / timestamp / prompt_stem
    out_dir.mkdir(parents=True, exist_ok=True)

    (out_dir / "output.txt").write_text(output_text)

    metadata = {
        "timestamp": timestamp,
        "prompt_file": prompt_name,
        "model": config["model"],
        "load": config["load"],
        "generation": config["generation"],
    }
    (out_dir / "metadata.json").write_text(json.dumps(metadata, indent=2))

    if JOB_SLURM_PATH.exists():
        shutil.copy(JOB_SLURM_PATH, out_dir / "job.slurm")

    print(f"Output saved to {out_dir}")


if __name__ == "__main__":
    main()
