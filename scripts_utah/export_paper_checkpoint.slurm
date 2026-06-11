#!/usr/bin/env bash
#SBATCH --job-name=seekui-paper-ckpt
#SBATCH --account=notchpeak-shared-short
#SBATCH --partition=notchpeak-shared-short
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=00:05:00
#SBATCH --output=seekui-paper-ckpt-%j.out

set -euo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:-$(pwd)}"
cd "$REPO_ROOT"

SEEKUI_WORK="${SEEKUI_WORK:-${SCRATCH:-$REPO_ROOT/.scratch}/seekui}"
OUT_DIR="${OUT_DIR:-$SEEKUI_WORK/outputs/paper_checkpoint}"

module load miniconda3/25.9.1
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate seekui

mkdir -p "$OUT_DIR"

python scripts_research/export_paper_checkpoint.py \
  --work-dir "$SEEKUI_WORK" \
  --output-md "$OUT_DIR/paper_checkpoint.md" \
  --output-json "$OUT_DIR/paper_checkpoint.json"

echo "Paper checkpoint: $OUT_DIR/paper_checkpoint.md"
cat "$OUT_DIR/paper_checkpoint.md"
