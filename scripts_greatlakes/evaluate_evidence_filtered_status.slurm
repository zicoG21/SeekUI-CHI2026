#!/usr/bin/env bash
#SBATCH --job-name=seekui-evid-filter
#SBATCH --account=engin1
#SBATCH --partition=standard
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=00:05:00
#SBATCH --output=seekui-evid-filter-%j.out

set -euo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:-$(pwd)}"
cd "$REPO_ROOT"

SEEKUI_WORK="${SEEKUI_WORK:-/scratch/engin_root/engin1/$USER/seekui}"
OUTPUT_DIR="$SEEKUI_WORK/outputs"
MODEL_LABEL="${MODEL_LABEL:-SeekUI_vlm_evidence_evidence_aware}"
PREDICTIONS="${PREDICTIONS:-$OUTPUT_DIR/vlm_evidence_predictions_${MODEL_LABEL}.json}"
FILTER_CSV="${FILTER_CSV:-$OUTPUT_DIR/absent_benchmark_sanity/absent_examples_sanity.csv}"

if [[ -n "${CONDA_MODULE:-}" ]]; then
  module load "$CONDA_MODULE"
else
  module load python3.10-anaconda/2023.03
fi
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate "${CONDA_ENV:-seekui}"

python scripts_research/evaluate_absent_status_filtered.py \
  --filter-csv "$FILTER_CSV" \
  --exclude-flag annotation_conflict_flag \
  --exclude-flag ocr_leak_flag \
  --prediction "${MODEL_LABEL}=${PREDICTIONS}" \
  --output-json "${PREDICTIONS%.json}_filtered_status_eval.json" \
  --output-csv "${PREDICTIONS%.json}_filtered_status_eval.csv" \
  --excluded-output "${PREDICTIONS%.json}_filtered_excluded.csv"

echo "Filtered eval: ${PREDICTIONS%.json}_filtered_status_eval.csv"
cat "${PREDICTIONS%.json}_filtered_status_eval.csv"
