#!/usr/bin/env bash
#SBATCH --job-name=seekui-realabs-prefill
#SBATCH --account=engin1
#SBATCH --partition=standard
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=00:05:00
#SBATCH --output=seekui-realabs-prefill-%j.out

set -euo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:-$(pwd)}"
cd "$REPO_ROOT"

SEEKUI_WORK="${SEEKUI_WORK:-/scratch/engin_root/engin1/$USER/seekui}"
OUT_DIR="${OUT_DIR:-$SEEKUI_WORK/outputs/real_absent_validation}"
INPUT_CSV="${INPUT_CSV:-$OUT_DIR/real_absent_validation_starter.csv}"
OUTPUT_CSV="${OUTPUT_CSV:-$OUT_DIR/real_absent_validation_prefilled.csv}"
OUTPUT_MD="${OUTPUT_MD:-$OUT_DIR/real_absent_validation_prefilled.md}"

if [[ -n "${CONDA_MODULE:-}" ]]; then
  module load "$CONDA_MODULE"
else
  module load python3.10-anaconda/2023.03
fi
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate "${CONDA_ENV:-seekui}"

python scripts_research/prefill_real_absent_validation_sheet.py \
  --input-csv "$INPUT_CSV" \
  --output-csv "$OUTPUT_CSV" \
  --output-md "$OUTPUT_MD"

echo "Prefilled CSV: $OUTPUT_CSV"
echo "Prefill summary: $OUTPUT_MD"
cat "$OUTPUT_MD"
