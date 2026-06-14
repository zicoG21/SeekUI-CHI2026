#!/usr/bin/env bash
#SBATCH --job-name=seekui-native-color
#SBATCH --account=notchpeak-shared-short
#SBATCH --partition=notchpeak-shared-short
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=00:30:00
#SBATCH --output=seekui-native-color-%j.out

set -euo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:-$(pwd)}"
cd "$REPO_ROOT"

SEEKUI_WORK="${SEEKUI_WORK:-${SCRATCH:-$REPO_ROOT/.scratch}/seekui}"
BASE_DATA_DIR="${SEEKUI_BASE_DATA_DIR:-$SEEKUI_WORK/data}"
OSF_DATA_DIR="${OSF_DATA_DIR:-$SEEKUI_WORK/data/osf_vsgui10k/extracted/data}"
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
if [[ "$THRESHOLD_METRIC" == filtered_* ]]; then
  DEFAULT_VARIANT_SUFFIX="color_aware_filtered_tuned_${THRESHOLD_METRIC#filtered_}"
else
  DEFAULT_VARIANT_SUFFIX="color_aware_native_tuned_${THRESHOLD_METRIC}"
fi
VARIANT_SUFFIX="${VARIANT_SUFFIX:-$DEFAULT_VARIANT_SUFFIX}"
OUT_BASE="$OUTPUT_DIR/present_absent_predictions_${MODEL_LABEL}_${VARIANT_SUFFIX}"
SELECTION_AUDIT_JSON="${SELECTION_AUDIT_JSON:-}"
if [[ -z "$SELECTION_AUDIT_JSON" && "$THRESHOLD_METRIC" == filtered_* ]]; then
  SELECTION_AUDIT_JSON="$NATIVE_DIR/label_conflict_audit/${SPLIT_NAME}_combined_and_present_only_best_f1.json"
fi

selection_args=()
if [[ -n "$SELECTION_AUDIT_JSON" ]]; then
  selection_args+=(--selection-audit-json "$SELECTION_AUDIT_JSON")
fi

module load miniconda3/25.9.1
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate seekui

python scripts_research/apply_native_color_aware_verifier.py \
  --predictions "$PREDICTIONS" \
  --evidence "$EVIDENCE" \
  --ocr-candidates "$OCR_CANDIDATES" \
  --image-root "$OSF_DATA_DIR" \
  --target2text "$BASE_DATA_DIR/target2text.json" \
  --mode present_only \
  --threshold-step "${THRESHOLD_STEP:-0.025}" \
  --cognitive-threshold-max "${COGNITIVE_THRESHOLD_MAX:-0.6}" \
  --score-threshold-max "${SCORE_THRESHOLD_MAX:-1.0}" \
  --select-threshold-metric "$THRESHOLD_METRIC" \
  "${selection_args[@]}" \
  --min-ocr-conf "${MIN_OCR_CONF:-35}" \
  --color-pad "${COLOR_PAD:-2}" \
  --output "${OUT_BASE}.json" \
  --metrics-output "${OUT_BASE}_status_eval.json" \
  --detail-output "${OUT_BASE}_details.csv" \
  --sweep-output "${OUT_BASE}_threshold_sweep.csv" \
  --selected-threshold-output "${OUT_BASE}_selected_threshold.json"

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
