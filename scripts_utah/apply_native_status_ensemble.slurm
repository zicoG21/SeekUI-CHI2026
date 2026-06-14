#!/usr/bin/env bash
#SBATCH --job-name=seekui-native-ens
#SBATCH --account=notchpeak-shared-short
#SBATCH --partition=notchpeak-shared-short
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:10:00
#SBATCH --output=seekui-native-ens-%j.out

set -euo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:-$(pwd)}"
cd "$REPO_ROOT"

SEEKUI_WORK="${SEEKUI_WORK:-${SCRATCH:-$REPO_ROOT/.scratch}/seekui}"
OUTPUT_DIR="$SEEKUI_WORK/outputs"
NATIVE_DIR="$OUTPUT_DIR/native_vsgui10k"

module load miniconda3/25.9.1
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate seekui

MODEL_NAME="${MODEL_NAME:-SeekUI}"
SPLIT_NAME="${SPLIT_NAME:-native_text_color_balanced}"
PRIMARY_VARIANT="${PRIMARY_VARIANT:-${SPLIT_NAME}_color_aware_filtered_tuned_absent_f1}"
SECONDARY_VARIANT="${SECONDARY_VARIANT:-${SPLIT_NAME}_context_crop_ocr_vlm}"
TERTIARY_VARIANT="${TERTIARY_VARIANT:-vlm_evidence_${SPLIT_NAME}_evidence_aware}"
PRIMARY_LABEL="${PRIMARY_LABEL:-color_aware}"
SECONDARY_LABEL="${SECONDARY_LABEL:-context_crop}"
TERTIARY_LABEL="${TERTIARY_LABEL:-evidence_aware}"
SELECT_METRIC="${SELECT_METRIC:-filtered_absent_f1}"

BASE_PREDICTIONS="${BASE_PREDICTIONS:-$OUTPUT_DIR/present_absent_predictions_${MODEL_NAME}_${SPLIT_NAME}.json}"
PRIMARY_PREDICTIONS="${PRIMARY_PREDICTIONS:-$OUTPUT_DIR/present_absent_predictions_${MODEL_NAME}_${PRIMARY_VARIANT}.json}"
SECONDARY_PREDICTIONS="${SECONDARY_PREDICTIONS:-$OUTPUT_DIR/present_absent_predictions_${MODEL_NAME}_${SECONDARY_VARIANT}.json}"
TERTIARY_PREDICTIONS="${TERTIARY_PREDICTIONS:-$OUTPUT_DIR/vlm_evidence_predictions_${MODEL_NAME}_${TERTIARY_VARIANT}.json}"
AUDIT_JSON="${AUDIT_JSON:-$NATIVE_DIR/label_conflict_audit/${SPLIT_NAME}_combined_and_present_only_best_f1.json}"
VARIANT_SUFFIX="${VARIANT_SUFFIX:-status_ensemble_${SELECT_METRIC}}"
OUT_BASE="$OUTPUT_DIR/present_absent_predictions_${MODEL_NAME}_${SPLIT_NAME}_${VARIANT_SUFFIX}"

python scripts_research/apply_native_status_ensemble.py \
  --base-predictions "$BASE_PREDICTIONS" \
  --primary-predictions "$PRIMARY_PREDICTIONS" \
  --secondary-predictions "$SECONDARY_PREDICTIONS" \
  --tertiary-predictions "$TERTIARY_PREDICTIONS" \
  --primary-label "$PRIMARY_LABEL" \
  --secondary-label "$SECONDARY_LABEL" \
  --tertiary-label "$TERTIARY_LABEL" \
  --audit-json "$AUDIT_JSON" \
  --select-metric "$SELECT_METRIC" \
  --output "${OUT_BASE}.json" \
  --metrics-output "${OUT_BASE}_status_eval.json" \
  --sweep-output "${OUT_BASE}_sweep.csv" \
  --selected-output "${OUT_BASE}_selected_rule.json"

python scripts_research/summarize_native_vsgui_results.py \
  --work-dir "$SEEKUI_WORK" \
  --output-json "$NATIVE_DIR/native_vsgui_results.json" \
  --output-csv "$NATIVE_DIR/native_vsgui_results.csv" \
  --output-md "$NATIVE_DIR/native_vsgui_results.md"

SPLIT_NAME="$SPLIT_NAME" \
MODEL_NAME="$MODEL_NAME" \
VLM_PROMPT_VARIANT=ocr_aware \
  bash scripts_utah/evaluate_native_vsgui_filtered.slurm

python scripts_research/export_native_extension_summary.py \
  --work-dir "$SEEKUI_WORK" \
  --output-json "$NATIVE_DIR/native_extension_summary.json" \
  --output-csv "$NATIVE_DIR/native_extension_summary.csv" \
  --output-md "$NATIVE_DIR/native_extension_summary.md"

echo "Native status ensemble metrics:"
cat "${OUT_BASE}_status_eval.json"
echo
echo "Native status ensemble sweep:"
cat "${OUT_BASE}_sweep.csv"
