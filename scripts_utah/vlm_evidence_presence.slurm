#!/usr/bin/env bash
#SBATCH --job-name=seekui-vlm-evid
#SBATCH --account=owner-gpu-guest
#SBATCH --partition=notchpeak-gpu-guest
#SBATCH --gres=gpu:a40:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=48G
#SBATCH --time=08:00:00
#SBATCH --output=seekui-vlm-evid-%j.out

set -euo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:-$(pwd)}"
cd "$REPO_ROOT"

SEEKUI_WORK="${SEEKUI_WORK:-${SCRATCH:-$REPO_ROOT/.scratch}/seekui}"
DATA_DIR="${SEEKUI_DATA_DIR:-$SEEKUI_WORK/data}"
OUTPUT_DIR="$SEEKUI_WORK/outputs"
export HF_HOME="${HF_HOME:-$SEEKUI_WORK/hf_cache}"
export PYTHONUNBUFFERED=1

module load miniconda3/25.9.1
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate seekui

MODEL_NAME="${MODEL_NAME:-SeekUI}"
MODEL_PATH="${MODEL_PATH:-$SEEKUI_WORK/models/$MODEL_NAME}"
VLM_EVIDENCE_PROMPT_VARIANT="${VLM_EVIDENCE_PROMPT_VARIANT:-evidence_aware}"
MODEL_LABEL="${MODEL_LABEL:-${MODEL_NAME}_vlm_evidence_${VLM_EVIDENCE_PROMPT_VARIANT}}"
INPUT_JSON="${INPUT_JSON:-$OUTPUT_DIR/present_absent_predictions_${MODEL_NAME}_combined_and_present_only_best_f1.json}"
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
  --target2text "$DATA_DIR/target2text.json" \
  --image_root "$DATA_DIR" \
  --output "$OUTPUT_PATH" \
  --prompt_variant "$VLM_EVIDENCE_PROMPT_VARIANT" \
  --max_new_tokens "${MAX_NEW_TOKENS:-64}" \
  --save_every "${SAVE_EVERY:-25}" \
  --resume \
  "${limit_args[@]}"

python scripts_research/evaluate_absent_status.py \
  --predictions "$OUTPUT_PATH" \
  --output "${OUTPUT_PATH%.json}_status_eval.json"

if [[ "$VLM_LIMIT" == "0" && -f "$OUTPUT_DIR/absent_benchmark_sanity/absent_examples_sanity.csv" ]]; then
  python scripts_research/evaluate_absent_status_filtered.py \
    --filter-csv "$OUTPUT_DIR/absent_benchmark_sanity/absent_examples_sanity.csv" \
    --exclude-flag annotation_conflict_flag \
    --exclude-flag ocr_leak_flag \
    --prediction "${MODEL_LABEL}=${OUTPUT_PATH}" \
    --output-json "${OUTPUT_PATH%.json}_filtered_status_eval.json" \
    --output-csv "${OUTPUT_PATH%.json}_filtered_status_eval.csv" \
    --excluded-output "${OUTPUT_PATH%.json}_filtered_excluded.csv"
fi

echo "Evidence-aware VLM predictions: $OUTPUT_PATH"
echo "Status eval: ${OUTPUT_PATH%.json}_status_eval.json"
cat "${OUTPUT_PATH%.json}_status_eval.json"
if [[ -f "${OUTPUT_PATH%.json}_filtered_status_eval.csv" ]]; then
  echo "Filtered eval: ${OUTPUT_PATH%.json}_filtered_status_eval.csv"
  cat "${OUTPUT_PATH%.json}_filtered_status_eval.csv"
fi
