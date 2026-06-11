#!/usr/bin/env bash
#SBATCH --job-name=seekui-ui-cases
#SBATCH --account=notchpeak-shared-short
#SBATCH --partition=notchpeak-shared-short
#SBATCH --cpus-per-task=4
#SBATCH --mem=12G
#SBATCH --time=00:20:00
#SBATCH --output=seekui-ui-cases-%j.out

set -euo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:-$(pwd)}"
cd "$REPO_ROOT"

SEEKUI_WORK="${SEEKUI_WORK:-${SCRATCH:-$REPO_ROOT/.scratch}/seekui}"
DATA_DIR="$SEEKUI_WORK/data"
OUTPUT_DIR="$SEEKUI_WORK/outputs"
MODEL_NAME="${MODEL_NAME:-SeekUI}"
ADJUSTED_VARIANT="${ADJUSTED_VARIANT:-combined_and_present_only_best_f1}"
CASE_LIMIT="${CASE_LIMIT:-12}"
OUT_DIR="${OUT_DIR:-$OUTPUT_DIR/gui_evaluation_case_study/${MODEL_NAME}_${ADJUSTED_VARIANT}}"

module load miniconda3/25.9.1
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate seekui

prompt="$OUTPUT_DIR/present_absent_predictions_${MODEL_NAME}.json"
adjusted="$OUTPUT_DIR/present_absent_predictions_${MODEL_NAME}_${ADJUSTED_VARIANT}.json"

python scripts_research/export_gui_evaluation_case_study.py \
  --prompt-predictions "$prompt" \
  --adjusted-predictions "$adjusted" \
  --out-dir "$OUT_DIR" \
  --limit "$CASE_LIMIT"

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

for case_type in \
  forced_choice_overestimate_corrected \
  forced_choice_overestimate_kept \
  conservative_cost_present_rejected; do
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
      --cols "${CONTACT_SHEET_COLS:-4}"
  else
    echo "Skipping empty case set: $json_path"
  fi
done

package="$OUTPUT_DIR/gui_evaluation_case_study/${MODEL_NAME}_${ADJUSTED_VARIANT}_case_study.tgz"
tar -C "$OUT_DIR" -czf "$package" \
  case_study_summary.md \
  case_study_index.csv \
  case_study_manifest.json \
  visualizations 2>/dev/null || \
tar -C "$OUT_DIR" -czf "$package" \
  case_study_summary.md \
  case_study_index.csv \
  case_study_manifest.json

echo "GUI evaluation case-study summary: $OUT_DIR/case_study_summary.md"
cat "$OUT_DIR/case_study_summary.md"
echo "Package: $package"
