#!/usr/bin/env bash
set -euo pipefail

SEEKUI_WORK="${SEEKUI_WORK:-${SCRATCH:-$(pwd)/.scratch}/seekui}"
NATIVE_V2_DIR="${NATIVE_V2_DIR:-$SEEKUI_WORK/outputs/native_vsgui10k/processed_v2}"
MODEL_NAME="${MODEL_NAME:-SeekUI}"

splits=(
  native_v2_main_text
  native_v2_main_text_color
  native_v2_clean_text_all
)

jobs=()
for split in "${splits[@]}"; do
  input_json="$NATIVE_V2_DIR/splits/${split}.json"
  if [[ ! -f "$input_json" ]]; then
    echo "Missing split JSON: $input_json" >&2
    exit 1
  fi
  echo "Submitting SeekUI native v2 inference: $split"
  jid=$(SPLIT_NAME="$split" \
    MODEL_NAME="$MODEL_NAME" \
    INPUT_JSON="$input_json" \
    OUTPUT_PATH="$SEEKUI_WORK/outputs/present_absent_predictions_${MODEL_NAME}_${split}.json" \
    sbatch --parsable scripts_utah/native_vsgui_seekui_inference.slurm)
  echo "  inference job: $jid"
  jobs+=("$jid")

  echo "Submitting postprocess dependency: $split"
  post_jid=$(SPLIT_NAME="$split" \
    MODEL_NAME="$MODEL_NAME" \
    INPUT_JSON="$input_json" \
    PREDICTIONS="$SEEKUI_WORK/outputs/present_absent_predictions_${MODEL_NAME}_${split}.json" \
    MODEL_LABEL="${MODEL_NAME}_${split}" \
    sbatch --parsable --dependency=afterok:"$jid" scripts_utah/native_vsgui_text_postprocess.slurm)
  echo "  postprocess job: $post_jid"
  jobs+=("$post_jid")
done

echo "Submitted native v2 text jobs: ${jobs[*]}"
