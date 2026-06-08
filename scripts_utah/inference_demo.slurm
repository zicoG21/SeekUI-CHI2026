#!/usr/bin/env bash
#SBATCH --job-name=seekui-demo
#SBATCH --account=owner-gpu-guest
#SBATCH --partition=notchpeak-gpu-guest
#SBATCH --gres=gpu:a40:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=48G
#SBATCH --time=00:30:00
#SBATCH --output=seekui-demo-%j.out

set -euo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:-$(pwd)}"
cd "$REPO_ROOT"

SEEKUI_WORK="${SEEKUI_WORK:-${SCRATCH:-$REPO_ROOT/.scratch}/seekui}"
export HF_HOME="${HF_HOME:-$SEEKUI_WORK/hf_cache}"
export TRANSFORMERS_CACHE="${TRANSFORMERS_CACHE:-$HF_HOME}"
export PYTHONUNBUFFERED=1

# Edit these lines for your CHPC Python environment.
# Examples:
#   module load miniconda3
#   source activate seekui
# or:
#   source ~/miniconda3/etc/profile.d/conda.sh
#   conda activate seekui

MODEL_PATH="${MODEL_PATH:-$SEEKUI_WORK/models/SeekUI}"
OUTPUT_PATH="${OUTPUT_PATH:-$SEEKUI_WORK/outputs/demo_prediction.json}"

python scripts_utah/inference_demo.py \
  --model_path "$MODEL_PATH" \
  --cache_dir "$HF_HOME" \
  --image_path demo/c3f5f9.png \
  --target_text WOMEN \
  --output "$OUTPUT_PATH" \
  --max_new_tokens 256
