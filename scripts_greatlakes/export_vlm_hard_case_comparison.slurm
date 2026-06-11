#!/usr/bin/env bash
#SBATCH --job-name=seekui-vlm-hardcmp
#SBATCH --account=engin1
#SBATCH --partition=standard
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=00:05:00
#SBATCH --output=seekui-vlm-hardcmp-%j.out

set -euo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:-$(pwd)}"
cd "$REPO_ROOT"

SEEKUI_WORK="${SEEKUI_WORK:-/scratch/engin_root/engin1/$USER/seekui}"
OUTPUT_DIR="$SEEKUI_WORK/outputs"
OUT_DIR="${OUT_DIR:-$OUTPUT_DIR/vlm_hard_cases}"

if [[ -n "${CONDA_MODULE:-}" ]]; then
  module load "$CONDA_MODULE"
else
  module load python3.10-anaconda/2023.03
fi
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate "${CONDA_ENV:-seekui}"

direct="$OUTPUT_DIR/vlm_hard_cases/SeekUI_vlm_presence_vs_SeekUI_combined_and/summary.json"
ocr_aware="$OUTPUT_DIR/vlm_hard_cases/SeekUI_vlm_presence_ocr_aware_vs_SeekUI_combined_and/summary.json"
evidence="$OUTPUT_DIR/vlm_hard_cases/SeekUI_vlm_evidence_aware_vs_SeekUI_combined_and/summary.json"

missing=0
for path in "$direct" "$ocr_aware" "$evidence"; do
  if [[ ! -f "$path" ]]; then
    echo "Missing summary: $path"
    missing=1
  fi
done
if [[ "$missing" != "0" ]]; then
  echo "Generate missing hard-case summaries before running this comparison."
  exit 1
fi

python scripts_research/export_vlm_hard_case_comparison.py \
  --summary "direct=$direct" \
  --summary "ocr_aware=$ocr_aware" \
  --summary "evidence_aware=$evidence" \
  --output-csv "$OUT_DIR/vlm_hard_case_comparison.csv" \
  --output-md "$OUT_DIR/vlm_hard_case_comparison.md"

echo "VLM hard-case comparison: $OUT_DIR/vlm_hard_case_comparison.md"
cat "$OUT_DIR/vlm_hard_case_comparison.md"
