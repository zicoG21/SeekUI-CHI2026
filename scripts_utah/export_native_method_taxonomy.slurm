#!/usr/bin/env bash
#SBATCH --job-name=seekui-native-tax
#SBATCH --account=notchpeak-shared-short
#SBATCH --partition=notchpeak-shared-short
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:10:00
#SBATCH --output=seekui-native-tax-%j.out

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
PRIMARY_LABEL="${PRIMARY_LABEL:-color_aware}"
SECONDARY_LABEL="${SECONDARY_LABEL:-context_crop}"
PROMPT_PREDICTIONS="${PROMPT_PREDICTIONS:-$OUTPUT_DIR/present_absent_predictions_${MODEL_NAME}_${SPLIT_NAME}.json}"
PRIMARY_PREDICTIONS="${PRIMARY_PREDICTIONS:-$OUTPUT_DIR/present_absent_predictions_${MODEL_NAME}_${PRIMARY_VARIANT}.json}"
SECONDARY_PREDICTIONS="${SECONDARY_PREDICTIONS:-$OUTPUT_DIR/present_absent_predictions_${MODEL_NAME}_${SECONDARY_VARIANT}.json}"
AUDIT_JSON="${AUDIT_JSON:-$NATIVE_DIR/label_conflict_audit/${SPLIT_NAME}_combined_and_present_only_best_f1.json}"
OUT_DIR="${OUT_DIR:-$NATIVE_DIR/method_taxonomy/${SPLIT_NAME}_${PRIMARY_LABEL}_vs_${SECONDARY_LABEL}}"

python scripts_research/export_native_method_taxonomy.py \
  --prompt-predictions "$PROMPT_PREDICTIONS" \
  --primary-predictions "$PRIMARY_PREDICTIONS" \
  --secondary-predictions "$SECONDARY_PREDICTIONS" \
  --audit-json "$AUDIT_JSON" \
  --primary-label "$PRIMARY_LABEL" \
  --secondary-label "$SECONDARY_LABEL" \
  --out-dir "$OUT_DIR" \
  --limit "${LIMIT:-40}"

echo "Native method taxonomy: $OUT_DIR/native_method_taxonomy.md"
cat "$OUT_DIR/native_method_taxonomy.md"
