#!/bin/bash
#SBATCH --job-name=hf-download
#SBATCH --partition=cpu
#SBATCH --account=158415475357
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=01:00:00
#SBATCH --output=logs/hf-download-%j.out
#SBATCH --error=logs/hf-download-%j.err

set -euo pipefail

source "$HOME/.bash_env"

module load Miniconda3/23.10.0-1
eval "$(conda shell.bash hook)"
conda activate hf-download
hf download "$1"
