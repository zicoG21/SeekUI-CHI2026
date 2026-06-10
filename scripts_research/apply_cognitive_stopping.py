#!/usr/bin/env python
import argparse
import csv
import json
from collections import Counter
from pathlib import Path


ABSENT_STATUSES = {"absent", "not_found", "not found", "no object", "no target", "not present"}


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_evidence(path):
    rows = {}
    with open(path, "r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            rows[int(row["index"])] = row
    return rows


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


def safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_div(num, den):
    return num / den if den else 0.0


def evaluate(examples):
    confusion = Counter()
    for example in examples:
        confusion[(gold_status(example), predicted_status(example))] += 1
    tp_absent = confusion[("absent", "absent")]
    fp_absent = confusion[("present", "absent")]
    fn_absent = confusion[("absent", "present")]
    tn_absent = confusion[("present", "present")]
    total = tp_absent + fp_absent + fn_absent + tn_absent
    precision = safe_div(tp_absent, tp_absent + fp_absent)
    recall = safe_div(tp_absent, tp_absent + fn_absent)
    f1 = safe_div(2 * precision * recall, precision + recall)
    return {
        "num_examples": total,
        "confusion": {
            "present->present": tn_absent,
            "present->absent": fp_absent,
            "absent->present": fn_absent,
            "absent->absent": tp_absent,
        },
        "accuracy": safe_div(tp_absent + tn_absent, total),
        "absent_precision": precision,
        "absent_recall": recall,
        "absent_f1": f1,
    }


def adjusted_status(original_status, score, threshold, mode):
    stopped_status = "absent" if score < threshold else "present"
    if mode == "present_only" and original_status == "absent":
        return original_status
    return stopped_status


def apply_threshold(predictions, evidence, threshold, mode):
    adjusted = []
    changed = 0
    missing_evidence = 0

    for idx, example in enumerate(predictions):
        result = dict(example)
        original_status = predicted_status(example)
        row = evidence.get(idx)
        if row is None:
            missing_evidence += 1
            adjusted.append(result)
            continue

        score = safe_float(row.get("path_best_evidence"))
        new_status = adjusted_status(original_status, score, threshold, mode)

        result["original_predicted_status"] = original_status
        result["predicted_status"] = new_status
        result["cognitive_stopping_applied"] = new_status != original_status
        result["cognitive_stopping_threshold"] = threshold
        result["path_best_evidence"] = score
        result["path_best_candidate"] = row.get("path_best_candidate", "")
        result["path_best_similarity"] = safe_float(row.get("path_best_similarity"))
        result["path_best_distance_px"] = row.get("path_best_distance_px", "")
        result["path_best_step"] = row.get("path_best_step", "")
        if new_status != original_status:
            changed += 1
        adjusted.append(result)

    metrics = evaluate(adjusted)
    metrics.update({
        "threshold": threshold,
        "mode": mode,
        "changed_predictions": changed,
        "missing_evidence": missing_evidence,
    })
    return adjusted, metrics


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def threshold_values(step):
    values = []
    value = 0.0
    while value <= 1.000001:
        values.append(round(value, 4))
        value += step
    return values


def sweep_thresholds(predictions, evidence, mode, step):
    rows = []
    for threshold in threshold_values(step):
        _, metrics = apply_threshold(predictions, evidence, threshold, mode)
        confusion = metrics["confusion"]
        rows.append({
            "threshold": threshold,
            "mode": mode,
            "accuracy": metrics["accuracy"],
            "absent_precision": metrics["absent_precision"],
            "absent_recall": metrics["absent_recall"],
            "absent_f1": metrics["absent_f1"],
            "changed_predictions": metrics["changed_predictions"],
            "missing_evidence": metrics["missing_evidence"],
            "present_present": confusion["present->present"],
            "present_absent": confusion["present->absent"],
            "absent_present": confusion["absent->present"],
            "absent_absent": confusion["absent->absent"],
        })
    return rows


def main():
    parser = argparse.ArgumentParser(description="Apply a post-hoc cognitive stopping threshold to predictions.")
    parser.add_argument("--predictions", required=True)
    parser.add_argument("--evidence", required=True)
    parser.add_argument("--threshold", type=float, default=None)
    parser.add_argument("--output", default="")
    parser.add_argument("--metrics-output", default="")
    parser.add_argument("--sweep-output", default="")
    parser.add_argument("--threshold-step", type=float, default=0.05)
    parser.add_argument(
        "--mode",
        choices=["override", "present_only"],
        default="override",
        help="override rewrites all statuses from evidence; present_only only changes present to absent.",
    )
    args = parser.parse_args()

    predictions = load_json(Path(args.predictions))
    evidence = load_evidence(Path(args.evidence))

    if args.sweep_output:
        sweep_rows = sweep_thresholds(predictions, evidence, args.mode, args.threshold_step)
        write_csv(Path(args.sweep_output), sweep_rows)

    if args.output or args.metrics_output:
        if args.threshold is None:
            raise ValueError("--threshold is required when writing --output or --metrics-output")
        adjusted, metrics = apply_threshold(predictions, evidence, args.threshold, args.mode)
        metrics.update({
            "input_predictions": str(Path(args.predictions)),
            "input_evidence": str(Path(args.evidence)),
            "output": str(Path(args.output)) if args.output else "",
        })
        if args.output:
            write_json(Path(args.output), adjusted)
        if args.metrics_output:
            write_json(Path(args.metrics_output), metrics)
        print(json.dumps(metrics, indent=2))
    elif args.sweep_output:
        print(json.dumps({
            "mode": args.mode,
            "sweep_output": str(Path(args.sweep_output)),
            "threshold_step": args.threshold_step,
        }, indent=2))
    else:
        raise ValueError("Set --output/--metrics-output with --threshold, or set --sweep-output")


if __name__ == "__main__":
    main()
