#!/usr/bin/env bash
#SBATCH --job-name=seekui-native-audit
#SBATCH --account=notchpeak-shared-short
#SBATCH --partition=notchpeak-shared-short
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:10:00
#SBATCH --output=seekui-native-audit-%j.out

set -euo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:-$(pwd)}"
cd "$REPO_ROOT"

SEEKUI_WORK="${SEEKUI_WORK:-${SCRATCH:-$REPO_ROOT/.scratch}/seekui}"
OUTPUT_DIR="$SEEKUI_WORK/outputs"

module load miniconda3/25.9.1
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate seekui

MODEL_NAME="${MODEL_NAME:-SeekUI}"
SPLIT_NAME="${SPLIT_NAME:-native_text_color_balanced}"
VARIANT="${VARIANT:-combined_and_present_only_best_f1}"
PREDICTIONS="${PREDICTIONS:-$OUTPUT_DIR/present_absent_predictions_${MODEL_NAME}_${SPLIT_NAME}_${VARIANT}.json}"
OUT_DIR="${OUT_DIR:-$OUTPUT_DIR/native_vsgui10k/label_conflict_audit}"
OUT_PREFIX="$OUT_DIR/${SPLIT_NAME}_${VARIANT}"

python scripts_research/audit_native_vsgui_label_conflicts.py \
  --predictions "$PREDICTIONS" \
  --output-json "${OUT_PREFIX}.json" \
  --output-csv "${OUT_PREFIX}_visible_conflicts.csv" \
  --output-md "${OUT_PREFIX}.md" \
  --strong-threshold "${STRONG_THRESHOLD:-0.8}"

echo "Native VSGUI label conflict audit: ${OUT_PREFIX}.md"
cat "${OUT_PREFIX}.md"
