#!/usr/bin/env bash
#SBATCH --job-name=seekui-semantic
#SBATCH --account=owner-gpu-guest
#SBATCH --partition=notchpeak-gpu-guest
#SBATCH --gres=gpu:a40:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=48G
#SBATCH --time=08:00:00
#SBATCH --output=seekui-semantic-%j.out

set -euo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:-$(pwd)}"
cd "$REPO_ROOT"

SEEKUI_WORK="${SEEKUI_WORK:-${SCRATCH:-$REPO_ROOT/.scratch}/seekui}"
DATA_DIR="${SEEKUI_DATA_DIR:-$SEEKUI_WORK/data}"
export HF_HOME="${HF_HOME:-$SEEKUI_WORK/hf_cache}"
export PYTHONUNBUFFERED=1

module load miniconda3/25.9.1
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate seekui

MODEL_NAME="${MODEL_NAME:-SeekUI}"
MODEL_PATH="${MODEL_PATH:-$SEEKUI_WORK/models/$MODEL_NAME}"
SEMANTIC_LIMIT="${SEMANTIC_LIMIT:-1362}"
VARIANTS_PER_EXAMPLE="${VARIANTS_PER_EXAMPLE:-2}"
SEMANTIC_JSON="${SEMANTIC_JSON:-$DATA_DIR/semantic_queries_${SEMANTIC_LIMIT}_v${VARIANTS_PER_EXAMPLE}.json}"
OUTPUT_PATH="${OUTPUT_PATH:-$SEEKUI_WORK/outputs/semantic_query_predictions_${MODEL_NAME}_${SEMANTIC_LIMIT}_v${VARIANTS_PER_EXAMPLE}.json}"

python scripts_research/build_semantic_query_dataset.py \
  --scanpath "$DATA_DIR/scanpath_train_explanation.json" \
  --target2text "$DATA_DIR/target2text.json" \
  --output "$SEMANTIC_JSON" \
  --limit "$SEMANTIC_LIMIT" \
  --variants-per-example "$VARIANTS_PER_EXAMPLE" \
  --seed "${SEED:-42}"

python inference/prediction_absent.py \
  --model_path "$MODEL_PATH" \
  --cache_dir "$HF_HOME" \
  --scanpath_test "$SEMANTIC_JSON" \
  --target2text "$DATA_DIR/target2text.json" \
  --image_root "$DATA_DIR" \
  --output "$OUTPUT_PATH" \
  --max_new_tokens "${MAX_NEW_TOKENS:-256}" \
  --save_every "${SAVE_EVERY:-10}" \
  --resume

python scripts_research/summarize_semantic_predictions.py \
  --predictions "$OUTPUT_PATH" \
  --output "${OUTPUT_PATH%.json}_summary.json"

echo "Semantic-query predictions saved to $OUTPUT_PATH"
