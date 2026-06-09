#!/usr/bin/env bash
#SBATCH --job-name=seekui-summary
#SBATCH --account=notchpeak-shared-short
#SBATCH --partition=notchpeak-shared-short
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=01:00:00
#SBATCH --output=seekui-summary-%j.out

set -euo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:-$(pwd)}"
cd "$REPO_ROOT"

SEEKUI_WORK="${SEEKUI_WORK:-${SCRATCH:-$REPO_ROOT/.scratch}/seekui}"
SUBSET_LIMIT="${SUBSET_LIMIT:-1362}"
VARIANTS_PER_EXAMPLE="${VARIANTS_PER_EXAMPLE:-2}"
OUTPUT_DIR="$SEEKUI_WORK/outputs"
COMPARE_DIR="$OUTPUT_DIR/comparisons"

module load miniconda3/25.9.1
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate seekui

mkdir -p "$OUTPUT_DIR" "$COMPARE_DIR"

python scripts_research/generate_review_artifacts.py \
  --work-dir "$SEEKUI_WORK" \
  --limit "$SUBSET_LIMIT" \
  --variants-per-example "$VARIANTS_PER_EXAMPLE" \
  --review-limit "${REVIEW_LIMIT:-50}" \
  --out-dir "$OUTPUT_DIR/review_cases"

review_inputs=()
if [[ -f "$OUTPUT_DIR/review_cases/absent_label_review.csv" ]]; then
  review_inputs+=("$OUTPUT_DIR/review_cases/absent_label_review.csv")
fi
if [[ -f "$OUTPUT_DIR/review_cases/semantic_query_review.csv" ]]; then
  review_inputs+=("$OUTPUT_DIR/review_cases/semantic_query_review.csv")
fi
if [[ -f "$OUTPUT_DIR/review_cases/prediction_edge_cases_review.csv" ]]; then
  review_inputs+=("$OUTPUT_DIR/review_cases/prediction_edge_cases_review.csv")
fi

if [[ ${#review_inputs[@]} -gt 0 ]]; then
  python scripts_research/summarize_manual_review.py \
    --input "${review_inputs[@]}" \
    --output-json "$OUTPUT_DIR/review_cases/manual_review_summary.json" \
    --output-md "$OUTPUT_DIR/review_cases/manual_review_summary.md"
fi

compare_if_available() {
  local name="$1"
  local a="$2"
  local b="$3"

  if [[ -f "$a" && -f "$b" ]]; then
    python scripts_research/compare_predictions.py \
      --a "$a" \
      --b "$b" \
      --label-a SeekUI \
      --label-b SeekUI_sft \
      --out-csv "$COMPARE_DIR/${name}.csv" \
      --out-json "$COMPARE_DIR/${name}.json" \
      --out-md "$COMPARE_DIR/${name}.md"
  else
    echo "Skipping $name comparison because one or both files are missing."
    echo "  A: $a"
    echo "  B: $b"
  fi
}

compare_if_available \
  "base_SeekUI_vs_SeekUI_sft_${SUBSET_LIMIT}" \
  "$OUTPUT_DIR/predictions_SeekUI_${SUBSET_LIMIT}.json" \
  "$OUTPUT_DIR/predictions_SeekUI_sft_${SUBSET_LIMIT}.json"

compare_if_available \
  "present_absent_SeekUI_vs_SeekUI_sft" \
  "$OUTPUT_DIR/present_absent_predictions_SeekUI.json" \
  "$OUTPUT_DIR/present_absent_predictions_SeekUI_sft.json"

compare_if_available \
  "image_cue_SeekUI_vs_SeekUI_sft_${SUBSET_LIMIT}" \
  "$OUTPUT_DIR/image_cue_predictions_SeekUI_${SUBSET_LIMIT}.json" \
  "$OUTPUT_DIR/image_cue_predictions_SeekUI_sft_${SUBSET_LIMIT}.json"

compare_if_available \
  "semantic_query_SeekUI_vs_SeekUI_sft_${SUBSET_LIMIT}_v${VARIANTS_PER_EXAMPLE}" \
  "$OUTPUT_DIR/semantic_query_predictions_SeekUI_${SUBSET_LIMIT}_v${VARIANTS_PER_EXAMPLE}.json" \
  "$OUTPUT_DIR/semantic_query_predictions_SeekUI_sft_${SUBSET_LIMIT}_v${VARIANTS_PER_EXAMPLE}.json"

python scripts_research/check_followup_status.py \
  --work-dir "$SEEKUI_WORK" \
  --limit "$SUBSET_LIMIT" \
  --variants-per-example "$VARIANTS_PER_EXAMPLE" \
  --output-json "$OUTPUT_DIR/followup_status.json" \
  --output-md "$OUTPUT_DIR/followup_status.md"

python scripts_research/summarize_research_outputs.py \
  --work-dir "$SEEKUI_WORK" \
  --output "$OUTPUT_DIR/research_summary.md"

echo "Research summary written to $OUTPUT_DIR/research_summary.md"
echo "CSV tables written under $OUTPUT_DIR/research_summary_tables"
echo "Pairwise comparisons written under $COMPARE_DIR when both model outputs exist."
