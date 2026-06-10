#!/usr/bin/env python
import argparse
import csv
import json
from pathlib import Path


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_csv(path, rows, fieldnames=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = list(rows[0].keys()) if rows else []
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def find_metric(summary, split, variant_prefix):
    for row in summary.get("metric_rows", []):
        if row.get("split") == split and str(row.get("variant", "")).startswith(variant_prefix):
            return row
    raise ValueError(f"Missing metric row split={split} variant={variant_prefix} for {summary.get('name')}")


def ci_text(ci):
    return f"[{ci['ci_low']:.4f}, {ci['ci_high']:.4f}]"


def rows_from_devtest(path, preferred=False):
    report = load_json(path)
    rows = []
    for summary in report.get("summaries", []):
        prompt = find_metric(summary, "test", "prompt")
        combined = find_metric(summary, "test", "combined")
        ci = summary.get("bootstrap_ci", {})
        delta_f1 = ci.get("delta_absent_f1", {})
        delta_acc = ci.get("delta_accuracy", {})
        rows.append({
            "model": summary["name"],
            "split": summary.get("split_by", report.get("split_by", "")),
            "preferred_headline": int(preferred),
            "prompt_absent_f1": prompt["absent_f1"],
            "combined_absent_f1": combined["absent_f1"],
            "delta_absent_f1_mean": delta_f1.get("mean", combined["absent_f1"] - prompt["absent_f1"]),
            "delta_absent_f1_ci": ci_text(delta_f1) if delta_f1 else "",
            "prompt_accuracy": prompt["accuracy"],
            "combined_accuracy": combined["accuracy"],
            "delta_accuracy_mean": delta_acc.get("mean", combined["accuracy"] - prompt["accuracy"]),
            "delta_accuracy_ci": ci_text(delta_acc) if delta_acc else "",
            "cognitive_threshold": combined.get("cognitive_threshold", ""),
            "ocr_threshold": combined.get("ocr_threshold", ""),
            "prompt_present_absent": prompt["present_absent"],
            "prompt_absent_present": prompt["absent_present"],
            "combined_present_absent": combined["present_absent"],
            "combined_absent_present": combined["absent_present"],
            "source_json": str(path),
        })
    return rows


def fmt(value):
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def write_md(path, rows):
    lines = [
        "# Main Result Table",
        "",
        "Combined AND uses thresholds selected on the dev split and is evaluated on held-out test examples.",
        "Image split is the cleaner headline because the sanity audit found heavy image leakage in the random split.",
        "",
        "| Model | Split | Prompt F1 | Combined F1 | Delta F1 | Delta F1 95% CI | Prompt Acc | Combined Acc | Delta Acc | Delta Acc 95% CI | Cog Thresh | OCR Thresh |",
        "|---|---|---:|---:|---:|---|---:|---:|---:|---|---:|---:|",
    ]
    for row in sorted(rows, key=lambda r: (not r["preferred_headline"], r["model"], r["split"])):
        split = row["split"]
        if row["preferred_headline"]:
            split = f"{split} *"
        lines.append(
            f"| {row['model']} | {split} | {row['prompt_absent_f1']:.4f} | "
            f"{row['combined_absent_f1']:.4f} | {row['delta_absent_f1_mean']:.4f} | "
            f"{row['delta_absent_f1_ci']} | {row['prompt_accuracy']:.4f} | "
            f"{row['combined_accuracy']:.4f} | {row['delta_accuracy_mean']:.4f} | "
            f"{row['delta_accuracy_ci']} | {row['cognitive_threshold']} | {row['ocr_threshold']} |"
        )
    lines.extend([
        "",
        "`*` Preferred headline split.",
        "",
        "## Error Count Shift",
        "",
        "| Model | Split | Prompt Present->Absent | Prompt Absent->Present | Combined Present->Absent | Combined Absent->Present |",
        "|---|---|---:|---:|---:|---:|",
    ])
    for row in sorted(rows, key=lambda r: (not r["preferred_headline"], r["model"], r["split"])):
        split = row["split"]
        if row["preferred_headline"]:
            split = f"{split} *"
        lines.append(
            f"| {row['model']} | {split} | {row['prompt_present_absent']} | "
            f"{row['prompt_absent_present']} | {row['combined_present_absent']} | "
            f"{row['combined_absent_present']} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Export paper-ready main result table from combined dev/test JSON outputs.")
    parser.add_argument("--random-json", required=True)
    parser.add_argument("--image-json", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--output-md", required=True)
    args = parser.parse_args()

    rows = []
    rows.extend(rows_from_devtest(Path(args.random_json), preferred=False))
    rows.extend(rows_from_devtest(Path(args.image_json), preferred=True))
    write_csv(Path(args.output_csv), rows)
    write_md(Path(args.output_md), rows)
    print(json.dumps({
        "rows": len(rows),
        "output_csv": args.output_csv,
        "output_md": args.output_md,
    }, indent=2))


if __name__ == "__main__":
    main()
