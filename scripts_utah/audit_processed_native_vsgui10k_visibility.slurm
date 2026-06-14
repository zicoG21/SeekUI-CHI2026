#!/usr/bin/env bash
#SBATCH --job-name=seekui-native-vis
#SBATCH --account=notchpeak-shared-short
#SBATCH --partition=notchpeak-shared-short
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=02:00:00
#SBATCH --output=seekui-native-vis-%j.out

set -euo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:-$(pwd)}"
cd "$REPO_ROOT"

SEEKUI_WORK="${SEEKUI_WORK:-${SCRATCH:-$REPO_ROOT/.scratch}/seekui}"
OSF_DIR="${OSF_DIR:-$SEEKUI_WORK/data/osf_vsgui10k}"
NATIVE_DIR="${NATIVE_DIR:-$SEEKUI_WORK/outputs/native_vsgui10k}"
TRIALS_JSON="${TRIALS_JSON:-$NATIVE_DIR/native_vsgui10k_trials.json}"
OUT_DIR="${OUT_DIR:-$NATIVE_DIR/processed_v2}"
AUDIT_DIR="${AUDIT_DIR:-$OUT_DIR/visibility_audit}"
OCR_JSON="${OCR_JSON:-$AUDIT_DIR/native_vsgui10k_ocr_candidates.json}"
IMAGE_ROOT="${IMAGE_ROOT:-$OSF_DIR/extracted/data}"
MIN_CONF="${MIN_CONF:-35}"

module load miniconda3/25.9.1
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate seekui

if [[ ! -f "$TRIALS_JSON" ]]; then
  python scripts_research/build_native_vsgui10k_trials.py \
    --fixations-csv "$OSF_DIR/extracted/data/vsgui10k_fixations.csv" \
    --out-dir "$NATIVE_DIR"
fi

mkdir -p "$AUDIT_DIR"

if [[ ! -f "$OCR_JSON" ]]; then
  python scripts_research/build_ocr_candidates.py \
    --input-json "$TRIALS_JSON" \
    --image-root "$IMAGE_ROOT" \
    --output "$OCR_JSON" \
    --min-conf "$MIN_CONF" \
    --include-tokens
else
  echo "Reusing OCR candidates: $OCR_JSON"
fi

python scripts_research/audit_native_vsgui10k_visibility.py \
  --trials-json "$TRIALS_JSON" \
  --ocr-candidates "$OCR_JSON" \
  --output-json "$AUDIT_DIR/native_vsgui10k_visibility_audit.json" \
  --output-csv "$AUDIT_DIR/native_vsgui10k_visible_conflicts.csv" \
  --output-md "$AUDIT_DIR/native_vsgui10k_visibility_audit.md"

python scripts_research/export_processed_native_vsgui10k.py \
  --trials-json "$TRIALS_JSON" \
  --audit-json "$AUDIT_DIR/native_vsgui10k_visibility_audit.json" \
  --out-dir "$OUT_DIR"

echo "Native VSGUI10K visibility audit:"
cat "$AUDIT_DIR/native_vsgui10k_visibility_audit.md"

echo "Processed Native VSGUI10K v2 summary:"
cat "$OUT_DIR/native_vsgui10k_v2_summary.md"
