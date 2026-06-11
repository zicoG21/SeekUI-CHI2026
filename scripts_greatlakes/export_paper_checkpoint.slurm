#!/usr/bin/env bash
#SBATCH --job-name=seekui-paper-ckpt
#SBATCH --account=engin1
#SBATCH --partition=standard
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=00:05:00
#SBATCH --output=seekui-paper-ckpt-%j.out

set -euo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:-$(pwd)}"
cd "$REPO_ROOT"

SEEKUI_WORK="${SEEKUI_WORK:-/scratch/engin_root/engin1/$USER/seekui}"
OUT_DIR="${OUT_DIR:-$SEEKUI_WORK/outputs/paper_checkpoint}"

if [[ -n "${CONDA_MODULE:-}" ]]; then
  module load "$CONDA_MODULE"
else
  module load python3.10-anaconda/2023.03
fi
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate "${CONDA_ENV:-seekui}"

mkdir -p "$OUT_DIR"

python scripts_research/export_paper_checkpoint.py \
  --work-dir "$SEEKUI_WORK" \
  --output-md "$OUT_DIR/paper_checkpoint.md" \
  --output-json "$OUT_DIR/paper_checkpoint.json"

echo "Paper checkpoint: $OUT_DIR/paper_checkpoint.md"
cat "$OUT_DIR/paper_checkpoint.md"
