#!/usr/bin/env bash
set -euo pipefail

MODEL_NAME="${MODEL_NAME:-SeekUI}"
VLM_LIMIT="${VLM_LIMIT:-0}"
VARIANTS=(${VLM_PROMPT_VARIANTS:-direct conservative ocr_aware search_behavior})
SBATCH_ARGS=()

if [[ -n "${SBATCH_ACCOUNT:-}" ]]; then
  SBATCH_ARGS+=(--account="$SBATCH_ACCOUNT")
fi
if [[ -n "${SBATCH_PARTITION:-}" ]]; then
  SBATCH_ARGS+=(--partition="$SBATCH_PARTITION")
fi
if [[ -n "${SBATCH_GRES:-}" ]]; then
  SBATCH_ARGS+=(--gres="$SBATCH_GRES")
fi

for variant in "${VARIANTS[@]}"; do
  echo "Submitting VLM presence baseline: model=${MODEL_NAME}, variant=${variant}, limit=${VLM_LIMIT}"
  MODEL_NAME="$MODEL_NAME" \
  MODEL_LABEL="${MODEL_NAME}_vlm_presence_${variant}" \
  VLM_PROMPT_VARIANT="$variant" \
  VLM_LIMIT="$VLM_LIMIT" \
    sbatch "${SBATCH_ARGS[@]}" scripts_greatlakes/vlm_presence_baseline.slurm
done
