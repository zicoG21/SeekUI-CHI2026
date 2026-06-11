#!/usr/bin/env bash
#SBATCH --job-name=seekui-realabs-sheet
#SBATCH --account=notchpeak-shared-short
#SBATCH --partition=notchpeak-shared-short
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=00:05:00
#SBATCH --output=seekui-realabs-sheet-%j.out

set -euo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:-$(pwd)}"
cd "$REPO_ROOT"

SEEKUI_WORK="${SEEKUI_WORK:-${SCRATCH:-$REPO_ROOT/.scratch}/seekui}"
DATA_DIR="${SEEKUI_DATA_DIR:-$SEEKUI_WORK/data}"
OUTPUT_DIR="$SEEKUI_WORK/outputs"
OUT_DIR="${OUT_DIR:-$OUTPUT_DIR/real_absent_validation}"

module load miniconda3/25.9.1
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate seekui

mkdir -p "$OUT_DIR"

python scripts_research/export_real_absent_validation_sheet.py \
  --scanpath "$DATA_DIR/scanpath_train_explanation.json" \
  --target2text "$DATA_DIR/target2text.json" \
  --output-csv "$OUT_DIR/real_absent_validation_starter.csv" \
  --output-md "$OUT_DIR/real_absent_validation_starter.md" \
  --present-count "${PRESENT_COUNT:-50}" \
  --absent-count "${ABSENT_COUNT:-50}" \
  --seed "${SEED:-42}"

echo "Starter CSV: $OUT_DIR/real_absent_validation_starter.csv"
echo "Starter notes: $OUT_DIR/real_absent_validation_starter.md"
cat "$OUT_DIR/real_absent_validation_starter.md"
