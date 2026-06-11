# One-Page Paper Skeleton

Last updated: 2026-06-10

## Working Title

From Forced-Choice Grounding to Uncertainty-Aware GUI Visual Search

## Core Problem

SeekUI-style GUI visual search assumes the requested target is present. In realistic UI use, a target may be absent from the current screen. Under target absence, a target-present model can behave like a forced-choice grounding system: it still produces a scanpath and often commits to a plausible but wrong UI element.

## Research Question

Can GUI visual search models recognize when a requested target is absent, while preserving useful scanpath behavior when the target is present?

## Method

We evaluate target-absent GUI visual search by constructing a synthetic present/absent benchmark from the released SeekUI/VSGUI subset:

```text
1362 present examples
1362 synthetic absent hard negatives
2724 total examples
```

We add a post-hoc stopping/verifier layer:

1. Cognitive path evidence estimates whether the predicted scanpath approached a target-like candidate.
2. OCR candidate verification checks whether visible text evidence supports the requested target.
3. A combined AND rule rejects a prediction only when both path evidence and OCR evidence are weak.

## Headline Result

On the cleaner image split, where dev/test images do not overlap:

| Model | Split | Prompt F1 | Combined F1 | Delta F1 95% CI | Prompt Acc | Combined Acc | Delta Acc 95% CI |
|---|---|---:|---:|---|---:|---:|---|
| SeekUI | image | 0.7347 | 0.8804 | [0.1167, 0.1739] | 0.7708 | 0.8692 | [0.0720, 0.1220] |
| SeekUI-SFT | image | 0.6744 | 0.8279 | [0.1232, 0.1834] | 0.7325 | 0.8148 | [0.0558, 0.1080] |

The full benchmark shows that prompt design strongly affects generic VLM yes/no baselines:

| Variant | Accuracy | Absent Precision | Absent Recall | Absent F1 |
|---|---:|---:|---:|---:|
| SeekUI prompt-only | 0.7684 | 0.8749 | 0.6263 | 0.7300 |
| VLM yes/no direct | 0.8510 | 0.9142 | 0.7746 | 0.8386 |
| VLM yes/no OCR-aware | 0.8924 | 0.8821 | 0.9060 | 0.8939 |
| SeekUI combined AND best-F1 | 0.8711 | 0.8115 | 0.9670 | 0.8824 |

The OCR-aware VLM prompt is the strongest full-benchmark classifier so far, while combined AND has higher absent recall and is grounded in the predicted scanpath. This suggests a revised framing: target-absent GUI search needs both strong presence classification and interpretable search-evidence analysis.

## Evidence Beyond the Main Table

Sanity checks:

- Annotation conflicts are rare: 4 cases.
- OCR-leak absent examples are nontrivial: 225 / 1362.
- Random split leaks images heavily; image split is the main held-out setting.
- Filtered sensitivity preserves the main effect after excluding annotation-conflict and OCR-leak absent examples.

Behavioral metrics:

- Prompt-only absent false-present errors are short and highly converged.
- Combined AND removes most easy false-present errors.
- Residual false-present errors are longer and have stronger distractor evidence.
- SeekUI-SFT scanpaths are much shorter, making stopping decisions brittle.

Qualitative taxonomy:

- Corrected absent false-present cases usually have weak path/OCR evidence and no stable target-like candidate.
- Residual absent false-present cases often contain strong text/function distractors such as login, continue, menu, upload, play, or language controls.
- New present false-absent cases often involve small, edge-positioned, low-contrast, stylized, cluttered, or OCR-missed targets.
- SeekUI-SFT failures often reflect short/off-target scanpaths and weak evidence accumulation.

## Contributions

1. A target-absent GUI visual search formulation that exposes a forced-choice limitation of target-present SeekUI inference.
2. A synthetic present/absent benchmark and sanity-audit protocol for evaluating target absence.
3. A cognitive stopping and OCR-verification layer that improves held-out absent F1 and accuracy.
4. Behavioral and qualitative analyses showing when the method corrects false-present errors and when it fails.
5. A VLM prompt-ablation baseline showing that generic presence classification is strong and prompt-sensitive, but trades off interpretability and absent recall.

## Current Limitations

- The absent benchmark is synthetic; a small real/manual validation set would strengthen the claim.
- Released data are text-target only, so non-text/icon/associative search remains a proxy experiment unless new annotations are added.
- OCR evidence is brittle for small, stylized, low-contrast, and edge-positioned targets.
- The post-hoc layer does not improve the scanpath itself; it changes the present/absent decision.

## Next Validation

1. Run hard-case analysis for examples where VLM and combined AND disagree.
2. Design a small manually verified realistic absent benchmark.
3. Evaluate whether VLM presence classification and scanpath-grounded stopping can be combined.
