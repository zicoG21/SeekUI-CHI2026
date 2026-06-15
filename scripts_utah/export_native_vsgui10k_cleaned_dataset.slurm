#!/usr/bin/env bash
#SBATCH --job-name=seekui-native-clean
#SBATCH --account=notchpeak-shared-short
#SBATCH --partition=notchpeak-shared-short
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:15:00
#SBATCH --output=seekui-native-clean-%j.out

set -euo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:-$(pwd)}"
cd "$REPO_ROOT"

SEEKUI_WORK="${SEEKUI_WORK:-${SCRATCH:-$REPO_ROOT/.scratch}/seekui}"
PROCESSED_DIR="${PROCESSED_DIR:-$SEEKUI_WORK/outputs/native_vsgui10k/processed_v2}"
OUT_DIR="${OUT_DIR:-$PROCESSED_DIR/final_cleaned}"

module load miniconda3/25.9.1
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate seekui

if [[ ! -d "$PROCESSED_DIR/splits" ]]; then
  echo "Missing processed splits: $PROCESSED_DIR/splits" >&2
  echo "Run: sbatch scripts_utah/export_processed_native_vsgui10k.slurm" >&2
  exit 1
fi

python scripts_research/export_native_vsgui10k_cleaned_dataset.py \
  --processed-dir "$PROCESSED_DIR" \
  --out-dir "$OUT_DIR"

echo "Native VSGUI10K cleaned dataset summary:"
cat "$OUT_DIR/native_vsgui10k_cleaned_summary.md"
