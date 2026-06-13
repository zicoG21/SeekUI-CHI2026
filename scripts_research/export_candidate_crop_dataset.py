#!/usr/bin/env python
import argparse
import json
import os
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path

from PIL import Image

from analyze_annotation_free_stopping_evidence import edge_visual_proposals


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def target_key(example):
    target_id = str(example.get("target_id", "") or "")
    return target_id[4:] if target_id.startswith("txt_") else target_id


def get_target_text(example, target2text):
    for key in ["query_text", "target", "original_target"]:
        value = str(example.get(key, "") or "").strip()
        if value:
            return value
    return str(target2text.get(target_key(example), example.get("target_id", "")))


def example_key(example, idx):
    return str(example.get("img_usr_tgt") or example.get("key") or example.get("id") or idx)


def gold_status(example):
    if "target_present" in example:
        return "present" if example["target_present"] else "absent"
    return "absent" if str(example.get("status", "")).casefold() == "absent" else "present"


def safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def resolve_image(image_root, image):
    image_root = Path(image_root)
    image = str(image or "")
    candidates = [
        image_root / image,
        image_root / "vsgui10k-images" / Path(image).name,
    ]
    for path in candidates:
        if path.exists():
            return path
    basename = Path(image).name
    if basename:
        for path in image_root.rglob(basename):
            if path.is_file():
                return path
    return None


def load_ocr_candidates(path):
    raw = load_json(path)
    rows = raw.get("images", []) if isinstance(raw, dict) else raw
    by_image = defaultdict(list)
    for row in rows or []:
        image = row.get("image", "")
        for candidate in row.get("candidates", []) or []:
            text = str(candidate.get("text", "") or "").strip()
            left = safe_float(candidate.get("left"))
            top = safe_float(candidate.get("top"))
            width = safe_float(candidate.get("width"))
            height = safe_float(candidate.get("height"))
            conf = safe_float(candidate.get("conf"), 0.0)
            if not text or width <= 0 or height <= 0:
                continue
            item = dict(candidate)
            item.update({
                "source": candidate.get("source", "ocr"),
                "text": text,
                "left": left,
                "top": top,
                "width": width,
                "height": height,
                "conf": conf,
            })
            by_image[image].append(item)
            basename = Path(image).name
            if basename and basename != image:
                by_image[basename].append(item)
    return by_image


def candidate_score(candidate, query):
    query_norm = query.casefold().strip()
    text_norm = str(candidate.get("text", "")).casefold().strip()
    if not text_norm:
        return 0.0
    ratio = SequenceMatcher(None, query_norm, text_norm).ratio()
    contains = 0.2 if query_norm and (query_norm in text_norm or text_norm in query_norm) else 0.0
    conf = safe_float(candidate.get("conf"), 0.0) / 1000.0
    return ratio + contains + conf


def clip_box(left, top, width, height, image_width, image_height, pad):
    x1 = max(0, int(round(left - pad)))
    y1 = max(0, int(round(top - pad)))
    x2 = min(image_width, int(round(left + width + pad)))
    y2 = min(image_height, int(round(top + height + pad)))
    if x2 <= x1 or y2 <= y1:
        return None
    return x1, y1, x2, y2


def add_visual_candidates(image_path, args):
    return edge_visual_proposals(
        image_path,
        args.visual_max_side,
        args.visual_edge_threshold,
        args.visual_min_area,
        args.visual_min_size,
        args.visual_max_proposals,
    )


def main():
    parser = argparse.ArgumentParser(description="Export candidate crops for crop-level VLM verification.")
    parser.add_argument("--input-json", required=True)
    parser.add_argument("--ocr-candidates", required=True)
    parser.add_argument("--target2text", default="")
    parser.add_argument("--image-root", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--top-k-ocr", type=int, default=3)
    parser.add_argument("--include-visual-proposals", action="store_true")
    parser.add_argument("--top-k-visual", type=int, default=3)
    parser.add_argument("--crop-pad", type=int, default=8)
    parser.add_argument("--min-ocr-conf", type=float, default=35.0)
    parser.add_argument("--visual-max-side", type=int, default=320)
    parser.add_argument("--visual-edge-threshold", type=int, default=45)
    parser.add_argument("--visual-min-area", type=int, default=8)
    parser.add_argument("--visual-min-size", type=int, default=3)
    parser.add_argument("--visual-max-proposals", type=int, default=80)
    args = parser.parse_args()

    examples = load_json(args.input_json)
    if args.limit > 0:
        examples = examples[:args.limit]
    target2text = load_json(args.target2text) if args.target2text else {}
    ocr_by_image = load_ocr_candidates(args.ocr_candidates)
    out_dir = Path(args.out_dir)
    crop_dir = out_dir / "crops"
    crop_dir.mkdir(parents=True, exist_ok=True)

    crop_rows = []
    example_rows = []
    missing_images = 0
    for idx, example in enumerate(examples):
        key = example_key(example, idx)
        query = get_target_text(example, target2text)
        image_path = resolve_image(args.image_root, example.get("image", ""))
        if image_path is None:
            missing_images += 1
            example_rows.append({"example_key": key, "candidate_count": 0, "missing_image": 1})
            continue

        with Image.open(image_path) as image:
            image = image.convert("RGB")
            image_width, image_height = image.size
            image_key = example.get("image", "")
            ocr_candidates = [
                item for item in (ocr_by_image.get(image_key, []) or ocr_by_image.get(Path(image_key).name, []))
                if safe_float(item.get("conf"), 0.0) >= args.min_ocr_conf
            ]
            ocr_candidates = sorted(
                ocr_candidates,
                key=lambda item: candidate_score(item, query),
                reverse=True,
            )[:args.top_k_ocr]

            visual_candidates = []
            if args.include_visual_proposals:
                visual_candidates = add_visual_candidates(image_path, args)[:args.top_k_visual]

            candidates = []
            for item in ocr_candidates:
                candidate = dict(item)
                candidate["candidate_source"] = "ocr"
                candidate["candidate_score"] = candidate_score(candidate, query)
                candidates.append(candidate)
            for item in visual_candidates:
                candidate = dict(item)
                candidate["candidate_source"] = "edge_visual"
                candidate["candidate_score"] = safe_float(candidate.get("edge_pixels"), 0.0)
                candidates.append(candidate)

            written = 0
            for candidate_index, candidate in enumerate(candidates):
                box = clip_box(
                    safe_float(candidate.get("left")),
                    safe_float(candidate.get("top")),
                    safe_float(candidate.get("width")),
                    safe_float(candidate.get("height")),
                    image_width,
                    image_height,
                    args.crop_pad,
                )
                if box is None:
                    continue
                crop = image.crop(box)
                crop_name = f"{idx:06d}_{candidate_index:02d}_{candidate.get('candidate_source', 'candidate')}.png"
                crop_path = crop_dir / crop_name
                crop.save(crop_path)
                crop_rows.append({
                    "candidate_uid": f"{key}::{candidate_index}",
                    "example_key": key,
                    "example_index": idx,
                    "img_usr_tgt": example.get("img_usr_tgt", ""),
                    "image": example.get("image", ""),
                    "original_image_path": str(image_path),
                    "crop_image": str(crop_path),
                    "query_text": query,
                    "gold_status": gold_status(example),
                    "candidate_index": candidate_index,
                    "candidate_source": candidate.get("candidate_source", candidate.get("source", "")),
                    "candidate_text": candidate.get("text", ""),
                    "candidate_score": candidate.get("candidate_score", ""),
                    "left": box[0],
                    "top": box[1],
                    "width": box[2] - box[0],
                    "height": box[3] - box[1],
                })
                written += 1
            example_rows.append({"example_key": key, "candidate_count": written, "missing_image": 0})

    output_json = Path(args.output_json)
    save_json(output_json, crop_rows)
    save_json(out_dir / "candidate_crop_manifest.json", {
        "input_json": args.input_json,
        "num_examples": len(examples),
        "num_crops": len(crop_rows),
        "missing_images": missing_images,
        "include_visual_proposals": args.include_visual_proposals,
        "top_k_ocr": args.top_k_ocr,
        "top_k_visual": args.top_k_visual,
        "examples": example_rows,
        "crops_json": str(output_json),
    })
    print(json.dumps({
        "examples": len(examples),
        "crops": len(crop_rows),
        "missing_images": missing_images,
        "output_json": str(output_json),
    }, indent=2))


if __name__ == "__main__":
    main()
