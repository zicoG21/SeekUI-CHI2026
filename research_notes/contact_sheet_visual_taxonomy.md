# Contact-Sheet Visual Taxonomy Notes

Last updated: 2026-06-10

These notes summarize the currently available local stopping-case contact sheets:

```text
/home/perzival/HCI_Research/seekui_stopping_cases/packaged/SeekUI/visualizations
/home/perzival/HCI_Research/seekui_stopping_cases/packaged/SeekUI_sft/visualizations
```

The combined-verifier contact sheets were not present locally at the time of review, so this is a working taxonomy to reuse and verify once the combined sheets are downloaded.

## Reviewed Sheets

| Model | Case type | Local sheet |
|---|---|---|
| SeekUI | corrected_absent_false_present | `SeekUI_corrected_absent_false_present_contact_sheet.jpg` |
| SeekUI | new_present_false_absent | `SeekUI_new_present_false_absent_contact_sheet.jpg` |
| SeekUI | kept_absent_false_present | `SeekUI_kept_absent_false_present_contact_sheet.jpg` |
| SeekUI_sft | corrected_absent_false_present | `SeekUI_sft_corrected_absent_false_present_contact_sheet.jpg` |
| SeekUI_sft | new_present_false_absent | `SeekUI_sft_new_present_false_absent_contact_sheet.jpg` |
| SeekUI_sft | kept_absent_false_present | `SeekUI_sft_kept_absent_false_present_contact_sheet.jpg` |

## Working Taxonomy

### Corrected Absent False-Present

These are cases where prompt-only predicted a present target on an absent trial, but the stopping layer correctly changed it to absent.

Dominant patterns:

- `overconfident_forced_choice`: the model commits to a plausible UI element even though the requested target is absent.
- `no_clear_target_match`: the scanpath does not land on a region with strong target evidence.
- `strong_text_distractor`: visible text or common button labels draw the model toward a semantically nearby but wrong candidate.
- `under_search_short_path`: many corrected cases have short, quickly convergent paths, consistent with forced-choice behavior.
- `layout_clutter`: dense pages produce plausible but weak target matches that the stopping evidence suppresses.

Interpretation:

The stopping layer is useful because many absent errors are not broad exploratory searches. They are short, confident commitments to weak evidence. This supports the forced-choice framing.

### New Present False-Absent

These are cases where the target is present, but the stopping layer incorrectly changes the prediction to absent.

Dominant patterns:

- `small_target`: target is small relative to the screen, often a compact link/button/icon-like text region.
- `edge_or_corner_target`: target appears in navigation bars, sidebars, top bars, or other peripheral UI areas.
- `low_contrast_or_stylized_text`: target is visually present but not easy to read or align to evidence.
- `layout_clutter`: target sits among many similar UI elements, so local evidence is diluted.
- `under_search_short_path`: especially for SeekUI-SFT, predicted paths are short or terminate before enough target evidence is accumulated.

Interpretation:

The main cost of stopping is false absence on present targets. This is not random: it concentrates on small, peripheral, low-contrast, or cluttered targets. For SeekUI-SFT, short scanpaths make this worse.

### Kept Absent False-Present

These are residual errors where both prompt-only and stopping still predict present on an absent trial.

Dominant patterns:

- `strong_text_distractor`: the screen contains a text region close enough to the target cue to pass the stopping evidence.
- `strong_icon_or_button_distractor`: common UI actions such as login, play, settings, upload, or menu-like controls attract predictions.
- `ambiguous_target`: the query is semantically broad enough that a related visible element may look acceptable.
- `layout_clutter`: dense pages contain many weakly related candidates.
- `overconfident_forced_choice`: the model still commits when a distractor provides enough local evidence.

Interpretation:

The remaining errors are harder than the corrected absent false-present cases. They often contain an actual distractor with semantic or functional overlap, so a text/evidence threshold alone is insufficient.

## Model Difference

SeekUI:

- Stronger base scanpath behavior.
- New false-absent cases are often due to small, edge, low-contrast, or cluttered targets.
- Kept false-present cases are mostly strong distractors.

SeekUI-SFT:

- More brittle after stopping because generated scanpaths are shorter.
- New false-absent cases more often look like evidence accumulation failures: the target may be visible, but the predicted path gives too little support.
- Kept false-present cases still show strong distractors, but short-path behavior makes the distinction between false absent and false present less stable.

## Combined-Sheet Review Plan

When the combined-verifier contact sheets are available locally, review the same three case types:

```text
corrected_absent_false_present
new_present_false_absent
kept_absent_false_present
```

Expected questions:

- Does combined AND mainly remove the short-path forced-choice errors?
- Are remaining false-present cases dominated by strong textual or functional distractors?
- Are new false-absent cases mainly OCR miss / small target / edge target cases?
- Does combined AND reduce the SFT short-path brittleness or merely shift it into present false-absent errors?

The completed review should fill:

```text
$SEEKUI_WORK/outputs/contact_sheet_review/combined_contact_sheet_review.csv
```

and then rerun:

```bash
sbatch scripts_utah/summarize_contact_sheet_review.slurm
```
