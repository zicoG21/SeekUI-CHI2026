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

The second implementation should make the cognitive process explicit. Instead of only taking the maximum candidate similarity, it simulates a short sequence of candidate inspections:

```text
score(region) =
  target_similarity
  + layout_prior
  - saccade_distance_cost
  - visited_region_penalty
```

At each step, the model visits the highest-scoring unvisited candidate. It then stops as absent when accumulated target-match evidence remains below threshold after the simulated search budget. This does not require training, but it gives us interpretable per-step traces and makes the stopping decision closer to a search process.

However, the process baseline is still an upper-bound because it can inspect annotated candidate regions. The next analysis should use the model's actual predicted fixation path instead of a simulated path. For each predicted fixation, we align it to nearby annotated text/target candidates and compute local evidence:

```text
path_evidence(step) =
  text_similarity(query, nearest_or_best_candidate)
  * exp(-distance_to_candidate / radius)

path_best_evidence = max_step path_evidence(step)
```

This turns stopping into a diagnostic question:

- Absent false-present with low path evidence suggests forced-choice hallucination.
- Present false-absent with high path evidence suggests premature stopping or parsing failure.
- Correct absent with low evidence suggests a plausible reject decision.
- Correct present with high evidence suggests the scanpath actually reached relevant evidence.

The script `scripts_research/analyze_prediction_stopping_evidence.py` implements this diagnostic for completed present/absent prediction JSONs and writes per-example evidence, per-step evidence, and threshold sweeps.

The first completed prediction-path evidence run supports the stopping hypothesis. There are two useful variants:

- `override`: fully re-decide present/absent from path evidence.
- `present_only`: conservative safety layer that only turns low-evidence `present` predictions into `absent`.

| Model / Variant | Absent F1 | Absent Recall | Accuracy | Threshold |
|---|---:|---:|---:|---:|
| SeekUI prompt-only | 0.7300 | 0.6263 | 0.7684 | n/a |
| SeekUI + stopping, override | 0.8380 | 0.9626 | 0.8139 | 0.20 |
| SeekUI + stopping, present-only | 0.8317 | 0.9853 | 0.8007 | 0.20 |
| SeekUI-SFT prompt-only | 0.6878 | 0.5661 | 0.7430 | n/a |
| SeekUI-SFT + stopping, override | 0.7394 | 0.9332 | 0.6711 | 0.10 |
| SeekUI-SFT + stopping, present-only | 0.7529 | 0.9721 | 0.6810 | 0.10 |

Low-evidence false-present errors dominate:

```text
SeekUI:     489 / 509 absent false-present errors = 96.1%
SeekUI-SFT: 578 / 591 absent false-present errors = 97.8%
```

For SeekUI, correct-present examples have much higher path evidence than absent false-present examples:

```text
correct_present mean evidence:       0.4175
absent_false_present mean evidence:  0.0379
correct_absent mean evidence:        0.0480
present_false_absent mean evidence:  0.3381
```

This suggests that many false-present errors are not cases where the model found strong misleading evidence. They are low-evidence forced-choice guesses. That distinction matters for the paper framing: the contribution can be a stopping/calibration layer over scanpath generation, not necessarily a new end-to-end generator.

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
   - Near-term scaffold: semantic-query robustness with template/query variants.

## Immediate Deliverables

- Data audit summary.
- Synthetic absent and mixed present/absent JSON.
- Prompt-only absent predictions for SeekUI and SeekUI-SFT.
- Status evaluation table.
- Cognitive stopping threshold sweep.
- Prediction-path stopping evidence analysis.
- Visualization examples of present, absent, and failure cases.
- Target-crop image-cue benchmark as a multimodal prototype.
- Semantic-query variant benchmark as an associative-search scaffold.

## Risks and Mitigations

- Synthetic absent labels may be noisy.
  - Mitigation: audit with OCR/manual checks for a subset.
- Prompt-only model may never output absent.
  - Mitigation: this itself demonstrates forced-choice behavior and motivates fine-tuning/stopping.
- Text-only data limits multimodal claims.
  - Mitigation: position non-text search as a second-stage extension after auditing data availability.
  - Mitigation: use target-crop image cues as a prototype while clearly labeling it as weakly constructed from text-target data.
- Associative search labels are subjective.
  - Mitigation: first report semantic-query robustness separately from true associative search.
