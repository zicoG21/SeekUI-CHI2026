#!/usr/bin/env bash
#SBATCH --job-name=seekui-vlm-table
#SBATCH --account=engin1
#SBATCH --partition=standard
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=00:05:00
#SBATCH --output=seekui-vlm-table-%j.out

set -euo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:-$(pwd)}"
cd "$REPO_ROOT"

SEEKUI_WORK="${SEEKUI_WORK:-/scratch/engin_root/engin1/$USER/seekui}"
OUTPUT_DIR="$SEEKUI_WORK/outputs"
OUT_DIR="${OUT_DIR:-$OUTPUT_DIR/paper_tables}"

if [[ -n "${CONDA_MODULE:-}" ]]; then
  module load "$CONDA_MODULE"
else
  module load python3.10-anaconda/2023.03
fi
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate "${CONDA_ENV:-seekui}"

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
