#!/usr/bin/env python
import argparse
import json
from collections import Counter
from pathlib import Path


ABSENT_STATUSES = {"absent", "not_found", "not found", "no object", "no target", "not present"}
VISIBLE_TEXT_BUCKETS = {"exact_text_visible", "substring_text_visible", "strong_ocr_match"}
COLOR_INSTANCE_BUCKETS = {"color_ignored_exact_text_visible", "color_ignored_substring_visible"}
CONFLICT_BUCKETS = VISIBLE_TEXT_BUCKETS | COLOR_INSTANCE_BUCKETS


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def normalize_status(value, default="present"):
    text = str(value or default).casefold()
    return "absent" if text in ABSENT_STATUSES else "present"


def gold_status(example):
    if "target_present" in example:
        return "present" if example["target_present"] else "absent"
    return normalize_status(example.get("status"), default="present")


def predicted_status(example):
    status = normalize_status(example.get("predicted_status"), default="")
    if status in {"present", "absent"}:
        return status
    return "present" if example.get("prediction", []) else "absent"


def safe_div(num, den):
    return num / den if den else 0.0


def evaluate(examples, excluded=None):
    excluded = excluded or set()
    confusion = Counter()
    for idx, example in enumerate(examples):
        if idx in excluded:
            continue
        confusion[(gold_status(example), predicted_status(example))] += 1
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
        "confusion": {
            "present->present": tn,
            "present->absent": fp,
            "absent->present": fn,
            "absent->absent": tp,
        },
        "accuracy": safe_div(tp + tn, total),
        "absent_precision": precision,
        "absent_recall": recall,
        "absent_f1": f1,
    }


def audit_maps(path):
    data = load_json(Path(path))
    rows = {int(row["index"]): row for row in data.get("rows", [])}
    conflicts = {int(row["index"]) for row in data.get("conflict_rows", [])}
    return rows, conflicts


def select_method(bucket, profile):
    if profile == "clean_vs_color":
        if bucket in COLOR_INSTANCE_BUCKETS:
            return "color_instance"
        if bucket in VISIBLE_TEXT_BUCKETS:
            return "visible_text"
        return "clean"
    if profile == "conflict_present_guard":
        if bucket in CONFLICT_BUCKETS:
            return "guard_present"
        return "clean"
    if profile == "color_instance_focus":
        if bucket in COLOR_INSTANCE_BUCKETS:
            return "color_instance"
        if bucket in VISIBLE_TEXT_BUCKETS:
            return "guard_present"
        return "clean"
    raise ValueError(f"Unknown profile: {profile}")


def main():
    parser = argparse.ArgumentParser(description="Route native VSGUI status predictions by OCR-visible target bucket.")
    parser.add_argument("--base-predictions", required=True)
    parser.add_argument("--clean-predictions", required=True)
    parser.add_argument("--visible-text-predictions", required=True)
    parser.add_argument("--color-instance-predictions", required=True)
    parser.add_argument("--guard-present-predictions", default="")
    parser.add_argument("--audit-json", required=True)
    parser.add_argument("--profile", default="clean_vs_color", choices=["clean_vs_color", "conflict_present_guard", "color_instance_focus"])
    parser.add_argument("--output", required=True)
    parser.add_argument("--metrics-output", required=True)
    parser.add_argument("--selected-output", required=True)
    args = parser.parse_args()

    base = load_json(Path(args.base_predictions))
    methods = {
        "clean": load_json(Path(args.clean_predictions)),
        "visible_text": load_json(Path(args.visible_text_predictions)),
        "color_instance": load_json(Path(args.color_instance_predictions)),
        "guard_present": load_json(Path(args.guard_present_predictions)) if args.guard_present_predictions else base,
    }
    lengths = {len(base), *(len(value) for value in methods.values())}
    if len(lengths) != 1:
        raise ValueError(f"Prediction lengths differ: {sorted(lengths)}")
    audit_rows, conflict_indices = audit_maps(args.audit_json)

    output = []
    counts = Counter()
    changed = 0
    for idx, example in enumerate(base):
        bucket = audit_rows.get(idx, {}).get("visibility_bucket", "")
        method_key = select_method(bucket, args.profile)
        chosen = methods[method_key][idx]
        result = dict(example)
        old_status = predicted_status(result)
        new_status = "present" if method_key == "guard_present" else predicted_status(chosen)
        result["predicted_status"] = new_status
        result["native_task_router_profile"] = args.profile
        result["native_task_router_bucket"] = bucket
        result["native_task_router_method"] = method_key
        result["native_task_router_original_status"] = old_status
        changed += int(old_status != new_status)
        counts[method_key] += 1
        output.append(result)

    raw = evaluate(output)
    filtered = evaluate(output, conflict_indices)
    metrics = {
        **raw,
        "profile": args.profile,
        "changed_predictions": changed,
        "route_counts": dict(counts),
        "filtered_num_examples": filtered["num_examples"],
        "filtered_accuracy": filtered["accuracy"],
        "filtered_absent_precision": filtered["absent_precision"],
        "filtered_absent_recall": filtered["absent_recall"],
        "filtered_absent_f1": filtered["absent_f1"],
        "filtered_confusion": filtered["confusion"],
        "output": args.output,
    }
    write_json(Path(args.output), output)
    write_json(Path(args.metrics_output), metrics)
    write_json(Path(args.selected_output), {
        "profile": args.profile,
        "route_counts": dict(counts),
        "metrics_output": args.metrics_output,
    })
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
