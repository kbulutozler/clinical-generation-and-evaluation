# any-llm-inference

A lean vLLM inference repo designed for a local-edit / HPC-execute workflow.

## Project Goal

Run LLM inference on HPC (Anvil or ACES) from prompts managed locally on a Mac. Local machine is for editing only; all compute runs on HPC.

## Repo Structure

```
any-llm-inference/
├── CLAUDE.md
├── configs/
│   └── config.yaml              # model path, load hparams, generation hparams
├── prompts/                     # one .txt file per prompt
│   └── example.txt
├── outputs/                     # HPC-generated, pulled to local
│   └── YYYYMMDD-HHMMSS/
│       └── <promptname>/
│           ├── output.txt
│           ├── metadata.json
│           └── job.slurm
├── logs/                        # SLURM stdout/stderr logs
├── utils.py                     # config loading, prompt reading
├── run.py                       # entry point: takes prompt filename, runs inference
├── environment.yml              # conda env definition (env name: vllm)
├── slurm/
│   ├── anvil/
│   │   ├── job.slurm            # inference job
│   │   ├── install.slurm        # conda env install
│   │   ├── image_install.slurm  # apptainer image pull
│   │   └── image_job.slurm      # inference via apptainer
│   └── aces/
│       ├── job.slurm
│       ├── install.slurm
│       ├── image_install.slurm
│       └── image_job.slurm
└── sync/
    ├── push.sh                  # local → anvil
    ├── pull.sh                  # anvil → local
    ├── push_aces.sh             # local → aces
    └── pull_aces.sh             # aces → local
```

## Machines

| Name | Description |
|------|-------------|
| **local** | MacBook — editing only, no GPU |
| **anvil** | Purdue Anvil HPC |
| **aces** | TAMU ACES HPC |

## Tooling

- **Inference:** vLLM
- **Env management:** conda (`environment.yml`, env name: `vllm`, Python 3.11)
- **Sync:** rsync (push/pull scripts per HPC, no git-based sync)
- **No uv** for this project — conda only

## Anvil

- **User:** `x-kozler`
- **Login:** `anvil.rcac.purdue.edu` (SSH alias: `anvil`)
- **Project dir:** `/anvil/projects/x-cis251377/x-kozler/` (`$PROJ_USER`)
- **Scratch dir:** `/anvil/scratch/x-kozler/` (`$SCRATCH`)
- **Repo:** `$PROJ_USER/repositories/any-llm-inference/`
- **Containers:** `$SCRATCH/containers/`
- **HF cache:** `$SCRATCH/.cache/huggingface/`
- **GPU types:** A100 (gpu partition), H100 (ai partition)
- **Account:** `cis251377` / `cis251377-gpu` / `cis251377-ai`
- **Docs:** https://www.rcac.purdue.edu/knowledge/anvil

### Anvil Environment (from `.bash_env`)
- `uv` at `$SCRATCH/.local/bin/uv`; `UV_INSTALL_DIR`, `UV_CACHE_DIR`, `UV_TOOL_DIR`, `UV_PYTHON_INSTALL_DIR` all on scratch
- `UV_LINK_MODE=copy` (no symlinks on scratch filesystem)
- GPU modules auto-loaded when `nvidia-smi` present: `gcc/11.2.0 cuda/12.8.0 conda/2024.09`
- Terminal sessions in interactive SLURM jobs logged to `$PROJ_USER/logs/terminal/`

### Anvil Aliases
```bash
alias proj="cd $PROJ_USER"
alias scr="cd $SCRATCH"
alias sq="squeue -u $USER"
alias sa="sacct -u $USER --format=JobID,JobName%15,Partition,AllocTRES%25,Elapsed,State -X"
```

### Anvil Quotas
| Filesystem | Limit |
|-----------|-------|
| home | 25GB |
| scratch | 100TB |
| project | 5TB |

### Anvil Interactive Jobs
```bash
# CPU
sinteractive -p debug -N 1 -n 4 -A cis251377 --qos=cpu -t 00:30:00

# GPU (A100)
sinteractive -p gpu -N 1 --gpus-per-node=1 -A cis251377-gpu --qos=gpu -t 01:00:00

# AI (H100)
sinteractive -p ai -N 1 --gpus-per-node=1 -A cis251377-ai --qos=ai -t 01:00:00
```

## ACES

- **User:** `u.ko341547`
- **Login:** `login.aces.hprc.tamu.edu` (SSH alias: `aces`, via jump host `aces-jump`)
- **Project dir:** `/scratch/group/p.cis251377.000/u.ko341547/` (`$PROJ_USER`)
- **Scratch dir:** `/scratch/user/u.ko341547/` (`$SCRATCH_USER`)
- **Repo:** `$PROJ_USER/repositories/any-llm-inference/`
- **Containers:** `$PROJ_USER/containers/` (group scratch — more quota, project-level artifact)
- **HF cache:** `$SCRATCH_USER/.cache/huggingface/`
- **GPU types:** 30x H100, 4x A30, 120x Intel PVC
- **Account:** `158415475357`
- **Docs:** https://hprc.tamu.edu/kb/User-Guides/ACES/

### ACES Environment (from `.bash_env`)
- `uv` at `$SCRATCH_USER/.local/bin/uv`; `UV_INSTALL_DIR`, `UV_CACHE_DIR`, `UV_TOOL_DIR`, `UV_PYTHON_INSTALL_DIR` all on scratch
- `UV_LINK_MODE=copy` (no symlinks on scratch filesystem)
- GPU modules auto-loaded when `nvidia-smi` present: `GCC/13.2.0 CUDA/12.8.0`
- Terminal sessions in interactive SLURM jobs logged to `$PROJ_USER/logs/terminal/`

### ACES Aliases
```bash
alias proj="cd $PROJ_USER"
alias scr="cd $SCRATCH_USER"
alias sq="squeue -u $USER"
alias sa="sacct -u $USER --format=JobID,JobName%15,Partition,AllocTRES%25,Elapsed,State -X"
```

### ACES Quotas
| Filesystem | Limit |
|-----------|-------|
| home | 10GB |
| scratch/user | 1TB |
| scratch/group | 5TB |

### ACES Interactive Jobs
```bash
# CPU
srun --time=02:00:00 --partition=cpu --nodes=1 --ntasks=1 --account=158415475357 --pty bash -i

# H100 debug (2hr max)
srun --time=02:00:00 --partition=gpu_debug --nodes=1 --ntasks=1 --gres=gpu:h100:1 --account=158415475357 --pty bash -i

# H100 full
srun --time=04:00:00 --partition=gpu --nodes=1 --ntasks=1 --gres=gpu:h100:1 --account=158415475357 --pty bash -i

# A30
srun --time=04:00:00 --partition=gpu --nodes=1 --ntasks=1 --gres=gpu:a30:1 --account=158415475357 --pty bash -i
```

## Sync Strategy

### Push (local → HPC)
Excludes: `outputs/`, `logs/`, `.claude/`. Uses `--delete` to remove stale files on remote.

### Pull (HPC → local)
Pulls `outputs/` and `logs/` only.

## Config (`configs/config.yaml`) Shape

Edited locally, pushed to HPC. Exists on both ends.

```yaml
model:
  name: "meta-llama/Llama-3-8B-Instruct"
  path: "/path/to/.cache/huggingface/hub/..."

load:
  dtype: "bfloat16"
  tensor_parallel_size: 1
  gpu_memory_utilization: 0.9
  max_model_len: 4096

generation:
  temperature: 0.7
  top_p: 0.9
  max_tokens: 512
```

## run.py Conventions

- Single argument: prompt filename — `python run.py my_prompt` or `python run.py my_prompt.txt`
- Hardcoded paths: config at `configs/config.yaml`, prompts at `prompts/`, outputs at `outputs/`
- Output dir: `outputs/YYYYMMDD-HHMMSS/<promptname>/` with `output.txt`, `metadata.json`, `job.slurm`

## utils.py Conventions

- Load and parse `configs/config.yaml`
- Read a prompt `.txt` file from `prompts/`
- Nothing else

## Running Inference on ACES

### Option 1: Load model per prompt (batch or interactive)

Loads the model fresh each time. Slower per prompt but no server needed.

```bash
# Interactive H100 job
srun --time=04:00:00 --partition=gpu --nodes=1 --ntasks=1 --gres=gpu:h100:1 --mem=64G --account=158415475357 --pty bash -i

source ~/.bash_env
cd $PROJ_USER/repositories/any-llm-inference

singularity exec --nv --env HF_HOME=$HF_HOME $PROJ_USER/containers/vllm.sif python3 run.py <promptname>
```

Or submit as a batch job:
```bash
sbatch slurm/aces/image_job.slurm <promptname>
```

### Option 2: Serve the model (fast repeated prompts)

Start the server once, send multiple prompts without reloading.

**Terminal 1 — start server:**
```bash
source ~/.bash_env
singularity exec --nv --env HF_HOME=$HF_HOME $PROJ_USER/containers/vllm.sif python3 -m vllm.entrypoints.openai.api_server --model <model-name>
```

Wait for: `Application startup complete.`

**Terminal 2 — send prompts:**
```bash
export no_proxy="127.0.0.1,localhost"
export NO_PROXY="127.0.0.1,localhost"
cd $PROJ_USER/repositories/any-llm-inference
python3 query.py <promptname>
```

> **Note:** `query.py` runs outside the container (uses stdlib only). Set `no_proxy` to bypass the WebProxy for localhost. Output is saved to `outputs/` same as `run.py`.

## SLURM Conventions

- `slurm/<hpc>/job.slurm` — calls `run.py <promptname>`, logs go to `logs/`
- `slurm/<hpc>/install.slurm` — builds conda env on a GPU node
- `slurm/<hpc>/image_install.slurm` — pulls vLLM singularity image
- `slurm/<hpc>/image_job.slurm` — runs inference via singularity
- A copy of the slurm script used is saved to the output dir by `run.py` at runtime

## Documentation References

### Anvil Docs
Base: https://www.rcac.purdue.edu/knowledge/anvil

| Topic | URL |
|-------|-----|
| Running jobs / SLURM | https://www.rcac.purdue.edu/knowledge/anvil/run |
| Storage / file transfer | https://www.rcac.purdue.edu/knowledge/anvil/storage |
| Software / modules | https://www.rcac.purdue.edu/knowledge/anvil/software |
| Hardware / architecture | https://www.rcac.purdue.edu/knowledge/anvil/about |
| Containers | https://www.rcac.purdue.edu/knowledge/anvil/software/containers |
| Policies / FAQ | https://www.rcac.purdue.edu/knowledge/anvil/policies |

### ACES Docs
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

## Downloading a Model on ACES

1. Get an interactive CPU node with enough memory:
   ```bash
   srun --time=02:00:00 --partition=cpu --nodes=1 --ntasks=1 --cpus-per-task=8 --mem=64G --account=158415475357 --pty bash -i
   ```

2. Source env (loads WebProxy for internet access):
   ```bash
   source ~/.bash_env
   ```

3. Load conda and activate the download env:
   ```bash
   module load Miniconda3/23.10.0-1
   eval "$(conda shell.bash hook)"
   conda activate hf-download
   ```

4. Download the model (saves to `$HF_HOME/hub/`):
   ```bash
   hf download <org/model-name>
   ```

   Example:
   ```bash
   hf download Qwen/Qwen3-4B-Instruct-2507
   ```

5. Use the model name directly in `configs/config.yaml` — vLLM resolves it via `$HF_HOME` automatically.

> **Note:** `hf-download` conda env must exist with `huggingface_hub` installed. HF token must be set as `HF_TOKEN` in `~/.bash_env` for gated models.

## Key Conventions

- Scripts are intentionally lean — no CLI arg parsers beyond the single prompt filename arg
- No git versioning for now
