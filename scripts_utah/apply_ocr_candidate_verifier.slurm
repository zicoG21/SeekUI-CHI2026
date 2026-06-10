#!/usr/bin/env bash
#SBATCH --job-name=seekui-ocr-ver
#SBATCH --account=notchpeak-shared-short
#SBATCH --partition=notchpeak-shared-short
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:20:00
#SBATCH --output=seekui-ocr-verifier-%j.out

set -euo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:-$(pwd)}"
cd "$REPO_ROOT"

SEEKUI_WORK="${SEEKUI_WORK:-${SCRATCH:-$REPO_ROOT/.scratch}/seekui}"
DATA_DIR="$SEEKUI_WORK/data"
OUTPUT_DIR="$SEEKUI_WORK/outputs"
OCR_CANDIDATES="${OCR_CANDIDATES:-$OUTPUT_DIR/ocr_candidates_tesseract.json}"
MODE="${MODE:-present_only}"
THRESHOLD="${THRESHOLD:-0.70}"
THRESHOLD_STEP="${THRESHOLD_STEP:-0.05}"
MIN_OCR_CONF="${MIN_OCR_CONF:-35}"

module load miniconda3/25.9.1
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate seekui

for model in SeekUI SeekUI_sft; do
  python scripts_research/apply_ocr_candidate_verifier.py \
    --predictions "$OUTPUT_DIR/present_absent_predictions_${model}.json" \
    --ocr-candidates "$OCR_CANDIDATES" \
    --target2text "$DATA_DIR/target2text.json" \
    --mode "$MODE" \
    --threshold "$THRESHOLD" \
    --threshold-step "$THRESHOLD_STEP" \
    --min-ocr-conf "$MIN_OCR_CONF" \
    --output "$OUTPUT_DIR/present_absent_predictions_${model}_ocr_candidate_verifier_${MODE}.json" \
    --metrics-output "$OUTPUT_DIR/present_absent_predictions_${model}_ocr_candidate_verifier_${MODE}_status_eval.json" \
    --detail-output "$OUTPUT_DIR/present_absent_predictions_${model}_ocr_candidate_verifier_${MODE}_details.csv" \
    --sweep-output "$OUTPUT_DIR/present_absent_predictions_${model}_ocr_candidate_verifier_${MODE}_threshold_sweep.csv"
done

echo "OCR candidate verifier outputs:"
echo "  $OUTPUT_DIR/present_absent_predictions_SeekUI_ocr_candidate_verifier_${MODE}_status_eval.json"
echo "  $OUTPUT_DIR/present_absent_predictions_SeekUI_sft_ocr_candidate_verifier_${MODE}_status_eval.json"
