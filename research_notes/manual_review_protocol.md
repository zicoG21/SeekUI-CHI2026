# Manual Review Protocol

This protocol standardizes how to fill the review CSV files generated under:

```text
$SEEKUI_WORK/outputs/review_cases/
```

The goal is not to make the synthetic benchmarks perfect. The goal is to quantify label/query/prediction quality well enough to decide whether the current follow-up direction is credible.

## Review Sheets

Expected sheets:

- `absent_label_review.csv`
- `semantic_query_review.csv`
- `prediction_edge_cases_review.csv`

Each sheet may contain some or all of these columns:

- `review_target_visible`
- `review_query_valid`
- `review_prediction_reasonable`
- `review_error_category`
- `review_notes`

Use `yes` / `no` for the first three review columns. Leave blank only when the item cannot be judged.

## Task 1: Synthetic Absent Label Review

Use this for rows with `review_type=absent_label_check`.

Fill `review_target_visible`:

- `yes`: the requested target is visibly present in the destination GUI, even if the synthetic construction thought it was absent.
- `no`: the requested target is not visibly present.
- blank: the image is missing, unreadable, or too ambiguous.

Fill `review_query_valid`:

- `yes`: the target text/query is understandable as a UI target.
- `no`: the target text is empty, corrupted, too generic, or not a meaningful UI target.

Recommended error categories:

- `absent_label_noise`: target appears to be present despite the absent label.
- `ambiguous_target`: the target could refer to multiple visible elements.
- `invalid_query`: target/query is not meaningful.
- `missing_image`: image cannot be inspected.

## Task 2: Semantic Query Review

Use this for rows with `review_type=semantic_query_check` or `semantic_prediction_check`.

Fill `review_query_valid`:

- `yes`: the semantic or functional query is a reasonable paraphrase/description of the original target.
- `no`: the query changes the task, overgeneralizes, or asks for a different UI element.

Fill `review_target_visible`:

- `yes`: the original target remains visible in the GUI.
- `no`: the original target is not visible or the image is not suitable.

Recommended error categories:

- `wrong_semantic_target`: query points to a different concept than the original target.
- `overbroad_query`: query is plausible but too broad to define one target.
- `invalid_query`: query is ungrammatical or not a useful target description.
- `ambiguous_target`: multiple visible elements match the query.

## Task 3: Prediction Quality Review

Use this for rows with `review_type=prediction_quality_check`, `absent_prediction_check`, or `semantic_prediction_check`.

Fill `review_prediction_reasonable`:

- `yes`: predicted fixations are plausibly directed toward the requested target or toward reasonable search regions.
- `no`: prediction is empty, off-screen, unrelated to the target, or clearly hallucinated.
- blank: cannot judge because image/prediction is missing.

Recommended error categories:

- `forced_choice_hallucination`: model points somewhere despite an absent or invalid target.
- `premature_absent`: model predicts absent when the target is visible.
- `wrong_text_target`: model follows a different text element.
- `wrong_semantic_target`: model follows a semantically related but incorrect element.
- `off_target_scanpath`: model looks around the GUI but misses the target.
- `parsing_failure`: model output could not be parsed reliably.
- `empty_prediction`: no usable points were produced.
- `other`: explain in `review_notes`.

## Minimal Review Batch

A useful first batch is:

- 50 synthetic absent rows.
- 50 semantic non-exact rows.
- 50 prediction edge cases after model outputs exist.

That is enough for a meeting-level estimate of:

- synthetic absent label validity rate,
- semantic query validity rate,
- common prediction failure modes.

## Summarize Filled Sheets

After editing the CSV files:

```bash
python scripts_research/summarize_manual_review.py \
  --input \
    "$SEEKUI_WORK/outputs/review_cases/absent_label_review.csv" \
    "$SEEKUI_WORK/outputs/review_cases/semantic_query_review.csv" \
    "$SEEKUI_WORK/outputs/review_cases/prediction_edge_cases_review.csv" \
  --output-json "$SEEKUI_WORK/outputs/review_cases/manual_review_summary.json" \
  --output-md "$SEEKUI_WORK/outputs/review_cases/manual_review_summary.md"
```

Then refresh the full report:

```bash
sbatch scripts_utah/summarize_research_outputs.slurm
```
