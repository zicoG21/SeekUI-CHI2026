#!/usr/bin/env python
import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path


ABSENT_VALUES = {"absent", "not_present", "not present", "not_found", "not found", "no object", "no objects", "missing"}
PRESENT_VALUES = {"present", "found", "visible", "yes", "true", "1"}
FALSE_VALUES = {"false", "0", "no", "n", "none", "null"}
TRUE_VALUES = {"true", "1", "yes", "y"}
COLOR_WORDS = {
    "red", "blue", "green", "yellow", "black", "white", "gray", "grey", "orange", "purple",
    "pink", "brown", "cyan", "magenta", "teal", "violet", "gold", "silver",
}
STATUS_FIELD_HINTS = ("status", "present", "visible", "found", "exist", "exists", "is_absent", "target_present")
COLOR_FIELD_HINTS = ("color", "colour", "rgb", "rgba", "hex")
IMAGE_TARGET_FIELD_HINTS = ("target_image", "target_img", "target_crop", "query_image", "cue_image", "template_image")


def load_records(path):
    suffix = path.suffix.casefold()
    if suffix == ".jsonl":
        with open(path, "r", encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]
    if suffix == ".csv":
        with open(path, "r", encoding="utf-8", newline="") as f:
            return list(csv.DictReader(f))
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ["data", "examples", "annotations", "records", "items", "rows"]:
            value = data.get(key)
            if isinstance(value, list):
                return value
        return [data]
    return []


def flatten_fields(record, prefix=""):
    rows = {}
    if isinstance(record, dict):
        for key, value in record.items():
            name = f"{prefix}.{key}" if prefix else str(key)
            if isinstance(value, dict):
                rows.update(flatten_fields(value, name))
            elif isinstance(value, list):
                rows[name] = value
            else:
                rows[name] = value
    return rows


def text_value(value):
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return "" if value is None else str(value)


def first_field(fields, names):
    for name in names:
        if name in fields and text_value(fields[name]).strip():
            return text_value(fields[name]).strip()
    return ""


def find_by_suffix(fields, suffixes):
    suffixes = tuple(s.casefold() for s in suffixes)
    for key, value in fields.items():
        low = key.casefold()
        if any(low.endswith(suffix) or low == suffix for suffix in suffixes):
            value = text_value(value).strip()
            if value:
                return value
    return ""


def target_prefix(target_id):
    target_id = str(target_id or "")
    if not target_id:
        return "missing"
    return target_id.split("_", 1)[0] if "_" in target_id else "no_prefix"


def status_guess(fields):
    candidates = []
    for key, value in fields.items():
        low_key = key.casefold()
        if any(hint in low_key for hint in STATUS_FIELD_HINTS):
            candidates.append((low_key, text_value(value).strip().casefold()))

    for key, value in candidates:
        if "absent" in key:
            if value in TRUE_VALUES:
                return "absent", key, value
            if value in FALSE_VALUES:
                return "present", key, value
        if "target_present" in key or low_key_is_present_key(key):
            if value in TRUE_VALUES or value in PRESENT_VALUES:
                return "present", key, value
            if value in FALSE_VALUES or value in ABSENT_VALUES:
                return "absent", key, value
        if value in ABSENT_VALUES:
            return "absent", key, value
        if value in PRESENT_VALUES:
            return "present", key, value
    return "unknown", "", ""


def low_key_is_present_key(key):
    return key.endswith("present") or key.endswith("visible") or key.endswith("found") or key.endswith("exists")


def color_fields(fields):
    matches = []
    for key, value in fields.items():
        low_key = key.casefold()
        raw = text_value(value).strip()
        if not raw:
            continue
        low_value = raw.casefold()
        if any(hint in low_key for hint in COLOR_FIELD_HINTS):
            matches.append(f"{key}={raw}")
        elif re.search(r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})\\b", raw):
            matches.append(f"{key}={raw}")
        elif any(re.search(rf"\\b{re.escape(color)}\\b", low_value) for color in COLOR_WORDS):
            if "target" in low_key or "query" in low_key or "cue" in low_key:
                matches.append(f"{key}={raw}")
    return matches


def has_image_target_field(fields):
    for key, value in fields.items():
        low_key = key.casefold()
        raw = text_value(value).strip()
        if not raw:
            continue
        if any(hint in low_key for hint in IMAGE_TARGET_FIELD_HINTS):
            return key, raw
        if ("target" in low_key or "query" in low_key or "cue" in low_key) and re.search(r"\\.(png|jpg|jpeg|webp)$", raw, re.I):
            return key, raw
    return "", ""


def modality_guess(fields, target_id, target_text):
    prefix = target_prefix(target_id).casefold()
    image_field, image_value = has_image_target_field(fields)
    colors = color_fields(fields)
    target_text_low = target_text.casefold()
    has_color_word = any(re.search(rf"\\b{re.escape(color)}\\b", target_text_low) for color in COLOR_WORDS)

    if prefix in {"img", "image", "icon", "ico", "visual"} or image_field:
        if colors:
            return "image+color", image_field, "; ".join(colors)
        return "image", image_field, image_value
    if prefix in {"txt", "text"}:
        if colors or has_color_word:
            return "text+color", "", "; ".join(colors) if colors else "color_word_in_target"
        return "text", "", ""
    if colors or has_color_word:
        return "unknown+color", "", "; ".join(colors) if colors else "color_word_in_target"
    if prefix in {"btn", "button", "component", "ui", "elt", "element"}:
        return "ui_component", "", ""
    return "unknown", "", ""


def discover_inputs(root):
    paths = []
    for pattern in ("*.json", "*.jsonl", "*.csv"):
        for path in sorted(root.rglob(pattern)):
            parts = set(path.parts)
            if "outputs" in parts or "paper_assets" in parts or "paper_draft" in parts or "__pycache__" in parts:
                continue
            paths.append(path)
    return paths


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames or ["empty"])
        writer.writeheader()
        writer.writerows(rows)


def write_summary(path, summary):
    lines = [
        "# Native VSGUI Target Audit",
        "",
        f"- Input files: {summary['input_files']}",
        f"- Records scanned: {summary['records_scanned']}",
        f"- Candidate absent rows: {summary['status_counts'].get('absent', 0)}",
        f"- Candidate image target rows: {summary['modality_counts'].get('image', 0) + summary['modality_counts'].get('image+color', 0)}",
        f"- Candidate text+color rows: {summary['modality_counts'].get('text+color', 0)}",
        "",
        "## Status Counts",
        "",
        "| Status | Count |",
        "|---|---:|",
    ]
    for key, count in summary["status_counts"].items():
        lines.append(f"| {key} | {count} |")
    lines.extend(["", "## Modality Counts", "", "| Modality | Count |", "|---|---:|"])
    for key, count in summary["modality_counts"].items():
        lines.append(f"| {key} | {count} |")
    lines.extend(["", "## Target Prefix Counts", "", "| Prefix | Count |", "|---|---:|"])
    for key, count in summary["target_prefix_counts"].items():
        lines.append(f"| {key} | {count} |")
    lines.extend([
        "",
        "## Interpretation",
        "",
        "- This audit is schema-flexible: counts are candidates inferred from field names and values.",
        "- Rows marked `unknown` may still contain useful target modality information if the raw schema uses unexpected names.",
        "- Confirm candidate absent/image/color rows manually before treating them as an official native validation split.",
        "",
    ])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Audit native VSGUI files for absent, image-target, and text+color target rows.")
    parser.add_argument("--input", action="append", default=[], help="Input JSON/JSONL/CSV. Can repeat.")
    parser.add_argument("--search-root", default="", help="If no --input is given, recursively scan this root.")
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--max-records-per-file", type=int, default=0)
    args = parser.parse_args()

    inputs = [Path(path) for path in args.input]
    if not inputs:
        if not args.search_root:
            raise SystemExit("Provide --input or --search-root")
        inputs = discover_inputs(Path(args.search_root))

    rows = []
    field_counts = Counter()
    status_counts = Counter()
    modality_counts = Counter()
    prefix_counts = Counter()
    failed = []

    for input_path in inputs:
        try:
            records = load_records(input_path)
        except Exception as exc:
            failed.append({"path": str(input_path), "error": str(exc)})
            continue
        if args.max_records_per_file > 0:
            records = records[:args.max_records_per_file]
        for idx, record in enumerate(records):
            if not isinstance(record, dict):
                continue
            fields = flatten_fields(record)
            field_counts.update(fields.keys())
            target_id = first_field(fields, ["target_id", "target.id"]) or find_by_suffix(fields, ["target_id", "id"])
            target_text = (
                first_field(fields, ["target", "target_text", "query_text", "cue_text", "text"])
                or find_by_suffix(fields, ["target", "target_text", "query_text", "cue_text"])
            )
            image = first_field(fields, ["image", "image_path", "screenshot", "screenshot_path"]) or find_by_suffix(fields, ["image", "image_path"])
            status, status_field, status_raw = status_guess(fields)
            modality, modality_field, modality_evidence = modality_guess(fields, target_id, target_text)
            prefix = target_prefix(target_id)

            status_counts[status] += 1
            modality_counts[modality] += 1
            prefix_counts[prefix] += 1
            rows.append({
                "source_file": str(input_path),
                "row_index": idx,
                "image": image,
                "target_id": target_id,
                "target_prefix": prefix,
                "target_text": target_text,
                "status_guess": status,
                "status_field": status_field,
                "status_raw": status_raw,
                "modality_guess": modality,
                "modality_field": modality_field,
                "modality_evidence": modality_evidence,
                "has_color_evidence": int(bool(color_fields(fields))),
                "field_count": len(fields),
            })

    out_dir = Path(args.out_dir)
    rows_path = out_dir / "native_vsgui_target_audit_rows.csv"
    write_csv(rows_path, rows)

    interesting = [
        row for row in rows
        if row["status_guess"] == "absent"
        or row["modality_guess"] in {"image", "image+color", "text+color", "unknown+color"}
    ]
    write_csv(out_dir / "native_vsgui_target_audit_candidates.csv", interesting)
    write_csv(
        out_dir / "native_vsgui_field_counts.csv",
        [{"field": key, "count": count} for key, count in field_counts.most_common()],
    )
    summary = {
        "input_files": len(inputs),
        "records_scanned": len(rows),
        "failed_files": failed,
        "status_counts": dict(status_counts.most_common()),
        "modality_counts": dict(modality_counts.most_common()),
        "target_prefix_counts": dict(prefix_counts.most_common()),
        "rows_csv": str(rows_path),
        "candidates_csv": str(out_dir / "native_vsgui_target_audit_candidates.csv"),
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "native_vsgui_target_audit_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    write_summary(out_dir / "native_vsgui_target_audit_summary.md", summary)
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
