#!/usr/bin/env bash
#SBATCH --job-name=seekui-verifier
#SBATCH --account=notchpeak-shared-short
#SBATCH --partition=notchpeak-shared-short
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:20:00
#SBATCH --output=seekui-verifier-%j.out

set -euo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:-$(pwd)}"
cd "$REPO_ROOT"

SEEKUI_WORK="${SEEKUI_WORK:-${SCRATCH:-$REPO_ROOT/.scratch}/seekui}"
OUTPUT_DIR="$SEEKUI_WORK/outputs"
MODE="${MODE:-present_only}"
SCORE_FIELD="${SCORE_FIELD:-candidate_similarity}"
THRESHOLD="${THRESHOLD:-0.50}"
THRESHOLD_STEP="${THRESHOLD_STEP:-0.05}"

module load miniconda3/25.9.1
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate seekui

for model in SeekUI SeekUI_sft; do
  python scripts_research/apply_candidate_verifier.py \
    --predictions "$OUTPUT_DIR/present_absent_predictions_${model}.json" \
    --evidence "$OUTPUT_DIR/stopping_evidence/${model}_stopping_evidence.csv" \
    --mode "$MODE" \
    --score-field "$SCORE_FIELD" \
    --threshold "$THRESHOLD" \
    --threshold-step "$THRESHOLD_STEP" \
    --output "$OUTPUT_DIR/present_absent_predictions_${model}_candidate_verifier_${SCORE_FIELD}_${MODE}.json" \
    --metrics-output "$OUTPUT_DIR/present_absent_predictions_${model}_candidate_verifier_${SCORE_FIELD}_${MODE}_status_eval.json" \
    --sweep-output "$OUTPUT_DIR/present_absent_predictions_${model}_candidate_verifier_${SCORE_FIELD}_${MODE}_threshold_sweep.csv"
done

echo "Candidate verifier outputs:"
echo "  $OUTPUT_DIR/present_absent_predictions_SeekUI_candidate_verifier_${SCORE_FIELD}_${MODE}_status_eval.json"
echo "  $OUTPUT_DIR/present_absent_predictions_SeekUI_sft_candidate_verifier_${SCORE_FIELD}_${MODE}_status_eval.json"
