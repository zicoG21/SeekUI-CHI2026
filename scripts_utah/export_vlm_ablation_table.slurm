#!/usr/bin/env bash
#SBATCH --job-name=seekui-vlm-table
#SBATCH --account=notchpeak-shared-short
#SBATCH --partition=notchpeak-shared-short
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=00:05:00
#SBATCH --output=seekui-vlm-table-%j.out

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

include_args=()
if [[ "${INCLUDE_PILOTS:-0}" != "0" ]]; then
  include_args+=(--include-pilots)
fi

python scripts_research/export_vlm_ablation_table.py \
  --outputs-dir "$OUTPUT_DIR" \
  --output-csv "$OUT_DIR/vlm_ablation_table.csv" \
  --output-md "$OUT_DIR/vlm_ablation_table.md" \
  "${include_args[@]}"

echo "VLM ablation table: $OUT_DIR/vlm_ablation_table.md"
cat "$OUT_DIR/vlm_ablation_table.md"
