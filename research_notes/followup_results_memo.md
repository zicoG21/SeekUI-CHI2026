# SeekUI Follow-Up Results Memo

This memo summarizes the completed Utah CHPC follow-up run for robust UI target search beyond the original forced-choice text-target setting.

## Current Status

All tracked follow-up tasks are complete.

```text
Done: 15
Pending: 0
```

Generated artifacts include:

- base SeekUI and SeekUI-SFT predictions,
- base evaluation metrics,
- synthetic present/absent benchmark,
- cognitive stopping baseline,
- image-cue benchmark,
- semantic-query benchmark,
- follow-up predictions for SeekUI and SeekUI-SFT,
- semantic split evaluations,
- SeekUI vs SeekUI-SFT comparison tables,
- manual review summaries,
- final research summary tables.

## Data Audit

The released VSGUI/SeekUI subset contains:

```text
Examples: 1362
Unique images: 646
Unique targets: 850
Target prefixes: {'txt': 1362}
Missing images: 0
```

The key implication is that the released subset is text-target only. Non-text, image-cue, and associative-search experiments should therefore be framed as controlled proxy evaluations derived from text-target examples, not as native non-text or native associative human-search datasets.

## Base Reproduction

SeekUI outperforms SeekUI-SFT on the released base evaluation.

| Model | AUC | NSS | ScanMatch without duration | SED | STDE |
|---|---:|---:|---:|---:|---:|
| SeekUI | 0.7454 | 1.5495 | 0.3473 | 5.7430 | 0.8728 |
| SeekUI-SFT | 0.6854 | 1.2283 | 0.2714 | 6.1285 | 0.8423 |

The comparison table suggests a likely reason: SeekUI-SFT produces shorter scanpaths and lands farther from the target.

```text
Base SeekUI avg prediction length:     5.34
Base SeekUI-SFT avg prediction length: 4.06

Base SeekUI last-to-target distance:     149.58
Base SeekUI-SFT last-to-target distance: 303.64
```

## Target-Absent Benchmark

The present/absent synthetic benchmark contains 2724 examples:

- 1362 present examples,
- 1362 synthetic absent examples.

Prompt-only absent handling is insufficient for both models.

| Model | Accuracy | Absent Precision | Absent Recall | Absent F1 | Present->Absent | Absent->Present |
|---|---:|---:|---:|---:|---:|---:|
| SeekUI | 0.7684 | 0.8749 | 0.6263 | 0.7300 | 122 | 509 |
| SeekUI-SFT | 0.7430 | 0.8761 | 0.5661 | 0.6878 | 109 | 591 |

The main limitation is false-present behavior. SeekUI predicts `present` for 509 absent examples, and SeekUI-SFT predicts `present` for 591 absent examples.

This supports the forced-choice/stopping research direction:

```text
Existing UI scanpath generation models are not reliable stopping models.
They can generate plausible gaze paths, but they often still ground an absent target somewhere on the screen.
```

SeekUI-SFT is not an absent-target improvement over SeekUI. It has lower absent recall and more absent->present errors.

## Prediction-Path Stopping Evidence

We analyzed whether each model's actual predicted fixation path accumulated enough target-match evidence to justify a present decision. For each predicted fixation, the analysis aligns the point to nearby annotated candidates in the same screenshot and computes:

```text
path_evidence(step) =
  text_similarity(query, nearby_candidate)
  * exp(-distance_to_candidate / radius)

path_best_evidence = max_step path_evidence(step)
```

This is not an oracle candidate-search baseline. It only scores evidence along the path the model actually produced.

Key result: most absent false-present errors have very low path evidence.

| Model | Mean Path Evidence | Best Evidence Threshold | Threshold Accuracy | Threshold Absent F1 | Absent False-Present | Low-Evidence False-Present |
|---|---:|---:|---:|---:|---:|---:|
| SeekUI | 0.2273 | 0.20 | 0.8139 | 0.8380 | 509 | 489 / 509 = 96.1% |
| SeekUI-SFT | 0.0911 | 0.10 | 0.6711 | 0.7394 | 591 | 578 / 591 = 97.8% |

Post-hoc cognitive stopping gives a large improvement over prompt-only status prediction. We report two variants:

- `override`: fully re-decides present/absent from path evidence.
- `present_only`: conservative safety layer; only changes low-evidence `present` predictions to `absent`.

| Model / Variant | Accuracy | Absent Precision | Absent Recall | Absent F1 | Changed Predictions |
|---|---:|---:|---:|---:|---:|
| SeekUI prompt-only | 0.7684 | 0.8749 | 0.6263 | 0.7300 | 0 |
| SeekUI + cognitive stop, override | 0.8139 | 0.7419 | 0.9626 | 0.8380 | 988 |
| SeekUI + cognitive stop, present-only | 0.8414 | 0.7981 | 0.9141 | 0.8522 | 585 |
| SeekUI-SFT prompt-only | 0.7430 | 0.8761 | 0.5661 | 0.6878 | 0 |
| SeekUI-SFT + cognitive stop, override | 0.6711 | 0.6122 | 0.9332 | 0.7394 | 1354 |
| SeekUI-SFT + cognitive stop, present-only | 0.7375 | 0.6704 | 0.9347 | 0.7807 | 1019 |

Group means show a clean separation for SeekUI:

| Group | Count | Mean Evidence | Mean Visited Candidate Rate | Mean Prediction Length |
|---|---:|---:|---:|---:|
| absent false-present | 509 | 0.0379 | 0.1297 | 3.16 |
| correct absent | 853 | 0.0480 | 0.1723 | 4.72 |
| correct present | 1240 | 0.4175 | 0.4246 | 4.21 |
| present false-absent | 122 | 0.3381 | 0.2992 | 4.70 |

For SeekUI-SFT, evidence is low overall, consistent with its much shorter scanpaths:

| Group | Count | Mean Evidence | Mean Visited Candidate Rate | Mean Prediction Length |
|---|---:|---:|---:|---:|
| absent false-present | 591 | 0.0275 | 0.0753 | 1.39 |
| correct absent | 771 | 0.0280 | 0.0681 | 1.56 |
| correct present | 1253 | 0.1599 | 0.1121 | 1.57 |
| present false-absent | 109 | 0.0928 | 0.0505 | 1.63 |

Interpretation:

1. The prompt-only present/absent output is not well calibrated to search evidence.
2. False-present predictions are usually not caused by the model finding strong but misleading evidence; they are mostly low-evidence forced-choice guesses.
3. A simple path-evidence stopping rule substantially improves absent F1 for SeekUI, from 0.7300 prompt-only to 0.8380 with aggressive override and 0.8522 with the conservative present-only safety layer at a lower threshold.
4. SeekUI-SFT remains weaker because its paths are too short and visit fewer useful candidates.

## Image-Cue Benchmark

The image-cue benchmark uses target crops as visual cue proxies. It tests whether the model can follow a visual target cue instead of only a text cue.

Prediction health:

| Model | N | Empty | Avg Prediction Length |
|---|---:|---:|---:|
| SeekUI image-cue | 1362 | 0 | 4.64 |
| SeekUI-SFT image-cue | 1362 | 0 | 2.77 |

Comparison summary:

```text
SeekUI image-cue last-to-target distance:     327.17
SeekUI-SFT image-cue last-to-target distance: 429.63
```

Image-cue grounding appears harder than the base text-target setting. The last fixation is farther from the target for both models, and SeekUI-SFT again produces shorter paths.

This is a useful multimodal proxy experiment, but it should not be overclaimed as a native non-text target benchmark because the visual cue is derived from the ground-truth target crop.

## Semantic-Query Benchmark

The semantic-query benchmark contains:

- 1362 exact queries,
- 1330 functional-template queries,
- 32 association-mapping queries.

Prediction health by query type:

| Model | Query Type | N | Predicted Absent Rate | Avg Prediction Length |
|---|---|---:|---:|---:|
| SeekUI | exact | 1362 | 0.0896 | 4.25 |
| SeekUI | functional_template | 1330 | 0.1496 | 4.21 |
| SeekUI | association_mapping | 32 | 0.4375 | 4.34 |
| SeekUI-SFT | exact | 1362 | 0.0800 | 1.57 |
| SeekUI-SFT | functional_template | 1330 | 0.1226 | 1.60 |
| SeekUI-SFT | association_mapping | 32 | 0.3750 | 1.66 |

For SeekUI, shallow functional-template queries are similar to exact queries on scanpath metrics, but association mappings are harder.

| Model | Query Type | AUC | NSS | ScanMatch without duration |
|---|---|---:|---:|---:|
| SeekUI | exact | 0.6933 | 1.3992 | 0.2846 |
| SeekUI | functional_template | 0.6945 | 1.3688 | 0.2752 |
| SeekUI | association_mapping | 0.6492 | 1.2659 | 0.2558 |
| SeekUI-SFT | exact | 0.6047 | 1.1098 | 0.1630 |
| SeekUI-SFT | functional_template | 0.6135 | 1.0581 | 0.1599 |
| SeekUI-SFT | association_mapping | 0.5984 | 1.2230 | 0.1500 |

The association subset is small, so it should be treated as exploratory. Still, the pattern is meaningful: when the query moves away from exact visible text toward functional or associative wording, the model is more likely to fail, reject, or produce weaker scanpaths.

## SeekUI vs SeekUI-SFT Behavior

Across settings, SeekUI-SFT consistently produces shorter scanpaths.

| Setting | SeekUI Avg Len | SeekUI-SFT Avg Len | Delta SFT-SeekUI |
|---|---:|---:|---:|
| Base | 5.34 | 4.06 | -1.28 |
| Image cue | 4.64 | 2.77 | -1.86 |
| Present/absent | 4.19 | 1.53 | -2.67 |
| Semantic query | 4.23 | 1.59 | -2.64 |

SeekUI-SFT also tends to land farther from the target.

| Setting | SeekUI Last-to-Target | SeekUI-SFT Last-to-Target |
|---|---:|---:|
| Base | 149.58 | 303.64 |
| Image cue | 327.17 | 429.63 |
| Present/absent | 222.30 | 386.89 |
| Semantic query | 229.68 | 381.42 |

This suggests that the SFT checkpoint may compress or truncate search behavior rather than improve robust target grounding.

## Manual Review

Manual review is now populated.

```text
review_query_valid: 194/200 valid = 97%
review_target_visible: 120 annotated
review_prediction_reasonable: 0 annotated
```

For absent visual audit:

```text
17 valid absent
1 ambiguous semantic match
1 ambiguous partial token
1 target visible / invalid synthetic absent
80 still need visual review
```

For semantic-query audit:

```text
94 valid query
6 low-quality semantic query
```

The manual review supports using the current benchmark as a pilot, while also making the main caveat explicit: the synthetic absent dataset is useful but requires more visual validation before being treated as a fully reliable benchmark.

## Annotation-Assisted Absent Validation

We added an annotation-assisted text-conflict validator to check whether synthetic absent targets appear in destination screenshots under another target annotation.

The refined validation found:

```text
Absent examples: 1362
Likely text conflicts: 8
Clean absent examples: 1354
Suspicious rate: 0.59%
```

The suspicious cases are mostly generic search targets:

```text
Search -> search gymshark
Search for anything -> Search
search local12.com -> SEARCH
Search -> Enter keywords to search
search github -> Search
Search -> [Search]
Search -> Search software...
```

This strengthens the absent benchmark caveat without undermining the benchmark. The synthetic absent set is mostly clean by available annotations, but generic UI functions such as search require extra validation because a destination screen may contain a semantically equivalent search field under a different annotation.

## Main Findings

1. The released VSGUI/SeekUI subset is text-target only.

This limits claims about native non-text or associative search. Current image-cue and semantic-query results are controlled proxy evaluations.

2. SeekUI has a clear forced-choice/stopping limitation.

Even with prompt-only absent handling, SeekUI predicts present for 509/1362 absent examples. SeekUI-SFT predicts present for 591/1362 absent examples.

3. Prediction-path evidence explains much of the stopping failure.

For SeekUI, 489/509 absent false-present errors have low path evidence. A path-evidence threshold improves absent F1 to 0.8380, suggesting that a cognitive stopping layer could reject many forced-choice guesses without retraining the base generator.

4. SeekUI-SFT is not more robust in these follow-up settings.

It produces shorter scanpaths, lower base metrics, lower absent recall, and larger final distances to the target.

5. Image-cue search is feasible but harder.

Both models produce non-empty outputs, but final fixations are farther from the target than in the base text setting.

6. Shallow semantic templates are not enough to stress the model strongly.

Functional-template queries are close to exact text queries. Association mappings show a stronger drop, but the current subset is only 32 examples.

## Recommended Research Direction

The strongest near-term paper direction is:

```text
Robust UI visual search beyond forced choice:
Can models decide when to stop or reject an absent target?
```

The target-absent/stopping direction is stronger than leading with multimodal or associative search because:

- it has the clearest limitation,
- it has a full 2724-example benchmark,
- it has interpretable metrics,
- it directly connects to cognitive visual search,
- current models visibly fail on it.

Image-cue and semantic-query results should be used as secondary stress tests:

- image-cue as a multimodal proxy,
- semantic/association mapping as a small robustness pilot,
- stronger association-first v3 benchmark as the next experiment.

## Next Steps

1. Generate prediction-review artifacts for failure cases.

Focus on:

- absent->present false positives,
- semantic association failures,
- image-cue large target-distance examples,
- SFT one-fixation failures.

2. Improve absent validation.

Run OCR or visual review on more synthetic absent examples. The current 20-example visual audit found 1 invalid and 2 ambiguous samples. Annotation-assisted text validation found 8 likely text conflicts out of 1362 absent examples, mostly search-related.

3. Run stronger associative v3 benchmark.

Use `scripts_research/associative_query_mapping.json` and `--selection-policy association_first` to increase the number of stronger functional/associative queries.

4. Prototype a cognitive stopping model.

The next model should not only generate scanpaths; it should explicitly decide:

```text
present / absent / uncertain
```

Possible stopping signals:

- target-text similarity,
- visual-region confidence,
- repeated low-confidence fixations,
- screen coverage,
- inhibition of return,
- movement cost,
- uncertainty threshold.

The first practical version can be a post-hoc stopping layer:

```text
if path_best_evidence < threshold:
    status = absent
else:
    status = present
```

For SeekUI, this already improves absent F1 from 0.7300 to 0.8380 on the synthetic present/absent benchmark.
