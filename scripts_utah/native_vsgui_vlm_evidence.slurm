#!/usr/bin/env bash
#SBATCH --job-name=seekui-native-evid
#SBATCH --account=owner-gpu-guest
#SBATCH --partition=notchpeak-gpu-guest
#SBATCH --gres=gpu:a40:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=48G
#SBATCH --time=08:00:00
#SBATCH --output=seekui-native-evid-%j.out

set -euo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:-$(pwd)}"
cd "$REPO_ROOT"

SEEKUI_WORK="${SEEKUI_WORK:-${SCRATCH:-$REPO_ROOT/.scratch}/seekui}"
BASE_DATA_DIR="${SEEKUI_BASE_DATA_DIR:-$SEEKUI_WORK/data}"
OSF_DATA_DIR="${OSF_DATA_DIR:-$SEEKUI_WORK/data/osf_vsgui10k/extracted/data}"
OUTPUT_DIR="$SEEKUI_WORK/outputs"
NATIVE_DIR="$OUTPUT_DIR/native_vsgui10k"
export HF_HOME="${HF_HOME:-$SEEKUI_WORK/hf_cache}"
export PYTHONUNBUFFERED=1

module load miniconda3/25.9.1
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate seekui

MODEL_NAME="${MODEL_NAME:-SeekUI}"
MODEL_PATH="${MODEL_PATH:-$SEEKUI_WORK/models/$MODEL_NAME}"
SPLIT_NAME="${SPLIT_NAME:-native_text_color_balanced}"
EVIDENCE_SOURCE_VARIANT="${EVIDENCE_SOURCE_VARIANT:-${SPLIT_NAME}_color_aware_filtered_tuned_absent_f1}"
VLM_EVIDENCE_PROMPT_VARIANT="${VLM_EVIDENCE_PROMPT_VARIANT:-evidence_aware}"
MODEL_LABEL="${MODEL_LABEL:-${MODEL_NAME}_vlm_evidence_${SPLIT_NAME}_${VLM_EVIDENCE_PROMPT_VARIANT}}"
INPUT_JSON="${INPUT_JSON:-$OUTPUT_DIR/present_absent_predictions_${MODEL_NAME}_${EVIDENCE_SOURCE_VARIANT}.json}"
VLM_LIMIT="${VLM_LIMIT:-0}"

limit_suffix=""
limit_args=()
if [[ "$VLM_LIMIT" != "0" ]]; then
  limit_suffix="_n${VLM_LIMIT}"
  limit_args+=(--limit "$VLM_LIMIT")
fi

OUTPUT_PATH="${OUTPUT_PATH:-$OUTPUT_DIR/vlm_evidence_predictions_${MODEL_LABEL}${limit_suffix}.json}"

python inference/vlm_evidence_presence_baseline.py \
  --model_path "$MODEL_PATH" \
  --cache_dir "$HF_HOME" \
  --input_json "$INPUT_JSON" \
  --target2text "$BASE_DATA_DIR/target2text.json" \
  --image_root "$OSF_DATA_DIR" \
  --output "$OUTPUT_PATH" \
  --prompt_variant "$VLM_EVIDENCE_PROMPT_VARIANT" \
  --max_new_tokens "${MAX_NEW_TOKENS:-64}" \
  --save_every "${SAVE_EVERY:-25}" \
  --resume \
  "${limit_args[@]}"

python scripts_research/evaluate_absent_status.py \
  --predictions "$OUTPUT_PATH" \
  --output "${OUTPUT_PATH%.json}_status_eval.json"

python scripts_research/summarize_native_vsgui_results.py \
  --work-dir "$SEEKUI_WORK" \
  --output-json "$NATIVE_DIR/native_vsgui_results.json" \
  --output-csv "$NATIVE_DIR/native_vsgui_results.csv" \
  --output-md "$NATIVE_DIR/native_vsgui_results.md"

echo "Native evidence-aware VLM predictions: $OUTPUT_PATH"
cat "${OUTPUT_PATH%.json}_status_eval.json"
