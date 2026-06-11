#!/usr/bin/env bash
#SBATCH --job-name=seekui-realabs-sum
#SBATCH --account=notchpeak-shared-short
#SBATCH --partition=notchpeak-shared-short
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=00:05:00
#SBATCH --output=seekui-realabs-sum-%j.out

set -euo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:-$(pwd)}"
cd "$REPO_ROOT"

SEEKUI_WORK="${SEEKUI_WORK:-${SCRATCH:-$REPO_ROOT/.scratch}/seekui}"
OUT_DIR="${OUT_DIR:-$SEEKUI_WORK/outputs/real_absent_validation}"

module load miniconda3/25.9.1
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate seekui

python scripts_research/summarize_real_absent_results.py \
  --work-dir "$SEEKUI_WORK" \
  --output-json "$OUT_DIR/real_absent_results.json" \
  --output-csv "$OUT_DIR/real_absent_results.csv" \
  --output-md "$OUT_DIR/real_absent_results.md"

echo "Real-absent results: $OUT_DIR/real_absent_results.md"
cat "$OUT_DIR/real_absent_results.md"
