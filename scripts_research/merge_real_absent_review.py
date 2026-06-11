#!/usr/bin/env python
import argparse
import csv
import json
from pathlib import Path


def read_csv(path):
    with open(path, "r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path, rows, fieldnames):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


MERGE_FIELDS = [
    "query_text",
    "target_visible",
    "query_realistic",
    "ambiguity_level",
    "notes",
]


def main():
    parser = argparse.ArgumentParser(description="Merge filled realistic absent review rows back into the prefilled sheet.")
    parser.add_argument("--base-csv", required=True)
    parser.add_argument("--review-csv", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--summary-md", required=True)
    args = parser.parse_args()

    base_rows = read_csv(Path(args.base_csv))
    review_rows = read_csv(Path(args.review_csv))
    review_by_id = {str(row.get("review_id", "")): row for row in review_rows}

    merged = []
    updated = 0
    missing = 0
    for row in base_rows:
        row = dict(row)
        review = review_by_id.get(str(row.get("review_id", "")))
        if review:
            changed = False
            for field in MERGE_FIELDS:
                value = str(review.get(field, "") or "").strip()
                if value and value != str(row.get(field, "") or "").strip():
                    row[field] = value
                    changed = True
            if changed:
                updated += 1
        elif row.get("gold_status") == "absent":
            missing += 1
        merged.append(row)

    fieldnames = list(base_rows[0].keys()) if base_rows else []
    for field in MERGE_FIELDS:
        if field not in fieldnames:
            fieldnames.append(field)
    write_csv(Path(args.output_csv), merged, fieldnames)

    absent_rows = [row for row in merged if row.get("gold_status") == "absent"]
    absent_ready = [
        row for row in absent_rows
        if row.get("query_text") and row.get("target_visible") and row.get("query_realistic") and row.get("ambiguity_level")
    ]
    lines = [
        "# Merged Realistic Absent Review",
        "",
        f"- Base rows: {len(base_rows)}",
        f"- Review rows: {len(review_rows)}",
        f"- Updated base rows: {updated}",
        f"- Absent rows missing from review CSV: {missing}",
        f"- Absent rows with all required review fields: {len(absent_ready)} / {len(absent_rows)}",
        f"- Output CSV: `{args.output_csv}`",
    ]
    Path(args.summary_md).parent.mkdir(parents=True, exist_ok=True)
    Path(args.summary_md).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({
        "base_rows": len(base_rows),
        "review_rows": len(review_rows),
        "updated_rows": updated,
        "absent_ready_rows": len(absent_ready),
        "absent_rows": len(absent_rows),
        "output_csv": args.output_csv,
        "summary_md": args.summary_md,
    }, indent=2))


if __name__ == "__main__":
    main()
