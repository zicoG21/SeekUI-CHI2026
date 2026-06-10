#!/usr/bin/env bash
set -euo pipefail

CONDA_MODULE="${CONDA_MODULE:-python3.10-anaconda/2023.03}"
CONDA_ENV="${CONDA_ENV:-seekui}"
PYTHON_VERSION="${PYTHON_VERSION:-3.10.12}"

module load "$CONDA_MODULE"
source "$(conda info --base)/etc/profile.d/conda.sh"

if ! conda env list | awk '{print $1}' | grep -qx "$CONDA_ENV"; then
  conda create -n "$CONDA_ENV" "python=$PYTHON_VERSION" -y
fi

conda activate "$CONDA_ENV"
bash scripts_utah/install_inference_deps.sh

python - <<'PY'
import torch
import transformers
print("torch", torch.__version__)
print("cuda available", torch.cuda.is_available())
print("transformers", transformers.__version__)
PY
