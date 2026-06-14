#!/usr/bin/env bash
#SBATCH --job-name=seekui-native-imgcue
#SBATCH --account=notchpeak-shared-short
#SBATCH --partition=notchpeak-shared-short
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:30:00
#SBATCH --output=seekui-native-imgcue-%j.out

set -euo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:-$(pwd)}"
cd "$REPO_ROOT"

SEEKUI_WORK="${SEEKUI_WORK:-${SCRATCH:-$REPO_ROOT/.scratch}/seekui}"
OSF_DIR="${OSF_DIR:-$SEEKUI_WORK/data/osf_vsgui10k}"
NATIVE_DIR="${NATIVE_DIR:-$SEEKUI_WORK/outputs/native_vsgui10k}"
TRIALS_JSON="${TRIALS_JSON:-$NATIVE_DIR/native_vsgui10k_trials.json}"
IMAGE_ROOT="${IMAGE_ROOT:-$OSF_DIR/extracted/data}"
OUT_DIR="${OUT_DIR:-$NATIVE_DIR/processed_v2/image_cue_audit}"

module load miniconda3/25.9.1
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate seekui

if [[ ! -f "$TRIALS_JSON" ]]; then
  python scripts_research/build_native_vsgui10k_trials.py \
    --fixations-csv "$OSF_DIR/extracted/data/vsgui10k_fixations.csv" \
    --out-dir "$NATIVE_DIR"
fi

python scripts_research/audit_native_vsgui10k_image_cues.py \
  --trials-json "$TRIALS_JSON" \
  --image-root "$IMAGE_ROOT" \
  --out-dir "$OUT_DIR" \
  --max-samples "${MAX_SAMPLES:-120}"

echo "Native VSGUI10K image-cue audit:"
cat "$OUT_DIR/native_vsgui10k_image_cue_audit.md"
