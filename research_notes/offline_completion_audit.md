# Offline Completion Audit

This note separates tasks that have been completed as local/offline preparation from tasks that still require real `$SEEKUI_WORK` outputs on CHPC. It is meant to prevent the follow-up TODO from blurring "tool exists" with "experiment output exists."

## Completed Without Waiting For Long GPU Jobs

### Reproduction and CHPC Workflow

- Utah CHPC setup scripts exist for model/data download, dependency installation, smoke tests, full inference, and evaluation.
- `scripts_utah/reproduce_seekui_and_sft.sh` submits SeekUI and SeekUI-SFT inference/evaluation with SLURM dependencies.
- `scripts_utah/submit_followup_experiments.sh` submits the follow-up pipeline with dependencies.
- `scripts_research/check_followup_status.py` checks which artifacts exist and recommends the next command.

### Data and Benchmark Preparation

- `scripts_research/audit_vsgui.py` audits target modality, bbox validity, missing images, and scanpath statistics.
- `scripts_research/build_absent_dataset.py` constructs synthetic target-absent and mixed present/absent benchmarks.
- `scripts_research/validate_absent_dataset.py` checks synthetic absent conflicts against known target ids/texts.
- `scripts_research/build_target_crop_dataset.py` creates the image-cue target-crop benchmark.
- `scripts_research/build_semantic_query_dataset.py` creates semantic/query-variant examples.
- `scripts_research/run_offline_research_prep.sh` runs the offline prep sequence end to end.

### Baselines and Evaluation Support

- `scripts_research/cognitive_stopping_baseline.py` implements a text-candidate stopping baseline with threshold sweep.
- `scripts_research/evaluate_absent_status.py` evaluates present/absent status predictions.
- `scripts_research/split_predictions.py` plus `scripts_utah/evaluate_prediction_splits.slurm` evaluate metrics by fields such as `query_type`.
- `scripts_research/compare_predictions.py` compares matched SeekUI and SeekUI-SFT prediction files.

### Review, Reporting, and Meeting Materials

- `research_notes/one_page_forced_choice_stopping.md` is the one-page research framing.
- `research_notes/target_absent_cognitive_memo.md` is the longer target-absent/cognitive memo.
- `scripts_research/export_manual_review_sheet.py` exports absent-label, semantic-query, and prediction-review CSV sheets.
- `scripts_research/generate_review_artifacts.py` samples edge cases from available prediction files.
- `scripts_research/summarize_manual_review.py` summarizes filled manual review sheets.
- `research_notes/manual_review_protocol.md` defines how to fill manual review sheets.
- `scripts_research/summarize_research_outputs.py` creates the rolling markdown/json report and CSV tables.
- `scripts_utah/summarize_research_outputs.slurm` runs review artifact generation, manual-review summary, comparisons, follow-up status, and final summary in the correct order.

## Still Requires CHPC Artifacts

These are not blocked by missing code, but they require real files under `$SEEKUI_WORK`:

- Data audit outputs from the full CHPC data directory.
- Synthetic present/absent JSONs and validation report from `run_offline_research_prep.sh`.
- Cognitive stopping sweep outputs.
- Target-crop and semantic-query benchmark JSONs.
- Present/absent prompt-only predictions for SeekUI and SeekUI-SFT.
- Image-cue predictions for SeekUI and SeekUI-SFT.
- Semantic-query predictions and split evaluations.
- SeekUI vs SeekUI-SFT comparison tables.
- Prediction edge-case review artifacts after predictions exist.
- Final `research_summary.md`, `research_summary.json`, and CSV tables from real outputs.
- Filled manual-review sheets and their summary, which require human annotation.

## Recommended Next Commands On CHPC

From the repository root:

```bash
git pull
```

If derived datasets have not yet been generated:

```bash
bash scripts_research/run_offline_research_prep.sh
```

Then submit follow-up GPU/CPU jobs:

```bash
SKIP_PREP=1 RUN_SFT=1 bash scripts_utah/submit_followup_experiments.sh
```

At any point, check current progress:

```bash
python scripts_research/check_followup_status.py \
  --work-dir "$SEEKUI_WORK" \
  --output-json "$SEEKUI_WORK/outputs/followup_status.json" \
  --output-md "$SEEKUI_WORK/outputs/followup_status.md"
```

Refresh the report:

```bash
sbatch scripts_utah/summarize_research_outputs.slurm
```

## Completion Criterion For This Stage

The local/offline preparation stage is complete when:

- all scripts above are present,
- syntax and dry-run checks pass,
- CHPC commands are documented,
- status checking can tell which real artifacts still need to be produced.

The experimental stage is complete only after the real CHPC artifacts listed above exist and `check_followup_status.py` reports the relevant items as `done`.
