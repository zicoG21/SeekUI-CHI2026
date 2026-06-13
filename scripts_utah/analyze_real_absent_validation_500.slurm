#!/usr/bin/env bash
#SBATCH --job-name=seekui-real500-analysis
#SBATCH --account=notchpeak-shared-short
#SBATCH --partition=notchpeak-shared-short
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:20:00
#SBATCH --output=seekui-real500-analysis-%j.out

set -euo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:-$(pwd)}"
cd "$REPO_ROOT"

SEEKUI_WORK="${SEEKUI_WORK:-${SCRATCH:-$REPO_ROOT/.scratch}/seekui}"
OUTPUT_DIR="$SEEKUI_WORK/outputs"
REALABS_DIR="${REALABS_DIR:-$OUTPUT_DIR/real_absent_validation_500}"
OUT_DIR="${OUT_DIR:-$REALABS_DIR/analysis}"
BOOTSTRAP="${BOOTSTRAP:-2000}"

module load miniconda3/25.9.1
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate seekui

args=(
  --input-json "$REALABS_DIR/real_absent_validation_eval.json"
  --baseline prompt
  --combined combined_best_f1
  --ocr-aware vlm_ocr_aware
  --evidence-aware vlm_evidence
  --bootstrap "$BOOTSTRAP"
  --out-dir "$OUT_DIR"
  --prediction "prompt=$OUTPUT_DIR/present_absent_predictions_SeekUI_real_absent500.json"
  --prediction "combined_best_f1=$OUTPUT_DIR/present_absent_predictions_SeekUI_real_absent500_combined_and_present_only_best_f1.json"
  --prediction "combined_default=$OUTPUT_DIR/present_absent_predictions_SeekUI_real_absent500_combined_and_present_only.json"
  --prediction "vlm_ocr_aware=$OUTPUT_DIR/vlm_presence_predictions_SeekUI_vlm_presence_real_absent500_ocr_aware.json"
  --prediction "vlm_search_behavior=$OUTPUT_DIR/vlm_presence_predictions_SeekUI_vlm_presence_real_absent500_search_behavior.json"
  --prediction "vlm_conservative=$OUTPUT_DIR/vlm_presence_predictions_SeekUI_vlm_presence_real_absent500_conservative.json"
  --prediction "vlm_direct=$OUTPUT_DIR/vlm_presence_predictions_SeekUI_vlm_presence_real_absent500.json"
)

if [[ -f "$OUTPUT_DIR/vlm_evidence_predictions_SeekUI_vlm_evidence_real_absent500_evidence_aware.json" ]]; then
  args+=(--prediction "vlm_evidence=$OUTPUT_DIR/vlm_evidence_predictions_SeekUI_vlm_evidence_real_absent500_evidence_aware.json")
else
  echo "Skipping evidence-aware prediction; file not found."
fi

python scripts_research/analyze_real_absent_validation.py "${args[@]}"

echo "Analysis:"
cat "$OUT_DIR/real_absent_validation_analysis.md"
