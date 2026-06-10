#!/usr/bin/env bash
#SBATCH --job-name=seekui-combo-cases
#SBATCH --account=notchpeak-shared-short
#SBATCH --partition=notchpeak-shared-short
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=00:30:00
#SBATCH --output=seekui-combo-cases-%j.out

set -euo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:-$(pwd)}"
cd "$REPO_ROOT"

SEEKUI_WORK="${SEEKUI_WORK:-${SCRATCH:-$REPO_ROOT/.scratch}/seekui}"
OUTPUT_DIR="$SEEKUI_WORK/outputs"
DATA_DIR="$SEEKUI_WORK/data"
OCR_CANDIDATES="${OCR_CANDIDATES:-$OUTPUT_DIR/ocr_candidates_tesseract.json}"
CASE_LIMIT="${CASE_LIMIT:-40}"
RULE="${RULE:-and}"
MODE="${MODE:-present_only}"
MIN_OCR_CONF="${MIN_OCR_CONF:-35}"

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

for model in SeekUI SeekUI_sft; do
  if [[ "$model" == "SeekUI" ]]; then
    cog_threshold="${SEEKUI_COGNITIVE_THRESHOLD:-0.20}"
    ocr_threshold="${SEEKUI_OCR_THRESHOLD:-0.60}"
  else
    cog_threshold="${SFT_COGNITIVE_THRESHOLD:-0.05}"
    ocr_threshold="${SFT_OCR_THRESHOLD:-0.55}"
  fi

  adjusted="$OUTPUT_DIR/present_absent_predictions_${model}_combined_${RULE}_${MODE}_best_f1.json"
  metrics="$OUTPUT_DIR/present_absent_predictions_${model}_combined_${RULE}_${MODE}_best_f1_status_eval.json"
  details="$OUTPUT_DIR/present_absent_predictions_${model}_combined_${RULE}_${MODE}_best_f1_details.csv"
  out_dir="$OUTPUT_DIR/combined_cases/${model}_${RULE}_${MODE}_best_f1"

  python scripts_research/apply_combined_verifier.py \
    --predictions "$OUTPUT_DIR/present_absent_predictions_${model}.json" \
    --evidence "$OUTPUT_DIR/stopping_evidence/${model}_stopping_evidence.csv" \
    --ocr-candidates "$OCR_CANDIDATES" \
    --target2text "$DATA_DIR/target2text.json" \
    --rule "$RULE" \
    --mode "$MODE" \
    --cognitive-threshold "$cog_threshold" \
    --ocr-threshold "$ocr_threshold" \
    --min-ocr-conf "$MIN_OCR_CONF" \
    --output "$adjusted" \
    --metrics-output "$metrics" \
    --detail-output "$details"

  python scripts_research/mine_stopping_cases.py \
    --original "$OUTPUT_DIR/present_absent_predictions_${model}.json" \
    --adjusted "$adjusted" \
    --evidence "$OUTPUT_DIR/stopping_evidence/${model}_stopping_evidence.csv" \
    --out-dir "$out_dir" \
    --limit "$CASE_LIMIT"

  for case_type in \
    corrected_absent_false_present \
    new_present_false_absent \
    corrected_present_false_absent \
    kept_absent_false_present; do
    json_path="$out_dir/${case_type}.json"
    if [[ -s "$json_path" ]] && json_has_examples "$json_path"; then
      viz_dir="$out_dir/visualizations/$case_type"
      python scripts_research/visualize_scanpaths.py \
        --json "$json_path" \
        --image-root "$DATA_DIR" \
        --out-dir "$viz_dir" \
        --limit "$CASE_LIMIT"

      python scripts_research/make_contact_sheet.py \
        --input-dir "$viz_dir" \
        --output "$out_dir/visualizations/${case_type}_contact_sheet.jpg" \
        --limit "$CASE_LIMIT" \
        --cols "${CONTACT_SHEET_COLS:-5}"

      cp "$out_dir/visualizations/${case_type}_contact_sheet.jpg" \
        "$out_dir/visualizations/${model}_${RULE}_${case_type}_contact_sheet.jpg"
    else
      echo "Skipping empty case set: $json_path"
    fi
  done

  export_dir="$out_dir/contact_sheet_export"
  rm -rf "$export_dir"
  mkdir -p "$export_dir"
  find "$out_dir/visualizations" -maxdepth 1 -type f -name '*contact_sheet.jpg' -exec cp {} "$export_dir/" \;

  package="$OUTPUT_DIR/combined_cases/${model}_${RULE}_${MODE}_best_f1_contact_sheets.tgz"
  tar -C "$out_dir" -czf "$package" \
    stopping_cases_summary.md \
    stopping_cases_index.csv \
    contact_sheet_export

  echo "Combined case summary: $out_dir/stopping_cases_summary.md"
  echo "Combined case package: $package"
done
