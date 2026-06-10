#!/usr/bin/env bash
#SBATCH --job-name=seekui-devtest-stop
#SBATCH --account=notchpeak-shared-short
#SBATCH --partition=notchpeak-shared-short
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=00:30:00
#SBATCH --output=seekui-devtest-stop-%j.out

set -euo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:-$(pwd)}"
cd "$REPO_ROOT"

SEEKUI_WORK="${SEEKUI_WORK:-${SCRATCH:-$REPO_ROOT/.scratch}/seekui}"
OUTPUT_DIR="$SEEKUI_WORK/outputs"
OUT_DIR="${OUT_DIR:-$OUTPUT_DIR/devtest_stopping}"
MODE="${MODE:-present_only}"
DEV_FRACTION="${DEV_FRACTION:-0.5}"
SEED="${SEED:-42}"
BOOTSTRAP="${BOOTSTRAP:-1000}"
THRESHOLD_STEP="${THRESHOLD_STEP:-0.05}"
SPLITS="${SPLITS:-random image}"

module load miniconda3/25.9.1
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate seekui

mkdir -p "$OUT_DIR"

for split_by in $SPLITS; do
  python scripts_research/evaluate_stopping_devtest.py \
    --model SeekUI="$OUTPUT_DIR/present_absent_predictions_SeekUI.json:$OUTPUT_DIR/stopping_evidence/SeekUI_stopping_evidence.csv" \
    --model SeekUI_sft="$OUTPUT_DIR/present_absent_predictions_SeekUI_sft.json:$OUTPUT_DIR/stopping_evidence/SeekUI_sft_stopping_evidence.csv" \
    --mode "$MODE" \
    --split-by "$split_by" \
    --dev-fraction "$DEV_FRACTION" \
    --seed "$SEED" \
    --threshold-step "$THRESHOLD_STEP" \
    --bootstrap "$BOOTSTRAP" \
    --output-json "$OUT_DIR/devtest_stopping_${MODE}_${split_by}.json" \
    --output-csv "$OUT_DIR/devtest_stopping_${MODE}_${split_by}.csv" \
    --output-md "$OUT_DIR/devtest_stopping_${MODE}_${split_by}.md"

  echo "Dev/test stopping outputs for split=$split_by:"
  echo "  $OUT_DIR/devtest_stopping_${MODE}_${split_by}.md"
  echo "  $OUT_DIR/devtest_stopping_${MODE}_${split_by}.csv"
  echo "  $OUT_DIR/devtest_stopping_${MODE}_${split_by}.json"
done
