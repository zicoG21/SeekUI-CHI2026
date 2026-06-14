#!/usr/bin/env bash
#SBATCH --job-name=seekui-native-bucket
#SBATCH --account=notchpeak-shared-short
#SBATCH --partition=notchpeak-shared-short
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:10:00
#SBATCH --output=seekui-native-bucket-%j.out

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
SELECTION_METRIC="${SELECTION_METRIC:-absent_f1}"

for view in native_original clean_absent_only visible_text_as_present color_instance_as_present all_visible_conflicts_as_present color_instance_only; do
  variant="native_bucket_router_${view}_${SELECTION_METRIC}"
  out_base="$OUTPUT_DIR/present_absent_predictions_${MODEL_NAME}_${SPLIT_NAME}_${variant}"
  python scripts_research/apply_native_bucket_tuned_router.py \
    --work-dir "$SEEKUI_WORK" \
    --split-name "$SPLIT_NAME" \
    --model-name "$MODEL_NAME" \
    --audit-json "$AUDIT_JSON" \
    --selection-view "$view" \
    --selection-metric "$SELECTION_METRIC" \
    --output "${out_base}.json" \
    --metrics-output "${out_base}_status_eval.json" \
    --mapping-output "${out_base}_mapping.json" \
    --bucket-scores-output "${out_base}_bucket_scores.csv"
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

python scripts_research/export_native_extension_summary.py \
  --work-dir "$SEEKUI_WORK" \
  --output-json "$NATIVE_DIR/native_extension_summary.json" \
  --output-csv "$NATIVE_DIR/native_extension_summary.csv" \
  --output-md "$NATIVE_DIR/native_extension_summary.md"

echo "Native bucket-tuned router complete."
cat "$RETASK_DIR/${SPLIT_NAME}_retasked_status.md"
