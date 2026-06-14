#!/usr/bin/env bash
#SBATCH --job-name=seekui-native-redef
#SBATCH --account=notchpeak-shared-short
#SBATCH --partition=notchpeak-shared-short
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:20:00
#SBATCH --output=seekui-native-redef-%j.out

set -euo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:-$(pwd)}"
cd "$REPO_ROOT"

SEEKUI_WORK="${SEEKUI_WORK:-${SCRATCH:-$REPO_ROOT/.scratch}/seekui}"
OUTPUT_DIR="$SEEKUI_WORK/outputs"
NATIVE_DIR="$OUTPUT_DIR/native_vsgui10k"
OUT_DIR="$NATIVE_DIR/retasked_eval"

module load miniconda3/25.9.1
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate seekui

MODEL_NAME="${MODEL_NAME:-SeekUI}"
SPLIT_NAME="${SPLIT_NAME:-native_text_color_balanced}"
AUDIT_JSON="${AUDIT_JSON:-$NATIVE_DIR/label_conflict_audit/${SPLIT_NAME}_combined_and_present_only_best_f1.json}"

python scripts_research/evaluate_native_retasked_status.py \
  --work-dir "$SEEKUI_WORK" \
  --split-name "$SPLIT_NAME" \
  --model-name "$MODEL_NAME" \
  --audit-json "$AUDIT_JSON" \
  --output-json "$OUT_DIR/${SPLIT_NAME}_retasked_status.json" \
  --output-csv "$OUT_DIR/${SPLIT_NAME}_retasked_status.csv" \
  --output-md "$OUT_DIR/${SPLIT_NAME}_retasked_status.md"

python scripts_research/train_native_status_calibrator.py \
  --base-predictions "$OUTPUT_DIR/present_absent_predictions_${MODEL_NAME}_${SPLIT_NAME}.json" \
  --primary-predictions "$OUTPUT_DIR/present_absent_predictions_${MODEL_NAME}_${SPLIT_NAME}_color_aware_filtered_tuned_absent_f1.json" \
  --secondary-predictions "$OUTPUT_DIR/present_absent_predictions_${MODEL_NAME}_${SPLIT_NAME}_context_crop_ocr_vlm.json" \
  --tertiary-predictions "$OUTPUT_DIR/vlm_evidence_predictions_${MODEL_NAME}_vlm_evidence_${SPLIT_NAME}_evidence_aware.json" \
  --audit-json "$AUDIT_JSON" \
  --output-json "$OUT_DIR/${SPLIT_NAME}_supervised_calibration.json" \
  --output-csv "$OUT_DIR/${SPLIT_NAME}_supervised_calibration.csv" \
  --output-md "$OUT_DIR/${SPLIT_NAME}_supervised_calibration.md" \
  --prediction-output-csv "$OUT_DIR/${SPLIT_NAME}_supervised_calibration_predictions.csv" \
  --sweep-output-csv "$OUT_DIR/${SPLIT_NAME}_supervised_calibration_threshold_sweep.csv" \
  --constraint-output-md "$OUT_DIR/${SPLIT_NAME}_supervised_calibration_threshold_tradeoff.md"

sbatch scripts_utah/apply_native_status_ensemble.slurm

echo "Native retasked status:"
cat "$OUT_DIR/${SPLIT_NAME}_retasked_status.md"
echo
echo "Native supervised calibration:"
cat "$OUT_DIR/${SPLIT_NAME}_supervised_calibration.md"
echo
echo "Native supervised calibration threshold tradeoff:"
cat "$OUT_DIR/${SPLIT_NAME}_supervised_calibration_threshold_tradeoff.md"
