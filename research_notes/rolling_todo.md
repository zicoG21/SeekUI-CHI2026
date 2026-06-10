# SeekUI Rolling TODO

Last updated: 2026-06-10

This is the short working TODO. Update every 1-2 days; keep only active or recently completed items here. Longer background notes stay in `RESEARCH_TODO.md` and `research_notes/current_progress_summary.md`.

## Active Queue

| Priority | Item | Status | Next action |
|---:|---|---|---|
| P0 | Finish v3 semantic-query jobs | running on CHPC | Check `squeue -u $USER`; when done, rerun summary and inspect semantic split tables |
| P0 | GL VLM prompt ablation | running/pending on Great Lakes | Keep only one full job each for `conservative`, `ocr_aware`, and `search_behavior`; compare against CHPC direct VLM and combined AND |
| P0 | VLM direct presence baseline | completed on CHPC | Direct VLM full: absent F1 0.8386, accuracy 0.8510; filtered F1 0.8494, accuracy 0.8706 |
| P0 | Combined cognitive + OCR verifier | completed | Best `and` combination beats cognitive stopping; keep as current strongest non-oracle method |
| P0 | Add dev/test validation for combined verifier | completed | Random and image splits both show positive held-out F1/accuracy deltas |
| P0 | Analyze combined dev/test results | completed | Combined AND is now strongest non-oracle result; keep random/image CI tables in `rolling_results.md` |
| P0 | Mine combined-verifier cases | completed | Contact-sheet exports are available for SeekUI and SeekUI-SFT combined best-F1 variants |
| P0 | Synthetic absent benchmark sanity check | completed | Annotation conflicts are low; random split leaks images; use image split as cleaner held-out result |
| P0 | Analyze combined contact sheets | pending | Preliminary stopping-sheet taxonomy is in `research_notes/contact_sheet_visual_taxonomy.md`; repeat on combined sheets after download |
| P0 | Contact-sheet visual review sheet | code ready | Run `sbatch scripts_utah/export_contact_sheet_review.slurm`; fill CSV, then `sbatch scripts_utah/summarize_contact_sheet_review.slurm` |
| P0 | Export main result table | completed | Image split table is paper-ready and stored under `$SEEKUI_WORK/outputs/paper_tables` |
| P0 | Refresh filtered sensitivity analysis | completed | SFT best-F1 adjusted output is included; combined AND remains strongest under filtering |
| P0 | Paper table cleanup | completed | Summary/export scripts now hide pilot-only `*_n200` rows by default; use `--include-pilots` for provenance |
| P1 | OCR verifier diagnosis | completed | Optional rerun after pulling latest polish so OCR outcomes are non-overlapping |
| P1 | Combined verifier error taxonomy | completed | Rerun after pulling latest fix so summary separates total cases from selected tagged rows |
| P1 | Behavioral search metrics | completed | Optional rerun after pulling latest polish so zero-N target-distance rows display `n/a` |
| P1 | Non-text / image-cue analysis | pending | Compare image-cue metrics and failure cases after v3 jobs settle |
| P1 | Simple VLM/OCR verifier baselines | in progress | CHPC direct VLM is done; GL is running prompt ablations for conservative/OCR-aware/search-behavior prompts |
| P1 | VLM hard-case analysis | pending | After GL ablations finish, run VLM only on combined kept false-present and new false-absent cases if full prompts expose useful differences |
| P1 | Great Lakes setup | active backup | Data/models/prep are ready; current GL jobs use `jaabell0` on `spgpu` A40 |
| P2 | Better non-oracle verifier | pending | Add OCR + icon/UI proposal or VLM verifier if OCR-only underperforms |
| P2 | Candidate-crop VLM verifier | pending | Test crop-level yes/no verifier only after full VLM prompt ablations finish |
| P2 | Multi-sample scanpath uncertainty | pending | Sample K scanpaths per target to measure endpoint variance and agreement if extra A40 capacity remains |

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
- Reviewed available stopping contact sheets and wrote a working visual taxonomy in `research_notes/contact_sheet_visual_taxonomy.md`.

## Decision Log

- Main research path is target-absent UI search with cognitive stopping.
- Oracle candidate verifier is an upper bound, not a deployable method.
- OCR-only verifier is useful as ablation, but currently too aggressive.
- Combined `AND` works better than either cognitive-only or OCR-only; `OR` is too aggressive or redundant.
- Combined `AND` holds up under dev/test threshold selection.
- Image split should be the main held-out evaluation because random split shares many images and image-target pairs.
- Filtered sensitivity supports the main combined-AND conclusion.
- Next practical question: what error taxonomy emerges from the combined-AND contact sheets?
- Direct VLM yes/no is a strong reviewer-risk baseline but does not close the gap to combined AND; GL prompt ablations test whether this is prompt-sensitive.
