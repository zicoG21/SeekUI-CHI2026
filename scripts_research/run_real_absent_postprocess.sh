#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="${REPO_ROOT:-$(pwd)}"
cd "$REPO_ROOT"

SEEKUI_WORK="${SEEKUI_WORK:-${SCRATCH:-$REPO_ROOT/.scratch}/seekui}"
DATA_DIR="${SEEKUI_DATA_DIR:-$SEEKUI_WORK/data}"
OUTPUT_DIR="$SEEKUI_WORK/outputs"
REALABS_DIR_WAS_SET="${REALABS_DIR+x}"
REALABS_DIR="${REALABS_DIR:-$OUTPUT_DIR/real_absent_validation}"
MODEL_NAME="${MODEL_NAME:-SeekUI}"
PREDICTIONS="${PREDICTIONS:-$OUTPUT_DIR/present_absent_predictions_${MODEL_NAME}_real_absent.json}"
INPUT_JSON="${INPUT_JSON:-$REALABS_DIR/real_absent_validation_eval.json}"
if [[ -z "$REALABS_DIR_WAS_SET" && "$(basename "$INPUT_JSON")" == "real_absent_validation_eval.json" ]]; then
  REALABS_DIR="$(dirname "$INPUT_JSON")"
fi
OCR_CANDIDATES="${OCR_CANDIDATES:-$REALABS_DIR/ocr_candidates_tesseract.json}"
EVIDENCE_DIR="${EVIDENCE_DIR:-$REALABS_DIR/stopping_evidence}"
MIN_OCR_CONF="${MIN_OCR_CONF:-35}"
prediction_base="$(basename "$PREDICTIONS")"
prediction_base="${prediction_base%.json}"
prediction_label="${PREDICTION_LABEL:-${prediction_base#present_absent_predictions_}}"

python scripts_research/evaluate_absent_status.py \
  --predictions "$PREDICTIONS" \
  --output "${PREDICTIONS%.json}_status_eval.json"

if command -v tesseract >/dev/null 2>&1; then
  python scripts_research/build_ocr_candidates.py \
    --input-json "$INPUT_JSON" \
    --image-root "$DATA_DIR" \
    --output "$OCR_CANDIDATES" \
    --min-conf "$MIN_OCR_CONF"
else
  echo "Warning: tesseract not found; skipping OCR and combined real-absent postprocess."
  python scripts_research/summarize_real_absent_results.py \
    --work-dir "$SEEKUI_WORK" \
    --output-json "$REALABS_DIR/real_absent_results.json" \
    --output-csv "$REALABS_DIR/real_absent_results.csv" \
    --output-md "$REALABS_DIR/real_absent_results.md"
  exit 0
fi

python scripts_research/analyze_prediction_stopping_evidence.py \
  --reference "$DATA_DIR/scanpath_train_explanation.json" \
  --target2text "$DATA_DIR/target2text.json" \
  --image-root "$DATA_DIR" \
  --out-dir "$EVIDENCE_DIR" \
  --prediction "${prediction_label}=$PREDICTIONS"

python scripts_research/apply_combined_verifier.py \
  --predictions "$PREDICTIONS" \
  --evidence "$EVIDENCE_DIR/${prediction_label}_stopping_evidence.csv" \
  --ocr-candidates "$OCR_CANDIDATES" \
  --target2text "$DATA_DIR/target2text.json" \
  --rule and \
  --mode present_only \
  --cognitive-threshold "${COGNITIVE_THRESHOLD:-0.05}" \
  --ocr-threshold "${OCR_THRESHOLD:-0.40}" \
  --threshold-step "${THRESHOLD_STEP:-0.05}" \
  --cognitive-threshold-max "${COGNITIVE_THRESHOLD_MAX:-0.30}" \
  --ocr-threshold-max "${OCR_THRESHOLD_MAX:-0.80}" \
  --min-ocr-conf "$MIN_OCR_CONF" \
  --output "$OUTPUT_DIR/present_absent_predictions_${prediction_label}_combined_and_present_only.json" \
  --metrics-output "$OUTPUT_DIR/present_absent_predictions_${prediction_label}_combined_and_present_only_status_eval.json" \
  --detail-output "$OUTPUT_DIR/present_absent_predictions_${prediction_label}_combined_and_present_only_details.csv" \
  --sweep-output "$OUTPUT_DIR/present_absent_predictions_${prediction_label}_combined_and_present_only_threshold_sweep.csv"

python scripts_research/apply_combined_verifier.py \
  --predictions "$PREDICTIONS" \
  --evidence "$EVIDENCE_DIR/${prediction_label}_stopping_evidence.csv" \
  --ocr-candidates "$OCR_CANDIDATES" \
  --target2text "$DATA_DIR/target2text.json" \
  --rule and \
  --mode present_only \
  --cognitive-threshold "${BEST_F1_COGNITIVE_THRESHOLD:-0.2}" \
  --ocr-threshold "${BEST_F1_OCR_THRESHOLD:-0.6}" \
  --min-ocr-conf "$MIN_OCR_CONF" \
  --output "$OUTPUT_DIR/present_absent_predictions_${prediction_label}_combined_and_present_only_best_f1.json" \
  --metrics-output "$OUTPUT_DIR/present_absent_predictions_${prediction_label}_combined_and_present_only_best_f1_status_eval.json" \
  --detail-output "$OUTPUT_DIR/present_absent_predictions_${prediction_label}_combined_and_present_only_best_f1_details.csv"

python scripts_research/summarize_real_absent_results.py \
  --work-dir "$SEEKUI_WORK" \
  --output-json "$REALABS_DIR/real_absent_results.json" \
  --output-csv "$REALABS_DIR/real_absent_results.csv" \
  --output-md "$REALABS_DIR/real_absent_results.md"

cat "$REALABS_DIR/real_absent_results.md"
