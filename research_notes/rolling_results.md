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

Sanity audit:

| Check | Value |
|---|---:|
| Unique images | 646 |
| Present unique images | 646 |
| Absent unique images | 566 |
| Shared present/absent images | 566 |
| Annotation conflicts | 4 |
| OCR leak absent examples | 225 / 1362 = 0.1652 |

Split leakage:

| Split | Dev examples | Test examples | Shared images | Shared target texts | Shared image-target pairs |
|---|---:|---:|---:|---:|---:|
| Random | 1362 | 1362 | 507 | 495 | 217 |
| Image | 1395 | 1329 | 0 | 465 | 0 |

Takeaway: annotation conflicts are low, so the synthetic absent labels are mostly not contradicted by known target annotations. However, random split has heavy image and image-target leakage; image split should be treated as the more credible held-out evaluation. OCR leak rate is nontrivial, so OCR-based verifier results must be interpreted carefully: some "absent" examples contain visually similar or identical OCR text.

## Present/Absent Status Results

Current core table:

| Model | Variant | Accuracy | Absent Precision | Absent Recall | Absent F1 | Present->Absent | Absent->Present |
|---|---|---:|---:|---:|---:|---:|---:|
| SeekUI | prompt-only | 0.7684 | 0.8749 | 0.6263 | 0.7300 | 122 | 509 |
| SeekUI | cognitive stop, override | 0.8139 | 0.7419 | 0.9626 | 0.8380 | 456 | 51 |
| SeekUI | cognitive stop, present-only | 0.8414 | 0.7981 | 0.9141 | 0.8522 | 315 | 117 |
| SeekUI | oracle candidate verifier | 0.9523 | 0.9173 | 0.9941 | 0.9542 | 122 | 8 |
| SeekUI | OCR verifier, threshold 0.70 | 0.7070 | 0.6323 | 0.9897 | 0.7716 | 784 | 14 |
| SeekUI | combined OR, default | 0.7834 | 0.7091 | 0.9611 | 0.8161 | 537 | 53 |
| SeekUI | combined AND, default | 0.8377 | 0.8657 | 0.7996 | 0.8313 | 169 | 273 |
| SeekUI-SFT | prompt-only | 0.7430 | 0.8761 | 0.5661 | 0.6878 | 109 | 591 |
| SeekUI-SFT | cognitive stop, override | 0.6711 | 0.6122 | 0.9332 | 0.7394 | 805 | 91 |
| SeekUI-SFT | cognitive stop, present-only | 0.7375 | 0.6704 | 0.9347 | 0.7807 | 626 | 89 |
| SeekUI-SFT | oracle candidate verifier | 0.9548 | 0.9252 | 0.9897 | 0.9564 | 109 | 14 |
| SeekUI-SFT | OCR verifier, threshold 0.70 | 0.7001 | 0.6272 | 0.9868 | 0.7669 | 799 | 18 |
| SeekUI-SFT | combined OR, default | 0.6920 | 0.6233 | 0.9706 | 0.7591 | 799 | 40 |
| SeekUI-SFT | combined AND, default | 0.8084 | 0.8292 | 0.7768 | 0.8021 | 218 | 304 |

Important interpretation:

- Cognitive stopping is the strongest practical non-oracle result for SeekUI so far.
- Combined `AND` is the strongest current non-oracle result after threshold sweep.
- Oracle candidate verifier is a diagnostic upper bound because it uses annotated same-screen candidate inventory.
- OCR-only verifier catches absent cases but over-rejects present cases.
- Combined `OR` is too aggressive or collapses to the stronger single signal; combined `AND` balances OCR false rejection against cognitive evidence.

## OCR Threshold Sweep

Best OCR-only settings from sweep:

| Model | Criterion | Threshold | Accuracy | Absent Precision | Absent Recall | Absent F1 | Present->Absent | Absent->Present |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| SeekUI | best F1 | 0.50 | 0.7610 | 0.6931 | 0.9369 | 0.7968 | 565 | 86 |
| SeekUI | best accuracy | 0.40 | 0.7797 | 0.7468 | 0.8465 | 0.7935 | 391 | 209 |
| SeekUI-SFT | best F1 | 0.55 | 0.7445 | 0.6701 | 0.9633 | 0.7904 | 646 | 50 |
| SeekUI-SFT | best accuracy | 0.40 | 0.7628 | 0.7390 | 0.8128 | 0.7741 | 391 | 255 |

Takeaway: OCR-only improves absent F1 over prompt-only but does not clearly beat cognitive stopping, especially for SeekUI.

## Combined Cognitive + OCR Verifier

Default combined settings used:

```text
cognitive_threshold = 0.05
ocr_threshold = 0.40
mode = present_only
```

Default `AND` is conservative and reduces OCR false rejection; default `OR` is generally too aggressive.

Best threshold-sweep results:

| Model | Rule | Criterion | Cognitive Threshold | OCR Threshold | Accuracy | Absent Precision | Absent Recall | Absent F1 | Present->Absent | Absent->Present |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| SeekUI | OR | best F1/accuracy | 0.05 | 0.00 | 0.8414 | 0.7981 | 0.9141 | 0.8522 | 315 | 117 |
| SeekUI | AND | best F1 | 0.20 | 0.60 | 0.8711 | 0.8115 | 0.9670 | 0.8824 | 306 | 45 |
| SeekUI | AND | best accuracy | 0.10 | 0.55 | 0.8730 | 0.8369 | 0.9266 | 0.8794 | 246 | 100 |
| SeekUI-SFT | OR | best F1 | 0.00 | 0.55 | 0.7445 | 0.6701 | 0.9633 | 0.7904 | 646 | 50 |
| SeekUI-SFT | OR | best accuracy | 0.00 | 0.40 | 0.7628 | 0.7390 | 0.8128 | 0.7741 | 391 | 255 |
| SeekUI-SFT | AND | best F1 | 0.05 | 0.55 | 0.8278 | 0.7853 | 0.9023 | 0.8398 | 336 | 133 |
| SeekUI-SFT | AND | best accuracy | 0.05 | 0.50 | 0.8286 | 0.8030 | 0.8708 | 0.8355 | 291 | 176 |

Takeaway:

- `OR` does not add value: for SeekUI it collapses to cognitive stopping; for SeekUI-SFT it collapses to OCR-only.
- `AND` is the current best non-oracle method:
  - SeekUI absent F1: `0.8522 -> 0.8824`
  - SeekUI accuracy: `0.8414 -> 0.8711/0.8730`
  - SeekUI-SFT absent F1: `0.7807 -> 0.8398`
  - SeekUI-SFT accuracy: `0.7375 -> 0.8278/0.8286`
- Interpretation: cognitive stopping catches low scanpath evidence; OCR acts as a guard against over-rejecting present targets when visible text evidence exists. Requiring both to be low gives a better precision/recall tradeoff.

## Filtered Sensitivity Check

Filtered benchmark removes:

```text
4 annotation-conflict absent examples
225 OCR-leak absent examples
227 total excluded examples
2497 examples kept
```

Filtered status results:

| Model | Variant | Accuracy | Absent Precision | Absent Recall | Absent F1 | Present->Absent | Absent->Present |
|---|---|---:|---:|---:|---:|---:|---:|
| SeekUI | prompt-only | 0.7853 | 0.8553 | 0.6352 | 0.7290 | 122 | 414 |
| SeekUI | cognitive stop | 0.8402 | 0.7694 | 0.9260 | 0.8405 | 315 | 84 |
| SeekUI | OCR-only | 0.6860 | 0.5915 | 1.0000 | 0.7433 | 784 | 0 |
| SeekUI | combined AND default | 0.8606 | 0.8498 | 0.8423 | 0.8460 | 169 | 179 |
| SeekUI | combined AND best-F1 | 0.8726 | 0.7859 | 0.9894 | 0.8760 | 306 | 12 |
| SeekUI-SFT | prompt-only | 0.7661 | 0.8583 | 0.5815 | 0.6933 | 109 | 475 |
| SeekUI-SFT | cognitive stop | 0.7213 | 0.6298 | 0.9383 | 0.7537 | 626 | 70 |
| SeekUI-SFT | OCR-only | 0.6800 | 0.5869 | 1.0000 | 0.7397 | 799 | 0 |
| SeekUI-SFT | combined AND default | 0.8370 | 0.8127 | 0.8335 | 0.8230 | 218 | 189 |
| SeekUI-SFT | combined AND best-F1 | 0.8370 | 0.7600 | 0.9374 | 0.8394 | 336 | 71 |

Takeaway: filtering out suspicious absent rows does not remove the main effect. For SeekUI, combined AND best-F1 remains strongest (`F1=0.8760`, `accuracy=0.8726`) and still beats cognitive stopping (`F1=0.8405`, `accuracy=0.8402`). For SFT, combined AND best-F1 is also strongest by absent F1 (`0.8394`) and combined default ties it on accuracy (`0.8370`) with higher precision.

## Dev/Test Validation

### Cognitive Stopping

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

### Combined Cognitive + OCR Verifier

Random split, thresholds selected on dev:

| Model | Test Variant | Cog Thresh | OCR Thresh | Accuracy | Absent Precision | Absent Recall | Absent F1 |
|---|---|---:|---:|---:|---:|---:|---:|
| SeekUI | prompt-only |  |  | 0.7805 | 0.8882 | 0.6417 | 0.7451 |
| SeekUI | combined AND | 0.15 | 0.60 | 0.8634 | 0.8121 | 0.9457 | 0.8738 |
| SeekUI-SFT | prompt-only |  |  | 0.7452 | 0.8866 | 0.5624 | 0.6882 |
| SeekUI-SFT | combined AND | 0.05 | 0.60 | 0.8209 | 0.7755 | 0.9031 | 0.8345 |

Random split bootstrap 95% CI:

| Model | Delta Absent F1 | 95% CI | Delta Accuracy | 95% CI |
|---|---:|---|---:|---|
| SeekUI | +0.1285 | [0.1001, 0.1573] | +0.0830 | [0.0580, 0.1087] |
| SeekUI-SFT | +0.1453 | [0.1143, 0.1770] | +0.0750 | [0.0462, 0.1035] |

Image split, thresholds selected on dev:

| Model | Test Variant | Cog Thresh | OCR Thresh | Accuracy | Absent Precision | Absent Recall | Absent F1 |
|---|---|---:|---:|---:|---:|---:|---:|
| SeekUI | prompt-only |  |  | 0.7708 | 0.8745 | 0.6334 | 0.7347 |
| SeekUI | combined AND | 0.25 | 0.55 | 0.8692 | 0.8127 | 0.9604 | 0.8804 |
| SeekUI-SFT | prompt-only |  |  | 0.7325 | 0.8647 | 0.5528 | 0.6744 |
| SeekUI-SFT | combined AND | 0.05 | 0.55 | 0.8148 | 0.7749 | 0.8886 | 0.8279 |

Image split bootstrap 95% CI:

| Model | Delta Absent F1 | 95% CI | Delta Accuracy | 95% CI |
|---|---:|---|---:|---|
| SeekUI | +0.1459 | [0.1167, 0.1739] | +0.0984 | [0.0720, 0.1220] |
| SeekUI-SFT | +0.1535 | [0.1232, 0.1834] | +0.0820 | [0.0558, 0.1080] |

Takeaway: combined AND holds up under held-out threshold selection. It improves both absent F1 and accuracy with positive bootstrap CIs on random and image splits. This is now the strongest non-oracle result.

Because the sanity audit shows heavy random split image leakage, the image-split combined result is the cleaner headline:

```text
SeekUI image split absent F1: 0.7347 -> 0.8804
SeekUI image split accuracy: 0.7708 -> 0.8692
Delta F1 95% CI: [0.1167, 0.1739]
Delta accuracy 95% CI: [0.0720, 0.1220]
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

Combined AND case mining, SeekUI best-F1 thresholds:

```text
cognitive_threshold = 0.20
ocr_threshold = 0.60
```

| Model | Corrected absent false-present | New present false-absent | Corrected present false-absent | Kept absent false-present |
|---|---:|---:|---:|---:|
| SeekUI + combined AND | 464 | 184 | 0 | 45 |
| SeekUI-SFT + combined AND | 458 | 227 | 0 | 133 |

Compared with cognitive stopping alone for SeekUI:

```text
corrected absent false-present: 392 -> 464
new present false-absent:       193 -> 184
kept absent false-present:      117 -> 45
```

Compared with cognitive stopping alone for SeekUI-SFT:

```text
corrected absent false-present: 502 -> 458
new present false-absent:       517 -> 227
kept absent false-present:       89 -> 133
```

Takeaway: combined AND improves the qualitative error profile for SeekUI: it fixes more absent hallucinations, creates slightly fewer present false-absent errors, and leaves far fewer absent false-present failures. For SeekUI-SFT the tradeoff is different: combined AND fixes fewer absent hallucinations than cognitive-only, but it greatly reduces new false-absent errors, which matches the stronger overall F1/accuracy tradeoff.

Contact-sheet packages:

```text
$SEEKUI_WORK/outputs/combined_cases/SeekUI_and_present_only_best_f1_contact_sheets.tgz
$SEEKUI_WORK/outputs/combined_cases/SeekUI_sft_and_present_only_best_f1_contact_sheets.tgz
```

## Pending Results

- v3 semantic-query jobs.
- Combined contact-sheet analysis.
- Combined heuristic error taxonomy via `scripts_utah/summarize_combined_error_taxonomy.slurm`.
- Behavioral scanpath metrics via `scripts_utah/summarize_behavioral_metrics.slurm`.

## Files To Check

```text
$SEEKUI_WORK/outputs/research_summary_tables/absent_status_core.csv
$SEEKUI_WORK/outputs/devtest_combined/combined_devtest_random.md
$SEEKUI_WORK/outputs/devtest_combined/combined_devtest_image.md
$SEEKUI_WORK/outputs/combined_cases/
$SEEKUI_WORK/outputs/combined_error_taxonomy/combined_error_taxonomy_summary.md
$SEEKUI_WORK/outputs/behavioral_metrics/behavioral_metrics_summary.md
$SEEKUI_WORK/outputs/absent_sanity/absent_benchmark_sanity.md
```
