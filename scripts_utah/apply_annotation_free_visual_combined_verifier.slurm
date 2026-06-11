#!/usr/bin/env bash
#SBATCH --job-name=seekui-af-vcombo
#SBATCH --account=notchpeak-shared-short
#SBATCH --partition=notchpeak-shared-short
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:30:00
#SBATCH --output=seekui-af-vcombo-%j.out

set -euo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:-$(pwd)}"
cd "$REPO_ROOT"

SEEKUI_WORK="${SEEKUI_WORK:-${SCRATCH:-$REPO_ROOT/.scratch}/seekui}"
OUTPUT_DIR="$SEEKUI_WORK/outputs"
EVIDENCE_DIR="${EVIDENCE_DIR:-$OUTPUT_DIR/annotation_free_visual_stopping_evidence}"

EVIDENCE_DIR="$EVIDENCE_DIR" \
VARIANT_PREFIX="annotation_free_visual_combined" \
bash scripts_utah/apply_annotation_free_combined_verifier.slurm
