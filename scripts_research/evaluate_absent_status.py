#!/usr/bin/env python
import argparse
import json
from collections import Counter
from pathlib import Path


def normalize_status(value, default="present"):
    text = str(value or default).casefold()
    if text in {"absent", "not_found", "not found", "no object", "no target", "not present"}:
        return "absent"
    return "present"


def safe_div(num, den):
    return num / den if den else 0.0


def main():
    parser = argparse.ArgumentParser(description="Evaluate target-present/absent status predictions.")
    parser.add_argument("--predictions", required=True)
    parser.add_argument("--output", default="", help="Optional JSON summary output.")
    args = parser.parse_args()

    examples = json.load(open(args.predictions, "r", encoding="utf-8"))
    confusion = Counter()
    for example in examples:
        gold = normalize_status(example.get("status"), default="present")
        if "target_present" in example:
            gold = "present" if example["target_present"] else "absent"
        pred = normalize_status(example.get("predicted_status"), default="present")
        confusion[(gold, pred)] += 1

    tp_absent = confusion[("absent", "absent")]
    fp_absent = confusion[("present", "absent")]
    fn_absent = confusion[("absent", "present")]
    tn_absent = confusion[("present", "present")]
    total = sum(confusion.values())

    precision = safe_div(tp_absent, tp_absent + fp_absent)
    recall = safe_div(tp_absent, tp_absent + fn_absent)
    f1 = safe_div(2 * precision * recall, precision + recall)
    accuracy = safe_div(tp_absent + tn_absent, total)

    summary = {
        "num_examples": total,
        "confusion": {
            "present->present": tn_absent,
            "present->absent": fp_absent,
            "absent->present": fn_absent,
            "absent->absent": tp_absent,
        },
        "accuracy": accuracy,
        "absent_precision": precision,
        "absent_recall": recall,
        "absent_f1": f1,
    }

    print(json.dumps(summary, indent=2))
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        with open(output, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)


if __name__ == "__main__":
    main()
