#!/usr/bin/env bash
#SBATCH --job-name=seekui-native-post
#SBATCH --account=notchpeak-shared-short
#SBATCH --partition=notchpeak-shared-short
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=00:45:00
#SBATCH --output=seekui-native-post-%j.out

set -euo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:-$(pwd)}"
cd "$REPO_ROOT"

SEEKUI_WORK="${SEEKUI_WORK:-${SCRATCH:-$REPO_ROOT/.scratch}/seekui}"
BASE_DATA_DIR="${SEEKUI_BASE_DATA_DIR:-$SEEKUI_WORK/data}"
OSF_DATA_DIR="${OSF_DATA_DIR:-$SEEKUI_WORK/data/osf_vsgui10k/extracted/data}"
OUTPUT_DIR="$SEEKUI_WORK/outputs"
NATIVE_DIR="$OUTPUT_DIR/native_vsgui10k"
SPLIT_NAME="${SPLIT_NAME:-native_text_balanced}"
MODEL_NAME="${MODEL_NAME:-SeekUI}"
INPUT_JSON="${INPUT_JSON:-$NATIVE_DIR/eval_splits/${SPLIT_NAME}.json}"
PREDICTIONS="${PREDICTIONS:-$OUTPUT_DIR/present_absent_predictions_${MODEL_NAME}_${SPLIT_NAME}.json}"
MODEL_LABEL="${MODEL_LABEL:-${MODEL_NAME}_${SPLIT_NAME}}"
OUT_DIR="${OUT_DIR:-$NATIVE_DIR/postprocess/${MODEL_LABEL}}"
MIN_OCR_CONF="${MIN_OCR_CONF:-35}"

module load miniconda3/25.9.1
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate seekui

mkdir -p "$OUT_DIR"

python scripts_research/evaluate_absent_status.py \
  --predictions "$PREDICTIONS" \
  --output "${PREDICTIONS%.json}_status_eval.json"

python scripts_research/build_ocr_candidates.py \
  --input-json "$INPUT_JSON" \
  --image-root "$OSF_DATA_DIR" \
  --output "$OUT_DIR/ocr_candidates_tesseract.json" \
  --min-conf "$MIN_OCR_CONF"

python scripts_research/analyze_prediction_stopping_evidence.py \
  --reference "$INPUT_JSON" \
  --target2text "$BASE_DATA_DIR/target2text.json" \
  --image-root "$OSF_DATA_DIR" \
  --out-dir "$OUT_DIR/stopping_evidence" \
  --prediction "${MODEL_LABEL}=$PREDICTIONS"

python scripts_research/apply_combined_verifier.py \
  --predictions "$PREDICTIONS" \
  --evidence "$OUT_DIR/stopping_evidence/${MODEL_LABEL}_stopping_evidence.csv" \
  --ocr-candidates "$OUT_DIR/ocr_candidates_tesseract.json" \
  --target2text "$BASE_DATA_DIR/target2text.json" \
  --rule and \
  --mode present_only \
  --cognitive-threshold "${COGNITIVE_THRESHOLD:-0.05}" \
  --ocr-threshold "${OCR_THRESHOLD:-0.40}" \
  --threshold-step "${THRESHOLD_STEP:-0.05}" \
  --cognitive-threshold-max "${COGNITIVE_THRESHOLD_MAX:-0.30}" \
  --ocr-threshold-max "${OCR_THRESHOLD_MAX:-0.80}" \
  --min-ocr-conf "$MIN_OCR_CONF" \
  --output "$OUTPUT_DIR/present_absent_predictions_${MODEL_LABEL}_combined_and_present_only.json" \
  --metrics-output "$OUTPUT_DIR/present_absent_predictions_${MODEL_LABEL}_combined_and_present_only_status_eval.json" \
  --detail-output "$OUTPUT_DIR/present_absent_predictions_${MODEL_LABEL}_combined_and_present_only_details.csv" \
  --sweep-output "$OUTPUT_DIR/present_absent_predictions_${MODEL_LABEL}_combined_and_present_only_threshold_sweep.csv"

python scripts_research/apply_combined_verifier.py \
  --predictions "$PREDICTIONS" \
  --evidence "$OUT_DIR/stopping_evidence/${MODEL_LABEL}_stopping_evidence.csv" \
  --ocr-candidates "$OUT_DIR/ocr_candidates_tesseract.json" \
  --target2text "$BASE_DATA_DIR/target2text.json" \
  --rule and \
  --mode present_only \
  --cognitive-threshold "${BEST_F1_COGNITIVE_THRESHOLD:-0.2}" \
  --ocr-threshold "${BEST_F1_OCR_THRESHOLD:-0.6}" \
  --min-ocr-conf "$MIN_OCR_CONF" \
  --output "$OUTPUT_DIR/present_absent_predictions_${MODEL_LABEL}_combined_and_present_only_best_f1.json" \
  --metrics-output "$OUTPUT_DIR/present_absent_predictions_${MODEL_LABEL}_combined_and_present_only_best_f1_status_eval.json" \
  --detail-output "$OUTPUT_DIR/present_absent_predictions_${MODEL_LABEL}_combined_and_present_only_best_f1_details.csv"

python scripts_research/summarize_native_vsgui_results.py \
  --work-dir "$SEEKUI_WORK" \
  --output-json "$NATIVE_DIR/native_vsgui_results.json" \
  --output-csv "$NATIVE_DIR/native_vsgui_results.csv" \
  --output-md "$NATIVE_DIR/native_vsgui_results.md"

echo "Native postprocess summary: $NATIVE_DIR/native_vsgui_results.md"
cat "$NATIVE_DIR/native_vsgui_results.md"
