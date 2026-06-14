#!/usr/bin/env bash
#SBATCH --job-name=seekui-native-tune
#SBATCH --account=notchpeak-shared-short
#SBATCH --partition=notchpeak-shared-short
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:15:00
#SBATCH --output=seekui-native-tune-%j.out

set -euo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:-$(pwd)}"
cd "$REPO_ROOT"

SEEKUI_WORK="${SEEKUI_WORK:-${SCRATCH:-$REPO_ROOT/.scratch}/seekui}"
BASE_DATA_DIR="${SEEKUI_BASE_DATA_DIR:-$SEEKUI_WORK/data}"
OUTPUT_DIR="$SEEKUI_WORK/outputs"
NATIVE_DIR="$OUTPUT_DIR/native_vsgui10k"
MODEL_NAME="${MODEL_NAME:-SeekUI}"
SPLIT_NAME="${SPLIT_NAME:-native_text_color_balanced}"
MODEL_LABEL="${MODEL_LABEL:-${MODEL_NAME}_${SPLIT_NAME}}"
POST_DIR="${POST_DIR:-$NATIVE_DIR/postprocess/${MODEL_LABEL}}"
PREDICTIONS="${PREDICTIONS:-$OUTPUT_DIR/present_absent_predictions_${MODEL_LABEL}.json}"
EVIDENCE="${EVIDENCE:-$POST_DIR/stopping_evidence/${MODEL_LABEL}_stopping_evidence.csv}"
OCR_CANDIDATES="${OCR_CANDIDATES:-$POST_DIR/ocr_candidates_tesseract.json}"
THRESHOLD_METRIC="${THRESHOLD_METRIC:-absent_f1}"
THRESHOLD_STEP="${THRESHOLD_STEP:-0.025}"
COGNITIVE_THRESHOLD_MAX="${COGNITIVE_THRESHOLD_MAX:-0.6}"
OCR_THRESHOLD_MAX="${OCR_THRESHOLD_MAX:-1.0}"
MIN_OCR_CONF="${MIN_OCR_CONF:-35}"
VARIANT_SUFFIX="${VARIANT_SUFFIX:-native_tuned_${THRESHOLD_METRIC}}"
OUT_BASE="$OUTPUT_DIR/present_absent_predictions_${MODEL_LABEL}_combined_and_present_only_${VARIANT_SUFFIX}"

module load miniconda3/25.9.1
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate seekui

if [[ ! -f "$PREDICTIONS" ]]; then
  echo "Missing predictions: $PREDICTIONS" >&2
  exit 1
fi
if [[ ! -f "$EVIDENCE" || ! -f "$OCR_CANDIDATES" ]]; then
  echo "Missing native postprocess evidence/OCR files." >&2
  echo "Run: SPLIT_NAME=$SPLIT_NAME sbatch scripts_utah/native_vsgui_text_postprocess.slurm" >&2
  echo "Missing evidence? $EVIDENCE" >&2
  echo "Missing OCR?      $OCR_CANDIDATES" >&2
  exit 1
fi

python scripts_research/apply_combined_verifier.py \
  --predictions "$PREDICTIONS" \
  --evidence "$EVIDENCE" \
  --ocr-candidates "$OCR_CANDIDATES" \
  --target2text "$BASE_DATA_DIR/target2text.json" \
  --rule and \
  --mode present_only \
  --threshold-step "$THRESHOLD_STEP" \
  --cognitive-threshold-max "$COGNITIVE_THRESHOLD_MAX" \
  --ocr-threshold-max "$OCR_THRESHOLD_MAX" \
  --min-ocr-conf "$MIN_OCR_CONF" \
  --select-threshold-metric "$THRESHOLD_METRIC" \
  --selected-threshold-output "${OUT_BASE}_selected_threshold.json" \
  --sweep-output "${OUT_BASE}_threshold_sweep.csv" \
  --output "${OUT_BASE}.json" \
  --metrics-output "${OUT_BASE}_status_eval.json" \
  --detail-output "${OUT_BASE}_details.csv"

python scripts_research/summarize_native_vsgui_results.py \
  --work-dir "$SEEKUI_WORK" \
  --output-json "$NATIVE_DIR/native_vsgui_results.json" \
  --output-csv "$NATIVE_DIR/native_vsgui_results.csv" \
  --output-md "$NATIVE_DIR/native_vsgui_results.md"

echo "Selected threshold:"
cat "${OUT_BASE}_selected_threshold.json"
echo
echo "Metrics:"
cat "${OUT_BASE}_status_eval.json"
echo
echo "Native VSGUI results:"
cat "$NATIVE_DIR/native_vsgui_results.md"
