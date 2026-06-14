#!/usr/bin/env python
import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path


VISIBLE_TEXT_BUCKETS = {"exact_text_visible", "substring_text_visible", "strong_ocr_match"}
COLOR_INSTANCE_BUCKETS = {"color_ignored_exact_text_visible", "color_ignored_substring_visible"}
CONFLICT_BUCKETS = VISIBLE_TEXT_BUCKETS | COLOR_INSTANCE_BUCKETS
CLEAN_BUCKETS = {"no_ocr_match", "weak_or_distractor_ocr_match", ""}


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


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


def audit_by_index(path):
    if not path or not Path(path).exists():
        return {}
    data = load_json(Path(path))
    return {int(row["index"]): row for row in data.get("rows", [])}


def task_family(example, audit_row):
    status = example.get("status", "")
    cue = example.get("cue_type", "unknown")
    bucket = audit_row.get("visibility_bucket", "")
    if status == "present":
        if cue == "text":
            return "present_text"
        if cue == "text+color":
            return "present_text_color"
        if cue == "image":
            return "present_image_unresolved"
        return "present_other"

    if cue == "text":
        if bucket in VISIBLE_TEXT_BUCKETS:
            return "visible_text_conflict"
        if bucket in COLOR_INSTANCE_BUCKETS:
            return "text_instance_conflict"
        if bucket in CLEAN_BUCKETS:
            return "clean_text_absent" if bucket else "text_absent_unverified"
        return "text_absent_uncertain"

    if cue == "text+color":
        if bucket in COLOR_INSTANCE_BUCKETS:
            return "text_color_instance_absent"
        if bucket in VISIBLE_TEXT_BUCKETS:
            return "visible_text_conflict"
        if bucket in CLEAN_BUCKETS:
            return "clean_text_color_absent" if bucket else "text_color_absent_unverified"
        return "text_color_absent_uncertain"

    if cue == "image":
        return "image_absent_unresolved"
    return "absent_other"


def eval_role(task):
    if task in {"clean_text_absent", "clean_text_color_absent", "present_text", "present_text_color"}:
        return "main_eval"
    if task in {"text_absent_unverified", "text_color_absent_unverified"}:
        return "candidate_needs_ocr_audit"
    if task in {"visible_text_conflict", "text_instance_conflict", "text_color_instance_absent"}:
        return "ambiguity_or_instance_eval"
    if task in {"present_image_unresolved", "image_absent_unresolved"}:
        return "image_cue_unresolved"
    return "audit_or_exclude"


def processed_example(example, index, audit_row):
    task = task_family(example, audit_row)
    out = dict(example)
    out["native_v2_index"] = index
    out["native_v2_task"] = task
    out["native_v2_eval_role"] = eval_role(task)
    out["native_v2_visibility_bucket"] = audit_row.get("visibility_bucket", "")
    out["native_v2_text_visibility_score"] = audit_row.get("best_text_visibility_score", "")
    out["native_v2_ocr_text"] = audit_row.get("ocr_text", "")
    out["native_v2_audit_available"] = int(bool(audit_row))
    return out


def split_specs():
    return {
        "native_v2_main_text": {
            "tasks": {"present_text", "clean_text_absent"},
            "description": "Clean native text target-present/target-absent split.",
        },
        "native_v2_main_text_color": {
            "tasks": {"present_text_color", "clean_text_color_absent"},
            "description": "Clean native text+color target-present/target-absent split.",
        },
        "native_v2_clean_text_all": {
            "tasks": {"present_text", "present_text_color", "clean_text_absent", "clean_text_color_absent"},
            "description": "Clean text and text+color target absence, excluding visible-text conflicts.",
        },
        "native_v2_visible_conflicts": {
            "tasks": {"visible_text_conflict", "text_instance_conflict"},
            "description": "Gold-absent rows with visible target text or instance ambiguity.",
        },
        "native_v2_color_instance": {
            "tasks": {"present_text_color", "text_color_instance_absent"},
            "description": "Text+color/instance matching stress test.",
        },
        "native_v2_image_cue_unresolved": {
            "tasks": {"present_image_unresolved", "image_absent_unresolved"},
            "description": "Native image-cue rows; cue-image assets/target definitions need resolution before headline evaluation.",
        },
        "native_v2_unverified_absent": {
            "tasks": {"text_absent_unverified", "text_color_absent_unverified"},
            "description": "Absent rows needing OCR audit before main evaluation.",
        },
    }


def compact_row(example):
    return {
        "native_v2_index": example.get("native_v2_index", ""),
        "img_usr_tgt": example.get("img_usr_tgt", ""),
        "image": example.get("image", ""),
        "status": example.get("status", ""),
        "target_present": example.get("target_present", ""),
        "cue_type": example.get("cue_type", ""),
        "target": example.get("target", ""),
        "query_text": example.get("query_text", ""),
        "target_color": example.get("target_color", ""),
        "category": example.get("category", ""),
        "native_v2_task": example.get("native_v2_task", ""),
        "native_v2_eval_role": example.get("native_v2_eval_role", ""),
        "visibility_bucket": example.get("native_v2_visibility_bucket", ""),
        "text_visibility_score": example.get("native_v2_text_visibility_score", ""),
        "ocr_text": example.get("native_v2_ocr_text", ""),
        "audit_available": example.get("native_v2_audit_available", ""),
        "fixation_count": example.get("fixation_count", ""),
    }


def summary_rows(examples):
    rows = []
    task_counts = Counter(ex["native_v2_task"] for ex in examples)
    role_counts = Counter(ex["native_v2_eval_role"] for ex in examples)
    status_task_counts = Counter((ex.get("status", ""), ex["native_v2_task"]) for ex in examples)
    cue_task_counts = Counter((ex.get("cue_type", ""), ex["native_v2_task"]) for ex in examples)
    for task, count in task_counts.most_common():
        rows.append({
            "kind": "task",
            "name": task,
            "count": count,
            "present": status_task_counts.get(("present", task), 0),
            "absent": status_task_counts.get(("absent", task), 0),
            "text": cue_task_counts.get(("text", task), 0),
            "text_color": cue_task_counts.get(("text+color", task), 0),
            "image": cue_task_counts.get(("image", task), 0),
        })
    for role, count in role_counts.most_common():
        rows.append({"kind": "eval_role", "name": role, "count": count})
    return rows


def split_rows(examples, specs):
    out = {}
    for name, spec in specs.items():
        rows = [ex for ex in examples if ex["native_v2_task"] in spec["tasks"]]
        out[name] = rows
    return out


def write_summary_md(path, examples, splits, specs, audit_json):
    task_counts = Counter(ex["native_v2_task"] for ex in examples)
    role_counts = Counter(ex["native_v2_eval_role"] for ex in examples)
    lines = [
        "# Processed Native VSGUI10K v2",
        "",
        f"- Examples: {len(examples)}",
        f"- OCR/visibility audit: `{audit_json or '(not provided)'}`",
        "",
        "## Evaluation Roles",
        "",
        "| Role | Count |",
        "|---|---:|",
    ]
    for role, count in role_counts.most_common():
        lines.append(f"| {role} | {count} |")
    lines.extend(["", "## Task Families", "", "| Task | Count |", "|---|---:|"])
    for task, count in task_counts.most_common():
        lines.append(f"| {task} | {count} |")
    lines.extend(["", "## Exported Splits", "", "| Split | Rows | Present | Absent | Description |", "|---|---:|---:|---:|---|"])
    for name, rows in splits.items():
        status = Counter(row.get("status", "") for row in rows)
        lines.append(
            f"| {name} | {len(rows)} | {status.get('present', 0)} | {status.get('absent', 0)} | "
            f"{specs[name]['description']} |"
        )
    lines.extend([
        "",
        "## Method Plan",
        "",
        "- Main text absent: compare prompt-only, combined AND, evidence-aware VLM, and CV bucket router.",
        "- Text+color clean absent: add color-aware verifier and context-crop VLM.",
        "- Visible conflict / instance subsets: report separately as target-definition ambiguity, not clean absence.",
        "- Image-cue subset: currently unresolved because released fixation rows reference cue-image names that are not available as direct image files; do not use it as a headline absent benchmark yet.",
        "- Unverified absent rows: run OCR/visibility audit before using them for headline metrics.",
        "",
    ])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Export processed/stratified Native VSGUI10K v2 task splits.")
    parser.add_argument("--trials-json", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--audit-json", default="")
    args = parser.parse_args()

    trials = load_json(Path(args.trials_json))
    audit_rows = audit_by_index(args.audit_json)
    examples = [processed_example(example, idx, audit_rows.get(idx, {})) for idx, example in enumerate(trials)]
    specs = split_specs()
    splits = split_rows(examples, specs)

    out_dir = Path(args.out_dir)
    write_json(out_dir / "native_vsgui10k_v2_processed.json", examples)
    write_csv(out_dir / "native_vsgui10k_v2_processed.csv", [compact_row(ex) for ex in examples])
    write_csv(out_dir / "native_vsgui10k_v2_summary.csv", summary_rows(examples))
    for name, rows in splits.items():
        write_json(out_dir / "splits" / f"{name}.json", rows)
        write_csv(out_dir / "splits" / f"{name}.csv", [compact_row(ex) for ex in rows])
    write_json(out_dir / "native_vsgui10k_v2_manifest.json", {
        "trials_json": args.trials_json,
        "audit_json": args.audit_json,
        "num_examples": len(examples),
        "splits": {
            name: {
                "rows": len(rows),
                "json": str(out_dir / "splits" / f"{name}.json"),
                "csv": str(out_dir / "splits" / f"{name}.csv"),
                "description": specs[name]["description"],
            }
            for name, rows in splits.items()
        },
    })
    write_summary_md(out_dir / "native_vsgui10k_v2_summary.md", examples, splits, specs, args.audit_json)
    print(json.dumps({
        "examples": len(examples),
        "splits": {name: len(rows) for name, rows in splits.items()},
        "summary_md": str(out_dir / "native_vsgui10k_v2_summary.md"),
    }, indent=2))


if __name__ == "__main__":
    main()
