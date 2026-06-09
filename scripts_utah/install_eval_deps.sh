#!/usr/bin/env bash
set -euo pipefail

python -m pip install -U pip setuptools wheel

# gensim 4.3.x imports scipy.linalg.triu, which is not available in scipy>=1.13.
python -m pip install \
  "numpy==1.26.4" \
  "scipy==1.12.0" \
  "opencv-python-headless==4.9.0.80" \
  "nltk==3.9.1" \
  "gensim==4.3.2" \
  "pandas" \
  "scikit-learn" \
  "scikit-image" \
  "matplotlib" \
  "tqdm" \
  "accelerate"

if ! command -v java >/dev/null 2>&1; then
  if command -v conda >/dev/null 2>&1; then
    conda install -y -c conda-forge "openjdk=8"
  else
    echo "java is not available and conda was not found. Load/install Java before running METEOR/PTBTokenizer."
    exit 1
  fi
fi

python - <<'PY'
import accelerate
import cv2
import gensim
import nltk
import numpy
import scipy
import sklearn
import skimage

print("numpy", numpy.__version__)
print("scipy", scipy.__version__)
print("cv2", cv2.__version__)
print("nltk", nltk.__version__)
print("gensim", gensim.__version__)
print("sklearn", sklearn.__version__)
print("skimage", skimage.__version__)
print("accelerate", accelerate.__version__)
PY

java -version
