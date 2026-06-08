#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SEEKUI_WORK="${SEEKUI_WORK:-${SCRATCH:-$REPO_ROOT/.scratch}/seekui}"
DATA_DIR="${SEEKUI_DATA_DIR:-$SEEKUI_WORK/data}"

mkdir -p "$DATA_DIR"

if ! command -v gdown >/dev/null 2>&1; then
  echo "gdown not found. Install it in your SeekUI environment first:"
  echo "  python -m pip install -U gdown"
  exit 1
fi

echo "Repo root: $REPO_ROOT"
echo "Data dir : $DATA_DIR"

cd "$DATA_DIR"

if [[ ! -d vsgui10k-images ]]; then
  echo "Downloading vsgui10k-images folder..."
  gdown --folder "https://drive.google.com/drive/folders/1Qbrwa6uZqRxgcwyWTF0bVZCEYkP7xTWK?usp=sharing"
else
  echo "Skipping vsgui10k-images; directory already exists."
fi

if [[ ! -f scanpath_train_explanation.json ]]; then
  echo "Downloading scanpath_train_explanation.json..."
  gdown --id 1ZIlf3GTTqXn-_kE8DBy-F1VV8QhAlBRh -O scanpath_train_explanation.json
else
  echo "Skipping scanpath_train_explanation.json; file already exists."
fi

if [[ ! -f target2text.json ]]; then
  echo "Downloading target2text.json..."
  gdown --id 1pLHVWtbS3y6jWDTmwYmmQrXzKFKwWZDl -O target2text.json
else
  echo "Skipping target2text.json; file already exists."
fi

echo
echo "Downloaded data:"
du -sh "$DATA_DIR"/*
