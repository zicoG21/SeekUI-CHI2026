#!/usr/bin/env bash
#SBATCH --job-name=seekui-native-v2-analysis
#SBATCH --account=notchpeak-shared-short
#SBATCH --partition=notchpeak-shared-short
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:20:00
#SBATCH --output=seekui-native-v2-analysis-%j.out

set -euo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:-$(pwd)}"
cd "$REPO_ROOT"

SEEKUI_WORK="${SEEKUI_WORK:-${SCRATCH:-$REPO_ROOT/.scratch}/seekui}"
OUT_DIR="${OUT_DIR:-$SEEKUI_WORK/outputs/native_vsgui10k/processed_v2/analysis}"
MODEL_NAME="${MODEL_NAME:-SeekUI}"
BOOTSTRAP="${BOOTSTRAP:-2000}"
CASE_LIMIT="${CASE_LIMIT:-80}"

module load miniconda3/25.9.1
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate seekui

python scripts_research/analyze_native_v2_balanced.py \
  --work-dir "$SEEKUI_WORK" \
  --model-name "$MODEL_NAME" \
  --bootstrap "$BOOTSTRAP" \
  --case-limit "$CASE_LIMIT" \
  --out-dir "$OUT_DIR"

python scripts_research/export_native_v2_operating_points.py \
  --input-csv "$OUT_DIR/native_v2_balanced_metrics_ci.csv" \
  --output-json "$OUT_DIR/native_v2_operating_points.json" \
  --output-csv "$OUT_DIR/native_v2_operating_points.csv" \
  --output-md "$OUT_DIR/native_v2_operating_points.md"

echo "Native v2 balanced analysis: $OUT_DIR/native_v2_balanced_analysis.md"
cat "$OUT_DIR/native_v2_balanced_analysis.md"
echo
echo "Native v2 operating points: $OUT_DIR/native_v2_operating_points.md"
cat "$OUT_DIR/native_v2_operating_points.md"
