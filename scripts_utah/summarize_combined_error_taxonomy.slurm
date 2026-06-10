#!/usr/bin/env bash
#SBATCH --job-name=seekui-taxonomy
#SBATCH --account=notchpeak-shared-short
#SBATCH --partition=notchpeak-shared-short
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:10:00
#SBATCH --output=seekui-taxonomy-%j.out

set -euo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:-$(pwd)}"
cd "$REPO_ROOT"

SEEKUI_WORK="${SEEKUI_WORK:-${SCRATCH:-$REPO_ROOT/.scratch}/seekui}"
OUTPUT_DIR="$SEEKUI_WORK/outputs"
OUT_DIR="${OUT_DIR:-$OUTPUT_DIR/combined_error_taxonomy}"

module load miniconda3/25.9.1
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate seekui

mkdir -p "$OUT_DIR"

python scripts_research/summarize_combined_error_taxonomy.py \
  --case-dir "$OUTPUT_DIR/combined_cases/SeekUI_and_present_only_best_f1" \
  --case-dir "$OUTPUT_DIR/combined_cases/SeekUI_sft_and_present_only_best_f1" \
  --out-dir "$OUT_DIR"

echo "Taxonomy summary: $OUT_DIR/combined_error_taxonomy_summary.md"
cat "$OUT_DIR/combined_error_taxonomy_summary.md"
