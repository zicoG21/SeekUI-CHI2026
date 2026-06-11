#!/usr/bin/env python
import argparse
import csv
import json
import random
from pathlib import Path


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def target_key(example):
    target_id = str(example.get("target_id", "") or "")
    return target_id[4:] if target_id.startswith("txt_") else target_id


def target_text(example, target2text):
    for key in ["query_text", "target", "original_target"]:
        text = str(example.get(key, "") or "")
        if text:
            return text
    return str(target2text.get(target_key(example), "") or "")


def target_box(example):
    keys = ["target_x", "target_y", "target_width", "target_height"]
    values = [example.get(key) for key in keys]
    if any(value in {None, ""} for value in values):
        return ""
    return ",".join(str(value) for value in values)


def target_area(example):
    try:
        return float(example.get("target_width") or 0) * float(example.get("target_height") or 0)
    except (TypeError, ValueError):
        return 0.0


def present_row(review_id, example, target2text):
    query = target_text(example, target2text)
    return {
        "review_id": review_id,
        "split": "manual_seed",
        "source_type": "existing_present",
        "img_usr_tgt": example.get("img_usr_tgt", ""),
        "image": example.get("image", ""),
        "query_text": query,
        "gold_status": "present",
        "target_bbox": target_box(example),
        "target_visible": "",
        "query_realistic": "",
        "ambiguity_level": "",
        "suggested_absent_query": "",
        "notes": "",
    }


def absent_placeholder_row(review_id, example):
    return {
        "review_id": review_id,
        "split": "manual_seed",
        "source_type": "realistic_absent_placeholder",
        "img_usr_tgt": example.get("img_usr_tgt", ""),
        "image": example.get("image", ""),
        "query_text": "",
        "gold_status": "absent",
        "target_bbox": "",
        "target_visible": "",
        "query_realistic": "",
        "ambiguity_level": "",
        "suggested_absent_query": "Fill a realistic missing UI target for this screen, e.g. create account, checkout, language, help, settings.",
        "notes": "",
    }


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "review_id",
        "split",
        "source_type",
        "img_usr_tgt",
        "image",
        "query_text",
        "gold_status",
        "target_bbox",
        "target_visible",
        "query_realistic",
        "ambiguity_level",
        "suggested_absent_query",
        "notes",
    ]
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_md(path, rows):
    counts = {}
    for row in rows:
        counts[row["source_type"]] = counts.get(row["source_type"], 0) + 1
    lines = [
        "# Realistic Absent Validation Starter Sheet",
        "",
        f"- Rows: {len(rows)}",
        f"- Source counts: {counts}",
        "",
        "Fill these columns before treating the sheet as evaluation data:",
        "",
        "- `query_text` for `realistic_absent_placeholder` rows.",
        "- `target_visible`: `yes` or `no` after visual inspection.",
        "- `query_realistic`: `yes` or `no` for whether the query is plausible for the screen.",
        "- `ambiguity_level`: `low`, `medium`, or `high`.",
        "- `notes`: short reason for ambiguous or invalid rows.",
        "",
        "Use only rows with internally consistent labels for evaluation:",
        "",
        "- present rows should have `target_visible=yes`.",
        "- absent rows should have `target_visible=no` and `query_realistic=yes`.",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Export a starter CSV for a small realistic target-absent validation set.")
    parser.add_argument("--scanpath", required=True, help="Existing present-target VSGUI/SeekUI JSON.")
    parser.add_argument("--target2text", default="", help="Optional target2text.json.")
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--output-md", required=True)
    parser.add_argument("--present-count", type=int, default=50)
    parser.add_argument("--absent-count", type=int, default=50)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    examples = load_json(Path(args.scanpath))
    target2text = load_json(Path(args.target2text)) if args.target2text else {}
    examples = [example for example in examples if example.get("image")]

    present_candidates = [example for example in examples if target_text(example, target2text)]
    present_candidates.sort(key=target_area)
    small = present_candidates[: len(present_candidates) // 3]
    medium = present_candidates[len(present_candidates) // 3: 2 * len(present_candidates) // 3]
    large = present_candidates[2 * len(present_candidates) // 3:]

    selected_present = []
    buckets = [small, medium, large]
    per_bucket = max(1, args.present_count // len(buckets))
    for bucket in buckets:
        rng.shuffle(bucket)
        selected_present.extend(bucket[:per_bucket])
    remaining = [example for example in present_candidates if example not in selected_present]
    rng.shuffle(remaining)
    selected_present.extend(remaining[: max(0, args.present_count - len(selected_present))])
    selected_present = selected_present[: args.present_count]

    image_representatives = {}
    shuffled = list(examples)
    rng.shuffle(shuffled)
    for example in shuffled:
        image_representatives.setdefault(example["image"], example)
    absent_candidates = list(image_representatives.values())
    rng.shuffle(absent_candidates)
    selected_absent = absent_candidates[: args.absent_count]

    rows = []
    for example in selected_present:
        rows.append(present_row(len(rows), example, target2text))
    for example in selected_absent:
        rows.append(absent_placeholder_row(len(rows), example))

    write_csv(Path(args.output_csv), rows)
    write_md(Path(args.output_md), rows)
    print(json.dumps({
        "input_examples": len(examples),
        "present_rows": sum(1 for row in rows if row["source_type"] == "existing_present"),
        "absent_placeholder_rows": sum(1 for row in rows if row["source_type"] == "realistic_absent_placeholder"),
        "output_csv": args.output_csv,
        "output_md": args.output_md,
    }, indent=2))


if __name__ == "__main__":
    main()
