#!/bin/bash
#SBATCH --job-name=conda-install
#SBATCH --partition=gpu
#SBATCH --account=158415475357
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gres=gpu:h100:1
#SBATCH --time=04:00:00
#SBATCH --output=logs/install-%j.out
#SBATCH --error=logs/install-%j.err
#SBATCH --mail-type=END,FAIL
#SBATCH --mail-user=kbozler@arizona.edu

set -euo pipefail

source "$HOME/.bash_env"
source "$(conda info --base)/etc/profile.d/conda.sh"

cd $PROJ_USER/repositories/any-llm-inference
mkdir -p logs

conda activate vllm
pip install vllm pyyaml
