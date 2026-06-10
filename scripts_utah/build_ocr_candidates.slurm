#!/usr/bin/env bash
#SBATCH --job-name=seekui-ocr
#SBATCH --account=notchpeak-shared-short
#SBATCH --partition=notchpeak-shared-short
#SBATCH --cpus-per-task=4
#SBATCH --mem=12G
#SBATCH --time=01:00:00
#SBATCH --output=seekui-ocr-%j.out

set -euo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:-$(pwd)}"
cd "$REPO_ROOT"

SEEKUI_WORK="${SEEKUI_WORK:-${SCRATCH:-$REPO_ROOT/.scratch}/seekui}"
DATA_DIR="$SEEKUI_WORK/data"
OUTPUT_DIR="$SEEKUI_WORK/outputs"
INPUT_JSON="${INPUT_JSON:-$DATA_DIR/present_absent_synthetic_2724.json}"
OUTPUT_PATH="${OUTPUT_PATH:-$OUTPUT_DIR/ocr_candidates_tesseract.json}"
OCR_LIMIT="${OCR_LIMIT:-0}"
MIN_CONF="${MIN_CONF:-35}"

module load miniconda3/25.9.1
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate seekui

if ! command -v tesseract >/dev/null 2>&1; then
  echo "tesseract was not found on PATH."
  echo "Try: module spider tesseract"
  echo "If CHPC has no module, run this in the conda env: conda install -y -c conda-forge tesseract"
  exit 1
fi

python scripts_research/build_ocr_candidates.py \
  --input-json "$INPUT_JSON" \
  --image-root "$DATA_DIR" \
  --output "$OUTPUT_PATH" \
  --limit "$OCR_LIMIT" \
  --min-conf "$MIN_CONF"

echo "OCR candidates: $OUTPUT_PATH"
