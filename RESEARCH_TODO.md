# SeekUI Follow-Up Research TODO

This document turns the current discussion with Prof. Jiang into concrete tasks that can move forward while long reproduction jobs are running.

## Current Foundation

- SeekUI full inference on the released 1362-example JSON has run successfully.
- Overall evaluation has run successfully.
- Utah CHPC batch scripts exist for full inference and evaluation.
- Data and model layout should use `$SEEKUI_WORK`, not the repo directory.
- Local/offline preparation status is summarized in `research_notes/offline_completion_audit.md`.

## Priority Order

1. Target-absent search and stopping.
2. Data audit for target modality and target presence.
3. Cognitive stopping baseline.
4. Non-text / multimodal target search.
5. Associative search, only after a data source is clear.

## Task 1: Data Audit

Goal: determine what can be studied with current VSGUI/SeekUI data.

Run:

```bash
python scripts_research/audit_vsgui.py \
  --scanpath "$SEEKUI_WORK/data/scanpath_train_explanation.json" \
  --target2text "$SEEKUI_WORK/data/target2text.json" \
  --image-root "$SEEKUI_WORK/data" \
  --out-dir "$SEEKUI_WORK/outputs/data_audit"
```

Questions this answers:

- How many examples and unique GUI images are available?
- What target prefixes exist, such as `txt` or non-text prefixes?
- How many target texts are empty?
- Are target boxes inside the image?
- Are any required images missing?
- What is the scanpath length distribution?

Deliverables:

```text
$SEEKUI_WORK/outputs/data_audit/audit_summary.md
$SEEKUI_WORK/outputs/data_audit/audit_summary.json
$SEEKUI_WORK/outputs/data_audit/target_prefix_counts.csv
$SEEKUI_WORK/outputs/data_audit/top_target_texts.csv
```

Run all offline preparation tasks at once:

```bash
bash scripts_research/run_offline_research_prep.sh
```

or:

```bash
sbatch scripts_utah/offline_research_prep.slurm
```

Generate a rolling summary report from available outputs:

```bash
python scripts_research/summarize_research_outputs.py \
  --work-dir "$SEEKUI_WORK" \
  --output "$SEEKUI_WORK/outputs/research_summary.md"
```

This also exports CSV tables to `$SEEKUI_WORK/outputs/research_summary_tables/`.

Check follow-up status and next commands:

```bash
python scripts_research/check_followup_status.py \
  --work-dir "$SEEKUI_WORK" \
  --output-json "$SEEKUI_WORK/outputs/followup_status.json" \
  --output-md "$SEEKUI_WORK/outputs/followup_status.md"
```

Or let SLURM run the whole follow-up pipeline with dependencies:

```bash
RUN_SFT=1 bash scripts_utah/submit_followup_experiments.sh
```

This submits offline prep, present/absent prompt baselines, image-cue baselines, semantic-query baselines, semantic split evaluation, and a final summary job. Use `SKIP_PREP=1` if the derived datasets have already been prepared.

## Task 2: Synthetic Target-Absent Dataset

Goal: create a first absent-target benchmark without collecting new eye-tracking data.

The builder swaps a target cue from one image onto another image where the same target id/text is not annotated.

Run:

```bash
python scripts_research/build_absent_dataset.py \
  --scanpath "$SEEKUI_WORK/data/scanpath_train_explanation.json" \
  --target2text "$SEEKUI_WORK/data/target2text.json" \
  --output "$SEEKUI_WORK/data/absent_synthetic_1362.json" \
  --mixed-output "$SEEKUI_WORK/data/present_absent_synthetic_2724.json" \
  --limit 1362 \
  --seed 42
```

Important caveat: this is a synthetic hard-negative benchmark. It avoids obvious positives from the current annotations, but it does not prove the target is visually absent unless we later audit with OCR/object detection or manual checks.

Validate the synthetic benchmark:

```bash
python scripts_research/validate_absent_dataset.py \
  --reference "$SEEKUI_WORK/data/scanpath_train_explanation.json" \
  --dataset "$SEEKUI_WORK/data/present_absent_synthetic_2724.json" \
  --target2text "$SEEKUI_WORK/data/target2text.json" \
  --output "$SEEKUI_WORK/outputs/absent_validation.json" \
  --fail-on-conflict
```

Run annotation-assisted text-conflict validation for likely false absent labels:

```bash
python scripts_research/validate_absent_text_conflicts.py \
  --reference "$SEEKUI_WORK/data/scanpath_train_explanation.json" \
  --dataset "$SEEKUI_WORK/data/present_absent_synthetic_2724.json" \
  --target2text "$SEEKUI_WORK/data/target2text.json" \
  --out-dir "$SEEKUI_WORK/outputs/absent_text_conflicts"
```

This catches destination images that may contain the target text under a different annotation, including substring cases such as `Search` versus `Search GymShark`.

## Task 3: Prompt-Only Absent Baseline

Goal: test whether SeekUI can refuse a target that is not present without fine-tuning.

Run:

```bash
ABSENT_INPUT="$SEEKUI_WORK/data/absent_synthetic_1362.json" \
MODEL_NAME=SeekUI \
OUTPUT_PATH="$SEEKUI_WORK/outputs/absent_predictions_SeekUI.json" \
sbatch scripts_utah/absent_inference.slurm
```

For a meaningful confusion matrix with both present and absent trials, use the mixed benchmark:

```bash
ABSENT_INPUT="$SEEKUI_WORK/data/present_absent_synthetic_2724.json" \
MODEL_NAME=SeekUI \
OUTPUT_PATH="$SEEKUI_WORK/outputs/present_absent_predictions_SeekUI.json" \
sbatch scripts_utah/absent_inference.slurm
```

Run the SFT checkpoint too:

```bash
ABSENT_INPUT="$SEEKUI_WORK/data/absent_synthetic_1362.json" \
MODEL_NAME=SeekUI_sft \
OUTPUT_PATH="$SEEKUI_WORK/outputs/absent_predictions_SeekUI_sft.json" \
sbatch scripts_utah/absent_inference.slurm
```

The SLURM script automatically evaluates status classification and writes:

```text
$SEEKUI_WORK/outputs/absent_predictions_SeekUI_status_eval.json
$SEEKUI_WORK/outputs/absent_predictions_SeekUI_sft_status_eval.json
```

Metrics:

- present/absent confusion matrix
- accuracy
- absent precision
- absent recall
- absent F1

## Task 4: Cognitive Stopping Baseline

Goal: make the "cognitive model" direction concrete and interpretable.

Minimum baseline:

```text
If no candidate region has target-match score above threshold after searching high-priority regions, stop and output absent.
```

First implementation can use:

- OCR or annotated target texts as candidate text regions.
- String similarity or embedding similarity to target cue.
- A threshold sweep for absent detection.
- Optional visited-region penalty and center/top-left layout prior.

Initial formula:

```text
score(region) =
  target_text_similarity
  + layout_prior
  - visited_penalty
  - saccade_distance_cost
```

Deliverables:

```text
scripts_research/cognitive_stopping_baseline.py
$SEEKUI_WORK/outputs/cognitive_stopping_threshold_sweep.csv
$SEEKUI_WORK/outputs/cognitive_stopping_summary.md
```

Run the minimal text-candidate stopping baseline:

```bash
python scripts_research/cognitive_stopping_baseline.py \
  --reference "$SEEKUI_WORK/data/scanpath_train_explanation.json" \
  --eval "$SEEKUI_WORK/data/present_absent_synthetic_2724.json" \
  --target2text "$SEEKUI_WORK/data/target2text.json" \
  --out-dir "$SEEKUI_WORK/outputs/cognitive_stopping"
```

This first version uses annotated target texts as candidate regions. It is not a final cognitive model, but it gives us a thresholded stopping baseline and a concrete result table.

## Task 6: Stronger Associative Query Benchmark

Goal: separate shallow semantic paraphrases from stronger associative or functional target descriptions.

The current `semantic_queries_1362_v2.json` is useful as a robustness stress test, but many examples are low semantic-distance templates such as `Search -> find the UI element for Search`. For a stronger associative pilot, build a v3 semantic benchmark that prefers handwritten association mappings when available.

Run after the current v2 GPU jobs finish:

```bash
python scripts_research/build_semantic_query_dataset.py \
  --scanpath "$SEEKUI_WORK/data/scanpath_train_explanation.json" \
  --target2text "$SEEKUI_WORK/data/target2text.json" \
  --mapping scripts_research/associative_query_mapping.json \
  --output "$SEEKUI_WORK/data/semantic_queries_1362_v3_assocfirst.json" \
  --variants-per-example 2 \
  --selection-policy association_first \
  --limit 1362 \
  --seed 42
```

This should be reported as a controlled proxy benchmark, not as a native associative-search dataset. The released VSGUI subset still contains text targets only, so the v3 benchmark asks whether the existing model can follow stronger semantic/function cues derived from those text targets.

## Task 4.5: Visualization for Discussion

Create examples for slides and debugging:

```bash
python scripts_research/visualize_scanpaths.py \
  --json "$SEEKUI_WORK/data/present_absent_synthetic_2724.json" \
  --image-root "$SEEKUI_WORK/data" \
  --out-dir "$SEEKUI_WORK/outputs/visualizations/absent_examples" \
  --status absent \
  --limit 20
```

For model predictions:

```bash
python scripts_research/visualize_scanpaths.py \
  --json "$SEEKUI_WORK/outputs/predictions_SeekUI_1362.json" \
  --image-root "$SEEKUI_WORK/data" \
  --out-dir "$SEEKUI_WORK/outputs/visualizations/seekui_predictions" \
  --limit 20
```

## Task 5: Non-Text / Multimodal Target Audit

Goal: determine whether current data has non-text targets or whether we need synthetic/image-cue construction.

Use the data audit target prefix counts:

- If target prefixes are almost all `txt`, current released data cannot directly evaluate non-text targets.
- If icon/image prefixes exist, inspect examples and create a multimodal target-crop benchmark.

Potential first benchmark:

```text
Input: GUI screenshot + target crop image
Output: scanpath
```

This requires either real non-text target trials or careful weak supervision from target boxes.

Implemented prototype: target-crop image cue.

```bash
python scripts_research/build_target_crop_dataset.py \
  --scanpath "$SEEKUI_WORK/data/scanpath_train_explanation.json" \
  --image-root "$SEEKUI_WORK/data" \
  --output "$SEEKUI_WORK/data/image_cue_1362.json" \
  --crop-dir "$SEEKUI_WORK/data/target_crops" \
  --crop-prefix "target_crops" \
  --limit 1362
```

Run a two-image VLM prompt where the first image is the GUI and the second image is the target crop:

```bash
MODEL_NAME=SeekUI \
SUBSET_LIMIT=1362 \
IMAGE_CUE_JSON="$SEEKUI_WORK/data/image_cue_1362.json" \
OUTPUT_PATH="$SEEKUI_WORK/outputs/image_cue_predictions_SeekUI_1362.json" \
sbatch scripts_utah/image_cue_inference.slurm
```

This is useful for checking whether SeekUI/Qwen2.5-VL can use visual target cues, but it is not a substitute for real non-text target trials.

## Task 6: Associative Search

This is intentionally lower priority, but we now have a lightweight semantic-query scaffold.

Examples:

```text
privacy -> lock icon / security settings
checkout -> pay now / cart
travel -> plane / luggage
```

Main blocker: ground truth is subjective without a new dataset or manual annotation protocol.

Implemented scaffold:

```bash
python scripts_research/build_semantic_query_dataset.py \
  --scanpath "$SEEKUI_WORK/data/scanpath_train_explanation.json" \
  --target2text "$SEEKUI_WORK/data/target2text.json" \
  --output "$SEEKUI_WORK/data/semantic_queries_1362_v2.json" \
  --limit 1362 \
  --variants-per-example 2 \
  --seed 42
```

Run:

```bash
MODEL_NAME=SeekUI \
SEMANTIC_LIMIT=1362 \
VARIANTS_PER_EXAMPLE=2 \
SEMANTIC_JSON="$SEEKUI_WORK/data/semantic_queries_1362_v2.json" \
OUTPUT_PATH="$SEEKUI_WORK/outputs/semantic_query_predictions_SeekUI_1362_v2.json" \
sbatch scripts_utah/semantic_query_inference.slurm
```

Run the stronger association-first v3 benchmark:

```bash
MODEL_NAME=SeekUI \
SEMANTIC_LIMIT=1362 \
VARIANTS_PER_EXAMPLE=2 \
SEMANTIC_MAPPING=scripts_research/associative_query_mapping.json \
SEMANTIC_SELECTION_POLICY=association_first \
SEMANTIC_JSON="$SEEKUI_WORK/data/semantic_queries_1362_v3_assocfirst.json" \
OUTPUT_PATH="$SEEKUI_WORK/outputs/semantic_query_predictions_SeekUI_1362_v3_assocfirst.json" \
sbatch scripts_utah/semantic_query_inference.slurm
```

Run the SFT checkpoint too:

```bash
MODEL_NAME=SeekUI_sft \
SEMANTIC_LIMIT=1362 \
VARIANTS_PER_EXAMPLE=2 \
SEMANTIC_MAPPING=scripts_research/associative_query_mapping.json \
SEMANTIC_SELECTION_POLICY=association_first \
SEMANTIC_JSON="$SEEKUI_WORK/data/semantic_queries_1362_v3_assocfirst.json" \
OUTPUT_PATH="$SEEKUI_WORK/outputs/semantic_query_predictions_SeekUI_sft_1362_v3_assocfirst.json" \
sbatch scripts_utah/semantic_query_inference.slurm
```

This measures robustness to query rephrasing/templates. It should be described as semantic-query robustness, not as a full associative-search benchmark.

Evaluate semantic-query scanpath quality by `query_type`:

```bash
PREDICTION_FILE="$SEEKUI_WORK/outputs/semantic_query_predictions_SeekUI_1362_v2.json" \
SPLIT_FIELD=query_type \
SPLIT_NAME=semantic_query_SeekUI_query_type \
sbatch scripts_utah/evaluate_prediction_splits.slurm
```

Compare SeekUI and SFT outputs on matched examples:

```bash
python scripts_research/compare_predictions.py \
  --a "$SEEKUI_WORK/outputs/predictions_SeekUI_1362.json" \
  --b "$SEEKUI_WORK/outputs/predictions_SeekUI_sft_1362.json" \
  --label-a SeekUI \
  --label-b SeekUI_sft \
  --out-csv "$SEEKUI_WORK/outputs/comparisons/base_SeekUI_vs_SeekUI_sft_1362.csv"
```

## Task 7: Failure Case Mining

Goal: move from aggregate metrics to qualitative examples that explain the failure modes.

Mine high-value failure cases from completed follow-up predictions:

```bash
python scripts_research/mine_failure_cases.py \
  --work-dir "$SEEKUI_WORK" \
  --limit 1362 \
  --variants-per-example 2 \
  --case-limit 30
```

This writes grouped JSON/CSV files under:

```text
$SEEKUI_WORK/outputs/failure_cases
```

Failure groups include:

- absent examples predicted as present,
- present examples predicted as absent,
- image-cue predictions far from the target,
- association queries predicted as absent,
- association queries that land far from the target,
- one-fixation present predictions.

Visualize one mined bundle:

```bash
python scripts_research/visualize_scanpaths.py \
  --json "$SEEKUI_WORK/outputs/failure_cases/SeekUI_present_absent_absent_false_present.json" \
  --image-root "$SEEKUI_WORK/data" \
  --out-dir "$SEEKUI_WORK/outputs/failure_cases/visualizations/SeekUI_absent_false_present" \
  --limit 30
```

## Near-Term Checklist

- [ ] Run data audit and save outputs.
- [ ] Inspect whether any non-text target prefixes exist.
- [ ] Build `absent_synthetic_1362.json` and `present_absent_synthetic_2724.json`.
- [ ] Validate synthetic absent benchmark with `validate_absent_dataset.py`.
- [ ] Run prompt-only absent baseline for SeekUI.
- [ ] Run prompt-only absent baseline for SeekUI-SFT.
- [ ] Compare SeekUI vs SeekUI-SFT absent behavior.
- [ ] Run cognitive stopping threshold sweep on the mixed benchmark.
- [ ] Generate visualization examples for present/absent/prediction cases.
- [ ] Build target-crop image-cue benchmark.
- [ ] Run image-cue inference baseline for SeekUI.
- [ ] Build semantic-query benchmark.
- [ ] Run semantic-query inference baseline for SeekUI.
- [ ] Run split evaluation by `query_type` for semantic-query predictions.
- [ ] Compare SeekUI vs SeekUI-SFT base, absent, image-cue, and semantic outputs.
- [ ] Generate `research_summary.md`.
- [ ] Export CSV tables from summary.
- [ ] Sample qualitative review cases for semantic and absent failures.
- [ ] Generate prediction edge-case review artifacts with `generate_review_artifacts.py`.
- [ ] Mine high-value failure cases with `mine_failure_cases.py`.
- [x] Draft one-page research memo: "SeekUI as forced-choice visual search; target-absent as stopping decision."
- [ ] Export manual review sheets for synthetic absent labels and semantic query validity. Automated in `run_offline_research_prep.sh`.
- [ ] Fill manual review sheets and summarize label/query validity with `summarize_manual_review.py`.
- [ ] Track follow-up completion with `check_followup_status.py`.
- [x] Define manual review annotation protocol.
