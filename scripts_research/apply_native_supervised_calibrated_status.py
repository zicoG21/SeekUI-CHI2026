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


def read_csv(path):
    with open(path, "r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


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


def select_threshold(sweep_rows, view, constraint):
    rows = [row for row in sweep_rows if row.get("view") == view]
    if not rows:
        raise ValueError(f"No sweep rows for view={view}")

    def keep(row):
        if constraint == "max_f1":
            return True
        if constraint.startswith("precision_ge_"):
            return safe_float(row.get("absent_precision")) >= safe_float(constraint.removeprefix("precision_ge_"))
        if constraint.startswith("pa_le_"):
            return safe_float(row.get("present_absent")) <= safe_float(constraint.removeprefix("pa_le_"))
        raise ValueError(f"Unknown constraint: {constraint}")

    candidates = [row for row in rows if keep(row)]
    if not candidates:
        raise ValueError(f"No threshold satisfies constraint={constraint} for view={view}")
    return max(
        candidates,
        key=lambda row: (
            safe_float(row.get("absent_f1")),
            safe_float(row.get("accuracy")),
            safe_float(row.get("absent_precision")),
            -safe_float(row.get("present_absent")),
        ),
    )


def main():
    parser = argparse.ArgumentParser(description="Apply native supervised calibration probabilities as status predictions.")
    parser.add_argument("--base-predictions", required=True)
    parser.add_argument("--calibration-predictions-csv", required=True)
    parser.add_argument("--calibration-sweep-csv", required=True)
    parser.add_argument("--view", default="native_original")
    parser.add_argument("--constraint", default="max_f1")
    parser.add_argument("--threshold", type=float, default=None)
    parser.add_argument("--variant-label", default="")
    parser.add_argument("--output", required=True)
    parser.add_argument("--metrics-output", required=True)
    parser.add_argument("--selected-output", required=True)
    args = parser.parse_args()

    examples = load_json(Path(args.base_predictions))
    prediction_rows = [row for row in read_csv(Path(args.calibration_predictions_csv)) if row.get("view") == args.view]
    probs = {int(row["index"]): safe_float(row.get("prob_absent")) for row in prediction_rows}
    if args.threshold is None:
        selected = select_threshold(read_csv(Path(args.calibration_sweep_csv)), args.view, args.constraint)
        threshold = safe_float(selected["threshold"])
    else:
        threshold = args.threshold
        selected = {"view": args.view, "constraint": "manual", "threshold": threshold}

    output = []
    changed = 0
    for idx, example in enumerate(examples):
        result = dict(example)
        if idx in probs:
            old_status = predicted_status(result)
            new_status = "absent" if probs[idx] >= threshold else "present"
            result["predicted_status"] = new_status
            result["native_supervised_calibration_view"] = args.view
            result["native_supervised_calibration_constraint"] = args.constraint
            result["native_supervised_calibration_threshold"] = threshold
            result["native_supervised_calibration_prob_absent"] = probs[idx]
            result["native_supervised_calibration_variant"] = args.variant_label or f"{args.view}_{args.constraint}"
            changed += int(old_status != new_status)
        output.append(result)

    metrics = evaluate(output)
    metrics.update({
        "view": args.view,
        "constraint": args.constraint,
        "threshold": threshold,
        "changed_predictions": changed,
        "output": args.output,
    })
    write_json(Path(args.output), output)
    write_json(Path(args.metrics_output), metrics)
    write_json(Path(args.selected_output), selected)
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
