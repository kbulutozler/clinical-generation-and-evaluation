#!/usr/bin/env bash
set -euo pipefail

shopt -s expand_aliases
source "$HOME/.bash_env"

mkdir -p logs/gepa gepa/servers/pids

UV="uv run --python 3.12 --with pyyaml --"

# Bind addresses and models come from gepa/config.yaml (via --serve-plan).
SERVE_PLAN_JSON=$(${UV} python3 gepa/servers/vllm_model_flags.py --serve-plan)

start_server() {
  local primary_role="$1"
  local gpu="$2"
  local host="$3"
  local port="$4"
  local model="$5"
  local roles_csv="$6"
  shift 6

  local log_path="logs/gepa/${primary_role}.log"
  local pid_path="gepa/servers/pids/${primary_role}.pid"

  echo "Starting listener roles=[${roles_csv}] primary=${primary_role} on GPU ${gpu}, ${host}:${port}: ${model}"
  local flags_json
  flags_json=$(${UV} python3 gepa/servers/vllm_model_flags.py "${model}" --load)
  local flags
  flags=$(echo "${flags_json}" | python3 -c "import sys,json; print(' '.join(json.load(sys.stdin)))")

  echo "  vLLM flags: ${flags}"
  CUDA_VISIBLE_DEVICES="${gpu}" vllm_latest vllm serve "${model}" \
    --served-model-name "${model}" \
    --host "${host}" \
    --port "${port}" \
    ${flags} \
    "$@" >"${log_path}" 2>&1 &
  echo "$!" >"${pid_path}"
}

gpu_for_primary() {
  case "$1" in
    generation) echo "${GENERATION_GPU:-0}" ;;
    evaluator) echo "${EVALUATOR_GPU:-1}" ;;
    reflector) echo "${REFLECTOR_GPU:-2}" ;;
    *) echo "0" ;;
  esac
}

while IFS= read -r listener_json; do
  [ -z "${listener_json}" ] && continue
  primary_role=$(echo "${listener_json}" | python3 -c "import json,sys; print(json.load(sys.stdin)['primary_role'])")
  host=$(echo "${listener_json}" | python3 -c "import json,sys; print(json.load(sys.stdin)['host'])")
  port=$(echo "${listener_json}" | python3 -c "import json,sys; print(json.load(sys.stdin)['port'])")
  model=$(echo "${listener_json}" | python3 -c "import json,sys; print(json.load(sys.stdin)['model'])")
  roles=$(echo "${listener_json}" | python3 -c "import json,sys; print(','.join(json.load(sys.stdin)['roles']))")
  echo "Planned listener: roles=${roles} primary=${primary_role} bind=${host}:${port} model=${model}"
  gpu="$(gpu_for_primary "${primary_role}")"
  start_server "${primary_role}" "${gpu}" "${host}" "${port}" "${model}" "${roles}"
done < <(echo "${SERVE_PLAN_JSON}" | python3 -c "import json,sys; [print(json.dumps(x)) for x in json.load(sys.stdin)['listeners']]")

echo "PIDs:"
cat gepa/servers/pids/*.pid 2>/dev/null || true
echo
echo "Waiting for OpenAI-compatible servers..."
${UV} python3 gepa/servers/check_vllm_servers.py \
  --timeout-seconds "${SERVER_TIMEOUT_SECONDS:-1200}" --skip-chat
echo "All model endpoints are ready."
