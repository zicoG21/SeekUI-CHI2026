#!/usr/bin/env bash
#SBATCH --job-name=seekui-imgcue
#SBATCH --account=owner-gpu-guest
#SBATCH --partition=notchpeak-gpu-guest
#SBATCH --gres=gpu:a40:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=48G
#SBATCH --time=08:00:00
#SBATCH --output=seekui-imgcue-%j.out

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

MODEL_NAME="${MODEL_NAME:-SeekUI}"
MODEL_PATH="${MODEL_PATH:-$SEEKUI_WORK/models/$MODEL_NAME}"
SUBSET_LIMIT="${SUBSET_LIMIT:-1362}"
CROP_DIR="${CROP_DIR:-$DATA_DIR/target_crops}"
IMAGE_CUE_JSON="${IMAGE_CUE_JSON:-$DATA_DIR/image_cue_${SUBSET_LIMIT}.json}"
OUTPUT_PATH="${OUTPUT_PATH:-$SEEKUI_WORK/outputs/image_cue_predictions_${MODEL_NAME}_${SUBSET_LIMIT}.json}"

python scripts_research/build_target_crop_dataset.py \
  --scanpath "$DATA_DIR/scanpath_train_explanation.json" \
  --image-root "$DATA_DIR" \
  --output "$IMAGE_CUE_JSON" \
  --crop-dir "$CROP_DIR" \
  --crop-prefix "target_crops" \
  --limit "$SUBSET_LIMIT"

python inference/prediction_image_cue.py \
  --model_path "$MODEL_PATH" \
  --cache_dir "$HF_HOME" \
  --scanpath_test "$IMAGE_CUE_JSON" \
  --image_root "$DATA_DIR" \
  --output "$OUTPUT_PATH" \
  --max_new_tokens "${MAX_NEW_TOKENS:-256}" \
  --save_every "${SAVE_EVERY:-10}" \
  --resume

echo "Image-cue predictions saved to $OUTPUT_PATH"
