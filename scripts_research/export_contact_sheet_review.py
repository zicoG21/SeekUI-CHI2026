#!/usr/bin/env python
import argparse
import csv
import json
from pathlib import Path


VISUAL_PATTERN_OPTIONS = [
    "no_clear_target_match",
    "strong_text_distractor",
    "strong_icon_or_button_distractor",
    "small_target",
    "edge_or_corner_target",
    "low_contrast_or_stylized_text",
    "ocr_miss",
    "under_search_short_path",
    "overconfident_forced_choice",
    "ambiguous_target",
    "layout_clutter",
]


def read_csv(path):
    if not path.exists() or path.stat().st_size == 0:
        return []
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


def parse_model(case_dir):
    name = case_dir.name
    if name.startswith("SeekUI_sft"):
        return "SeekUI_sft"
    if name.startswith("SeekUI"):
        return "SeekUI"
    return name.split("_", 1)[0]


def contact_sheet_for(case_dir, case_type):
    candidates = [
        case_dir / "contact_sheet_export" / f"{case_type}_contact_sheet.jpg",
        case_dir / "visualizations" / f"{case_type}_contact_sheet.jpg",
    ]
    model = parse_model(case_dir)
    candidates.extend([
        case_dir / "contact_sheet_export" / f"{model}_and_{case_type}_contact_sheet.jpg",
        case_dir / "visualizations" / f"{model}_and_{case_type}_contact_sheet.jpg",
    ])
    for path in candidates:
        if path.exists():
            return str(path)
    return ""


def main():
    parser = argparse.ArgumentParser(description="Create visual review sheet for combined contact-sheet taxonomy.")
    parser.add_argument("--case-dir", action="append", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--output-md", required=True)
    parser.add_argument("--output-json", required=True)
    args = parser.parse_args()

    rows = []
    for raw_case_dir in args.case_dir:
        case_dir = Path(raw_case_dir)
        model = parse_model(case_dir)
        index_rows = read_csv(case_dir / "stopping_cases_index.csv")
        by_case = {}
        for row in index_rows:
            by_case.setdefault(row.get("case_type", ""), []).append(row)
        for case_type, case_rows in sorted(by_case.items()):
            rows.append({
                "model": model,
                "case_type": case_type,
                "selected_rows": len(case_rows),
                "contact_sheet": contact_sheet_for(case_dir, case_type),
                "primary_visual_pattern": "",
                "secondary_visual_pattern": "",
                "representative_examples": "",
                "notes": "",
                "review_status": "pending",
            })

    fieldnames = [
        "model",
        "case_type",
        "selected_rows",
        "contact_sheet",
        "primary_visual_pattern",
        "secondary_visual_pattern",
        "representative_examples",
        "notes",
        "review_status",
    ]
    write_csv(Path(args.output_csv), rows, fieldnames)
    write_json(Path(args.output_json), {
        "pattern_options": VISUAL_PATTERN_OPTIONS,
        "rows": rows,
    })

    lines = [
        "# Combined Contact-Sheet Visual Review",
        "",
        "Fill `primary_visual_pattern`, `secondary_visual_pattern`, representative examples, and notes after inspecting each contact sheet.",
        "",
        "Suggested pattern labels:",
        "",
    ]
    lines.extend(f"- `{item}`" for item in VISUAL_PATTERN_OPTIONS)
    lines.extend([
        "",
        "| Model | Case Type | Selected Rows | Contact Sheet |",
        "|---|---|---:|---|",
    ])
    for row in rows:
        lines.append(
            f"| {row['model']} | {row['case_type']} | {row['selected_rows']} | {row['contact_sheet']} |"
        )
    Path(args.output_md).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output_md).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({
        "rows": len(rows),
        "output_csv": args.output_csv,
        "output_md": args.output_md,
    }, indent=2))


if __name__ == "__main__":
    main()
