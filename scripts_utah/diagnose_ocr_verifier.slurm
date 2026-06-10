#!/usr/bin/env bash
#SBATCH --job-name=seekui-ocr-diag
#SBATCH --account=notchpeak-shared-short
#SBATCH --partition=notchpeak-shared-short
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:10:00
#SBATCH --output=seekui-ocr-diag-%j.out

set -euo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:-$(pwd)}"
cd "$REPO_ROOT"

SEEKUI_WORK="${SEEKUI_WORK:-${SCRATCH:-$REPO_ROOT/.scratch}/seekui}"
OUTPUT_DIR="$SEEKUI_WORK/outputs"
OUT_DIR="${OUT_DIR:-$OUTPUT_DIR/ocr_diagnosis}"
THRESHOLD="${THRESHOLD:-0.4}"

module load miniconda3/25.9.1
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate seekui

mkdir -p "$OUT_DIR"

python scripts_research/diagnose_ocr_verifier.py \
  --threshold "$THRESHOLD" \
  --ocr-detail "$OUTPUT_DIR/present_absent_predictions_SeekUI_ocr_candidate_verifier_present_only_details.csv" \
  --ocr-detail "$OUTPUT_DIR/present_absent_predictions_SeekUI_sft_ocr_candidate_verifier_present_only_details.csv" \
  --combined-detail "$OUTPUT_DIR/present_absent_predictions_SeekUI_combined_and_present_only_best_f1_details.csv" \
  --combined-detail "$OUTPUT_DIR/present_absent_predictions_SeekUI_sft_combined_and_present_only_best_f1_details.csv" \
  --absent-ocr-leaks "$OUTPUT_DIR/absent_benchmark_sanity/absent_ocr_leaks.csv" \
  --out-dir "$OUT_DIR"

echo "OCR diagnosis: $OUT_DIR/ocr_verifier_diagnosis.md"
cat "$OUT_DIR/ocr_verifier_diagnosis.md"
