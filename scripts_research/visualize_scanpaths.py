#!/usr/bin/env python
import argparse
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def status(example):
    if "target_present" in example:
        return "present" if example["target_present"] else "absent"
    return "absent" if str(example.get("status", "")).casefold() == "absent" else "present"


def draw_polyline(draw, points, color, radius=5, width=3):
    if not points:
        return
    xy = [(float(x), float(y)) for x, y in points]
    if len(xy) > 1:
        draw.line(xy, fill=color, width=width)
    for idx, (x, y) in enumerate(xy, start=1):
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), outline=color, width=2)
        draw.text((x + radius + 2, y - radius - 2), str(idx), fill=color)


def points_from_xy(example):
    xs = example.get("x", []) or []
    ys = example.get("y", []) or []
    return [[x, y] for x, y in zip(xs, ys)]


def valid_bbox(example):
    values = [example.get("target_x"), example.get("target_y"), example.get("target_width"), example.get("target_height")]
    if any(value is None for value in values):
        return None
    try:
        x, y, w, h = [float(value) for value in values]
    except (TypeError, ValueError):
        return None
    if w <= 0 or h <= 0:
        return None
    return x, y, w, h


def safe_name(example, idx):
    sample_id = str(example.get("img_usr_tgt", idx))
    keep = []
    for char in sample_id:
        keep.append(char if char.isalnum() or char in {"-", "_"} else "_")
    return "".join(keep)[:180]


def main():
    parser = argparse.ArgumentParser(description="Visualize target boxes and scanpaths for VSGUI/SeekUI JSON files.")
    parser.add_argument("--json", required=True, help="Input examples or predictions JSON.")
    parser.add_argument("--image-root", required=True, help="Data root containing image paths from JSON.")
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--status", choices=["all", "present", "absent"], default="all")
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--max-scan", type=int, default=0, help="Maximum examples to scan before stopping. 0 means no limit.")
    parser.add_argument("--max-missing-logs", type=int, default=10)
    args = parser.parse_args()

    examples = load_json(Path(args.json))
    image_root = Path(args.image_root)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    font = ImageFont.load_default()
    written = 0
    scanned = 0
    missing = 0
    for idx, example in enumerate(examples[args.start:], start=args.start):
        scanned += 1
        if args.max_scan and scanned > args.max_scan:
            break
        if args.status != "all" and status(example) != args.status:
            continue
        image_path = image_root / example["image"]
        if not image_path.exists():
            missing += 1
            if missing <= args.max_missing_logs:
                print(f"Skipping missing image: {image_path}")
            continue

        canvas = Image.open(image_path).convert("RGB")
        draw = ImageDraw.Draw(canvas)

        bbox = valid_bbox(example)
        if bbox:
            x, y, w, h = bbox
            draw.rectangle((x, y, x + w, y + h), outline=(0, 210, 0), width=4)

        gt_points = points_from_xy(example)
        pred_points = example.get("prediction", []) or []
        draw_polyline(draw, gt_points, (0, 120, 255), radius=5, width=3)
        draw_polyline(draw, pred_points, (255, 80, 0), radius=4, width=3)

        label_lines = [
            f"id: {example.get('img_usr_tgt', idx)}",
            f"target: {example.get('target', '')}",
            f"status: {status(example)}",
            "blue=GT orange=prediction green=target bbox",
        ]
        label = "\n".join(label_lines)
        text_bbox = draw.multiline_textbbox((8, 8), label, font=font)
        pad = 6
        draw.rectangle(
            (text_bbox[0] - pad, text_bbox[1] - pad, text_bbox[2] + pad, text_bbox[3] + pad),
            fill=(255, 255, 255),
            outline=(40, 40, 40),
        )
        draw.multiline_text((8, 8), label, fill=(0, 0, 0), font=font)

        output = out_dir / f"{idx:04d}_{safe_name(example, idx)}.png"
        canvas.save(output)
        written += 1
        if written >= args.limit:
            break

    print(f"Wrote {written} visualizations to {out_dir}")
    print(f"Scanned {scanned} examples; skipped {missing} missing images")


if __name__ == "__main__":
    main()
