---
name: anvil-batch-inference
description: Run and verify queue-safe Anvil vLLM generation jobs for this clinical-generation-and-evaluation repo. Use when the user asks to push changes to Anvil, submit one or more Slurm inference jobs, run multiple configured models safely, monitor Anvil jobs, pull outputs/logs, or verify generation outputs from run_chat_batch.py.
---

# Anvil Batch Inference

## Scope

Use this skill only from this repo:

```text
/Users/bulut/Dropbox/repositories/hpc-sync/clinical-generation-and-evaluation
```

The remote Anvil repo is:

```text
/anvil/projects/x-cis251377/x-kozler/repositories/clinical-generation-and-evaluation
```

## Safety Rule

Do not rely on editing `configs/config.yaml` between queued jobs when launching multiple models. A Slurm job reads config when it starts, not when it is submitted. Use the `--model <config_model_key>` argument for generation jobs so each queued job carries its own model.

Safe pattern:

```bash
sbatch slurm/image_job.slurm aci_bench clinicalnlp_taskB_test1_0shot --model google/gemma-4-E4B-it
sbatch slurm/image_job.slurm aci_bench clinicalnlp_taskB_test1_0shot --model Qwen/Qwen3.5-4B
```

Use an encounter id only for smoke tests:

```bash
sbatch slurm/image_job.slurm aci_bench clinicalnlp_taskB_test1_0shot D2N088 --model Qwen/Qwen3.5-4B
```

## Standard Workflow

1. Read the current state:

   ```bash
   git status --short
   sed -n '1,40p' slurm/anvil/image_job.slurm
   uv run --with pyyaml python3 run_chat_batch.py --help
   ```

2. Confirm the model keys exist in `configs/config.yaml`. Prefer models not already used if the user asks for new runs.

3. Push to Anvil:

   ```bash
   make push-anvil
   ```

4. Submit jobs from the remote repo root. For full test set, omit encounter id:

   ```bash
   ssh x-kozler@anvil.rcac.purdue.edu 'cd /anvil/projects/x-cis251377/x-kozler/repositories/clinical-generation-and-evaluation && sbatch slurm/image_job.slurm aci_bench clinicalnlp_taskB_test1_0shot --model <model-key>'
   ```

5. Monitor status. If the user specifies cadence, follow it exactly; otherwise use a practical interval such as 2 minutes:

   ```bash
   ssh x-kozler@anvil.rcac.purdue.edu 'squeue -j <jobids> -o "%.18i %.9P %.20j %.8u %.2t %.10M %.10l %.6D %R"; sacct -j <jobids> --format=JobID,JobName%20,Partition,AllocTRES%50,Elapsed,State,ExitCode -X'
   ```

6. When complete, inspect logs remotely:

   ```bash
   ssh x-kozler@anvil.rcac.purdue.edu 'tail -n 80 /anvil/projects/x-cis251377/x-kozler/repositories/clinical-generation-and-evaluation/logs/slurm-<jobid>.out; tail -n 120 /anvil/projects/x-cis251377/x-kozler/repositories/clinical-generation-and-evaluation/logs/slurm-<jobid>.err'
   ```

   Success indicators:
   - `sacct` state is `COMPLETED`
   - `ExitCode` is `0:0`
   - stdout contains `[N/N]` progress and `Done. Outputs saved to outputs/<yyyymmdd>/<dataset>`
   - stdout model line matches the requested `--model`

7. Pull outputs and logs:

   ```bash
   make pull-anvil
   ```

8. Verify local outputs:

   ```bash
   find outputs/anvil/<yyyymmdd>/<dataset> -maxdepth 6 -type f | sort
   wc -c outputs/anvil/<yyyymmdd>/<dataset>/<encounter_id>/<modelname>/<testsplit_nshot>/output.txt
   sed -n '1,80p' outputs/anvil/<yyyymmdd>/<dataset>/_batch_metadata/<modelname>/<testsplit_nshot>.json
   ```

## Anvil Details

The batch script should use:

```bash
vllm_latest python3 run_chat_batch.py "$@"
```

Expected Anvil Slurm request:

```text
partition=ai
account=cis251377-ai
qos=ai
gpus-per-node=1
time=00:30:00
mem=64G
```

`vllm_latest` is expected in the Anvil login environment. It points to `/anvil/scratch/x-kozler/containers/vllm.sif` and uses `HF_HOME=/anvil/scratch/x-kozler/.cache/huggingface` plus `CC=gcc`.

## Output Layout

Generation output directories are date-only:

```text
outputs/<yyyymmdd>/<dataset>/<encounter_id>/<modelname>/<testsplit_nshot>/
```

After pulling from Anvil:

```text
outputs/anvil/<yyyymmdd>/<dataset>/<encounter_id>/<modelname>/<testsplit_nshot>/
```

Each successful leaf should usually contain:

```text
output.txt
thinking.txt
sourcedoc.txt
sourcetarget.txt
```

Batch metadata should exist at:

```text
outputs/anvil/<yyyymmdd>/<dataset>/_batch_metadata/<modelname>/<testsplit_nshot>.json
```

## Evaluation Override

For eval jobs, use `--eval-model <config_model_key>` when the evaluator should be fixed independently of `active_eval_model`:

```bash
vllm_latest python3 evaluate_outputs.py aci_bench prompts/evaluation/eval_prompt_template.json --eval-model google/gemma-4-31B-it
```
