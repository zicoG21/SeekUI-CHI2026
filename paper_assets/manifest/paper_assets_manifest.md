# Paper Assets Manifest

Source note: CHPC paper checkpoint and research notes, 2026-06-11

## Generated Assets

- `figures/case_sources/SeekUI_and_corrected_absent_false_present_contact_sheet.jpg`
- `figures/case_sources/SeekUI_and_kept_absent_false_present_contact_sheet.jpg`
- `figures/case_sources/SeekUI_and_new_present_false_absent_contact_sheet.jpg`
- `figures/case_taxonomy_caption.md`
- `figures/case_taxonomy_compact.jpg`
- `figures/case_taxonomy_compact.png`
- `figures/case_taxonomy_contact_sheet.jpg`
- `figures/case_taxonomy_contact_sheet.png`
- `figures/error_taxonomy.png`
- `figures/error_taxonomy.svg`
- `figures/error_taxonomy_caption.md`
- `figures/method_diagram.png`
- `figures/method_diagram.svg`
- `figures/method_diagram_caption.md`
- `tables/error_taxonomy_counts.csv`
- `tables/error_taxonomy_counts.md`
- `tables/error_taxonomy_counts.tex`
- `tables/heldout_image_split.csv`
- `tables/heldout_image_split.md`
- `tables/heldout_image_split.tex`
- `tables/main_results.csv`
- `tables/main_results.md`
- `tables/main_results.tex`
- `tables/realistic_absent_validation.csv`
- `tables/realistic_absent_validation.md`
- `tables/realistic_absent_validation.tex`

## Recommended Use

- `tables/main_results.*`: full synthetic present/absent benchmark baselines and verifier variants.
- `tables/heldout_image_split.*`: cleaner image-split headline result with bootstrap confidence intervals.
- `tables/realistic_absent_validation.*`: small manually reviewed external-validity check.
- `figures/method_diagram.*`: method overview.
- `figures/case_taxonomy_contact_sheet.*`: qualitative case figure from local contact sheets.
- `figures/case_taxonomy_compact.*`: compact qualitative case figure for paper body.
- `figures/error_taxonomy.*`: mined case-count taxonomy figure.

## Caveat

Candidate-verifier rows with F1 around 0.95 are diagnostic/oracle-like because they rely on candidate similarity evidence; the practical paper headline should use combined AND and evidence-aware VLM rows unless the candidate evidence is fully justified.
