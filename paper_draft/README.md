# Paper Draft v0

This directory is a lightweight LaTeX v0 draft for turning the generated paper assets into a paper narrative.

Current framing:

- Primary claim: target-present GUI visual-search models show forced-choice grounding under target absence.
- Main held-out result: combined path+OCR verification improves SeekUI on the image-disjoint split.
- Secondary verifier comparison: evidence-aware VLM is promising, but should not become the headline until matched split validation is complete.
- External-validity check: the 100-row realistic absent validation is included as an initial, not final, real-absent result.

Compile from this directory:

```bash
pdflatex main.tex
```

The current draft compiles to an 11-page PDF including appendix figures; the main text is roughly a 6-8 page v0 body before the appendix/contact sheets.

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
