#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SEEKUI_WORK="${SEEKUI_WORK:-${SCRATCH:-$REPO_ROOT/.scratch}/seekui}"

export HF_HOME="${HF_HOME:-$SEEKUI_WORK/hf_cache}"
export TRANSFORMERS_CACHE="${TRANSFORMERS_CACHE:-$HF_HOME}"
export HF_XET_HIGH_PERFORMANCE="${HF_XET_HIGH_PERFORMANCE:-1}"

MODEL_DIR="$SEEKUI_WORK/models"
mkdir -p "$MODEL_DIR" "$HF_HOME"

if command -v hf >/dev/null 2>&1; then
  HF_DOWNLOAD=(hf download)
elif command -v huggingface-cli >/dev/null 2>&1; then
  HF_DOWNLOAD=(huggingface-cli download)
else
  echo "Hugging Face CLI not found. Install huggingface_hub in your SeekUI environment first:"
  echo "  pip install -U huggingface_hub hf_xet"
  exit 1
fi

echo "Repo root: $REPO_ROOT"
echo "Work dir : $SEEKUI_WORK"
echo "HF_HOME  : $HF_HOME"

"${HF_DOWNLOAD[@]}" sushizixin1/SeekUI \
  --local-dir "$MODEL_DIR/SeekUI" \
  --local-dir-use-symlinks False

"${HF_DOWNLOAD[@]}" sushizixin1/SeekUI_sft \
  --local-dir "$MODEL_DIR/SeekUI_sft" \
  --local-dir-use-symlinks False

echo
echo "Downloaded models:"
du -sh "$MODEL_DIR"/SeekUI "$MODEL_DIR"/SeekUI_sft
