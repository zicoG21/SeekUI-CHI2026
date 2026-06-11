#!/usr/bin/env bash
#SBATCH --job-name=seekui-realabs-merge
#SBATCH --account=notchpeak-shared-short
#SBATCH --partition=notchpeak-shared-short
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=00:05:00
#SBATCH --output=seekui-realabs-merge-%j.out

set -euo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:-$(pwd)}"
cd "$REPO_ROOT"

SEEKUI_WORK="${SEEKUI_WORK:-${SCRATCH:-$REPO_ROOT/.scratch}/seekui}"
OUT_DIR="${OUT_DIR:-$SEEKUI_WORK/outputs/real_absent_validation}"
BASE_CSV="${BASE_CSV:-$OUT_DIR/real_absent_validation_prefilled.csv}"
REVIEW_CSV="${REVIEW_CSV:-$OUT_DIR/review_package/real_absent_rows_to_fill.csv}"
OUTPUT_CSV="${OUTPUT_CSV:-$OUT_DIR/real_absent_validation_filled.csv}"
SUMMARY_MD="${SUMMARY_MD:-$OUT_DIR/real_absent_validation_merge.md}"

module load miniconda3/25.9.1
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate seekui

python scripts_research/merge_real_absent_review.py \
  --base-csv "$BASE_CSV" \
  --review-csv "$REVIEW_CSV" \
  --output-csv "$OUTPUT_CSV" \
  --summary-md "$SUMMARY_MD"

cat "$SUMMARY_MD"
