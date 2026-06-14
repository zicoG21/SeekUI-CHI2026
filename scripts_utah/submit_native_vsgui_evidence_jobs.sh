#!/usr/bin/env bash
set -euo pipefail

MODEL_NAME="${MODEL_NAME:-SeekUI}"
SPLIT_NAME="${SPLIT_NAME:-native_text_color_balanced}"
EVIDENCE_SOURCE_VARIANT="${EVIDENCE_SOURCE_VARIANT:-${SPLIT_NAME}_color_aware_filtered_tuned_absent_f1}"
VARIANTS=(${VLM_EVIDENCE_PROMPT_VARIANTS:-evidence_aware evidence_rescue_present})
SUBMIT_POSTPROCESS="${SUBMIT_POSTPROCESS:-1}"
POSTPROCESS_SCRIPT="${POSTPROCESS_SCRIPT:-scripts_utah/postprocess_native_vsgui_extension.slurm}"

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
if [[ -n "${SBATCH_TIME:-}" ]]; then
  SBATCH_ARGS+=(--time="$SBATCH_TIME")
fi

job_ids=()
for variant in "${VARIANTS[@]}"; do
  echo "Submitting native evidence-aware VLM: split=${SPLIT_NAME}, source=${EVIDENCE_SOURCE_VARIANT}, variant=${variant}"
  job_id="$(
    MODEL_NAME="$MODEL_NAME" \
    SPLIT_NAME="$SPLIT_NAME" \
    EVIDENCE_SOURCE_VARIANT="$EVIDENCE_SOURCE_VARIANT" \
    VLM_EVIDENCE_PROMPT_VARIANT="$variant" \
      sbatch --parsable "${SBATCH_ARGS[@]}" scripts_utah/native_vsgui_vlm_evidence.slurm
  )"
  job_ids+=("$job_id")
  echo "  job: $job_id"
done

post_job=""
if [[ "$SUBMIT_POSTPROCESS" == "1" ]]; then
  dependency="$(IFS=:; echo "${job_ids[*]}")"
  post_job="$(
    MODEL_NAME="$MODEL_NAME" \
    SPLIT_NAME="$SPLIT_NAME" \
    PRIMARY_VARIANT="$EVIDENCE_SOURCE_VARIANT" \
      sbatch --parsable \
        --dependency="afterok:$dependency" \
        "$POSTPROCESS_SCRIPT"
  )"
  echo "Submitting native postprocess after jobs ${dependency}: $post_job"
fi

cat <<EOF
Native VSGUI evidence jobs submitted.
  model       : $MODEL_NAME
  split       : $SPLIT_NAME
  source      : $EVIDENCE_SOURCE_VARIANT
  variants    : ${VARIANTS[*]}
  gpu jobs    : ${job_ids[*]}
  postprocess : ${post_job:-skipped}

Use:
  squeue -u "\$USER" -o "%.18i %.12a %.18P %.28j %.8T %.10M %.12l %.20b %.30R"

Expected outputs:
  \$SEEKUI_WORK/outputs/vlm_evidence_predictions_${MODEL_NAME}_vlm_evidence_${SPLIT_NAME}_evidence_aware.json
  \$SEEKUI_WORK/outputs/vlm_evidence_predictions_${MODEL_NAME}_vlm_evidence_${SPLIT_NAME}_evidence_rescue_present.json
  \$SEEKUI_WORK/outputs/native_vsgui10k/native_extension_summary.md
EOF
