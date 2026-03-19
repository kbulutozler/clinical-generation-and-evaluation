import json
import sys
from datetime import datetime
from pathlib import Path
from urllib import request, error

from utils import load_config, read_prompt

CONFIG_PATH = Path("configs/config.yaml")
PROMPTS_DIR = Path("prompts")
OUTPUTS_DIR = Path("outputs")
SERVER_URL = "http://127.0.0.1:8000/v1/completions"


def main():
    if len(sys.argv) != 2:
        print("Usage: python3 query.py <prompt_filename>")
        sys.exit(1)

    prompt_name = sys.argv[1]
    if not prompt_name.endswith(".txt"):
        prompt_name += ".txt"

    config = load_config(CONFIG_PATH)
    prompt = read_prompt(PROMPTS_DIR / prompt_name)

    payload = json.dumps({
        "model": config["model"]["name"],
        "prompt": prompt,
        "temperature": config["generation"]["temperature"],
        "top_p": config["generation"]["top_p"],
        "max_tokens": config["generation"]["max_tokens"],
    }).encode()

    req = request.Request(SERVER_URL, data=payload, headers={"Content-Type": "application/json"})
    with request.urlopen(req) as resp:
        result = json.loads(resp.read())

    output_text = result["choices"][0]["text"]

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    prompt_stem = Path(prompt_name).stem
    out_dir = OUTPUTS_DIR / timestamp / prompt_stem
    out_dir.mkdir(parents=True, exist_ok=True)

    (out_dir / "output.txt").write_text(output_text)

    metadata = {
        "timestamp": timestamp,
        "prompt_file": prompt_name,
        "model": config["model"],
        "generation": config["generation"],
    }
    (out_dir / "metadata.json").write_text(json.dumps(metadata, indent=2))

    print(f"Output saved to {out_dir}")


if __name__ == "__main__":
    main()
