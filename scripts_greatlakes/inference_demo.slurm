#!/usr/bin/env bash
#SBATCH --job-name=seekui-demo
#SBATCH --account=engin1
#SBATCH --partition=spgpu
#SBATCH --gres=gpu:a40:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=48G
#SBATCH --time=00:30:00
#SBATCH --output=seekui-demo-%j.out

set -euo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:-$(pwd)}"
cd "$REPO_ROOT"

SEEKUI_WORK="${SEEKUI_WORK:-/scratch/engin_root/engin1/$USER/seekui}"
export HF_HOME="${HF_HOME:-$SEEKUI_WORK/hf_cache}"
export TRANSFORMERS_CACHE="${TRANSFORMERS_CACHE:-$HF_HOME}"
export PYTHONUNBUFFERED=1

if [[ -n "${CONDA_MODULE:-}" ]]; then
  module load "$CONDA_MODULE"
else
  module load python3.10-anaconda/2023.03
fi
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate "${CONDA_ENV:-seekui}"

MODEL_PATH="${MODEL_PATH:-$SEEKUI_WORK/models/SeekUI}"
OUTPUT_PATH="${OUTPUT_PATH:-$SEEKUI_WORK/outputs/demo_prediction.json}"

python scripts_utah/inference_demo.py \
  --model_path "$MODEL_PATH" \
  --cache_dir "$HF_HOME" \
  --image_path demo/c3f5f9.png \
  --target_text WOMEN \
  --output "$OUTPUT_PATH" \
  --max_new_tokens 256
