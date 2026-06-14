#!/usr/bin/env bash
#SBATCH --job-name=seekui-native-crop
#SBATCH --account=owner-gpu-guest
#SBATCH --partition=notchpeak-gpu-guest
#SBATCH --gres=gpu:a40:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=48G
#SBATCH --time=08:00:00
#SBATCH --output=seekui-native-crop-%j.out

set -euo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:-$(pwd)}"
cd "$REPO_ROOT"

SEEKUI_WORK="${SEEKUI_WORK:-${SCRATCH:-$REPO_ROOT/.scratch}/seekui}"
BASE_DATA_DIR="${SEEKUI_BASE_DATA_DIR:-$SEEKUI_WORK/data}"
OSF_DATA_DIR="${OSF_DATA_DIR:-$SEEKUI_WORK/data/osf_vsgui10k/extracted/data}"
OUTPUT_DIR="$SEEKUI_WORK/outputs"
NATIVE_DIR="$OUTPUT_DIR/native_vsgui10k"
export HF_HOME="${HF_HOME:-$SEEKUI_WORK/hf_cache}"
export PYTHONUNBUFFERED=1

module load miniconda3/25.9.1
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate seekui

MODEL_NAME="${MODEL_NAME:-SeekUI}"
MODEL_PATH="${MODEL_PATH:-$SEEKUI_WORK/models/$MODEL_NAME}"
SPLIT_NAME="${SPLIT_NAME:-native_text_color_balanced}"
CROP_INCLUDE_CONTEXT="${CROP_INCLUDE_CONTEXT:-0}"
if [[ "$CROP_INCLUDE_CONTEXT" == "1" ]]; then
  DEFAULT_MODEL_LABEL="${MODEL_NAME}_${SPLIT_NAME}_context_crop_ocr_vlm"
else
  DEFAULT_MODEL_LABEL="${MODEL_NAME}_${SPLIT_NAME}_crop_ocr_vlm"
fi
MODEL_LABEL="${MODEL_LABEL:-$DEFAULT_MODEL_LABEL}"
INPUT_JSON="${INPUT_JSON:-$NATIVE_DIR/eval_splits/${SPLIT_NAME}.json}"
POST_LABEL="${POST_LABEL:-${MODEL_NAME}_${SPLIT_NAME}}"
POST_DIR="${POST_DIR:-$NATIVE_DIR/postprocess/${POST_LABEL}}"
OCR_CANDIDATES="${OCR_CANDIDATES:-$POST_DIR/ocr_candidates_tesseract.json}"
CROP_LIMIT="${CROP_LIMIT:-0}"
CROP_TOP_K_OCR="${CROP_TOP_K_OCR:-2}"

limit_suffix=""
limit_args=()
if [[ "$CROP_LIMIT" != "0" ]]; then
  limit_suffix="_n${CROP_LIMIT}"
  limit_args+=(--limit "$CROP_LIMIT")
fi

OUT_DIR="$OUTPUT_DIR/candidate_crop_verifier/${MODEL_LABEL}${limit_suffix}"
CROP_JSON="$OUT_DIR/candidate_crops.json"
CROP_PREDICTIONS="$OUT_DIR/candidate_crop_vlm_predictions.json"
EXAMPLE_PREDICTIONS="$OUTPUT_DIR/present_absent_predictions_${MODEL_LABEL}${limit_suffix}.json"
SUMMARY_JSON="${EXAMPLE_PREDICTIONS%.json}_status_eval.json"
context_args=()
if [[ "$CROP_INCLUDE_CONTEXT" == "1" ]]; then
  context_args+=(--include_context_image)
fi

python scripts_research/export_candidate_crop_dataset.py \
  --input-json "$INPUT_JSON" \
  --ocr-candidates "$OCR_CANDIDATES" \
  --target2text "$BASE_DATA_DIR/target2text.json" \
  --image-root "$OSF_DATA_DIR" \
  --out-dir "$OUT_DIR" \
  --output-json "$CROP_JSON" \
  --top-k-ocr "$CROP_TOP_K_OCR" \
  --min-ocr-conf "${MIN_OCR_CONF:-35}" \
  --crop-pad "${CROP_PAD:-8}" \
  "${limit_args[@]}"

python inference/vlm_candidate_crop_verifier.py \
  --model_path "$MODEL_PATH" \
  --cache_dir "$HF_HOME" \
  --crop_json "$CROP_JSON" \
  --output "$CROP_PREDICTIONS" \
  --max_new_tokens "${MAX_NEW_TOKENS:-48}" \
  --save_every "${SAVE_EVERY:-50}" \
  "${context_args[@]}" \
  --resume

python scripts_research/evaluate_candidate_crop_verifier.py \
  --examples-json "$INPUT_JSON" \
  --crop-predictions "$CROP_PREDICTIONS" \
  --output-predictions "$EXAMPLE_PREDICTIONS" \
  --output-summary "$SUMMARY_JSON" \
  "${limit_args[@]}"

python scripts_research/summarize_native_vsgui_results.py \
  --work-dir "$SEEKUI_WORK" \
  --output-json "$NATIVE_DIR/native_vsgui_results.json" \
  --output-csv "$NATIVE_DIR/native_vsgui_results.csv" \
  --output-md "$NATIVE_DIR/native_vsgui_results.md"

echo "Native crop VLM output dir: $OUT_DIR"
cat "$SUMMARY_JSON"
echo
echo "Native VSGUI results:"
cat "$NATIVE_DIR/native_vsgui_results.md"
