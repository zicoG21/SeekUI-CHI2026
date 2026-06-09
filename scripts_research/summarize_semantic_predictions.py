#!/usr/bin/env python
import argparse
import json
from collections import defaultdict
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Summarize semantic-query prediction behavior by query type.")
    parser.add_argument("--predictions", required=True)
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    data = json.load(open(args.predictions, "r", encoding="utf-8"))
    groups = defaultdict(list)
    for example in data:
        groups[example.get("query_type", "unknown")].append(example)

    summary = {}
    for query_type, examples in groups.items():
        lengths = [len(example.get("prediction", []) or []) for example in examples]
        absent = sum(1 for example in examples if example.get("predicted_status") == "absent")
        summary[query_type] = {
            "num_examples": len(examples),
            "empty_predictions": sum(1 for length in lengths if length == 0),
            "avg_prediction_len": sum(lengths) / len(lengths) if lengths else 0,
            "predicted_absent": absent,
            "predicted_absent_rate": absent / len(examples) if examples else 0,
        }

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        with open(output, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
