#!/usr/bin/env bash
#SBATCH --job-name=seekui-af-evidence
#SBATCH --account=notchpeak-shared-short
#SBATCH --partition=notchpeak-shared-short
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=01:00:00
#SBATCH --output=seekui-af-evidence-%j.out

set -euo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:-$(pwd)}"
cd "$REPO_ROOT"

SEEKUI_WORK="${SEEKUI_WORK:-${SCRATCH:-$REPO_ROOT/.scratch}/seekui}"
DATA_DIR="$SEEKUI_WORK/data"
OUTPUT_ROOT="$SEEKUI_WORK/outputs"
OUTPUT_DIR="${OUTPUT_DIR:-$OUTPUT_ROOT/annotation_free_stopping_evidence}"
OCR_CANDIDATES="${OCR_CANDIDATES:-$OUTPUT_ROOT/ocr_candidates_tesseract.json}"
MIN_OCR_CONF="${MIN_OCR_CONF:-35}"

module load miniconda3/25.9.1
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate seekui

python scripts_research/analyze_annotation_free_stopping_evidence.py \
  --ocr-candidates "$OCR_CANDIDATES" \
  --target2text "$DATA_DIR/target2text.json" \
  --image-root "$DATA_DIR" \
  --out-dir "$OUTPUT_DIR" \
  --min-ocr-conf "$MIN_OCR_CONF" \
  --prediction SeekUI="$OUTPUT_ROOT/present_absent_predictions_SeekUI.json" \
  --prediction SeekUI_sft="$OUTPUT_ROOT/present_absent_predictions_SeekUI_sft.json"

echo "Annotation-free stopping evidence summary: $OUTPUT_DIR/annotation_free_stopping_evidence_summary.md"
