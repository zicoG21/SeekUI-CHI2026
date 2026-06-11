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
    sbatch "${SBATCH_ARGS[@]}" scripts_utah/real_absent_seekui_inference.slurm
)"
echo "$infer_output"
infer_job="$(awk '/Submitted batch job/ {job=$4} END {print job}' <<<"$infer_output")"

if [[ -n "${POST_ACCOUNT:-}" ]]; then
  POST_ARGS+=(--account="$POST_ACCOUNT")
fi
if [[ -n "${POST_PARTITION:-}" ]]; then
  POST_ARGS+=(--partition="$POST_PARTITION")
fi
POST_ARGS+=(--dependency="afterok:$infer_job")

echo "Submitting real-absent postprocess after job: $infer_job"
MODEL_NAME="${MODEL_NAME:-SeekUI}" \
  sbatch "${POST_ARGS[@]}" scripts_utah/real_absent_postprocess.slurm
