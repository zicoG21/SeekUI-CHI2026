#!/usr/bin/env python
import argparse
import csv
import json
from collections import Counter
from pathlib import Path


ABSENT_STATUSES = {"absent", "not_found", "not found", "no object", "no target", "not present"}
VISIBLE_TEXT_BUCKETS = {
    "exact_text_visible",
    "substring_text_visible",
    "strong_ocr_match",
}
COLOR_INSTANCE_BUCKETS = {
    "color_ignored_exact_text_visible",
    "color_ignored_substring_visible",
}
CONFLICT_BUCKETS = VISIBLE_TEXT_BUCKETS | COLOR_INSTANCE_BUCKETS


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


def safe_div(num, den):
    return num / den if den else 0.0


def evaluate(rows):
    confusion = Counter()
    for row in rows:
        confusion[(row["gold"], row["pred"])] += 1
    tp = confusion[("absent", "absent")]
    fp = confusion[("present", "absent")]
    fn = confusion[("absent", "present")]
    tn = confusion[("present", "present")]
    total = tp + fp + fn + tn
    precision = safe_div(tp, tp + fp)
    recall = safe_div(tp, tp + fn)
    f1 = safe_div(2 * precision * recall, precision + recall)
    return {
        "num_examples": total,
        "accuracy": safe_div(tp + tn, total),
        "absent_precision": precision,
        "absent_recall": recall,
        "absent_f1": f1,
        "present_absent": fp,
        "absent_present": fn,
        "present_present": tn,
        "absent_absent": tp,
    }


def audit_by_index(path):
    data = load_json(path)
    return {int(row["index"]): row for row in data.get("rows", [])}


def retasked_gold(original_gold, bucket, view):
    if view == "native_original":
        return original_gold, True
    if original_gold == "present":
        return "present", True
    if view == "clean_absent_only":
        return ("absent", True) if bucket not in CONFLICT_BUCKETS else ("absent", False)
    if view == "visible_text_as_present":
        return ("present", True) if bucket in VISIBLE_TEXT_BUCKETS else ("absent", True)
    if view == "color_instance_as_present":
        return ("present", True) if bucket in COLOR_INSTANCE_BUCKETS else ("absent", True)
    if view == "all_visible_conflicts_as_present":
        return ("present", True) if bucket in CONFLICT_BUCKETS else ("absent", True)
    if view == "color_instance_only":
        return ("absent", True) if bucket in COLOR_INSTANCE_BUCKETS else ("absent", False)
    raise ValueError(f"Unknown view: {view}")


def candidate_prediction_files(outputs, model, split):
    rows = [
        ("prompt", split, outputs / f"present_absent_predictions_{model}_{split}.json"),
        ("combined", f"{split}_combined_and_present_only_native_tuned_absent_f1", outputs / f"present_absent_predictions_{model}_{split}_combined_and_present_only_native_tuned_absent_f1.json"),
        ("combined", f"{split}_combined_and_present_only_best_f1", outputs / f"present_absent_predictions_{model}_{split}_combined_and_present_only_best_f1.json"),
        ("color_aware", f"{split}_color_aware_filtered_tuned_absent_f1", outputs / f"present_absent_predictions_{model}_{split}_color_aware_filtered_tuned_absent_f1.json"),
        ("color_aware", f"{split}_color_aware_native_tuned_absent_f1", outputs / f"present_absent_predictions_{model}_{split}_color_aware_native_tuned_absent_f1.json"),
        ("crop_vlm", f"{split}_crop_ocr_vlm", outputs / f"present_absent_predictions_{model}_{split}_crop_ocr_vlm.json"),
        ("context_crop_vlm", f"{split}_context_crop_ocr_vlm", outputs / f"present_absent_predictions_{model}_{split}_context_crop_ocr_vlm.json"),
        ("ensemble", f"{split}_status_ensemble_filtered_absent_f1", outputs / f"present_absent_predictions_{model}_{split}_status_ensemble_filtered_absent_f1.json"),
    ]
    for path in sorted(outputs.glob(f"vlm_presence_predictions_{model}_vlm_presence_{split}_*.json")):
        if path.name.endswith("_status_eval.json"):
            continue
        rows.append(("vlm_presence", path.name.removeprefix(f"vlm_presence_predictions_{model}_").removesuffix(".json"), path))
    for path in sorted(outputs.glob(f"vlm_evidence_predictions_{model}_vlm_evidence_{split}_*.json")):
        if path.name.endswith("_status_eval.json"):
            continue
        rows.append(("vlm_evidence", path.name.removeprefix(f"vlm_evidence_predictions_{model}_").removesuffix(".json"), path))
    for path in sorted(outputs.glob(f"present_absent_predictions_{model}_{split}_native_supervised_calibrated_*.json")):
        if path.name.endswith(("_status_eval.json", "_selected_threshold.json")):
            continue
        rows.append(("supervised_calibrated", path.name.removeprefix(f"present_absent_predictions_{model}_").removesuffix(".json"), path))
    for path in sorted(outputs.glob(f"present_absent_predictions_{model}_{split}_native_task_routed_*.json")):
        if path.name.endswith(("_status_eval.json", "_selected_profile.json")):
            continue
        rows.append(("task_routed", path.name.removeprefix(f"present_absent_predictions_{model}_").removesuffix(".json"), path))
    for path in sorted(outputs.glob(f"present_absent_predictions_{model}_{split}_native_bucket_router_*.json")):
        if path.name.endswith(("_status_eval.json", "_mapping.json")):
            continue
        rows.append(("bucket_router", path.name.removeprefix(f"present_absent_predictions_{model}_").removesuffix(".json"), path))
    for path in sorted(outputs.glob(f"present_absent_predictions_{model}_{split}_native_cv_bucket_router_*.json")):
        if path.name.endswith("_status_eval.json"):
            continue
        rows.append(("cv_bucket_router", path.name.removeprefix(f"present_absent_predictions_{model}_").removesuffix(".json"), path))
    return rows


def rows_for_prediction(data, audit_rows, view):
    rows = []
    excluded = 0
    bucket_counts = Counter()
    for idx, example in enumerate(data):
        original_gold = gold_status(example)
        bucket = audit_rows.get(idx, {}).get("visibility_bucket", "")
        if original_gold == "absent":
            bucket_counts[bucket or "missing"] += 1
        gold, keep = retasked_gold(original_gold, bucket, view)
        if not keep:
            excluded += 1
            continue
        rows.append({
            "index": idx,
            "gold": gold,
            "pred": predicted_status(example),
            "original_gold": original_gold,
            "visibility_bucket": bucket,
        })
    return rows, excluded, bucket_counts


def fmt(value):
    try:
        return f"{float(value):.4f}"
    except (TypeError, ValueError):
        return ""


def write_md(path, rows):
    lines = [
        "# Native Retasked Status Evaluation",
        "",
        "| View | Family | Variant | N | Excluded | Acc | Prec. | Rec. | F1 | P->A | A->P |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['view']} | {row['family']} | {row['variant']} | {row['num_examples']} | "
            f"{row['excluded_examples']} | {fmt(row['accuracy'])} | {fmt(row['absent_precision'])} | "
            f"{fmt(row['absent_recall'])} | {fmt(row['absent_f1'])} | {row['present_absent']} | {row['absent_present']} |"
        )
    lines.extend([
        "",
        "## View Definitions",
        "",
        "- `native_original`: original native gold labels.",
        "- `clean_absent_only`: excludes gold-absent rows where OCR suggests visible target text/color-instance conflict.",
        "- `visible_text_as_present`: treats exact/substring/strong text-visible gold-absent rows as present.",
        "- `color_instance_as_present`: treats color-ignored text-visible gold-absent rows as present.",
        "- `all_visible_conflicts_as_present`: treats all strong visible-text conflicts as present.",
        "- `color_instance_only`: evaluates only color/instance-sensitive absent rows plus present rows.",
        "",
    ])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Evaluate native VSGUI under cleaned/redefined label views.")
    parser.add_argument("--work-dir", required=True)
    parser.add_argument("--split-name", default="native_text_color_balanced")
    parser.add_argument("--model-name", default="SeekUI")
    parser.add_argument("--audit-json", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--output-md", required=True)
    args = parser.parse_args()

    outputs = Path(args.work_dir) / "outputs"
    audit_rows = audit_by_index(Path(args.audit_json))
    views = [
        "native_original",
        "clean_absent_only",
        "visible_text_as_present",
        "color_instance_as_present",
        "all_visible_conflicts_as_present",
        "color_instance_only",
    ]
    result_rows = []
    missing = []
    for family, variant, path in candidate_prediction_files(outputs, args.model_name, args.split_name):
        if not path.exists():
            missing.append(str(path))
            continue
        data = load_json(path)
        for view in views:
            eval_rows, excluded, bucket_counts = rows_for_prediction(data, audit_rows, view)
            metrics = evaluate(eval_rows)
            result_rows.append({
                "view": view,
                "family": family,
                "variant": variant,
                "source": str(path),
                "excluded_examples": excluded,
                "absent_bucket_counts": dict(bucket_counts),
                **metrics,
            })
    result_rows.sort(key=lambda row: (row["view"], -row["absent_f1"], -row["accuracy"], row["variant"]))
    write_json(Path(args.output_json), {"rows": result_rows, "missing_prediction_files": missing})
    write_csv(Path(args.output_csv), result_rows)
    write_md(Path(args.output_md), result_rows)
    print(json.dumps({"rows": len(result_rows), "missing": len(missing), "output_md": args.output_md}, indent=2))


if __name__ == "__main__":
    main()
