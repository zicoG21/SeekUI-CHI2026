#!/usr/bin/env bash
#SBATCH --job-name=seekui-tradeoff
#SBATCH --account=notchpeak-shared-short
#SBATCH --partition=notchpeak-shared-short
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=00:05:00
#SBATCH --output=seekui-tradeoff-%j.out

set -euo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:-$(pwd)}"
cd "$REPO_ROOT"

SEEKUI_WORK="${SEEKUI_WORK:-${SCRATCH:-$REPO_ROOT/.scratch}/seekui}"
OUTPUT_DIR="$SEEKUI_WORK/outputs"
OUT_DIR="${OUT_DIR:-$OUTPUT_DIR/tradeoff_utility}"
COST_RATIOS="${COST_RATIOS:-1:1,2:1,5:1,10:1,1:2,1:5,1:10}"

module load miniconda3/25.9.1
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate seekui

python scripts_research/export_tradeoff_utility.py \
  --work-dir "$SEEKUI_WORK" \
  --out-dir "$OUT_DIR" \
  --cost-ratios "$COST_RATIOS"

echo "Tradeoff utility summary: $OUT_DIR/tradeoff_summary.md"
cat "$OUT_DIR/tradeoff_summary.md"
