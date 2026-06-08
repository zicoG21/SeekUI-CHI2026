# Utah CHPC Preparation

This folder contains small helper scripts for preparing and smoke-testing SeekUI on Utah CHPC before spending longer GPU time.

## 1. Prepare cache and model files

Run this on a login node or CPU job. Choose a shared filesystem path that is visible from GPU nodes.

```bash
cd /path/to/SeekUI-CHI2026
export SEEKUI_WORK=${SCRATCH:-$PWD/.scratch}/seekui
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

## 2. Run a one-image GPU smoke test

Submit the SLURM template after editing the account, partition, GPU type, and conda activation lines if needed.

```bash
sbatch scripts_utah/inference_demo.slurm
```

The script runs inference on `demo/c3f5f9.png` and writes:

```text
$SEEKUI_WORK/outputs/demo_prediction.json
```

## Notes

- Prefer `a40`, `a6000`, `l40`, `l40s`, `a100`, `a800`, `h100`, or `h200` for SeekUI.
- Avoid small MIG slices for training. They are fine only for basic environment checks.
- Guest GPU partitions are preemptable, so keep smoke tests short and use checkpoints for longer training.
