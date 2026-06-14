#!/usr/bin/env bash
#SBATCH --job-name=seekui-native-route
#SBATCH --account=notchpeak-shared-short
#SBATCH --partition=notchpeak-shared-short
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:15:00
#SBATCH --output=seekui-native-route-%j.out

set -euo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:-$(pwd)}"
cd "$REPO_ROOT"

SEEKUI_WORK="${SEEKUI_WORK:-${SCRATCH:-$REPO_ROOT/.scratch}/seekui}"
OUTPUT_DIR="$SEEKUI_WORK/outputs"
NATIVE_DIR="$OUTPUT_DIR/native_vsgui10k"
RETASK_DIR="$NATIVE_DIR/retasked_eval"

module load miniconda3/25.9.1
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate seekui

MODEL_NAME="${MODEL_NAME:-SeekUI}"
SPLIT_NAME="${SPLIT_NAME:-native_text_color_balanced}"
AUDIT_JSON="${AUDIT_JSON:-$NATIVE_DIR/label_conflict_audit/${SPLIT_NAME}_combined_and_present_only_best_f1.json}"
BASE_PREDICTIONS="${BASE_PREDICTIONS:-$OUTPUT_DIR/present_absent_predictions_${MODEL_NAME}_${SPLIT_NAME}.json}"
CALIBRATION_PREDICTIONS="${CALIBRATION_PREDICTIONS:-$RETASK_DIR/${SPLIT_NAME}_supervised_calibration_predictions.csv}"
CALIBRATION_SWEEP="${CALIBRATION_SWEEP:-$RETASK_DIR/${SPLIT_NAME}_supervised_calibration_threshold_sweep.csv}"

for spec in \
  "native_original:max_f1" \
  "native_original:precision_ge_0.55" \
  "native_original:pa_le_100" \
  "clean_absent_only:max_f1" \
  "color_instance_only:max_f1" \
  "color_instance_only:precision_ge_0.55"
do
  view="${spec%%:*}"
  constraint="${spec##*:}"
  safe_constraint="${constraint//./p}"
  variant="native_supervised_calibrated_${view}_${safe_constraint}"
  out_base="$OUTPUT_DIR/present_absent_predictions_${MODEL_NAME}_${SPLIT_NAME}_${variant}"
  python scripts_research/apply_native_supervised_calibrated_status.py \
    --base-predictions "$BASE_PREDICTIONS" \
    --calibration-predictions-csv "$CALIBRATION_PREDICTIONS" \
    --calibration-sweep-csv "$CALIBRATION_SWEEP" \
    --view "$view" \
    --constraint "$constraint" \
    --variant-label "$variant" \
    --output "${out_base}.json" \
    --metrics-output "${out_base}_status_eval.json" \
    --selected-output "${out_base}_selected_threshold.json"
done

CLEAN_PREDICTIONS="${CLEAN_PREDICTIONS:-$OUTPUT_DIR/present_absent_predictions_${MODEL_NAME}_${SPLIT_NAME}_status_ensemble_filtered_absent_f1.json}"
VISIBLE_TEXT_PREDICTIONS="${VISIBLE_TEXT_PREDICTIONS:-$OUTPUT_DIR/present_absent_predictions_${MODEL_NAME}_${SPLIT_NAME}_combined_and_present_only_native_tuned_absent_f1.json}"
COLOR_INSTANCE_PREDICTIONS="${COLOR_INSTANCE_PREDICTIONS:-$OUTPUT_DIR/present_absent_predictions_${MODEL_NAME}_${SPLIT_NAME}_combined_and_present_only_native_tuned_absent_f1.json}"
GUARD_PRESENT_PREDICTIONS="${GUARD_PRESENT_PREDICTIONS:-$BASE_PREDICTIONS}"

for profile in clean_vs_color conflict_present_guard color_instance_focus; do
  variant="native_task_routed_${profile}"
  out_base="$OUTPUT_DIR/present_absent_predictions_${MODEL_NAME}_${SPLIT_NAME}_${variant}"
  python scripts_research/apply_native_task_routed_verifier.py \
    --base-predictions "$BASE_PREDICTIONS" \
    --clean-predictions "$CLEAN_PREDICTIONS" \
    --visible-text-predictions "$VISIBLE_TEXT_PREDICTIONS" \
    --color-instance-predictions "$COLOR_INSTANCE_PREDICTIONS" \
    --guard-present-predictions "$GUARD_PRESENT_PREDICTIONS" \
    --audit-json "$AUDIT_JSON" \
    --profile "$profile" \
    --output "${out_base}.json" \
    --metrics-output "${out_base}_status_eval.json" \
    --selected-output "${out_base}_selected_profile.json"
done

python scripts_research/evaluate_native_retasked_status.py \
  --work-dir "$SEEKUI_WORK" \
  --split-name "$SPLIT_NAME" \
  --model-name "$MODEL_NAME" \
  --audit-json "$AUDIT_JSON" \
  --output-json "$RETASK_DIR/${SPLIT_NAME}_retasked_status.json" \
  --output-csv "$RETASK_DIR/${SPLIT_NAME}_retasked_status.csv" \
  --output-md "$RETASK_DIR/${SPLIT_NAME}_retasked_status.md"

python scripts_research/summarize_native_vsgui_results.py \
  --work-dir "$SEEKUI_WORK" \
  --output-json "$NATIVE_DIR/native_vsgui_results.json" \
  --output-csv "$NATIVE_DIR/native_vsgui_results.csv" \
  --output-md "$NATIVE_DIR/native_vsgui_results.md"

SPLIT_NAME="$SPLIT_NAME" MODEL_NAME="$MODEL_NAME" VLM_PROMPT_VARIANT=ocr_aware \
  bash scripts_utah/evaluate_native_vsgui_filtered.slurm

echo "Native supervised/routed methods complete."
echo
cat "$RETASK_DIR/${SPLIT_NAME}_retasked_status.md"
