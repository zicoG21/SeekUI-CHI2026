#!/usr/bin/env bash
#SBATCH --job-name=seekui-stop-cases
#SBATCH --account=notchpeak-shared-short
#SBATCH --partition=notchpeak-shared-short
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=00:30:00
#SBATCH --output=seekui-stop-cases-%j.out

set -euo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:-$(pwd)}"
cd "$REPO_ROOT"

SEEKUI_WORK="${SEEKUI_WORK:-${SCRATCH:-$REPO_ROOT/.scratch}/seekui}"
OUTPUT_DIR="$SEEKUI_WORK/outputs"
DATA_DIR="$SEEKUI_WORK/data"
MODEL_NAME="${MODEL_NAME:-SeekUI}"
CASE_LIMIT="${CASE_LIMIT:-40}"
OUT_DIR="${OUT_DIR:-$OUTPUT_DIR/stopping_cases/${MODEL_NAME}_present_only}"

module load miniconda3/25.9.1
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate seekui

json_has_examples() {
  python - "$1" <<'PY'
import json
import sys
path = sys.argv[1]
with open(path, "r", encoding="utf-8") as f:
    data = json.load(f)
raise SystemExit(0 if len(data) > 0 else 1)
PY
}

python scripts_research/mine_stopping_cases.py \
  --original "$OUTPUT_DIR/present_absent_predictions_${MODEL_NAME}.json" \
  --adjusted "$OUTPUT_DIR/present_absent_predictions_${MODEL_NAME}_cognitive_stop_present_only.json" \
  --evidence "$OUTPUT_DIR/stopping_evidence/${MODEL_NAME}_stopping_evidence.csv" \
  --out-dir "$OUT_DIR" \
  --limit "$CASE_LIMIT"

for case_type in \
  corrected_absent_false_present \
  new_present_false_absent \
  corrected_present_false_absent \
  kept_absent_false_present; do
  json_path="$OUT_DIR/${case_type}.json"
  if [[ -s "$json_path" ]] && json_has_examples "$json_path"; then
    viz_dir="$OUT_DIR/visualizations/$case_type"
    python scripts_research/visualize_scanpaths.py \
      --json "$json_path" \
      --image-root "$DATA_DIR" \
      --out-dir "$viz_dir" \
      --limit "$CASE_LIMIT"

    python scripts_research/make_contact_sheet.py \
      --input-dir "$viz_dir" \
      --output "$OUT_DIR/visualizations/${case_type}_contact_sheet.jpg" \
      --limit "$CASE_LIMIT" \
      --cols "${CONTACT_SHEET_COLS:-5}"

    cp "$OUT_DIR/visualizations/${case_type}_contact_sheet.jpg" \
      "$OUT_DIR/visualizations/${MODEL_NAME}_${case_type}_contact_sheet.jpg"
  else
    echo "Skipping empty case set: $json_path"
  fi
done

EXPORT_DIR="$OUT_DIR/contact_sheet_export"
rm -rf "$EXPORT_DIR"
mkdir -p "$EXPORT_DIR"
find "$OUT_DIR/visualizations" -maxdepth 1 -type f -name '*contact_sheet.jpg' -exec cp {} "$EXPORT_DIR/" \;

PACKAGE="$OUTPUT_DIR/stopping_cases/${MODEL_NAME}_present_only_contact_sheets.tgz"
tar -C "$OUT_DIR" -czf "$PACKAGE" \
  stopping_cases_summary.md \
  stopping_cases_index.csv \
  contact_sheet_export

echo "Stopping case summary: $OUT_DIR/stopping_cases_summary.md"
echo "Prefixed contact sheets: $OUT_DIR/visualizations/${MODEL_NAME}_*_contact_sheet.jpg"
echo "Download package: $PACKAGE"
