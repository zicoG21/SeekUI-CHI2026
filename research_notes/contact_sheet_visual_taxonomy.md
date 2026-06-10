# Contact-Sheet Visual Taxonomy Notes

Last updated: 2026-06-10

These notes summarize the locally reviewed stopping-case and combined-verifier contact sheets:

```text
/home/perzival/HCI_Research/seekui_stopping_cases/packaged/SeekUI/visualizations
/home/perzival/HCI_Research/seekui_stopping_cases/packaged/SeekUI_sft/visualizations
/home/perzival/HCI_Research/seekui_combined_cases/SeekUI_and_present_only_best_f1_contact_sheets/contact_sheet_export
/home/perzival/HCI_Research/seekui_combined_cases/SeekUI_sft_and_present_only_best_f1_contact_sheets/contact_sheet_export
```

## Reviewed Sheets

| Model | Case type | Local sheet |
|---|---|---|
| SeekUI | corrected_absent_false_present | `SeekUI_corrected_absent_false_present_contact_sheet.jpg` |
| SeekUI | new_present_false_absent | `SeekUI_new_present_false_absent_contact_sheet.jpg` |
| SeekUI | kept_absent_false_present | `SeekUI_kept_absent_false_present_contact_sheet.jpg` |
| SeekUI_sft | corrected_absent_false_present | `SeekUI_sft_corrected_absent_false_present_contact_sheet.jpg` |
| SeekUI_sft | new_present_false_absent | `SeekUI_sft_new_present_false_absent_contact_sheet.jpg` |
| SeekUI_sft | kept_absent_false_present | `SeekUI_sft_kept_absent_false_present_contact_sheet.jpg` |
| SeekUI + combined AND | corrected_absent_false_present | `SeekUI_and_corrected_absent_false_present_contact_sheet.jpg` |
| SeekUI + combined AND | new_present_false_absent | `SeekUI_and_new_present_false_absent_contact_sheet.jpg` |
| SeekUI + combined AND | kept_absent_false_present | `SeekUI_and_kept_absent_false_present_contact_sheet.jpg` |
| SeekUI_sft + combined AND | corrected_absent_false_present | `SeekUI_sft_and_corrected_absent_false_present_contact_sheet.jpg` |
| SeekUI_sft + combined AND | new_present_false_absent | `SeekUI_sft_and_new_present_false_absent_contact_sheet.jpg` |
| SeekUI_sft + combined AND | kept_absent_false_present | `SeekUI_sft_and_kept_absent_false_present_contact_sheet.jpg` |

## Combined Case Counts

| Model | Corrected absent false-present | New present false-absent | Kept absent false-present |
|---|---:|---:|---:|
| SeekUI + combined AND | 464 | 184 | 45 |
| SeekUI_sft + combined AND | 458 | 227 | 133 |

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

## Combined-Sheet Review

The combined-verifier sheets largely confirm the stopping-only taxonomy, but sharpen the mechanism.

### SeekUI + Combined AND

Corrected absent false-present:

- The corrected examples are mostly weak-evidence forced-choice errors.
- Many screens contain plausible UI elements, but no clear visual/text target match.
- The combined rule suppresses cases where neither the path evidence nor OCR evidence strongly supports the predicted target.
- This is the strongest qualitative support for the claim that target-absent errors are often forced-choice commitments rather than meaningful searches.

New present false-absent:

- The dominant failure mode is conservative rejection of present targets.
- Many true targets are small, peripheral, low contrast, or embedded in long/cluttered pages.
- OCR and local candidate evidence appear brittle around compact buttons, menu items, stylized text, and dense web layouts.
- These are the main cost of the combined method: improved absent recall in exchange for some missed present targets.

Kept absent false-present:

- These are genuine hard residual cases.
- Most include a strong text, button, menu, or functional distractor that overlaps with the target cue.
- Common examples include login/continue/save/open-type controls, language buttons, menu items, news/site navigation, and visually salient action buttons.
- The residual set is qualitatively harder than the corrected set; these are not merely low-evidence hallucinations.

### SeekUI-SFT + Combined AND

Corrected absent false-present:

- The corrected examples again show weak target evidence and forced-choice behavior.
- Compared with SeekUI, the correction often looks more like evidence absence from short paths rather than a robust search process.

New present false-absent:

- This is the clearest SFT weakness.
- Many targets are visibly present, sometimes even clearly boxed, but the generated scanpath is short, off-target, or provides too little support.
- Combined AND amplifies this brittleness because both cognitive/path evidence and OCR evidence can fail on small or peripheral present targets.

Kept absent false-present:

- Residual SFT errors are dominated by strong distractors and cluttered screens.
- There are more kept false-present cases for SFT than SeekUI, consistent with weaker base scanpaths and shorter evidence accumulation.
- The residual set includes semantically broad or function-like targets where a related visible control makes the absent/present decision ambiguous.

## Paper-Useful Takeaways

1. Combined AND does not merely threshold random outputs. It preferentially removes weak-evidence forced-choice absent errors.
2. The remaining false-present errors are harder: they usually have a real distractor with text, visual, or functional overlap.
3. The main tradeoff is conservative false absence on present targets, especially small, edge, low-contrast, stylized, or cluttered targets.
4. SeekUI-SFT is more brittle because short scanpaths provide less evidence for the stopping/verifier layer.
5. This supports framing the method as an interpretable safety layer, not a replacement for better visual grounding.

## Review CSV Mapping

If filling the CHPC review CSV, use this sheet-level mapping:

| Model | Case type | Primary pattern | Secondary pattern | Review status |
|---|---|---|---|---|
| SeekUI | corrected_absent_false_present | `overconfident_forced_choice;no_clear_target_match` | `under_search_short_path;layout_clutter` | reviewed |
| SeekUI | new_present_false_absent | `small_target;edge_or_corner_target` | `ocr_miss;low_contrast_or_stylized_text;layout_clutter` | reviewed |
| SeekUI | kept_absent_false_present | `strong_text_distractor;strong_icon_or_button_distractor` | `ambiguous_target;layout_clutter` | reviewed |
| SeekUI_sft | corrected_absent_false_present | `overconfident_forced_choice;no_clear_target_match` | `under_search_short_path` | reviewed |
| SeekUI_sft | new_present_false_absent | `under_search_short_path;small_target` | `ocr_miss;edge_or_corner_target;layout_clutter` | reviewed |
| SeekUI_sft | kept_absent_false_present | `strong_text_distractor;strong_icon_or_button_distractor` | `ambiguous_target;layout_clutter;under_search_short_path` | reviewed |

Suggested notes:

```text
SeekUI corrected: Combined AND removes many weak-evidence forced-choice absent errors where no clear target match is visible.
SeekUI new false-absent: Errors concentrate on small, edge, stylized, or cluttered present targets where OCR/path evidence is brittle.
SeekUI kept false-present: Residual errors usually contain strong text/button/function distractors, making them genuinely hard.
SeekUI_sft corrected: Similar forced-choice corrections, but often driven by missing evidence from short generated paths.
SeekUI_sft new false-absent: Short/off-target paths make SFT more likely to reject visible present targets.
SeekUI_sft kept false-present: Residual cases combine strong distractors with SFT's weaker evidence accumulation.
```
