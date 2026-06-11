#!/usr/bin/env python
import argparse
import csv
import json
import re
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


def absent_variant(name):
    marker = "_vlm_evidence"
    if marker in name:
        model, variant = name.split(marker, 1)
        return model, f"vlm_evidence{variant}"
    marker = "_vlm_presence"
    if marker in name:
        model, variant = name.split(marker, 1)
        return model, f"vlm_presence{variant}"
    marker = "_combined_"
    if marker in name:
        model, variant = name.split(marker, 1)
        return model, f"combined_{variant}"
    marker = "_ocr_candidate_verifier_"
    if marker in name:
        model, variant = name.split(marker, 1)
        return model, f"ocr_candidate_verifier_{variant}"
    marker = "_candidate_verifier_"
    if marker in name:
        model, variant = name.split(marker, 1)
        return model, f"candidate_verifier_{variant}"
    if name.endswith("_cognitive_stop_present_only"):
        return name.removesuffix("_cognitive_stop_present_only"), "cognitive_stop_present_only"
    if name.endswith("_cognitive_stop"):
        return name.removesuffix("_cognitive_stop"), "cognitive_stop_override"
    return name, "prompt_only"


def absent_status_core_rows(absent_status):
    rows = []
    for name, metrics in absent_status.items():
        model, variant = absent_variant(name)
        rows.append({
            "model": model,
            "variant": variant,
            "accuracy": metrics.get("accuracy", ""),
            "absent_precision": metrics.get("absent_precision", ""),
            "absent_recall": metrics.get("absent_recall", ""),
            "absent_f1": metrics.get("absent_f1", ""),
            "present_to_absent": metrics.get("confusion", {}).get("present->absent", ""),
            "absent_to_present": metrics.get("confusion", {}).get("absent->present", ""),
            "changed_predictions": metrics.get("changed_predictions", 0 if variant == "prompt_only" else ""),
            "threshold": metrics.get("threshold", ""),
            "mode": metrics.get("mode", ""),
        })
    order = {"SeekUI": 0, "SeekUI_sft": 1}
    variant_order = {
        "prompt_only": 0,
        "cognitive_stop_override": 1,
        "cognitive_stop_present_only": 2,
        "candidate_verifier_candidate_similarity_present_only": 3,
        "candidate_verifier_hybrid_present_only": 4,
        "candidate_verifier_path_best_evidence_present_only": 5,
        "ocr_candidate_verifier_present_only": 6,
        "combined_or_present_only": 7,
        "combined_and_present_only": 8,
        "combined_and_present_only_best_f1": 9,
        "vlm_presence": 10,
        "vlm_presence_ocr_aware": 11,
        "vlm_presence_search_behavior": 12,
        "vlm_presence_conservative": 13,
        "vlm_evidence_evidence_aware": 14,
        "vlm_evidence_evidence_conservative": 15,
        "vlm_evidence_evidence_rescue_present": 16,
    }
    rows.sort(key=lambda row: (order.get(row["model"], 99), variant_order.get(row["variant"], 99)))
    return rows


def main():
    parser = argparse.ArgumentParser(description="Export research_summary.json into CSV tables.")
    parser.add_argument("--summary-json", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--include-pilots", action="store_true", help="Include pilot-only outputs such as *_n200 runs.")
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
        if args.include_pilots or not re.search(r"_n\d+$", model)
    ]
    absent_status_source = {
        model: metrics
        for model, metrics in summary.get("absent_status", {}).items()
        if args.include_pilots or not re.search(r"_n\d+$", model)
    }
    absent_status_core = absent_status_core_rows(absent_status_source)
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
    write_rows(out_dir / "absent_status_core.csv", absent_status_core)
    write_rows(out_dir / "semantic_query_summary.csv", semantic_query)
    write_rows(out_dir / "split_metrics.csv", split_metrics)
    write_rows(out_dir / "cognitive_stopping.csv", cognitive)

    print(f"Exported tables to {out_dir}")


if __name__ == "__main__":
    main()
