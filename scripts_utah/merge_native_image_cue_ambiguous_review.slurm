#!/usr/bin/env bash
#SBATCH --job-name=seekui-native-img-merge
#SBATCH --account=notchpeak-shared-short
#SBATCH --partition=notchpeak-shared-short
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:10:00
#SBATCH --output=seekui-native-img-merge-%j.out

set -euo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:-$(pwd)}"
cd "$REPO_ROOT"

SEEKUI_WORK="${SEEKUI_WORK:-${SCRATCH:-$REPO_ROOT/.scratch}/seekui}"
NATIVE_DIR="${NATIVE_DIR:-$SEEKUI_WORK/outputs/native_vsgui10k}"
RESOLUTION_DIR="${RESOLUTION_DIR:-$NATIVE_DIR/processed_v2/image_cue_resolution}"
TRIALS_JSON="${TRIALS_JSON:-$NATIVE_DIR/native_vsgui10k_trials.json}"
IMAGE_ROOT="${IMAGE_ROOT:-$SEEKUI_WORK/data}"
BASE_EVAL_JSON="${BASE_EVAL_JSON:-$RESOLUTION_DIR/native_image_cue_eval.json}"
REVIEW_CSV="${REVIEW_CSV:-$RESOLUTION_DIR/ambiguous_review/native_image_cue_ambiguous_review_filled.csv}"
OUT_DIR="${OUT_DIR:-$RESOLUTION_DIR/review_merged}"

module load miniconda3/25.9.1
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate seekui

if [[ ! -f "$REVIEW_CSV" ]]; then
  echo "Missing filled review CSV: $REVIEW_CSV" >&2
  echo "Fill/copy ambiguous review CSV first, or set REVIEW_CSV=/path/to/file." >&2
  exit 1
fi

python scripts_research/merge_native_image_cue_ambiguous_review.py \
  --trials-json "$TRIALS_JSON" \
  --base-eval-json "$BASE_EVAL_JSON" \
  --review-csv "$REVIEW_CSV" \
  --image-root "$IMAGE_ROOT" \
  --out-dir "$OUT_DIR"

echo "Native image-cue review merge:"
cat "$OUT_DIR/native_image_cue_review_merge.md"
