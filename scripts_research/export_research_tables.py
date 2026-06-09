#!/usr/bin/env python
import argparse
import csv
import json
from pathlib import Path


def write_rows(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = sorted({key for row in rows for key in row})
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def flatten_metrics(name, metrics):
    row = {"name": name}
    row.update(metrics)
    return row


def main():
    parser = argparse.ArgumentParser(description="Export research_summary.json into CSV tables.")
    parser.add_argument("--summary-json", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()

    summary = json.load(open(args.summary_json, "r", encoding="utf-8"))
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    prediction_health = [
        flatten_metrics(name, metrics)
        for name, metrics in summary.get("prediction_health", {}).items()
    ]
    overall_metrics = [
        flatten_metrics(model, metrics)
        for model, metrics in summary.get("evaluation_metrics", {}).items()
    ]
    absent_status = [
        flatten_metrics(model, metrics)
        for model, metrics in summary.get("absent_status", {}).items()
    ]
    semantic_query = []
    for model, groups in summary.get("semantic_query", {}).items():
        for query_type, metrics in groups.items():
            row = {"model": model, "query_type": query_type}
            row.update(metrics)
            semantic_query.append(row)

    split_metrics = []
    for row in summary.get("split_metrics", []):
        flat = {
            "group": row.get("group"),
            "field": row.get("field"),
            "value": row.get("value"),
            "count": row.get("count"),
            "log": row.get("log"),
        }
        flat.update(row.get("metrics", {}))
        split_metrics.append(flat)

    cognitive = []
    if summary.get("cognitive_stopping"):
        best = summary["cognitive_stopping"].get("best_by_absent_f1", {})
        row = {
            "num_examples": summary["cognitive_stopping"].get("num_examples"),
            "num_present": summary["cognitive_stopping"].get("num_present"),
            "num_absent": summary["cognitive_stopping"].get("num_absent"),
        }
        row.update(best)
        cognitive.append(row)

    write_rows(out_dir / "prediction_health.csv", prediction_health)
    write_rows(out_dir / "overall_metrics.csv", overall_metrics)
    write_rows(out_dir / "absent_status.csv", absent_status)
    write_rows(out_dir / "semantic_query_summary.csv", semantic_query)
    write_rows(out_dir / "split_metrics.csv", split_metrics)
    write_rows(out_dir / "cognitive_stopping.csv", cognitive)

    print(f"Exported tables to {out_dir}")


if __name__ == "__main__":
    main()
