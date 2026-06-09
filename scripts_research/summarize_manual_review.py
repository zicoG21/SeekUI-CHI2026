#!/usr/bin/env python
import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path


YES_VALUES = {"1", "true", "t", "yes", "y", "valid", "visible", "reasonable"}
NO_VALUES = {"0", "false", "f", "no", "n", "invalid", "not visible", "unreasonable"}


def norm(value):
    return " ".join(str(value or "").casefold().strip().split())


def normalize_answer(value):
    text = norm(value)
    if not text:
        return "blank"
    if text in YES_VALUES:
        return "yes"
    if text in NO_VALUES:
        return "no"
    return text


def safe_div(num, den):
    return num / den if den else 0.0


def read_rows(paths):
    rows = []
    for path in paths:
        with open(path, "r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                row["_source"] = str(path)
                rows.append(row)
    return rows


def answer_summary(rows, field):
    counts = Counter(normalize_answer(row.get(field, "")) for row in rows)
    annotated = sum(count for value, count in counts.items() if value != "blank")
    yes = counts.get("yes", 0)
    no = counts.get("no", 0)
    return {
        "counts": dict(counts),
        "annotated": annotated,
        "yes": yes,
        "no": no,
        "yes_rate_annotated": safe_div(yes, yes + no),
    }


def summarize(rows):
    by_type = defaultdict(list)
    for row in rows:
        by_type[row.get("review_type", "") or "unknown"].append(row)

    summary = {
        "num_rows": len(rows),
        "source_files": sorted(set(row["_source"] for row in rows)),
        "review_type_counts": dict(Counter(row.get("review_type", "") or "unknown" for row in rows)),
        "fields": {
            "review_target_visible": answer_summary(rows, "review_target_visible"),
            "review_query_valid": answer_summary(rows, "review_query_valid"),
            "review_prediction_reasonable": answer_summary(rows, "review_prediction_reasonable"),
        },
        "error_category_counts": dict(Counter(
            norm(row.get("review_error_category", "")) or "blank" for row in rows
        )),
        "by_review_type": {},
    }

    for review_type, group_rows in sorted(by_type.items()):
        summary["by_review_type"][review_type] = {
            "num_rows": len(group_rows),
            "review_target_visible": answer_summary(group_rows, "review_target_visible"),
            "review_query_valid": answer_summary(group_rows, "review_query_valid"),
            "review_prediction_reasonable": answer_summary(group_rows, "review_prediction_reasonable"),
            "error_category_counts": dict(Counter(
                norm(row.get("review_error_category", "")) or "blank" for row in group_rows
            )),
        }
    return summary


def write_markdown(path, summary):
    lines = [
        "# Manual Review Summary",
        "",
        f"- Rows: {summary['num_rows']}",
        f"- Source files: {', '.join(f'`{item}`' for item in summary['source_files'])}",
        "",
        "## Review Types",
        "",
        "| Type | Rows |",
        "|---|---:|",
    ]
    for review_type, count in sorted(summary["review_type_counts"].items()):
        lines.append(f"| {review_type} | {count} |")
    lines.extend(["", "## Annotation Fields", ""])
    lines.append("| Field | Annotated | Yes | No | Yes Rate |")
    lines.append("|---|---:|---:|---:|---:|")
    for field, field_summary in summary["fields"].items():
        lines.append(
            f"| {field} | {field_summary['annotated']} | {field_summary['yes']} | "
            f"{field_summary['no']} | {field_summary['yes_rate_annotated']:.4f} |"
        )
    lines.extend(["", "## Error Categories", ""])
    lines.append("| Category | Count |")
    lines.append("|---|---:|")
    for category, count in sorted(summary["error_category_counts"].items()):
        lines.append(f"| {category} | {count} |")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Summarize filled manual review CSV sheets.")
    parser.add_argument("--input", nargs="+", required=True, help="One or more review CSV files.")
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-md", default="")
    args = parser.parse_args()

    input_paths = [Path(item) for item in args.input]
    rows = read_rows(input_paths)
    summary = summarize(rows)

    output_json = Path(args.output_json)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    output_md = Path(args.output_md) if args.output_md else output_json.with_suffix(".md")
    write_markdown(output_md, summary)

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"Summary JSON: {output_json}")
    print(f"Summary MD  : {output_md}")


if __name__ == "__main__":
    main()
