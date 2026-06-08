#!/usr/bin/env bash
set -euo pipefail

python -m pip install -U pip

python -m pip install torch torchvision \
  --index-url https://download.pytorch.org/whl/cu121

python -m pip install \
  "transformers==4.55.0" \
  "accelerate" \
  "qwen-vl-utils" \
  "pillow" \
  "tqdm" \
  "matplotlib" \
  "huggingface_hub" \
  "hf_xet"

python - <<'PY'
import torch
import transformers

print("torch", torch.__version__)
print("cuda available", torch.cuda.is_available())
print("transformers", transformers.__version__)
PY
