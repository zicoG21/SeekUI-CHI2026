# Non-Text and Image-Cue Experiment Scaffold

This scaffold turns the non-text/image-cue direction into concrete experiments that can be run after the current absent-aware pipeline.

## Experiment Matrix

| ID | Priority | Cue Type | Data Source | Metric | Purpose | Risk |
|---|---|---|---|---|---|---|
| image_crop_proxy | P0 | target_crop_image | existing present targets cropped from VSGUI10K | last-to-target distance, scanpath metrics, absent-status rate | Feasibility check for multimodal target cues without new annotation. | Proxy remains text-derived; does not prove native non-text search. |
| icon_category_pilot | P1 | category_text | manual 100-200 row icon/category pilot | hit rate, absent F1, error taxonomy | Test non-exact visual/semantic target search. | Requires manual confirmation of valid targets. |
| functional_query_pilot | P1 | functional_text | manual realistic GUI query pilot | grounding accuracy, ambiguity rate, absent F1 | Separate exact text grounding from task/function understanding. | Ambiguity can dominate unless annotation rules are strict. |
| non_text_absent_pilot | P1 | icon_or_function_absent | manual real absent validation extension | absent precision/recall/F1 | External-validity check for absent-aware non-text search. | Small pilot only; needs balanced present/absent rows. |
| candidate_crop_vlm_verifier | P2 | candidate_crop_verification | model predictions + candidate crops | verification accuracy, rescue rate, over-rejection rate | Replace brittle OCR-only evidence for icons and stylized UI targets. | Requires reliable candidate proposal/cropping. |

## Annotation Schema

| Field | Meaning |
|---|---|
| `row_id` | stable integer or UUID |
| `image` | relative screenshot path |
| `cue_type` | target_crop_image &#124; category_text &#124; functional_text &#124; icon_or_function_absent |
| `query_text` | text cue when applicable |
| `query_image` | target crop path when applicable |
| `gold_status` | present &#124; absent |
| `target_bbox` | x,y,w,h for present rows; empty for absent rows |
| `target_visible` | yes &#124; no |
| `query_realistic` | yes &#124; no |
| `ambiguity_level` | low &#124; medium &#124; high |
| `primary_target_modality` | text &#124; icon &#124; image &#124; layout &#124; function |
| `notes` | short reason for ambiguity/invalidity |

## Commands

### Regenerate current image-cue proxy benchmark

```bash
bash scripts_research/run_offline_research_prep.sh
```

### Summarize current image-cue proxy results

```bash
python scripts_research/summarize_research_outputs.py --work-dir "$SEEKUI_WORK" --output "$SEEKUI_WORK/outputs/research_summary.md" --tables-dir "$SEEKUI_WORK/outputs/research_summary_tables"
```

### Create manual non-text annotation sheet

```bash
python scripts_research/export_non_text_image_cue_scaffold.py --out-dir paper_assets/non_text_image_cue_scaffold
```

## Immediate Recommendation

Use `image_crop_proxy` as the current feasibility result, then build a 100-200 row `icon_category_pilot` with balanced present/absent labels. Keep functional queries separate because ambiguity is higher.
