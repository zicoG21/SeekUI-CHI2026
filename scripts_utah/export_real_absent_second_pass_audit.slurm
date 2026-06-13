#!/usr/bin/env bash
#SBATCH --job-name=seekui-real500-audit
#SBATCH --account=notchpeak-shared-short
#SBATCH --partition=notchpeak-shared-short
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:15:00
#SBATCH --output=seekui-real500-audit-%j.out

set -euo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:-$(pwd)}"
cd "$REPO_ROOT"

SEEKUI_WORK="${SEEKUI_WORK:-${SCRATCH:-$REPO_ROOT/.scratch}/seekui}"
DATA_DIR="${SEEKUI_DATA_DIR:-$SEEKUI_WORK/data}"
REALABS_DIR="${REALABS_DIR:-$SEEKUI_WORK/outputs/real_absent_validation_500}"
ANALYSIS_DIR="${ANALYSIS_DIR:-$REALABS_DIR/analysis}"
OUT_DIR="${OUT_DIR:-$REALABS_DIR/second_pass_audit}"

module load miniconda3/25.9.1
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate seekui

python scripts_research/export_real_absent_second_pass_audit.py \
  --filled-csv "$REALABS_DIR/real_absent_validation_filled.csv" \
  --analysis-cases-dir "$ANALYSIS_DIR/cases" \
  --image-root "$DATA_DIR" \
  --out-dir "$OUT_DIR" \
  --random-present "${RANDOM_PRESENT:-25}" \
  --random-absent "${RANDOM_ABSENT:-25}" \
  --case-limit "${CASE_LIMIT:-15}" \
  --seed "${SEED:-29}"

echo "Second-pass audit protocol:"
cat "$OUT_DIR/real_absent_validation_protocol.md"
