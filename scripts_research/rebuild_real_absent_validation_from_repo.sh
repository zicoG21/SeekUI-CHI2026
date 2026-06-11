#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="${REPO_ROOT:-$(pwd)}"
cd "$REPO_ROOT"

SEEKUI_WORK="${SEEKUI_WORK:-${SCRATCH:-$REPO_ROOT/.scratch}/seekui}"
DATA_DIR="${SEEKUI_DATA_DIR:-$SEEKUI_WORK/data}"
OUT_DIR="${OUT_DIR:-$SEEKUI_WORK/outputs/real_absent_validation}"
REVIEW_SOURCE="${REVIEW_SOURCE:-$REPO_ROOT/research_notes/real_absent_validation/real_absent_rows_to_fill_filled_by_codex.csv}"

mkdir -p "$OUT_DIR/review_package"

python scripts_research/export_real_absent_validation_sheet.py \
  --scanpath "$DATA_DIR/scanpath_train_explanation.json" \
  --target2text "$DATA_DIR/target2text.json" \
  --output-csv "$OUT_DIR/real_absent_validation_starter.csv" \
  --output-md "$OUT_DIR/real_absent_validation_starter.md"

python scripts_research/prefill_real_absent_validation_sheet.py \
  --input-csv "$OUT_DIR/real_absent_validation_starter.csv" \
  --output-csv "$OUT_DIR/real_absent_validation_prefilled.csv" \
  --output-md "$OUT_DIR/real_absent_validation_prefilled.md"

cp "$REVIEW_SOURCE" "$OUT_DIR/review_package/real_absent_rows_to_fill.csv"

python scripts_research/merge_real_absent_review.py \
  --base-csv "$OUT_DIR/real_absent_validation_prefilled.csv" \
  --review-csv "$OUT_DIR/review_package/real_absent_rows_to_fill.csv" \
  --output-csv "$OUT_DIR/real_absent_validation_filled.csv" \
  --summary-md "$OUT_DIR/real_absent_validation_merge.md"

python scripts_research/prepare_real_absent_validation_dataset.py \
  --sheet "$OUT_DIR/real_absent_validation_filled.csv" \
  --scanpath "$DATA_DIR/scanpath_train_explanation.json" \
  --output-json "$OUT_DIR/real_absent_validation_eval.json" \
  --excluded-csv "$OUT_DIR/real_absent_validation_excluded.csv" \
  --summary-md "$OUT_DIR/real_absent_validation_prep.md"

echo "Real absent validation rebuilt from repo artifact."
echo "Eval JSON: $OUT_DIR/real_absent_validation_eval.json"
cat "$OUT_DIR/real_absent_validation_prep.md"
