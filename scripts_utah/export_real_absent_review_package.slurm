#!/usr/bin/env bash
#SBATCH --job-name=seekui-realabs-review
#SBATCH --account=notchpeak-shared-short
#SBATCH --partition=notchpeak-shared-short
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=00:05:00
#SBATCH --output=seekui-realabs-review-%j.out

set -euo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:-$(pwd)}"
cd "$REPO_ROOT"

SEEKUI_WORK="${SEEKUI_WORK:-${SCRATCH:-$REPO_ROOT/.scratch}/seekui}"
DATA_DIR="${SEEKUI_DATA_DIR:-$SEEKUI_WORK/data}"
OUT_DIR="${OUT_DIR:-$SEEKUI_WORK/outputs/real_absent_validation/review_package}"
INPUT_CSV="${INPUT_CSV:-$SEEKUI_WORK/outputs/real_absent_validation/real_absent_validation_prefilled.csv}"

module load miniconda3/25.9.1
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate seekui

python scripts_research/export_real_absent_review_package.py \
  --input-csv "$INPUT_CSV" \
  --image-root "$DATA_DIR" \
  --out-dir "$OUT_DIR"

cat "$OUT_DIR/real_absent_review_package.md"
