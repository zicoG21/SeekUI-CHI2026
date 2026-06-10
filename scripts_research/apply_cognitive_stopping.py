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


def main():
    parser = argparse.ArgumentParser(description="Apply a post-hoc cognitive stopping threshold to predictions.")
    parser.add_argument("--predictions", required=True)
    parser.add_argument("--evidence", required=True)
    parser.add_argument("--threshold", type=float, required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--metrics-output", default="")
    parser.add_argument(
        "--mode",
        choices=["override", "present_only"],
        default="override",
        help="override rewrites all statuses from evidence; present_only only changes present to absent.",
    )
    args = parser.parse_args()

    predictions = load_json(Path(args.predictions))
    evidence = load_evidence(Path(args.evidence))
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
        stopped_status = "absent" if score < args.threshold else "present"
        if args.mode == "present_only" and original_status == "absent":
            new_status = original_status
        else:
            new_status = stopped_status

        result["original_predicted_status"] = original_status
        result["predicted_status"] = new_status
        result["cognitive_stopping_applied"] = new_status != original_status
        result["cognitive_stopping_threshold"] = args.threshold
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
        "threshold": args.threshold,
        "mode": args.mode,
        "changed_predictions": changed,
        "missing_evidence": missing_evidence,
        "input_predictions": str(Path(args.predictions)),
        "input_evidence": str(Path(args.evidence)),
        "output": str(Path(args.output)),
    })
    write_json(Path(args.output), adjusted)
    if args.metrics_output:
        write_json(Path(args.metrics_output), metrics)
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
