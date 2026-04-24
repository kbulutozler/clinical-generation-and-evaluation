# clinical-generation-and-evaluation

LLM inference and evaluation pipeline for clinical note generation, designed for a local-edit / HPC-execute workflow.

## Scripts

### `prepare_aci_prompts.py` — build prompt files (run locally)

Reads the ACI-bench dataset and writes one JSON file per encounter under `prompts/aci_bench/`.

```bash
uv run --with pyyaml python3 prepare_aci_prompts.py \
  --dataset aci_bench \
  --machine local \
  --test_split clinicalnlp_taskB_test1 \
  --shots 0 1 2
```

Each output file contains `encounter_id`, `messages` (chat format), and `target` (gold reference note).

---

### `run_chat_batch.py` — batch inference (run on HPC)

Loads the active model from config, runs inference on all prompts in a directory, and saves outputs.

```bash
python3 run_chat_batch.py <prompts_dir> [encounter_id]
```

Outputs saved to `outputs/YYYYMMDD/<modelname>/<dataset>/<split>/`:
- `output.txt` — generated note
- `thinking.txt` — thinking trace (if model produced one)
- `sourcedoc.txt` — input dialogue
- `sourcetarget.txt` — gold reference note
- `_batch_metadata.json` — load/inference times and hyperparameters

---

### `evaluate_outputs.py` — LLM-as-judge evaluation (run on HPC)

Loads the active eval model from config and evaluates generated notes in an output directory.

```bash
python3 evaluate_outputs.py <exp_dir> <eval_prompt_template>
```

The eval prompt template is a JSON file under `prompts/evaluation/` (e.g. `prompts/evaluation/eval_prompt_template.json`) defining the system prompt and a user message with `{sourcedoc}`, `{sourcetarget}`, and `{generated_note}` placeholders.

Reads `sourcedoc.txt`, `sourcetarget.txt`, and `output.txt` per encounter. Writes:
- `eval_output.txt` — structured evaluation (hallucinations + omissions + score)
- `eval_thinking.txt` — eval model thinking trace (if present)
- `_eval_batch_metadata.json` — batch-level metadata

---

### `utils.py` — shared helpers

| Function | Description |
|---|---|
| `load_config(path)` | Load `configs/config.yaml` |
| `get_model_config(config)` | Return active model's config dict |
| `get_dataset_path(config, dataset, machine)` | Resolve dataset path for a given machine |
| `extract_thinking(text)` | Split `</think>` boundary into `(output, thinking)` |

---

## Configuration (`configs/config.yaml`)

```yaml
active_model: "Qwen/Qwen3.5-27B"           # used by run_chat_batch.py
active_eval_model: "Qwen/Qwen3.5-27B"      # used by evaluate_outputs.py
active_model_thinking: true                 # toggles thinking vs non_thinking hparams

models:
  Qwen/Qwen3.5-27B:
    modelname: "Qwen3.5-27B"               # used for output directory naming
    path: "Qwen/Qwen3.5-27B"              # resolved via HF_HOME on HPC
    load:
      dtype: "bfloat16"
      tensor_parallel_size: 1
      gpu_memory_utilization: 0.9
      max_model_len: 32768
      max_cudagraph_capture_size: 16       # optional: cap CUDA graph batch size (workaround for hybrid models)
      enforce_eager: false                 # optional: disable CUDA graphs entirely
    generation:
      thinking:   { temperature: 1.0, top_p: 0.95, top_k: 20, ... }
      non_thinking: { temperature: 0.7, top_p: 0.8,  top_k: 20, ... }

datasets:
  aci_bench:
    anvil: "/anvil/projects/.../data/aci-bench-main"
    aces:  "/scratch/group/.../data/aci-bench-main"
    local: "~/Dropbox/repositories/aci-bench"
```

Edit locally, push to HPC with `make push-anvil` or `make push-aces`.

---

## vLLM Image Alias (HPC)

- **Anvil:**
  ```bash
  alias vllm="apptainer exec --nv --env HF_HOME=$HF_HOME --env CC=gcc $SCRATCH/containers/vllm.sif"
  ```
- **ACES:**
  ```bash
  alias vllm="singularity exec --nv --env HF_HOME=$HF_HOME $PROJ_USER/containers/vllm.sif"
  ```
