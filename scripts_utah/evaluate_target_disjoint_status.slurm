#!/usr/bin/env bash
#SBATCH --job-name=seekui-target-split
#SBATCH --account=notchpeak-shared-short
#SBATCH --partition=notchpeak-shared-short
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G
#SBATCH --time=00:30:00
#SBATCH --output=seekui-target-split-%j.out

set -euo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:-$(pwd)}"
cd "$REPO_ROOT"

SEEKUI_WORK="${SEEKUI_WORK:-${SCRATCH:-$REPO_ROOT/.scratch}/seekui}"
DATA_DIR="${SEEKUI_DATA_DIR:-$SEEKUI_WORK/data}"
OUTPUT_DIR="$SEEKUI_WORK/outputs"
OUT_DIR="${OUT_DIR:-$OUTPUT_DIR/devtest_status}"
SPLITS="${SPLITS:-target image_target}"
DEV_FRACTION="${DEV_FRACTION:-0.5}"
SEED="${SEED:-42}"
BOOTSTRAP="${BOOTSTRAP:-1000}"

module load miniconda3/25.9.1
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate seekui

mkdir -p "$OUT_DIR"

run_model() {
  local model="$1"
  local specs=(
    "${model}_prompt=$OUTPUT_DIR/present_absent_predictions_${model}.json"
    "${model}_combined=$OUTPUT_DIR/present_absent_predictions_${model}_combined_and_present_only_best_f1.json"
    "${model}_annotation_free=$OUTPUT_DIR/present_absent_predictions_${model}_annotation_free_combined_and_present_only_best_f1.json"
    "${model}_vlm_evidence=$OUTPUT_DIR/vlm_evidence_predictions_${model}_vlm_evidence_evidence_aware.json"
  )

  local prediction_args=()
  local existing_specs=()
  for spec in "${specs[@]}"; do
    local path="${spec#*=}"
    if [[ -f "$path" ]]; then
      prediction_args+=(--prediction "$spec")
      existing_specs+=("$spec")
    else
      echo "Skipping missing prediction for ${model}: $path"
    fi
  done
  if [[ "${#existing_specs[@]}" -lt 2 ]]; then
    echo "Need at least baseline plus one comparison for ${model}; skipping."
    return
  fi

  local baseline_name="${existing_specs[0]%%=*}"
  for split_by in $SPLITS; do
    python scripts_research/evaluate_status_devtest.py \
      "${prediction_args[@]}" \
      --baseline-name "$baseline_name" \
      --target2text "$DATA_DIR/target2text.json" \
      --split-by "$split_by" \
      --dev-fraction "$DEV_FRACTION" \
      --seed "$SEED" \
      --bootstrap "$BOOTSTRAP" \
      --output-json "$OUT_DIR/devtest_status_${model}_${split_by}.json" \
      --output-csv "$OUT_DIR/devtest_status_${model}_${split_by}.csv" \
      --output-md "$OUT_DIR/devtest_status_${model}_${split_by}.md"

    echo "Target-disjoint status outputs for model=$model split=$split_by:"
    echo "  $OUT_DIR/devtest_status_${model}_${split_by}.md"
    cat "$OUT_DIR/devtest_status_${model}_${split_by}.md"
  done
}

run_model SeekUI
run_model SeekUI_sft
