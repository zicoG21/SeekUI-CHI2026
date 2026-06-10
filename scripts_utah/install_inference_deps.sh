#!/usr/bin/env bash
set -euo pipefail

python -m pip install -U pip

python -m pip install torch torchvision \
  --index-url https://download.pytorch.org/whl/cu121

python -m pip install \
  "beautifulsoup4" \
  "packaging" \
  "psutil" \
  "pyyaml" \
  "regex" \
  "requests[socks]" \
  "safetensors" \
  "tokenizers>=0.21,<0.22" \
  "tqdm" \
  "transformers==4.55.0" \
  "accelerate" \
  "qwen-vl-utils" \
  "pillow" \
  "matplotlib" \
  "huggingface_hub" \
  "hf_xet" \
  "gdown"

python - <<'PY'
import torch
import transformers
import accelerate
import requests
import yaml
import tqdm
import tokenizers

print("torch", torch.__version__)
print("cuda available", torch.cuda.is_available())
print("transformers", transformers.__version__)
print("tokenizers", tokenizers.__version__)
print("accelerate", accelerate.__version__)
print("requests", requests.__version__)

major, minor, *_ = [int(part) for part in tokenizers.__version__.split(".")[:2]]
assert (major, minor) >= (0, 21) and (major, minor) < (0, 22), tokenizers.__version__
PY
