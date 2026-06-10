#!/usr/bin/env bash
#SBATCH --job-name=seekui-stop-cases
#SBATCH --account=notchpeak-shared-short
#SBATCH --partition=notchpeak-shared-short
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=00:30:00
#SBATCH --output=seekui-stop-cases-%j.out

set -euo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:-$(pwd)}"
cd "$REPO_ROOT"

SEEKUI_WORK="${SEEKUI_WORK:-${SCRATCH:-$REPO_ROOT/.scratch}/seekui}"
OUTPUT_DIR="$SEEKUI_WORK/outputs"
DATA_DIR="$SEEKUI_WORK/data"
MODEL_NAME="${MODEL_NAME:-SeekUI}"
CASE_LIMIT="${CASE_LIMIT:-40}"
OUT_DIR="${OUT_DIR:-$OUTPUT_DIR/stopping_cases/${MODEL_NAME}_present_only}"

module load miniconda3/25.9.1
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate seekui

python scripts_research/mine_stopping_cases.py \
  --original "$OUTPUT_DIR/present_absent_predictions_${MODEL_NAME}.json" \
  --adjusted "$OUTPUT_DIR/present_absent_predictions_${MODEL_NAME}_cognitive_stop_present_only.json" \
  --evidence "$OUTPUT_DIR/stopping_evidence/${MODEL_NAME}_stopping_evidence.csv" \
  --out-dir "$OUT_DIR" \
  --limit "$CASE_LIMIT"

for case_type in \
  corrected_absent_false_present \
  new_present_false_absent \
  corrected_present_false_absent \
  kept_absent_false_present; do
  json_path="$OUT_DIR/${case_type}.json"
  if [[ -s "$json_path" ]]; then
    python scripts_research/visualize_scanpaths.py \
      --json "$json_path" \
      --image-root "$DATA_DIR" \
      --out-dir "$OUT_DIR/visualizations/$case_type" \
      --limit "$CASE_LIMIT"
  fi
done

echo "Stopping case summary: $OUT_DIR/stopping_cases_summary.md"
