# Memo: SeekUI Beyond Forced-Choice Search

## Working Thesis

SeekUI currently behaves like a forced-choice visual search model: given a GUI and a text target, it predicts a scanpath to a target that is assumed to exist. Human visual search is not forced-choice. People search, accumulate uncertainty, and eventually stop when a target is absent. This makes target-absent UI search a natural HCI extension of SeekUI and a concrete way to incorporate cognitive modeling.

## Why This Direction First

Compared with non-text target search and associative search, target-absent search can start immediately from the released SeekUI data and checkpoints.

- The current released JSON has 1362 examples and 646 unique GUI images.
- A local audit found `target_prefix_counts: txt=1362`, so the released data is essentially text-target only.
- This means non-text target search likely needs new data, target-crop construction, or another VSGUI split.
- In contrast, absent-target hard negatives can be constructed now by swapping target cues across images while avoiding known target id/text conflicts.

## Research Question

Can UI visual-search models decide when a requested target is absent, rather than hallucinating a plausible fixation path to a nonexistent target?

## Proposed Benchmark

Create a mixed present/absent benchmark:

- Present trials: original SeekUI/VSGUI examples.
- Absent trials: synthetic hard negatives made by placing a target cue from one image onto another image where the same target id/text is not annotated.

The synthetic construction is not a perfect proof of visual absence, but it is a practical first benchmark. It can later be strengthened with OCR/manual validation.

## Model Conditions

1. SeekUI prompt-only absent detection.
2. SeekUI-SFT prompt-only absent detection.
3. Minimal cognitive stopping baseline.
4. Future: fine-tuned present/absent SeekUI.
5. Future: reward-augmented stopping model.

## Metrics

For present/absent status:

- Accuracy
- Absent precision
- Absent recall
- Absent F1
- False positive rate on absent trials

For scanpath quality on present trials:

- Existing SeekUI scanpath metrics: ScanMatch, MultiMatch, SED, STDE, SS, CC, AUC, NSS, sAUC

For stopping behavior:

- Number of fixations before absent decision
- Calibration/threshold sweep
- Tradeoff between present hit rate and absent rejection

## Cognitive Model Framing

The cognitive baseline models stopping as thresholded evidence accumulation:

```text
continue searching if max target-match evidence >= threshold
stop as absent if max target-match evidence < threshold after candidate coverage
```

The first implementation uses annotated target texts as candidate regions and string similarity as evidence. This is intentionally simple. It establishes an interpretable lower bound and a threshold sweep.

A richer later version can use:

- OCR boxes as candidate regions
- icon/object proposals
- visual saliency
- semantic text embeddings
- layout priors
- inhibition of return
- saccade distance cost

## Relationship to Jiang's Four Directions

1. Target absent: primary immediate contribution.
2. Cognitive model: used to frame stopping and uncertainty accumulation.
3. Non-text/multimodal targets: important, but current released JSON is text-only, so this needs additional data construction.
4. Associative search: high-level future direction requiring new annotation or a separate benchmark.

## Immediate Deliverables

- Data audit summary.
- Synthetic absent and mixed present/absent JSON.
- Prompt-only absent predictions for SeekUI and SeekUI-SFT.
- Status evaluation table.
- Cognitive stopping threshold sweep.
- Visualization examples of present, absent, and failure cases.

## Risks and Mitigations

- Synthetic absent labels may be noisy.
  - Mitigation: audit with OCR/manual checks for a subset.
- Prompt-only model may never output absent.
  - Mitigation: this itself demonstrates forced-choice behavior and motivates fine-tuning/stopping.
- Text-only data limits multimodal claims.
  - Mitigation: position non-text search as a second-stage extension after auditing data availability.
