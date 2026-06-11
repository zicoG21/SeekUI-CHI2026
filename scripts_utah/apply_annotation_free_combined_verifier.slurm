#!/usr/bin/env bash
#SBATCH --job-name=seekui-af-combo
#SBATCH --account=notchpeak-shared-short
#SBATCH --partition=notchpeak-shared-short
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:30:00
#SBATCH --output=seekui-af-combo-%j.out

set -euo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:-$(pwd)}"
cd "$REPO_ROOT"

SEEKUI_WORK="${SEEKUI_WORK:-${SCRATCH:-$REPO_ROOT/.scratch}/seekui}"
DATA_DIR="$SEEKUI_WORK/data"
OUTPUT_DIR="$SEEKUI_WORK/outputs"
EVIDENCE_DIR="${EVIDENCE_DIR:-$OUTPUT_DIR/annotation_free_stopping_evidence}"
OCR_CANDIDATES="${OCR_CANDIDATES:-$OUTPUT_DIR/ocr_candidates_tesseract.json}"
MODE="${MODE:-present_only}"
RULES="${RULES:-and}"
COGNITIVE_THRESHOLD="${COGNITIVE_THRESHOLD:-0.05}"
OCR_THRESHOLD="${OCR_THRESHOLD:-0.40}"
THRESHOLD_STEP="${THRESHOLD_STEP:-0.05}"
COGNITIVE_THRESHOLD_MAX="${COGNITIVE_THRESHOLD_MAX:-0.60}"
OCR_THRESHOLD_MAX="${OCR_THRESHOLD_MAX:-0.80}"
MIN_OCR_CONF="${MIN_OCR_CONF:-35}"

module load miniconda3/25.9.1
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate seekui

best_thresholds() {
  python - "$1" <<'PY'
import csv
import sys

path = sys.argv[1]
with open(path, "r", encoding="utf-8", newline="") as f:
    rows = list(csv.DictReader(f))
if not rows:
    raise SystemExit(f"No rows in sweep: {path}")
best = max(
    rows,
    key=lambda r: (
        float(r.get("absent_f1") or 0.0),
        float(r.get("accuracy") or 0.0),
        float(r.get("absent_precision") or 0.0),
    ),
)
print(best["cognitive_threshold"], best["ocr_threshold"])
PY
}

for model in SeekUI SeekUI_sft; do
  for rule in $RULES; do
    base="$OUTPUT_DIR/present_absent_predictions_${model}_annotation_free_combined_${rule}_${MODE}"
    evidence="$EVIDENCE_DIR/${model}_annotation_free_stopping_evidence.csv"
    sweep_path="${base}_threshold_sweep.csv"

    python scripts_research/apply_combined_verifier.py \
      --predictions "$OUTPUT_DIR/present_absent_predictions_${model}.json" \
      --evidence "$evidence" \
      --ocr-candidates "$OCR_CANDIDATES" \
      --target2text "$DATA_DIR/target2text.json" \
      --rule "$rule" \
      --mode "$MODE" \
      --cognitive-threshold "$COGNITIVE_THRESHOLD" \
      --ocr-threshold "$OCR_THRESHOLD" \
      --threshold-step "$THRESHOLD_STEP" \
      --cognitive-threshold-max "$COGNITIVE_THRESHOLD_MAX" \
      --ocr-threshold-max "$OCR_THRESHOLD_MAX" \
      --min-ocr-conf "$MIN_OCR_CONF" \
      --output "${base}.json" \
      --metrics-output "${base}_status_eval.json" \
      --detail-output "${base}_details.csv" \
      --sweep-output "$sweep_path"

    read -r best_cog best_ocr < <(best_thresholds "$sweep_path")
    echo "$model $rule best absent-F1 thresholds: cognitive=$best_cog ocr=$best_ocr"

    python scripts_research/apply_combined_verifier.py \
      --predictions "$OUTPUT_DIR/present_absent_predictions_${model}.json" \
      --evidence "$evidence" \
      --ocr-candidates "$OCR_CANDIDATES" \
      --target2text "$DATA_DIR/target2text.json" \
      --rule "$rule" \
      --mode "$MODE" \
      --cognitive-threshold "$best_cog" \
      --ocr-threshold "$best_ocr" \
      --min-ocr-conf "$MIN_OCR_CONF" \
      --output "${base}_best_f1.json" \
      --metrics-output "${base}_best_f1_status_eval.json" \
      --detail-output "${base}_best_f1_details.csv"
  done
done

echo "Annotation-free combined verifier outputs:"
ls -lh "$OUTPUT_DIR"/present_absent_predictions_*_annotation_free_combined_*_"$MODE"*_status_eval.json
