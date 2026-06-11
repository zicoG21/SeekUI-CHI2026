#!/usr/bin/env python
import argparse
import csv
import json
from pathlib import Path


KEY_ROWS = [
    ("vlm_wrong_combined_correct", "absent_case"),
    ("combined_wrong_vlm_correct", "present_case"),
    ("both_wrong", "absent_case"),
    ("both_wrong", "present_case"),
]


def read_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "label",
        "case_source",
        "case_type",
        "count",
        "mean_path_best_evidence",
        "mean_ocr_score",
    ]
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def fmt_num(value):
    if value == "" or value is None:
        return ""
    return f"{float(value):.4f}"


def write_md(path, rows):
    lines = [
        "# VLM Hard-Case Comparison",
        "",
        "Key rows compare each VLM-style verifier against the same combined AND prediction file.",
        "",
        "| Label | Case Source | Case Type | Count | Mean Path Evidence | Mean OCR Score |",
        "|---|---|---|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['label']} | {row['case_source']} | {row['case_type']} | {row['count']} | "
            f"{fmt_num(row['mean_path_best_evidence'])} | {fmt_num(row['mean_ocr_score'])} |"
        )
    lines.extend([
        "",
        "Interpretation:",
        "",
        "- `vlm_wrong_combined_correct / absent_case`: VLM still says present on absent examples that combined AND rejects correctly.",
        "- `combined_wrong_vlm_correct / present_case`: combined AND over-rejects visible present targets that VLM rescues.",
        "- `both_wrong / absent_case`: hard distractor or OCR-leak cases where both systems say present.",
        "- `both_wrong / present_case`: visible targets missed by both systems.",
    ])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def rows_from_summary(label, path):
    data = read_json(path)
    rows = []
    for report in data.values():
        for row in report.get("summary", []):
            key = (row.get("case_source"), row.get("case_type"))
            if key in KEY_ROWS:
                rows.append({
                    "label": label,
                    "case_source": row.get("case_source"),
                    "case_type": row.get("case_type"),
                    "count": row.get("count", 0),
                    "mean_path_best_evidence": row.get("mean_path_best_evidence", ""),
                    "mean_ocr_score": row.get("mean_ocr_score", ""),
                })
    order = {key: idx for idx, key in enumerate(KEY_ROWS)}
    rows.sort(key=lambda row: order[(row["case_source"], row["case_type"])])
    return rows


def parse_summary_spec(spec):
    if "=" not in spec:
        path = Path(spec)
        return path.parent.name, path
    label, raw_path = spec.split("=", 1)
    return label, Path(raw_path)


def main():
    parser = argparse.ArgumentParser(description="Compare multiple VLM-vs-combined hard-case summaries.")
    parser.add_argument("--summary", action="append", required=True, help="LABEL=PATH or PATH. Can repeat.")
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--output-md", required=True)
    args = parser.parse_args()

    rows = []
    for spec in args.summary:
        label, path = parse_summary_spec(spec)
        rows.extend(rows_from_summary(label, path))

    write_csv(Path(args.output_csv), rows)
    write_md(Path(args.output_md), rows)
    print(json.dumps({
        "rows": len(rows),
        "output_csv": args.output_csv,
        "output_md": args.output_md,
    }, indent=2))


if __name__ == "__main__":
    main()
