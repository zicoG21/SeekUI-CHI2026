#!/usr/bin/env bash
#SBATCH --job-name=seekui-devtest-combo
#SBATCH --account=notchpeak-shared-short
#SBATCH --partition=notchpeak-shared-short
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=00:30:00
#SBATCH --output=seekui-devtest-combo-%j.out

set -euo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:-$(pwd)}"
cd "$REPO_ROOT"

SEEKUI_WORK="${SEEKUI_WORK:-${SCRATCH:-$REPO_ROOT/.scratch}/seekui}"
OUTPUT_DIR="$SEEKUI_WORK/outputs"
DATA_DIR="$SEEKUI_WORK/data"
OUT_DIR="${OUT_DIR:-$OUTPUT_DIR/devtest_combined}"
OCR_CANDIDATES="${OCR_CANDIDATES:-$OUTPUT_DIR/ocr_candidates_tesseract.json}"
RULE="${RULE:-and}"
MODE="${MODE:-present_only}"
DEV_FRACTION="${DEV_FRACTION:-0.5}"
SEED="${SEED:-42}"
BOOTSTRAP="${BOOTSTRAP:-1000}"
THRESHOLD_STEP="${THRESHOLD_STEP:-0.05}"
COGNITIVE_THRESHOLD_MAX="${COGNITIVE_THRESHOLD_MAX:-0.30}"
OCR_THRESHOLD_MAX="${OCR_THRESHOLD_MAX:-0.80}"
MIN_OCR_CONF="${MIN_OCR_CONF:-35}"
SPLITS="${SPLITS:-random image}"

module load miniconda3/25.9.1
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate seekui

mkdir -p "$OUT_DIR"

for split_by in $SPLITS; do
  python scripts_research/evaluate_combined_devtest.py \
    --model SeekUI="$OUTPUT_DIR/present_absent_predictions_SeekUI.json:$OUTPUT_DIR/stopping_evidence/SeekUI_stopping_evidence.csv" \
    --model SeekUI_sft="$OUTPUT_DIR/present_absent_predictions_SeekUI_sft.json:$OUTPUT_DIR/stopping_evidence/SeekUI_sft_stopping_evidence.csv" \
    --ocr-candidates "$OCR_CANDIDATES" \
    --target2text "$DATA_DIR/target2text.json" \
    --rule "$RULE" \
    --mode "$MODE" \
    --split-by "$split_by" \
    --dev-fraction "$DEV_FRACTION" \
    --seed "$SEED" \
    --threshold-step "$THRESHOLD_STEP" \
    --cognitive-threshold-max "$COGNITIVE_THRESHOLD_MAX" \
    --ocr-threshold-max "$OCR_THRESHOLD_MAX" \
    --min-ocr-conf "$MIN_OCR_CONF" \
    --bootstrap "$BOOTSTRAP" \
    --output-json "$OUT_DIR/devtest_combined_${RULE}_${MODE}_${split_by}.json" \
    --output-csv "$OUT_DIR/devtest_combined_${RULE}_${MODE}_${split_by}.csv" \
    --output-md "$OUT_DIR/devtest_combined_${RULE}_${MODE}_${split_by}.md"

  echo "Dev/test combined outputs for split=$split_by:"
  echo "  $OUT_DIR/devtest_combined_${RULE}_${MODE}_${split_by}.md"
  echo "  $OUT_DIR/devtest_combined_${RULE}_${MODE}_${split_by}.csv"
  echo "  $OUT_DIR/devtest_combined_${RULE}_${MODE}_${split_by}.json"
done
