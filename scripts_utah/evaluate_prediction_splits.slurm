#!/usr/bin/env bash
#SBATCH --job-name=seekui-spliteval
#SBATCH --account=notchpeak-shared-short
#SBATCH --partition=notchpeak-shared-short
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=04:00:00
#SBATCH --output=seekui-spliteval-%j.out

set -euo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:-$(pwd)}"
cd "$REPO_ROOT"

SEEKUI_WORK="${SEEKUI_WORK:-${SCRATCH:-$REPO_ROOT/.scratch}/seekui}"
PREDICTION_FILE="${PREDICTION_FILE:?Set PREDICTION_FILE to the predictions JSON to split and evaluate}"
SPLIT_FIELD="${SPLIT_FIELD:-query_type}"
SPLIT_NAME="${SPLIT_NAME:-$(basename "${PREDICTION_FILE%.json}")_${SPLIT_FIELD}}"
SPLIT_DIR="${SPLIT_DIR:-$SEEKUI_WORK/outputs/splits/$SPLIT_NAME}"
EVAL_DIR="${EVAL_DIR:-$SEEKUI_WORK/outputs/split_eval/$SPLIT_NAME}"
MIN_COUNT="${MIN_COUNT:-1}"

module load miniconda3/25.9.1
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate seekui

mkdir -p "$SPLIT_DIR" "$EVAL_DIR"

MANIFEST="$SPLIT_DIR/manifest.json"
python scripts_research/split_predictions.py \
  --predictions "$PREDICTION_FILE" \
  --field "$SPLIT_FIELD" \
  --out-dir "$SPLIT_DIR" \
  --prefix "$(basename "${PREDICTION_FILE%.json}")" \
  --min-count "$MIN_COUNT" \
  --manifest "$MANIFEST"

python - <<'PY' "$MANIFEST" "$EVAL_DIR" "$REPO_ROOT"
import json
import subprocess
import sys
from pathlib import Path

manifest = json.load(open(sys.argv[1]))
eval_dir = Path(sys.argv[2])
repo_root = Path(sys.argv[3])
evaluation_dir = repo_root / "evaluation"

for row in manifest:
    split_path = Path(row["path"]).resolve()
    log_path = eval_dir / f"{split_path.stem}.txt"
    print(f"Evaluating {row['value']} ({row['count']} examples)")
    cmd = [sys.executable, "evaluation.py", "--prediction_file", str(split_path)]
    with open(log_path, "w", encoding="utf-8") as log:
        proc = subprocess.Popen(
            cmd,
            cwd=evaluation_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        assert proc.stdout is not None
        for line in proc.stdout:
            print(line, end="")
            log.write(line)
        ret = proc.wait()
    if ret != 0:
        raise SystemExit(f"Evaluation failed for {split_path} with exit code {ret}")
    row["eval_log"] = str(log_path)

with open(eval_dir / "manifest_with_logs.json", "w", encoding="utf-8") as f:
    json.dump(manifest, f, indent=2)

print(f"Split evaluation logs saved to {eval_dir}")
PY
