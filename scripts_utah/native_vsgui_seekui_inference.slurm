#!/usr/bin/env bash
#SBATCH --job-name=seekui-native
#SBATCH --account=owner-gpu-guest
#SBATCH --partition=notchpeak-gpu-guest
#SBATCH --gres=gpu:a40:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=40G
#SBATCH --time=06:00:00
#SBATCH --output=seekui-native-%j.out

set -euo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:-$(pwd)}"
cd "$REPO_ROOT"

SEEKUI_WORK="${SEEKUI_WORK:-${SCRATCH:-$REPO_ROOT/.scratch}/seekui}"
BASE_DATA_DIR="${SEEKUI_BASE_DATA_DIR:-$SEEKUI_WORK/data}"
OSF_DATA_DIR="${OSF_DATA_DIR:-$SEEKUI_WORK/data/osf_vsgui10k/extracted/data}"
OUTPUT_DIR="$SEEKUI_WORK/outputs"
export HF_HOME="${HF_HOME:-$SEEKUI_WORK/hf_cache}"
export PYTHONUNBUFFERED=1

module load miniconda3/25.9.1
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate seekui

MODEL_NAME="${MODEL_NAME:-SeekUI}"
MODEL_PATH="${MODEL_PATH:-$SEEKUI_WORK/models/$MODEL_NAME}"
SPLIT_NAME="${SPLIT_NAME:-native_text_balanced}"
INPUT_JSON="${INPUT_JSON:-$OUTPUT_DIR/native_vsgui10k/eval_splits/${SPLIT_NAME}.json}"
OUTPUT_PATH="${OUTPUT_PATH:-$OUTPUT_DIR/present_absent_predictions_${MODEL_NAME}_${SPLIT_NAME}.json}"

python inference/prediction_absent.py \
  --model_path "$MODEL_PATH" \
  --cache_dir "$HF_HOME" \
  --scanpath_test "$INPUT_JSON" \
  --target2text "$BASE_DATA_DIR/target2text.json" \
  --image_root "$OSF_DATA_DIR" \
  --output "$OUTPUT_PATH" \
  --max_new_tokens "${MAX_NEW_TOKENS:-256}" \
  --save_every "${SAVE_EVERY:-10}" \
  --resume

python scripts_research/evaluate_absent_status.py \
  --predictions "$OUTPUT_PATH" \
  --output "${OUTPUT_PATH%.json}_status_eval.json"

echo "Native VSGUI SeekUI predictions: $OUTPUT_PATH"
cat "${OUTPUT_PATH%.json}_status_eval.json"
