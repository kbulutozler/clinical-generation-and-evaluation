# clinical-generation-and-evaluation

A vLLM inference and evaluation repo for clinical note generation from ACI-Bench prompts. Local is the source of truth for code, config, and prompts; HPC systems run inference and produce outputs.

## Repo Shape

```
clinical-generation-and-evaluation/
|-- CLAUDE.md
|-- AGENTS.md
|-- GEMINI.md
|-- Makefile
|-- configs/config.yaml
|-- docs/
|   |-- anvil.md
|   |-- aces.md
|   `-- stampede3.md
|-- prompts/
|   |-- aci_bench/<split>_<n>shot/<encounter_id>.json
|   |-- evaluation/eval_prompt_template.json
|   `-- examples/
|-- outputs/<machine>/YYYYMMDD/<modelname>/<dataset>/<exp>/<encounter_id>/evals/<eval_modelname>/
|-- logs/<machine>/
|-- prepare_aci_prompts.py
|-- run_chat_batch.py
|-- evaluate_outputs.py
`-- slurm/
    |-- anvil/
    |-- aces/
    `-- stampede3/
```

## Machine Docs

Read the matching machine doc before HPC-side work:

- Anvil: `docs/anvil.md`
- ACES: `docs/aces.md`
- Stampede3: `docs/stampede3.md`

The Makefile pushes only the matching machine's Slurm files to remote `slurm/`, so remote batch commands use `sbatch slurm/image_job.slurm ...`.

## Sync Rules

- `push-*`: local -> HPC for code, config, prompts, docs, and the selected machine's Slurm files.
- `pull-*`: HPC -> local for `outputs/` and `logs/` only.
- Pulled results are machine-scoped: `outputs/anvil/`, `outputs/aces/`, `outputs/stampede3/`.
- Prompts are built locally and pushed. Do not pull prompts back from HPC.
- `dotfiles/` is gitignored and local-only.

## Core Commands

Build prompts locally:

```bash
uv run --with pyyaml python3 prepare_aci_prompts.py --dataset aci_bench --test_split clinicalnlp_taskB_test1 --shots 0 1 2
```

Run inference on HPC:

```bash
vllm python3 run_chat_batch.py prompts/aci_bench/clinicalnlp_taskB_test1_0shot
```

Run one encounter:

```bash
vllm python3 run_chat_batch.py prompts/aci_bench/clinicalnlp_taskB_test1_0shot D2N088
```

Evaluate outputs on HPC:

```bash
vllm python3 evaluate_outputs.py outputs/YYYYMMDD/Qwen3.5-27B/aci_bench/clinicalnlp_taskB_test1_0shot prompts/evaluation/eval_prompt_template.json
```

## Config Conventions

- `active_model` controls `run_chat_batch.py`.
- `active_eval_model` controls `evaluate_outputs.py`.
- `active_model_thinking` chooses `generation.thinking` or `generation.non_thinking`.
- Optional vLLM load keys are passed when present and non-null: `max_cudagraph_capture_size`, `max_num_seqs`, `kv_cache_dtype`, `calculate_kv_scales`, `enforce_eager`.
- Prompt JSON must contain `encounter_id` and `messages`; `target` is optional but needed for evaluation.

## Git Conventions

- Never add `Co-Authored-By` lines to commit messages.
