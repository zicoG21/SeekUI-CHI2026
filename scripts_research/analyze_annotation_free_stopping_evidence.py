#!/usr/bin/env python
import argparse
import json
from collections import defaultdict
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    Image = None

from analyze_prediction_stopping_evidence import (
    analyze_example,
    get_target_text,
    image_size,
    load_json,
    summarize_rows,
    threshold_sweep,
    write_csv,
    write_json,
    write_summary_md,
)


def safe_float(value, default=None):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def load_ocr_rows(path):
    raw = load_json(path)
    if isinstance(raw, dict):
        return raw.get("images", [])
    return raw if isinstance(raw, list) else []


def ocr_candidate_center(candidate):
    left = safe_float(candidate.get("left"))
    top = safe_float(candidate.get("top"))
    width = safe_float(candidate.get("width"))
    height = safe_float(candidate.get("height"))
    if left is None or top is None or width is None or height is None:
        return None
    if width <= 0 or height <= 0:
        return None
    return left + width / 2.0, top + height / 2.0


def build_annotation_free_candidates(ocr_rows, min_conf):
    by_image = defaultdict(list)
    raw_counts = defaultdict(int)
    status_counts = defaultdict(int)
    for row in ocr_rows:
        image = row.get("image", "")
        if not image:
            continue
        status_counts[row.get("status", "unknown")] += 1
        candidates = row.get("candidates", []) or []
        raw_counts[image] += len(candidates)
        seen = set()
        for candidate in candidates:
            text = str(candidate.get("text", "") or "").strip()
            conf = safe_float(candidate.get("conf"), 0.0)
            center = ocr_candidate_center(candidate)
            if not text or conf < min_conf or center is None:
                continue
            key = (
                text.casefold(),
                round(center[0], 2),
                round(center[1], 2),
                candidate.get("source", ""),
            )
            if key in seen:
                continue
            seen.add(key)
            by_image[image].append({
                "candidate_index": len(by_image[image]),
                "text": text,
                "target_id": "",
                "img_usr_tgt": "",
                "x": center[0],
                "y": center[1],
                "conf": conf,
                "source": candidate.get("source", "ocr"),
                "left": candidate.get("left", ""),
                "top": candidate.get("top", ""),
                "width": candidate.get("width", ""),
                "height": candidate.get("height", ""),
            })
    return by_image, raw_counts, dict(status_counts)


def resolve_image(image_root, image):
    if not image_root or Image is None:
        return None
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


def edge_visual_proposals(image_path, max_side, edge_threshold, min_area, min_size, max_proposals):
    if image_path is None or Image is None:
        return []
    with Image.open(image_path) as image:
        original_w, original_h = image.size
        gray = image.convert("L")
        scale = min(1.0, max_side / max(original_w, original_h))
        if scale < 1.0:
            gray = gray.resize((max(1, int(original_w * scale)), max(1, int(original_h * scale))))
        width, height = gray.size
        pixels = gray.load()

        edge = [[False] * width for _ in range(height)]
        for y in range(height - 1):
            for x in range(width - 1):
                diff = abs(int(pixels[x + 1, y]) - int(pixels[x, y])) + abs(int(pixels[x, y + 1]) - int(pixels[x, y]))
                if diff >= edge_threshold:
                    edge[y][x] = True

        visited = [[False] * width for _ in range(height)]
        boxes = []
        for y0 in range(height):
            for x0 in range(width):
                if visited[y0][x0] or not edge[y0][x0]:
                    continue
                stack = [(x0, y0)]
                visited[y0][x0] = True
                min_x = max_x = x0
                min_y = max_y = y0
                count = 0
                while stack:
                    x, y = stack.pop()
                    count += 1
                    min_x = min(min_x, x)
                    max_x = max(max_x, x)
                    min_y = min(min_y, y)
                    max_y = max(max_y, y)
                    for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                        if nx < 0 or nx >= width or ny < 0 or ny >= height:
                            continue
                        if visited[ny][nx] or not edge[ny][nx]:
                            continue
                        visited[ny][nx] = True
                        stack.append((nx, ny))
                box_w = max_x - min_x + 1
                box_h = max_y - min_y + 1
                if count < min_area or box_w < min_size or box_h < min_size:
                    continue
                boxes.append((count, min_x, min_y, max_x, max_y))

        boxes.sort(reverse=True)
        proposals = []
        inv_scale = 1.0 / scale if scale else 1.0
        for count, min_x, min_y, max_x, max_y in boxes[:max_proposals]:
            left = min_x * inv_scale
            top = min_y * inv_scale
            right = (max_x + 1) * inv_scale
            bottom = (max_y + 1) * inv_scale
            proposals.append({
                "candidate_index": len(proposals),
                "text": "__QUERY__",
                "target_id": "",
                "img_usr_tgt": "",
                "x": (left + right) / 2.0,
                "y": (top + bottom) / 2.0,
                "conf": "",
                "source": "edge_visual_proposal",
                "left": left,
                "top": top,
                "width": max(1.0, right - left),
                "height": max(1.0, bottom - top),
                "edge_pixels": count,
            })
        return proposals


def build_visual_candidates(images, image_root, args):
    by_image = defaultdict(list)
    if not args.include_visual_proposals:
        return by_image
    for image in sorted(images):
        image_path = resolve_image(image_root, image)
        by_image[image] = edge_visual_proposals(
            image_path,
            args.visual_max_side,
            args.visual_edge_threshold,
            args.visual_min_area,
            args.visual_min_size,
            args.visual_max_proposals,
        )
    return by_image


def materialize_candidates(candidates, query):
    result = []
    for idx, candidate in enumerate(candidates):
        item = dict(candidate)
        if item.get("text") == "__QUERY__":
            item["text"] = query
        item["candidate_index"] = idx
        result.append(item)
    return result


def write_annotation_free_summary_md(path, summaries, best_sweeps, ocr_status_counts, min_conf):
    write_summary_md(path, summaries, best_sweeps)
    with open(path, "a", encoding="utf-8") as f:
        f.write("\n## Annotation-Free Candidate Inventory\n\n")
        source = summaries[0].get("candidate_inventory", "annotation_free_ocr") if summaries else "annotation_free_ocr"
        f.write(f"- Candidate source: {source}; no target annotations are used.\n")
        f.write(f"- Minimum OCR confidence: {min_conf:g}\n\n")
        f.write("| OCR Status | Images |\n")
        f.write("|---|---:|\n")
        for status, count in sorted(ocr_status_counts.items()):
            f.write(f"| {status} | {count} |\n")


def main():
    parser = argparse.ArgumentParser(
        description="Analyze stopping evidence with an annotation-free OCR candidate inventory."
    )
    parser.add_argument("--ocr-candidates", required=True)
    parser.add_argument("--target2text", default="")
    parser.add_argument("--image-root", default="")
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--prediction", action="append", required=True, help="NAME=PATH prediction JSON. Can repeat.")
    parser.add_argument("--radius-px", type=float, default=0.0, help="Fixed evidence radius. Overrides --radius-norm if >0.")
    parser.add_argument("--radius-norm", type=float, default=0.08, help="Evidence radius as image diagonal fraction.")
    parser.add_argument("--low-evidence-threshold", type=float, default=0.2)
    parser.add_argument("--threshold-step", type=float, default=0.05)
    parser.add_argument("--fallback-width", type=float, default=1280)
    parser.add_argument("--fallback-height", type=float, default=720)
    parser.add_argument("--min-ocr-conf", type=float, default=35.0)
    parser.add_argument("--include-visual-proposals", action="store_true")
    parser.add_argument("--visual-max-side", type=int, default=320)
    parser.add_argument("--visual-edge-threshold", type=int, default=45)
    parser.add_argument("--visual-min-area", type=int, default=8)
    parser.add_argument("--visual-min-size", type=int, default=3)
    parser.add_argument("--visual-max-proposals", type=int, default=80)
    args = parser.parse_args()

    target2text = load_json(Path(args.target2text)) if args.target2text else {}
    image_root = Path(args.image_root) if args.image_root else None
    fallback_size = (args.fallback_width, args.fallback_height)
    out_dir = Path(args.out_dir)

    ocr_rows = load_ocr_rows(Path(args.ocr_candidates))
    candidates_by_image, raw_counts, ocr_status_counts = build_annotation_free_candidates(
        ocr_rows,
        args.min_ocr_conf,
    )
    visual_by_image = build_visual_candidates(
        {row.get("image", "") for row in ocr_rows if row.get("image")},
        image_root,
        args,
    )
    candidate_inventory = "annotation_free_ocr+edge_visual" if args.include_visual_proposals else "annotation_free_ocr"

    summaries = []
    best_sweeps = {}
    for spec in args.prediction:
        if "=" not in spec:
            raise ValueError(f"Prediction must be NAME=PATH, got: {spec}")
        name, raw_path = spec.split("=", 1)
        prediction_path = Path(raw_path)
        examples = load_json(prediction_path)
        rows = []
        step_rows = []
        missing_ocr_images = 0
        zero_candidate_images = 0
        for idx, example in enumerate(examples):
            image = example.get("image", "")
            size = image_size(image_root, image, fallback_size)
            query = get_target_text(example, target2text)
            candidates = materialize_candidates(
                list(candidates_by_image.get(image, [])) + list(visual_by_image.get(image, [])),
                query,
            )
            if image not in raw_counts:
                missing_ocr_images += 1
            elif not candidates:
                zero_candidate_images += 1
            row, steps = analyze_example(
                idx,
                example,
                candidates,
                target2text,
                size,
                args,
            )
            row.update({
                "candidate_inventory": candidate_inventory,
                "raw_ocr_candidate_count": raw_counts.get(image, 0),
                "visual_candidate_count": len(visual_by_image.get(image, [])),
                "missing_ocr_image": int(image not in raw_counts and image not in candidates_by_image),
                "min_ocr_conf": args.min_ocr_conf,
            })
            rows.append(row)
            step_rows.extend(steps)

        detail_path = out_dir / f"{name}_annotation_free_stopping_evidence.csv"
        steps_path = out_dir / f"{name}_annotation_free_stopping_evidence_steps.csv"
        sweep_path = out_dir / f"{name}_annotation_free_stopping_evidence_threshold_sweep.csv"
        write_csv(detail_path, rows, list(rows[0].keys()) if rows else [])
        if step_rows:
            write_csv(steps_path, step_rows, list(step_rows[0].keys()))
        sweep = threshold_sweep(rows, args.threshold_step)
        write_csv(sweep_path, sweep, list(sweep[0].keys()) if sweep else [])
        best_sweeps[name] = max(sweep, key=lambda row: row["absent_f1"]) if sweep else None

        summary = summarize_rows(name, rows, args.low_evidence_threshold)
        summary.update({
            "candidate_inventory": candidate_inventory,
            "missing_ocr_images": missing_ocr_images,
            "zero_candidate_images": zero_candidate_images,
            "prediction_file": str(prediction_path),
            "detail_csv": str(detail_path),
            "steps_csv": str(steps_path),
            "threshold_sweep_csv": str(sweep_path),
        })
        summaries.append(summary)

    summary_json = out_dir / "annotation_free_stopping_evidence_summary.json"
    summary_md = out_dir / "annotation_free_stopping_evidence_summary.md"
    write_json(summary_json, {
        "candidate_inventory": candidate_inventory,
        "ocr_candidates": str(Path(args.ocr_candidates)),
        "min_ocr_conf": args.min_ocr_conf,
        "include_visual_proposals": args.include_visual_proposals,
        "visual_proposal_params": {
            "max_side": args.visual_max_side,
            "edge_threshold": args.visual_edge_threshold,
            "min_area": args.visual_min_area,
            "min_size": args.visual_min_size,
            "max_proposals": args.visual_max_proposals,
        },
        "radius_px": args.radius_px,
        "radius_norm": args.radius_norm,
        "low_evidence_threshold": args.low_evidence_threshold,
        "ocr_status_counts": ocr_status_counts,
        "models": summaries,
        "best_thresholds": best_sweeps,
    })
    write_annotation_free_summary_md(
        summary_md,
        summaries,
        best_sweeps,
        ocr_status_counts,
        args.min_ocr_conf,
    )
    print(json.dumps({
        "candidate_inventory": candidate_inventory,
        "models": [summary["name"] for summary in summaries],
        "summary_md": str(summary_md),
        "summary_json": str(summary_json),
    }, indent=2))


if __name__ == "__main__":
    main()
