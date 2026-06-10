# SeekUI Rolling Results

Last updated: 2026-06-10

This file tracks the current empirical state of the SeekUI follow-up. Update every 1-2 days after new jobs finish.

## Current Thesis

SeekUI behaves like a forced-choice UI visual search model. When the requested target is absent, it often still grounds the query somewhere. A cognitive stopping layer can reduce this false-present behavior, and candidate verification gives a diagnostic upper bound on what better UI candidate extraction could unlock.

## Base Scanpath Reproduction

| Model | AUC | NSS | ScanMatch w/o Duration | SED | STDE |
|---|---:|---:|---:|---:|---:|
| SeekUI | 0.7454 | 1.5495 | 0.3473 | 5.7430 | 0.8728 |
| SeekUI-SFT | 0.6854 | 1.2283 | 0.2714 | 6.1285 | 0.8423 |

Takeaway: released SeekUI checkpoint is stronger than SeekUI-SFT on the original scanpath task in our reproduction.

## Data Audit

| Item | Value |
|---|---:|
| Examples | 1362 |
| Unique images | 646 |
| Unique targets | 850 |
| Target prefix counts | `{'txt': 1362}` |
| Missing images | 0 |

Takeaway: the released subset is text-target only. Non-text and associative directions currently need proxy datasets or new annotation.

## Present/Absent Benchmark

Synthetic benchmark:

```text
1362 present examples
1362 synthetic absent examples
2724 total examples
```

## Present/Absent Status Results

Current core table:

| Model | Variant | Accuracy | Absent Precision | Absent Recall | Absent F1 | Present->Absent | Absent->Present |
|---|---|---:|---:|---:|---:|---:|---:|
| SeekUI | prompt-only | 0.7684 | 0.8749 | 0.6263 | 0.7300 | 122 | 509 |
| SeekUI | cognitive stop, override | 0.8139 | 0.7419 | 0.9626 | 0.8380 | 456 | 51 |
| SeekUI | cognitive stop, present-only | 0.8414 | 0.7981 | 0.9141 | 0.8522 | 315 | 117 |
| SeekUI | oracle candidate verifier | 0.9523 | 0.9173 | 0.9941 | 0.9542 | 122 | 8 |
| SeekUI | OCR verifier, threshold 0.70 | 0.7070 | 0.6323 | 0.9897 | 0.7716 | 784 | 14 |
| SeekUI-SFT | prompt-only | 0.7430 | 0.8761 | 0.5661 | 0.6878 | 109 | 591 |
| SeekUI-SFT | cognitive stop, override | 0.6711 | 0.6122 | 0.9332 | 0.7394 | 805 | 91 |
| SeekUI-SFT | cognitive stop, present-only | 0.7375 | 0.6704 | 0.9347 | 0.7807 | 626 | 89 |
| SeekUI-SFT | oracle candidate verifier | 0.9548 | 0.9252 | 0.9897 | 0.9564 | 109 | 14 |
| SeekUI-SFT | OCR verifier, threshold 0.70 | 0.7001 | 0.6272 | 0.9868 | 0.7669 | 799 | 18 |

Important interpretation:

- Cognitive stopping is the strongest practical non-oracle result for SeekUI so far.
- Oracle candidate verifier is a diagnostic upper bound because it uses annotated same-screen candidate inventory.
- OCR-only verifier catches absent cases but over-rejects present cases.

## OCR Threshold Sweep

Best OCR-only settings from sweep:

| Model | Criterion | Threshold | Accuracy | Absent Precision | Absent Recall | Absent F1 | Present->Absent | Absent->Present |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| SeekUI | best F1 | 0.50 | 0.7610 | 0.6931 | 0.9369 | 0.7968 | 565 | 86 |
| SeekUI | best accuracy | 0.40 | 0.7797 | 0.7468 | 0.8465 | 0.7935 | 391 | 209 |
| SeekUI-SFT | best F1 | 0.55 | 0.7445 | 0.6701 | 0.9633 | 0.7904 | 646 | 50 |
| SeekUI-SFT | best accuracy | 0.40 | 0.7628 | 0.7390 | 0.8128 | 0.7741 | 391 | 255 |

Takeaway: OCR-only improves absent F1 over prompt-only but does not clearly beat cognitive stopping, especially for SeekUI.

## Dev/Test Validation

Random split, threshold selected on dev:

| Model | Test Variant | Accuracy | Absent Precision | Absent Recall | Absent F1 |
|---|---|---:|---:|---:|---:|
| SeekUI | prompt-only | 0.7805 | 0.8882 | 0.6417 | 0.7451 |
| SeekUI | present-only stopping | 0.8421 | 0.7972 | 0.9178 | 0.8532 |
| SeekUI-SFT | prompt-only | 0.7452 | 0.8866 | 0.5624 | 0.6882 |
| SeekUI-SFT | present-only stopping | 0.7349 | 0.6688 | 0.9310 | 0.7784 |

Bootstrap 95% CI on held-out test:

| Model | Delta Absent F1 | 95% CI | Delta Accuracy | 95% CI |
|---|---:|---|---:|---|
| SeekUI | +0.1079 | [0.0798, 0.1353] | +0.0616 | [0.0374, 0.0852] |
| SeekUI-SFT | +0.0893 | [0.0547, 0.1224] | -0.0109 | [-0.0441, 0.0228] |

Image split showed the same pattern for SeekUI:

```text
SeekUI absent F1: 0.7347 -> 0.8554
Delta F1 95% CI: [0.0935, 0.1487]
Delta accuracy 95% CI: [0.0500, 0.0977]
```

## Qualitative Case Mining

Cognitive stopping case counts:

| Model | Corrected absent false-present | New present false-absent | Kept absent false-present |
|---|---:|---:|---:|
| SeekUI | 392 | 193 | 117 |
| SeekUI-SFT | 502 | 517 | 89 |

Observed patterns:

- Stopping succeeds when scanpath does not strongly converge to a target-like candidate.
- New false-absent cases often involve small, edge, low-contrast, or weakly OCR-readable targets.
- Kept false-present cases often contain strong distractor controls such as login, upload, play, settings, or menu buttons.

## Pending Results

- Combined cognitive + OCR verifier:
  - `combined_or_present_only`
  - `combined_and_present_only`
- v3 semantic-query jobs.
- Combined-verifier case mining if it improves over cognitive stopping.

## Files To Check

```text
$SEEKUI_WORK/outputs/research_summary_tables/absent_status_core.csv
$SEEKUI_WORK/outputs/devtest_stopping/devtest_stopping_present_only_random.md
$SEEKUI_WORK/outputs/devtest_stopping/devtest_stopping_present_only_image.md
$SEEKUI_WORK/outputs/stopping_cases/
```
