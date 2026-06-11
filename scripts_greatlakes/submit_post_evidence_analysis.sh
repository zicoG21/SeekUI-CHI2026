#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

SEEKUI_WORK="${SEEKUI_WORK:-/scratch/engin_root/engin1/$USER/seekui}"
SKIP_REAL_ABSENT_STARTER="${SKIP_REAL_ABSENT_STARTER:-0}"
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

filtered_job="$(submit_job "seekui-evid-filter" scripts_greatlakes/evaluate_evidence_filtered_status.slurm)"
hardcmp_job="$(submit_job "seekui-vlm-hardcmp" scripts_greatlakes/export_vlm_hard_case_comparison.slurm)"

realabs_job=""
if [[ "$SKIP_REAL_ABSENT_STARTER" != "1" ]]; then
  realabs_job="$(submit_job "seekui-realabs-sheet" scripts_greatlakes/export_real_absent_validation_sheet.slurm)"
fi

cat <<EOF
Great Lakes post-evidence CPU analysis submitted.
  evidence filtered eval : $filtered_job
  hard-case comparison   : $hardcmp_job
  real absent starter    : ${realabs_job:-skipped}

Key outputs:
  $SEEKUI_WORK/outputs/vlm_evidence_predictions_SeekUI_vlm_evidence_evidence_aware_filtered_status_eval.csv
  $SEEKUI_WORK/outputs/vlm_hard_cases/vlm_hard_case_comparison.md
  $SEEKUI_WORK/outputs/real_absent_validation/real_absent_validation_starter.md

Use:
  squeue -u "$USER" -o "%.18i %.18a %.14P %.28j %.8T %.10M %.12l %.20b %.30R"
EOF
