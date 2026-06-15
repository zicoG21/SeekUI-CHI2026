#!/usr/bin/env bash
#SBATCH --job-name=seekui-native-imgcue
#SBATCH --account=owner-gpu-guest
#SBATCH --partition=notchpeak-gpu-guest
#SBATCH --gres=gpu:a40:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=48G
#SBATCH --time=08:00:00
#SBATCH --output=seekui-native-imgcue-%j.out

set -euo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:-$(pwd)}"
cd "$REPO_ROOT"

SEEKUI_WORK="${SEEKUI_WORK:-${SCRATCH:-$REPO_ROOT/.scratch}/seekui}"
DATA_DIR="${SEEKUI_DATA_DIR:-$SEEKUI_WORK/data}"
NATIVE_DIR="${NATIVE_DIR:-$SEEKUI_WORK/outputs/native_vsgui10k}"
export HF_HOME="${HF_HOME:-$SEEKUI_WORK/hf_cache}"
export PYTHONUNBUFFERED=1

module load miniconda3/25.9.1
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate seekui

MODEL_NAME="${MODEL_NAME:-SeekUI}"
MODEL_PATH="${MODEL_PATH:-$SEEKUI_WORK/models/$MODEL_NAME}"
IMAGE_CUE_JSON="${IMAGE_CUE_JSON:-$NATIVE_DIR/processed_v2/image_cue_resolution/native_image_cue_balanced_eval.json}"
OUTPUT_PATH="${OUTPUT_PATH:-$SEEKUI_WORK/outputs/image_cue_predictions_${MODEL_NAME}_native_v2_image_cue_balanced.json}"

if [[ ! -f "$IMAGE_CUE_JSON" ]]; then
  echo "Missing IMAGE_CUE_JSON: $IMAGE_CUE_JSON" >&2
  echo "Run: sbatch scripts_utah/resolve_native_vsgui10k_image_cues.slurm" >&2
  exit 1
fi

python inference/prediction_image_cue.py \
  --model_path "$MODEL_PATH" \
  --cache_dir "$HF_HOME" \
  --scanpath_test "$IMAGE_CUE_JSON" \
  --image_root "$DATA_DIR" \
  --output "$OUTPUT_PATH" \
  --max_new_tokens "${MAX_NEW_TOKENS:-256}" \
  --save_every "${SAVE_EVERY:-10}" \
  --resume

echo "Native image-cue predictions saved to $OUTPUT_PATH"
