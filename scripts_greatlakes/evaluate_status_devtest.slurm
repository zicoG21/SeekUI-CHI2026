#!/usr/bin/env bash
#SBATCH --job-name=seekui-devtest-status
#SBATCH --account=engin1
#SBATCH --partition=standard
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G
#SBATCH --time=00:15:00
#SBATCH --output=seekui-devtest-status-%j.out

set -euo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:-$(pwd)}"
cd "$REPO_ROOT"

SEEKUI_WORK="${SEEKUI_WORK:-/scratch/engin_root/engin1/$USER/seekui}"
OUTPUT_DIR="$SEEKUI_WORK/outputs"
OUT_DIR="${OUT_DIR:-$OUTPUT_DIR/devtest_status}"
MODEL_NAME="${MODEL_NAME:-SeekUI}"
SPLITS="${SPLITS:-random image}"
DEV_FRACTION="${DEV_FRACTION:-0.5}"
SEED="${SEED:-42}"
BOOTSTRAP="${BOOTSTRAP:-1000}"

if [[ -n "${CONDA_MODULE:-}" ]]; then
  module load "$CONDA_MODULE"
else
  module load python3.10-anaconda/2023.03
fi
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate "${CONDA_ENV:-seekui}"

mkdir -p "$OUT_DIR"

DEFAULT_MODEL_SPECS=(
  "${MODEL_NAME}_prompt=$OUTPUT_DIR/present_absent_predictions_${MODEL_NAME}.json"
  "${MODEL_NAME}_vlm_evidence=$OUTPUT_DIR/vlm_evidence_predictions_${MODEL_NAME}_vlm_evidence_evidence_aware.json"
)

if [[ -n "${MODEL_SPECS:-}" ]]; then
  # shellcheck disable=SC2206
  SPECS=($MODEL_SPECS)
else
  SPECS=("${DEFAULT_MODEL_SPECS[@]}")
fi

prediction_args=()
for spec in "${SPECS[@]}"; do
  prediction_args+=(--prediction "$spec")
done

baseline_name="${BASELINE_NAME:-${SPECS[0]%%=*}}"

for split_by in $SPLITS; do
  python scripts_research/evaluate_status_devtest.py \
    "${prediction_args[@]}" \
    --baseline-name "$baseline_name" \
    --split-by "$split_by" \
    --dev-fraction "$DEV_FRACTION" \
    --seed "$SEED" \
    --bootstrap "$BOOTSTRAP" \
    --output-json "$OUT_DIR/devtest_status_${MODEL_NAME}_${split_by}.json" \
    --output-csv "$OUT_DIR/devtest_status_${MODEL_NAME}_${split_by}.csv" \
    --output-md "$OUT_DIR/devtest_status_${MODEL_NAME}_${split_by}.md"

  echo "Dev/test status outputs for model=$MODEL_NAME split=$split_by:"
  echo "  $OUT_DIR/devtest_status_${MODEL_NAME}_${split_by}.md"
  cat "$OUT_DIR/devtest_status_${MODEL_NAME}_${split_by}.md"
done
