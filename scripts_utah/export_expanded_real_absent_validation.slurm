#!/usr/bin/env bash
#SBATCH --job-name=seekui-realabs-expand
#SBATCH --account=notchpeak-shared-short
#SBATCH --partition=notchpeak-shared-short
#SBATCH --cpus-per-task=2
#SBATCH --mem=6G
#SBATCH --time=00:10:00
#SBATCH --output=seekui-realabs-expand-%j.out

set -euo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:-$(pwd)}"
cd "$REPO_ROOT"

SEEKUI_WORK="${SEEKUI_WORK:-${SCRATCH:-$REPO_ROOT/.scratch}/seekui}"
DATA_DIR="${SEEKUI_DATA_DIR:-$SEEKUI_WORK/data}"
OUTPUT_DIR="$SEEKUI_WORK/outputs"
PRESENT_COUNT="${PRESENT_COUNT:-100}"
ABSENT_COUNT="${ABSENT_COUNT:-100}"
TOTAL_COUNT=$((PRESENT_COUNT + ABSENT_COUNT))
OUT_DIR="${OUT_DIR:-$OUTPUT_DIR/real_absent_validation_${TOTAL_COUNT}}"
REVIEW_DIR="${REVIEW_DIR:-$OUT_DIR/review_package}"
SEED="${SEED:-43}"

module load miniconda3/25.9.1
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate seekui

mkdir -p "$OUT_DIR"

python scripts_research/export_real_absent_validation_sheet.py \
  --scanpath "$DATA_DIR/scanpath_train_explanation.json" \
  --target2text "$DATA_DIR/target2text.json" \
  --output-csv "$OUT_DIR/real_absent_validation_starter.csv" \
  --output-md "$OUT_DIR/real_absent_validation_starter.md" \
  --present-count "$PRESENT_COUNT" \
  --absent-count "$ABSENT_COUNT" \
  --seed "$SEED"

python scripts_research/prefill_real_absent_validation_sheet.py \
  --input-csv "$OUT_DIR/real_absent_validation_starter.csv" \
  --output-csv "$OUT_DIR/real_absent_validation_prefilled.csv" \
  --output-md "$OUT_DIR/real_absent_validation_prefilled.md"

python scripts_research/export_real_absent_review_package.py \
  --input-csv "$OUT_DIR/real_absent_validation_prefilled.csv" \
  --image-root "$DATA_DIR" \
  --out-dir "$REVIEW_DIR"

echo "Expanded realistic absent validation starter:"
cat "$OUT_DIR/real_absent_validation_starter.md"
echo
echo "Prefill summary:"
cat "$OUT_DIR/real_absent_validation_prefilled.md"
echo
echo "Review package:"
cat "$REVIEW_DIR/real_absent_review_package.md"
