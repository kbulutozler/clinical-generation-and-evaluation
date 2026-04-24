#!/bin/bash
#SBATCH --job-name=hf-download
#SBATCH --partition=shared
#SBATCH --account=cis251377
#SBATCH --qos=cpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=01:00:00
#SBATCH --output=logs/hf-download-%j.out
#SBATCH --error=logs/hf-download-%j.err

set -euo pipefail

source "$HOME/.bash_env"

uv run --with huggingface_hub huggingface-cli download "$1"
