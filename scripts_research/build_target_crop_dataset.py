#!/usr/bin/env python
import argparse
import json
import math
from pathlib import Path

from PIL import Image


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def valid_bbox(example):
    fields = ["target_x", "target_y", "target_width", "target_height"]
    if any(example.get(field) is None for field in fields):
        return None
    try:
        x = float(example["target_x"])
        y = float(example["target_y"])
        w = float(example["target_width"])
        h = float(example["target_height"])
    except (TypeError, ValueError):
        return None
    if w <= 0 or h <= 0:
        return None
    return x, y, w, h


def crop_box(bbox, image_size, padding_ratio, min_padding):
    x, y, w, h = bbox
    width, height = image_size
    pad = max(min_padding, padding_ratio * max(w, h))
    left = max(0, math.floor(x - pad))
    top = max(0, math.floor(y - pad))
    right = min(width, math.ceil(x + w + pad))
    bottom = min(height, math.ceil(y + h + pad))
    if right <= left or bottom <= top:
        return None
    return left, top, right, bottom


def safe_name(example, idx):
    sample_id = str(example.get("img_usr_tgt", idx))
    keep = []
    for char in sample_id:
        keep.append(char if char.isalnum() or char in {"-", "_"} else "_")
    return "".join(keep)[:160]


def main():
    parser = argparse.ArgumentParser(description="Build an image-cue target-crop benchmark from VSGUI target boxes.")
    parser.add_argument("--scanpath", required=True)
    parser.add_argument("--image-root", required=True, help="Data root containing image paths from scanpath JSON.")
    parser.add_argument("--output", required=True)
    parser.add_argument("--crop-dir", required=True, help="Directory where target crops will be written.")
    parser.add_argument("--crop-prefix", default="target_crops", help="Path prefix stored in JSON, relative to image-root.")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--padding-ratio", type=float, default=0.20)
    parser.add_argument("--min-padding", type=float, default=4.0)
    parser.add_argument("--skip-missing", action="store_true")
    args = parser.parse_args()

    examples = load_json(Path(args.scanpath))
    image_root = Path(args.image_root)
    crop_dir = Path(args.crop_dir)
    crop_dir.mkdir(parents=True, exist_ok=True)

    output_examples = []
    skipped_missing = 0
    skipped_bbox = 0
    for idx, example in enumerate(examples):
        if args.limit and len(output_examples) >= args.limit:
            break

        image_path = image_root / example["image"]
        if not image_path.exists():
            skipped_missing += 1
            if args.skip_missing:
                continue
            raise FileNotFoundError(image_path)

        bbox = valid_bbox(example)
        if bbox is None:
            skipped_bbox += 1
            continue

        with Image.open(image_path).convert("RGB") as image:
            box = crop_box(bbox, image.size, args.padding_ratio, args.min_padding)
            if box is None:
                skipped_bbox += 1
                continue
            crop = image.crop(box)
            crop_name = f"{idx:06d}_{safe_name(example, idx)}.png"
            crop_path = crop_dir / crop_name
            crop.save(crop_path)

        result = dict(example)
        result["target_crop"] = f"{args.crop_prefix.rstrip('/')}/{crop_name}"
        result["target_crop_box"] = list(box)
        result["target_cue_type"] = "image_crop"
        output_examples.append(result)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w", encoding="utf-8") as f:
        json.dump(output_examples, f, indent=2, ensure_ascii=False)

    print(f"Input examples       : {len(examples)}")
    print(f"Output examples      : {len(output_examples)}")
    print(f"Skipped missing image: {skipped_missing}")
    print(f"Skipped invalid bbox : {skipped_bbox}")
    print(f"Output JSON          : {output}")
    print(f"Crop directory       : {crop_dir}")


if __name__ == "__main__":
    main()
