# Research Scripts

These scripts support follow-up experiments that do not require changing or retraining SeekUI first.

## 1. Audit Current Data

```bash
python scripts_research/audit_vsgui.py \
  --scanpath "$SEEKUI_WORK/data/scanpath_train_explanation.json" \
  --target2text "$SEEKUI_WORK/data/target2text.json" \
  --image-root "$SEEKUI_WORK/data" \
  --out-dir "$SEEKUI_WORK/outputs/data_audit"
```

## 2. Build Synthetic Target-Absent Data

```bash
python scripts_research/build_absent_dataset.py \
  --scanpath "$SEEKUI_WORK/data/scanpath_train_explanation.json" \
  --target2text "$SEEKUI_WORK/data/target2text.json" \
  --output "$SEEKUI_WORK/data/absent_synthetic_1362.json" \
  --mixed-output "$SEEKUI_WORK/data/present_absent_synthetic_2724.json" \
  --limit 1362 \
  --seed 42
```

Validate it:

```bash
python scripts_research/validate_absent_dataset.py \
  --reference "$SEEKUI_WORK/data/scanpath_train_explanation.json" \
  --dataset "$SEEKUI_WORK/data/present_absent_synthetic_2724.json" \
  --target2text "$SEEKUI_WORK/data/target2text.json" \
  --output "$SEEKUI_WORK/outputs/absent_validation.json" \
  --fail-on-conflict
```

## 3. Visualize Examples

```bash
python scripts_research/visualize_scanpaths.py \
  --json "$SEEKUI_WORK/data/present_absent_synthetic_2724.json" \
  --image-root "$SEEKUI_WORK/data" \
  --out-dir "$SEEKUI_WORK/outputs/visualizations/absent_examples" \
  --status absent \
  --limit 20
```

For predictions:

```bash
python scripts_research/visualize_scanpaths.py \
  --json "$SEEKUI_WORK/outputs/predictions_SeekUI_1362.json" \
  --image-root "$SEEKUI_WORK/data" \
  --out-dir "$SEEKUI_WORK/outputs/visualizations/seekui_predictions" \
  --limit 20
```

## 4. Evaluate Prompt-Only Absent Predictions

After running `scripts_utah/absent_inference.slurm`:

```bash
python scripts_research/evaluate_absent_status.py \
  --predictions "$SEEKUI_WORK/outputs/present_absent_predictions_SeekUI.json" \
  --output "$SEEKUI_WORK/outputs/present_absent_predictions_SeekUI_status_eval.json"
```

## 5. Run Minimal Cognitive Stopping Baseline

```bash
python scripts_research/cognitive_stopping_baseline.py \
  --reference "$SEEKUI_WORK/data/scanpath_train_explanation.json" \
  --eval "$SEEKUI_WORK/data/present_absent_synthetic_2724.json" \
  --target2text "$SEEKUI_WORK/data/target2text.json" \
  --out-dir "$SEEKUI_WORK/outputs/cognitive_stopping"
```
