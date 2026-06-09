#!/usr/bin/env python
import json
import os
from pathlib import Path


def require(path, kind):
    if not path.exists():
        raise SystemExit(f"Missing {kind}: {path}")
    return path


def main():
    root = Path(os.environ.get("SEEKUI_WORK", "")).expanduser()
    if not root:
        raise SystemExit("SEEKUI_WORK is not set")

    data_dir = require(root / "data", "data directory")
    model_dir = require(root / "models", "model directory")
    require(model_dir / "SeekUI", "SeekUI model")
    require(model_dir / "SeekUI_sft", "SeekUI-SFT model")
    require(data_dir / "target2text.json", "target2text.json")
    scanpath_json = require(data_dir / "scanpath_train_explanation.json", "scanpath_train_explanation.json")
    image_dir = require(data_dir / "vsgui10k-images", "image directory")

    examples = json.loads(scanpath_json.read_text(encoding="utf-8"))
    unique_images = sorted({example["image"] for example in examples})
    missing_images = [image for image in unique_images if not (data_dir / image).exists()]

    print(f"SEEKUI_WORK          : {root}")
    print(f"examples             : {len(examples)}")
    print(f"unique images in JSON: {len(unique_images)}")
    print(f"local png files      : {len(list(image_dir.glob('*.png')))}")
    print(f"missing images       : {len(missing_images)}")
    if missing_images:
        print("First missing images:")
        for image in missing_images[:30]:
            print(f"  {image}")
        raise SystemExit("Input check failed: missing images")

    print("Input check passed.")


if __name__ == "__main__":
    main()
