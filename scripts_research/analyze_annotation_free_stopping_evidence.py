#!/usr/bin/env python
import argparse
import json
from collections import defaultdict
from pathlib import Path

from analyze_prediction_stopping_evidence import (
    analyze_example,
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


def write_annotation_free_summary_md(path, summaries, best_sweeps, ocr_status_counts, min_conf):
    write_summary_md(path, summaries, best_sweeps)
    with open(path, "a", encoding="utf-8") as f:
        f.write("\n## Annotation-Free Candidate Inventory\n\n")
        f.write("- Candidate source: OCR boxes only; no target annotations are used.\n")
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
            candidates = candidates_by_image.get(image, [])
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
                "candidate_inventory": "annotation_free_ocr",
                "raw_ocr_candidate_count": raw_counts.get(image, 0),
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
            "candidate_inventory": "annotation_free_ocr",
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
        "candidate_inventory": "annotation_free_ocr",
        "ocr_candidates": str(Path(args.ocr_candidates)),
        "min_ocr_conf": args.min_ocr_conf,
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
        "candidate_inventory": "annotation_free_ocr",
        "models": [summary["name"] for summary in summaries],
        "summary_md": str(summary_md),
        "summary_json": str(summary_json),
    }, indent=2))


if __name__ == "__main__":
    main()
