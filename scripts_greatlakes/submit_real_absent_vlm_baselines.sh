#!/usr/bin/env bash
set -euo pipefail

MODEL_NAME="${MODEL_NAME:-SeekUI}"
INPUT_JSON="${INPUT_JSON:-${SEEKUI_WORK:?Set SEEKUI_WORK}/outputs/real_absent_validation/real_absent_validation_eval.json}"
VLM_LIMIT="${VLM_LIMIT:-0}"
VARIANTS=(${VLM_PROMPT_VARIANTS:-direct conservative ocr_aware search_behavior})
SBATCH_ARGS=()
JOB_IDS=()

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

for variant in "${VARIANTS[@]}"; do
  if [[ "$variant" == "direct" ]]; then
    label="${MODEL_NAME}_vlm_presence_real_absent"
  else
    label="${MODEL_NAME}_vlm_presence_real_absent_${variant}"
  fi
  echo "Submitting real-absent VLM presence: model=${MODEL_NAME}, variant=${variant}, label=${label}, limit=${VLM_LIMIT}"
  output="$(
    MODEL_NAME="$MODEL_NAME" \
    MODEL_LABEL="$label" \
    INPUT_JSON="$INPUT_JSON" \
    VLM_PROMPT_VARIANT="$variant" \
    VLM_LIMIT="$VLM_LIMIT" \
      sbatch "${SBATCH_ARGS[@]}" scripts_greatlakes/vlm_presence_baseline.slurm
  )"
  echo "$output"
  JOB_IDS+=("$(awk '/Submitted batch job/ {job=$4} END {print job}' <<<"$output")")
done

if [[ "${RUN_EVIDENCE:-0}" != "0" ]]; then
  EVIDENCE_VARIANTS=(${VLM_EVIDENCE_PROMPT_VARIANTS:-evidence_aware})
  for variant in "${EVIDENCE_VARIANTS[@]}"; do
    label="${MODEL_NAME}_vlm_evidence_real_absent_${variant}"
    echo "Submitting real-absent evidence-prompt VLM: model=${MODEL_NAME}, variant=${variant}, label=${label}, limit=${VLM_LIMIT}"
    output="$(
      MODEL_NAME="$MODEL_NAME" \
      MODEL_LABEL="$label" \
      INPUT_JSON="$INPUT_JSON" \
      VLM_EVIDENCE_PROMPT_VARIANT="$variant" \
      VLM_LIMIT="$VLM_LIMIT" \
        sbatch "${SBATCH_ARGS[@]}" scripts_greatlakes/vlm_evidence_presence.slurm
    )"
    echo "$output"
    JOB_IDS+=("$(awk '/Submitted batch job/ {job=$4} END {print job}' <<<"$output")")
  done
fi

if [[ "${SUBMIT_SUMMARY:-1}" != "0" && "${#JOB_IDS[@]}" -gt 0 ]]; then
  dep="$(IFS=:; echo "${JOB_IDS[*]}")"
  SUMMARY_ARGS=(--dependency="afterok:$dep")
  summary_account="${SUMMARY_ACCOUNT:-${SBATCH_ACCOUNT:-}}"
  summary_partition="${SUMMARY_PARTITION:-standard}"
  if [[ -n "$summary_account" ]]; then
    SUMMARY_ARGS+=(--account="$summary_account")
  fi
  if [[ -n "$summary_partition" ]]; then
    SUMMARY_ARGS+=(--partition="$summary_partition")
  fi
  echo "Submitting real-absent summary after jobs: $dep"
  sbatch "${SUMMARY_ARGS[@]}" scripts_greatlakes/summarize_real_absent_results.slurm
fi
