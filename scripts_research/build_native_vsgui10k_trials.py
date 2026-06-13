#!/usr/bin/env python
import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path


def safe_float(value, default=0.0):
    try:
        if value in {"", None}:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def norm_bool(value):
    return str(value).strip().casefold() in {"true", "1", "yes", "y"}


def cue_label(value):
    value = str(value).strip().casefold()
    return {"t": "text", "tc": "text+color", "i": "image"}.get(value, value or "unknown")


def image_path(img_name):
    return f"vsgui10k-images/{img_name}"


def pixel(value, scale):
    value = safe_float(value)
    if 0 <= value <= 1:
        return value * scale
    if 1 < value <= 100:
        return value * scale / 100.0
    return value


def trial_key(row):
    return (
        row.get("pid", ""),
        row.get("media_id", ""),
        row.get("img_name", ""),
        row.get("new_img_name", ""),
        row.get("tgt_id", ""),
        row.get("absent", ""),
        row.get("cue", ""),
    )


def stable_id(row):
    raw = "_".join(str(part) for part in trial_key(row))
    raw = re.sub(r"[^A-Za-z0-9_.-]+", "-", raw).strip("-")
    return raw


def sort_fixations(rows):
    return sorted(
        rows,
        key=lambda row: (
            safe_float(row.get("FPOGS"), 0.0),
            safe_float(row.get("TIME"), 0.0),
            safe_float(row.get("FPOGID"), 0.0),
        ),
    )


def build_example(row, fixation_rows):
    width = safe_float(row.get("original_width"), 0.0)
    height = safe_float(row.get("original_height"), 0.0)
    absent = norm_bool(row.get("absent"))
    cue = cue_label(row.get("cue"))
    ordered = sort_fixations(fixation_rows)

    xs = [pixel(r.get("FPOGX_scaled"), width) for r in ordered if str(r.get("FPOGV", "1")) == "1"]
    ys = [pixel(r.get("FPOGY_scaled"), height) for r in ordered if str(r.get("FPOGV", "1")) == "1"]
    ts = [safe_float(r.get("FPOGD"), 0.0) for r in ordered if str(r.get("FPOGV", "1")) == "1"]

    target_text = str(row.get("tgt_text", "") or "").strip()
    target_color = str(row.get("tgt_color", "") or "").strip()
    query_text = target_text
    if cue == "text+color" and target_color:
        query_text = f"{target_color} {target_text}".strip()

    example = {
        "img_usr_tgt": stable_id(row),
        "image": image_path(row.get("img_name", "")),
        "width": width,
        "height": height,
        "username": row.get("pid", ""),
        "target_id": f"{row.get('cue', 'native')}_{row.get('tgt_id', '')}",
        "target_x": pixel(row.get("tgt_x"), width),
        "target_y": pixel(row.get("tgt_y"), height),
        "target_width": pixel(row.get("tgt_width"), width),
        "target_height": pixel(row.get("tgt_height"), height),
        "x": xs,
        "y": ys,
        "t": ts,
        "target": target_text,
        "query_text": query_text,
        "status": "absent" if absent else "present",
        "target_present": not absent,
        "cue_type": cue,
        "target_color": target_color,
        "category": row.get("category", ""),
        "native_absent": row.get("absent", ""),
        "native_cue": row.get("cue", ""),
        "native_img_name": row.get("img_name", ""),
        "native_new_img_name": row.get("new_img_name", ""),
        "native_media_id": row.get("media_id", ""),
        "native_balanced_block_id": row.get("balanced_block_id", ""),
        "fixation_count": len(xs),
    }
    return example


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


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
        "# Native VSGUI10K Trial Summary",
        "",
        f"- Visual-search trials: {summary['num_trials']}",
        f"- Present trials: {summary['status_counts'].get('present', 0)}",
        f"- Absent trials: {summary['status_counts'].get('absent', 0)}",
        f"- Text cue trials: {summary['cue_counts'].get('text', 0)}",
        f"- Text+color cue trials: {summary['cue_counts'].get('text+color', 0)}",
        f"- Image cue trials: {summary['cue_counts'].get('image', 0)}",
        "",
        "## Status x Cue",
        "",
        "| Status | Cue | Trials |",
        "|---|---|---:|",
    ]
    for key, count in summary["status_cue_counts"].items():
        status, cue = key.split("::", 1)
        lines.append(f"| {status} | {cue} | {count} |")
    lines.extend(["", "## Category x Status x Cue", "", "| Category | Status | Cue | Trials |", "|---|---|---|---:|"])
    for key, count in summary["category_status_cue_counts"].items():
        category, status, cue = key.split("::", 2)
        lines.append(f"| {category} | {status} | {cue} | {count} |")
    lines.extend([
        "",
        "## Suggested Uses",
        "",
        "- Use `native_vsgui10k_trials.json` as a native present/absent evaluation source.",
        "- Use `cue_type=image` rows for the non-text/image-cue direction.",
        "- Use `cue_type=text+color` rows for multimodal text+attribute grounding.",
        "- Treat absent image/text+color rows as especially valuable because they combine target absence with non-text cue complexity.",
        "",
    ])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Build native VSGUI10K visual-search trials from OSF fixation CSV.")
    parser.add_argument("--fixations-csv", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--visual-img-type", default="2")
    parser.add_argument("--min-fixations", type=int, default=1)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    groups = defaultdict(list)
    first_rows = {}
    with open(args.fixations_csv, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if str(row.get("img_type", "")) != str(args.visual_img_type):
                continue
            key = trial_key(row)
            groups[key].append(row)
            first_rows.setdefault(key, row)

    examples = []
    for key, rows in groups.items():
        example = build_example(first_rows[key], rows)
        if example["fixation_count"] < args.min_fixations:
            continue
        examples.append(example)
    examples.sort(key=lambda row: row["img_usr_tgt"])
    if args.limit > 0:
        examples = examples[:args.limit]

    status_counts = Counter(example["status"] for example in examples)
    cue_counts = Counter(example["cue_type"] for example in examples)
    status_cue = Counter(f"{example['status']}::{example['cue_type']}" for example in examples)
    category_status_cue = Counter(
        f"{example['category']}::{example['status']}::{example['cue_type']}" for example in examples
    )
    summary_rows = [
        {
            "img_usr_tgt": ex["img_usr_tgt"],
            "image": ex["image"],
            "status": ex["status"],
            "target_present": ex["target_present"],
            "cue_type": ex["cue_type"],
            "query_text": ex["query_text"],
            "target": ex["target"],
            "target_color": ex["target_color"],
            "category": ex["category"],
            "fixation_count": ex["fixation_count"],
        }
        for ex in examples
    ]
    summary = {
        "num_trials": len(examples),
        "status_counts": dict(status_counts.most_common()),
        "cue_counts": dict(cue_counts.most_common()),
        "status_cue_counts": dict(status_cue.most_common()),
        "category_status_cue_counts": dict(category_status_cue.most_common()),
    }

    out_dir = Path(args.out_dir)
    write_json(out_dir / "native_vsgui10k_trials.json", examples)
    write_csv(out_dir / "native_vsgui10k_trials.csv", summary_rows)
    write_json(out_dir / "native_vsgui10k_trial_summary.json", summary)
    write_summary(out_dir / "native_vsgui10k_trial_summary.md", summary)
    print(json.dumps({
        "num_trials": len(examples),
        "out_dir": str(out_dir),
        "summary_md": str(out_dir / "native_vsgui10k_trial_summary.md"),
    }, indent=2))


if __name__ == "__main__":
    main()
