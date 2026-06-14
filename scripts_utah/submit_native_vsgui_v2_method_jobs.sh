#!/usr/bin/env bash
set -euo pipefail

SEEKUI_WORK="${SEEKUI_WORK:-${SCRATCH:-$(pwd)/.scratch}/seekui}"
OUTPUT_DIR="$SEEKUI_WORK/outputs"
NATIVE_V2_DIR="${NATIVE_V2_DIR:-$OUTPUT_DIR/native_vsgui10k/processed_v2}"
MODEL_NAME="${MODEL_NAME:-SeekUI}"

SPLITS=(${NATIVE_V2_SPLITS:-native_v2_main_text native_v2_main_text_color native_v2_clean_text_all})
RUN_VLM_PRESENCE="${RUN_VLM_PRESENCE:-1}"
RUN_COLOR_AWARE="${RUN_COLOR_AWARE:-1}"
RUN_CONTEXT_CROP="${RUN_CONTEXT_CROP:-1}"
RUN_EVIDENCE_VLM="${RUN_EVIDENCE_VLM:-1}"
RUN_ENSEMBLE="${RUN_ENSEMBLE:-1}"
RUN_SUMMARY="${RUN_SUMMARY:-1}"

SBATCH_GPU_ARGS=()
if [[ -n "${SBATCH_ACCOUNT:-}" ]]; then
  SBATCH_GPU_ARGS+=(--account="$SBATCH_ACCOUNT")
fi
if [[ -n "${SBATCH_PARTITION:-}" ]]; then
  SBATCH_GPU_ARGS+=(--partition="$SBATCH_PARTITION")
fi
if [[ -n "${SBATCH_GRES:-}" ]]; then
  SBATCH_GPU_ARGS+=(--gres="$SBATCH_GRES")
fi
if [[ -n "${SBATCH_CPUS_PER_TASK:-}" ]]; then
  SBATCH_GPU_ARGS+=(--cpus-per-task="$SBATCH_CPUS_PER_TASK")
fi
if [[ -n "${SBATCH_MEM:-}" ]]; then
  SBATCH_GPU_ARGS+=(--mem="$SBATCH_MEM")
fi
if [[ -n "${SBATCH_TIME:-}" ]]; then
  SBATCH_GPU_ARGS+=(--time="$SBATCH_TIME")
fi

submit_cpu_after() {
  local dependency="$1"
  shift
  if [[ -n "$dependency" ]]; then
    sbatch --parsable --dependency="afterok:$dependency" "$@"
  else
    sbatch --parsable "$@"
  fi
}

jobs=()
for split in "${SPLITS[@]}"; do
  input_json="$NATIVE_V2_DIR/splits/${split}.json"
  if [[ ! -f "$input_json" ]]; then
    echo "Missing split JSON: $input_json" >&2
    echo "Run first: sbatch scripts_utah/audit_processed_native_vsgui10k_visibility.slurm" >&2
    exit 1
  fi

  n_rows="$(python - <<PY
import json
print(len(json.load(open("$input_json"))))
PY
)"
  n_absent="$(python - <<PY
import json
rows=json.load(open("$input_json"))
print(sum(1 for r in rows if r.get("status") == "absent" or r.get("target_present") is False))
PY
)"
  if [[ "$n_rows" == "0" || "$n_absent" == "0" ]]; then
    echo "Skipping $split: rows=$n_rows absent=$n_absent"
    continue
  fi

  label="${MODEL_NAME}_${split}"
  pred="$OUTPUT_DIR/present_absent_predictions_${label}.json"
  echo "Submitting v2 SeekUI inference: split=$split rows=$n_rows absent=$n_absent"
  infer_jid="$(
    SPLIT_NAME="$split" \
    MODEL_NAME="$MODEL_NAME" \
    INPUT_JSON="$input_json" \
    OUTPUT_PATH="$pred" \
      sbatch --parsable "${SBATCH_GPU_ARGS[@]}" scripts_utah/native_vsgui_seekui_inference.slurm
  )"
  echo "  inference: $infer_jid"
  jobs+=("$infer_jid")

  post_jid="$(
    SPLIT_NAME="$split" \
    MODEL_NAME="$MODEL_NAME" \
    INPUT_JSON="$input_json" \
    PREDICTIONS="$pred" \
    MODEL_LABEL="$label" \
      submit_cpu_after "$infer_jid" scripts_utah/native_vsgui_text_postprocess.slurm
  )"
  echo "  postprocess: $post_jid"
  jobs+=("$post_jid")

  if [[ "$RUN_VLM_PRESENCE" == "1" ]]; then
    vlm_jid="$(
      SPLIT_NAME="$split" \
      MODEL_NAME="$MODEL_NAME" \
      INPUT_JSON="$input_json" \
      VLM_PROMPT_VARIANT=ocr_aware \
      MODEL_LABEL="${MODEL_NAME}_vlm_presence_${split}_ocr_aware" \
        sbatch --parsable "${SBATCH_GPU_ARGS[@]}" scripts_utah/native_vsgui_vlm_presence.slurm
    )"
    echo "  vlm presence: $vlm_jid"
    jobs+=("$vlm_jid")
  fi

  color_jid=""
  color_variant="${split}_color_aware_native_tuned_absent_f1"
  if [[ "$RUN_COLOR_AWARE" == "1" && "$split" != "native_v2_main_text" ]]; then
    color_jid="$(
      SPLIT_NAME="$split" \
      MODEL_NAME="$MODEL_NAME" \
      MODEL_LABEL="$label" \
      THRESHOLD_METRIC=absent_f1 \
      VARIANT_SUFFIX="color_aware_native_tuned_absent_f1" \
        submit_cpu_after "$post_jid" scripts_utah/apply_native_color_aware_verifier.slurm
    )"
    echo "  color-aware: $color_jid"
    jobs+=("$color_jid")
  fi

  crop_jid=""
  if [[ "$RUN_CONTEXT_CROP" == "1" && "$split" != "native_v2_main_text" ]]; then
    crop_jid="$(
      SPLIT_NAME="$split" \
      MODEL_NAME="$MODEL_NAME" \
      INPUT_JSON="$input_json" \
      POST_LABEL="$label" \
      CROP_INCLUDE_CONTEXT=1 \
      MODEL_LABEL="${MODEL_NAME}_${split}_context_crop_ocr_vlm" \
        sbatch --parsable --dependency="afterok:$post_jid" "${SBATCH_GPU_ARGS[@]}" scripts_utah/native_vsgui_candidate_crop_verifier.slurm
    )"
    echo "  context crop VLM: $crop_jid"
    jobs+=("$crop_jid")
  fi

  evidence_source="${split}_combined_and_present_only_best_f1"
  evidence_dep="$post_jid"
  if [[ -n "$color_jid" ]]; then
    evidence_source="$color_variant"
    evidence_dep="$color_jid"
  fi
  evidence_jid=""
  if [[ "$RUN_EVIDENCE_VLM" == "1" ]]; then
    evidence_jid="$(
      SPLIT_NAME="$split" \
      MODEL_NAME="$MODEL_NAME" \
      EVIDENCE_SOURCE_VARIANT="$evidence_source" \
      VLM_EVIDENCE_PROMPT_VARIANT=evidence_aware \
      MODEL_LABEL="${MODEL_NAME}_vlm_evidence_${split}_evidence_aware" \
        sbatch --parsable --dependency="afterok:$evidence_dep" "${SBATCH_GPU_ARGS[@]}" scripts_utah/native_vsgui_vlm_evidence.slurm
    )"
    echo "  evidence-aware VLM: $evidence_jid (source=$evidence_source)"
    jobs+=("$evidence_jid")
  fi

  if [[ "$RUN_ENSEMBLE" == "1" && -n "$color_jid" && -n "$crop_jid" && -n "$evidence_jid" ]]; then
    ens_dep="${color_jid}:${crop_jid}:${evidence_jid}"
    ens_jid="$(
      SPLIT_NAME="$split" \
      MODEL_NAME="$MODEL_NAME" \
      PRIMARY_VARIANT="$color_variant" \
      SECONDARY_VARIANT="${split}_context_crop_ocr_vlm" \
      TERTIARY_VARIANT="vlm_evidence_${split}_evidence_aware" \
      SELECT_METRIC=absent_f1 \
      AUDIT_JSON="" \
      VARIANT_SUFFIX="status_ensemble_absent_f1" \
        submit_cpu_after "$ens_dep" scripts_utah/apply_native_status_ensemble.slurm
    )"
    echo "  ensemble: $ens_jid"
    jobs+=("$ens_jid")
  fi
done

summary_job=""
if [[ "$RUN_SUMMARY" == "1" && "${#jobs[@]}" -gt 0 ]]; then
  dependency="$(IFS=:; echo "${jobs[*]}")"
  summary_job="$(
    sbatch --parsable --dependency="afterany:$dependency" scripts_utah/summarize_native_vsgui_results.slurm
  )"
fi

cat <<EOF
Submitted native VSGUI v2 method jobs:
  ${jobs[*]:-none}
  summary: ${summary_job:-skipped}

Queue:
  squeue -u "\$USER" -o "%.18i %.12a %.18P %.28j %.8T %.10M %.12l %.20b %.30R"

Main prerequisites:
  sbatch scripts_utah/audit_processed_native_vsgui10k_visibility.slurm

After jobs finish:
  python scripts_research/summarize_native_vsgui_results.py \\
    --work-dir "\$SEEKUI_WORK" \\
    --output-json "\$SEEKUI_WORK/outputs/native_vsgui10k/native_vsgui_results.json" \\
    --output-csv "\$SEEKUI_WORK/outputs/native_vsgui10k/native_vsgui_results.csv" \\
    --output-md "\$SEEKUI_WORK/outputs/native_vsgui10k/native_vsgui_results.md"
EOF
