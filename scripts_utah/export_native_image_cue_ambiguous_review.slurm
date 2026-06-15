#!/usr/bin/env bash
#SBATCH --job-name=seekui-native-img-review
#SBATCH --account=notchpeak-shared-short
#SBATCH --partition=notchpeak-shared-short
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:30:00
#SBATCH --output=seekui-native-img-review-%j.out

set -euo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:-$(pwd)}"
cd "$REPO_ROOT"

SEEKUI_WORK="${SEEKUI_WORK:-${SCRATCH:-$REPO_ROOT/.scratch}/seekui}"
OSF_DIR="${OSF_DIR:-$SEEKUI_WORK/data/osf_vsgui10k}"
NATIVE_DIR="${NATIVE_DIR:-$SEEKUI_WORK/outputs/native_vsgui10k}"
TRIALS_JSON="${TRIALS_JSON:-$NATIVE_DIR/native_vsgui10k_trials.json}"
IMAGE_ROOT="${IMAGE_ROOT:-$SEEKUI_WORK/data}"
OUT_DIR="${OUT_DIR:-$NATIVE_DIR/processed_v2/image_cue_resolution/ambiguous_review}"

module load miniconda3/25.9.1
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate seekui

args=(
  --trials-json "$TRIALS_JSON"
  --image-root "$IMAGE_ROOT"
  --out-dir "$OUT_DIR"
  --fixations-csv "$OSF_DIR/extracted/data/vsgui10k_fixations.csv"
  --search-root "$OSF_DIR/extracted"
  --search-root "$SEEKUI_WORK/data"
)

if [[ -f "$OSF_DIR/VSGUI10K.zip" ]]; then
  args+=(--zip-path "$OSF_DIR/VSGUI10K.zip")
fi

if [[ "${REVIEW_LIMIT:-0}" != "0" ]]; then
  args+=(--limit "$REVIEW_LIMIT")
fi

python scripts_research/export_native_image_cue_ambiguous_review.py "${args[@]}"

echo "Native image-cue ambiguous review:"
cat "$OUT_DIR/native_image_cue_ambiguous_review.md"
