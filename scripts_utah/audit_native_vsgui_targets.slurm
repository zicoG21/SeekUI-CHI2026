#!/usr/bin/env bash
#SBATCH --job-name=seekui-native-audit
#SBATCH --account=notchpeak-shared-short
#SBATCH --partition=notchpeak-shared-short
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:20:00
#SBATCH --output=seekui-native-audit-%j.out

set -euo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:-$(pwd)}"
cd "$REPO_ROOT"

SEEKUI_WORK="${SEEKUI_WORK:-${SCRATCH:-$REPO_ROOT/.scratch}/seekui}"
DATA_DIR="${SEEKUI_DATA_DIR:-$SEEKUI_WORK/data}"
OUT_DIR="${OUT_DIR:-$SEEKUI_WORK/outputs/native_vsgui_target_audit}"

module load miniconda3/25.9.1
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate seekui

args=(--out-dir "$OUT_DIR")

if [[ -n "${NATIVE_VSGUI_INPUTS:-}" ]]; then
  IFS=':' read -r -a inputs <<< "$NATIVE_VSGUI_INPUTS"
  for input in "${inputs[@]}"; do
    [[ -n "$input" ]] && args+=(--input "$input")
  done
else
  args+=(--search-root "$DATA_DIR")
fi

if [[ -n "${MAX_RECORDS_PER_FILE:-}" ]]; then
  args+=(--max-records-per-file "$MAX_RECORDS_PER_FILE")
fi

python scripts_research/audit_native_vsgui_targets.py "${args[@]}"

echo "Native VSGUI target audit summary: $OUT_DIR/native_vsgui_target_audit_summary.md"
cat "$OUT_DIR/native_vsgui_target_audit_summary.md"
