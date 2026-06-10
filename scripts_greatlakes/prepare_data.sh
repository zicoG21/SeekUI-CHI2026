#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SEEKUI_WORK="${SEEKUI_WORK:-/scratch/engin_root/engin1/$USER/seekui}"
DATA_DIR="${SEEKUI_DATA_DIR:-$SEEKUI_WORK/data}"

mkdir -p "$DATA_DIR" "$DATA_DIR/vsgui10k-images"

if [[ -f "$REPO_ROOT/data/scanpath_train_think.json" && ! -f "$DATA_DIR/scanpath_train_explanation.json" ]]; then
  cp "$REPO_ROOT/data/scanpath_train_think.json" "$DATA_DIR/scanpath_train_explanation.json"
fi

if [[ -f "$REPO_ROOT/data/target2text.json" && ! -f "$DATA_DIR/target2text.json" ]]; then
  cp "$REPO_ROOT/data/target2text.json" "$DATA_DIR/target2text.json"
fi

if [[ -f "$DATA_DIR/vsgui10k-images.zip" ]]; then
  unzip -q -n "$DATA_DIR/vsgui10k-images.zip" -d "$DATA_DIR/vsgui10k-images"
  find "$DATA_DIR/vsgui10k-images" -mindepth 2 -type f -name '*.png' -exec mv -n {} "$DATA_DIR/vsgui10k-images/" \;
fi

echo "Data dir: $DATA_DIR"
missing=0
for file in scanpath_train_explanation.json target2text.json; do
  if [[ -f "$DATA_DIR/$file" ]]; then
    ls -lh "$DATA_DIR/$file"
  else
    echo "Missing: $DATA_DIR/$file"
    missing=1
  fi
done
echo -n "Images: "
find "$DATA_DIR/vsgui10k-images" -maxdepth 1 -type f -name '*.png' | wc -l

if [[ "$missing" == "1" ]]; then
  cat <<EOF

The small JSON files are not tracked by git because data/*.json is ignored.
Copy them from CHPC or your local machine, then rerun this script.

From CHPC:
  scp u6076267@notchpeak.chpc.utah.edu:/scratch/general/vast/u6076267/seekui/data/scanpath_train_explanation.json "$DATA_DIR/"
  scp u6076267@notchpeak.chpc.utah.edu:/scratch/general/vast/u6076267/seekui/data/target2text.json "$DATA_DIR/"

From your local repo:
  scp data/scanpath_train_think.json zicong@greatlakes.arc-ts.umich.edu:"$DATA_DIR/scanpath_train_explanation.json"
  scp data/target2text.json zicong@greatlakes.arc-ts.umich.edu:"$DATA_DIR/target2text.json"
EOF
  exit 1
fi
