#!/usr/bin/env bash
#SBATCH --job-name=seekui-vlm-pres
#SBATCH --account=engin1
#SBATCH --partition=spgpu
#SBATCH --gres=gpu:a40:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=48G
#SBATCH --time=08:00:00
#SBATCH --output=seekui-vlm-pres-%j.out

set -euo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:-$(pwd)}"
cd "$REPO_ROOT"

SEEKUI_WORK="${SEEKUI_WORK:-/scratch/engin_root/engin1/$USER/seekui}"
DATA_DIR="${SEEKUI_DATA_DIR:-$SEEKUI_WORK/data}"
OUTPUT_DIR="$SEEKUI_WORK/outputs"
export HF_HOME="${HF_HOME:-$SEEKUI_WORK/hf_cache}"
export PYTHONUNBUFFERED=1

if [[ -n "${CONDA_MODULE:-}" ]]; then
  module load "$CONDA_MODULE"
else
  module load python3.10-anaconda/2023.03
fi
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate "${CONDA_ENV:-seekui}"

MODEL_NAME="${MODEL_NAME:-SeekUI}"
MODEL_PATH="${MODEL_PATH:-$SEEKUI_WORK/models/$MODEL_NAME}"
MODEL_LABEL="${MODEL_LABEL:-${MODEL_NAME}_vlm_presence}"
INPUT_JSON="${INPUT_JSON:-$DATA_DIR/present_absent_synthetic_2724.json}"
VLM_LIMIT="${VLM_LIMIT:-0}"
VLM_PROMPT_VARIANT="${VLM_PROMPT_VARIANT:-direct}"

limit_suffix=""
limit_args=()
if [[ "$VLM_LIMIT" != "0" ]]; then
  limit_suffix="_n${VLM_LIMIT}"
  limit_args+=(--limit "$VLM_LIMIT")
fi

OUTPUT_PATH="${OUTPUT_PATH:-$OUTPUT_DIR/vlm_presence_predictions_${MODEL_LABEL}${limit_suffix}.json}"

python inference/vlm_presence_baseline.py \
  --model_path "$MODEL_PATH" \
  --cache_dir "$HF_HOME" \
  --input_json "$INPUT_JSON" \
  --target2text "$DATA_DIR/target2text.json" \
  --image_root "$DATA_DIR" \
  --output "$OUTPUT_PATH" \
  --prompt_variant "$VLM_PROMPT_VARIANT" \
  --max_new_tokens "${MAX_NEW_TOKENS:-32}" \
  --save_every "${SAVE_EVERY:-25}" \
  --resume \
  "${limit_args[@]}"

python scripts_research/evaluate_absent_status.py \
  --predictions "$OUTPUT_PATH" \
  --output "${OUTPUT_PATH%.json}_status_eval.json"

echo "VLM presence predictions: $OUTPUT_PATH"
echo "Status eval: ${OUTPUT_PATH%.json}_status_eval.json"
cat "${OUTPUT_PATH%.json}_status_eval.json"
