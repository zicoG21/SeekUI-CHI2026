# SeekUI Rolling TODO

Last updated: 2026-06-10

This is the short working TODO. Update every 1-2 days; keep only active or recently completed items here. Longer background notes stay in `RESEARCH_TODO.md` and `research_notes/current_progress_summary.md`.

## Active Queue

| Priority | Item | Status | Next action |
|---:|---|---|---|
| P0 | Finish v3 semantic-query jobs | running on CHPC | Check `squeue -u $USER`; when done, rerun summary and inspect semantic split tables |
| P0 | Combined cognitive + OCR verifier | completed | Best `and` combination beats cognitive stopping; keep as current strongest non-oracle method |
| P0 | Add dev/test validation for combined verifier | code ready | Run `sbatch scripts_utah/evaluate_combined_devtest.slurm` |
| P0 | Mine combined-verifier cases | code ready | Run `sbatch scripts_utah/mine_combined_cases.slurm` |
| P1 | OCR verifier diagnosis | partial | Use details CSV to identify why present targets are missed by OCR |
| P1 | Non-text / image-cue analysis | pending | Compare image-cue metrics and failure cases after v3 jobs settle |
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

Run combined verifier validation and case mining:

```bash
sbatch scripts_utah/evaluate_combined_devtest.slurm
sbatch scripts_utah/mine_combined_cases.slurm
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

## Decision Log

- Main research path is target-absent UI search with cognitive stopping.
- Oracle candidate verifier is an upper bound, not a deployable method.
- OCR-only verifier is useful as ablation, but currently too aggressive.
- Combined `AND` works better than either cognitive-only or OCR-only; `OR` is too aggressive or redundant.
- Next practical question: does combined `AND` hold up under dev/test threshold selection?
