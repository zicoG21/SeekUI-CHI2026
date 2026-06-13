#!/usr/bin/env bash
#SBATCH --job-name=seekui-crop-vis
#SBATCH --account=engin1
#SBATCH --partition=spgpu
#SBATCH --gres=gpu:a40:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=48G
#SBATCH --time=08:00:00
#SBATCH --output=seekui-crop-vis-%j.out

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
CROP_LIMIT="${CROP_LIMIT:-120}"
CROP_TOP_K_OCR="${CROP_TOP_K_OCR:-2}"
CROP_TOP_K_VISUAL="${CROP_TOP_K_VISUAL:-3}"
MODEL_LABEL="${MODEL_LABEL:-${MODEL_NAME}_real_absent500_crop_ocr_visual_vlm}"

limit_suffix=""
limit_args=()
if [[ "$CROP_LIMIT" != "0" ]]; then
  limit_suffix="_n${CROP_LIMIT}"
  limit_args+=(--limit "$CROP_LIMIT")
fi

OUT_DIR="$OUTPUT_DIR/candidate_crop_verifier/${MODEL_LABEL}${limit_suffix}"
CROP_JSON="$OUT_DIR/candidate_crops.json"
CROP_PREDICTIONS="$OUT_DIR/candidate_crop_vlm_predictions.json"
EXAMPLE_PREDICTIONS="$OUT_DIR/example_predictions.json"
SUMMARY_JSON="$OUT_DIR/status_eval.json"

python scripts_research/export_candidate_crop_dataset.py \
  --input-json "$INPUT_JSON" \
  --ocr-candidates "$OUTPUT_DIR/ocr_candidates_tesseract.json" \
  --target2text "$DATA_DIR/target2text.json" \
  --image-root "$DATA_DIR" \
  --out-dir "$OUT_DIR" \
  --output-json "$CROP_JSON" \
  --top-k-ocr "$CROP_TOP_K_OCR" \
  --include-visual-proposals \
  --top-k-visual "$CROP_TOP_K_VISUAL" \
  --min-ocr-conf "${MIN_OCR_CONF:-35}" \
  --crop-pad "${CROP_PAD:-8}" \
  --visual-max-side "${VISUAL_MAX_SIDE:-320}" \
  --visual-edge-threshold "${VISUAL_EDGE_THRESHOLD:-45}" \
  --visual-min-area "${VISUAL_MIN_AREA:-8}" \
  --visual-min-size "${VISUAL_MIN_SIZE:-3}" \
  --visual-max-proposals "${VISUAL_MAX_PROPOSALS:-80}" \
  "${limit_args[@]}"

python inference/vlm_candidate_crop_verifier.py \
  --model_path "$MODEL_PATH" \
  --cache_dir "$HF_HOME" \
  --crop_json "$CROP_JSON" \
  --output "$CROP_PREDICTIONS" \
  --max_new_tokens "${MAX_NEW_TOKENS:-48}" \
  --save_every "${SAVE_EVERY:-50}" \
  --resume

python scripts_research/evaluate_candidate_crop_verifier.py \
  --examples-json "$INPUT_JSON" \
  --crop-predictions "$CROP_PREDICTIONS" \
  --output-predictions "$EXAMPLE_PREDICTIONS" \
  --output-summary "$SUMMARY_JSON" \
  "${limit_args[@]}"

echo "Crop OCR+visual VLM output dir: $OUT_DIR"
cat "$SUMMARY_JSON"
