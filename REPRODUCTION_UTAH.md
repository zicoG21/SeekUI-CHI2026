# SeekUI Reproduction on Utah CHPC

This is the batch-oriented reproduction path used for Utah CHPC.

## Assumed Layout

```text
$SEEKUI_WORK/
├── data/
│   ├── scanpath_train_explanation.json
│   ├── target2text.json
│   └── vsgui10k-images/
├── models/
│   ├── SeekUI/
│   └── SeekUI_sft/
└── outputs/
```

Set:

```bash
export SEEKUI_WORK=/scratch/general/vast/$USER/seekui
```

## Install Dependencies

```bash
module load miniconda3/25.9.1
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate seekui

bash scripts_utah/install_inference_deps.sh
bash scripts_utah/install_eval_deps.sh
```

Install FlashAttention 2:

```bash
sbatch scripts_utah/install_flash_attn.slurm
```

## Check Inputs

```bash
python scripts_utah/check_reproduction_inputs.py
```

Expected for the current released JSON:

```text
examples             : 1362
unique images in JSON: 646
missing images       : 0
```

## Run All Main Reproduction Jobs

This submits full inference and evaluation for both `SeekUI` and `SeekUI_sft`.

```bash
bash scripts_utah/reproduce_seekui_and_sft.sh
```

The script uses SLURM dependencies so each evaluation starts after its corresponding inference finishes.

## Run One Model Manually

SeekUI:

```bash
MODEL_NAME=SeekUI \
SUBSET_LIMIT=1362 \
OUTPUT_PATH="$SEEKUI_WORK/outputs/predictions_SeekUI_1362.json" \
sbatch scripts_utah/full_inference.slurm
```

SeekUI-SFT:

```bash
MODEL_NAME=SeekUI_sft \
SUBSET_LIMIT=1362 \
OUTPUT_PATH="$SEEKUI_WORK/outputs/predictions_SeekUI_sft_1362.json" \
sbatch scripts_utah/full_inference.slurm
```

Evaluate:

```bash
PREDICTION_FILE="$SEEKUI_WORK/outputs/predictions_SeekUI_1362.json" \
EVAL_COPY="evaluation/test_predictions_SeekUI_1362.json" \
EVAL_LOG="$SEEKUI_WORK/outputs/eval_SeekUI_1362.txt" \
sbatch scripts_utah/evaluate_predictions.slurm
```

## Inspect Results

```bash
cat "$SEEKUI_WORK/outputs/eval_SeekUI_1362.txt"
cat "$SEEKUI_WORK/outputs/eval_SeekUI_sft_1362.txt"
```

Check prediction health:

```bash
python - <<'PY'
import json, os
for name in ["SeekUI", "SeekUI_sft"]:
    p = f"{os.environ['SEEKUI_WORK']}/outputs/predictions_{name}_1362.json"
    data = json.load(open(p))
    print(name, "num:", len(data), "empty:", sum(1 for x in data if not x.get("prediction")))
PY
```
