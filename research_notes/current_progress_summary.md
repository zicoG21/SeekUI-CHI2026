# Current SeekUI Follow-Up Progress

## Main Direction

We are extending SeekUI from forced-choice target-present visual search to robust UI target search with a stopping/rejection decision:

```text
Given GUI + target cue:
  predict scanpath
  decide present / absent
```

This is motivated by a core limitation of the original setting: SeekUI assumes the target exists. Real UI search also includes cases where the requested target is absent.

## Completed Work

1. Reproduced base SeekUI and SeekUI-SFT evaluation.

SeekUI is stronger than SeekUI-SFT on the original scanpath task:

| Model | AUC | NSS | ScanMatch w/o Duration | SED | STDE |
|---|---:|---:|---:|---:|---:|
| SeekUI | 0.7454 | 1.5495 | 0.3473 | 5.7430 | 0.8728 |
| SeekUI-SFT | 0.6854 | 1.2283 | 0.2714 | 6.1285 | 0.8423 |

2. Audited the released data.

The released subset has 1362 examples, 646 unique images, and text targets only:

```text
target_prefix_counts: {'txt': 1362}
```

This means non-text and associative search should currently be framed as proxy/stress-test experiments unless we add new annotations or new datasets.

3. Built a synthetic present/absent benchmark.

The benchmark contains:

```text
1362 original present examples
1362 synthetic absent hard negatives
2724 total examples
```

4. Evaluated prompt-only absent detection.

Prompt-only SeekUI has a strong false-present problem:

| Model | Accuracy | Absent Precision | Absent Recall | Absent F1 | Absent->Present |
|---|---:|---:|---:|---:|---:|
| SeekUI | 0.7684 | 0.8749 | 0.6263 | 0.7300 | 509 |
| SeekUI-SFT | 0.7430 | 0.8761 | 0.5661 | 0.6878 | 591 |

5. Built prediction-path evidence analysis.

For each model fixation, we compute local target-match evidence from nearby annotated UI candidates:

```text
path_evidence(step) =
  text_similarity(query, nearby_candidate)
  * exp(-distance_to_candidate / radius)
```

Most false-present errors have low path evidence:

```text
SeekUI:     489 / 509 absent false-present errors = 96.1%
SeekUI-SFT: 578 / 591 absent false-present errors = 97.8%
```

This supports the forced-choice hallucination interpretation.

6. Added a cognitive stopping postprocessor.

The strongest practical version is a conservative safety layer:

```text
if original prediction is present and path_best_evidence < threshold:
    change status to absent
else:
    keep original status
```

Full benchmark sweep result:

| Model / Variant | Accuracy | Absent Precision | Absent Recall | Absent F1 | Changed |
|---|---:|---:|---:|---:|---:|
| SeekUI prompt-only | 0.7684 | 0.8749 | 0.6263 | 0.7300 | 0 |
| SeekUI + stopping, present-only | 0.8414 | 0.7981 | 0.9141 | 0.8522 | 585 |
| SeekUI-SFT prompt-only | 0.7430 | 0.8761 | 0.5661 | 0.6878 | 0 |
| SeekUI-SFT + stopping, present-only | 0.7375 | 0.6704 | 0.9347 | 0.7807 | 1019 |

7. Added dev/test validation and bootstrap confidence intervals.

With threshold selected on dev and evaluated on held-out test:

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

This makes the SeekUI stopping-layer result much stronger: the held-out F1 and accuracy improvements are both reliably positive.

8. Built secondary stress tests.

We also built:

- image-cue target-crop benchmark as a multimodal proxy,
- semantic-query benchmark as an associative/functional wording proxy,
- v3 association-first semantic query jobs for a stronger stress test.

These are useful secondary results, but the main contribution is currently target-absent stopping.

## Current Takeaway

The most promising paper claim is:

```text
SeekUI behaves like a forced-choice visual search model.
When the target is absent, it often still grounds the request somewhere.
A simple cognitive stopping layer based on path evidence substantially reduces this failure.
```

The strongest current empirical result is:

```text
SeekUI held-out test absent F1:
0.7451 -> 0.8532

Delta F1:
+0.1079, 95% CI [0.0798, 0.1353]

SeekUI held-out test accuracy:
0.7805 -> 0.8421

Delta accuracy:
+0.0616, 95% CI [0.0374, 0.0852]
```

## Next Steps

1. Add more validation for synthetic absent labels.
2. Mine representative qualitative examples for the cognitive stopping layer.
3. Finish v3 association-first semantic jobs and evaluate split metrics.
4. Consider an OCR/icon proposal version of path evidence to reduce reliance on annotated candidates.
5. Write a short one-page research pitch around target-absent UI search and cognitive stopping.
