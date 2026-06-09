#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

SEEKUI_WORK="${SEEKUI_WORK:-${SCRATCH:-$REPO_ROOT/.scratch}/seekui}"
SUBSET_LIMIT="${SUBSET_LIMIT:-1362}"
VARIANTS_PER_EXAMPLE="${VARIANTS_PER_EXAMPLE:-2}"
RUN_SFT="${RUN_SFT:-0}"
SKIP_PREP="${SKIP_PREP:-0}"

models=(SeekUI)
if [[ "$RUN_SFT" == "1" ]]; then
  models+=(SeekUI_sft)
fi

submit_prep() {
  if [[ "$SKIP_PREP" == "1" ]]; then
    echo ""
    return
  fi
  sbatch --parsable scripts_utah/offline_research_prep.slurm
}

dependency_arg() {
  local dependency="$1"
  if [[ -n "$dependency" ]]; then
    printf -- '--dependency=afterok:%s' "$dependency"
  fi
}

submit_absent() {
  local dependency="$1"
  local model_name="$2"
  local output_path="$SEEKUI_WORK/outputs/present_absent_predictions_${model_name}.json"
  local dep_arg
  dep_arg="$(dependency_arg "$dependency")"
  sbatch --parsable \
    ${dep_arg:+"$dep_arg"} \
    --job-name="seekui-${model_name}-absent" \
    --export=ALL,MODEL_NAME="$model_name",ABSENT_INPUT="$SEEKUI_WORK/data/present_absent_synthetic_2724.json",OUTPUT_PATH="$output_path" \
    scripts_utah/absent_inference.slurm
}

submit_image_cue() {
  local dependency="$1"
  local model_name="$2"
  local output_path="$SEEKUI_WORK/outputs/image_cue_predictions_${model_name}_${SUBSET_LIMIT}.json"
  local dep_arg
  dep_arg="$(dependency_arg "$dependency")"
  sbatch --parsable \
    ${dep_arg:+"$dep_arg"} \
    --job-name="seekui-${model_name}-imgcue" \
    --export=ALL,MODEL_NAME="$model_name",SUBSET_LIMIT="$SUBSET_LIMIT",OUTPUT_PATH="$output_path" \
    scripts_utah/image_cue_inference.slurm
}

submit_semantic() {
  local dependency="$1"
  local model_name="$2"
  local output_path="$SEEKUI_WORK/outputs/semantic_query_predictions_${model_name}_${SUBSET_LIMIT}_v${VARIANTS_PER_EXAMPLE}.json"
  local dep_arg
  dep_arg="$(dependency_arg "$dependency")"
  sbatch --parsable \
    ${dep_arg:+"$dep_arg"} \
    --job-name="seekui-${model_name}-semantic" \
    --export=ALL,MODEL_NAME="$model_name",SEMANTIC_LIMIT="$SUBSET_LIMIT",VARIANTS_PER_EXAMPLE="$VARIANTS_PER_EXAMPLE",OUTPUT_PATH="$output_path" \
    scripts_utah/semantic_query_inference.slurm
}

submit_split_eval() {
  local dependency="$1"
  local model_name="$2"
  local prediction_path="$SEEKUI_WORK/outputs/semantic_query_predictions_${model_name}_${SUBSET_LIMIT}_v${VARIANTS_PER_EXAMPLE}.json"
  sbatch --parsable \
    --dependency="afterok:$dependency" \
    --job-name="seekui-${model_name}-sem-split" \
    --export=ALL,PREDICTION_FILE="$prediction_path",SPLIT_FIELD=query_type,SPLIT_NAME="semantic_query_${model_name}_query_type" \
    scripts_utah/evaluate_prediction_splits.slurm
}

submit_summary() {
  local dependencies="$1"
  sbatch --parsable \
    --dependency="afterok:$dependencies" \
    --job-name="seekui-follow-summary" \
    --export=ALL,SUBSET_LIMIT="$SUBSET_LIMIT",VARIANTS_PER_EXAMPLE="$VARIANTS_PER_EXAMPLE" \
    scripts_utah/summarize_research_outputs.slurm
}

prep_job="$(submit_prep)"
job_dependency="$prep_job"
terminal_jobs=()

if [[ -z "$prep_job" ]]; then
  echo "Skipping offline prep because SKIP_PREP=1."
fi

for model_name in "${models[@]}"; do
  absent_job="$(submit_absent "$job_dependency" "$model_name")"
  image_job="$(submit_image_cue "$job_dependency" "$model_name")"
  semantic_job="$(submit_semantic "$job_dependency" "$model_name")"
  split_job="$(submit_split_eval "$semantic_job" "$model_name")"

  terminal_jobs+=("$absent_job" "$image_job" "$split_job")

  cat <<EOF
Submitted follow-up jobs for $model_name:
  absent mixed benchmark : $absent_job
  image-cue benchmark    : $image_job
  semantic benchmark     : $semantic_job
  semantic split eval    : $split_job
EOF
done

summary_dependency="$(IFS=:; echo "${terminal_jobs[*]}")"
summary_job="$(submit_summary "$summary_dependency")"

cat <<EOF

Follow-up pipeline submitted.
  offline prep : ${prep_job:-skipped}
  summary     : $summary_job

Key outputs:
  $SEEKUI_WORK/outputs/research_summary.md
  $SEEKUI_WORK/outputs/research_summary.json
  $SEEKUI_WORK/outputs/research_summary_tables/
  $SEEKUI_WORK/outputs/comparisons/

Use:
  squeue -u "$USER"
  tail -n 120 seekui-summary-*.out
EOF
