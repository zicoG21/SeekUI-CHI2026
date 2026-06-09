#!/usr/bin/env python
import argparse
import csv
import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def percentile(values, pct):
    if not values:
        return None
    values = sorted(values)
    index = (len(values) - 1) * pct / 100
    lower = math.floor(index)
    upper = math.ceil(index)
    if lower == upper:
        return values[int(index)]
    return values[lower] * (upper - index) + values[upper] * (index - lower)


def summarize_numeric(values):
    if not values:
        return {"min": None, "p25": None, "median": None, "mean": None, "p75": None, "max": None}
    return {
        "min": min(values),
        "p25": percentile(values, 25),
        "median": statistics.median(values),
        "mean": statistics.mean(values),
        "p75": percentile(values, 75),
        "max": max(values),
    }


def target_prefix(target_id):
    if not target_id:
        return "missing"
    return target_id.split("_", 1)[0] if "_" in target_id else "no_prefix"


def in_bounds(example):
    width = float(example.get("width", 0) or 0)
    height = float(example.get("height", 0) or 0)
    x = float(example.get("target_x", -1) or -1)
    y = float(example.get("target_y", -1) or -1)
    w = float(example.get("target_width", 0) or 0)
    h = float(example.get("target_height", 0) or 0)
    center_x = x + w / 2
    center_y = y + h / 2
    center_inside = 0 <= center_x <= width and 0 <= center_y <= height
    box_inside = 0 <= x <= width and 0 <= y <= height and 0 <= x + w <= width and 0 <= y + h <= height
    positive_area = w > 0 and h > 0
    return center_inside, box_inside, positive_area


def write_counter_csv(path, counter, headers):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for key, count in counter.most_common():
            writer.writerow([key, count])


def main():
    parser = argparse.ArgumentParser(description="Audit VSGUI/SeekUI scanpath data.")
    parser.add_argument("--scanpath", required=True, help="Path to scanpath_train_explanation.json or similar.")
    parser.add_argument("--target2text", default="", help="Optional target2text.json path.")
    parser.add_argument("--image-root", default="", help="Optional data root containing vsgui10k-images/.")
    parser.add_argument("--out-dir", default="", help="Optional directory for audit CSV/Markdown outputs.")
    args = parser.parse_args()

    scanpath_path = Path(args.scanpath)
    examples = load_json(scanpath_path)
    target2text = load_json(Path(args.target2text)) if args.target2text else {}
    image_root = Path(args.image_root) if args.image_root else None

    prefix_counts = Counter()
    target_text_counts = Counter()
    image_counts = Counter()
    target_counts = Counter()
    examples_per_image_target = Counter()
    scanpath_lengths = []
    fixation_durations = []
    missing_images = []
    empty_text = 0
    target_text_mismatch = 0
    center_inside_count = 0
    box_inside_count = 0
    positive_area_count = 0
    has_conversations = 0

    image_to_targets = defaultdict(set)
    image_to_target_texts = defaultdict(set)

    for example in examples:
        image = example.get("image", "")
        target_id = example.get("target_id", "")
        target_key = target_id[4:] if target_id.startswith("txt_") else target_id
        target_text = str(example.get("target", "") or "")
        mapped_text = str(target2text.get(target_key, "") or "")

        prefix_counts[target_prefix(target_id)] += 1
        target_text_counts[target_text if target_text else "<EMPTY>"] += 1
        image_counts[image] += 1
        target_counts[target_id] += 1
        examples_per_image_target[(image, target_id)] += 1
        image_to_targets[image].add(target_id)
        if target_text:
            image_to_target_texts[image].add(target_text.casefold())

        if not target_text.strip():
            empty_text += 1
        if mapped_text and target_text and mapped_text != target_text:
            target_text_mismatch += 1

        xs = example.get("x", []) or []
        ts = example.get("t", []) or []
        scanpath_lengths.append(len(xs))
        fixation_durations.extend(float(t) for t in ts if isinstance(t, (int, float)))

        if example.get("conversations"):
            has_conversations += 1

        center_inside, box_inside, positive_area = in_bounds(example)
        center_inside_count += int(center_inside)
        box_inside_count += int(box_inside)
        positive_area_count += int(positive_area)

        if image_root and image and not (image_root / image).exists():
            missing_images.append(image)

    unique_images = len(image_counts)
    unique_targets = len(target_counts)
    unique_target_texts = len([text for text in target_text_counts if text != "<EMPTY>"])
    repeated_image_target = sum(1 for count in examples_per_image_target.values() if count > 1)

    summary = {
        "scanpath_file": str(scanpath_path),
        "num_examples": len(examples),
        "unique_images": unique_images,
        "unique_targets": unique_targets,
        "unique_target_texts": unique_target_texts,
        "empty_target_text_examples": empty_text,
        "target2text_mismatches": target_text_mismatch,
        "examples_with_conversations": has_conversations,
        "target_center_inside_image": center_inside_count,
        "target_bbox_inside_image": box_inside_count,
        "target_bbox_positive_area": positive_area_count,
        "repeated_image_target_pairs": repeated_image_target,
        "missing_image_files": len(set(missing_images)),
        "scanpath_length": summarize_numeric(scanpath_lengths),
        "fixation_duration_seconds": summarize_numeric(fixation_durations),
        "target_prefix_counts": dict(prefix_counts.most_common()),
    }

    print(json.dumps(summary, indent=2, ensure_ascii=False))

    if args.out_dir:
        out_dir = Path(args.out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        with open(out_dir / "audit_summary.json", "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)

        write_counter_csv(out_dir / "target_prefix_counts.csv", prefix_counts, ["target_prefix", "count"])
        write_counter_csv(out_dir / "top_target_texts.csv", target_text_counts, ["target_text", "count"])
        write_counter_csv(out_dir / "image_trial_counts.csv", image_counts, ["image", "trial_count"])
        write_counter_csv(out_dir / "target_id_counts.csv", target_counts, ["target_id", "count"])

        with open(out_dir / "audit_summary.md", "w", encoding="utf-8") as f:
            f.write("# VSGUI Data Audit\n\n")
            f.write(f"- Examples: {len(examples)}\n")
            f.write(f"- Unique images: {unique_images}\n")
            f.write(f"- Unique targets: {unique_targets}\n")
            f.write(f"- Unique non-empty target texts: {unique_target_texts}\n")
            f.write(f"- Empty target text examples: {empty_text}\n")
            f.write(f"- Missing image files: {len(set(missing_images))}\n")
            f.write(f"- Target center inside image: {center_inside_count}/{len(examples)}\n")
            f.write(f"- Target bbox inside image: {box_inside_count}/{len(examples)}\n")
            f.write(f"- Examples with conversations: {has_conversations}/{len(examples)}\n\n")
            f.write("## Target Prefix Counts\n\n")
            for key, count in prefix_counts.most_common():
                f.write(f"- `{key}`: {count}\n")
            f.write("\n## Scanpath Length\n\n")
            for key, value in summary["scanpath_length"].items():
                f.write(f"- {key}: {value}\n")


if __name__ == "__main__":
    main()
