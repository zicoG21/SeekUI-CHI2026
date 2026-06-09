#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

SEEKUI_WORK="${SEEKUI_WORK:-${SCRATCH:-$REPO_ROOT/.scratch}/seekui}"
DATA_DIR="${SEEKUI_DATA_DIR:-$SEEKUI_WORK/data}"
LIMIT="${LIMIT:-1362}"

SCANPATH_JSON="$DATA_DIR/scanpath_train_explanation.json"
TARGET2TEXT_JSON="$DATA_DIR/target2text.json"
ABSENT_JSON="$DATA_DIR/absent_synthetic_${LIMIT}.json"
MIXED_JSON="$DATA_DIR/present_absent_synthetic_$((LIMIT * 2)).json"
IMAGE_CUE_JSON="$DATA_DIR/image_cue_${LIMIT}.json"
SEMANTIC_JSON="$DATA_DIR/semantic_queries_${LIMIT}_v${VARIANTS_PER_EXAMPLE:-2}.json"
CROP_DIR="$DATA_DIR/target_crops"
REVIEW_DIR="$SEEKUI_WORK/outputs/review_cases"

python scripts_utah/check_reproduction_inputs.py

python scripts_research/audit_vsgui.py \
  --scanpath "$SCANPATH_JSON" \
  --target2text "$TARGET2TEXT_JSON" \
  --image-root "$DATA_DIR" \
  --out-dir "$SEEKUI_WORK/outputs/data_audit"

python scripts_research/build_absent_dataset.py \
  --scanpath "$SCANPATH_JSON" \
  --target2text "$TARGET2TEXT_JSON" \
  --output "$ABSENT_JSON" \
  --mixed-output "$MIXED_JSON" \
  --limit "$LIMIT" \
  --seed "${SEED:-42}"

python scripts_research/validate_absent_dataset.py \
  --reference "$SCANPATH_JSON" \
  --dataset "$MIXED_JSON" \
  --target2text "$TARGET2TEXT_JSON" \
  --output "$SEEKUI_WORK/outputs/absent_validation.json" \
  --fail-on-conflict

python scripts_research/cognitive_stopping_baseline.py \
  --reference "$SCANPATH_JSON" \
  --eval "$MIXED_JSON" \
  --target2text "$TARGET2TEXT_JSON" \
  --out-dir "$SEEKUI_WORK/outputs/cognitive_stopping"

python scripts_research/build_target_crop_dataset.py \
  --scanpath "$SCANPATH_JSON" \
  --image-root "$DATA_DIR" \
  --output "$IMAGE_CUE_JSON" \
  --crop-dir "$CROP_DIR" \
  --crop-prefix "target_crops" \
  --limit "$LIMIT"

python scripts_research/build_semantic_query_dataset.py \
  --scanpath "$SCANPATH_JSON" \
  --target2text "$TARGET2TEXT_JSON" \
  --output "$SEMANTIC_JSON" \
  --limit "$LIMIT" \
  --variants-per-example "${VARIANTS_PER_EXAMPLE:-2}" \
  --seed "${SEED:-42}"

python scripts_research/export_manual_review_sheet.py \
  --input "$MIXED_JSON" \
  --mode absent \
  --limit "${REVIEW_LIMIT:-100}" \
  --output "$REVIEW_DIR/absent_label_review.csv"

python scripts_research/export_manual_review_sheet.py \
  --input "$SEMANTIC_JSON" \
  --mode semantic_non_exact \
  --limit "${REVIEW_LIMIT:-100}" \
  --output "$REVIEW_DIR/semantic_query_review.csv"

python scripts_research/visualize_scanpaths.py \
  --json "$MIXED_JSON" \
  --image-root "$DATA_DIR" \
  --out-dir "$SEEKUI_WORK/outputs/visualizations/absent_examples" \
  --status absent \
  --limit "${VIZ_LIMIT:-20}" \
  --max-scan "${VIZ_MAX_SCAN:-0}"

python scripts_research/summarize_research_outputs.py \
  --work-dir "$SEEKUI_WORK" \
  --output "$SEEKUI_WORK/outputs/research_summary.md"

cat <<EOF
Offline research prep complete.

Generated:
  $SEEKUI_WORK/outputs/data_audit/audit_summary.md
  $ABSENT_JSON
  $MIXED_JSON
  $SEEKUI_WORK/outputs/absent_validation.json
  $SEEKUI_WORK/outputs/cognitive_stopping/cognitive_stopping_summary.md
  $IMAGE_CUE_JSON
  $CROP_DIR
  $SEMANTIC_JSON
  $REVIEW_DIR/absent_label_review.csv
  $REVIEW_DIR/semantic_query_review.csv
  $SEEKUI_WORK/outputs/visualizations/absent_examples
  $SEEKUI_WORK/outputs/research_summary.md
EOF
