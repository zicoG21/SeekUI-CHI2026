#!/usr/bin/env python
import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path


def read_csv(path):
    with open(path, "r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path, rows, fieldnames=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = list(rows[0].keys()) if rows else []
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def split_patterns(row):
    patterns = []
    for key in ["primary_visual_pattern", "secondary_visual_pattern"]:
        value = str(row.get(key, "") or "").strip()
        if not value:
            continue
        patterns.extend(item.strip() for item in value.split(";") if item.strip())
    return patterns


def main():
    parser = argparse.ArgumentParser(description="Summarize filled combined contact-sheet visual review CSV.")
    parser.add_argument("--input-csv", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--output-md", required=True)
    args = parser.parse_args()

    rows = read_csv(Path(args.input_csv))
    pattern_counts = Counter()
    case_pattern_counts = Counter()
    model_pattern_counts = Counter()
    status_counts = Counter()
    for row in rows:
        status_counts[str(row.get("review_status", "") or "blank")] += 1
        for pattern in split_patterns(row):
            pattern_counts[pattern] += 1
            case_pattern_counts[(row.get("case_type", ""), pattern)] += 1
            model_pattern_counts[(row.get("model", ""), pattern)] += 1

    summary_rows = [
        {"scope": "overall", "group": "all", "pattern": pattern, "count": count}
        for pattern, count in pattern_counts.most_common()
    ]
    summary_rows.extend(
        {"scope": "case_type", "group": case_type, "pattern": pattern, "count": count}
        for (case_type, pattern), count in sorted(case_pattern_counts.items())
    )
    summary_rows.extend(
        {"scope": "model", "group": model, "pattern": pattern, "count": count}
        for (model, pattern), count in sorted(model_pattern_counts.items())
    )
    write_csv(Path(args.output_csv), summary_rows)
    write_json(Path(args.output_json), {
        "num_rows": len(rows),
        "review_status_counts": dict(status_counts),
        "pattern_counts": dict(pattern_counts),
        "case_pattern_counts": {f"{k[0]}::{k[1]}": v for k, v in case_pattern_counts.items()},
        "model_pattern_counts": {f"{k[0]}::{k[1]}": v for k, v in model_pattern_counts.items()},
    })

    lines = [
        "# Combined Contact-Sheet Visual Review Summary",
        "",
        f"- Review rows: {len(rows)}",
        f"- Review status counts: {dict(status_counts)}",
        "",
        "## Overall Patterns",
        "",
        "| Pattern | Count |",
        "|---|---:|",
    ]
    for pattern, count in pattern_counts.most_common():
        lines.append(f"| {pattern} | {count} |")
    lines.extend(["", "## Notes", ""])
    for row in rows:
        notes = str(row.get("notes", "") or "").strip()
        if notes:
            lines.append(f"- **{row.get('model')} / {row.get('case_type')}**: {notes}")
    Path(args.output_md).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output_md).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({
        "input_rows": len(rows),
        "output_md": args.output_md,
        "output_csv": args.output_csv,
    }, indent=2))


if __name__ == "__main__":
    main()
