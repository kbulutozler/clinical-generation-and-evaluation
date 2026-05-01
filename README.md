# clinical-generation-and-evaluation

LLM inference and evaluation pipeline for clinical note generation, designed for a local-edit / HPC-execute workflow.

Local is the source of truth for code, config, and prompts. HPC systems run vLLM inference and produce outputs. Pulls bring back only generated outputs and logs.

## Core Workflow

1. Build or edit prompts locally under `prompts/`.
2. Push to an HPC system with `make push-anvil`, `make push-aces`, or `make push-stampede3`.
3. Run inference on the HPC with `vllm` or `sbatch slurm/image_job.slurm ...`.
4. Pull results with `make pull-anvil`, `make pull-aces`, or `make pull-stampede3`.
5. Evaluate generated notes with `evaluate_outputs.py` on the HPC.

Pulled results are machine-scoped:

```text
outputs/<machine>/YYYYMMDD/<modelname>/<dataset>/<experiment>/<encounter_id>/
logs/<machine>/
```

## Scripts

### `prepare_aci_prompts.py`

Build ACI-Bench prompt files locally. It reads the dataset and writes one JSON file per encounter under `prompts/aci_bench/`.

```bash
uv run --with pyyaml python3 prepare_aci_prompts.py \
  --dataset aci_bench \
  --test_split clinicalnlp_taskB_test1 \
  --shots 0 1 2
```

Each prompt contains:

- `encounter_id`
- `messages` in chat format
- `target`, the gold reference note

### `run_chat_batch.py`

Run vLLM chat inference on all prompt JSONs in a directory, or on one encounter.

```bash
python3 run_chat_batch.py <prompts_dir> [encounter_id]
```

Examples:

```bash
vllm python3 run_chat_batch.py prompts/aci_bench/clinicalnlp_taskB_test1_0shot
vllm python3 run_chat_batch.py prompts/aci_bench/clinicalnlp_taskB_test1_0shot D2N088
```

HPC outputs are written to:

```text
outputs/YYYYMMDD/<modelname>/<dataset>/<experiment>/<encounter_id>/
```

Per-encounter files:

- `output.txt`: generated note
- `thinking.txt`: thinking trace if the model emitted one
- `sourcedoc.txt`: input dialogue
- `sourcetarget.txt`: gold reference note, when `target` exists in the prompt

Batch metadata:

- `_batch_metadata.json`: model, load config, generation config, prompt count, load time, inference time

### `evaluate_outputs.py`

Run LLM-as-judge evaluation for generated clinical notes.

```bash
python3 evaluate_outputs.py <exp_dir> <eval_prompt_template>
```

Example:

```bash
vllm python3 evaluate_outputs.py \
  outputs/20260423/Qwen3.5-27B/aci_bench/clinicalnlp_taskB_test1_0shot \
  prompts/evaluation/eval_prompt_template.json
```

The eval prompt template must define a system message and a user message with these placeholders:

- `{sourcedoc}`
- `{sourcetarget}`
- `{generated_note}`

Evaluation writes:

- `<encounter_id>/evals/<eval_modelname>/eval_output.txt`: structured judgment
- `<encounter_id>/evals/<eval_modelname>/eval_thinking.txt`: eval model thinking trace, if emitted
- `evals/<eval_modelname>/_eval_batch_metadata.json`: eval batch metadata

## Sync

Pushes are local -> HPC and include prompts. Pulls are HPC -> local and include only outputs/logs.

```bash
make push-anvil
make pull-anvil

make push-aces
make pull-aces

make push-stampede3
make pull-stampede3
```

The Makefile keeps local Slurm files machine-scoped:

```text
slurm/anvil/
slurm/aces/
slurm/stampede3/
```

During `make push-*`, only the selected machine's Slurm files are copied to remote `slurm/`. On the HPC, submit jobs with:

```bash
sbatch slurm/image_job.slurm prompts/aci_bench/clinicalnlp_taskB_test1_0shot
```

Machine-specific reference docs:

- `docs/anvil.md`
- `docs/aces.md`
- `docs/stampede3.md`

## Configuration

Edit `configs/config.yaml` locally, then push it to HPC.

```yaml
active_model: "Qwen/Qwen3.5-27B"
active_eval_model: "Qwen/Qwen3.5-27B"
active_model_thinking: true

models:
  Qwen/Qwen3.5-27B:
    modelname: "Qwen3.5-27B"
    path: "Qwen/Qwen3.5-27B"
    load:
      dtype: "bfloat16"
      tensor_parallel_size: 1
      gpu_memory_utilization: 0.9
      max_model_len: 32768
      max_cudagraph_capture_size: 64
      max_num_seqs: 128
      kv_cache_dtype: "fp8"
      calculate_kv_scales: null
      enforce_eager: null
    generation:
      thinking: { temperature: 1.0, top_p: 0.95, top_k: 20, min_p: 0.0, presence_penalty: 1.5, repetition_penalty: 1.0, max_tokens: null }
      non_thinking: { temperature: 0.7, top_p: 0.8, top_k: 20, min_p: 0.0, presence_penalty: 1.5, repetition_penalty: 1.0, max_tokens: null }

datasets:
  aci_bench:
    local: "~/Dropbox/repositories/aci-bench"
```

Optional vLLM load keys are forwarded when present and non-null:

- `max_cudagraph_capture_size`
- `max_num_seqs`
- `kv_cache_dtype`
- `calculate_kv_scales`
- `enforce_eager`

## Local Environment

`environment.yml` is a small local/reference environment. Inference and evaluation are intended to run through vLLM containers on HPC, not through a local conda environment.
