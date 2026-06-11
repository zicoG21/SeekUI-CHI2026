# Paper Assets Checklist

Last updated: 2026-06-11

Generated local assets:

```text
paper_assets/manifest/paper_assets_manifest.md
paper_assets/tables/main_results.md
paper_assets/tables/heldout_image_split.md
paper_assets/tables/realistic_absent_validation.md
paper_assets/tables/method_strength_summary.md
paper_assets/tables/error_taxonomy_counts.md
paper_assets/figures/method_diagram.png
paper_assets/figures/case_taxonomy_compact.jpg
paper_assets/figures/case_taxonomy_contact_sheet.jpg
paper_assets/figures/error_taxonomy.png
paper_assets/real_absent_case_analysis/real_absent_case_analysis.md
paper_assets/appendix/real_absent_100row_audit_appendix.md
paper_assets/non_text_image_cue_scaffold/non_text_image_cue_scaffold.md
```

Regenerate with:

```bash
python scripts_research/export_paper_assets.py --out-dir paper_assets
```

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

Show that VLM yes/no prompting is a strong, prompt-sensitive baseline, and that the strongest current practical method is an evidence-aware VLM that sees both the screenshot and scanpath/OCR evidence.

Current full-benchmark rows:

| Variant | Accuracy | Absent Precision | Absent Recall | Absent F1 | Present->Absent | Absent->Present |
|---|---:|---:|---:|---:|---:|---:|
| SeekUI prompt-only | 0.7684 | 0.8749 | 0.6263 | 0.7300 | 122 | 509 |
| VLM yes/no direct | 0.8510 | 0.9142 | 0.7746 | 0.8386 | 99 | 307 |
| VLM yes/no conservative | 0.8605 | 0.8160 | 0.9310 | 0.8697 | 286 | 94 |
| VLM yes/no OCR-aware | 0.8924 | 0.8821 | 0.9060 | 0.8939 | 165 | 128 |
| VLM yes/no search-behavior | 0.8902 | 0.9136 | 0.8620 | 0.8870 | 111 | 188 |
| Cognitive stop present-only | 0.8414 | 0.7981 | 0.9141 | 0.8522 | 315 | 117 |
| Combined AND best-F1 | 0.8711 | 0.8115 | 0.9670 | 0.8824 | 306 | 45 |
| Evidence-aware VLM | 0.8891 | 0.8308 | 0.9772 | 0.8981 | 271 | 31 |

Source:

```text
$SEEKUI_WORK/outputs/paper_tables/vlm_ablation_table.md
```

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
    -> evidence-aware VLM verifier
    -> present scanpath or absent decision
```

Message:

The method is a post-hoc verifier: no retraining is required, but the VLM is given interpretable scanpath/OCR evidence when making the final target-presence decision.

## Table 4: VLM vs Combined Hard-Case Overlap

Purpose:

Show that OCR-aware VLM and combined AND are complementary.

| Comparison | Case Source | Case Type | Count | Mean Path Evidence | Mean OCR Score |
|---|---|---|---:|---:|---:|
| Direct VLM vs combined | vlm wrong, combined correct | absent | 100 capped | 0.0428 | 0.3604 |
| Direct VLM vs combined | combined wrong, VLM correct | present | 100 capped | 0.1643 | 0.4497 |
| OCR-aware VLM vs combined | vlm wrong, combined correct | absent | 100 capped | 0.0373 | 0.3613 |
| OCR-aware VLM vs combined | combined wrong, VLM correct | present | 100 capped | 0.1545 | 0.4569 |
| OCR-aware VLM vs combined | both wrong | absent | 22 | 0.0919 | 0.7750 |
| Evidence-aware VLM vs combined | vlm wrong, combined correct | absent | 16 | 0.0401 | 0.3749 |
| Evidence-aware VLM vs combined | combined wrong, VLM correct | present | 100 capped | 0.1604 | 0.5089 |
| Evidence-aware VLM vs combined | both wrong | absent | 15 | 0.0999 | 0.8618 |

Message:

Evidence-aware VLM keeps much of combined AND's not-found safety while rescuing many visible present targets that rule-based combined AND over-rejects. The remaining both-wrong absent cases have high OCR scores, suggesting hard distractors or OCR leakage.
