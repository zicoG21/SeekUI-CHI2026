#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

SEEKUI_WORK="${SEEKUI_WORK:-${SCRATCH:-$REPO_ROOT/.scratch}/seekui}"
SUBSET_LIMIT="${SUBSET_LIMIT:-1362}"
VARIANTS_PER_EXAMPLE="${VARIANTS_PER_EXAMPLE:-2}"
SKIP_REAL_ABSENT_STARTER="${SKIP_REAL_ABSENT_STARTER:-0}"

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

filtered_job="$(submit_optional "" "seekui-evid-filter" scripts_utah/evaluate_evidence_filtered_status.slurm)"
hardcmp_job="$(submit_optional "" "seekui-vlm-hardcmp" scripts_utah/export_vlm_hard_case_comparison.slurm)"
terminal_jobs=("$filtered_job" "$hardcmp_job")

realabs_job=""
if [[ "$SKIP_REAL_ABSENT_STARTER" != "1" ]]; then
  realabs_job="$(submit_optional "" "seekui-realabs-sheet" scripts_utah/export_real_absent_validation_sheet.slurm)"
  terminal_jobs+=("$realabs_job")
fi

summary_dependency="$(IFS=:; echo "${terminal_jobs[*]}")"
summary_job="$(sbatch --parsable \
  --dependency="afterok:$summary_dependency" \
  --job-name="seekui-post-summary" \
  --export=ALL,SUBSET_LIMIT="$SUBSET_LIMIT",VARIANTS_PER_EXAMPLE="$VARIANTS_PER_EXAMPLE" \
  scripts_utah/summarize_research_outputs.slurm)"

cat <<EOF
Post-evidence CPU analysis submitted.
  evidence filtered eval : $filtered_job
  hard-case comparison   : $hardcmp_job
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
