#!/usr/bin/env bash
#SBATCH --job-name=seekui-abs-audit
#SBATCH --account=notchpeak-shared-short
#SBATCH --partition=notchpeak-shared-short
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:15:00
#SBATCH --output=seekui-abs-audit-%j.out

set -euo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:-$(pwd)}"
cd "$REPO_ROOT"

SEEKUI_WORK="${SEEKUI_WORK:-${SCRATCH:-$REPO_ROOT/.scratch}/seekui}"
DATA_DIR="$SEEKUI_WORK/data"
OUTPUT_DIR="$SEEKUI_WORK/outputs"
OCR_CANDIDATES="${OCR_CANDIDATES:-$OUTPUT_DIR/ocr_candidates_tesseract.json}"
OUT_DIR="${OUT_DIR:-$OUTPUT_DIR/absent_benchmark_sanity}"

module load miniconda3/25.9.1
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate seekui

python scripts_research/audit_absent_benchmark.py \
  --reference "$DATA_DIR/scanpath_train_explanation.json" \
  --dataset "$DATA_DIR/present_absent_synthetic_2724.json" \
  --target2text "$DATA_DIR/target2text.json" \
  --ocr-candidates "$OCR_CANDIDATES" \
  --out-dir "$OUT_DIR"

echo "Absent benchmark sanity summary: $OUT_DIR/absent_benchmark_sanity.md"
