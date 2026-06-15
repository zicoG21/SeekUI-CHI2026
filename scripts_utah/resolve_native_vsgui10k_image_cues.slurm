#!/usr/bin/env bash
#SBATCH --job-name=seekui-native-img-resolve
#SBATCH --account=notchpeak-shared-short
#SBATCH --partition=notchpeak-shared-short
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:30:00
#SBATCH --output=seekui-native-img-resolve-%j.out

set -euo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:-$(pwd)}"
cd "$REPO_ROOT"

SEEKUI_WORK="${SEEKUI_WORK:-${SCRATCH:-$REPO_ROOT/.scratch}/seekui}"
OSF_DIR="${OSF_DIR:-$SEEKUI_WORK/data/osf_vsgui10k}"
NATIVE_DIR="${NATIVE_DIR:-$SEEKUI_WORK/outputs/native_vsgui10k}"
TRIALS_JSON="${TRIALS_JSON:-$NATIVE_DIR/native_vsgui10k_trials.json}"
IMAGE_ROOT="${IMAGE_ROOT:-$SEEKUI_WORK/data}"
OUT_DIR="${OUT_DIR:-$NATIVE_DIR/processed_v2/image_cue_resolution}"

module load miniconda3/25.9.1
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate seekui

if [[ ! -f "$TRIALS_JSON" ]]; then
  python scripts_research/build_native_vsgui10k_trials.py \
    --fixations-csv "$OSF_DIR/extracted/data/vsgui10k_fixations.csv" \
    --out-dir "$NATIVE_DIR"
fi

args=(
  --trials-json "$TRIALS_JSON"
  --image-root "$IMAGE_ROOT"
  --out-dir "$OUT_DIR"
  --search-root "$OSF_DIR/extracted"
  --search-root "$SEEKUI_WORK/data"
)

if [[ -f "$OSF_DIR/VSGUI10K.zip" ]]; then
  args+=(--zip-path "$OSF_DIR/VSGUI10K.zip")
fi

if [[ "${INCLUDE_AMBIGUOUS:-0}" == "1" ]]; then
  args+=(--include-ambiguous)
fi

python scripts_research/resolve_native_vsgui10k_image_cues.py "${args[@]}"

echo "Native VSGUI10K image-cue resolution:"
cat "$OUT_DIR/native_image_cue_resolution.md"
