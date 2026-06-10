#!/usr/bin/env bash
#SBATCH --job-name=seekui-sheet-sum
#SBATCH --account=notchpeak-shared-short
#SBATCH --partition=notchpeak-shared-short
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=00:05:00
#SBATCH --output=seekui-sheet-sum-%j.out

set -euo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:-$(pwd)}"
cd "$REPO_ROOT"

SEEKUI_WORK="${SEEKUI_WORK:-${SCRATCH:-$REPO_ROOT/.scratch}/seekui}"
OUTPUT_DIR="$SEEKUI_WORK/outputs"
REVIEW_DIR="${REVIEW_DIR:-$OUTPUT_DIR/contact_sheet_review}"
INPUT_CSV="${INPUT_CSV:-$REVIEW_DIR/combined_contact_sheet_review.csv}"

module load miniconda3/25.9.1
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate seekui

python scripts_research/summarize_contact_sheet_review.py \
  --input-csv "$INPUT_CSV" \
  --output-json "$REVIEW_DIR/combined_contact_sheet_review_summary.json" \
  --output-csv "$REVIEW_DIR/combined_contact_sheet_review_summary.csv" \
  --output-md "$REVIEW_DIR/combined_contact_sheet_review_summary.md"

echo "Contact-sheet review summary: $REVIEW_DIR/combined_contact_sheet_review_summary.md"
cat "$REVIEW_DIR/combined_contact_sheet_review_summary.md"
