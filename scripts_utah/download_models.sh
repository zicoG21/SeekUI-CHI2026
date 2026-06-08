#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SEEKUI_WORK="${SEEKUI_WORK:-${SCRATCH:-$REPO_ROOT/.scratch}/seekui}"

export HF_HOME="${HF_HOME:-$SEEKUI_WORK/hf_cache}"
export TRANSFORMERS_CACHE="${TRANSFORMERS_CACHE:-$HF_HOME}"
export HF_HUB_ENABLE_HF_TRANSFER="${HF_HUB_ENABLE_HF_TRANSFER:-1}"

MODEL_DIR="$SEEKUI_WORK/models"
mkdir -p "$MODEL_DIR" "$HF_HOME"

if ! command -v huggingface-cli >/dev/null 2>&1; then
  echo "huggingface-cli not found. Install huggingface_hub in your SeekUI environment first:"
  echo "  pip install -U huggingface_hub hf_transfer"
  exit 1
fi

echo "Repo root: $REPO_ROOT"
echo "Work dir : $SEEKUI_WORK"
echo "HF_HOME  : $HF_HOME"

huggingface-cli download sushizixin1/SeekUI \
  --local-dir "$MODEL_DIR/SeekUI" \
  --local-dir-use-symlinks False

huggingface-cli download sushizixin1/SeekUI_sft \
  --local-dir "$MODEL_DIR/SeekUI_sft" \
  --local-dir-use-symlinks False

echo
echo "Downloaded models:"
du -sh "$MODEL_DIR"/SeekUI "$MODEL_DIR"/SeekUI_sft
