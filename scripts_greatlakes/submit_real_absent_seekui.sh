#!/usr/bin/env bash
set -euo pipefail

SBATCH_ARGS=()
POST_ARGS=()

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
if [[ -n "${SBATCH_TIME:-}" ]]; then
  SBATCH_ARGS+=(--time="$SBATCH_TIME")
fi

infer_output="$(
  MODEL_NAME="${MODEL_NAME:-SeekUI}" \
    sbatch "${SBATCH_ARGS[@]}" scripts_greatlakes/real_absent_seekui_inference.slurm
)"
echo "$infer_output"
infer_job="$(awk '/Submitted batch job/ {job=$4} END {print job}' <<<"$infer_output")"

post_account="${POST_ACCOUNT:-${SBATCH_ACCOUNT:-}}"
post_partition="${POST_PARTITION:-standard}"
if [[ -n "$post_account" ]]; then
  POST_ARGS+=(--account="$post_account")
fi
if [[ -n "$post_partition" ]]; then
  POST_ARGS+=(--partition="$post_partition")
fi
POST_ARGS+=(--dependency="afterok:$infer_job")

echo "Submitting real-absent postprocess after job: $infer_job"
MODEL_NAME="${MODEL_NAME:-SeekUI}" \
  sbatch "${POST_ARGS[@]}" scripts_greatlakes/real_absent_postprocess.slurm
