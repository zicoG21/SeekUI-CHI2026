# Research Scripts

These scripts support follow-up experiments that do not require changing or retraining SeekUI first.

## 0. Run All Offline Prep

```bash
bash scripts_research/run_offline_research_prep.sh
```

Or submit it as a CPU batch job:

```bash
sbatch scripts_utah/offline_research_prep.slurm
```

Generate a rolling Markdown summary from whatever outputs exist:

```bash
python scripts_research/summarize_research_outputs.py \
  --work-dir "$SEEKUI_WORK" \
  --output "$SEEKUI_WORK/outputs/research_summary.md"
```

This also writes CSV tables under:

```text
$SEEKUI_WORK/outputs/research_summary_tables/
```

## 1. Audit Current Data

```bash
python scripts_research/audit_vsgui.py \
  --scanpath "$SEEKUI_WORK/data/scanpath_train_explanation.json" \
  --target2text "$SEEKUI_WORK/data/target2text.json" \
  --image-root "$SEEKUI_WORK/data" \
  --out-dir "$SEEKUI_WORK/outputs/data_audit"
```

## 2. Build Synthetic Target-Absent Data

```bash
python scripts_research/build_absent_dataset.py \
  --scanpath "$SEEKUI_WORK/data/scanpath_train_explanation.json" \
  --target2text "$SEEKUI_WORK/data/target2text.json" \
  --output "$SEEKUI_WORK/data/absent_synthetic_1362.json" \
  --mixed-output "$SEEKUI_WORK/data/present_absent_synthetic_2724.json" \
  --limit 1362 \
  --seed 42
```

Validate it:

```bash
python scripts_research/validate_absent_dataset.py \
  --reference "$SEEKUI_WORK/data/scanpath_train_explanation.json" \
  --dataset "$SEEKUI_WORK/data/present_absent_synthetic_2724.json" \
  --target2text "$SEEKUI_WORK/data/target2text.json" \
  --output "$SEEKUI_WORK/outputs/absent_validation.json" \
  --fail-on-conflict
```

## 3. Visualize Examples

```bash
python scripts_research/visualize_scanpaths.py \
  --json "$SEEKUI_WORK/data/present_absent_synthetic_2724.json" \
  --image-root "$SEEKUI_WORK/data" \
  --out-dir "$SEEKUI_WORK/outputs/visualizations/absent_examples" \
  --status absent \
  --limit 20
```

For predictions:

```bash
python scripts_research/visualize_scanpaths.py \
  --json "$SEEKUI_WORK/outputs/predictions_SeekUI_1362.json" \
  --image-root "$SEEKUI_WORK/data" \
  --out-dir "$SEEKUI_WORK/outputs/visualizations/seekui_predictions" \
  --limit 20
```

## 4. Evaluate Prompt-Only Absent Predictions

After running `scripts_utah/absent_inference.slurm`:

```bash
python scripts_research/evaluate_absent_status.py \
  --predictions "$SEEKUI_WORK/outputs/present_absent_predictions_SeekUI.json" \
  --output "$SEEKUI_WORK/outputs/present_absent_predictions_SeekUI_status_eval.json"
```

## 5. Run Minimal Cognitive Stopping Baseline

```bash
python scripts_research/cognitive_stopping_baseline.py \
  --reference "$SEEKUI_WORK/data/scanpath_train_explanation.json" \
  --eval "$SEEKUI_WORK/data/present_absent_synthetic_2724.json" \
  --target2text "$SEEKUI_WORK/data/target2text.json" \
  --out-dir "$SEEKUI_WORK/outputs/cognitive_stopping"
```

## 6. Build Image-Cue Target-Crop Benchmark

This creates target crops from existing target bounding boxes. It is a multimodal prototype, not proof that current data has non-text targets.

```bash
python scripts_research/build_target_crop_dataset.py \
  --scanpath "$SEEKUI_WORK/data/scanpath_train_explanation.json" \
  --image-root "$SEEKUI_WORK/data" \
  --output "$SEEKUI_WORK/data/image_cue_1362.json" \
  --crop-dir "$SEEKUI_WORK/data/target_crops" \
  --crop-prefix "target_crops" \
  --limit 1362
```

Run image-cue inference:

```bash
MODEL_NAME=SeekUI \
SUBSET_LIMIT=1362 \
IMAGE_CUE_JSON="$SEEKUI_WORK/data/image_cue_1362.json" \
OUTPUT_PATH="$SEEKUI_WORK/outputs/image_cue_predictions_SeekUI_1362.json" \
sbatch scripts_utah/image_cue_inference.slurm
```

## 7. Build Semantic Query Benchmark

This is a lightweight scaffold for semantic/associative search. It creates query variants from templates and a small handwritten mapping. It is not a replacement for a real associative-search dataset.

```bash
python scripts_research/build_semantic_query_dataset.py \
  --scanpath "$SEEKUI_WORK/data/scanpath_train_explanation.json" \
  --target2text "$SEEKUI_WORK/data/target2text.json" \
  --output "$SEEKUI_WORK/data/semantic_queries_1362_v2.json" \
  --limit 1362 \
  --variants-per-example 2 \
  --seed 42
```

Run semantic-query inference:

```bash
MODEL_NAME=SeekUI \
SEMANTIC_LIMIT=1362 \
VARIANTS_PER_EXAMPLE=2 \
SEMANTIC_JSON="$SEEKUI_WORK/data/semantic_queries_1362_v2.json" \
OUTPUT_PATH="$SEEKUI_WORK/outputs/semantic_query_predictions_SeekUI_1362_v2.json" \
sbatch scripts_utah/semantic_query_inference.slurm
```

Evaluate scanpath metrics separately by query type:

```bash
PREDICTION_FILE="$SEEKUI_WORK/outputs/semantic_query_predictions_SeekUI_1362_v2.json" \
SPLIT_FIELD=query_type \
SPLIT_NAME=semantic_query_SeekUI_query_type \
sbatch scripts_utah/evaluate_prediction_splits.slurm
```

After split evaluation finishes, refresh the summary:

```bash
python scripts_research/summarize_research_outputs.py \
  --work-dir "$SEEKUI_WORK" \
  --output "$SEEKUI_WORK/outputs/research_summary.md"
```

## 8. Sample Qualitative Review Cases

```bash
python scripts_research/sample_review_cases.py \
  --predictions "$SEEKUI_WORK/outputs/semantic_query_predictions_SeekUI_1362_v2.json" \
  --mode semantic_non_exact \
  --limit 50 \
  --output "$SEEKUI_WORK/outputs/review_cases/semantic_non_exact_SeekUI.json"
```

Visualize sampled cases:

```bash
python scripts_research/visualize_scanpaths.py \
  --json "$SEEKUI_WORK/outputs/review_cases/semantic_non_exact_SeekUI.json" \
  --image-root "$SEEKUI_WORK/data" \
  --out-dir "$SEEKUI_WORK/outputs/visualizations/semantic_non_exact_SeekUI" \
  --limit 50
```
