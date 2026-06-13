#!/usr/bin/env bash
#SBATCH --job-name=seekui-ms-unc
#SBATCH --account=engin1
#SBATCH --partition=spgpu
#SBATCH --gres=gpu:a40:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=48G
#SBATCH --time=08:00:00
#SBATCH --output=seekui-ms-unc-%j.out

set -euo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:-$(pwd)}"
cd "$REPO_ROOT"

SEEKUI_WORK="${SEEKUI_WORK:-/scratch/engin_root/engin1/$USER/seekui}"
DATA_DIR="${SEEKUI_DATA_DIR:-$SEEKUI_WORK/data}"
OUTPUT_DIR="$SEEKUI_WORK/outputs"
export HF_HOME="${HF_HOME:-$SEEKUI_WORK/hf_cache}"
export PYTHONUNBUFFERED=1

module load "${CONDA_MODULE:-python3.10-anaconda/2023.03}"
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate "${CONDA_ENV:-seekui}"

MODEL_NAME="${MODEL_NAME:-SeekUI}"
MODEL_PATH="${MODEL_PATH:-$SEEKUI_WORK/models/$MODEL_NAME}"
INPUT_JSON="${INPUT_JSON:-$OUTPUT_DIR/real_absent_validation_500/real_absent_validation_eval.json}"
MULTISAMPLE_K="${MULTISAMPLE_K:-5}"
MULTISAMPLE_LIMIT="${MULTISAMPLE_LIMIT:-200}"
MODEL_LABEL="${MODEL_LABEL:-${MODEL_NAME}_real_absent500_multisample_k${MULTISAMPLE_K}}"

limit_suffix=""
limit_args=()
if [[ "$MULTISAMPLE_LIMIT" != "0" ]]; then
  limit_suffix="_n${MULTISAMPLE_LIMIT}"
  limit_args+=(--limit "$MULTISAMPLE_LIMIT")
fi

OUT_DIR="$OUTPUT_DIR/multisample_uncertainty"
OUTPUT_PATH="$OUT_DIR/${MODEL_LABEL}${limit_suffix}.json"

python inference/prediction_absent_multisample.py \
  --model_path "$MODEL_PATH" \
  --cache_dir "$HF_HOME" \
  --scanpath_test "$INPUT_JSON" \
  --target2text "$DATA_DIR/target2text.json" \
  --image_root "$DATA_DIR" \
  --output "$OUTPUT_PATH" \
  --samples_per_example "$MULTISAMPLE_K" \
  --temperature "${MULTISAMPLE_TEMPERATURE:-0.7}" \
  --top_p "${MULTISAMPLE_TOP_P:-0.9}" \
  --top_k "${MULTISAMPLE_TOP_K:-50}" \
  --max_new_tokens "${MAX_NEW_TOKENS:-256}" \
  --save_every "${SAVE_EVERY:-5}" \
  --resume \
  "${limit_args[@]}"

python scripts_research/evaluate_absent_status.py \
  --predictions "$OUTPUT_PATH" \
  --output "${OUTPUT_PATH%.json}_status_eval.json"

python scripts_research/summarize_multisample_uncertainty.py \
  --predictions "$OUTPUT_PATH" \
  --output-json "${OUTPUT_PATH%.json}_summary.json" \
  --output-csv "${OUTPUT_PATH%.json}_summary_rows.csv" \
  --output-md "${OUTPUT_PATH%.json}_summary.md"

echo "Multi-sample predictions: $OUTPUT_PATH"
cat "${OUTPUT_PATH%.json}_status_eval.json"
cat "${OUTPUT_PATH%.json}_summary.md"
