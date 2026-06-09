# One-Page Research Plan: Beyond Forced-Choice SeekUI

## Core Claim

Current SeekUI-style UI visual-search models are forced-choice systems: they receive a GUI screenshot and a text target, then predict a scanpath as if the target must exist. Human visual search includes a stopping decision. A user can search, accumulate uncertainty, and decide that the requested target is not present on the current screen.

## Research Direction

Build and evaluate robust UI target search beyond the target-present assumption.

Primary question:

```text
Can a UI visual-search model decide when a requested target is absent instead of hallucinating a plausible target location?
```

Secondary questions:

- Can a simple cognitive stopping model explain target-absent behavior better than prompt-only VLM inference?
- How much does performance drop when the query is a semantic or functional rephrasing rather than exact interface text?
- Can image-cue prompting serve as a first prototype for non-text target search before collecting real icon/image-cue trials?

## Why This Is The First Project

The released SeekUI/VSGUI JSON is text-target only in the current audit (`txt: 1362`). That makes real non-text target search difficult without new data. Target-absent search can start immediately by constructing hard-negative trials from existing images, then validating those negatives with manual/OCR review.

This gives a clean HCI framing:

```text
Existing model: forced-choice scanpath prediction.
Proposed extension: visual search with uncertainty and stopping.
```

## Initial Benchmark

Create a mixed present/absent benchmark:

- Present examples: original VSGUI/SeekUI trials.
- Absent examples: target cue is swapped onto another GUI where that target id/text is not annotated.
- Validation: export a manual review sheet for a subset to check whether the target is truly absent and whether the query is valid.

## Baselines

1. SeekUI prompt-only absent detection.
2. SeekUI-SFT prompt-only absent detection.
3. Text-candidate cognitive stopping baseline.
4. Semantic-query robustness benchmark using exact vs rephrased/functional queries.
5. Image-cue target-crop benchmark as a weak multimodal prototype.

## Metrics

Status metrics:

- accuracy
- absent precision
- absent recall
- absent F1
- false-positive rate on absent trials

Scanpath metrics:

- ScanMatch
- MultiMatch
- SED / STDE
- SS, CC, AUC, NSS, sAUC

Review/audit metrics:

- synthetic absent label validity rate
- semantic query validity rate
- common failure modes: forced-choice hallucination, premature absent, wrong semantic target, over-reliance on text

## Expected Contribution

This project can show that target-present UI search is an incomplete model of real interaction. The contribution is not only a new benchmark, but a cognitive framing: UI search models need both scanpath prediction and a stopping decision under uncertainty.

## Near-Term Deliverables

- Data audit proving the released split is text-target only.
- Synthetic present/absent benchmark plus validation report.
- Prompt-only absent baselines for SeekUI and SeekUI-SFT.
- Cognitive stopping threshold sweep.
- Semantic-query and image-cue prototype results.
- Manual review sheets for absent-label and semantic-query quality.
- A short slide-ready error taxonomy from reviewed cases.
