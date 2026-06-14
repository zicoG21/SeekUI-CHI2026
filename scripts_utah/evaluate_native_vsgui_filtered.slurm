#!/usr/bin/env bash
#SBATCH --job-name=seekui-native-filter
#SBATCH --account=notchpeak-shared-short
#SBATCH --partition=notchpeak-shared-short
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:10:00
#SBATCH --output=seekui-native-filter-%j.out

set -euo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:-$(pwd)}"
cd "$REPO_ROOT"

SEEKUI_WORK="${SEEKUI_WORK:-${SCRATCH:-$REPO_ROOT/.scratch}/seekui}"
OUTPUT_DIR="$SEEKUI_WORK/outputs"
OUT_DIR="$OUTPUT_DIR/native_vsgui10k/filtered_eval"

module load miniconda3/25.9.1
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate seekui

MODEL_NAME="${MODEL_NAME:-SeekUI}"
SPLIT_NAME="${SPLIT_NAME:-native_text_color_balanced}"
VLM_PROMPT_VARIANT="${VLM_PROMPT_VARIANT:-ocr_aware}"
AUDIT_JSON="${AUDIT_JSON:-$OUTPUT_DIR/native_vsgui10k/label_conflict_audit/${SPLIT_NAME}_combined_and_present_only_best_f1.json}"
OUT_PREFIX="$OUT_DIR/${SPLIT_NAME}_${VLM_PROMPT_VARIANT}"

python scripts_research/evaluate_native_vsgui_filtered.py \
  --work-dir "$SEEKUI_WORK" \
  --split-name "$SPLIT_NAME" \
  --model-name "$MODEL_NAME" \
  --vlm-prompt-variant "$VLM_PROMPT_VARIANT" \
  --audit-json "$AUDIT_JSON" \
  --output-json "${OUT_PREFIX}.json" \
  --output-csv "${OUT_PREFIX}.csv" \
  --output-md "${OUT_PREFIX}.md"

echo "Filtered native VSGUI evaluation: ${OUT_PREFIX}.md"
cat "${OUT_PREFIX}.md"
