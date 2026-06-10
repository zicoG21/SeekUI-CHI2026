#!/usr/bin/env python
import argparse
import csv
import json
import subprocess
from collections import defaultdict
from pathlib import Path


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def normalize(text):
    return " ".join(str(text or "").replace("\n", " ").split())


def image_list_from_json(path):
    data = load_json(path)
    images = []
    seen = set()
    for item in data:
        image = item.get("image", "")
        if image and image not in seen:
            seen.add(image)
            images.append(image)
    return images


def run_tesseract(image_path, tesseract_cmd, psm):
    cmd = [
        tesseract_cmd,
        str(image_path),
        "stdout",
        "--psm",
        str(psm),
        "tsv",
    ]
    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    return result.stdout


def parse_tsv(tsv_text, min_conf):
    reader = csv.DictReader(tsv_text.splitlines(), delimiter="\t")
    tokens = []
    for row in reader:
        text = normalize(row.get("text", ""))
        if not text:
            continue
        try:
            conf = float(row.get("conf", "-1"))
        except ValueError:
            conf = -1.0
        if conf < min_conf:
            continue
        try:
            left = float(row.get("left", 0))
            top = float(row.get("top", 0))
            width = float(row.get("width", 0))
            height = float(row.get("height", 0))
        except ValueError:
            continue
        if width <= 0 or height <= 0:
            continue
        tokens.append({
            "text": text,
            "conf": conf,
            "left": left,
            "top": top,
            "width": width,
            "height": height,
            "block_num": row.get("block_num", ""),
            "par_num": row.get("par_num", ""),
            "line_num": row.get("line_num", ""),
        })
    return tokens


def merge_line_tokens(tokens):
    groups = defaultdict(list)
    for token in tokens:
        key = (token["block_num"], token["par_num"], token["line_num"])
        groups[key].append(token)

    candidates = []
    for group_tokens in groups.values():
        group_tokens.sort(key=lambda token: (token["top"], token["left"]))
        text = normalize(" ".join(token["text"] for token in group_tokens))
        if not text:
            continue
        left = min(token["left"] for token in group_tokens)
        top = min(token["top"] for token in group_tokens)
        right = max(token["left"] + token["width"] for token in group_tokens)
        bottom = max(token["top"] + token["height"] for token in group_tokens)
        conf = sum(token["conf"] for token in group_tokens) / len(group_tokens)
        candidates.append({
            "text": text,
            "conf": conf,
            "left": left,
            "top": top,
            "width": right - left,
            "height": bottom - top,
            "source": "tesseract_line",
        })
    return candidates


def build_candidates_for_image(image_root, image, args):
    image_path = image_root / image
    if not image_path.exists():
        return {
            "image": image,
            "status": "missing_image",
            "candidates": [],
            "error": f"Missing image: {image_path}",
        }
    try:
        tsv = run_tesseract(image_path, args.tesseract_cmd, args.psm)
        tokens = parse_tsv(tsv, args.min_conf)
        candidates = merge_line_tokens(tokens)
        if args.include_tokens:
            candidates.extend({**token, "source": "tesseract_token"} for token in tokens)
        return {
            "image": image,
            "status": "ok",
            "candidates": candidates,
            "num_candidates": len(candidates),
        }
    except FileNotFoundError as exc:
        return {
            "image": image,
            "status": "tesseract_not_found",
            "candidates": [],
            "error": str(exc),
        }
    except subprocess.CalledProcessError as exc:
        return {
            "image": image,
            "status": "tesseract_error",
            "candidates": [],
            "error": (exc.stderr or str(exc))[-1000:],
        }


def main():
    parser = argparse.ArgumentParser(description="Build non-oracle OCR candidates for VSGUI screenshots.")
    parser.add_argument("--input-json", required=True, help="Prediction/dataset JSON containing image paths.")
    parser.add_argument("--image-root", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--min-conf", type=float, default=35.0)
    parser.add_argument("--psm", type=int, default=11)
    parser.add_argument("--tesseract-cmd", default="tesseract")
    parser.add_argument("--include-tokens", action="store_true")
    args = parser.parse_args()

    images = image_list_from_json(Path(args.input_json))
    if args.limit > 0:
        images = images[:args.limit]
    image_root = Path(args.image_root)

    rows = []
    for idx, image in enumerate(images, start=1):
        row = build_candidates_for_image(image_root, image, args)
        rows.append(row)
        if idx % 50 == 0:
            print(f"Processed {idx}/{len(images)} images")

    status_counts = defaultdict(int)
    total_candidates = 0
    for row in rows:
        status_counts[row["status"]] += 1
        total_candidates += len(row.get("candidates", []))

    output = Path(args.output)
    write_json(output, {
        "input_json": str(Path(args.input_json)),
        "image_root": str(image_root),
        "num_images": len(rows),
        "total_candidates": total_candidates,
        "status_counts": dict(sorted(status_counts.items())),
        "images": rows,
    })
    print(json.dumps({
        "output": str(output),
        "num_images": len(rows),
        "total_candidates": total_candidates,
        "status_counts": dict(sorted(status_counts.items())),
    }, indent=2))


if __name__ == "__main__":
    main()
