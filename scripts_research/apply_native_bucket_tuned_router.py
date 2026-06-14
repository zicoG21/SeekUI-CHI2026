#!/usr/bin/env python
import argparse
import csv
import json
from collections import Counter, defaultdict
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


def evaluate_rows(rows):
    confusion = Counter((row["gold"], row["pred"]) for row in rows)
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


def evaluate_examples(examples, excluded=None):
    excluded = excluded or set()
    rows = [
        {"gold": gold_status(example), "pred": predicted_status(example)}
        for idx, example in enumerate(examples)
        if idx not in excluded
    ]
    metrics = evaluate_rows(rows)
    return {
        "num_examples": metrics["num_examples"],
        "confusion": {
            "present->present": metrics["present_present"],
            "present->absent": metrics["present_absent"],
            "absent->present": metrics["absent_present"],
            "absent->absent": metrics["absent_absent"],
        },
        "accuracy": metrics["accuracy"],
        "absent_precision": metrics["absent_precision"],
        "absent_recall": metrics["absent_recall"],
        "absent_f1": metrics["absent_f1"],
    }


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


def audit_maps(path):
    data = load_json(Path(path))
    rows = {int(row["index"]): row for row in data.get("rows", [])}
    conflicts = {int(row["index"]) for row in data.get("conflict_rows", [])}
    return rows, conflicts


def candidate_prediction_files(outputs, model, split):
    rows = []
    patterns = [
        (f"present_absent_predictions_{model}_{split}.json", "prompt"),
        (f"present_absent_predictions_{model}_{split}_combined_*.json", "combined"),
        (f"present_absent_predictions_{model}_{split}_color_aware_*.json", "color_aware"),
        (f"present_absent_predictions_{model}_{split}_crop_ocr_vlm.json", "crop_vlm"),
        (f"present_absent_predictions_{model}_{split}_context_crop_ocr_vlm.json", "context_crop_vlm"),
        (f"present_absent_predictions_{model}_{split}_status_ensemble_*.json", "ensemble"),
        (f"present_absent_predictions_{model}_{split}_native_supervised_calibrated_*.json", "supervised_calibrated"),
        (f"present_absent_predictions_{model}_{split}_native_task_routed_*.json", "task_routed"),
        (f"vlm_presence_predictions_{model}_vlm_presence_{split}_*.json", "vlm_presence"),
        (f"vlm_evidence_predictions_{model}_vlm_evidence_{split}_*.json", "vlm_evidence"),
    ]
    skip_suffixes = (
        "_status_eval.json",
        "_selected_threshold.json",
        "_selected_profile.json",
        "_selected_rule.json",
    )
    for pattern, family in patterns:
        for path in sorted(outputs.glob(pattern)):
            if path.name.endswith(skip_suffixes):
                continue
            if path.name.startswith("present_absent_predictions_"):
                variant = path.name.removeprefix(f"present_absent_predictions_{model}_").removesuffix(".json")
            elif path.name.startswith("vlm_presence_predictions_"):
                variant = path.name.removeprefix(f"vlm_presence_predictions_{model}_").removesuffix(".json")
            else:
                variant = path.name.removeprefix(f"vlm_evidence_predictions_{model}_").removesuffix(".json")
            item = {"family": family, "variant": variant, "path": path}
            if item not in rows:
                rows.append(item)
    return rows


def select_mapping(base, candidates, audit_rows, view, metric):
    bucket_method_rows = defaultdict(list)
    bucket_counts = Counter()
    for idx, example in enumerate(base):
        original_gold = gold_status(example)
        bucket = audit_rows.get(idx, {}).get("visibility_bucket", "") or "present_or_missing"
        gold, keep = retasked_gold(original_gold, bucket, view)
        if not keep:
            continue
        bucket_counts[bucket] += 1
        for candidate in candidates:
            data = candidate["data"]
            bucket_method_rows[(bucket, candidate["variant"])].append({
                "gold": gold,
                "pred": predicted_status(data[idx]),
            })
    mapping = {}
    scores = []
    for bucket in sorted(bucket_counts):
        best = None
        for candidate in candidates:
            rows = bucket_method_rows[(bucket, candidate["variant"])]
            if not rows:
                continue
            metrics = evaluate_rows(rows)
            row = {
                "bucket": bucket,
                "family": candidate["family"],
                "variant": candidate["variant"],
                "selection_view": view,
                **metrics,
            }
            scores.append(row)
            key = (
                row.get(metric, -1),
                row["absent_f1"],
                row["accuracy"],
                -row["present_absent"],
            )
            if best is None or key > best[0]:
                best = (key, row)
        if best:
            mapping[bucket] = best[1]
    return mapping, scores


def apply_mapping(base, candidate_by_variant, audit_rows, mapping, fallback_variant):
    output = []
    route_counts = Counter()
    changed = 0
    for idx, example in enumerate(base):
        bucket = audit_rows.get(idx, {}).get("visibility_bucket", "") or "present_or_missing"
        selected = mapping.get(bucket, {}).get("variant", fallback_variant)
        chosen = candidate_by_variant[selected][idx]
        result = dict(example)
        old_status = predicted_status(result)
        new_status = predicted_status(chosen)
        result["predicted_status"] = new_status
        result["native_bucket_router_bucket"] = bucket
        result["native_bucket_router_variant"] = selected
        result["native_bucket_router_original_status"] = old_status
        route_counts[selected] += 1
        changed += int(old_status != new_status)
        output.append(result)
    return output, route_counts, changed


def main():
    parser = argparse.ArgumentParser(description="Tune a native VSGUI router by OCR-visibility bucket over existing methods.")
    parser.add_argument("--work-dir", required=True)
    parser.add_argument("--split-name", default="native_text_color_balanced")
    parser.add_argument("--model-name", default="SeekUI")
    parser.add_argument("--audit-json", required=True)
    parser.add_argument("--selection-view", default="clean_absent_only")
    parser.add_argument("--selection-metric", default="absent_f1", choices=["absent_f1", "accuracy", "absent_precision", "absent_recall"])
    parser.add_argument("--fallback-variant", default="")
    parser.add_argument("--output", required=True)
    parser.add_argument("--metrics-output", required=True)
    parser.add_argument("--mapping-output", required=True)
    parser.add_argument("--bucket-scores-output", required=True)
    args = parser.parse_args()

    outputs = Path(args.work_dir) / "outputs"
    base_path = outputs / f"present_absent_predictions_{args.model_name}_{args.split_name}.json"
    base = load_json(base_path)
    audit_rows, conflict_indices = audit_maps(Path(args.audit_json))
    candidates = []
    for item in candidate_prediction_files(outputs, args.model_name, args.split_name):
        data = load_json(item["path"])
        if len(data) != len(base):
            continue
        candidates.append({**item, "data": data})
    if not candidates:
        raise ValueError("No candidate prediction files found.")
    candidate_by_variant = {item["variant"]: item["data"] for item in candidates}
    fallback_variant = args.fallback_variant or args.split_name
    if fallback_variant not in candidate_by_variant:
        fallback_variant = candidates[0]["variant"]

    mapping, scores = select_mapping(base, candidates, audit_rows, args.selection_view, args.selection_metric)
    output, route_counts, changed = apply_mapping(base, candidate_by_variant, audit_rows, mapping, fallback_variant)
    raw = evaluate_examples(output)
    filtered = evaluate_examples(output, conflict_indices)
    metrics = {
        **raw,
        "selection_view": args.selection_view,
        "selection_metric": args.selection_metric,
        "changed_predictions": changed,
        "route_counts": dict(route_counts),
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
    write_json(Path(args.mapping_output), {
        "selection_view": args.selection_view,
        "selection_metric": args.selection_metric,
        "fallback_variant": fallback_variant,
        "mapping": mapping,
        "route_counts": dict(route_counts),
    })
    write_csv(Path(args.bucket_scores_output), scores)
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
