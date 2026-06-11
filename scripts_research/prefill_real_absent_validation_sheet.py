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


def append_note(existing, note):
    existing = str(existing or "").strip()
    if not existing:
        return note
    if note in existing:
        return existing
    return f"{existing}; {note}"


def prefill_row(row, fill_absent_from_suggestion):
    row = dict(row)
    changed = []
    source_type = row.get("source_type", "")
    gold = row.get("gold_status", "")

    if source_type == "existing_present" or gold == "present":
        if not row.get("target_visible"):
            row["target_visible"] = "yes"
            changed.append("target_visible")
        if not row.get("query_realistic"):
            row["query_realistic"] = "yes"
            changed.append("query_realistic")
        if not row.get("ambiguity_level"):
            row["ambiguity_level"] = "low"
            changed.append("ambiguity_level")
        row["notes"] = append_note(row.get("notes"), "auto_prefilled_present_verify_if_used")

    elif source_type == "realistic_absent_placeholder" or gold == "absent":
        if fill_absent_from_suggestion and not row.get("query_text") and row.get("suggested_absent_query"):
            row["query_text"] = row["suggested_absent_query"]
            changed.append("query_text")
        # Do not auto-mark absent rows as visually absent or realistic; that is the validation itself.
        row["notes"] = append_note(row.get("notes"), "needs_visual_query_review")

    row["_prefill_changed_fields"] = ",".join(changed)
    return row


def write_md(path, rows):
    counts = {}
    changed = 0
    for row in rows:
        counts[row.get("source_type", "")] = counts.get(row.get("source_type", ""), 0) + 1
        if row.get("_prefill_changed_fields"):
            changed += 1
    missing_absent_query = sum(
        1 for row in rows
        if row.get("gold_status") == "absent" and not str(row.get("query_text", "")).strip()
    )
    missing_review_fields = sum(
        1 for row in rows
        if not row.get("target_visible") or not row.get("query_realistic") or not row.get("ambiguity_level")
    )
    lines = [
        "# Prefilled Realistic Absent Validation Sheet",
        "",
        f"- Rows: {len(rows)}",
        f"- Source counts: {counts}",
        f"- Rows with auto-filled fields: {changed}",
        f"- Absent rows still missing query_text: {missing_absent_query}",
        f"- Rows still missing one or more review fields: {missing_review_fields}",
        "",
        "Notes:",
        "",
        "- Existing-present rows are prefilled as visible, realistic, low ambiguity.",
        "- Absent placeholder rows are not automatically marked as absent or realistic.",
        "- Treat this as a review accelerator, not a finished evaluation file.",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Prefill safe fields in the realistic absent validation starter CSV.")
    parser.add_argument("--input-csv", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--output-md", required=True)
    parser.add_argument(
        "--fill-absent-from-suggestion",
        action="store_true",
        help="Copy suggested_absent_query into blank absent query_text. Off by default because suggestions are generic.",
    )
    args = parser.parse_args()

    rows = read_csv(Path(args.input_csv))
    fieldnames = list(rows[0].keys()) if rows else []
    if "_prefill_changed_fields" not in fieldnames:
        fieldnames.append("_prefill_changed_fields")
    filled = [prefill_row(row, args.fill_absent_from_suggestion) for row in rows]
    write_csv(Path(args.output_csv), filled, fieldnames)
    write_md(Path(args.output_md), filled)
    print(json.dumps({
        "input_rows": len(rows),
        "output_csv": args.output_csv,
        "output_md": args.output_md,
        "changed_rows": sum(1 for row in filled if row.get("_prefill_changed_fields")),
        "absent_missing_query_text": sum(
            1 for row in filled
            if row.get("gold_status") == "absent" and not str(row.get("query_text", "")).strip()
        ),
    }, indent=2))


if __name__ == "__main__":
    main()
