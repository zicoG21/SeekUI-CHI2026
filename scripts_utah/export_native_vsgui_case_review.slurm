#!/usr/bin/env bash
#SBATCH --job-name=seekui-native-review
#SBATCH --account=notchpeak-shared-short
#SBATCH --partition=notchpeak-shared-short
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:10:00
#SBATCH --output=seekui-native-review-%j.out

set -euo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:-$(pwd)}"
cd "$REPO_ROOT"

SEEKUI_WORK="${SEEKUI_WORK:-${SCRATCH:-$REPO_ROOT/.scratch}/seekui}"
OUTPUT_DIR="$SEEKUI_WORK/outputs"

module load miniconda3/25.9.1
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate seekui

MODEL_NAME="${MODEL_NAME:-SeekUI}"
SPLIT_NAME="${SPLIT_NAME:-native_text_color_balanced}"
VLM_PROMPT_VARIANT="${VLM_PROMPT_VARIANT:-ocr_aware}"
PROMPT_PREDICTIONS="${PROMPT_PREDICTIONS:-$OUTPUT_DIR/present_absent_predictions_${MODEL_NAME}_${SPLIT_NAME}.json}"
COMBINED_PREDICTIONS="${COMBINED_PREDICTIONS:-$OUTPUT_DIR/present_absent_predictions_${MODEL_NAME}_${SPLIT_NAME}_combined_and_present_only_best_f1.json}"
VLM_PREDICTIONS="${VLM_PREDICTIONS:-$OUTPUT_DIR/vlm_presence_predictions_${MODEL_NAME}_vlm_presence_${SPLIT_NAME}_${VLM_PROMPT_VARIANT}.json}"
OUT_DIR="${OUT_DIR:-$OUTPUT_DIR/native_vsgui10k/case_review/${SPLIT_NAME}_${VLM_PROMPT_VARIANT}}"

args=(
  --prompt-predictions "$PROMPT_PREDICTIONS"
  --combined-predictions "$COMBINED_PREDICTIONS"
  --out-dir "$OUT_DIR"
  --limit "${CASE_LIMIT:-30}"
)

if [[ -f "$VLM_PREDICTIONS" ]]; then
  args+=(--vlm-predictions "$VLM_PREDICTIONS")
else
  echo "Warning: missing VLM predictions, exporting prompt/combined cases only: $VLM_PREDICTIONS"
fi

python scripts_research/export_native_vsgui_case_review.py "${args[@]}"

echo "Native VSGUI case review: $OUT_DIR/native_case_review_summary.md"
cat "$OUT_DIR/native_case_review_summary.md"
