# Anvil (Purdue)

- **User:** `x-kozler`
- **Login:** `anvil.rcac.purdue.edu` (SSH alias: `anvil`)
- **Project dir:** `/anvil/projects/x-cis251377/x-kozler/` (`$PROJ_USER`)
- **Scratch dir:** `/anvil/scratch/x-kozler/` (`$SCRATCH`)
- **Repo:** `$PROJ_USER/repositories/clinical-generation-and-evaluation/`
- **Containers:** `$SCRATCH/containers/`
- **HF cache:** `$SCRATCH/.cache/huggingface/`
- **GPU types:** A100 (gpu partition), H100 (ai partition)
- **Account:** `cis251377` / `cis251377-gpu` / `cis251377-ai`
- **Docs:** https://www.rcac.purdue.edu/knowledge/anvil

## Environment (from `.bash_env`)

- GPU modules auto-loaded when `nvidia-smi` present: `gcc/11.2.0 cuda/12.8.0 conda/2024.09`
- Terminal sessions in interactive SLURM jobs logged to `$PROJ_USER/logs/terminal/`

## Aliases

```bash
alias proj="cd $PROJ_USER"
alias scr="cd $SCRATCH"
alias sq="squeue -u $USER"
alias sa="sacct -u $USER --format=JobID,JobName%15,Partition,AllocTRES%25,Elapsed,State -X"
alias vllm="apptainer exec --nv --env HF_HOME=$HF_HOME --env CC=gcc $SCRATCH/containers/vllm.sif"
```

## Quotas

| Filesystem | Limit |
|-----------|-------|
| home | 25GB |
| scratch | 100TB |
| project | 5TB |

## Interactive Jobs

```bash
# CPU
sinteractive -p debug -N 1 -n 4 -A cis251377 --qos=cpu -t 00:30:00 --mem=32G

# GPU (A100)
sinteractive -p gpu -N 1 --gpus-per-node=1 -A cis251377-gpu --qos=gpu -t 01:00:00 --mem=64G

# AI (H100)
sinteractive -p ai -N 1 --gpus-per-node=1 -A cis251377-ai --qos=ai -t 01:00:00 --mem=64G
```

## Running Inference

The local repo stores Anvil scripts under `slurm/anvil/`. `make push-anvil` sends those files to remote `slurm/`.

### Download vLLM Image

Submit as batch (recommended because image pulls can take a while):

```bash
sbatch slurm/image_install.slurm
```

Or interactively on a shared CPU node:

```bash
sinteractive -p shared -N 1 -n 4 -A cis251377 --qos=cpu -t 02:00:00 --mem=32G
source ~/.bash_env
mkdir -p $SCRATCH/containers
apptainer pull $SCRATCH/containers/vllm.sif docker://vllm/vllm-openai:v0.17.1
```

### Run Batch Inference

Interactive:

```bash
source ~/.bash_env
cd $PROJ_USER/repositories/clinical-generation-and-evaluation
vllm python3 run_chat_batch.py prompts/aci_bench/clinicalnlp_taskB_test1_0shot
```

Batch job:

```bash
sbatch slurm/image_job.slurm prompts/aci_bench/clinicalnlp_taskB_test1_0shot
```

One encounter:

```bash
sbatch slurm/image_job.slurm prompts/aci_bench/clinicalnlp_taskB_test1_0shot D2N088
```

> **Note:** `--env CC=gcc` is baked into the `vllm` alias on Anvil. Anvil's `.bash_env` sets `CC=mpicc` through MPI modules, which can leak into the container and break Triton's JIT compiler.

## Downloading a Model

1. Get an interactive CPU node:

   ```bash
   sinteractive -p debug -N 1 -n 4 -A cis251377 --qos=cpu -t 00:30:00 --mem=32G
   ```

2. Source env and download:

   ```bash
   source ~/.bash_env
   uv run --with huggingface_hub hf download <org/model-name>
   ```

Model saves to `$HF_HOME/hub/`. Use the model name directly in `configs/config.yaml`; vLLM resolves it via `$HF_HOME` automatically.

## Documentation References

Base: https://www.rcac.purdue.edu/knowledge/anvil

| Topic | URL |
|-------|-----|
| Running jobs / SLURM | https://www.rcac.purdue.edu/knowledge/anvil/run |
| Storage / file transfer | https://www.rcac.purdue.edu/knowledge/anvil/storage |
| Software / modules | https://www.rcac.purdue.edu/knowledge/anvil/software |
| Hardware / architecture | https://www.rcac.purdue.edu/knowledge/anvil/about |
| Containers | https://www.rcac.purdue.edu/knowledge/anvil/software/containers |
| Policies / FAQ | https://www.rcac.purdue.edu/knowledge/anvil/policies |
