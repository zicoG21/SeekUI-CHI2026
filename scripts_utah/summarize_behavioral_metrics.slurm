#!/usr/bin/env bash
#SBATCH --job-name=seekui-behavior
#SBATCH --account=notchpeak-shared-short
#SBATCH --partition=notchpeak-shared-short
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:15:00
#SBATCH --output=seekui-behavior-%j.out

set -euo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:-$(pwd)}"
cd "$REPO_ROOT"

SEEKUI_WORK="${SEEKUI_WORK:-${SCRATCH:-$REPO_ROOT/.scratch}/seekui}"
OUTPUT_DIR="$SEEKUI_WORK/outputs"
OUT_DIR="${OUT_DIR:-$OUTPUT_DIR/behavioral_metrics}"

module load miniconda3/25.9.1
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate seekui

mkdir -p "$OUT_DIR"

python scripts_research/summarize_behavioral_metrics.py \
  --image-root "$SEEKUI_WORK/data" \
  --prediction "SeekUI_prompt=$OUTPUT_DIR/present_absent_predictions_SeekUI.json" \
  --prediction "SeekUI_cognitive=$OUTPUT_DIR/present_absent_predictions_SeekUI_cognitive_stop_present_only.json" \
  --prediction "SeekUI_combined_best_f1=$OUTPUT_DIR/present_absent_predictions_SeekUI_combined_and_present_only_best_f1.json" \
  --prediction "SeekUI_sft_prompt=$OUTPUT_DIR/present_absent_predictions_SeekUI_sft.json" \
  --prediction "SeekUI_sft_cognitive=$OUTPUT_DIR/present_absent_predictions_SeekUI_sft_cognitive_stop_present_only.json" \
  --prediction "SeekUI_sft_combined_best_f1=$OUTPUT_DIR/present_absent_predictions_SeekUI_sft_combined_and_present_only_best_f1.json" \
  --out-dir "$OUT_DIR"

echo "Behavioral summary: $OUT_DIR/behavioral_metrics_summary.md"
cat "$OUT_DIR/behavioral_metrics_summary.md"
