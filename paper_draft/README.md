# Paper Draft Skeleton

This directory is a lightweight LaTeX scaffold for turning the generated paper assets into a draft.

Compile from this directory:

```bash
pdflatex main.tex
```

The draft references generated assets from:

```text
../paper_assets/
```

Regenerate assets from the repository root:

```bash
python scripts_research/export_paper_assets.py --out-dir paper_assets
python scripts_research/export_real_absent_case_analysis.py \
  --real-absent-source /home/perzival/HCI_Research/real_absent_results_gl_full.tgz \
  --out-dir paper_assets/real_absent_case_analysis
```
