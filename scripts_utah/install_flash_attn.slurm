#!/usr/bin/env bash
#SBATCH --job-name=seekui-fa2
#SBATCH --account=owner-gpu-guest
#SBATCH --partition=notchpeak-gpu-guest
#SBATCH --gres=gpu:a40:1
#SBATCH --cpus-per-task=16
#SBATCH --mem=64G
#SBATCH --time=02:00:00
#SBATCH --output=seekui-fa2-%j.out

set -euo pipefail

module load miniconda3/25.9.1
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate seekui

python -m pip install -U pip setuptools wheel packaging ninja

python - <<'PY'
import torch
print("torch", torch.__version__)
print("torch cuda", torch.version.cuda)
print("cuda available", torch.cuda.is_available())
if torch.cuda.is_available():
    print("gpu", torch.cuda.get_device_name(0))
    print("capability", torch.cuda.get_device_capability(0))
PY

python -m pip install "flash-attn==2.7.4.post1" --no-build-isolation

python - <<'PY'
import flash_attn
print("flash_attn", flash_attn.__version__)
PY
