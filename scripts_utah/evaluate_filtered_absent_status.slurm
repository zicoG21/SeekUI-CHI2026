#!/usr/bin/env bash
#SBATCH --job-name=seekui-filter-eval
#SBATCH --account=notchpeak-shared-short
#SBATCH --partition=notchpeak-shared-short
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:10:00
#SBATCH --output=seekui-filter-eval-%j.out

set -euo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:-$(pwd)}"
cd "$REPO_ROOT"

SEEKUI_WORK="${SEEKUI_WORK:-${SCRATCH:-$REPO_ROOT/.scratch}/seekui}"
OUTPUT_DIR="$SEEKUI_WORK/outputs"
FILTER_CSV="${FILTER_CSV:-$OUTPUT_DIR/absent_benchmark_sanity/absent_examples_sanity.csv}"
OUT_DIR="${OUT_DIR:-$OUTPUT_DIR/filtered_status_eval}"

module load miniconda3/25.9.1
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate seekui

mkdir -p "$OUT_DIR"

predictions=()
for model in SeekUI SeekUI_sft; do
  for variant in \
    "prompt=$OUTPUT_DIR/present_absent_predictions_${model}.json" \
    "cognitive=$OUTPUT_DIR/present_absent_predictions_${model}_cognitive_stop_present_only.json" \
    "ocr=$OUTPUT_DIR/present_absent_predictions_${model}_ocr_candidate_verifier_present_only.json" \
    "combined_default=$OUTPUT_DIR/present_absent_predictions_${model}_combined_and_present_only.json" \
    "combined_best_f1=$OUTPUT_DIR/present_absent_predictions_${model}_combined_and_present_only_best_f1.json"; do
    name="${variant%%=*}"
    path="${variant#*=}"
    predictions+=(--prediction "${model}_${name}=${path}")
  done
done

python scripts_research/evaluate_absent_status_filtered.py \
  --filter-csv "$FILTER_CSV" \
  --exclude-flag annotation_conflict_flag \
  --exclude-flag ocr_leak_flag \
  "${predictions[@]}" \
  --output-json "$OUT_DIR/filtered_absent_status.json" \
  --output-csv "$OUT_DIR/filtered_absent_status.csv" \
  --excluded-output "$OUT_DIR/excluded_absent_examples.csv"

echo "Filtered status CSV: $OUT_DIR/filtered_absent_status.csv"
cat "$OUT_DIR/filtered_absent_status.csv"
