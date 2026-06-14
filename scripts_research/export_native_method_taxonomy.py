#!/usr/bin/env python
import argparse
import csv
import json
from collections import Counter
from pathlib import Path


ABSENT_STATUSES = {"absent", "not_found", "not found", "no object", "no target", "not present"}
CASE_TYPES = [
    "prompt_forced_choice_fixed_by_primary",
    "primary_overreject_present",
    "primary_correct_secondary_wrong_absent",
    "primary_correct_secondary_wrong_present",
    "secondary_correct_primary_wrong_absent",
    "secondary_correct_primary_wrong_present",
    "both_wrong_absent",
    "both_wrong_present",
    "native_label_conflict_absent",
    "color_or_instance_sensitive_absent",
]


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys()) if rows else ["empty"]
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def normalize_status(value, default="present"):
    text = str(value or default).casefold()
    return "absent" if text in ABSENT_STATUSES else "present"


def gold_status(example):
    if "target_present" in example:
        return "present" if example["target_present"] else "absent"
    return normalize_status(example.get("status"), default="present")


def predicted_status(example):
    status = str(example.get("predicted_status", "") or "").casefold()
    if status in ABSENT_STATUSES:
        return "absent"
    if status == "present":
        return "present"
    return "present" if example.get("prediction", []) else "absent"


def is_correct(gold, pred):
    return gold == pred


def key_for(example, idx):
    return str(example.get("img_usr_tgt") or example.get("key") or example.get("id") or idx)


def target_for(example):
    return str(example.get("query_text") or example.get("target") or example.get("original_target") or "")


def load_audit_rows(path):
    if not path:
        return {}
    data = load_json(Path(path))
    rows = data.get("rows", [])
    return {int(row["index"]): row for row in rows if "index" in row}


def conflict_bucket(audit_row):
    return (audit_row or {}).get("visibility_bucket", "")


def is_strong_conflict(bucket):
    return bucket in {
        "exact_text_visible",
        "color_ignored_exact_text_visible",
        "substring_text_visible",
        "color_ignored_substring_visible",
        "strong_ocr_match",
    }


def is_color_or_instance_bucket(bucket):
    return bucket in {
        "color_ignored_exact_text_visible",
        "color_ignored_substring_visible",
    }


def row_for(idx, prompt, primary, secondary, audit_row, case_type, primary_label, secondary_label):
    gold = gold_status(prompt)
    prompt_pred = predicted_status(prompt)
    primary_pred = predicted_status(primary)
    secondary_pred = predicted_status(secondary) if secondary else ""
    bucket = conflict_bucket(audit_row)
    return {
        "index": idx,
        "case_type": case_type,
        "key": key_for(prompt, idx),
        "image": prompt.get("image", ""),
        "target": target_for(prompt),
        "cue": prompt.get("cue", ""),
        "gold_status": gold,
        "prompt_status": prompt_pred,
        f"{primary_label}_status": primary_pred,
        f"{secondary_label}_status": secondary_pred,
        "prompt_correct": int(is_correct(gold, prompt_pred)),
        f"{primary_label}_correct": int(is_correct(gold, primary_pred)),
        f"{secondary_label}_correct": int(is_correct(gold, secondary_pred)) if secondary else "",
        "visibility_bucket": bucket,
        "strong_visible_text_conflict": int(is_strong_conflict(bucket)),
        "color_or_instance_sensitive": int(is_color_or_instance_bucket(bucket)),
        "path_best_evidence": primary.get("path_best_evidence", ""),
        "color_aware_score": primary.get("color_aware_score", ""),
        "color_aware_text_score": primary.get("color_aware_text_score", ""),
        "color_aware_color_score": primary.get("color_aware_color_score", ""),
        "color_aware_ocr_text": primary.get("color_aware_ocr_text", ""),
        "candidate_crop_count": secondary.get("candidate_crop_count", "") if secondary else "",
        "candidate_crop_present_count": secondary.get("candidate_crop_present_count", "") if secondary else "",
    }


def classify(prompt, primary, secondary, audit_row):
    gold = gold_status(prompt)
    prompt_pred = predicted_status(prompt)
    primary_pred = predicted_status(primary)
    secondary_pred = predicted_status(secondary) if secondary else ""
    primary_ok = is_correct(gold, primary_pred)
    secondary_ok = is_correct(gold, secondary_pred) if secondary else False
    bucket = conflict_bucket(audit_row)

    labels = []
    if gold == "absent" and prompt_pred == "present" and primary_pred == "absent":
        labels.append("prompt_forced_choice_fixed_by_primary")
    if gold == "present" and prompt_pred == "present" and primary_pred == "absent":
        labels.append("primary_overreject_present")
    if secondary:
        if primary_ok and not secondary_ok and gold == "absent":
            labels.append("primary_correct_secondary_wrong_absent")
        if primary_ok and not secondary_ok and gold == "present":
            labels.append("primary_correct_secondary_wrong_present")
        if secondary_ok and not primary_ok and gold == "absent":
            labels.append("secondary_correct_primary_wrong_absent")
        if secondary_ok and not primary_ok and gold == "present":
            labels.append("secondary_correct_primary_wrong_present")
        if not primary_ok and not secondary_ok and gold == "absent":
            labels.append("both_wrong_absent")
        if not primary_ok and not secondary_ok and gold == "present":
            labels.append("both_wrong_present")
    if gold == "absent" and is_strong_conflict(bucket):
        labels.append("native_label_conflict_absent")
    if gold == "absent" and is_color_or_instance_bucket(bucket):
        labels.append("color_or_instance_sensitive_absent")
    return labels


def sample_rows(rows, limit):
    if limit <= 0:
        return rows
    return rows[:limit]


def write_md(path, manifest, rows, primary_label, secondary_label, audit_json):
    counts = Counter(row["case_type"] for row in rows)
    bucket_counts = Counter(row["visibility_bucket"] for row in rows if row.get("visibility_bucket"))
    lines = [
        "# Native Method Taxonomy",
        "",
        f"- Primary method: `{primary_label}`",
        f"- Secondary method: `{secondary_label}`",
        f"- Label-conflict audit: `{audit_json}`" if audit_json else "- Label-conflict audit: not provided",
        "",
        "## Case Counts",
        "",
        "| Case Type | Count | Selected |",
        "|---|---:|---:|",
    ]
    for item in manifest:
        lines.append(f"| {item['case_type']} | {item['count']} | {item['selected']} |")
    lines.extend([
        "",
        "## Visibility Buckets Among Exported Rows",
        "",
        "| Bucket | Count |",
        "|---|---:|",
    ])
    for bucket, count in bucket_counts.most_common():
        lines.append(f"| {bucket} | {count} |")
    lines.extend([
        "",
        "## Method Reading",
        "",
        "- `prompt_forced_choice_fixed_by_primary` captures native absent rows where the base model forced a present grounding and the primary verifier stopped.",
        "- `primary_overreject_present` captures the main conservative cost of the primary verifier.",
        "- `primary_correct_secondary_wrong_*` and `secondary_correct_primary_wrong_*` separate color-aware/path evidence from context-crop VLM behavior.",
        "- `native_label_conflict_absent` and `color_or_instance_sensitive_absent` mark rows where native labels may involve visible text, color mismatch, or instance-level ambiguity rather than clean absence.",
        "",
    ])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Export native VSGUI method taxonomy and disagreement cases.")
    parser.add_argument("--prompt-predictions", required=True)
    parser.add_argument("--primary-predictions", required=True)
    parser.add_argument("--secondary-predictions", default="")
    parser.add_argument("--audit-json", default="")
    parser.add_argument("--primary-label", default="primary")
    parser.add_argument("--secondary-label", default="secondary")
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--limit", type=int, default=40)
    args = parser.parse_args()

    prompt_data = load_json(Path(args.prompt_predictions))
    primary_data = load_json(Path(args.primary_predictions))
    secondary_data = load_json(Path(args.secondary_predictions)) if args.secondary_predictions else [None] * len(prompt_data)
    if len(prompt_data) != len(primary_data):
        raise ValueError("Prompt and primary prediction files must have the same length.")
    if len(prompt_data) != len(secondary_data):
        raise ValueError("Prompt and secondary prediction files must have the same length.")
    audit_rows = load_audit_rows(args.audit_json)

    grouped = {case_type: [] for case_type in CASE_TYPES}
    all_rows = []
    for idx, (prompt, primary, secondary) in enumerate(zip(prompt_data, primary_data, secondary_data)):
        audit_row = audit_rows.get(idx, {})
        for case_type in classify(prompt, primary, secondary, audit_row):
            row = row_for(idx, prompt, primary, secondary, audit_row, case_type, args.primary_label, args.secondary_label)
            grouped[case_type].append(row)
            all_rows.append(row)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = []
    sampled_index = []
    for case_type in CASE_TYPES:
        rows = grouped[case_type]
        selected = sample_rows(rows, args.limit)
        write_csv(out_dir / f"{case_type}.csv", selected)
        sampled_index.extend(selected)
        manifest.append({
            "case_type": case_type,
            "count": len(rows),
            "selected": len(selected),
            "csv": str(out_dir / f"{case_type}.csv"),
        })
    write_csv(out_dir / "native_method_taxonomy_index.csv", sampled_index)
    write_json(out_dir / "native_method_taxonomy_manifest.json", {
        "primary_label": args.primary_label,
        "secondary_label": args.secondary_label,
        "audit_json": args.audit_json,
        "manifest": manifest,
    })
    write_md(out_dir / "native_method_taxonomy.md", manifest, sampled_index, args.primary_label, args.secondary_label, args.audit_json)
    print(json.dumps({"out_dir": str(out_dir), "case_types": len(manifest), "rows": len(all_rows)}, indent=2))


if __name__ == "__main__":
    main()
