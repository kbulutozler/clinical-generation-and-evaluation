#!/bin/bash
#SBATCH --job-name=llm-inference
#SBATCH --partition=ai
#SBATCH --account=cis251377-ai
#SBATCH --qos=ai
#SBATCH --nodes=1
#SBATCH --gpus-per-node=1
#SBATCH --time=01:00:00
#SBATCH --output=logs/slurm-%j.out
#SBATCH --error=logs/slurm-%j.err

set -euo pipefail

shopt -s expand_aliases
source "$HOME/.bash_env"

cd "$SLURM_SUBMIT_DIR"
mkdir -p logs

vllm python3 run_chat_batch.py "$@"
