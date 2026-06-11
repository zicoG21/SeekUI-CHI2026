#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

SEEKUI_WORK="${SEEKUI_WORK:-${SCRATCH:-$REPO_ROOT/.scratch}/seekui}"
SUBSET_LIMIT="${SUBSET_LIMIT:-1362}"
VARIANTS_PER_EXAMPLE="${VARIANTS_PER_EXAMPLE:-2}"
SKIP_REAL_ABSENT_STARTER="${SKIP_REAL_ABSENT_STARTER:-0}"
OUTPUT_DIR="$SEEKUI_WORK/outputs"

dependency_arg() {
  local dependency="$1"
  if [[ -n "$dependency" ]]; then
    printf -- '--dependency=afterok:%s' "$dependency"
  fi
}

submit_optional() {
  local dependency="$1"
  local job_name="$2"
  local script="$3"
  local dep_arg
  dep_arg="$(dependency_arg "$dependency")"
  sbatch --parsable \
    ${dep_arg:+"$dep_arg"} \
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

terminal_jobs=()

filtered_job=""
if can_run_evidence_filter; then
  filtered_job="$(submit_optional "" "seekui-evid-filter" scripts_utah/evaluate_evidence_filtered_status.slurm)"
  terminal_jobs+=("$filtered_job")
else
  echo "Skipping evidence filtered eval; missing evidence prediction or absent sanity CSV."
fi

hardcmp_job=""
if can_run_hardcmp; then
  hardcmp_job="$(submit_optional "" "seekui-vlm-hardcmp" scripts_utah/export_vlm_hard_case_comparison.slurm)"
  terminal_jobs+=("$hardcmp_job")
else
  echo "Skipping hard-case comparison; missing one or more VLM hard-case summary JSONs."
fi

realabs_job=""
if [[ "$SKIP_REAL_ABSENT_STARTER" != "1" ]]; then
  if can_run_realabs_starter; then
    realabs_job="$(submit_optional "" "seekui-realabs-sheet" scripts_utah/export_real_absent_validation_sheet.slurm)"
    terminal_jobs+=("$realabs_job")
  else
    echo "Skipping real absent starter; missing scanpath_train_explanation.json or target2text.json."
  fi
fi

summary_args=(--parsable --job-name="seekui-post-summary")
if [[ ${#terminal_jobs[@]} -gt 0 ]]; then
  summary_dependency="$(IFS=:; echo "${terminal_jobs[*]}")"
  summary_args+=(--dependency="afterok:$summary_dependency")
fi
summary_args+=(--export=ALL,SUBSET_LIMIT="$SUBSET_LIMIT",VARIANTS_PER_EXAMPLE="$VARIANTS_PER_EXAMPLE")
summary_job="$(sbatch "${summary_args[@]}" scripts_utah/summarize_research_outputs.slurm)"

cat <<EOF
Post-evidence CPU analysis submitted.
  evidence filtered eval : ${filtered_job:-skipped}
  hard-case comparison   : ${hardcmp_job:-skipped}
  real absent starter    : ${realabs_job:-skipped}
  summary/status         : $summary_job

Key outputs:
  $SEEKUI_WORK/outputs/vlm_evidence_predictions_SeekUI_vlm_evidence_evidence_aware_filtered_status_eval.csv
  $SEEKUI_WORK/outputs/vlm_hard_cases/vlm_hard_case_comparison.md
  $SEEKUI_WORK/outputs/real_absent_validation/real_absent_validation_starter.md
  $SEEKUI_WORK/outputs/followup_status.md
  $SEEKUI_WORK/outputs/research_summary.md

Use:
  squeue -u "$USER" -o "%.18i %.18a %.14P %.28j %.8T %.10M %.12l %.20b %.30R"
EOF
