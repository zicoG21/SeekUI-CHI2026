#!/usr/bin/env python
import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def example_key(example, idx):
    return str(example.get("img_usr_tgt") or example.get("key") or example.get("id") or idx)


def gold_status(example):
    if "target_present" in example:
        return "present" if example["target_present"] else "absent"
    return "absent" if str(example.get("status", "")).casefold() == "absent" else "present"


def safe_div(num, den):
    return num / den if den else 0.0


def metrics(predictions):
    confusion = Counter()
    for row in predictions:
        confusion[(gold_status(row), row.get("predicted_status", "absent"))] += 1
    tp = confusion[("absent", "absent")]
    fp = confusion[("present", "absent")]
    fn = confusion[("absent", "present")]
    tn = confusion[("present", "present")]
    total = sum(confusion.values())
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


def main():
    parser = argparse.ArgumentParser(description="Aggregate crop-level VLM verifier predictions to examples.")
    parser.add_argument("--examples-json", required=True)
    parser.add_argument("--crop-predictions", required=True)
    parser.add_argument("--output-predictions", required=True)
    parser.add_argument("--output-summary", required=True)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    examples = load_json(args.examples_json)
    if args.limit > 0:
        examples = examples[:args.limit]
    crop_predictions = load_json(args.crop_predictions)
    by_key = defaultdict(list)
    for row in crop_predictions:
        by_key[str(row.get("example_key", ""))].append(row)

    predictions = []
    for idx, example in enumerate(examples):
        key = example_key(example, idx)
        crops = by_key.get(key, [])
        present_crops = [row for row in crops if row.get("predicted_status") == "present"]
        result = dict(example)
        result["predicted_status"] = "present" if present_crops else "absent"
        result["candidate_crop_count"] = len(crops)
        result["candidate_crop_present_count"] = len(present_crops)
        result["candidate_crop_present_sources"] = sorted({row.get("candidate_source", "") for row in present_crops})
        predictions.append(result)

    summary = metrics(predictions)
    summary.update({
        "crop_predictions": args.crop_predictions,
        "total_crop_predictions": len(crop_predictions),
        "examples_with_crops": sum(1 for row in predictions if row["candidate_crop_count"] > 0),
    })
    save_json(Path(args.output_predictions), predictions)
    save_json(Path(args.output_summary), summary)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
