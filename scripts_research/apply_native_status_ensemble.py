#!/usr/bin/env python
import argparse
import csv
import json
from collections import Counter
from pathlib import Path


ABSENT_STATUSES = {"absent", "not_found", "not found", "no object", "no target", "not present"}
RULES = [
    "primary",
    "secondary",
    "tertiary",
    "primary_or_secondary_absent",
    "primary_and_secondary_absent",
    "primary_rescue_by_secondary_present",
    "primary_rescue_by_tertiary_present",
    "primary_rescue_by_any_present",
    "primary_confirmed_by_any_absent",
    "majority_absent",
    "unanimous_absent",
    "any_absent",
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
        "accuracy": safe_div(tp + tn, total),
        "absent_precision": precision,
        "absent_recall": recall,
        "absent_f1": f1,
        "present_absent": fp,
        "absent_present": fn,
        "present_present": tn,
        "absent_absent": tp,
    }


def conflict_indices(path):
    if not path:
        return set()
    data = load_json(Path(path))
    return {int(row["index"]) for row in data.get("conflict_rows", [])}


def decide(rule, primary, secondary, tertiary):
    statuses = [primary, secondary, tertiary]
    absent_count = sum(1 for status in statuses if status == "absent")
    present_count = len(statuses) - absent_count
    if rule == "primary":
        return primary
    if rule == "secondary":
        return secondary
    if rule == "tertiary":
        return tertiary
    if rule == "primary_or_secondary_absent":
        return "absent" if primary == "absent" or secondary == "absent" else "present"
    if rule == "primary_and_secondary_absent":
        return "absent" if primary == "absent" and secondary == "absent" else "present"
    if rule == "primary_rescue_by_secondary_present":
        return "present" if primary == "absent" and secondary == "present" else primary
    if rule == "primary_rescue_by_tertiary_present":
        return "present" if primary == "absent" and tertiary == "present" else primary
    if rule == "primary_rescue_by_any_present":
        return "present" if primary == "absent" and (secondary == "present" or tertiary == "present") else primary
    if rule == "primary_confirmed_by_any_absent":
        return "absent" if primary == "absent" and (secondary == "absent" or tertiary == "absent") else "present"
    if rule == "majority_absent":
        return "absent" if absent_count >= 2 else "present"
    if rule == "unanimous_absent":
        return "absent" if absent_count == 3 else "present"
    if rule == "any_absent":
        return "absent" if present_count < 3 else "present"
    raise ValueError(f"Unknown ensemble rule: {rule}")


def apply_rule(base, primary, secondary, tertiary, rule, labels):
    output = []
    changed = 0
    for idx, example in enumerate(base):
        p_status = predicted_status(primary[idx])
        s_status = predicted_status(secondary[idx])
        t_status = predicted_status(tertiary[idx])
        new_status = decide(rule, p_status, s_status, t_status)
        result = dict(example)
        original = predicted_status(example)
        result["predicted_status"] = new_status
        result["native_ensemble_rule"] = rule
        result["native_ensemble_primary_label"] = labels["primary"]
        result["native_ensemble_secondary_label"] = labels["secondary"]
        result["native_ensemble_tertiary_label"] = labels["tertiary"]
        result["native_ensemble_primary_status"] = p_status
        result["native_ensemble_secondary_status"] = s_status
        result["native_ensemble_tertiary_status"] = t_status
        result["native_ensemble_original_status"] = original
        changed += int(new_status != original)
        output.append(result)
    return output, changed


def select_best(rows, metric):
    return max(
        rows,
        key=lambda row: (
            float(row.get(metric, -1)),
            float(row.get("filtered_absent_f1", -1)),
            float(row.get("absent_f1", -1)),
            float(row.get("accuracy", -1)),
            -float(row.get("present_absent", 0)),
        ),
    )


def main():
    parser = argparse.ArgumentParser(description="Apply simple native status ensembles over existing method predictions.")
    parser.add_argument("--base-predictions", required=True)
    parser.add_argument("--primary-predictions", required=True)
    parser.add_argument("--secondary-predictions", required=True)
    parser.add_argument("--tertiary-predictions", required=True)
    parser.add_argument("--primary-label", default="primary")
    parser.add_argument("--secondary-label", default="secondary")
    parser.add_argument("--tertiary-label", default="tertiary")
    parser.add_argument("--audit-json", default="")
    parser.add_argument("--select-metric", default="filtered_absent_f1", choices=["absent_f1", "accuracy", "filtered_absent_f1", "filtered_accuracy"])
    parser.add_argument("--output", required=True)
    parser.add_argument("--metrics-output", required=True)
    parser.add_argument("--sweep-output", required=True)
    parser.add_argument("--selected-output", required=True)
    args = parser.parse_args()

    base = load_json(Path(args.base_predictions))
    primary = load_json(Path(args.primary_predictions))
    secondary = load_json(Path(args.secondary_predictions))
    tertiary = load_json(Path(args.tertiary_predictions))
    lengths = {len(base), len(primary), len(secondary), len(tertiary)}
    if len(lengths) != 1:
        raise ValueError(f"Prediction lengths differ: {sorted(lengths)}")

    labels = {"primary": args.primary_label, "secondary": args.secondary_label, "tertiary": args.tertiary_label}
    excluded = conflict_indices(args.audit_json)
    rows = []
    candidates = {}
    for rule in RULES:
        predictions, changed = apply_rule(base, primary, secondary, tertiary, rule, labels)
        raw = evaluate(predictions)
        filtered = evaluate(predictions, excluded)
        row = {
            "rule": rule,
            "changed_predictions": changed,
            **raw,
            "filtered_num_examples": filtered["num_examples"],
            "filtered_accuracy": filtered["accuracy"],
            "filtered_absent_precision": filtered["absent_precision"],
            "filtered_absent_recall": filtered["absent_recall"],
            "filtered_absent_f1": filtered["absent_f1"],
            "filtered_present_absent": filtered["present_absent"],
            "filtered_absent_present": filtered["absent_present"],
        }
        rows.append(row)
        candidates[rule] = predictions

    selected = select_best(rows, args.select_metric)
    selected_rule = selected["rule"]
    write_csv(Path(args.sweep_output), rows)
    write_json(Path(args.output), candidates[selected_rule])
    selected_with_confusion = {
        **selected,
        "confusion": {
            "present->present": selected["present_present"],
            "present->absent": selected["present_absent"],
            "absent->present": selected["absent_present"],
            "absent->absent": selected["absent_absent"],
        },
    }
    write_json(Path(args.metrics_output), {
        **selected_with_confusion,
        "selected_metric": args.select_metric,
        "selected_rule": selected_rule,
        "audit_json": args.audit_json,
        "output": args.output,
    })
    write_json(Path(args.selected_output), selected)
    print(json.dumps({"selected": selected, "output": args.output}, indent=2))


if __name__ == "__main__":
    main()
