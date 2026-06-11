#!/usr/bin/env python
import argparse
import csv
import json
from pathlib import Path


YES = {"yes", "y", "true", "1"}
NO = {"no", "n", "false", "0"}


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def read_csv(path):
    with open(path, "r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = sorted({key for row in rows for key in row})
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def normalize_status(value):
    text = str(value or "").strip().casefold()
    if text in {"present", "p"}:
        return "present"
    if text in {"absent", "a", "not_found", "not found", "not present"}:
        return "absent"
    return ""


def normalize_yes_no(value):
    text = str(value or "").strip().casefold()
    if text in YES:
        return "yes"
    if text in NO:
        return "no"
    return ""


def by_img_usr_tgt(examples):
    return {example.get("img_usr_tgt"): example for example in examples if example.get("img_usr_tgt")}


def by_image(examples):
    result = {}
    for example in examples:
        result.setdefault(example.get("image"), example)
    return result


def parse_bbox(value):
    parts = [part.strip() for part in str(value or "").split(",") if part.strip()]
    if len(parts) != 4:
        return {}
    try:
        x, y, w, h = [float(part) for part in parts]
    except ValueError:
        return {}
    return {
        "target_x": x,
        "target_y": y,
        "target_width": w,
        "target_height": h,
    }


def source_example(row, by_id, by_img):
    return by_id.get(row.get("img_usr_tgt")) or by_img.get(row.get("image")) or {}


def validation_reason(row):
    gold = normalize_status(row.get("gold_status"))
    target_visible = normalize_yes_no(row.get("target_visible"))
    query_realistic = normalize_yes_no(row.get("query_realistic"))
    query_text = str(row.get("query_text", "") or "").strip()
    ambiguity = str(row.get("ambiguity_level", "") or "").strip().casefold()

    if gold not in {"present", "absent"}:
        return "invalid_gold_status"
    if not query_text:
        return "missing_query_text"
    if target_visible not in {"yes", "no"}:
        return "missing_target_visible"
    if query_realistic not in {"yes", "no"}:
        return "missing_query_realistic"
    if query_realistic != "yes":
        return "query_not_realistic"
    if gold == "present" and target_visible != "yes":
        return "present_not_visible"
    if gold == "absent" and target_visible != "no":
        return "absent_marked_visible"
    if ambiguity == "high":
        return "high_ambiguity"
    return ""


def build_example(row, source):
    gold = normalize_status(row.get("gold_status"))
    query = str(row.get("query_text", "") or "").strip()
    result = dict(source)
    result.update({
        "img_usr_tgt": f"manual_real_absent_{row.get('review_id', len(query))}_{gold}",
        "image": row.get("image") or source.get("image", ""),
        "target": query,
        "query_text": query,
        "original_target": source.get("target", ""),
        "target_id": f"manual_{row.get('review_id', '')}",
        "status": gold,
        "target_present": gold == "present",
        "manual_review_id": row.get("review_id", ""),
        "manual_source_type": row.get("source_type", ""),
        "manual_target_visible": normalize_yes_no(row.get("target_visible")),
        "manual_query_realistic": normalize_yes_no(row.get("query_realistic")),
        "manual_ambiguity_level": row.get("ambiguity_level", ""),
        "manual_notes": row.get("notes", ""),
    })
    result.pop("conversations", None)
    if gold == "present":
        result.update(parse_bbox(row.get("target_bbox")))
    else:
        result["x"] = []
        result["y"] = []
        result["t"] = []
        result["target_x"] = None
        result["target_y"] = None
        result["target_width"] = None
        result["target_height"] = None
    return result


def write_md(path, summary, excluded_rows):
    lines = [
        "# Realistic Absent Validation Dataset Prep",
        "",
        f"- Input rows: {summary['input_rows']}",
        f"- Included rows: {summary['included_rows']}",
        f"- Excluded rows: {summary['excluded_rows']}",
        f"- Present rows: {summary['present_rows']}",
        f"- Absent rows: {summary['absent_rows']}",
        "",
        "## Exclusion Reasons",
        "",
        "| Reason | Count |",
        "|---|---:|",
    ]
    for reason, count in sorted(summary["exclusion_reasons"].items()):
        lines.append(f"| {reason} | {count} |")
    if excluded_rows:
        lines.extend([
            "",
            "See the excluded CSV for row-level details.",
        ])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Convert a filled realistic absent validation CSV into model/eval JSON.")
    parser.add_argument("--sheet", required=True, help="Filled CSV from export_real_absent_validation_sheet.py.")
    parser.add_argument("--scanpath", required=True, help="Original scanpath JSON for metadata lookup.")
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--excluded-csv", required=True)
    parser.add_argument("--summary-md", required=True)
    parser.add_argument("--include-high-ambiguity", action="store_true")
    args = parser.parse_args()

    rows = read_csv(Path(args.sheet))
    source_examples = load_json(Path(args.scanpath))
    source_by_id = by_img_usr_tgt(source_examples)
    source_by_image = by_image(source_examples)

    included = []
    excluded = []
    reason_counts = {}
    for row in rows:
        reason = validation_reason(row)
        if args.include_high_ambiguity and reason == "high_ambiguity":
            reason = ""
        if reason:
            excluded_row = dict(row)
            excluded_row["exclude_reason"] = reason
            excluded.append(excluded_row)
            reason_counts[reason] = reason_counts.get(reason, 0) + 1
            continue
        included.append(build_example(row, source_example(row, source_by_id, source_by_image)))

    summary = {
        "input_rows": len(rows),
        "included_rows": len(included),
        "excluded_rows": len(excluded),
        "present_rows": sum(1 for example in included if example["status"] == "present"),
        "absent_rows": sum(1 for example in included if example["status"] == "absent"),
        "exclusion_reasons": reason_counts,
        "output_json": args.output_json,
        "excluded_csv": args.excluded_csv,
    }

    write_json(Path(args.output_json), included)
    write_csv(Path(args.excluded_csv), excluded)
    write_md(Path(args.summary_md), summary, excluded)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
