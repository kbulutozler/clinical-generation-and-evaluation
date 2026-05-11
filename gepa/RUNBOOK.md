# GEPA Anvil Smoke Pipeline

This folder contains a minimal GEPA pipeline for optimizing the generation system prompt on ACI-Bench. It uses GEPA for generation-prompt optimization only. Evaluation is a scoring/feedback step inside GEPA, not the repo's final evaluation pipeline.

## Model Layout

Run one vLLM OpenAI-compatible server per model:

| Role | Model key | Port | GPU |
| --- | --- | ---: | ---: |
| Generation | `Qwen/Qwen3.5-2B` | 8010 | 0 |
| Evaluator | `google/gemma-4-E4B-it` | 8011 | 0 |
| Reflector | `google/gemma-4-26B-A4B-it` | 8012 | 1 |

vLLM serves one model per server process. Multiple models on the same node are reached by separate `http://127.0.0.1:<port>/v1` base URLs. The small generation and evaluator models are pinned to GPU 0 with conservative `--gpu-memory-utilization` values; the 26B reflector is pinned to GPU 1.

## Push Branch To Anvil

From local repo root on branch `gepa`:

```bash
make push-anvil
```

## Start Interactive H100 Allocation

On Anvil:

```bash
ssh x-kozler@anvil.rcac.purdue.edu
source ~/.bash_env
cd /anvil/projects/x-cis251377/x-kozler/repositories/clinical-generation-and-evaluation
sinteractive -p ai -N 1 --gpus-per-node=2 -A cis251377-ai --qos=ai -t 02:00:00 --mem=160G
```

After the allocation starts:

```bash
source ~/.bash_env
cd /anvil/projects/x-cis251377/x-kozler/repositories/clinical-generation-and-evaluation
nvidia-smi
```

Confirm the allocation is one node with two H100 GPUs. The server script uses `CUDA_VISIBLE_DEVICES=0` for generation/evaluator and `CUDA_VISIBLE_DEVICES=1` for the reflector.

## Start Model Servers

Use the vLLM latest image via the `vllm_latest` alias:

```bash
bash gepa/start_vllm_servers.sh
```

Check all three servers, including a tiny chat request:

```bash
python3 gepa/check_vllm_servers.py
```

The command prints `3` when all chat checks pass.

## Run Minimal GEPA Pipeline

Use `uv` for the GEPA environment. The default smoke run uses one encounter and a small metric budget:

```bash
uv run --python 3.12 --with gepa --with pyyaml python3 gepa/run_gepa_pipeline.py \
  --dataset aci_bench \
  --split clinicalnlp_taskB_test1_0shot \
  --encounter-ids D2N088 \
  --max-metric-calls 3 \
  --run-dir outputs/gepa_smoke
```

Expected output:

```text
GEPA pipeline complete: outputs/gepa_smoke/<timestamp>
1
```

Key artifacts:

```text
outputs/gepa_smoke/<timestamp>/summary.json
outputs/gepa_smoke/<timestamp>/best_generation_system_prompt.txt
outputs/gepa_smoke/<timestamp>/gepa_state/
logs/gepa/generation.log
logs/gepa/evaluator.log
logs/gepa/reflector.log
```

## Stop Servers

```bash
bash gepa/stop_vllm_servers.sh
```

## Local Static Verification

This does not require GPUs or GEPA installation:

```bash
uv run --with pyyaml python3 gepa/verify_pipeline.py
```

The verifier prints the number of checks that passed.
