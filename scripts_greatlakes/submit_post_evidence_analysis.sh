#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

SEEKUI_WORK="${SEEKUI_WORK:-/scratch/engin_root/engin1/$USER/seekui}"
SKIP_REAL_ABSENT_STARTER="${SKIP_REAL_ABSENT_STARTER:-0}"
OUTPUT_DIR="$SEEKUI_WORK/outputs"
SBATCH_ARGS=()

if [[ -n "${SBATCH_ACCOUNT:-}" ]]; then
  SBATCH_ARGS+=(--account="$SBATCH_ACCOUNT")
fi
if [[ -n "${SBATCH_PARTITION:-}" ]]; then
  SBATCH_ARGS+=(--partition="$SBATCH_PARTITION")
fi

submit_job() {
  local job_name="$1"
  local script="$2"
  sbatch --parsable \
    "${SBATCH_ARGS[@]}" \
    --job-name="$job_name" \
    "$script"
}

can_run_evidence_filter() {
  [[ -f "$OUTPUT_DIR/vlm_evidence_predictions_SeekUI_vlm_evidence_evidence_aware.json" \
    && -f "$OUTPUT_DIR/absent_benchmark_sanity/absent_examples_sanity.csv" ]]
}

can_run_hardcmp() {
  [[ -f "$OUTPUT_DIR/vlm_hard_cases/SeekUI_vlm_presence_vs_SeekUI_combined_and/summary.json" \
    && -f "$OUTPUT_DIR/vlm_hard_cases/SeekUI_vlm_presence_ocr_aware_vs_SeekUI_combined_and/summary.json" \
    && -f "$OUTPUT_DIR/vlm_hard_cases/SeekUI_vlm_evidence_aware_vs_SeekUI_combined_and/summary.json" ]]
}

can_run_realabs_starter() {
  [[ -f "$SEEKUI_WORK/data/scanpath_train_explanation.json" \
    && -f "$SEEKUI_WORK/data/target2text.json" ]]
}

filtered_job=""
if can_run_evidence_filter; then
  filtered_job="$(submit_job "seekui-evid-filter" scripts_greatlakes/evaluate_evidence_filtered_status.slurm)"
else
  echo "Skipping evidence filtered eval; missing evidence prediction or absent sanity CSV."
fi

hardcmp_job=""
if can_run_hardcmp; then
  hardcmp_job="$(submit_job "seekui-vlm-hardcmp" scripts_greatlakes/export_vlm_hard_case_comparison.slurm)"
else
  echo "Skipping hard-case comparison; missing one or more VLM hard-case summary JSONs."
fi

realabs_job=""
if [[ "$SKIP_REAL_ABSENT_STARTER" != "1" ]]; then
  if can_run_realabs_starter; then
    realabs_job="$(submit_job "seekui-realabs-sheet" scripts_greatlakes/export_real_absent_validation_sheet.slurm)"
  else
    echo "Skipping real absent starter; missing scanpath_train_explanation.json or target2text.json."
  fi
fi

cat <<EOF
Great Lakes post-evidence CPU analysis submitted.
  evidence filtered eval : ${filtered_job:-skipped}
  hard-case comparison   : ${hardcmp_job:-skipped}
  real absent starter    : ${realabs_job:-skipped}

Key outputs:
  $SEEKUI_WORK/outputs/vlm_evidence_predictions_SeekUI_vlm_evidence_evidence_aware_filtered_status_eval.csv
  $SEEKUI_WORK/outputs/vlm_hard_cases/vlm_hard_case_comparison.md
  $SEEKUI_WORK/outputs/real_absent_validation/real_absent_validation_starter.md

Use:
  squeue -u "$USER" -o "%.18i %.18a %.14P %.28j %.8T %.10M %.12l %.20b %.30R"
EOF
