#!/usr/bin/env bash
#SBATCH --job-name=seekui-subset
#SBATCH --account=owner-gpu-guest
#SBATCH --partition=notchpeak-gpu-guest
#SBATCH --gres=gpu:a40:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=48G
#SBATCH --time=00:45:00
#SBATCH --output=seekui-subset-%j.out

set -euo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:-$(pwd)}"
cd "$REPO_ROOT"

SEEKUI_WORK="${SEEKUI_WORK:-${SCRATCH:-$REPO_ROOT/.scratch}/seekui}"
DATA_DIR="${SEEKUI_DATA_DIR:-$SEEKUI_WORK/data}"
export HF_HOME="${HF_HOME:-$SEEKUI_WORK/hf_cache}"
export PYTHONUNBUFFERED=1

module load miniconda3/25.9.1
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate seekui

MODEL_PATH="${MODEL_PATH:-$SEEKUI_WORK/models/SeekUI}"
SUBSET_PATH="${SUBSET_PATH:-$DATA_DIR/subset_available_10.json}"
OUTPUT_PATH="${OUTPUT_PATH:-$SEEKUI_WORK/outputs/subset_predictions.json}"

python scripts_utah/make_available_subset.py \
  --data_dir "$DATA_DIR" \
  --output "$SUBSET_PATH" \
  --limit "${SUBSET_LIMIT:-10}"

python inference/prediction_think.py \
  --model_path "$MODEL_PATH" \
  --cache_dir "$HF_HOME" \
  --scanpath_test "$SUBSET_PATH" \
  --target2text "$DATA_DIR/target2text.json" \
  --image_root "$DATA_DIR" \
  --output "$OUTPUT_PATH" \
  --max_new_tokens 256 \
  --save_every "${SAVE_EVERY:-10}" \
  --resume

echo "Subset predictions saved to $OUTPUT_PATH"
