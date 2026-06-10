#!/usr/bin/env bash
#SBATCH --job-name=seekui-cog-stop
#SBATCH --account=notchpeak-shared-short
#SBATCH --partition=notchpeak-shared-short
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:20:00
#SBATCH --output=seekui-cog-stop-%j.out

set -euo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:-$(pwd)}"
cd "$REPO_ROOT"

SEEKUI_WORK="${SEEKUI_WORK:-${SCRATCH:-$REPO_ROOT/.scratch}/seekui}"
OUTPUT_DIR="$SEEKUI_WORK/outputs"
STOP_DIR="$OUTPUT_DIR/stopping_evidence"

SEEKUI_THRESHOLD="${SEEKUI_THRESHOLD:-0.20}"
SEEKUI_SFT_THRESHOLD="${SEEKUI_SFT_THRESHOLD:-0.10}"
STOPPING_MODE="${STOPPING_MODE:-override}"
RUN_PRESENT_ONLY="${RUN_PRESENT_ONLY:-1}"

module load miniconda3/25.9.1
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate seekui

python scripts_research/apply_cognitive_stopping.py \
  --predictions "$OUTPUT_DIR/present_absent_predictions_SeekUI.json" \
  --evidence "$STOP_DIR/SeekUI_stopping_evidence.csv" \
  --threshold "$SEEKUI_THRESHOLD" \
  --mode "$STOPPING_MODE" \
  --output "$OUTPUT_DIR/present_absent_predictions_SeekUI_cognitive_stop.json" \
  --metrics-output "$OUTPUT_DIR/present_absent_predictions_SeekUI_cognitive_stop_status_eval.json"

python scripts_research/apply_cognitive_stopping.py \
  --predictions "$OUTPUT_DIR/present_absent_predictions_SeekUI_sft.json" \
  --evidence "$STOP_DIR/SeekUI_sft_stopping_evidence.csv" \
  --threshold "$SEEKUI_SFT_THRESHOLD" \
  --mode "$STOPPING_MODE" \
  --output "$OUTPUT_DIR/present_absent_predictions_SeekUI_sft_cognitive_stop.json" \
  --metrics-output "$OUTPUT_DIR/present_absent_predictions_SeekUI_sft_cognitive_stop_status_eval.json"

echo "Cognitive stopping outputs:"
echo "  $OUTPUT_DIR/present_absent_predictions_SeekUI_cognitive_stop_status_eval.json"
echo "  $OUTPUT_DIR/present_absent_predictions_SeekUI_sft_cognitive_stop_status_eval.json"

if [[ "$RUN_PRESENT_ONLY" == "1" ]]; then
  python scripts_research/apply_cognitive_stopping.py \
    --predictions "$OUTPUT_DIR/present_absent_predictions_SeekUI.json" \
    --evidence "$STOP_DIR/SeekUI_stopping_evidence.csv" \
    --threshold "$SEEKUI_THRESHOLD" \
    --mode present_only \
    --output "$OUTPUT_DIR/present_absent_predictions_SeekUI_cognitive_stop_present_only.json" \
    --metrics-output "$OUTPUT_DIR/present_absent_predictions_SeekUI_cognitive_stop_present_only_status_eval.json"

  python scripts_research/apply_cognitive_stopping.py \
    --predictions "$OUTPUT_DIR/present_absent_predictions_SeekUI_sft.json" \
    --evidence "$STOP_DIR/SeekUI_sft_stopping_evidence.csv" \
    --threshold "$SEEKUI_SFT_THRESHOLD" \
    --mode present_only \
    --output "$OUTPUT_DIR/present_absent_predictions_SeekUI_sft_cognitive_stop_present_only.json" \
    --metrics-output "$OUTPUT_DIR/present_absent_predictions_SeekUI_sft_cognitive_stop_present_only_status_eval.json"

  echo "Conservative present-only stopping outputs:"
  echo "  $OUTPUT_DIR/present_absent_predictions_SeekUI_cognitive_stop_present_only_status_eval.json"
  echo "  $OUTPUT_DIR/present_absent_predictions_SeekUI_sft_cognitive_stop_present_only_status_eval.json"
fi
