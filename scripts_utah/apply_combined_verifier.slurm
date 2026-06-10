#!/usr/bin/env bash
#SBATCH --job-name=seekui-combo
#SBATCH --account=notchpeak-shared-short
#SBATCH --partition=notchpeak-shared-short
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:20:00
#SBATCH --output=seekui-combo-%j.out

set -euo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:-$(pwd)}"
cd "$REPO_ROOT"

SEEKUI_WORK="${SEEKUI_WORK:-${SCRATCH:-$REPO_ROOT/.scratch}/seekui}"
DATA_DIR="$SEEKUI_WORK/data"
OUTPUT_DIR="$SEEKUI_WORK/outputs"
OCR_CANDIDATES="${OCR_CANDIDATES:-$OUTPUT_DIR/ocr_candidates_tesseract.json}"
MODE="${MODE:-present_only}"
RULES="${RULES:-or and}"
COGNITIVE_THRESHOLD="${COGNITIVE_THRESHOLD:-0.05}"
OCR_THRESHOLD="${OCR_THRESHOLD:-0.40}"
THRESHOLD_STEP="${THRESHOLD_STEP:-0.05}"
COGNITIVE_THRESHOLD_MAX="${COGNITIVE_THRESHOLD_MAX:-0.30}"
OCR_THRESHOLD_MAX="${OCR_THRESHOLD_MAX:-0.80}"
MIN_OCR_CONF="${MIN_OCR_CONF:-35}"

module load miniconda3/25.9.1
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate seekui

for model in SeekUI SeekUI_sft; do
  for rule in $RULES; do
    python scripts_research/apply_combined_verifier.py \
      --predictions "$OUTPUT_DIR/present_absent_predictions_${model}.json" \
      --evidence "$OUTPUT_DIR/stopping_evidence/${model}_stopping_evidence.csv" \
      --ocr-candidates "$OCR_CANDIDATES" \
      --target2text "$DATA_DIR/target2text.json" \
      --rule "$rule" \
      --mode "$MODE" \
      --cognitive-threshold "$COGNITIVE_THRESHOLD" \
      --ocr-threshold "$OCR_THRESHOLD" \
      --threshold-step "$THRESHOLD_STEP" \
      --cognitive-threshold-max "$COGNITIVE_THRESHOLD_MAX" \
      --ocr-threshold-max "$OCR_THRESHOLD_MAX" \
      --min-ocr-conf "$MIN_OCR_CONF" \
      --output "$OUTPUT_DIR/present_absent_predictions_${model}_combined_${rule}_${MODE}.json" \
      --metrics-output "$OUTPUT_DIR/present_absent_predictions_${model}_combined_${rule}_${MODE}_status_eval.json" \
      --detail-output "$OUTPUT_DIR/present_absent_predictions_${model}_combined_${rule}_${MODE}_details.csv" \
      --sweep-output "$OUTPUT_DIR/present_absent_predictions_${model}_combined_${rule}_${MODE}_threshold_sweep.csv"
  done
done

echo "Combined verifier outputs:"
ls -lh "$OUTPUT_DIR"/present_absent_predictions_*_combined_*_"$MODE"_status_eval.json
