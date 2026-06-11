#!/usr/bin/env bash
#SBATCH --job-name=seekui-af-visual
#SBATCH --account=notchpeak-shared-short
#SBATCH --partition=notchpeak-shared-short
#SBATCH --cpus-per-task=4
#SBATCH --mem=12G
#SBATCH --time=00:45:00
#SBATCH --output=seekui-af-visual-%j.out

set -euo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:-$(pwd)}"
cd "$REPO_ROOT"

SEEKUI_WORK="${SEEKUI_WORK:-${SCRATCH:-$REPO_ROOT/.scratch}/seekui}"
DATA_DIR="$SEEKUI_WORK/data"
OUTPUT_ROOT="$SEEKUI_WORK/outputs"
OUTPUT_DIR="${OUTPUT_DIR:-$OUTPUT_ROOT/annotation_free_visual_stopping_evidence}"
OCR_CANDIDATES="${OCR_CANDIDATES:-$OUTPUT_ROOT/ocr_candidates_tesseract.json}"
MIN_OCR_CONF="${MIN_OCR_CONF:-35}"
VISUAL_MAX_SIDE="${VISUAL_MAX_SIDE:-320}"
VISUAL_EDGE_THRESHOLD="${VISUAL_EDGE_THRESHOLD:-45}"
VISUAL_MIN_AREA="${VISUAL_MIN_AREA:-8}"
VISUAL_MIN_SIZE="${VISUAL_MIN_SIZE:-3}"
VISUAL_MAX_PROPOSALS="${VISUAL_MAX_PROPOSALS:-80}"

module load miniconda3/25.9.1
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate seekui

mkdir -p "$OUTPUT_DIR"

python scripts_research/analyze_annotation_free_stopping_evidence.py \
  --ocr-candidates "$OCR_CANDIDATES" \
  --target2text "$DATA_DIR/target2text.json" \
  --image-root "$DATA_DIR" \
  --out-dir "$OUTPUT_DIR" \
  --prediction "SeekUI=$OUTPUT_ROOT/present_absent_predictions_SeekUI.json" \
  --prediction "SeekUI_sft=$OUTPUT_ROOT/present_absent_predictions_SeekUI_sft.json" \
  --min-ocr-conf "$MIN_OCR_CONF" \
  --include-visual-proposals \
  --visual-max-side "$VISUAL_MAX_SIDE" \
  --visual-edge-threshold "$VISUAL_EDGE_THRESHOLD" \
  --visual-min-area "$VISUAL_MIN_AREA" \
  --visual-min-size "$VISUAL_MIN_SIZE" \
  --visual-max-proposals "$VISUAL_MAX_PROPOSALS"

echo "Annotation-free visual stopping evidence summary: $OUTPUT_DIR/annotation_free_stopping_evidence_summary.md"
cat "$OUTPUT_DIR/annotation_free_stopping_evidence_summary.md"
