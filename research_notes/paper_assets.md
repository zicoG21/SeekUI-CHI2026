# Paper Assets Checklist

Last updated: 2026-06-10

## Figure 1: Problem Setup

Purpose:

Show why target-present GUI visual search is incomplete.

Panel sketch:

1. Present target: query appears in the screenshot, model scanpath can end near target.
2. Absent target: query does not appear, target-present model still produces a forced-choice scanpath.
3. Proposed behavior: model searches, accumulates weak evidence, and stops with `absent`.

Needed artifacts:

- One present example with target box and scanpath.
- One absent false-present prompt-only example.
- Same absent example after combined AND rejection.

## Table 1: Main Held-Out Result

Use image split as headline because random split has image leakage.

| Model | Split | Prompt F1 | Combined F1 | Delta F1 95% CI | Prompt Acc | Combined Acc | Delta Acc 95% CI |
|---|---|---:|---:|---|---:|---:|---|
| SeekUI | image | 0.7347 | 0.8804 | [0.1167, 0.1739] | 0.7708 | 0.8692 | [0.0720, 0.1220] |
| SeekUI-SFT | image | 0.6744 | 0.8279 | [0.1232, 0.1834] | 0.7325 | 0.8148 | [0.0558, 0.1080] |

Source:

```text
$SEEKUI_WORK/outputs/devtest_combined/combined_devtest_image.md
$SEEKUI_WORK/outputs/paper_tables/main_result_table.md
```

## Table 2: Baselines and Ablations

Purpose:

Show that direct VLM yes/no is a strong baseline but does not beat combined AND.

Current full-benchmark rows:

| Variant | Accuracy | Absent Precision | Absent Recall | Absent F1 | Present->Absent | Absent->Present |
|---|---:|---:|---:|---:|---:|---:|
| SeekUI prompt-only | 0.7684 | 0.8749 | 0.6263 | 0.7300 | 122 | 509 |
| VLM yes/no direct | 0.8510 | 0.9142 | 0.7746 | 0.8386 | 99 | 307 |
| Cognitive stop present-only | 0.8414 | 0.7981 | 0.9141 | 0.8522 | 315 | 117 |
| Combined AND best-F1 | 0.8711 | 0.8115 | 0.9670 | 0.8824 | 306 | 45 |

Pending GL prompt rows:

| Prompt Variant | Accuracy | Absent Precision | Absent Recall | Absent F1 | Present->Absent | Absent->Present |
|---|---:|---:|---:|---:|---:|---:|
| Direct | 0.8510 | 0.9142 | 0.7746 | 0.8386 | 99 | 307 |
| Conservative | pending | pending | pending | pending | pending | pending |
| OCR-aware | pending | pending | pending | pending | pending | pending |
| Search-behavior | pending | pending | pending | pending | pending | pending |
| Combined AND best-F1 | 0.8711 | 0.8115 | 0.9670 | 0.8824 | 306 | 45 |

## Table 3: Sanity and Sensitivity

Purpose:

Defend the synthetic absent benchmark.

| Check | Value |
|---|---:|
| Annotation conflicts | 4 |
| OCR-leak absent examples | 225 / 1362 = 0.1652 |
| Random shared images | 507 |
| Image split shared images | 0 |
| Filtered examples kept | 2497 |
| SeekUI combined AND best-F1 filtered F1 | 0.8760 |
| SeekUI combined AND best-F1 filtered accuracy | 0.8726 |

## Figure 2: Visual Taxonomy

Purpose:

Show what combined AND fixes and what it breaks.

Panels:

1. Corrected absent false-present: weak evidence forced-choice.
2. New present false-absent: small/edge/OCR-missed true target.
3. Kept absent false-present: strong text/function distractor.

Source:

```text
research_notes/contact_sheet_visual_taxonomy.md
/home/perzival/HCI_Research/seekui_combined_cases/*/contact_sheet_export
```

## Figure 3: Behavioral Evidence

Purpose:

Support forced-choice interpretation with scanpath statistics.

Candidate plot:

- x-axis: variant/error type.
- y-axis: convergence, path length, or coverage.
- Highlight prompt-only absent false-present as short/highly converged.
- Highlight combined residual false-present as longer/lower convergence/harder.

Key rows:

| Model | Variant | Error Type | Count | Pred Len | Path Len Norm | Coverage | Convergence |
|---|---|---|---:|---:|---:|---:|---:|
| SeekUI | prompt | absent false-present | 509 | 3.16 | 0.1459 | 0.1126 | 0.9138 |
| SeekUI | combined best-F1 | absent false-present | 45 | 4.09 | 0.2339 | 0.1375 | 0.8606 |

## Figure 4: Method Diagram

Pipeline:

```text
GUI + target cue
    -> SeekUI scanpath + predicted status
    -> cognitive path evidence
    -> OCR candidate verifier
    -> combined AND stopping decision
    -> present scanpath or absent decision
```

Message:

The method is a post-hoc interpretable safety layer, not a retrained model.
