# VLM Prompt Ablation Template

Last updated: 2026-06-11

## Question

Can generic VLM yes/no prompting solve target absence, or does the combined scanpath-grounded verifier remain stronger?

## Prompt Variants

| Variant | Intent |
|---|---|
| direct | Ask whether the target is visible. |
| conservative | Only answer present if the target is clearly visible. |
| ocr_aware | Ask the model to check exact text, near text variants, or obvious visual matches. |
| search_behavior | Ask whether a user searching the UI would likely find the target. |
| evidence_aware | Give the VLM the screenshot plus combined scanpath/OCR evidence. |
| evidence_conservative | Same evidence, but bias toward absent unless the target is clearly visible. |
| evidence_rescue_present | Same evidence, but bias toward rescuing present targets over-rejected by the rule. |

## Result Table

| Prompt Variant | Accuracy | Absent Precision | Absent Recall | Absent F1 | Present->Absent | Absent->Present |
|---|---:|---:|---:|---:|---:|---:|
| direct | 0.8510 | 0.9142 | 0.7746 | 0.8386 | 99 | 307 |
| conservative | 0.8605 | 0.8160 | 0.9310 | 0.8697 | 286 | 94 |
| ocr_aware | 0.8924 | 0.8821 | 0.9060 | 0.8939 | 165 | 128 |
| search_behavior | 0.8902 | 0.9136 | 0.8620 | 0.8870 | 111 | 188 |
| combined AND best-F1 | 0.8711 | 0.8115 | 0.9670 | 0.8824 | 306 | 45 |
| evidence_aware | 0.8891 | 0.8308 | 0.9772 | 0.8981 | 271 | 31 |
| evidence_conservative | 0.7529 | 0.6715 | 0.9905 | 0.8004 | 660 | 13 |
| evidence_rescue_present | 0.6219 | 0.8473 | 0.2974 | 0.4402 | 73 | 957 |

Filtered direct baseline:

| Prompt Variant | Accuracy | Absent Precision | Absent Recall | Absent F1 | Present->Absent | Absent->Present |
|---|---:|---:|---:|---:|---:|---:|
| direct filtered | 0.8706 | 0.9020 | 0.8026 | 0.8494 | 99 | 224 |

## Current Interpretation

The GL prompt ablation shows that prompt design matters substantially:

- `direct` is strong but misses many absent cases: absent recall 0.7746.
- `conservative` strongly improves absent recall to 0.9310, but causes many present false-absent errors.
- `ocr_aware` is the best screenshot-only VLM prompt so far: absent F1 0.8939 and accuracy 0.8924.
- `search_behavior` has high precision and accuracy, but lower absent recall than `ocr_aware`.
- `combined AND` has high absent recall among rule-based practical methods: 0.9670, but lower precision and accuracy than `ocr_aware`.
- `evidence_aware` is now the strongest practical variant overall: absent F1 0.8981, accuracy 0.8891, and absent recall 0.9772.
- `evidence_conservative` is too aggressive: absent recall 0.9905 but 660 present false-absent errors.
- `evidence_rescue_present` goes the wrong way: it over-predicts present and misses 957 absent examples.

This changes the framing again: screenshot-only VLM prompting is strong, but the best result comes from giving the VLM scanpath/OCR evidence. Evidence-aware VLM can be framed as a hybrid of semantic screenshot reasoning and interpretable search evidence.

Hard-case overlap supports this revised framing:

- OCR-aware VLM still has 100 capped absent cases where VLM is wrong and combined AND is correct; these have low mean path evidence (0.0373) and low-to-moderate OCR score (0.3613).
- OCR-aware VLM also corrects 100 capped present cases where combined AND is wrong; these have weak path/OCR evidence, suggesting VLM can preserve visible targets that the scanpath verifier over-rejects.
- Both-wrong absent cases have high OCR scores (0.7750), indicating strong distractors or OCR-leak cases.
- Evidence-aware VLM reduces the combined-correct/VLM-wrong absent cases from the 100 cap to 16, while still rescuing 100 capped present cases where combined AND is wrong.
- Evidence-aware both-wrong absent cases are fewer (15) but have very high OCR scores (0.8618), suggesting the remaining absent failures are hard distractor / OCR-leak cases.

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
