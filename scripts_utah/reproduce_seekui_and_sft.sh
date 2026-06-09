#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

SEEKUI_WORK="${SEEKUI_WORK:-${SCRATCH:-$REPO_ROOT/.scratch}/seekui}"
SUBSET_LIMIT="${SUBSET_LIMIT:-1362}"

if ! command -v python >/dev/null 2>&1; then
  module load miniconda3/25.9.1
  source "$(conda info --base)/etc/profile.d/conda.sh"
  conda activate seekui
fi

submit_inference() {
  local model_name="$1"
  local output_path="$SEEKUI_WORK/outputs/predictions_${model_name}_${SUBSET_LIMIT}.json"
  sbatch --parsable \
    --job-name="seekui-${model_name}-infer" \
    --export=ALL,MODEL_NAME="$model_name",SUBSET_LIMIT="$SUBSET_LIMIT",OUTPUT_PATH="$output_path" \
    scripts_utah/full_inference.slurm
}

submit_eval() {
  local dependency="$1"
  local model_name="$2"
  local prediction_path="$SEEKUI_WORK/outputs/predictions_${model_name}_${SUBSET_LIMIT}.json"
  local eval_copy="evaluation/test_predictions_${model_name}_${SUBSET_LIMIT}.json"
  local eval_log="$SEEKUI_WORK/outputs/eval_${model_name}_${SUBSET_LIMIT}.txt"
  sbatch --parsable \
    --dependency="afterok:$dependency" \
    --job-name="seekui-${model_name}-eval" \
    --export=ALL,PREDICTION_FILE="$prediction_path",EVAL_COPY="$eval_copy",EVAL_LOG="$eval_log" \
    scripts_utah/evaluate_predictions.slurm
}

python scripts_utah/check_reproduction_inputs.py

seekui_job="$(submit_inference SeekUI)"
sft_job="$(submit_inference SeekUI_sft)"
seekui_eval_job="$(submit_eval "$seekui_job" SeekUI)"
sft_eval_job="$(submit_eval "$sft_job" SeekUI_sft)"

cat <<EOF
Submitted reproduction jobs:
  SeekUI inference     : $seekui_job
  SeekUI-SFT inference : $sft_job
  SeekUI evaluation    : $seekui_eval_job
  SeekUI-SFT evaluation: $sft_eval_job

Outputs:
  $SEEKUI_WORK/outputs/predictions_SeekUI_${SUBSET_LIMIT}.json
  $SEEKUI_WORK/outputs/predictions_SeekUI_sft_${SUBSET_LIMIT}.json
  $SEEKUI_WORK/outputs/eval_SeekUI_${SUBSET_LIMIT}.txt
  $SEEKUI_WORK/outputs/eval_SeekUI_sft_${SUBSET_LIMIT}.txt
EOF
