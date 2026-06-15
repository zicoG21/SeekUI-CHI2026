#!/usr/bin/env bash
#SBATCH --job-name=seekui-imgcue-vlm
#SBATCH --account=owner-gpu-guest
#SBATCH --partition=notchpeak-gpu-guest
#SBATCH --gres=gpu:a40:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=48G
#SBATCH --time=08:00:00
#SBATCH --output=seekui-imgcue-vlm-%j.out

set -euo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:-$(pwd)}"
cd "$REPO_ROOT"

SEEKUI_WORK="${SEEKUI_WORK:-${SCRATCH:-$REPO_ROOT/.scratch}/seekui}"
DATA_DIR="${SEEKUI_DATA_DIR:-$SEEKUI_WORK/data}"
OUTPUT_DIR="$SEEKUI_WORK/outputs"
NATIVE_DIR="$OUTPUT_DIR/native_vsgui10k"
export HF_HOME="${HF_HOME:-$SEEKUI_WORK/hf_cache}"
export PYTHONUNBUFFERED=1

module load miniconda3/25.9.1
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate seekui

MODEL_NAME="${MODEL_NAME:-SeekUI}"
MODEL_PATH="${MODEL_PATH:-$SEEKUI_WORK/models/$MODEL_NAME}"
INPUT_JSON="${INPUT_JSON:-$NATIVE_DIR/processed_v2/image_cue_resolution/review_merged/native_image_cue_balanced_eval_review_merged.json}"
VLM_IMAGE_CUE_PROMPT_VARIANT="${VLM_IMAGE_CUE_PROMPT_VARIANT:-conservative}"
MODEL_LABEL="${MODEL_LABEL:-${MODEL_NAME}_vlm_image_cue_native_v2_balanced_${VLM_IMAGE_CUE_PROMPT_VARIANT}}"
OUTPUT_PATH="${OUTPUT_PATH:-$OUTPUT_DIR/vlm_image_cue_predictions_${MODEL_LABEL}.json}"

if [[ ! -f "$INPUT_JSON" ]]; then
  echo "Missing INPUT_JSON: $INPUT_JSON" >&2
  echo "Run native image-cue resolution and review merge first." >&2
  exit 1
fi

python inference/vlm_image_cue_presence.py \
  --model_path "$MODEL_PATH" \
  --cache_dir "$HF_HOME" \
  --input_json "$INPUT_JSON" \
  --image_root "$DATA_DIR" \
  --output "$OUTPUT_PATH" \
  --prompt_variant "$VLM_IMAGE_CUE_PROMPT_VARIANT" \
  --max_new_tokens "${MAX_NEW_TOKENS:-32}" \
  --save_every "${SAVE_EVERY:-10}" \
  --resume

python scripts_research/evaluate_absent_status.py \
  --predictions "$OUTPUT_PATH" \
  --output "${OUTPUT_PATH%.json}_status_eval.json"

echo "VLM image-cue presence predictions: $OUTPUT_PATH"
echo "Status eval: ${OUTPUT_PATH%.json}_status_eval.json"
cat "${OUTPUT_PATH%.json}_status_eval.json"
