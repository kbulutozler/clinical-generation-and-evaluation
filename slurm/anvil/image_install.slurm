#!/bin/bash
#SBATCH --job-name=vllm-image-pull
#SBATCH --partition=shared
#SBATCH --account=cis251377
#SBATCH --qos=cpu
#SBATCH --nodes=1
#SBATCH --time=02:00:00
#SBATCH --output=logs/image-install-%j.out
#SBATCH --error=logs/image-install-%j.err
#SBATCH --mail-type=END,FAIL
#SBATCH --mail-user=kbozler@arizona.edu

set -euo pipefail

source "$HOME/.bash_env"

mkdir -p $SCRATCH/containers
mkdir -p $PROJ_USER/repositories/any-llm-inference/logs

apptainer pull $SCRATCH/containers/vllm.sif docker://vllm/vllm-openai:v0.17.1
