#!/usr/bin/env bash
#SBATCH --job-name=seekui-eval
#SBATCH --account=notchpeak-shared-short
#SBATCH --partition=notchpeak-shared-short
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=02:00:00
#SBATCH --output=seekui-eval-%j.out

set -euo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:-$(pwd)}"
cd "$REPO_ROOT"

SEEKUI_WORK="${SEEKUI_WORK:-${SCRATCH:-$REPO_ROOT/.scratch}/seekui}"
PREDICTION_FILE="${PREDICTION_FILE:-$SEEKUI_WORK/outputs/predictions_1362.json}"
EVAL_COPY="${EVAL_COPY:-evaluation/test_predictions_seekui_1362.json}"
EVAL_LOG="${EVAL_LOG:-$SEEKUI_WORK/outputs/eval_seekui_1362.txt}"

module load miniconda3/25.9.1
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate seekui

mkdir -p "$(dirname "$EVAL_LOG")"
cp "$PREDICTION_FILE" "$EVAL_COPY"

cd evaluation
python evaluation.py --prediction_file "$(basename "$EVAL_COPY")" | tee "$EVAL_LOG"

echo "Evaluation log saved to $EVAL_LOG"
