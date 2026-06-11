# Real Absent Case Analysis

This analysis reconstructs prompt-only and combined-AND decisions from the real-absent eval set, stopping evidence, and OCR candidates.

## Method Metrics

| Method | N | Acc | Precision | Recall | F1 | Present->Absent | Absent->Present |
|---|---:|---:|---:|---:|---:|---:|---:|
| prompt_only_real_absent | 100 | 0.8200 | 0.9444 | 0.6800 | 0.7907 | 2 | 16 |
| combined_and_present_only | 100 | 0.8600 | 0.9091 | 0.8000 | 0.8511 | 4 | 10 |
| combined_and_present_only_best_f1 | 100 | 0.9100 | 0.8596 | 0.9800 | 0.9159 | 8 | 1 |

## Case Groups

| Group | Count | Interpretation |
|---|---:|---|
| Prompt wrong, combined correct | 15 | Combined fixes prompt-only mistakes; mostly absent safety gains. |
| Prompt correct, combined wrong | 6 | Cost of the verifier; visible targets may be over-rejected. |
| Both wrong | 3 | Hard residual cases where both methods miss the label. |
| Both correct | 76 | Stable cases where verifier preserves the correct decision. |
| Absent false-present corrected by combined | 15 | Target-absent queries that prompt-only hallucinated but combined rejected. |
| New present false-absent from combined | 6 | Present targets newly rejected by combined. |
| Absent false-present kept by combined | 1 | Residual target-absent hallucinations after combined. |

## Key Takeaways

- Combined best-F1 reduces absent->present errors from 16 to 1 on the 100-row realistic validation set.
- The main tradeoff is present->absent errors, increasing from 2 to 8.
- Per-example VLM predictions are not included in the local archive, so this file reports VLM only through aggregate tables elsewhere.

Aggregate real-absent VLM results source: `paper_assets/tables/realistic_absent_validation.md`
