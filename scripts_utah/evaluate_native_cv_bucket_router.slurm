#!/usr/bin/env bash
#SBATCH --job-name=seekui-native-cvroute
#SBATCH --account=notchpeak-shared-short
#SBATCH --partition=notchpeak-shared-short
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:10:00
#SBATCH --output=seekui-native-cvroute-%j.out

set -euo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:-$(pwd)}"
cd "$REPO_ROOT"

SEEKUI_WORK="${SEEKUI_WORK:-${SCRATCH:-$REPO_ROOT/.scratch}/seekui}"
OUTPUT_DIR="$SEEKUI_WORK/outputs"
NATIVE_DIR="$OUTPUT_DIR/native_vsgui10k"
OUT_DIR="$NATIVE_DIR/cv_bucket_router"

module load miniconda3/25.9.1
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate seekui

MODEL_NAME="${MODEL_NAME:-SeekUI}"
SPLIT_NAME="${SPLIT_NAME:-native_text_color_balanced}"
SELECTION_METRIC="${SELECTION_METRIC:-absent_f1}"
AUDIT_JSON="${AUDIT_JSON:-$NATIVE_DIR/label_conflict_audit/${SPLIT_NAME}_combined_and_present_only_best_f1.json}"

python scripts_research/evaluate_native_cv_bucket_router.py \
  --work-dir "$SEEKUI_WORK" \
  --split-name "$SPLIT_NAME" \
  --model-name "$MODEL_NAME" \
  --audit-json "$AUDIT_JSON" \
  --selection-metric "$SELECTION_METRIC" \
  --output-json "$OUT_DIR/${SPLIT_NAME}_cv_bucket_router.json" \
  --output-csv "$OUT_DIR/${SPLIT_NAME}_cv_bucket_router.csv" \
  --output-md "$OUT_DIR/${SPLIT_NAME}_cv_bucket_router.md"

python scripts_research/summarize_native_vsgui_results.py \
  --work-dir "$SEEKUI_WORK" \
  --output-json "$NATIVE_DIR/native_vsgui_results.json" \
  --output-csv "$NATIVE_DIR/native_vsgui_results.csv" \
  --output-md "$NATIVE_DIR/native_vsgui_results.md"

SPLIT_NAME="$SPLIT_NAME" MODEL_NAME="$MODEL_NAME" VLM_PROMPT_VARIANT=ocr_aware \
  bash scripts_utah/evaluate_native_vsgui_filtered.slurm

echo "Native CV bucket router:"
cat "$OUT_DIR/${SPLIT_NAME}_cv_bucket_router.md"
