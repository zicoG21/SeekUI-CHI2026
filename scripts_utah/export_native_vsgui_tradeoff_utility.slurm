#!/usr/bin/env bash
#SBATCH --job-name=seekui-native-util
#SBATCH --account=notchpeak-shared-short
#SBATCH --partition=notchpeak-shared-short
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:10:00
#SBATCH --output=seekui-native-util-%j.out

set -euo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:-$(pwd)}"
cd "$REPO_ROOT"

SEEKUI_WORK="${SEEKUI_WORK:-${SCRATCH:-$REPO_ROOT/.scratch}/seekui}"
OUT_DIR="${OUT_DIR:-$SEEKUI_WORK/outputs/native_vsgui10k/tradeoff_utility}"

module load miniconda3/25.9.1
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate seekui

python scripts_research/export_tradeoff_utility.py \
  --work-dir "$SEEKUI_WORK" \
  --out-dir "$OUT_DIR" \
  --method-contains native \
  --cost-ratios "${COST_RATIOS:-1:1,1:2,1:5,1:10,2:1,5:1,10:1}" \
  --title "Native VSGUI PR/ROC and Cost-Sensitive Utility"

echo "Native VSGUI utility summary: $OUT_DIR/tradeoff_summary.md"
cat "$OUT_DIR/tradeoff_summary.md"
