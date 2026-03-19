#!/bin/bash
#SBATCH --job-name=vllm-image-pull
#SBATCH --partition=cpu
#SBATCH --account=158415475357
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=02:00:00
#SBATCH --output=logs/image-install-%j.out
#SBATCH --error=logs/image-install-%j.err
#SBATCH --mail-type=END,FAIL
#SBATCH --mail-user=kbozler@arizona.edu

set -euo pipefail

source "$HOME/.bash_env"

mkdir -p $PROJ_USER/containers
mkdir -p $PROJ_USER/repositories/any-llm-inference/logs

singularity pull $PROJ_USER/containers/vllm.sif docker://vllm/vllm-openai:v0.17.1
