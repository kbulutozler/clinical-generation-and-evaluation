#!/bin/bash
#SBATCH --job-name=llm-inference
#SBATCH --partition=gpu
#SBATCH --account=158415475357
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gres=gpu:h100:1
#SBATCH --time=01:00:00
#SBATCH --output=logs/slurm-%j.out
#SBATCH --error=logs/slurm-%j.err

set -euo pipefail

source "$HOME/.bash_env"

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_DIR"

mkdir -p logs

conda run -n vllm python run.py "$1"
