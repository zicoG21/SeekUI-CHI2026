# SeekUI Rolling TODO

Last updated: 2026-06-10

This is the short working TODO. Update every 1-2 days; keep only active or recently completed items here. Longer background notes stay in `RESEARCH_TODO.md` and `research_notes/current_progress_summary.md`.

## Active Queue

| Priority | Item | Status | Next action |
|---:|---|---|---|
| P0 | Finish v3 semantic-query jobs | running on CHPC | Check `squeue -u $USER`; when done, rerun summary and inspect semantic split tables |
| P0 | Combined cognitive + OCR verifier | completed | Best `and` combination beats cognitive stopping; keep as current strongest non-oracle method |
| P0 | Add dev/test validation for combined verifier | completed | Random and image splits both show positive held-out F1/accuracy deltas |
| P0 | Analyze combined dev/test results | completed | Combined AND is now strongest non-oracle result; keep random/image CI tables in `rolling_results.md` |
| P0 | Mine combined-verifier cases | running/partial | Check logs and confirm SeekUI-SFT contact sheets/packages were generated |
| P0 | Synthetic absent benchmark sanity check | completed | Annotation conflicts are low; random split leaks images; use image split as cleaner held-out result |
| P0 | Absent benchmark sensitivity analysis | code ready | Run `sbatch scripts_utah/evaluate_filtered_absent_status.slurm` to exclude 4 annotation conflicts and 225 OCR-leak absent examples |
| P1 | OCR verifier diagnosis | partial | Use details CSV to identify why present targets are missed by OCR |
| P1 | Combined verifier error taxonomy | pending | Categorize corrected absent, new false-absent, kept false-present, OCR failures, small/edge targets, and strong distractors |
| P1 | Behavioral search metrics | pending | Compute fixation count, coverage, revisit rate, convergence score, and stopping-confidence curves |
| P1 | Non-text / image-cue analysis | pending | Compare image-cue metrics and failure cases after v3 jobs settle |
| P1 | Simple VLM/OCR verifier baselines | pending | Compare against OCR exact/fuzzy match and generic VLM yes/no target-presence verifier |
| P2 | Better non-oracle verifier | pending | Add OCR + icon/UI proposal or VLM verifier if OCR-only underperforms |
| P2 | Great Lakes backup setup | paused | Only resume if CHPC queue blocks GPU jobs |

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

Run remaining validation and case mining:

```bash
sbatch scripts_utah/audit_absent_benchmark.slurm
sbatch scripts_utah/evaluate_filtered_absent_status.slurm
tail -n 120 $(ls -t seekui-combo-cases-*.out | head -1)
find "$SEEKUI_WORK/outputs/combined_cases" \( -name '*contact_sheet.jpg' -o -name '*contact_sheets.tgz' \) -print
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

## Decision Log

- Main research path is target-absent UI search with cognitive stopping.
- Oracle candidate verifier is an upper bound, not a deployable method.
- OCR-only verifier is useful as ablation, but currently too aggressive.
- Combined `AND` works better than either cognitive-only or OCR-only; `OR` is too aggressive or redundant.
- Combined `AND` holds up under dev/test threshold selection.
- Image split should be the main held-out evaluation because random split shares many images and image-target pairs.
- Next practical question: are case-mined errors interpretable, and do results hold after removing OCR-leak/annotation-conflict absent examples?
