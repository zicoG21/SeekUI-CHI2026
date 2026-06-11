#!/usr/bin/env bash
#SBATCH --job-name=seekui-realabs-sum
#SBATCH --account=engin1
#SBATCH --partition=standard
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=00:05:00
#SBATCH --output=seekui-realabs-sum-%j.out

set -euo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:-$(pwd)}"
cd "$REPO_ROOT"

SEEKUI_WORK="${SEEKUI_WORK:-/scratch/engin_root/engin1/$USER/seekui}"
OUT_DIR="${OUT_DIR:-$SEEKUI_WORK/outputs/real_absent_validation}"

if [[ -n "${CONDA_MODULE:-}" ]]; then
  module load "$CONDA_MODULE"
else
  module load python3.10-anaconda/2023.03
fi
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate "${CONDA_ENV:-seekui}"

python scripts_research/summarize_real_absent_results.py \
  --work-dir "$SEEKUI_WORK" \
  --output-json "$OUT_DIR/real_absent_results.json" \
  --output-csv "$OUT_DIR/real_absent_results.csv" \
  --output-md "$OUT_DIR/real_absent_results.md"

echo "Real-absent results: $OUT_DIR/real_absent_results.md"
cat "$OUT_DIR/real_absent_results.md"
