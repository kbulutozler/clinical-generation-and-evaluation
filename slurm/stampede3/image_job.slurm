#!/bin/bash
#SBATCH --job-name=llm-inference
#SBATCH --partition=h100
#SBATCH --account=TG-CIS251377
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=00:45:00
#SBATCH --output=logs/slurm-%j.out
#SBATCH --error=logs/slurm-%j.err

set -euo pipefail

shopt -s expand_aliases
source "$HOME/.bash_env"

cd "$SLURM_SUBMIT_DIR"
mkdir -p logs
nvidia-smi

vllm python3 run_chat_batch.py "$@"
