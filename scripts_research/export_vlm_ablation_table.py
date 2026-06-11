#!/usr/bin/env python
import argparse
import csv
import json
import re
from pathlib import Path


def read_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = [
        "rank_absent_f1",
        "model",
        "family",
        "variant",
        "num_examples",
        "accuracy",
        "absent_precision",
        "absent_recall",
        "absent_f1",
        "present_absent",
        "absent_present",
        "source_json",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def infer_label(path, outputs_dir):
    name = path.name
    patterns = [
        (r"^present_absent_predictions_(?P<model>SeekUI(?:_sft)?)_status_eval\.json$", "seekui_prompt", "prompt_only"),
        (
            r"^present_absent_predictions_(?P<model>SeekUI(?:_sft)?)_(?P<variant>combined_.*)_status_eval\.json$",
            "combined",
            None,
        ),
        (
            r"^present_absent_predictions_(?P<model>SeekUI(?:_sft)?)_(?P<variant>annotation_free_combined_.*)_status_eval\.json$",
            "annotation_free_combined",
            None,
        ),
        (
            r"^vlm_presence_predictions_(?P<model>SeekUI(?:_sft)?)_(?P<variant>vlm_presence.*)_status_eval\.json$",
            "vlm_presence",
            None,
        ),
        (
            r"^vlm_evidence_predictions_(?P<model>SeekUI(?:_sft)?)_(?P<variant>vlm_evidence.*)_status_eval\.json$",
            "vlm_evidence",
            None,
        ),
    ]
    for pattern, family, fixed_variant in patterns:
        match = re.match(pattern, name)
        if match:
            model = match.group("model")
            variant = fixed_variant if fixed_variant else match.group("variant")
            return model, family, variant
    rel = path.relative_to(outputs_dir) if path.is_relative_to(outputs_dir) else path
    return "unknown", "unknown", str(rel)


def row_from_eval(path, outputs_dir):
    metrics = read_json(path)
    confusion = metrics.get("confusion", {})
    model, family, variant = infer_label(path, outputs_dir)
    return {
        "rank_absent_f1": "",
        "model": model,
        "family": family,
        "variant": variant,
        "num_examples": metrics.get("num_examples", ""),
        "accuracy": metrics.get("accuracy", 0.0),
        "absent_precision": metrics.get("absent_precision", 0.0),
        "absent_recall": metrics.get("absent_recall", 0.0),
        "absent_f1": metrics.get("absent_f1", 0.0),
        "present_absent": confusion.get("present->absent", ""),
        "absent_present": confusion.get("absent->present", ""),
        "source_json": str(path),
    }


def fmt(value):
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def write_md(path, rows):
    lines = [
        "# VLM And Evidence Ablation Table",
        "",
        "Rows are sorted by absent F1. Pilot outputs such as `_n200` are excluded unless `--include-pilots` is set.",
        "",
        "| Rank | Model | Family | Variant | N | Acc | Precision | Recall | F1 | Present->Absent | Absent->Present |",
        "|---:|---|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['rank_absent_f1']} | {row['model']} | {row['family']} | {row['variant']} | "
            f"{row['num_examples']} | {fmt(row['accuracy'])} | {fmt(row['absent_precision'])} | "
            f"{fmt(row['absent_recall'])} | {fmt(row['absent_f1'])} | "
            f"{row['present_absent']} | {row['absent_present']} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def collect_paths(outputs_dir, include_pilots):
    patterns = [
        "present_absent_predictions_SeekUI_status_eval.json",
        "present_absent_predictions_SeekUI_sft_status_eval.json",
        "present_absent_predictions_SeekUI_combined_*_status_eval.json",
        "present_absent_predictions_SeekUI_sft_combined_*_status_eval.json",
        "present_absent_predictions_SeekUI_annotation_free_combined_*_status_eval.json",
        "present_absent_predictions_SeekUI_sft_annotation_free_combined_*_status_eval.json",
        "vlm_presence_predictions_SeekUI_vlm_presence*_status_eval.json",
        "vlm_presence_predictions_SeekUI_sft_vlm_presence*_status_eval.json",
        "vlm_evidence_predictions_SeekUI_vlm_evidence*_status_eval.json",
        "vlm_evidence_predictions_SeekUI_sft_vlm_evidence*_status_eval.json",
    ]
    paths = []
    for pattern in patterns:
        for path in sorted(outputs_dir.glob(pattern)):
            if path.name.endswith("_filtered_status_eval.json"):
                continue
            if not include_pilots and re.search(r"_n\d+_status_eval\.json$", path.name):
                continue
            paths.append(path)
    return sorted(set(paths))


def main():
    parser = argparse.ArgumentParser(description="Export a compact VLM/presence/evidence ablation table.")
    parser.add_argument("--outputs-dir", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--output-md", required=True)
    parser.add_argument("--include-pilots", action="store_true")
    args = parser.parse_args()

    outputs_dir = Path(args.outputs_dir)
    rows = [row_from_eval(path, outputs_dir) for path in collect_paths(outputs_dir, args.include_pilots)]
    rows.sort(key=lambda row: (float(row["absent_f1"]), float(row["accuracy"])), reverse=True)
    for idx, row in enumerate(rows, start=1):
        row["rank_absent_f1"] = idx

    write_csv(Path(args.output_csv), rows)
    write_md(Path(args.output_md), rows)
    print(json.dumps({
        "rows": len(rows),
        "output_csv": args.output_csv,
        "output_md": args.output_md,
    }, indent=2))


if __name__ == "__main__":
    main()
