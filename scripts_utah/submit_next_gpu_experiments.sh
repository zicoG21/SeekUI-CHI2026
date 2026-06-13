#!/usr/bin/env bash
set -euo pipefail

sbatch_args=()
if [[ -n "${SBATCH_ACCOUNT:-}" ]]; then
  sbatch_args+=(--account="$SBATCH_ACCOUNT")
fi
if [[ -n "${SBATCH_PARTITION:-}" ]]; then
  sbatch_args+=(--partition="$SBATCH_PARTITION")
fi
if [[ -n "${SBATCH_GRES:-}" ]]; then
  sbatch_args+=(--gres="$SBATCH_GRES")
fi
if [[ -n "${SBATCH_CPUS_PER_TASK:-}" ]]; then
  sbatch_args+=(--cpus-per-task="$SBATCH_CPUS_PER_TASK")
fi
if [[ -n "${SBATCH_MEM:-}" ]]; then
  sbatch_args+=(--mem="$SBATCH_MEM")
fi

echo "Submitting multi-sample scanpath uncertainty pilot..."
sbatch "${sbatch_args[@]}" scripts_utah/multisample_uncertainty.slurm

echo "Submitting OCR crop-level VLM verifier pilot..."
sbatch "${sbatch_args[@]}" scripts_utah/vlm_candidate_crop_verifier.slurm

echo "Submitting OCR+visual crop-level VLM verifier pilot..."
sbatch "${sbatch_args[@]}" scripts_utah/vlm_candidate_crop_visual_verifier.slurm

echo "Submitted next GPU experiment pilots."
