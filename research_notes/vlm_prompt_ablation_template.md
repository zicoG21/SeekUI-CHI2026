# VLM Prompt Ablation Template

Last updated: 2026-06-10

## Question

Can generic VLM yes/no prompting solve target absence, or does the combined scanpath-grounded verifier remain stronger?

## Prompt Variants

| Variant | Intent |
|---|---|
| direct | Ask whether the target is visible. |
| conservative | Only answer present if the target is clearly visible. |
| ocr_aware | Ask the model to check exact text, near text variants, or obvious visual matches. |
| search_behavior | Ask whether a user searching the UI would likely find the target. |

## Result Table

| Prompt Variant | Accuracy | Absent Precision | Absent Recall | Absent F1 | Present->Absent | Absent->Present |
|---|---:|---:|---:|---:|---:|---:|
| direct | 0.8510 | 0.9142 | 0.7746 | 0.8386 | 99 | 307 |
| conservative | 0.8605 | 0.8160 | 0.9310 | 0.8697 | 286 | 94 |
| ocr_aware | 0.8924 | 0.8821 | 0.9060 | 0.8939 | 165 | 128 |
| search_behavior | 0.8902 | 0.9136 | 0.8620 | 0.8870 | 111 | 188 |
| combined AND best-F1 | 0.8711 | 0.8115 | 0.9670 | 0.8824 | 306 | 45 |

Filtered direct baseline:

| Prompt Variant | Accuracy | Absent Precision | Absent Recall | Absent F1 | Present->Absent | Absent->Present |
|---|---:|---:|---:|---:|---:|---:|
| direct filtered | 0.8706 | 0.9020 | 0.8026 | 0.8494 | 99 | 224 |

## Current Interpretation

The GL prompt ablation shows that prompt design matters substantially:

- `direct` is strong but misses many absent cases: absent recall 0.7746.
- `conservative` strongly improves absent recall to 0.9310, but causes many present false-absent errors.
- `ocr_aware` is the best full-benchmark VLM prompt so far: absent F1 0.8939 and accuracy 0.8924.
- `search_behavior` has high precision and accuracy, but lower absent recall than `ocr_aware`.
- `combined AND` still has the highest absent recall among non-oracle practical methods: 0.9670, but lower precision and accuracy than `ocr_aware`.

This changes the framing: the strongest generic VLM prompt can outperform combined AND on full-benchmark absent F1/accuracy, while combined AND remains a scanpath-grounded, interpretable safety layer with stronger absent recall and complementary hard cases.

## Interpretation Guide

If conservative improves absent recall but causes many present false-absent errors:

- It confirms that prompt framing shifts the precision/recall tradeoff.
- Combined AND can be positioned as a scanpath-grounded way to control this tradeoff.

If OCR-aware improves over direct:

- It suggests visible text verification is important.
- Compare against OCR-only and combined AND to show why OCR needs a guard.

If search-behavior improves over direct:

- It supports the cognitive framing.
- Check whether it still underperforms combined AND on absent recall.

If any VLM prompt beats combined AND:

- Reframe combined AND as interpretable and scanpath-grounded rather than state-of-the-art classification.
- Run hard-case overlap analysis to test complementarity.

## Commands

Great Lakes status:

```bash
squeue -u $USER -o "%.18i %.18a %.14P %.28j %.8T %.10M %.12l %.20b %.30R"
```

After jobs finish:

```bash
find "$SEEKUI_WORK/outputs" -maxdepth 1 \
  -name 'vlm_presence_predictions_SeekUI_vlm_presence_*_status_eval.json' \
  -print -exec cat {} \;
```

Copy the results into this file and rerun the main summary on the machine where outputs live.
