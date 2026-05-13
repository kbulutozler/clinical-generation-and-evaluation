# clinical-generation-and-evaluation

Current task: generating clinical notes from patient-doctor conversations and evaluating the generations with LLM-as-a-judge method.

## Datasets
aci-bench: https://github.com/wyim/aci-bench

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
encounter_id is optional.

Run evaluation:

```bash
python3 evaluate_outputs.py <dataset> <eval_prompt_template>
```
Currently, dataset is aci-bench. 
Run analysis:

```bash
uv run --with pyyaml --with matplotlib python3 analyze.py --evaluator Qwen3.5-27B
```

## Model Families

Generation models in [configs/config.yaml](configs/config.yaml):

- `google/gemma-4-E2B-it`
- `google/gemma-4-E4B-it`
- `google/gemma-4-26B-A4B-it`
- `google/gemma-4-31B-it`
- `google/medgemma-27b-text-it`
- `Qwen/Qwen3.5-2B`
- `Qwen/Qwen3.5-4B`
- `Qwen/Qwen3.5-9B`
- `Qwen/Qwen3.5-27B`

Evaluation models in [configs/config.yaml](configs/config.yaml):

- `google/gemma-4-31B-it`
- `Qwen/Qwen3.5-27B`

## Evaluation Snapshot

These means come from the current analysis artifacts in [analysis/Qwen3.5-27B_eval_analysis.md](analysis/Qwen3.5-27B_eval_analysis.md) and [analysis/gemma-4-31B-it_eval_analysis.md](analysis/gemma-4-31B-it_eval_analysis.md). Check these files for further details in current results.


| Generation run              | Evaluator: Qwen3.5-27B mean | Evaluator: gemma-4-31B-it mean |
| --------------------------- | --------------------------- | ------------------------------ |
| Qwen3.5-2B 0-shot           | 0.165                       | 0.217                          |
| Qwen3.5-4B 0-shot           | 0.533                       | 0.615                          |
| gemma-4-E2B-it 0-shot       | 0.690                       | 0.786                          |
| gemma-4-E4B-it 0-shot       | 0.770                       | 0.836                          |
| Qwen3.5-9B 0-shot           | 0.584                       | 0.640                          |
| gemma-4-26B-A4B-it 0-shot   | **0.824**                   | **0.906**                      |
| medgemma-27b-text-it 0-shot | 0.634                       | 0.676                          |
| medgemma-27b-text-it 1-shot | 0.659                       | 0.682                          |
| Qwen3.5-27B 0-shot          | 0.670                       | 0.705                          |


## Eval Prompt

The evaluation template lives at [prompts/evaluation/eval_prompt_template.json](prompts/evaluation/eval_prompt_template.json).

The prompt structure was inspired by:

Asgari et al. (2025), "A framework to assess clinical safety and hallucination rates of LLMs for medical text summarisation," *npj Digital Medicine* 8, 274. [https://doi.org/10.1038/s41746-025-01670-7](https://doi.org/10.1038/s41746-025-01670-7)

## Configuration

Edit [configs/config.yaml](configs/config.yaml) to choose the active generation model, active evaluation model, and model-specific load and sampling settings.

`run_chat_batch.py --model <config_model_key>` overrides `active_model` for one generation run. `evaluate_outputs.py --eval-model <config_model_key>` overrides `active_eval_model` for one evaluation run.

Generation and evaluation require a GPU, preferably 80gb vram A100/H100.

For generation and evaluation scripts, use the official vLLM Docker image tag `vllm/vllm-openai:v0.20.0`. The matching official docs are here: [Using Docker - vLLM v0.20.0](https://docs.vllm.ai/en/v0.20.0/deployment/docker/).
