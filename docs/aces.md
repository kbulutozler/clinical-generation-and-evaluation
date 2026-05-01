# ACES (TAMU)

- **User:** `u.ko341547`
- **Login:** `login.aces.hprc.tamu.edu` (SSH alias: `aces`, via jump host `aces-jump`)
- **Project dir:** `/scratch/group/p.cis251377.000/u.ko341547/` (`$PROJ_USER`)
- **Scratch dir:** `/scratch/user/u.ko341547/` (`$SCRATCH_USER`)
- **Repo:** `$PROJ_USER/repositories/clinical-generation-and-evaluation/`
- **Containers:** `$PROJ_USER/containers/` (group scratch, more quota, project-level artifact)
- **HF cache:** `$SCRATCH_USER/.cache/huggingface/`
- **GPU types:** 30x H100, 4x A30, 120x Intel PVC
- **Account:** `158415475357`
- **Docs:** https://hprc.tamu.edu/kb/User-Guides/ACES/

## Environment (from `.bash_env`)

- GPU modules auto-loaded when `nvidia-smi` present: `GCC/13.2.0 CUDA/12.8.0`
- Terminal sessions in interactive SLURM jobs logged to `$PROJ_USER/logs/terminal/`

## Aliases

```bash
alias proj="cd $PROJ_USER"
alias scr="cd $SCRATCH_USER"
alias sq="squeue -u $USER"
alias sa="sacct -u $USER --format=JobID,JobName%15,Partition,AllocTRES%25,Elapsed,State -X"
alias vllm="singularity exec --nv --env HF_HOME=$HF_HOME $PROJ_USER/containers/vllm.sif"
```

## Quotas

| Filesystem | Limit |
|-----------|-------|
| home | 10GB |
| scratch/user | 1TB |
| scratch/group | 5TB |

## Interactive Jobs

```bash
# CPU
srun --time=02:00:00 --partition=cpu --nodes=1 --ntasks=1 --cpus-per-task=8 --mem=64G --account=158415475357 --pty bash -i

# H100 debug (2hr max)
srun --time=02:00:00 --partition=gpu_debug --nodes=1 --ntasks=1 --cpus-per-task=8 --mem=64G --gres=gpu:h100:1 --account=158415475357 --pty bash -i

# H100 full
srun --time=02:00:00 --partition=gpu --nodes=1 --ntasks=1 --cpus-per-task=8 --mem=64G --gres=gpu:h100:1 --account=158415475357 --pty bash -i

# A30
srun --time=04:00:00 --partition=gpu --nodes=1 --ntasks=1 --cpus-per-task=8 --mem=64G --gres=gpu:a30:1 --account=158415475357 --pty bash -i
```

## SSH Keys

ACES uses certificate-based SSH authentication with keys that expire daily. Each day, download fresh keys from the ACES portal to `~/Downloads/aces keys/`, then install them:

```bash
make install-aces-keys
```

This copies `id_aces_tamu` and `id_aces_tamu-cert.pub` from `~/Downloads/aces keys/` to `~/.ssh/`, replacing the previous day's keys. After running, SSH access to ACES from the local terminal works normally (`ssh aces`).

## Running Inference

The local repo stores ACES scripts under `slurm/aces/`. `make push-aces` sends those files to remote `slurm/`.

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
srun --time=00:30:00 --partition=cpu --nodes=1 --ntasks=1 --cpus-per-task=8 --mem=64G --account=158415475357 --pty bash -i
source ~/.bash_env
uv run --with huggingface_hub hf download <org/model-name>
```

Model saves to `$HF_HOME`. Use the model name directly in `configs/config.yaml`; vLLM resolves it via `$HF_HOME` automatically.

## Documentation References

Base: https://hprc.tamu.edu/kb/User-Guides/ACES/

| Topic | URL |
|-------|-----|
| Hardware | https://hprc.tamu.edu/kb/User-Guides/ACES/Hardware/ |
| Batch system / SLURM | https://hprc.tamu.edu/kb/User-Guides/ACES/Batch/ |
| File systems / storage | https://hprc.tamu.edu/kb/User-Guides/ACES/File-Systems/ |
| Computing environment | https://hprc.tamu.edu/kb/User-Guides/ACES/Computing-Environment/ |
| AI/ML support | https://hprc.tamu.edu/kb/User-Guides/ACES/AI-ML/ |
| Containers (Apptainer) | https://hprc.tamu.edu/kb/Software/Containers/ |
| Policies | https://hprc.tamu.edu/kb/User-Guides/ACES/Policies/ |
| FAQ | https://hprc.tamu.edu/kb/FAQ/ |
