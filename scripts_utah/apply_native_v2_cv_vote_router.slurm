#!/usr/bin/env bash
#SBATCH --job-name=seekui-native-v2-router
#SBATCH --account=notchpeak-shared-short
#SBATCH --partition=notchpeak-shared-short
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:20:00
#SBATCH --output=seekui-native-v2-router-%j.out

set -euo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:-$(pwd)}"
cd "$REPO_ROOT"

SEEKUI_WORK="${SEEKUI_WORK:-${SCRATCH:-$REPO_ROOT/.scratch}/seekui}"
OUTPUT_DIR="$SEEKUI_WORK/outputs"
NATIVE_DIR="$OUTPUT_DIR/native_vsgui10k"
MODEL_NAME="${MODEL_NAME:-SeekUI}"
FOLDS="${FOLDS:-5}"
MAX_SUBSET_SIZE="${MAX_SUBSET_SIZE:-4}"
SPLITS=(${NATIVE_V2_SPLITS:-native_v2_main_text_balanced native_v2_main_text_color_balanced native_v2_clean_text_all_balanced native_v2_color_instance_balanced})
OBJECTIVES=(${NATIVE_V2_ROUTER_OBJECTIVES:-max_f1 precision_ge_0p60 pa_rate_le_0p25 utility_ap2_pa1})

module load miniconda3/25.9.1
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate seekui

for split in "${SPLITS[@]}"; do
  for objective in "${OBJECTIVES[@]}"; do
    suffix="native_v2_cv_vote_router"
    if [[ "$objective" != "max_f1" ]]; then
      suffix="native_v2_cv_vote_router_${objective}"
    fi
    out_base="$OUTPUT_DIR/present_absent_predictions_${MODEL_NAME}_${split}_${suffix}"
    echo "Running native v2 CV vote router: split=$split objective=$objective"
    python scripts_research/apply_native_v2_cv_vote_router.py \
      --work-dir "$SEEKUI_WORK" \
      --split-name "$split" \
      --model-name "$MODEL_NAME" \
      --folds "$FOLDS" \
      --max-subset-size "$MAX_SUBSET_SIZE" \
      --objective "$objective" \
      --output "${out_base}.json" \
      --metrics-output "${out_base}_status_eval.json" \
      --sweep-output "${out_base}_sweep.csv" \
      --summary-md "$NATIVE_DIR/processed_v2/cv_vote_router/${split}_${objective}.md"
  done
done

python scripts_research/summarize_native_vsgui_results.py \
  --work-dir "$SEEKUI_WORK" \
  --output-json "$NATIVE_DIR/native_vsgui_results.json" \
  --output-csv "$NATIVE_DIR/native_vsgui_results.csv" \
  --output-md "$NATIVE_DIR/native_vsgui_results.md"

python scripts_research/analyze_native_v2_balanced.py \
  --work-dir "$SEEKUI_WORK" \
  --model-name "$MODEL_NAME" \
  --out-dir "$NATIVE_DIR/processed_v2/analysis"

python scripts_research/export_native_v2_operating_points.py \
  --input-csv "$NATIVE_DIR/processed_v2/analysis/native_v2_balanced_metrics_ci.csv" \
  --output-json "$NATIVE_DIR/processed_v2/analysis/native_v2_operating_points.json" \
  --output-csv "$NATIVE_DIR/processed_v2/analysis/native_v2_operating_points.csv" \
  --output-md "$NATIVE_DIR/processed_v2/analysis/native_v2_operating_points.md"

python scripts_research/export_native_v2_recommended_cases.py \
  --work-dir "$SEEKUI_WORK" \
  --model-name "$MODEL_NAME" \
  --operating-points-csv "$NATIVE_DIR/processed_v2/analysis/native_v2_operating_points.csv" \
  --out-dir "$NATIVE_DIR/processed_v2/recommended_cases" \
  --limit "${CASE_LIMIT:-80}"

echo "Native v2 CV vote router complete."
cat "$NATIVE_DIR/processed_v2/analysis/native_v2_balanced_analysis.md"
echo
echo "Native v2 operating points:"
cat "$NATIVE_DIR/processed_v2/analysis/native_v2_operating_points.md"
echo
echo "Native v2 recommended cases:"
cat "$NATIVE_DIR/processed_v2/recommended_cases/native_v2_recommended_case_analysis.md"
