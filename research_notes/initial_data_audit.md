# Initial VSGUI/SeekUI Data Audit

This note records the first local audit of `data/scanpath_train_think.json`, which matches the released SeekUI-style explanation data format.

Command:

```bash
python scripts_research/audit_vsgui.py \
  --scanpath data/scanpath_train_think.json \
  --target2text data/target2text.json \
  --out-dir /tmp/seekui_audit_test
```

## Summary

```text
examples: 1362
unique images: 646
unique targets: 850
unique non-empty target texts: 764
empty target text examples: 2
target2text mismatches: 0
examples with conversations: 1362
target center inside image: 1362 / 1362
target bbox inside image: 1348 / 1362
target bbox positive area: 1362 / 1362
repeated image-target pairs: 374
```

## Target Modality

```text
target_prefix_counts:
  txt: 1362
```

Immediate implication: the currently available released JSON is essentially a text-target benchmark. The non-text / icon / image-cue direction likely needs either another split/source from VSGUI10K, synthetic target-crop construction, or new annotation.

## Scanpath Length

```text
min: 1
p25: 4
median: 6
mean: 7.58
p75: 10
max: 20
```

## Fixation Duration

```text
min: 0.0 s
p25: 0.22656 s
median: 0.30664 s
mean: 0.34635 s
p75: 0.42041 s
max: 2.94385 s
```

## Research Consequences

- Target-absent can be started with synthetic hard negatives now.
- Non-text target search cannot be evaluated directly from this JSON alone.
- Cognitive stopping is a good fit because the current model is forced-choice and the data has enough target/image repetitions to construct controlled negatives.
- Before claiming true target absence, synthetic negatives should be audited with OCR/manual checks because the construction only guarantees absence relative to current annotations.
