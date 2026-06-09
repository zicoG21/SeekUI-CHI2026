# Utah CHPC Preparation

This folder contains small helper scripts for preparing and smoke-testing SeekUI on Utah CHPC before spending longer GPU time.

## 1. Prepare cache and model files

Run this on a login node or CPU job. Choose a shared filesystem path that is visible from GPU nodes.

```bash
cd /path/to/SeekUI-CHI2026
export SEEKUI_WORK=${SCRATCH:-$PWD/.scratch}/seekui
module load miniconda3/25.9.1
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate seekui
bash scripts_utah/install_inference_deps.sh
bash scripts_utah/download_models.sh
```

This downloads:

- `sushizixin1/SeekUI`
- `sushizixin1/SeekUI_sft`

into:

```text
$SEEKUI_WORK/models/
$SEEKUI_WORK/hf_cache/
```

## 2. Download VSGUI data

```bash
bash scripts_utah/download_data.sh
```

This downloads the files listed in `data/README.md` into:

```text
$SEEKUI_WORK/data/
```

## 3. Run a one-image GPU smoke test

Submit the SLURM template after editing the account, partition, GPU type, and conda activation lines if needed.

```bash
sbatch scripts_utah/inference_demo.slurm
```

The script runs inference on `demo/c3f5f9.png` and writes:

```text
$SEEKUI_WORK/outputs/demo_prediction.json
```

## 3.5. Install FlashAttention 2

For production inference/training, install FlashAttention 2 inside a GPU job:

```bash
sbatch scripts_utah/install_flash_attn.slurm
```

Check the log with:

```bash
tail -n 120 seekui-fa2-*.out
```

## 4. Run a real-data subset smoke test

After placing `scanpath_train_explanation.json`, `target2text.json`, and at least some images under `$SEEKUI_WORK/data`, submit:

```bash
sbatch scripts_utah/inference_subset.slurm
```

This first creates:

```text
$SEEKUI_WORK/data/subset_available_10.json
```

then writes predictions to:

```text
$SEEKUI_WORK/outputs/subset_predictions.json
```

## 5. Install Evaluation Dependencies

```bash
bash scripts_utah/install_eval_deps.sh
```

Then run:

```bash
cd evaluation
python evaluation.py --prediction_file test_predictions_seekui_1362.json
```

## Notes

- Prefer `a40`, `a6000`, `l40`, `l40s`, `a100`, `a800`, `h100`, or `h200` for SeekUI.
- Avoid small MIG slices for training. They are fine only for basic environment checks.
- Guest GPU partitions are preemptable, so keep smoke tests short and use checkpoints for longer training.
