#!/usr/bin/env bash
#SBATCH --job-name=seekui-realabs-500
#SBATCH --account=notchpeak-shared-short
#SBATCH --partition=notchpeak-shared-short
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:15:00
#SBATCH --output=seekui-realabs-500-%j.out

set -euo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:-$(pwd)}"
cd "$REPO_ROOT"

SEEKUI_WORK="${SEEKUI_WORK:-${SCRATCH:-$REPO_ROOT/.scratch}/seekui}"
OUTPUT_DIR="$SEEKUI_WORK/outputs"
PRESENT_COUNT="${PRESENT_COUNT:-250}"
ABSENT_COUNT="${ABSENT_COUNT:-250}"
TOTAL_COUNT=$((PRESENT_COUNT + ABSENT_COUNT))

PRESENT_COUNT="$PRESENT_COUNT" \
ABSENT_COUNT="$ABSENT_COUNT" \
OUT_DIR="${OUT_DIR:-$OUTPUT_DIR/real_absent_validation_${TOTAL_COUNT}}" \
SEED="${SEED:-44}" \
bash scripts_utah/export_expanded_real_absent_validation.slurm
