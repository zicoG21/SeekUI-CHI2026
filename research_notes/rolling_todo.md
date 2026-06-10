# SeekUI Rolling TODO

Last updated: 2026-06-10

This is the short working TODO. Update every 1-2 days; keep only active or recently completed items here. Longer background notes stay in `RESEARCH_TODO.md` and `research_notes/current_progress_summary.md`.

## Active Queue

| Priority | Item | Status | Next action |
|---:|---|---|---|
| P0 | Finish v3 semantic-query jobs | running on CHPC | Check `squeue -u $USER`; when done, rerun summary and inspect semantic split tables |
| P0 | Combined cognitive + OCR verifier | code ready | Run `sbatch scripts_utah/apply_combined_verifier.slurm`, then inspect best `or`/`and` sweeps |
| P0 | Summarize combined verifier results | pending | Update `absent_status_core.csv` and copy best F1/accuracy rows into `rolling_results.md` |
| P1 | Mine combined-verifier cases | pending | If combined beats stopping or OCR, create case sheets for corrected/new errors |
| P1 | OCR verifier diagnosis | partial | Use details CSV to identify why present targets are missed by OCR |
| P1 | Non-text / image-cue analysis | pending | Compare image-cue metrics and failure cases after v3 jobs settle |
| P2 | Better non-oracle verifier | pending | Add OCR + icon/UI proposal or VLM verifier if OCR-only underperforms |
| P2 | Great Lakes backup setup | paused | Only resume if CHPC queue blocks GPU jobs |

## Commands To Run Next

```bash
cd ~/projects/SeekUI-CHI2026
git pull
sbatch scripts_utah/apply_combined_verifier.slurm
```

After the combined job finishes:

```bash
python scripts_research/summarize_research_outputs.py \
  --work-dir "$SEEKUI_WORK" \
  --output "$SEEKUI_WORK/outputs/research_summary.md" \
  --tables-dir "$SEEKUI_WORK/outputs/research_summary_tables"

cat "$SEEKUI_WORK/outputs/research_summary_tables/absent_status_core.csv"
```

Find best combined thresholds:

```bash
python - <<'PY'
import csv, os
for model in ["SeekUI", "SeekUI_sft"]:
    for rule in ["or", "and"]:
        p = os.environ["SEEKUI_WORK"] + f"/outputs/present_absent_predictions_{model}_combined_{rule}_present_only_threshold_sweep.csv"
        rows = list(csv.DictReader(open(p)))
        best_f1 = max(rows, key=lambda r: float(r["absent_f1"]))
        best_acc = max(rows, key=lambda r: float(r["accuracy"]))
        print("\n", model, rule)
        print("best by F1 :", best_f1)
        print("best by Acc:", best_acc)
PY
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

## Decision Log

- Main research path is target-absent UI search with cognitive stopping.
- Oracle candidate verifier is an upper bound, not a deployable method.
- OCR-only verifier is useful as ablation, but currently too aggressive.
- Next practical question: can combined cognitive + OCR improve over cognitive stopping alone?
