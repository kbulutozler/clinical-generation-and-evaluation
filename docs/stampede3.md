# Stampede3 (TACC)

- **User:** `kbozler`
- **Login:** `stampede3.tacc.utexas.edu` (SSH alias: `stampede3`)
- **Project dir:** `/work2/11527/kbozler/stampede3/` (`$PROJ_USER` = `$WORK`)
- **Scratch dir:** `/scratch/11527/kbozler/` (`$SCRATCH`)
- **Repo:** `$PROJ_USER/repositories/clinical-generation-and-evaluation/`
- **Containers:** `$PROJ_USER/containers/`
- **HF cache:** `$SCRATCH/.cache/huggingface/`
- **GPU types:** H100 (h100 partition, 4x H100/node)
- **CPU partitions:** skx (Skylake, 48-core), spr (Sapphire Rapids, 112-core), icx (Ice Lake, 80-core)
- **Account:** `TG-CIS251377`
- **Docs:** https://docs.tacc.utexas.edu/hpc/stampede3/

## Environment (from `.bash_env`)

- Apptainer module auto-loaded: `tacc-apptainer/1.4.1`
- CUDA module load is optional/non-fatal on GPU nodes; container jobs use Apptainer `--nv`
- Terminal sessions in interactive SLURM jobs logged to `$PROJ_USER/logs/terminal/`

## Aliases

```bash
alias proj="cd $PROJ_USER"
alias scr="cd $SCRATCH"
alias sq="squeue -u $USER"
alias sa="sacct -u $USER --format=JobID,JobName%15,Partition,AllocTRES%25,Elapsed,State -X"
alias vllm="apptainer exec --nv --env HF_HOME=$HF_HOME $PROJ_USER/containers/vllm.sif"
```

## Quotas

| Filesystem | Limit | Notes |
|-----------|-------|-------|
| `$HOME` | 15GB, 300k files | backed up |
| `$WORK` | 1TB, 3M files | shared across all TACC systems, not backed up |
| `$SCRATCH` | no quota, ~10PB | files purged after 10 days inactivity |

## SSH Auth

TACC uses SSH keys plus TACC token (TOTP MFA). Add your local public key once:

```bash
ssh-copy-id -i ~/.ssh/id_rsa.pub stampede3
```

After this, no password prompt; TACC token is still required on every new connection.

## Interactive Jobs

```bash
# CPU (Sapphire Rapids)
srun --time=02:00:00 --partition=spr --nodes=1 --ntasks=1 --account=TG-CIS251377 --pty bash -i

# H100 GPU
srun --time=02:00:00 --partition=h100 --nodes=1 --ntasks=1 --cpus-per-task=8 --mem=64G --account=TG-CIS251377 --pty bash -i
```

> **Note:** TACC does not support node-sharing or partial GPU allocation. `--gres` and `--gpus` flags are not supported. Requesting 1 node on h100 always allocates all 4 H100s. Use `CUDA_VISIBLE_DEVICES=0` inside the job to limit to 1 GPU.

> **Note:** TACC charges per node-hour (1 SU = 1 node-hour). H100: 4 SU/node-hr, SPR: 2 SU/node-hr, ICX: 1.5 SU/node-hr, SKX: 1 SU/node-hr. Minimum 15-minute billing.

## Running Inference

The local repo stores Stampede3 scripts under `slurm/stampede3/`. `make push-stampede3` sends those files to remote `slurm/`.

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

## Downloading a Model

```bash
srun --time=00:30:00 --partition=spr --nodes=1 --ntasks=1 --account=TG-CIS251377 --pty bash -i
source ~/.bash_env
uv run --with huggingface_hub hf download <org/model-name>
```

Model saves to `$HF_HOME`. Use the model name directly in `configs/config.yaml`; vLLM resolves it via `$HF_HOME` automatically.

## Documentation References

Base: https://docs.tacc.utexas.edu/hpc/stampede3/

| Topic | URL |
|-------|-----|
| Filesystems / storage | https://docs.tacc.utexas.edu/hpc/stampede3/#files |
| Software / modules | https://docs.tacc.utexas.edu/hpc/stampede3/#software |
| Running jobs / SLURM | https://docs.tacc.utexas.edu/hpc/stampede3/#running |
| Hardware | https://docs.tacc.utexas.edu/hpc/stampede3/#system |
| Containers at TACC | https://containers-at-tacc.readthedocs.io/en/latest/ |
| TACC user portal | https://portal.tacc.utexas.edu |
