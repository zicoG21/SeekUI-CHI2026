#!/usr/bin/env python
import argparse
import csv
import json
import math
from collections import Counter
from pathlib import Path


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def sample_id(example):
    return example.get("img_usr_tgt") or f"{example.get('image', '')}::{example.get('target_id', '')}::{example.get('username', '')}"


def target_center(example):
    try:
        x = float(example["target_x"]) + float(example["target_width"]) / 2
        y = float(example["target_y"]) + float(example["target_height"]) / 2
        return x, y
    except (KeyError, TypeError, ValueError):
        return None


def dist(a, b):
    if not a or not b:
        return None
    return math.hypot(float(a[0]) - float(b[0]), float(a[1]) - float(b[1]))


def first_point(example):
    pred = example.get("prediction", []) or []
    return pred[0] if pred else None


def last_point(example):
    pred = example.get("prediction", []) or []
    return pred[-1] if pred else None


def mean(values):
    values = [value for value in values if value is not None]
    return sum(values) / len(values) if values else None


def summarize(rows):
    summary = {
        "num_matched": len(rows),
        "a_empty": sum(1 for row in rows if row["a_len"] == 0),
        "b_empty": sum(1 for row in rows if row["b_len"] == 0),
        "mean_a_len": mean([row["a_len"] for row in rows]),
        "mean_b_len": mean([row["b_len"] for row in rows]),
        "mean_len_delta_b_minus_a": mean([row["len_delta_b_minus_a"] for row in rows]),
        "mean_last_point_distance": mean([row["last_point_distance"] for row in rows]),
        "mean_a_last_to_target": mean([row["a_last_to_target"] for row in rows]),
        "mean_b_last_to_target": mean([row["b_last_to_target"] for row in rows]),
        "b_closer_to_target_count": sum(
            1 for row in rows
            if row["a_last_to_target"] is not None
            and row["b_last_to_target"] is not None
            and row["b_last_to_target"] < row["a_last_to_target"]
        ),
        "a_closer_to_target_count": sum(
            1 for row in rows
            if row["a_last_to_target"] is not None
            and row["b_last_to_target"] is not None
            and row["a_last_to_target"] < row["b_last_to_target"]
        ),
    }
    return summary


def index_by_id(data):
    ids = [sample_id(example) for example in data]
    counts = Counter(ids)
    by_id = {}
    duplicates = {}
    for example_id, example in zip(ids, data):
        if counts[example_id] > 1:
            duplicates.setdefault(example_id, 0)
            duplicates[example_id] += 1
        by_id[example_id] = example
    return by_id, duplicates


def write_markdown(path, label_a, label_b, summary):
    lines = [
        "# Prediction Comparison",
        "",
        f"- A: `{label_a}`",
        f"- B: `{label_b}`",
        f"- A examples: {summary.get('num_a', 'n/a')}",
        f"- B examples: {summary.get('num_b', 'n/a')}",
        f"- Matched examples: {summary['num_matched']}",
        f"- A-only examples: {summary.get('a_only', 'n/a')}",
        f"- B-only examples: {summary.get('b_only', 'n/a')}",
        f"- A duplicate ids: {summary.get('a_duplicate_ids', 'n/a')}",
        f"- B duplicate ids: {summary.get('b_duplicate_ids', 'n/a')}",
        f"- A empty predictions: {summary['a_empty']}",
        f"- B empty predictions: {summary['b_empty']}",
        f"- Mean A length: {summary['mean_a_len']:.4f}" if summary["mean_a_len"] is not None else "- Mean A length: n/a",
        f"- Mean B length: {summary['mean_b_len']:.4f}" if summary["mean_b_len"] is not None else "- Mean B length: n/a",
        f"- Mean length delta B-A: {summary['mean_len_delta_b_minus_a']:.4f}" if summary["mean_len_delta_b_minus_a"] is not None else "- Mean length delta B-A: n/a",
        f"- Mean last-point distance A vs B: {summary['mean_last_point_distance']:.4f}" if summary["mean_last_point_distance"] is not None else "- Mean last-point distance A vs B: n/a",
        f"- Mean A last-to-target: {summary['mean_a_last_to_target']:.4f}" if summary["mean_a_last_to_target"] is not None else "- Mean A last-to-target: n/a",
        f"- Mean B last-to-target: {summary['mean_b_last_to_target']:.4f}" if summary["mean_b_last_to_target"] is not None else "- Mean B last-to-target: n/a",
        f"- B closer to target count: {summary['b_closer_to_target_count']}",
        f"- A closer to target count: {summary['a_closer_to_target_count']}",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Compare two SeekUI prediction JSON files on matched examples.")
    parser.add_argument("--a", required=True, help="First prediction JSON.")
    parser.add_argument("--b", required=True, help="Second prediction JSON.")
    parser.add_argument("--label-a", default="A")
    parser.add_argument("--label-b", default="B")
    parser.add_argument("--out-csv", required=True)
    parser.add_argument("--out-json", default="")
    parser.add_argument("--out-md", default="")
    args = parser.parse_args()

    data_a = load_json(Path(args.a))
    data_b = load_json(Path(args.b))
    by_id_a, duplicates_a = index_by_id(data_a)
    by_id_b, duplicates_b = index_by_id(data_b)
    ids_a = set(by_id_a)
    ids_b = set(by_id_b)
    ids = sorted(ids_a & ids_b)

    rows = []
    for item_id in ids:
        a = by_id_a[item_id]
        b = by_id_b[item_id]
        a_pred = a.get("prediction", []) or []
        b_pred = b.get("prediction", []) or []
        center = target_center(a) or target_center(b)
        a_last = last_point(a)
        b_last = last_point(b)
        row = {
            "img_usr_tgt": item_id,
            "image": a.get("image", b.get("image", "")),
            "target": a.get("target", b.get("target", "")),
            "a_len": len(a_pred),
            "b_len": len(b_pred),
            "len_delta_b_minus_a": len(b_pred) - len(a_pred),
            "first_point_distance": dist(first_point(a), first_point(b)),
            "last_point_distance": dist(a_last, b_last),
            "a_last_to_target": dist(a_last, center),
            "b_last_to_target": dist(b_last, center),
            "a_predicted_status": a.get("predicted_status", ""),
            "b_predicted_status": b.get("predicted_status", ""),
        }
        rows.append(row)

    out_csv = Path(args.out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "img_usr_tgt",
        "image",
        "target",
        "a_len",
        "b_len",
        "len_delta_b_minus_a",
        "first_point_distance",
        "last_point_distance",
        "a_last_to_target",
        "b_last_to_target",
        "a_predicted_status",
        "b_predicted_status",
    ]
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    summary = summarize(rows)
    summary.update({
        "num_a": len(data_a),
        "num_b": len(data_b),
        "a_only": len(ids_a - ids_b),
        "b_only": len(ids_b - ids_a),
        "a_duplicate_ids": len(duplicates_a),
        "b_duplicate_ids": len(duplicates_b),
    })
    out_json = Path(args.out_json) if args.out_json else out_csv.with_suffix(".json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    out_md = Path(args.out_md) if args.out_md else out_csv.with_suffix(".md")
    write_markdown(out_md, args.label_a, args.label_b, summary)

    print(json.dumps(summary, indent=2))
    print(f"Rows written   : {out_csv}")
    print(f"Summary JSON   : {out_json}")
    print(f"Summary Markdown: {out_md}")


if __name__ == "__main__":
    main()
