# Research Scripts

These scripts support follow-up experiments that do not require changing or retraining SeekUI first.

For a concise separation between completed local/offline preparation and CHPC-output-dependent tasks, see:

```text
research_notes/offline_completion_audit.md
```

For manual review annotation rules, see:

```text
research_notes/manual_review_protocol.md
```

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

Or submit summary generation as a CPU job:

```bash
sbatch scripts_utah/summarize_research_outputs.slurm
```

This also writes CSV tables under:

```text
$SEEKUI_WORK/outputs/research_summary_tables/
```

Submit the full follow-up pipeline with SLURM dependencies:

```bash
RUN_SFT=1 bash scripts_utah/submit_followup_experiments.sh
```

Check which follow-up artifacts already exist and what command should run next:

```bash
python scripts_research/check_followup_status.py \
  --work-dir "$SEEKUI_WORK" \
  --output-json "$SEEKUI_WORK/outputs/followup_status.json" \
  --output-md "$SEEKUI_WORK/outputs/followup_status.md"
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

Run the process-style upper-bound baseline:

```bash
python scripts_research/cognitive_stopping_process.py \
  --reference "$SEEKUI_WORK/data/scanpath_train_explanation.json" \
  --eval "$SEEKUI_WORK/data/present_absent_synthetic_2724.json" \
  --target2text "$SEEKUI_WORK/data/target2text.json" \
  --image-root "$SEEKUI_WORK/data" \
  --out-dir "$SEEKUI_WORK/outputs/cognitive_process_stopping"
```

Analyze whether actual model predictions show enough evidence to justify present/absent stopping decisions:

```bash
python scripts_research/analyze_prediction_stopping_evidence.py \
  --reference "$SEEKUI_WORK/data/scanpath_train_explanation.json" \
  --target2text "$SEEKUI_WORK/data/target2text.json" \
  --image-root "$SEEKUI_WORK/data" \
  --out-dir "$SEEKUI_WORK/outputs/stopping_evidence" \
  --prediction SeekUI="$SEEKUI_WORK/outputs/present_absent_predictions_SeekUI.json" \
  --prediction SeekUI_sft="$SEEKUI_WORK/outputs/present_absent_predictions_SeekUI_sft.json"
```

Or submit it as a CPU batch job:

```bash
sbatch scripts_utah/analyze_stopping_evidence.slurm
```

Key outputs:

```text
$SEEKUI_WORK/outputs/stopping_evidence/stopping_evidence_summary.md
$SEEKUI_WORK/outputs/stopping_evidence/SeekUI_stopping_evidence.csv
$SEEKUI_WORK/outputs/stopping_evidence/SeekUI_stopping_evidence_threshold_sweep.csv
$SEEKUI_WORK/outputs/stopping_evidence/SeekUI_sft_stopping_evidence.csv
$SEEKUI_WORK/outputs/stopping_evidence/SeekUI_sft_stopping_evidence_threshold_sweep.csv
```

Apply the resulting post-hoc cognitive stopping layer:

```bash
sbatch scripts_utah/apply_cognitive_stopping.slurm
```

This writes:

```text
$SEEKUI_WORK/outputs/present_absent_predictions_SeekUI_cognitive_stop.json
$SEEKUI_WORK/outputs/present_absent_predictions_SeekUI_cognitive_stop_status_eval.json
$SEEKUI_WORK/outputs/present_absent_predictions_SeekUI_sft_cognitive_stop.json
$SEEKUI_WORK/outputs/present_absent_predictions_SeekUI_sft_cognitive_stop_status_eval.json
$SEEKUI_WORK/outputs/present_absent_predictions_SeekUI_cognitive_stop_present_only.json
$SEEKUI_WORK/outputs/present_absent_predictions_SeekUI_cognitive_stop_present_only_status_eval.json
```

Default thresholds come from the completed evidence sweep:

```text
SeekUI:     0.20
SeekUI-SFT: 0.10
```

The default batch job writes both an aggressive `override` variant and a conservative `present_only` variant. The conservative variant only changes low-evidence `present` predictions to `absent`; it does not turn original `absent` predictions back into `present`.

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

Compare two prediction files on matched examples:

```bash
python scripts_research/compare_predictions.py \
  --a "$SEEKUI_WORK/outputs/semantic_query_predictions_SeekUI_1362_v2.json" \
  --b "$SEEKUI_WORK/outputs/semantic_query_predictions_SeekUI_sft_1362_v2.json" \
  --label-a SeekUI \
  --label-b SeekUI_sft \
  --out-csv "$SEEKUI_WORK/outputs/comparisons/semantic_query_SeekUI_vs_SeekUI_sft.csv"
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

Generate qualitative review artifacts automatically from all prediction files that already exist:

```bash
python scripts_research/generate_review_artifacts.py \
  --work-dir "$SEEKUI_WORK" \
  --limit 1362 \
  --variants-per-example 2 \
  --review-limit 50 \
  --out-dir "$SEEKUI_WORK/outputs/review_cases"
```

This writes per-condition sample JSON/CSV files and, when any prediction files exist:

```text
$SEEKUI_WORK/outputs/review_cases/prediction_edge_cases_review.csv
$SEEKUI_WORK/outputs/review_cases/review_artifacts_manifest.json
```

## 9. Export Manual Review Sheets

For checking whether synthetic absent labels are truly absent:

```bash
python scripts_research/export_manual_review_sheet.py \
  --input "$SEEKUI_WORK/data/present_absent_synthetic_2724.json" \
  --mode absent \
  --limit 100 \
  --output "$SEEKUI_WORK/outputs/review_cases/absent_label_review.csv"
```

For checking whether semantic query variants are valid:

```bash
python scripts_research/export_manual_review_sheet.py \
  --input "$SEEKUI_WORK/data/semantic_queries_1362_v2.json" \
  --mode semantic_non_exact \
  --limit 100 \
  --output "$SEEKUI_WORK/outputs/review_cases/semantic_query_review.csv"
```

Suggested `review_error_category` values:

```text
absent_label_noise
forced_choice_hallucination
premature_absent
wrong_text_target
wrong_semantic_target
off_target_scanpath
parsing_failure
other
```

After filling the review columns, summarize the sheets:

```bash
python scripts_research/summarize_manual_review.py \
  --input \
    "$SEEKUI_WORK/outputs/review_cases/absent_label_review.csv" \
    "$SEEKUI_WORK/outputs/review_cases/semantic_query_review.csv" \
  --output-json "$SEEKUI_WORK/outputs/review_cases/manual_review_summary.json" \
  --output-md "$SEEKUI_WORK/outputs/review_cases/manual_review_summary.md"
```
