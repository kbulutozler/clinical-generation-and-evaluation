# clinical-generation-and-evaluation

Clinical note generation and evaluation utilities.

This public repo contains the code needed to:

- build prompt JSON for ACI-Bench
- run vLLM chat generation
- run LLM-as-judge evaluation
- analyze evaluation outputs

## Included Files

- `prepare_prompts.py`
- `run_chat_batch.py`
- `evaluate_outputs.py`
- `analyze.py`
- `utils.py`
- `configs/config.yaml`

## Main Entry Points

Generate prompts:

```bash
uv run --with pyyaml python3 prepare_prompts.py --dataset aci_bench --test_split clinicalnlp_taskB_test1 --shots 0 1 2
```

Run generation:

```bash
python3 run_chat_batch.py <dataset> <testsplit_nshot> [encounter_id]
```

Run evaluation:

```bash
python3 evaluate_outputs.py <dataset> <eval_prompt_template>
```

Run analysis:

```bash
uv run --with pyyaml --with matplotlib python3 analyze.py --evaluator Qwen3.5-27B
```

## Configuration

Edit `configs/config.yaml` to choose the active generation model, active evaluation model, and model-specific load and sampling settings.
