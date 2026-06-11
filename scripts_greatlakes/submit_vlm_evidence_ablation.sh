#!/usr/bin/env bash
set -euo pipefail

MODEL_NAME="${MODEL_NAME:-SeekUI}"
VLM_LIMIT="${VLM_LIMIT:-0}"
VARIANTS=(${VLM_EVIDENCE_PROMPT_VARIANTS:-evidence_aware evidence_conservative evidence_rescue_present})
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
if [[ -n "${SBATCH_CPUS_PER_TASK:-}" ]]; then
  SBATCH_ARGS+=(--cpus-per-task="$SBATCH_CPUS_PER_TASK")
fi
if [[ -n "${SBATCH_MEM:-}" ]]; then
  SBATCH_ARGS+=(--mem="$SBATCH_MEM")
fi

for variant in "${VARIANTS[@]}"; do
  echo "Submitting evidence-aware VLM: model=${MODEL_NAME}, variant=${variant}, limit=${VLM_LIMIT}"
  MODEL_NAME="$MODEL_NAME" \
  MODEL_LABEL="${MODEL_NAME}_vlm_evidence_${variant}" \
  VLM_EVIDENCE_PROMPT_VARIANT="$variant" \
  VLM_LIMIT="$VLM_LIMIT" \
    sbatch "${SBATCH_ARGS[@]}" scripts_greatlakes/vlm_evidence_presence.slurm
done
