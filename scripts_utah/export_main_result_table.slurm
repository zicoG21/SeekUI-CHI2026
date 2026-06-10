#!/usr/bin/env bash
#SBATCH --job-name=seekui-main-table
#SBATCH --account=notchpeak-shared-short
#SBATCH --partition=notchpeak-shared-short
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=00:05:00
#SBATCH --output=seekui-main-table-%j.out

set -euo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:-$(pwd)}"
cd "$REPO_ROOT"

SEEKUI_WORK="${SEEKUI_WORK:-${SCRATCH:-$REPO_ROOT/.scratch}/seekui}"
OUTPUT_DIR="$SEEKUI_WORK/outputs"
OUT_DIR="${OUT_DIR:-$OUTPUT_DIR/paper_tables}"

module load miniconda3/25.9.1
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate seekui

mkdir -p "$OUT_DIR"

python scripts_research/export_main_result_table.py \
  --random-json "$OUTPUT_DIR/devtest_combined/devtest_combined_and_present_only_random.json" \
  --image-json "$OUTPUT_DIR/devtest_combined/devtest_combined_and_present_only_image.json" \
  --output-csv "$OUT_DIR/main_result_table.csv" \
  --output-md "$OUT_DIR/main_result_table.md"

echo "Main result table: $OUT_DIR/main_result_table.md"
cat "$OUT_DIR/main_result_table.md"
