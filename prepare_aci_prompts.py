import argparse
import csv
import json
import random
from pathlib import Path

from utils import load_config, get_dataset_path

CONFIG_PATH = Path("configs/config.yaml")
PROMPTS_DIR = Path("prompts")

SYSTEM_PROMPT = (
    "You are a clinical documentation specialist. "
    "Given a doctor-patient conversation, write a comprehensive clinical note."
)


def read_csv(path):
    with open(path) as f:
        return list(csv.DictReader(f))


def build_messages(test_sample, shot_examples):
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for ex in shot_examples:
        messages.append({"role": "user", "content": ex["dialogue"]})
        messages.append({"role": "assistant", "content": ex["note"]})
    messages.append({"role": "user", "content": test_sample["dialogue"]})
    return messages


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True, help="Dataset name as defined in configs/config.yaml (e.g. aci_bench)")
    parser.add_argument("--machine", default=None, choices=["anvil", "aces", "local"], help="Machine to resolve dataset path for (default: infer from hostname)")
    parser.add_argument("--test_split", default="clinicalnlp_taskB_test1")
    parser.add_argument("--shots", nargs="+", type=int, default=[0, 1, 2])
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    random.seed(args.seed)

    config = load_config(CONFIG_PATH)
    dataset_root = get_dataset_path(config, args.dataset, args.machine)
    data_dir = dataset_root / "data" / "challenge_data"
    train = read_csv(data_dir / "train.csv")
    test = read_csv(data_dir / f"{args.test_split}.csv")

    for n_shots in args.shots:
        out_dir = PROMPTS_DIR / "aci_bench" / f"{args.test_split}_{n_shots}shot"
        out_dir.mkdir(parents=True, exist_ok=True)

        for sample in test:
            shot_examples = random.sample(train, n_shots) if n_shots > 0 else []
            messages = build_messages(sample, shot_examples)
            payload = {
                "encounter_id": sample["encounter_id"],
                "messages": messages,
                "target": sample["note"],
            }
            (out_dir / f"{sample['encounter_id']}.json").write_text(json.dumps(payload, indent=2))

        print(f"{n_shots}-shot: {len(test)} prompts → {out_dir}")


if __name__ == "__main__":
    main()
