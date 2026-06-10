#!/usr/bin/env bash
#SBATCH --job-name=seekui-stop-evidence
#SBATCH --account=notchpeak-shared-short
#SBATCH --partition=notchpeak-shared-short
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=01:00:00
#SBATCH --output=seekui-stop-evidence-%j.out

set -euo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:-$(pwd)}"
cd "$REPO_ROOT"

SEEKUI_WORK="${SEEKUI_WORK:-${SCRATCH:-$REPO_ROOT/.scratch}/seekui}"
OUTPUT_DIR="${OUTPUT_DIR:-$SEEKUI_WORK/outputs/stopping_evidence}"

module load miniconda3/25.9.1
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate seekui

python scripts_research/analyze_prediction_stopping_evidence.py \
  --reference "$SEEKUI_WORK/data/scanpath_train_explanation.json" \
  --target2text "$SEEKUI_WORK/data/target2text.json" \
  --image-root "$SEEKUI_WORK/data" \
  --out-dir "$OUTPUT_DIR" \
  --prediction SeekUI="$SEEKUI_WORK/outputs/present_absent_predictions_SeekUI.json" \
  --prediction SeekUI_sft="$SEEKUI_WORK/outputs/present_absent_predictions_SeekUI_sft.json"

echo "Stopping evidence summary: $OUTPUT_DIR/stopping_evidence_summary.md"
