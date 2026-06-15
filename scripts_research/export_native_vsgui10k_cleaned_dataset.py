#!/usr/bin/env python
import argparse
import csv
import json
import shutil
from collections import Counter
from pathlib import Path


def load_json(path, default=None):
    path = Path(path)
    if not path.exists():
        return default if default is not None else []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def read_csv(path):
    path = Path(path)
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def write_csv(path, rows, fieldnames=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = []
        for row in rows:
            for key in row:
                if key not in fieldnames:
                    fieldnames.append(key)
        if not fieldnames:
            fieldnames = ["empty"]
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def copy_if_exists(src, dst):
    src = Path(src)
    if not src.exists():
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return True


def status_counts(rows):
    counts = Counter(str(row.get("status", "")).casefold() for row in rows)
    return {"present": counts.get("present", 0), "absent": counts.get("absent", 0), "rows": len(rows)}


def compact_image_cue_row(row):
    return {
        "index": row.get("index", ""),
        "key": row.get("key", ""),
        "gold_status": row.get("gold_status", ""),
        "image": row.get("image", ""),
        "native_new_img_name": row.get("native_new_img_name", ""),
        "matched_cue_field": row.get("matched_cue_field", ""),
        "resolution_status": row.get("resolution_status", ""),
        "num_matches": row.get("num_matches", ""),
        "selected_path": row.get("selected_path", ""),
        "notes": row.get("notes", ""),
    }


def split_record(name, role, description, json_path, csv_path):
    rows = load_json(json_path, default=[])
    counts = status_counts(rows)
    return {
        "name": name,
        "role": role,
        "description": description,
        "rows": counts["rows"],
        "present": counts["present"],
        "absent": counts["absent"],
        "json": str(json_path),
        "csv": str(csv_path),
    }


def add_split(manifest_rows, source_json, source_csv, out_json, out_csv, name, role, description):
    copied_json = copy_if_exists(source_json, out_json)
    copied_csv = copy_if_exists(source_csv, out_csv)
    if copied_json:
        if not copied_csv:
            rows = load_json(out_json, default=[])
            write_csv(out_csv, rows)
            copied_csv = True
        manifest_rows.append(split_record(name, role, description, out_json, out_csv if copied_csv else source_csv))


def write_summary(path, manifest, image_cue_summary):
    lines = [
        "# Native VSGUI10K Cleaned Dataset",
        "",
        "This package separates paper-facing clean target-absence splits from diagnostic or excluded native VSGUI10K rows.",
        "",
        "## Split Manifest",
        "",
        "| Split | Role | Rows | Present | Absent | Description |",
        "|---|---|---:|---:|---:|---|",
    ]
    for row in manifest:
        lines.append(
            f"| {row['name']} | {row['role']} | {row['rows']} | {row['present']} | {row['absent']} | {row['description']} |"
        )
    lines.extend(["", "## Image-Cue Resolution", ""])
    if image_cue_summary:
        lines.extend([
            f"- Total image-cue rows: {image_cue_summary.get('total', 0)}",
            f"- Resolved/evaluable rows: {image_cue_summary.get('resolved', 0)}",
            f"- Balanced resolved rows: {image_cue_summary.get('balanced', 0)}",
            f"- Missing rows: {image_cue_summary.get('missing', 0)}",
            f"- Ambiguous rows excluded after review: {image_cue_summary.get('ambiguous_excluded', 0)}",
        ])
    else:
        lines.append("- No image-cue resolution artifacts were found.")
    lines.extend([
        "",
        "## Recommended Use",
        "",
        "- Use `headline_*` splits for main native text/text+color target-absence evaluation.",
        "- Use `diagnostic_visible_conflicts` to discuss noisy native labels where absent targets have visible text evidence.",
        "- Use `diagnostic_color_instance*` for color/instance matching stress tests, not as solved target absence.",
        "- Use `diagnostic_image_cue_resolved*` only as a small pilot because cue-asset coverage is limited.",
        "- Do not pool headline, diagnostic, and excluded rows into one headline metric.",
        "",
    ])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Export final cleaned Native VSGUI10K dataset package.")
    parser.add_argument("--processed-dir", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()

    processed_dir = Path(args.processed_dir)
    out_dir = Path(args.out_dir)
    split_dir = processed_dir / "splits"
    out_split_dir = out_dir / "splits"

    manifest_rows = []
    split_specs = [
        (
            "native_v2_main_text",
            "headline",
            "headline_main_text",
            "Clean native text target-present/target-absent split.",
        ),
        (
            "native_v2_main_text_balanced",
            "headline_balanced",
            "headline_main_text_balanced",
            "Balanced clean native text split.",
        ),
        (
            "native_v2_main_text_color",
            "headline",
            "headline_main_text_color",
            "Clean native text+color target-present/target-absent split.",
        ),
        (
            "native_v2_main_text_color_balanced",
            "headline_balanced",
            "headline_main_text_color_balanced",
            "Balanced clean native text+color split.",
        ),
        (
            "native_v2_clean_text_all",
            "headline",
            "headline_clean_text_all",
            "Clean text and text+color split with visible-text conflicts removed.",
        ),
        (
            "native_v2_clean_text_all_balanced",
            "headline_balanced",
            "headline_clean_text_all_balanced",
            "Balanced clean text/text+color split with visible-text conflicts removed.",
        ),
        (
            "native_v2_visible_conflicts",
            "diagnostic",
            "diagnostic_visible_conflicts",
            "Gold-absent rows with visible target text or instance ambiguity.",
        ),
        (
            "native_v2_color_instance",
            "diagnostic",
            "diagnostic_color_instance",
            "Text+color/instance matching stress split.",
        ),
        (
            "native_v2_color_instance_balanced",
            "diagnostic_balanced",
            "diagnostic_color_instance_balanced",
            "Balanced text+color/instance matching stress split.",
        ),
        (
            "native_v2_image_cue_unresolved",
            "excluded_or_diagnostic",
            "excluded_image_cue_unresolved_raw",
            "Raw native image-cue rows before cue-asset resolution.",
        ),
    ]

    for source_name, role, output_name, description in split_specs:
        add_split(
            manifest_rows,
            split_dir / f"{source_name}.json",
            split_dir / f"{source_name}.csv",
            out_split_dir / f"{output_name}.json",
            out_split_dir / f"{output_name}.csv",
            output_name,
            role,
            description,
        )

    resolution_dir = processed_dir / "image_cue_resolution"
    review_dir = resolution_dir / "review_merged"
    image_cue_eval = review_dir / "native_image_cue_eval_review_merged.json"
    image_cue_balanced = review_dir / "native_image_cue_balanced_eval_review_merged.json"
    add_split(
        manifest_rows,
        image_cue_eval,
        review_dir / "native_image_cue_eval_review_merged.csv",
        out_split_dir / "diagnostic_image_cue_resolved.json",
        out_split_dir / "diagnostic_image_cue_resolved.csv",
        "diagnostic_image_cue_resolved",
        "diagnostic",
        "Resolved native image-cue rows after strict asset matching and ambiguous review.",
    )
    add_split(
        manifest_rows,
        image_cue_balanced,
        review_dir / "native_image_cue_balanced_eval_review_merged.csv",
        out_split_dir / "diagnostic_image_cue_resolved_balanced.json",
        out_split_dir / "diagnostic_image_cue_resolved_balanced.csv",
        "diagnostic_image_cue_resolved_balanced",
        "diagnostic_balanced",
        "Balanced resolved native image-cue pilot split.",
    )

    resolution_rows = read_csv(resolution_dir / "native_image_cue_resolution.csv")
    missing_rows = [row for row in resolution_rows if row.get("resolution_status") == "missing"]
    ambiguous_rows = [row for row in resolution_rows if str(row.get("resolution_status", "")).startswith("ambiguous")]
    write_csv(out_dir / "image_cue_missing_or_unresolved.csv", [compact_image_cue_row(row) for row in missing_rows])
    write_csv(out_dir / "image_cue_ambiguous_excluded.csv", [compact_image_cue_row(row) for row in ambiguous_rows])

    review_csv = resolution_dir / "ambiguous_review" / "native_image_cue_ambiguous_review_filled.csv"
    reviewed = read_csv(review_csv)
    ambiguous_excluded = sum(1 for row in reviewed if row.get("review_decision") == "exclude")

    image_cue_summary = {
        "total": len(resolution_rows),
        "resolved": status_counts(load_json(image_cue_eval, default=[]))["rows"],
        "balanced": status_counts(load_json(image_cue_balanced, default=[]))["rows"],
        "missing": len(missing_rows),
        "ambiguous": len(ambiguous_rows),
        "ambiguous_excluded": ambiguous_excluded,
        "review_csv": str(review_csv) if review_csv.exists() else "",
    }

    manifest = {
        "processed_dir": str(processed_dir),
        "out_dir": str(out_dir),
        "splits": manifest_rows,
        "image_cue_resolution": image_cue_summary,
    }
    write_json(out_dir / "native_vsgui10k_cleaned_manifest.json", manifest)
    write_csv(out_dir / "native_vsgui10k_cleaned_manifest.csv", manifest_rows)
    write_summary(out_dir / "native_vsgui10k_cleaned_summary.md", manifest_rows, image_cue_summary)
    print(json.dumps({
        "splits": len(manifest_rows),
        "out_dir": str(out_dir),
        "summary_md": str(out_dir / "native_vsgui10k_cleaned_summary.md"),
    }, indent=2))


if __name__ == "__main__":
    main()
