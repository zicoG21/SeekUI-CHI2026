#!/usr/bin/env bash
#SBATCH --job-name=seekui-vlm-hard
#SBATCH --account=owner-guest
#SBATCH --partition=notchpeak-shared-guest
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:20:00
#SBATCH --output=seekui-vlm-hard-%j.out

set -euo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:-$(pwd)}"
cd "$REPO_ROOT"

SEEKUI_WORK="${SEEKUI_WORK:-${SCRATCH:-$REPO_ROOT/.scratch}/seekui}"
OUTPUT_DIR="$SEEKUI_WORK/outputs"
MODEL_NAME="${MODEL_NAME:-SeekUI}"
VLM_LABEL="${VLM_LABEL:-${MODEL_NAME}_vlm_presence}"

module load miniconda3/25.9.1
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate seekui

combined_predictions="${COMBINED_PREDICTIONS:-$OUTPUT_DIR/present_absent_predictions_${MODEL_NAME}_combined_and_present_only_best_f1.json}"
vlm_predictions="${VLM_PREDICTIONS:-$OUTPUT_DIR/vlm_presence_predictions_${VLM_LABEL}.json}"
out_dir="${OUT_DIR:-$OUTPUT_DIR/vlm_hard_cases/${VLM_LABEL}_vs_${MODEL_NAME}_combined_and}"

case_args=()
case_dir="$OUTPUT_DIR/combined_cases/${MODEL_NAME}_and_present_only_best_f1"
if [[ -f "$case_dir/stopping_cases_index.csv" ]]; then
  case_args+=(--combined-case-index "$case_dir/stopping_cases_index.csv")
fi

python scripts_research/export_vlm_hard_cases.py \
  --combined-predictions "$combined_predictions" \
  --vlm-predictions "$vlm_predictions" \
  --out-dir "$out_dir" \
  --limit-per-type "${LIMIT_PER_TYPE:-100}" \
  "${case_args[@]}"

echo "VLM hard cases: $out_dir"
cat "$out_dir/manifest.json"
