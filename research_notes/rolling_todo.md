# SeekUI Rolling TODO

Last updated: 2026-06-11

This is the short working TODO. Update every 1-2 days; keep only active or recently completed items here. Longer background notes stay in `RESEARCH_TODO.md` and `research_notes/current_progress_summary.md`.

## Active Queue

| Priority | Item | Status | Next action |
|---:|---|---|---|
| P0 | Finish v3 semantic-query jobs | completed | v3 association-first summaries are in `rolling_results.md`; run split eval if scanpath metrics are needed |
| P0 | GL VLM prompt ablation | completed | OCR-aware VLM is strongest full-benchmark classifier so far; run hard-case overlap with combined AND |
| P0 | Evidence-aware VLM verifier | completed for SeekUI | Evidence-aware VLM is current strongest practical method; run SFT version as secondary check |
| P0 | VLM/evidence ablation table | completed | Evidence-aware VLM ranks first in `$SEEKUI_WORK/outputs/paper_tables/vlm_ablation_table.md` |
| P0 | Evidence-aware hard-case comparison | completed | Evidence-aware VLM vs combined AND summary is recorded in `rolling_results.md`; export compact comparison table after pulling latest code |
| P0 | Paper checkpoint summary | code ready | Run `sbatch scripts_utah/export_paper_checkpoint.slurm`, or use `bash scripts_utah/submit_post_evidence_analysis.sh` to refresh it after summary |
| P0 | VLM direct presence baseline | completed on CHPC | Direct VLM full: absent F1 0.8386, accuracy 0.8510; filtered F1 0.8494, accuracy 0.8706 |
| P0 | Combined cognitive + OCR verifier | completed | Best `and` combination beats cognitive stopping; keep as current strongest non-oracle method |
| P0 | Add dev/test validation for combined verifier | completed | Random and image splits both show positive held-out F1/accuracy deltas |
| P0 | Analyze combined dev/test results | completed | Combined AND is now strongest non-oracle result; keep random/image CI tables in `rolling_results.md` |
| P0 | Mine combined-verifier cases | completed | Contact-sheet exports are available for SeekUI and SeekUI-SFT combined best-F1 variants |
| P0 | Synthetic absent benchmark sanity check | completed | Annotation conflicts are low; random split leaks images; use image split as cleaner held-out result |
| P0 | Analyze combined contact sheets | completed | Combined-sheet visual taxonomy is in `research_notes/contact_sheet_visual_taxonomy.md` |
| P0 | Contact-sheet visual review sheet | code ready | Run `sbatch scripts_utah/export_contact_sheet_review.slurm`; fill CSV, then `sbatch scripts_utah/summarize_contact_sheet_review.slurm` |
| P0 | Export main result table | completed | Image split table is paper-ready and stored under `$SEEKUI_WORK/outputs/paper_tables` |
| P0 | Refresh filtered sensitivity analysis | completed | SFT best-F1 adjusted output is included; combined AND remains strongest under filtering |
| P0 | Paper table cleanup | completed | Summary/export scripts now hide pilot-only `*_n200` rows by default; use `--include-pilots` for provenance |
| P1 | OCR verifier diagnosis | completed | Optional rerun after pulling latest polish so OCR outcomes are non-overlapping |
| P1 | Combined verifier error taxonomy | completed | Rerun after pulling latest fix so summary separates total cases from selected tagged rows |
| P1 | Behavioral search metrics | completed | Optional rerun after pulling latest polish so zero-N target-distance rows display `n/a` |
| P1 | Non-text / image-cue analysis | partial | Paper checkpoint now includes image-cue comparison summary when comparison JSON exists; next inspect image-cue failure cases if needed |
| P1 | Simple VLM/OCR verifier baselines | completed | Direct/conservative/OCR-aware/search-behavior VLM baselines are recorded in `rolling_results.md` |
| P1 | VLM hard-case analysis | completed | Direct and OCR-aware VLM hard-case overlap summaries are recorded in `rolling_results.md` |
| P1 | Evidence-aware filtered sensitivity | code ready | Run `sbatch scripts_utah/evaluate_evidence_filtered_status.slurm` |
| P1 | Great Lakes setup | active backup | Data/models/prep are ready; current GL jobs use `jaabell0` on `spgpu` A40 |
| P2 | Better non-oracle verifier | pending | Add OCR + icon/UI proposal or VLM verifier if OCR-only underperforms |
| P2 | Candidate-crop VLM verifier | pending | Test crop-level yes/no verifier only after full VLM prompt ablations finish |
| P2 | Multi-sample scanpath uncertainty | pending | Sample K scanpaths per target to measure endpoint variance and agreement if extra A40 capacity remains |
| P2 | Small real/manual absent validation | starter + safe-prefill code ready | Prefill present rows, fill/review absent rows, then run prepare with `SHEET=$SEEKUI_WORK/outputs/real_absent_validation/real_absent_validation_prefilled.csv` |

## Commands To Run Next

```bash
cd ~/projects/SeekUI-CHI2026
git pull
```

Refresh summary tables after new jobs finish:

```bash
python scripts_research/summarize_research_outputs.py \
  --work-dir "$SEEKUI_WORK" \
  --output "$SEEKUI_WORK/outputs/research_summary.md" \
  --tables-dir "$SEEKUI_WORK/outputs/research_summary_tables"

cat "$SEEKUI_WORK/outputs/research_summary_tables/absent_status_core.csv"
```

Check all original and new follow-up artifacts:

```bash
python scripts_research/check_followup_status.py \
  --work-dir "$SEEKUI_WORK" \
  --output-json "$SEEKUI_WORK/outputs/followup_status.json" \
  --output-md "$SEEKUI_WORK/outputs/followup_status.md"

cat "$SEEKUI_WORK/outputs/followup_status.md"
```

Run post-evidence CPU analysis bundle:

```bash
bash scripts_utah/submit_post_evidence_analysis.sh
```

Refresh validation outputs after new jobs finish:

```bash
sbatch scripts_utah/audit_absent_benchmark.slurm
sbatch scripts_utah/evaluate_filtered_absent_status.slurm
tail -n 120 $(ls -t seekui-combo-cases-*.out | head -1)
find "$SEEKUI_WORK/outputs/combined_cases" \( -name '*contact_sheet.jpg' -o -name '*contact_sheets.tgz' \) -print
```

Run non-semantic analysis jobs:

```bash
sbatch scripts_utah/export_main_result_table.slurm
sbatch scripts_utah/diagnose_ocr_verifier.slurm
sbatch scripts_utah/export_contact_sheet_review.slurm
sbatch scripts_utah/summarize_combined_error_taxonomy.slurm
sbatch scripts_utah/summarize_behavioral_metrics.slurm
```

Run VLM yes/no baseline:

```bash
VLM_LIMIT=200 sbatch scripts_utah/vlm_presence_baseline.slurm
```

Current CHPC direct VLM full baseline is complete. Re-summarize after pulling latest code:

```bash
python scripts_research/summarize_research_outputs.py \
  --work-dir "$SEEKUI_WORK" \
  --output "$SEEKUI_WORK/outputs/research_summary.md" \
  --tables-dir "$SEEKUI_WORK/outputs/research_summary_tables"

cat "$SEEKUI_WORK/outputs/research_summary_tables/absent_status_core.csv"
```

Great Lakes setup path:

```bash
export SEEKUI_WORK=/scratch/engin_root/engin1/$USER/seekui
mkdir -p "$SEEKUI_WORK"/{data,models,outputs,hf_cache}
bash scripts_greatlakes/setup_env.sh
bash scripts_greatlakes/prepare_data.sh
bash scripts_utah/download_models.sh
VLM_LIMIT=200 sbatch scripts_greatlakes/vlm_presence_baseline.slurm
```

Great Lakes VLM prompt ablation, using `jaabell0` A40:

```bash
SBATCH_ACCOUNT=jaabell0 \
SBATCH_PARTITION=spgpu \
SBATCH_GRES=gpu:a40:1 \
VLM_PROMPT_VARIANTS="conservative ocr_aware search_behavior" \
bash scripts_greatlakes/submit_vlm_prompt_ablation.sh
```

Run evidence-aware VLM ablation on CHPC:

```bash
VLM_EVIDENCE_PROMPT_VARIANTS="evidence_aware evidence_conservative evidence_rescue_present" \
bash scripts_utah/submit_vlm_evidence_ablation.sh
```

After VLM/evidence jobs finish, export a compact ablation table:

```bash
sbatch scripts_utah/export_vlm_ablation_table.slurm
cat "$SEEKUI_WORK/outputs/paper_tables/vlm_ablation_table.md"
```

Export direct/OCR-aware/evidence-aware hard-case comparison:

```bash
sbatch scripts_utah/export_vlm_hard_case_comparison.slurm
cat "$SEEKUI_WORK/outputs/vlm_hard_cases/vlm_hard_case_comparison.md"
```

Export a compact paper checkpoint:

```bash
sbatch scripts_utah/export_paper_checkpoint.slurm
cat "$SEEKUI_WORK/outputs/paper_checkpoint/paper_checkpoint.md"
```

Run filtered sensitivity for evidence-aware VLM:

```bash
sbatch scripts_utah/evaluate_evidence_filtered_status.slurm
cat "$SEEKUI_WORK/outputs/vlm_evidence_predictions_SeekUI_vlm_evidence_evidence_aware_filtered_status_eval.csv"
```

Run evidence-aware VLM for SFT as a secondary-model GPU check:

```bash
MODEL_NAME=SeekUI_sft \
VLM_EVIDENCE_PROMPT_VARIANTS="evidence_aware" \
bash scripts_utah/submit_vlm_evidence_ablation.sh
```

Generate a starter CSV for small realistic absent validation:

```bash
sbatch scripts_utah/export_real_absent_validation_sheet.slurm
cat "$SEEKUI_WORK/outputs/real_absent_validation/real_absent_validation_starter.md"
```

Prefill safe fields before manual review:

```bash
sbatch scripts_utah/prefill_real_absent_validation_sheet.slurm
cat "$SEEKUI_WORK/outputs/real_absent_validation/real_absent_validation_prefilled.md"
```

After filling the starter CSV, prepare model/eval JSON:

```bash
SHEET="$SEEKUI_WORK/outputs/real_absent_validation/real_absent_validation_prefilled.csv" \
sbatch scripts_utah/prepare_real_absent_validation_dataset.slurm
cat "$SEEKUI_WORK/outputs/real_absent_validation/real_absent_validation_prep.md"
```

Then run OCR-aware VLM on the filled realistic validation set:

```bash
INPUT_JSON="$SEEKUI_WORK/outputs/real_absent_validation/real_absent_validation_eval.json" \
MODEL_LABEL=SeekUI_vlm_presence_real_absent_ocr_aware \
VLM_PROMPT_VARIANT=ocr_aware \
sbatch scripts_utah/vlm_presence_baseline.slurm
```

Run the same evidence-aware VLM ablation on Great Lakes with `jaabell0`:

```bash
SBATCH_ACCOUNT=jaabell0 \
SBATCH_PARTITION=spgpu \
SBATCH_GRES=gpu:a40:1 \
SBATCH_CPUS_PER_TASK=4 \
SBATCH_MEM=40G \
VLM_EVIDENCE_PROMPT_VARIANTS="evidence_aware evidence_conservative evidence_rescue_present" \
bash scripts_greatlakes/submit_vlm_evidence_ablation.sh
```

Great Lakes ablation table:

```bash
SBATCH_ACCOUNT=jaabell0 \
SBATCH_PARTITION=standard \
sbatch scripts_greatlakes/export_vlm_ablation_table.slurm
```

Queue view with account:

```bash
squeue -u $USER -o "%.18i %.18a %.14P %.28j %.8T %.10M %.12l %.20b %.30R"
```

After GL jobs finish:

```bash
find "$SEEKUI_WORK/outputs" -maxdepth 1 \
  -name 'vlm_presence_predictions_SeekUI_vlm_presence_*_status_eval.json' \
  -print -exec cat {} \;
```

Export VLM-vs-combined hard-case lists after a VLM output is available:

```bash
VLM_LABEL=SeekUI_vlm_presence sbatch scripts_utah/export_vlm_hard_cases.slurm
```

If the short partition is unavailable, run the same analysis directly:

```bash
python scripts_research/export_vlm_hard_cases.py \
  --combined-predictions "$SEEKUI_WORK/outputs/present_absent_predictions_SeekUI_combined_and_present_only_best_f1.json" \
  --vlm-predictions "$SEEKUI_WORK/outputs/vlm_presence_predictions_SeekUI_vlm_presence.json" \
  --combined-case-index "$SEEKUI_WORK/outputs/combined_cases/SeekUI_and_present_only_best_f1/stopping_cases_index.csv" \
  --out-dir "$SEEKUI_WORK/outputs/vlm_hard_cases/SeekUI_vlm_presence_vs_SeekUI_combined_and" \
  --limit-per-type 100

python scripts_research/summarize_vlm_hard_cases.py \
  --manifest "$SEEKUI_WORK/outputs/vlm_hard_cases/SeekUI_vlm_presence_vs_SeekUI_combined_and/manifest.json" \
  --output-json "$SEEKUI_WORK/outputs/vlm_hard_cases/SeekUI_vlm_presence_vs_SeekUI_combined_and/summary.json" \
  --output-csv "$SEEKUI_WORK/outputs/vlm_hard_cases/SeekUI_vlm_presence_vs_SeekUI_combined_and/summary.csv" \
  --output-md "$SEEKUI_WORK/outputs/vlm_hard_cases/SeekUI_vlm_presence_vs_SeekUI_combined_and/summary.md"
```

Download combined contact sheets locally:

```bash
mkdir -p ~/HCI_Research/seekui_combined_cases
scp 'u6076267@notchpeak.chpc.utah.edu:/scratch/general/vast/u6076267/seekui/outputs/combined_cases/*_best_f1_contact_sheets.tgz' \
  ~/HCI_Research/seekui_combined_cases/
```

## Recently Completed

- Reproduced base SeekUI and SeekUI-SFT scanpath inference/evaluation.
- Built VSGUI data audit and verified local image coverage.
- Built synthetic present/absent benchmark: 1362 present + 1362 absent.
- Ran prompt-only present/absent predictions for SeekUI and SeekUI-SFT.
- Added prediction-path evidence analysis.
- Added cognitive stopping postprocessor and dev/test validation.
- Generated stopping case visualizations/contact sheets.
- Added oracle candidate verifier as diagnostic upper bound.
- Added OCR candidate verifier as a non-oracle text-only baseline.
- Added combined cognitive + OCR verifier code.
- Ran combined cognitive + OCR verifier; `AND` improves over cognitive stopping.
- Ran combined dev/test validation; `AND` improves held-out absent F1 and accuracy on random and image splits.
- Ran synthetic absent sanity audit; random split leaks images, image split is cleaner, OCR leak rate is 16.5%.
- Ran filtered sensitivity analysis; combined AND remains strongest after excluding annotation-conflict and OCR-leak absent examples.
- Ran combined-verifier case mining for SeekUI and SeekUI-SFT; contact-sheet exports are packaged on CHPC.
- Refreshed filtered sensitivity after combined case mining; SFT best-F1 adjusted output is now included.
- Added code for combined-verifier heuristic taxonomy and behavioral scanpath metrics.
- Ran combined taxonomy and behavioral metrics; patched summaries to reduce ambiguity in selected-case counts and target-distance validity.
- Added code for a paper-ready main result table and OCR verifier diagnosis.
- Ran main result table and OCR diagnosis; main table is ready, OCR diagnosis supports OCR-as-guard interpretation.
- Added code for VLM yes/no presence baseline and contact-sheet visual review artifacts.
- Added Great Lakes setup/data-prep/VLM scripts with `engin1` defaults.
- Reran taxonomy/behavioral summaries; taxonomy now reports full mined counts and selected tagged rows, behavioral metrics now report target-distance valid N.
- Ran CHPC direct VLM yes/no full baseline: absent F1 0.8386, accuracy 0.8510; filtered F1 0.8494, accuracy 0.8706.
- Added VLM prompt variants (`direct`, `conservative`, `ocr_aware`, `search_behavior`) and Great Lakes submission helper.
- Added summary support for VLM presence baselines so `absent_status_core.csv` includes full VLM results.
- Hid pilot-only `*_n200` rows from default research tables while preserving an `--include-pilots` option.
- Reviewed stopping and combined contact sheets; visual taxonomy and CSV mapping are in `research_notes/contact_sheet_visual_taxonomy.md`.
- Added a one-page paper skeleton, paper asset checklist, VLM prompt-ablation template, manual validation protocol, and VLM hard-case export script.
- Completed GL VLM prompt ablation: OCR-aware VLM reaches absent F1 0.8939 and accuracy 0.8924.
- Completed v3 semantic association-first summaries; association prompts have much higher predicted-absent rates.
- Completed direct and OCR-aware VLM hard-case overlap analysis; results support VLM/combined complementarity.

## Decision Log

- Main research path is target-absent UI search with cognitive stopping.
- Oracle candidate verifier is an upper bound, not a deployable method.
- OCR-only verifier is useful as ablation, but currently too aggressive.
- Combined `AND` works better than either cognitive-only or OCR-only; `OR` is too aggressive or redundant.
- Combined `AND` holds up under dev/test threshold selection.
- Image split should be the main held-out evaluation because random split shares many images and image-target pairs.
- Filtered sensitivity supports the main combined-AND conclusion.
- Next practical question: what error taxonomy emerges from the combined-AND contact sheets?
- Direct VLM yes/no underperforms combined AND, but OCR-aware VLM surpasses combined AND on full-benchmark F1/accuracy; combined AND remains more interpretable and has higher absent recall.
