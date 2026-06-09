#!/usr/bin/env python
import argparse
import csv
import json
import random
from pathlib import Path


def status(example):
    if "predicted_status" in example:
        return str(example.get("predicted_status") or "")
    if "target_present" in example:
        return "present" if example["target_present"] else "absent"
    return str(example.get("status") or "")


def matches(example, mode):
    pred = example.get("prediction", []) or []
    if mode == "all":
        return True
    if mode == "empty_prediction":
        return len(pred) == 0
    if mode == "short_prediction":
        return len(pred) <= 2
    if mode == "long_prediction":
        return len(pred) >= 8
    if mode == "predicted_absent":
        return status(example) == "absent"
    if mode == "fallback":
        return bool(example.get("prediction_fallback"))
    if mode == "semantic_non_exact":
        return example.get("query_type") not in {None, "", "exact"}
    return False


def main():
    parser = argparse.ArgumentParser(description="Sample qualitative review cases from prediction JSON.")
    parser.add_argument("--predictions", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--index-csv", default="")
    parser.add_argument("--mode", default="all", choices=[
        "all",
        "empty_prediction",
        "short_prediction",
        "long_prediction",
        "predicted_absent",
        "fallback",
        "semantic_non_exact",
    ])
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    data = json.load(open(args.predictions, "r", encoding="utf-8"))
    candidates = [example for example in data if matches(example, args.mode)]
    rng.shuffle(candidates)
    selected = candidates[: args.limit]

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w", encoding="utf-8") as f:
        json.dump(selected, f, indent=2, ensure_ascii=False)

    index_path = Path(args.index_csv) if args.index_csv else output.with_suffix(".csv")
    with open(index_path, "w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "img_usr_tgt",
            "image",
            "target",
            "query_text",
            "query_type",
            "status",
            "predicted_status",
            "prediction_len",
            "prediction_fallback",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for example in selected:
            writer.writerow({
                "img_usr_tgt": example.get("img_usr_tgt"),
                "image": example.get("image"),
                "target": example.get("target"),
                "query_text": example.get("query_text"),
                "query_type": example.get("query_type"),
                "status": example.get("status"),
                "predicted_status": example.get("predicted_status"),
                "prediction_len": len(example.get("prediction", []) or []),
                "prediction_fallback": example.get("prediction_fallback", ""),
            })

    print(f"Input examples     : {len(data)}")
    print(f"Matching candidates: {len(candidates)}")
    print(f"Selected examples  : {len(selected)}")
    print(f"Output JSON        : {output}")
    print(f"Index CSV          : {index_path}")


if __name__ == "__main__":
    main()
