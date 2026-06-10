#!/usr/bin/env python
import argparse
import csv
from pathlib import Path


def read_rows(path):
    with open(path, "r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def as_float(row, key):
    try:
        return float(row.get(key, 0) or 0)
    except ValueError:
        return 0.0


def choose(rows, predicate, key):
    candidates = [row for row in rows if predicate(row)]
    if not candidates:
        return None
    return max(candidates, key=lambda row: (as_float(row, key), as_float(row, "accuracy")))


def compact_row(name, criterion, row):
    if row is None:
        return {
            "name": name,
            "criterion": criterion,
            "threshold": "",
            "accuracy": "",
            "absent_precision": "",
            "absent_recall": "",
            "absent_f1": "",
            "changed_predictions": "",
            "present_absent": "",
            "absent_present": "",
        }
    return {
        "name": name,
        "criterion": criterion,
        "threshold": row.get("threshold", ""),
        "accuracy": row.get("accuracy", ""),
        "absent_precision": row.get("absent_precision", ""),
        "absent_recall": row.get("absent_recall", ""),
        "absent_f1": row.get("absent_f1", ""),
        "changed_predictions": row.get("changed_predictions", ""),
        "present_absent": row.get("present_absent", ""),
        "absent_present": row.get("absent_present", ""),
    }


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys()) if rows else []
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_md(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Cognitive Stopping Threshold Summary",
        "",
        "| Name | Criterion | Threshold | Accuracy | Absent Precision | Absent Recall | Absent F1 | Changed | Present->Absent | Absent->Present |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['name']} | {row['criterion']} | {row['threshold']} | "
            f"{row['accuracy']} | {row['absent_precision']} | {row['absent_recall']} | "
            f"{row['absent_f1']} | {row['changed_predictions']} | {row['present_absent']} | {row['absent_present']} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Summarize cognitive stopping threshold sweeps.")
    parser.add_argument("--sweep", action="append", required=True, help="NAME=CSV threshold sweep. Can repeat.")
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--output-md", required=True)
    parser.add_argument("--min-precision", type=float, default=0.75)
    parser.add_argument("--min-recall", type=float, default=0.90)
    args = parser.parse_args()

    summary_rows = []
    for spec in args.sweep:
        if "=" not in spec:
            raise ValueError(f"Sweep must be NAME=CSV, got: {spec}")
        name, raw_path = spec.split("=", 1)
        rows = read_rows(Path(raw_path))
        summary_rows.extend([
            compact_row(name, "best_absent_f1", choose(rows, lambda row: True, "absent_f1")),
            compact_row(name, "best_accuracy", choose(rows, lambda row: True, "accuracy")),
            compact_row(
                name,
                f"best_f1_precision_ge_{args.min_precision:g}",
                choose(rows, lambda row: as_float(row, "absent_precision") >= args.min_precision, "absent_f1"),
            ),
            compact_row(
                name,
                f"best_f1_recall_ge_{args.min_recall:g}",
                choose(rows, lambda row: as_float(row, "absent_recall") >= args.min_recall, "absent_f1"),
            ),
        ])

    write_csv(Path(args.output_csv), summary_rows)
    write_md(Path(args.output_md), summary_rows)
    print(f"Wrote {args.output_csv}")
    print(f"Wrote {args.output_md}")


if __name__ == "__main__":
    main()
