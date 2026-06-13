#!/usr/bin/env python
import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from pathlib import Path


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def gold_status(example):
    if "target_present" in example:
        return "present" if example["target_present"] else "absent"
    status = str(example.get("status") or "present").casefold()
    return "absent" if status == "absent" else "present"


def endpoint(sample):
    points = sample.get("prediction") or []
    if not points:
        return None
    return points[-1]


def endpoint_spread(samples):
    endpoints = [endpoint(sample) for sample in samples if endpoint(sample)]
    if len(endpoints) < 2:
        return 0.0
    xs = [pt[0] for pt in endpoints]
    ys = [pt[1] for pt in endpoints]
    cx = sum(xs) / len(xs)
    cy = sum(ys) / len(ys)
    return math.sqrt(sum((x - cx) ** 2 + (y - cy) ** 2 for x, y in endpoints) / len(endpoints))


def status_entropy(samples):
    total = len(samples)
    if total == 0:
        return 0.0
    counts = Counter(sample.get("predicted_status", "present") for sample in samples)
    entropy = 0.0
    for count in counts.values():
        p = count / total
        entropy -= p * math.log2(p)
    return entropy


def safe_div(num, den):
    return num / den if den else 0.0


def write_csv(path, rows, fieldnames):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description="Summarize multi-sample scanpath uncertainty.")
    parser.add_argument("--predictions", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--output-md", required=True)
    args = parser.parse_args()

    examples = load_json(args.predictions)
    rows = []
    grouped = defaultdict(list)
    for idx, example in enumerate(examples):
        samples = example.get("multisample_samples", []) or []
        statuses = [sample.get("predicted_status", "present") for sample in samples]
        path_lens = [len(sample.get("prediction") or []) for sample in samples]
        absent_votes = sum(1 for status in statuses if status == "absent")
        row = {
            "index": idx,
            "img_usr_tgt": example.get("img_usr_tgt", ""),
            "image": example.get("image", ""),
            "query_text": example.get("query_text", example.get("target", "")),
            "gold_status": gold_status(example),
            "majority_status": example.get("predicted_status", "present"),
            "samples": len(samples),
            "absent_votes": absent_votes,
            "absent_vote_rate": safe_div(absent_votes, len(samples)),
            "status_entropy": status_entropy(samples),
            "endpoint_spread": endpoint_spread(samples),
            "mean_path_len": safe_div(sum(path_lens), len(path_lens)),
        }
        rows.append(row)
        grouped[row["gold_status"]].append(row)

    summaries = []
    for status, items in sorted(grouped.items()):
        summaries.append({
            "gold_status": status,
            "num_examples": len(items),
            "mean_absent_vote_rate": safe_div(sum(item["absent_vote_rate"] for item in items), len(items)),
            "mean_status_entropy": safe_div(sum(item["status_entropy"] for item in items), len(items)),
            "mean_endpoint_spread": safe_div(sum(item["endpoint_spread"] for item in items), len(items)),
            "mean_path_len": safe_div(sum(item["mean_path_len"] for item in items), len(items)),
        })

    output_json = Path(args.output_json)
    output_csv = Path(args.output_csv)
    output_md = Path(args.output_md)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump({"num_examples": len(rows), "summary": summaries, "rows": rows}, f, indent=2, ensure_ascii=False)
    write_csv(output_csv, rows, list(rows[0].keys()) if rows else [])

    with open(output_md, "w", encoding="utf-8") as f:
        f.write("# Multi-Sample Scanpath Uncertainty\n\n")
        f.write(f"- Prediction file: `{args.predictions}`\n")
        f.write(f"- Examples: {len(rows)}\n\n")
        f.write("| Gold Status | N | Absent Vote Rate | Status Entropy | Endpoint Spread | Path Len |\n")
        f.write("|---|---:|---:|---:|---:|---:|\n")
        for row in summaries:
            f.write(
                f"| {row['gold_status']} | {row['num_examples']} | "
                f"{row['mean_absent_vote_rate']:.4f} | {row['mean_status_entropy']:.4f} | "
                f"{row['mean_endpoint_spread']:.2f} | {row['mean_path_len']:.2f} |\n"
            )

    print(json.dumps({"examples": len(rows), "output_md": str(output_md)}, indent=2))


if __name__ == "__main__":
    main()
