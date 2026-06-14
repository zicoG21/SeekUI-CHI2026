#!/usr/bin/env bash
#SBATCH --job-name=seekui-native-post
#SBATCH --account=notchpeak-shared-short
#SBATCH --partition=notchpeak-shared-short
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:15:00
#SBATCH --output=seekui-native-post-%j.out

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
VLM_PROMPT_VARIANT="${VLM_PROMPT_VARIANT:-ocr_aware}"
PRIMARY_VARIANT="${PRIMARY_VARIANT:-${SPLIT_NAME}_color_aware_filtered_tuned_absent_f1}"
PRIMARY_LABEL="${PRIMARY_LABEL:-color_aware}"
AUDIT_JSON="${AUDIT_JSON:-$NATIVE_DIR/label_conflict_audit/${SPLIT_NAME}_combined_and_present_only_best_f1.json}"

python scripts_research/summarize_native_vsgui_results.py \
  --work-dir "$SEEKUI_WORK" \
  --output-json "$NATIVE_DIR/native_vsgui_results.json" \
  --output-csv "$NATIVE_DIR/native_vsgui_results.csv" \
  --output-md "$NATIVE_DIR/native_vsgui_results.md"

OUT_PREFIX="$NATIVE_DIR/filtered_eval/${SPLIT_NAME}_${VLM_PROMPT_VARIANT}"
python scripts_research/evaluate_native_vsgui_filtered.py \
  --work-dir "$SEEKUI_WORK" \
  --split-name "$SPLIT_NAME" \
  --model-name "$MODEL_NAME" \
  --vlm-prompt-variant "$VLM_PROMPT_VARIANT" \
  --audit-json "$AUDIT_JSON" \
  --output-json "${OUT_PREFIX}.json" \
  --output-csv "${OUT_PREFIX}.csv" \
  --output-md "${OUT_PREFIX}.md"

python scripts_research/export_native_extension_summary.py \
  --work-dir "$SEEKUI_WORK" \
  --output-json "$NATIVE_DIR/native_extension_summary.json" \
  --output-csv "$NATIVE_DIR/native_extension_summary.csv" \
  --output-md "$NATIVE_DIR/native_extension_summary.md"

run_taxonomy_if_present() {
  local secondary_variant="$1"
  local secondary_label="$2"
  local secondary_predictions="$3"
  if [[ ! -f "$secondary_predictions" ]]; then
    echo "Skipping taxonomy for ${secondary_label}; missing $secondary_predictions"
    return
  fi
  PRIMARY_VARIANT="$PRIMARY_VARIANT" \
  SECONDARY_VARIANT="$secondary_variant" \
  PRIMARY_LABEL="$PRIMARY_LABEL" \
  SECONDARY_LABEL="$secondary_label" \
  OUT_DIR="$NATIVE_DIR/method_taxonomy/${SPLIT_NAME}_${PRIMARY_LABEL}_vs_${secondary_label}" \
  PROMPT_PREDICTIONS="$OUTPUT_DIR/present_absent_predictions_${MODEL_NAME}_${SPLIT_NAME}.json" \
  PRIMARY_PREDICTIONS="$OUTPUT_DIR/present_absent_predictions_${MODEL_NAME}_${PRIMARY_VARIANT}.json" \
  SECONDARY_PREDICTIONS="$secondary_predictions" \
  AUDIT_JSON="$AUDIT_JSON" \
    bash scripts_utah/export_native_method_taxonomy.slurm
}

run_taxonomy_if_present \
  "${SPLIT_NAME}_context_crop_ocr_vlm" \
  "context_crop" \
  "$OUTPUT_DIR/present_absent_predictions_${MODEL_NAME}_${SPLIT_NAME}_context_crop_ocr_vlm.json"
run_taxonomy_if_present \
  "vlm_evidence_${SPLIT_NAME}_evidence_aware" \
  "evidence_aware" \
  "$OUTPUT_DIR/vlm_evidence_predictions_${MODEL_NAME}_vlm_evidence_${SPLIT_NAME}_evidence_aware.json"
run_taxonomy_if_present \
  "vlm_evidence_${SPLIT_NAME}_evidence_rescue_present" \
  "evidence_rescue" \
  "$OUTPUT_DIR/vlm_evidence_predictions_${MODEL_NAME}_vlm_evidence_${SPLIT_NAME}_evidence_rescue_present.json"

echo "Native VSGUI extension postprocess complete."
echo
echo "Native results:"
cat "$NATIVE_DIR/native_vsgui_results.md"
echo
echo "Filtered native results:"
cat "${OUT_PREFIX}.md"
echo
echo "Native extension summary:"
cat "$NATIVE_DIR/native_extension_summary.md"
