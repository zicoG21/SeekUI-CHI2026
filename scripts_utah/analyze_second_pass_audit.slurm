#!/usr/bin/env bash
#SBATCH --job-name=seekui-audit2
#SBATCH --account=notchpeak-shared-short
#SBATCH --partition=notchpeak-shared-short
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=00:05:00
#SBATCH --output=seekui-audit2-%j.out

set -euo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:-$(pwd)}"
cd "$REPO_ROOT"

SEEKUI_WORK="${SEEKUI_WORK:-${SCRATCH:-$REPO_ROOT/.scratch}/seekui}"
AUDIT_DIR="${AUDIT_DIR:-$SEEKUI_WORK/outputs/real_absent_validation_500/second_pass_audit_hardcases}"
AUDIT_CSV="${AUDIT_CSV:-$AUDIT_DIR/real_absent_second_pass_audit_filled_by_codex.csv}"
OUT_DIR="${OUT_DIR:-$AUDIT_DIR/analysis}"

module load miniconda3/25.9.1
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate seekui

python scripts_research/analyze_second_pass_audit.py \
  --audit-csv "$AUDIT_CSV" \
  --output-json "$OUT_DIR/second_pass_audit_robustness.json" \
  --output-csv "$OUT_DIR/second_pass_audit_robustness.csv" \
  --output-md "$OUT_DIR/second_pass_audit_robustness.md"

echo "Second-pass audit robustness: $OUT_DIR/second_pass_audit_robustness.md"
cat "$OUT_DIR/second_pass_audit_robustness.md"
