#!/usr/bin/env bash
set -euo pipefail

shopt -s expand_aliases
source "$HOME/.bash_env"

mkdir -p logs/gepa gepa/pids

GENERATION_MODEL="${GENERATION_MODEL:-Qwen/Qwen3.5-2B}"
EVALUATOR_MODEL="${EVALUATOR_MODEL:-google/gemma-4-E4B-it}"
REFLECTOR_MODEL="${REFLECTOR_MODEL:-google/gemma-4-26B-A4B-it}"

GENERATION_PORT="${GENERATION_PORT:-8010}"
EVALUATOR_PORT="${EVALUATOR_PORT:-8011}"
REFLECTOR_PORT="${REFLECTOR_PORT:-8012}"

GENERATION_GPU="${GENERATION_GPU:-0}"
EVALUATOR_GPU="${EVALUATOR_GPU:-0}"
REFLECTOR_GPU="${REFLECTOR_GPU:-1}"

MAX_MODEL_LEN="${MAX_MODEL_LEN:-8192}"
SMALL_GPU_MEMORY_UTILIZATION="${SMALL_GPU_MEMORY_UTILIZATION:-0.32}"
EVAL_GPU_MEMORY_UTILIZATION="${EVAL_GPU_MEMORY_UTILIZATION:-0.48}"
REFLECTOR_GPU_MEMORY_UTILIZATION="${REFLECTOR_GPU_MEMORY_UTILIZATION:-0.90}"

start_server() {
  local role="$1"
  local gpu="$2"
  local port="$3"
  local model="$4"
  local mem_util="$5"
  shift 5

  local log_path="logs/gepa/${role}.log"
  local pid_path="gepa/pids/${role}.pid"

  echo "Starting ${role} on GPU ${gpu}, port ${port}: ${model}"
  CUDA_VISIBLE_DEVICES="${gpu}" vllm_latest vllm serve "${model}" \
    --served-model-name "${model}" \
    --host 127.0.0.1 \
    --port "${port}" \
    --dtype bfloat16 \
    --max-model-len "${MAX_MODEL_LEN}" \
    --gpu-memory-utilization "${mem_util}" \
    --disable-log-requests \
    "$@" >"${log_path}" 2>&1 &
  echo "$!" >"${pid_path}"
}

start_server generation "${GENERATION_GPU}" "${GENERATION_PORT}" "${GENERATION_MODEL}" "${SMALL_GPU_MEMORY_UTILIZATION}" \
  --max-num-seqs 16

start_server evaluator "${EVALUATOR_GPU}" "${EVALUATOR_PORT}" "${EVALUATOR_MODEL}" "${EVAL_GPU_MEMORY_UTILIZATION}" \
  --max-num-seqs 16

start_server reflector "${REFLECTOR_GPU}" "${REFLECTOR_PORT}" "${REFLECTOR_MODEL}" "${REFLECTOR_GPU_MEMORY_UTILIZATION}" \
  --max-num-seqs 8 \
  --kv-cache-dtype fp8

echo "PIDs:"
cat gepa/pids/*.pid
echo
echo "Waiting for OpenAI-compatible servers..."
python3 gepa/check_vllm_servers.py --timeout-seconds "${SERVER_TIMEOUT_SECONDS:-1200}" --skip-chat
echo "All model endpoints are ready."
