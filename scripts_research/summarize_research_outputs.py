#!/usr/bin/env python
import argparse
import csv
import json
import os
import re
from pathlib import Path


METRIC_RE = re.compile(r"^([A-Za-z0-9_]+)\s*:\s*([-+0-9.]+)\s*$")


def read_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def parse_eval_log(path):
    metrics = {}
    if not path.exists():
        return metrics
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        match = METRIC_RE.match(line.strip())
        if match:
            metrics[match.group(1)] = float(match.group(2))
    return metrics


def read_optional_json(path):
    if path.exists():
        return read_json(path)
    return None


def prediction_health(path):
    if not path.exists():
        return None
    data = read_json(path)
    lengths = [len(item.get("prediction", []) or []) for item in data]
    return {
        "num_examples": len(data),
        "empty_predictions": sum(1 for length in lengths if length == 0),
        "min_prediction_len": min(lengths) if lengths else 0,
        "max_prediction_len": max(lengths) if lengths else 0,
        "avg_prediction_len": sum(lengths) / len(lengths) if lengths else 0,
    }


def collect_split_metrics(outputs):
    split_root = outputs / "split_eval"
    rows = []
    if not split_root.exists():
        return rows
    for manifest_path in sorted(split_root.glob("**/manifest_with_logs.json")):
        group = manifest_path.parent.name
        manifest = read_json(manifest_path)
        for item in manifest:
            log_path = Path(item.get("eval_log", ""))
            metrics = parse_eval_log(log_path)
            rows.append({
                "group": group,
                "field": item.get("field"),
                "value": item.get("value"),
                "count": item.get("count"),
                "metrics": metrics,
                "log": str(log_path) if log_path else "",
            })
    return rows


def write_metric_table(lines, title, metrics_by_name):
    lines.append(f"## {title}")
    lines.append("")
    if not metrics_by_name:
        lines.append("Pending.")
        lines.append("")
        return
    metric_names = sorted({metric for metrics in metrics_by_name.values() for metric in metrics})
    header = "| Model | " + " | ".join(metric_names) + " |"
    sep = "|---" * (len(metric_names) + 1) + "|"
    lines.append(header)
    lines.append(sep)
    for model, metrics in metrics_by_name.items():
        values = [f"{metrics.get(metric, ''):.4f}" if metric in metrics else "" for metric in metric_names]
        lines.append("| " + model + " | " + " | ".join(values) + " |")
    lines.append("")


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


def export_tables(report, out_dir):
    prediction_health = [{"name": name, **metrics} for name, metrics in report.get("prediction_health", {}).items()]
    overall_metrics = [{"name": name, **metrics} for name, metrics in report.get("evaluation_metrics", {}).items()]
    absent_status = [{"name": name, **metrics} for name, metrics in report.get("absent_status", {}).items()]
    semantic_query = []
    for model, groups in report.get("semantic_query", {}).items():
        for query_type, metrics in groups.items():
            semantic_query.append({"model": model, "query_type": query_type, **metrics})
    split_metrics = []
    for row in report.get("split_metrics", []):
        split_metrics.append({
            "group": row.get("group"),
            "field": row.get("field"),
            "value": row.get("value"),
            "count": row.get("count"),
            "log": row.get("log"),
            **row.get("metrics", {}),
        })
    manual_review_fields = []
    manual_review_errors = []
    manual_review = report.get("manual_review")
    if manual_review:
        for field, metrics in manual_review.get("fields", {}).items():
            manual_review_fields.append({"field": field, **metrics})
        for category, count in manual_review.get("error_category_counts", {}).items():
            manual_review_errors.append({"category": category, "count": count})
    followup_status = []
    if report.get("followup_status"):
        for item in report["followup_status"].get("items", []):
            followup_status.append({
                "id": item.get("id"),
                "title": item.get("title"),
                "state": item.get("state"),
                "missing_count": len(item.get("missing", [])),
                "command": item.get("command", ""),
            })

    write_rows(out_dir / "prediction_health.csv", prediction_health)
    write_rows(out_dir / "overall_metrics.csv", overall_metrics)
    write_rows(out_dir / "absent_status.csv", absent_status)
    write_rows(out_dir / "semantic_query_summary.csv", semantic_query)
    write_rows(out_dir / "split_metrics.csv", split_metrics)
    write_rows(out_dir / "manual_review_fields.csv", manual_review_fields)
    write_rows(out_dir / "manual_review_errors.csv", manual_review_errors)
    write_rows(out_dir / "followup_status.csv", followup_status)


def main():
    parser = argparse.ArgumentParser(description="Summarize SeekUI reproduction and follow-up research outputs.")
    parser.add_argument("--work-dir", default=os.environ.get("SEEKUI_WORK", ""))
    parser.add_argument("--output", default="")
    parser.add_argument("--tables-dir", default="", help="Optional CSV table output directory. Defaults to <output stem>_tables.")
    args = parser.parse_args()

    work_dir = Path(args.work_dir) if args.work_dir else Path(".scratch/seekui")
    outputs = work_dir / "outputs"
    data_dir = work_dir / "data"

    report = {
        "work_dir": str(work_dir),
        "files": {},
        "prediction_health": {},
        "evaluation_metrics": {},
        "absent_status": {},
        "manual_review": None,
        "cognitive_stopping": None,
        "data_audit": None,
    }

    audit_path = outputs / "data_audit" / "audit_summary.json"
    if audit_path.exists():
        report["data_audit"] = read_json(audit_path)

    for model in ["SeekUI", "SeekUI_sft"]:
        pred_path = outputs / f"predictions_{model}_1362.json"
        eval_path = outputs / f"eval_{model}_1362.txt"
        image_cue_path = outputs / f"image_cue_predictions_{model}_1362.json"
        semantic_path = outputs / f"semantic_query_predictions_{model}_1362_v2.json"
        semantic_summary_path = outputs / f"semantic_query_predictions_{model}_1362_v2_summary.json"
        absent_path = outputs / f"present_absent_predictions_{model}.json"
        absent_eval_path = outputs / f"present_absent_predictions_{model}_status_eval.json"
        cognitive_stop_path = outputs / f"present_absent_predictions_{model}_cognitive_stop.json"
        cognitive_stop_eval_path = outputs / f"present_absent_predictions_{model}_cognitive_stop_status_eval.json"

        report["files"][f"{model}_predictions"] = str(pred_path) if pred_path.exists() else None
        report["files"][f"{model}_eval"] = str(eval_path) if eval_path.exists() else None
        report["files"][f"{model}_image_cue_predictions"] = str(image_cue_path) if image_cue_path.exists() else None
        report["files"][f"{model}_semantic_query_predictions"] = str(semantic_path) if semantic_path.exists() else None
        report["files"][f"{model}_present_absent_predictions"] = str(absent_path) if absent_path.exists() else None
        report["files"][f"{model}_cognitive_stop_predictions"] = (
            str(cognitive_stop_path) if cognitive_stop_path.exists() else None
        )

        health = prediction_health(pred_path)
        if health:
            report["prediction_health"][model] = health
        image_health = prediction_health(image_cue_path)
        if image_health:
            report["prediction_health"][f"{model}_image_cue"] = image_health
        semantic_health = prediction_health(semantic_path)
        if semantic_health:
            report["prediction_health"][f"{model}_semantic_query"] = semantic_health

        metrics = parse_eval_log(eval_path)
        if metrics:
            report["evaluation_metrics"][model] = metrics
        if absent_eval_path.exists():
            report["absent_status"][model] = read_json(absent_eval_path)
        if cognitive_stop_eval_path.exists():
            report["absent_status"][f"{model}_cognitive_stop"] = read_json(cognitive_stop_eval_path)
        if semantic_summary_path.exists():
            report.setdefault("semantic_query", {})[model] = read_json(semantic_summary_path)

    cognitive_path = outputs / "cognitive_stopping" / "cognitive_stopping_summary.json"
    if cognitive_path.exists():
        report["cognitive_stopping"] = read_json(cognitive_path)

    validation_path = outputs / "absent_validation.json"
    if validation_path.exists():
        report["absent_validation"] = read_json(validation_path)
    report["split_metrics"] = collect_split_metrics(outputs)

    image_cue_json = data_dir / "image_cue_1362.json"
    if image_cue_json.exists():
        report["files"]["image_cue_dataset"] = str(image_cue_json)
    mixed_json = data_dir / "present_absent_synthetic_2724.json"
    if mixed_json.exists():
        report["files"]["present_absent_dataset"] = str(mixed_json)
    absent_review = outputs / "review_cases" / "absent_label_review.csv"
    if absent_review.exists():
        report["files"]["absent_label_review"] = str(absent_review)
    semantic_review = outputs / "review_cases" / "semantic_query_review.csv"
    if semantic_review.exists():
        report["files"]["semantic_query_review"] = str(semantic_review)
    prediction_review = outputs / "review_cases" / "prediction_edge_cases_review.csv"
    if prediction_review.exists():
        report["files"]["prediction_edge_cases_review"] = str(prediction_review)
    review_manifest = outputs / "review_cases" / "review_artifacts_manifest.json"
    if review_manifest.exists():
        report["files"]["review_artifacts_manifest"] = str(review_manifest)
    manual_review_summary = outputs / "review_cases" / "manual_review_summary.json"
    report["manual_review"] = read_optional_json(manual_review_summary)
    if manual_review_summary.exists():
        report["files"]["manual_review_summary"] = str(manual_review_summary)
    followup_status = outputs / "followup_status.json"
    if followup_status.exists():
        report["followup_status"] = read_json(followup_status)
        report["files"]["followup_status"] = str(followup_status)

    lines = ["# SeekUI Research Output Summary", ""]
    lines.append(f"Work dir: `{work_dir}`")
    lines.append("")

    lines.append("## Data Audit")
    lines.append("")
    if report["data_audit"]:
        audit = report["data_audit"]
        lines.append(f"- Examples: {audit.get('num_examples')}")
        lines.append(f"- Unique images: {audit.get('unique_images')}")
        lines.append(f"- Unique targets: {audit.get('unique_targets')}")
        lines.append(f"- Target prefixes: {audit.get('target_prefix_counts')}")
        lines.append(f"- Missing images: {audit.get('missing_image_files')}")
    else:
        lines.append("Pending.")
    lines.append("")

    lines.append("## Follow-Up Status")
    lines.append("")
    if report.get("followup_status"):
        status = report["followup_status"]
        counts = status.get("counts", {})
        lines.append(f"- Done: {counts.get('done', 0)}")
        lines.append(f"- Pending: {counts.get('pending', 0)}")
        pending = [item for item in status.get("items", []) if item.get("state") == "pending"]
        if pending:
            lines.append("")
            lines.append("| ID | Task | Missing | Next command |")
            lines.append("|---|---|---:|---|")
            for item in pending[:10]:
                lines.append(
                    f"| {item.get('id')} | {item.get('title')} | {len(item.get('missing', []))} | "
                    f"`{item.get('command', '')}` |"
                )
    else:
        lines.append("Pending.")
    lines.append("")

    lines.append("## Prediction Health")
    lines.append("")
    if report["prediction_health"]:
        lines.append("| Output | N | Empty | Min Len | Avg Len | Max Len |")
        lines.append("|---|---:|---:|---:|---:|---:|")
        for name, health in report["prediction_health"].items():
            lines.append(
                f"| {name} | {health['num_examples']} | {health['empty_predictions']} | "
                f"{health['min_prediction_len']} | {health['avg_prediction_len']:.2f} | {health['max_prediction_len']} |"
            )
    else:
        lines.append("Pending.")
    lines.append("")

    write_metric_table(lines, "Overall Evaluation Metrics", report["evaluation_metrics"])

    lines.append("## Present/Absent Status")
    lines.append("")
    if report["absent_status"]:
        lines.append("| Model | N | Accuracy | Absent Precision | Absent Recall | Absent F1 |")
        lines.append("|---|---:|---:|---:|---:|---:|")
        for model, status in report["absent_status"].items():
            lines.append(
                f"| {model} | {status.get('num_examples', '')} | {status.get('accuracy', 0):.4f} | "
                f"{status.get('absent_precision', 0):.4f} | {status.get('absent_recall', 0):.4f} | "
                f"{status.get('absent_f1', 0):.4f} |"
            )
    else:
        lines.append("Pending.")
    lines.append("")

    lines.append("## Cognitive Stopping")
    lines.append("")
    if report["cognitive_stopping"]:
        best = report["cognitive_stopping"].get("best_by_absent_f1", {})
        lines.append(f"- Examples: {report['cognitive_stopping'].get('num_examples')}")
        lines.append(f"- Present: {report['cognitive_stopping'].get('num_present')}")
        lines.append(f"- Absent: {report['cognitive_stopping'].get('num_absent')}")
        lines.append(f"- Best threshold: {best.get('threshold')}")
        lines.append(f"- Absent F1: {best.get('absent_f1', 0):.4f}")
    else:
        lines.append("Pending.")
    lines.append("")

    lines.append("## Semantic Query Robustness")
    lines.append("")
    if report.get("semantic_query"):
        for model, summary in report["semantic_query"].items():
            lines.append(f"### {model}")
            lines.append("")
            lines.append("| Query Type | N | Empty | Avg Len | Predicted Absent Rate |")
            lines.append("|---|---:|---:|---:|---:|")
            for query_type, row in sorted(summary.items()):
                lines.append(
                    f"| {query_type} | {row.get('num_examples', '')} | {row.get('empty_predictions', '')} | "
                    f"{row.get('avg_prediction_len', 0):.2f} | {row.get('predicted_absent_rate', 0):.4f} |"
                )
            lines.append("")
    else:
        lines.append("Pending.")
        lines.append("")

    lines.append("## Manual Review")
    lines.append("")
    if report["manual_review"]:
        review = report["manual_review"]
        lines.append(f"- Rows: {review.get('num_rows')}")
        lines.append(f"- Review types: {review.get('review_type_counts')}")
        for field in ["review_target_visible", "review_query_valid", "review_prediction_reasonable"]:
            field_summary = review.get("fields", {}).get(field, {})
            lines.append(
                f"- {field}: annotated={field_summary.get('annotated', 0)}, "
                f"yes_rate={field_summary.get('yes_rate_annotated', 0):.4f}"
            )
    else:
        lines.append("Pending.")
    lines.append("")

    lines.append("## Split Evaluation Metrics")
    lines.append("")
    if report["split_metrics"]:
        preferred = ["sm_score_wo_d", "mm_score_Pos", "sed_score", "stde_score", "ss_score", "AUC", "NSS", "sAUC"]
        lines.append("| Group | Field | Value | N | " + " | ".join(preferred) + " |")
        lines.append("|---|---|---|---:|" + "|".join(["---:"] * len(preferred)) + "|")
        for row in report["split_metrics"]:
            metrics = row["metrics"]
            values = [f"{metrics.get(metric, ''):.4f}" if metric in metrics else "" for metric in preferred]
            lines.append(
                f"| {row['group']} | {row.get('field', '')} | {row.get('value', '')} | {row.get('count', '')} | "
                + " | ".join(values)
                + " |"
            )
    else:
        lines.append("Pending.")
    lines.append("")

    lines.append("## Files")
    lines.append("")
    for key, value in sorted(report["files"].items()):
        lines.append(f"- {key}: `{value or 'pending'}`")
    lines.append("")

    output = Path(args.output) if args.output else outputs / "research_summary.md"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines), encoding="utf-8")

    json_output = output.with_suffix(".json")
    with open(json_output, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    tables_dir = Path(args.tables_dir) if args.tables_dir else output.with_suffix("").parent / f"{output.with_suffix('').name}_tables"
    export_tables(report, tables_dir)

    print(f"Wrote Markdown summary: {output}")
    print(f"Wrote JSON summary    : {json_output}")
    print(f"Wrote CSV tables      : {tables_dir}")


if __name__ == "__main__":
    main()
