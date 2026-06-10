#!/usr/bin/env python
import argparse
import csv
import json
from collections import Counter
from pathlib import Path


ABSENT_STATUSES = {"absent", "not_found", "not found", "no object", "no target", "not present"}


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def normalize_status(value, default="present"):
    text = str(value or default).casefold()
    return "absent" if text in ABSENT_STATUSES else "present"


def gold_status(example):
    if "target_present" in example:
        return "present" if example["target_present"] else "absent"
    return normalize_status(example.get("status"), default="present")


def predicted_status(example):
    status = str(example.get("predicted_status", "") or "").casefold()
    if status in ABSENT_STATUSES:
        return "absent"
    if status == "present":
        return "present"
    return "present" if example.get("prediction", []) else "absent"


def truthy(value):
    return str(value).strip().casefold() in {"1", "true", "yes", "y"}


def excluded_indices(path, flags):
    excluded = set()
    rows = []
    with open(path, "r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            idx = int(row["index"])
            matched = [flag for flag in flags if truthy(row.get(flag, ""))]
            if matched:
                excluded.add(idx)
                rows.append({
                    "index": idx,
                    "matched_flags": ",".join(matched),
                    "image": row.get("image", ""),
                    "target": row.get("target", ""),
                })
    return excluded, rows


def safe_div(num, den):
    return num / den if den else 0.0


def evaluate(examples, exclude):
    confusion = Counter()
    kept = 0
    excluded = 0
    for idx, example in enumerate(examples):
        if idx in exclude:
            excluded += 1
            continue
        kept += 1
        confusion[(gold_status(example), predicted_status(example))] += 1
    tp_absent = confusion[("absent", "absent")]
    fp_absent = confusion[("present", "absent")]
    fn_absent = confusion[("absent", "present")]
    tn_absent = confusion[("present", "present")]
    total = tp_absent + fp_absent + fn_absent + tn_absent
    precision = safe_div(tp_absent, tp_absent + fp_absent)
    recall = safe_div(tp_absent, tp_absent + fn_absent)
    f1 = safe_div(2 * precision * recall, precision + recall)
    return {
        "num_examples": total,
        "kept_examples": kept,
        "excluded_examples": excluded,
        "confusion": {
            "present->present": tn_absent,
            "present->absent": fp_absent,
            "absent->present": fn_absent,
            "absent->absent": tp_absent,
        },
        "accuracy": safe_div(tp_absent + tn_absent, total),
        "absent_precision": precision,
        "absent_recall": recall,
        "absent_f1": f1,
    }


def main():
    parser = argparse.ArgumentParser(description="Evaluate present/absent status after excluding flagged benchmark rows.")
    parser.add_argument("--filter-csv", required=True)
    parser.add_argument("--exclude-flag", action="append", required=True)
    parser.add_argument("--prediction", action="append", required=True, help="NAME=PATH. Can repeat.")
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--excluded-output", default="")
    args = parser.parse_args()

    exclude, excluded_rows = excluded_indices(Path(args.filter_csv), args.exclude_flag)
    rows = []
    report = {
        "filter_csv": args.filter_csv,
        "exclude_flags": args.exclude_flag,
        "excluded_indices": len(exclude),
        "models": {},
    }

    for spec in args.prediction:
        if "=" not in spec:
            raise ValueError(f"Prediction must be NAME=PATH, got {spec}")
        name, raw_path = spec.split("=", 1)
        path = Path(raw_path)
        if not path.exists():
            print(f"Skipping missing prediction: {path}")
            continue
        metrics = evaluate(load_json(path), exclude)
        report["models"][name] = metrics
        confusion = metrics["confusion"]
        rows.append({
            "name": name,
            "num_examples": metrics["num_examples"],
            "excluded_examples": metrics["excluded_examples"],
            "accuracy": metrics["accuracy"],
            "absent_precision": metrics["absent_precision"],
            "absent_recall": metrics["absent_recall"],
            "absent_f1": metrics["absent_f1"],
            "present_absent": confusion["present->absent"],
            "absent_present": confusion["absent->present"],
        })

    write_json(Path(args.output_json), report)
    write_csv(Path(args.output_csv), rows)
    if args.excluded_output:
        write_csv(Path(args.excluded_output), excluded_rows)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
