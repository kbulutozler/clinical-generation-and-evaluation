#!/bin/bash
#SBATCH --job-name=llm-inference
#SBATCH --partition=gpu
#SBATCH --account=cis251377
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --gpus-per-node=1
#SBATCH --time=01:00:00
#SBATCH --output=logs/slurm-%j.out
#SBATCH --error=logs/slurm-%j.err

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_DIR"

mkdir -p logs

source "$HOME/.bash_env"

conda run -n vllm python run.py "$1"
