#!/bin/bash
#SBATCH --job-name=vllm-image-pull
#SBATCH --partition=spr
#SBATCH --account=TG-CIS251377
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --time=02:00:00
#SBATCH --output=logs/image-install-%j.out
#SBATCH --error=logs/image-install-%j.err
#SBATCH --mail-type=END,FAIL
#SBATCH --mail-user=kbulutozler@gmail.com

set -euo pipefail

source "$HOME/.bash_env"

mkdir -p "$PROJ_USER/containers"
mkdir -p "$SLURM_SUBMIT_DIR/logs"

apptainer pull "$PROJ_USER/containers/vllm.sif" docker://vllm/vllm-openai:v0.17.1
