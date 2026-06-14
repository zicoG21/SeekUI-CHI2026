#!/usr/bin/env bash
#SBATCH --job-name=seekui-native-v2
#SBATCH --account=notchpeak-shared-short
#SBATCH --partition=notchpeak-shared-short
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:20:00
#SBATCH --output=seekui-native-v2-%j.out

set -euo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:-$(pwd)}"
cd "$REPO_ROOT"

SEEKUI_WORK="${SEEKUI_WORK:-${SCRATCH:-$REPO_ROOT/.scratch}/seekui}"
OSF_DIR="${OSF_DIR:-$SEEKUI_WORK/data/osf_vsgui10k}"
NATIVE_DIR="${NATIVE_DIR:-$SEEKUI_WORK/outputs/native_vsgui10k}"
OUT_DIR="${OUT_DIR:-$NATIVE_DIR/processed_v2}"
TRIALS_JSON="${TRIALS_JSON:-$NATIVE_DIR/native_vsgui10k_trials.json}"
AUDIT_JSON="${AUDIT_JSON:-$NATIVE_DIR/processed_v2/visibility_audit/native_vsgui10k_visibility_audit.json}"

module load miniconda3/25.9.1
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate seekui

if [[ ! -f "$TRIALS_JSON" ]]; then
  python scripts_research/build_native_vsgui10k_trials.py \
    --fixations-csv "$OSF_DIR/extracted/data/vsgui10k_fixations.csv" \
    --out-dir "$NATIVE_DIR"
fi

audit_args=()
if [[ -f "$AUDIT_JSON" ]]; then
  audit_args+=(--audit-json "$AUDIT_JSON")
else
  echo "Warning: full-trials visibility audit JSON not found; exporting v2 with unverified absent buckets: $AUDIT_JSON"
fi

python scripts_research/export_processed_native_vsgui10k.py \
  --trials-json "$TRIALS_JSON" \
  --out-dir "$OUT_DIR" \
  "${audit_args[@]}"

echo "Processed native VSGUI10K v2 summary:"
cat "$OUT_DIR/native_vsgui10k_v2_summary.md"
