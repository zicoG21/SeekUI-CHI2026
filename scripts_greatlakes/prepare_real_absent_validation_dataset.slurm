#!/usr/bin/env bash
#SBATCH --job-name=seekui-realabs-prep
#SBATCH --account=engin1
#SBATCH --partition=standard
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=00:05:00
#SBATCH --output=seekui-realabs-prep-%j.out

set -euo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:-$(pwd)}"
cd "$REPO_ROOT"

SEEKUI_WORK="${SEEKUI_WORK:-/scratch/engin_root/engin1/$USER/seekui}"
DATA_DIR="${SEEKUI_DATA_DIR:-$SEEKUI_WORK/data}"
OUTPUT_DIR="$SEEKUI_WORK/outputs"
OUT_DIR="${OUT_DIR:-$OUTPUT_DIR/real_absent_validation}"
SHEET="${SHEET:-$OUT_DIR/real_absent_validation_starter.csv}"

if [[ -n "${CONDA_MODULE:-}" ]]; then
  module load "$CONDA_MODULE"
else
  module load python3.10-anaconda/2023.03
fi
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate "${CONDA_ENV:-seekui}"

include_args=()
if [[ "${INCLUDE_HIGH_AMBIGUITY:-0}" != "0" ]]; then
  include_args+=(--include-high-ambiguity)
fi

python scripts_research/prepare_real_absent_validation_dataset.py \
  --sheet "$SHEET" \
  --scanpath "$DATA_DIR/scanpath_train_explanation.json" \
  --output-json "$OUT_DIR/real_absent_validation_eval.json" \
  --excluded-csv "$OUT_DIR/real_absent_validation_excluded.csv" \
  --summary-md "$OUT_DIR/real_absent_validation_prep.md" \
  "${include_args[@]}"

echo "Eval JSON: $OUT_DIR/real_absent_validation_eval.json"
echo "Prep summary: $OUT_DIR/real_absent_validation_prep.md"
cat "$OUT_DIR/real_absent_validation_prep.md"
