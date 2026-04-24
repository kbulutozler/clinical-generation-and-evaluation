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

source "$HOME/.bash_env"

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_DIR"

mkdir -p logs

apptainer exec --nv --env HF_HOME=$HF_HOME --env CC=gcc $SCRATCH/containers/vllm.sif python3 run_chat_batch.py "$1"
