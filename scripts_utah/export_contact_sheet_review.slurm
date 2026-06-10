#!/usr/bin/env bash
#SBATCH --job-name=seekui-sheet-review
#SBATCH --account=notchpeak-shared-short
#SBATCH --partition=notchpeak-shared-short
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=00:05:00
#SBATCH --output=seekui-sheet-review-%j.out

set -euo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:-$(pwd)}"
cd "$REPO_ROOT"

SEEKUI_WORK="${SEEKUI_WORK:-${SCRATCH:-$REPO_ROOT/.scratch}/seekui}"
OUTPUT_DIR="$SEEKUI_WORK/outputs"
OUT_DIR="${OUT_DIR:-$OUTPUT_DIR/contact_sheet_review}"

module load miniconda3/25.9.1
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate seekui

mkdir -p "$OUT_DIR"

python scripts_research/export_contact_sheet_review.py \
  --case-dir "$OUTPUT_DIR/combined_cases/SeekUI_and_present_only_best_f1" \
  --case-dir "$OUTPUT_DIR/combined_cases/SeekUI_sft_and_present_only_best_f1" \
  --output-csv "$OUT_DIR/combined_contact_sheet_review.csv" \
  --output-md "$OUT_DIR/combined_contact_sheet_review.md" \
  --output-json "$OUT_DIR/combined_contact_sheet_review.json"

echo "Contact-sheet review sheet: $OUT_DIR/combined_contact_sheet_review.csv"
cat "$OUT_DIR/combined_contact_sheet_review.md"
