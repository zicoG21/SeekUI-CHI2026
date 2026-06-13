#!/usr/bin/env bash
#SBATCH --job-name=seekui-osf-vsgui
#SBATCH --account=notchpeak-shared-short
#SBATCH --partition=notchpeak-shared-short
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=01:00:00
#SBATCH --output=seekui-osf-vsgui-%j.out

set -euo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:-$(pwd)}"
cd "$REPO_ROOT"

SEEKUI_WORK="${SEEKUI_WORK:-${SCRATCH:-$REPO_ROOT/.scratch}/seekui}"
OSF_DIR="${OSF_DIR:-$SEEKUI_WORK/data/osf_vsgui10k}"
OUT_DIR="${OUT_DIR:-$SEEKUI_WORK/outputs/native_vsgui10k}"
EXTRACT_IMAGES="${EXTRACT_IMAGES:-0}"

module load miniconda3/25.9.1
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate seekui

download_args=(--out-dir "$OSF_DIR")
if [[ "$EXTRACT_IMAGES" == "1" ]]; then
  download_args+=(--extract-images)
fi

python scripts_research/download_osf_vsgui10k.py "${download_args[@]}"

python scripts_research/build_native_vsgui10k_trials.py \
  --fixations-csv "$OSF_DIR/extracted/data/vsgui10k_fixations.csv" \
  --out-dir "$OUT_DIR"

python scripts_research/audit_native_vsgui_targets.py \
  --input "$OUT_DIR/native_vsgui10k_trials.json" \
  --input "$OSF_DIR/extracted/data/vsgui10k_targets.csv" \
  --out-dir "$OUT_DIR/native_target_audit"

echo "Native VSGUI10K summary: $OUT_DIR/native_vsgui10k_trial_summary.md"
cat "$OUT_DIR/native_vsgui10k_trial_summary.md"

echo "Native target audit summary: $OUT_DIR/native_target_audit/native_vsgui_target_audit_summary.md"
cat "$OUT_DIR/native_target_audit/native_vsgui_target_audit_summary.md"
