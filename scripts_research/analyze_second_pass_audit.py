#!/usr/bin/env python
import argparse
import csv
import json
from collections import Counter
from pathlib import Path


ABSENT_STATUSES = {"absent", "not_found", "not found", "no object", "no target", "not present"}
PRESENT_STATUSES = {"present", "found", "yes", "visible"}

METHOD_COLUMNS = [
    ("prompt", "prompt_status"),
    ("combined", "combined_status"),
    ("ocr_aware_vlm", "ocr_aware_status"),
    ("evidence_aware_vlm", "evidence_status"),
]


def read_csv(path):
    with open(path, "r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path, rows, fieldnames=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = []
        for row in rows:
            for key in row:
                if key not in fieldnames:
                    fieldnames.append(key)
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def normalize_status(value, default="present"):
    text = str(value or default).strip().casefold()
    if text in ABSENT_STATUSES:
        return "absent"
    if text in PRESENT_STATUSES:
        return "present"
    return default


def safe_div(num, den):
    return num / den if den else 0.0


def metrics_from_pairs(pairs):
    confusion = Counter(pairs)
    absent_absent = confusion[("absent", "absent")]
    absent_present = confusion[("absent", "present")]
    present_absent = confusion[("present", "absent")]
    present_present = confusion[("present", "present")]
    total = absent_absent + absent_present + present_absent + present_present
    precision = safe_div(absent_absent, absent_absent + present_absent)
    recall = safe_div(absent_absent, absent_absent + absent_present)
    f1 = safe_div(2 * precision * recall, precision + recall)
    return {
        "num_examples": total,
        "accuracy": safe_div(absent_absent + present_present, total),
        "absent_precision": precision,
        "absent_recall": recall,
        "absent_f1": f1,
        "present_absent": present_absent,
        "absent_present": absent_present,
        "present_present": present_present,
        "absent_absent": absent_absent,
    }


def evaluate(rows, gold_column, exclude_value=None):
    output = []
    included = [
        row for row in rows
        if not exclude_value or row.get(gold_column, "").strip().casefold() != exclude_value
    ]
    for method, pred_column in METHOD_COLUMNS:
        pairs = []
        missing = 0
        for row in included:
            gold = normalize_status(row.get(gold_column), default="present")
            pred_raw = row.get(pred_column, "")
            if not pred_raw:
                missing += 1
                continue
            pred = normalize_status(pred_raw, default="present")
            pairs.append((gold, pred))
        output.append({
            "label_set": gold_column,
            "method": method,
            "candidate_rows": len(included),
            "missing_predictions": missing,
            **metrics_from_pairs(pairs),
        })
    return output


def fmt(value):
    try:
        return f"{float(value):.4f}"
    except (TypeError, ValueError):
        return ""


def add_deltas(rows, baseline_method="prompt"):
    by_label = {}
    for row in rows:
        by_label.setdefault(row["label_set"], {})[row["method"]] = row
    for row in rows:
        baseline = by_label.get(row["label_set"], {}).get(baseline_method, {})
        if row["method"] == baseline_method or not baseline:
            row["delta_absent_f1"] = ""
            row["delta_accuracy"] = ""
        else:
            row["delta_absent_f1"] = row["absent_f1"] - baseline.get("absent_f1", 0.0)
            row["delta_accuracy"] = row["accuracy"] - baseline.get("accuracy", 0.0)
    return rows


def summarize_labels(rows):
    changed = [
        row for row in rows
        if row.get("audit_gold_status", "") != row.get("gold_status", "")
    ]
    return {
        "num_rows": len(rows),
        "original_gold_counts": dict(Counter(row.get("gold_status", "") for row in rows)),
        "audit_gold_counts": dict(Counter(row.get("audit_gold_status", "") for row in rows)),
        "audit_ambiguity_counts": dict(Counter(row.get("audit_ambiguity_level", "") for row in rows)),
        "changed_or_excluded_rows": len(changed),
        "changed_or_excluded": [
            {
                "audit_id": row.get("audit_id", ""),
                "case_source": row.get("case_source", ""),
                "query_text": row.get("query_text", ""),
                "original_gold": row.get("gold_status", ""),
                "audit_gold": row.get("audit_gold_status", ""),
                "audit_ambiguity": row.get("audit_ambiguity_level", ""),
                "audit_notes": row.get("audit_notes", ""),
            }
            for row in changed
        ],
    }


def write_markdown(path, payload):
    rows = payload["metrics"]
    lines = [
        "# Second-Pass Audit Robustness",
        "",
        f"- Input CSV: `{payload['input_csv']}`",
        f"- Reviewed rows: {payload['label_summary']['num_rows']}",
        f"- Corrected/excluded rows: {payload['label_summary']['changed_or_excluded_rows']}",
        "",
        "The audit-label evaluation removes rows whose audited gold status is `exclude`.",
        "",
        "## Label Summary",
        "",
        "| Field | Counts |",
        "|---|---|",
        f"| Original gold | `{payload['label_summary']['original_gold_counts']}` |",
        f"| Audit gold | `{payload['label_summary']['audit_gold_counts']}` |",
        f"| Audit ambiguity | `{payload['label_summary']['audit_ambiguity_counts']}` |",
        "",
        "## Robustness Metrics",
        "",
        "| Label Set | Method | N | Candidate Rows | Acc | Precision | Recall | F1 | Delta F1 | Delta Acc | P->A | A->P | Missing |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['label_set']} | {row['method']} | {row['num_examples']} | "
            f"{row['candidate_rows']} | "
            f"{fmt(row['accuracy'])} | {fmt(row['absent_precision'])} | {fmt(row['absent_recall'])} | "
            f"{fmt(row['absent_f1'])} | {fmt(row.get('delta_absent_f1'))} | "
            f"{fmt(row.get('delta_accuracy'))} | {row['present_absent']} | {row['absent_present']} | "
            f"{row['missing_predictions']} |"
        )
    lines.extend([
        "",
        "## Corrected Or Excluded Rows",
        "",
        "| Audit ID | Source | Query | Original | Audit | Ambiguity | Notes |",
        "|---:|---|---|---|---|---|---|",
    ])
    for row in payload["label_summary"]["changed_or_excluded"]:
        lines.append(
            f"| {row['audit_id']} | {row['case_source']} | {row['query_text']} | "
            f"{row['original_gold']} | {row['audit_gold']} | {row['audit_ambiguity']} | "
            f"{row['audit_notes']} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Analyze robustness of real-absent second-pass audit labels.")
    parser.add_argument("--audit-csv", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--output-md", required=True)
    args = parser.parse_args()

    rows = read_csv(Path(args.audit_csv))
    metrics = []
    metrics.extend(evaluate(rows, "gold_status"))
    metrics.extend(evaluate(rows, "audit_gold_status", exclude_value="exclude"))
    metrics = add_deltas(metrics)
    payload = {
        "input_csv": args.audit_csv,
        "label_summary": summarize_labels(rows),
        "metrics": metrics,
    }
    write_json(Path(args.output_json), payload)
    write_csv(Path(args.output_csv), metrics)
    write_markdown(Path(args.output_md), payload)
    print(json.dumps({
        "rows": len(rows),
        "changed_or_excluded": payload["label_summary"]["changed_or_excluded_rows"],
        "output_md": args.output_md,
    }, indent=2))


if __name__ == "__main__":
    main()
