# clinical-generation-and-evaluation

A lean vLLM inference repo designed for a local-edit / HPC-execute workflow.

## Project Goal

Run LLM inference on HPC (Anvil or ACES) from prompts managed locally on a Mac. Local machine is for editing only; all compute runs on HPC.

## Repo Structure

```
clinical-generation-and-evaluation/
├── CLAUDE.md
├── Makefile                         # push/pull/key-install targets
├── configs/
│   └── config.yaml                  # active model, per-model load/generation hparams
├── prompts/                         # prompt files per task
│   ├── examples/                    # simple example prompts
│   ├── evaluation/                  # LLM-as-judge prompt templates
│   │   └── eval_prompt_template.json
│   └── aci_bench/
│       └── <split>_<n>shot/         # one .json file per encounter
│           └── <encounter_id>.json
├── outputs/                         # HPC-generated, pulled to local
│   └── YYYYMMDD/
│       └── <model>/
│           └── aci_bench/
│               └── <split>_<n>shot/
│                   ├── _batch_metadata.json     # load/inference times, hyperparams
│                   └── <encounter_id>/
│                       ├── output.txt
│                       ├── thinking.txt         # if model produced thinking traces
│                       ├── sourcedoc.txt        # input prompt/dialogue
│                       ├── sourcetarget.txt     # gold reference note
│                       ├── metadata.json
│                       ├── eval_output.txt      # eval model judgment (after evaluate_outputs.py)
│                       └── eval_thinking.txt    # eval model thinking (if present)
├── logs/                            # SLURM stdout/stderr logs
├── utils.py                         # config loading, prompt reading, thinking extraction
├── run_chat_batch.py                # batch chat inference (loads model directly)
├── evaluate_outputs.py              # LLM-as-judge eval (loads eval model directly)
├── prepare_aci_prompts.py           # generate ACI-bench prompt JSON files locally
├── environment.yml                  # conda env definition — not used for inference, reference only
├── slurm/
│   ├── anvil/
│   │   ├── job.slurm                # inference job
│   │   ├── install.slurm            # conda env install
│   │   ├── image_install.slurm      # apptainer image pull
│   │   └── image_job.slurm          # inference via apptainer
│   └── aces/
│       ├── job.slurm
│       ├── install.slurm
│       ├── image_install.slurm
│       └── image_job.slurm
└── sync/
    ├── push.sh                      # local → anvil
    ├── pull.sh                      # anvil → local
    ├── push_aces.sh                 # local → aces
    ├── pull_aces.sh                 # aces → local
    └── install_aces_keys.sh         # copy ACES SSH keys from Downloads to ~/.ssh (local only)
```

## Machines

| Name | Description |
|------|-------------|
| **local** | MacBook — editing only, no GPU |
| **anvil** | Purdue Anvil HPC |
| **aces** | TAMU ACES HPC |

## Tooling

- **Inference:** vLLM (via Singularity/Apptainer container)
- **Sync:** rsync via Makefile targets (`make push-aces`, `make pull-aces`, etc.)
- **No uv, no conda** for inference — container only

## Anvil

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

### Anvil Environment (from `.bash_env`)
- GPU modules auto-loaded when `nvidia-smi` present: `gcc/11.2.0 cuda/12.8.0 conda/2024.09`
- Terminal sessions in interactive SLURM jobs logged to `$PROJ_USER/logs/terminal/`

### Anvil Aliases
```bash
alias proj="cd $PROJ_USER"
alias scr="cd $SCRATCH"
alias sq="squeue -u $USER"
alias sa="sacct -u $USER --format=JobID,JobName%15,Partition,AllocTRES%25,Elapsed,State -X"
alias vllm="apptainer exec --nv --env HF_HOME=$HF_HOME --env CC=gcc $SCRATCH/containers/vllm.sif"
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
sinteractive -p debug -N 1 -n 4 -A cis251377 --qos=cpu -t 00:30:00 --mem=32G

# GPU (A100)
sinteractive -p gpu -N 1 --gpus-per-node=1 -A cis251377-gpu --qos=gpu -t 01:00:00 --mem=64G

# AI (H100)
sinteractive -p ai -N 1 --gpus-per-node=1 -A cis251377-ai --qos=ai -t 01:00:00 --mem=64G
```

## ACES

- **User:** `u.ko341547`
- **Login:** `login.aces.hprc.tamu.edu` (SSH alias: `aces`, via jump host `aces-jump`)
- **Project dir:** `/scratch/group/p.cis251377.000/u.ko341547/` (`$PROJ_USER`)
- **Scratch dir:** `/scratch/user/u.ko341547/` (`$SCRATCH_USER`)
- **Repo:** `$PROJ_USER/repositories/clinical-generation-and-evaluation/`
- **Containers:** `$PROJ_USER/containers/` (group scratch — more quota, project-level artifact)
- **HF cache:** `$SCRATCH_USER/.cache/huggingface/`
- **GPU types:** 30x H100, 4x A30, 120x Intel PVC
- **Account:** `158415475357`
- **Docs:** https://hprc.tamu.edu/kb/User-Guides/ACES/

### ACES Environment (from `.bash_env`)
- GPU modules auto-loaded when `nvidia-smi` present: `GCC/13.2.0 CUDA/12.8.0`
- Terminal sessions in interactive SLURM jobs logged to `$PROJ_USER/logs/terminal/`

### ACES Aliases
```bash
alias proj="cd $PROJ_USER"
alias scr="cd $SCRATCH_USER"
alias sq="squeue -u $USER"
alias sa="sacct -u $USER --format=JobID,JobName%15,Partition,AllocTRES%25,Elapsed,State -X"
alias vllm="singularity exec --nv --env HF_HOME=$HF_HOME $PROJ_USER/containers/vllm.sif"
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
srun --time=02:00:00 --partition=cpu --nodes=1 --ntasks=1 --cpus-per-task=8 --mem=64G --account=158415475357 --pty bash -i

# H100 debug (2hr max)
srun --time=02:00:00 --partition=gpu_debug --nodes=1 --ntasks=1 --cpus-per-task=8 --mem=64G --gres=gpu:h100:1 --account=158415475357 --pty bash -i

# H100 full
srun --time=02:00:00 --partition=gpu --nodes=1 --ntasks=1 --cpus-per-task=8 --mem=64G --gres=gpu:h100:1 --account=158415475357 --pty bash -i

# A30
srun --time=04:00:00 --partition=gpu --nodes=1 --ntasks=1 --cpus-per-task=8 --mem=64G --gres=gpu:a30:1 --account=158415475357 --pty bash -i
```

## ACES SSH Keys

ACES uses certificate-based SSH authentication with keys that expire daily. Each day, download fresh keys from the ACES portal to `~/Downloads/aces keys/`, then install them:

```bash
make install-aces-keys
```

This copies `id_aces_tamu` and `id_aces_tamu-cert.pub` from `~/Downloads/aces keys/` to `~/.ssh/`, replacing the previous day's keys. After running, SSH access to ACES from the local terminal works normally (`ssh aces`). The script is local-only and excluded from HPC sync.

## Sync Strategy

### Push (local → HPC)
Excludes: `outputs/`, `logs/`, `.claude/`, `sync/install_aces_keys.sh`. Uses `--delete` to remove stale files on remote.

### Pull (HPC → local)
Pulls `outputs/` and `logs/` only (ACES also pulls `prompts/`).

### Makefile targets
```bash
make push-anvil
make pull-anvil
make push-aces
make pull-aces
make push-dotfiles-aces
make install-aces-keys
```

## Config (`configs/config.yaml`) Shape

Edited locally, pushed to HPC. Exists on both ends.

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
      max_cudagraph_capture_size: 16   # optional: cap CUDA graph batch size
      enforce_eager: false             # optional: disable CUDA graphs entirely
    generation:
      thinking:
        temperature: 1.0
        top_p: 0.95
        top_k: 20
        min_p: 0.0
        presence_penalty: 1.5
        repetition_penalty: 1.0
        max_tokens: null
      non_thinking:
        temperature: 0.7
        top_p: 0.8
        top_k: 20
        min_p: 0.0
        presence_penalty: 1.5
        repetition_penalty: 1.0
        max_tokens: null

datasets:
  aci_bench:
    anvil: "/anvil/projects/x-cis251377/x-kozler/data/aci-bench-main"
    aces: "/scratch/group/p.cis251377.000/u.ko341547/data/aci-bench-main"
```

## Running Inference on Anvil

### Download vLLM image

Submit as batch (recommended — pull can take ~30 min):
```bash
sbatch slurm/anvil/image_install.slurm
```

Or interactively on a shared CPU node:
```bash
sinteractive -p shared -N 1 -n 4 -A cis251377 --qos=cpu -t 02:00:00 --mem=32G
source ~/.bash_env
mkdir -p $SCRATCH/containers
apptainer pull $SCRATCH/containers/vllm.sif docker://vllm/vllm-openai:v0.17.1
```

### Run batch inference

Interactive:
```bash
source ~/.bash_env
cd $PROJ_USER/repositories/clinical-generation-and-evaluation
vllm python3 run_chat_batch.py prompts/aci_bench/<split>_<n>shot
```

Batch job:
```bash
sbatch slurm/anvil/image_job.slurm prompts/aci_bench/<split>_<n>shot
```

> **Note:** `--env CC=gcc` is baked into the `vllm` alias on Anvil. Anvil's `.bash_env` sets `CC=mpicc` via MPI modules, which leaks into the container and breaks Triton's JIT compiler.

## Downloading a Model on Anvil

```bash
sbatch slurm/anvil/hf_download.slurm <org/model-name>
```

Downloads to `$HF_HOME/hub/`. Use the model name directly in `configs/config.yaml` — vLLM resolves it via `$HF_HOME` automatically.

> **Note:** HF token must be set as `HF_TOKEN` in `~/.bash_env` for gated models.

## Running Inference on ACES

Interactive:
```bash
source ~/.bash_env
cd $PROJ_USER/repositories/clinical-generation-and-evaluation
vllm python3 run_chat_batch.py prompts/aci_bench/<split>_<n>shot
```

Batch job:
```bash
sbatch slurm/aces/image_job.slurm prompts/aci_bench/<split>_<n>shot
```

## Downloading a Model on ACES

1. Get an interactive CPU node with enough memory:
   ```bash
   srun --time=00:30:00 --partition=cpu --nodes=1 --ntasks=1 --cpus-per-task=8 --mem=64G --account=158415475357 --pty bash -i
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

5. Use the model name directly in `configs/config.yaml` — vLLM resolves it via `$HF_HOME` automatically.

> **Note:** `hf-download` conda env must exist with `huggingface_hub` installed. HF token must be set as `HF_TOKEN` in `~/.bash_env` for gated models.

## ACI-BENCH Inference

Dataset paths (used only by `prepare_aci_prompts.py` to build prompt files):
- **Anvil:** `/anvil/projects/x-cis251377/x-kozler/data/aci-bench-main`
- **ACES:** `/scratch/group/p.cis251377.000/u.ko341547/data/aci-bench-main`

Set in `configs/config.yaml` under `datasets.aci_bench`. `evaluate_outputs.py` does **not** use the dataset path — it reads `sourcedoc.txt` and `sourcetarget.txt` from the output directory directly.

**Step 1 — Generate prompts locally:**
```bash
uv run --with pyyaml python3 prepare_aci_prompts.py \
  --dataset aci_bench \
  --machine local \
  --test_split clinicalnlp_taskB_test1 \
  --shots 0 1 2
```
Creates `prompts/aci_bench/clinicalnlp_taskB_test1_{0,1,2}shot/` — 40 JSON files each.

**Step 2 — Push to HPC:**
```bash
make push-anvil   # Anvil
make push-aces    # ACES
```

**Step 3 — Run batch inference:**
```bash
vllm python3 run_chat_batch.py prompts/aci_bench/clinicalnlp_taskB_test1_0shot
```

Outputs saved to `outputs/YYYYMMDD/<model>/aci_bench/<split>_<n>shot/<encounter_id>/`.

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

## Key Conventions

- `active_model_thinking` in config toggles between `generation.thinking` and `generation.non_thinking` hyperparameters
- Scripts are intentionally lean — no CLI arg parsers beyond the prompt dir and optional encounter ID
- No git versioning for now
