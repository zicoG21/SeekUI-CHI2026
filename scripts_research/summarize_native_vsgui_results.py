#!/usr/bin/env python
import argparse
import csv
import json
import re
from pathlib import Path


STATUS_PATTERNS = [
    re.compile(r"^present_absent_predictions_(?P<label>.+native_.+)_status_eval\.json$"),
    re.compile(r"^vlm_presence_predictions_(?P<label>.+native_.+)_status_eval\.json$"),
    re.compile(r"^vlm_evidence_predictions_(?P<label>.+native_.+)_status_eval\.json$"),
]


def read_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "label",
        "model",
        "family",
        "variant",
        "split",
        "num_examples",
        "accuracy",
        "absent_precision",
        "absent_recall",
        "absent_f1",
        "present_absent",
        "absent_present",
        "source",
    ]
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def model_from_label(label):
    if label.startswith("SeekUI_sft_"):
        return "SeekUI_sft", label[len("SeekUI_sft_"):]
    if label.startswith("SeekUI_"):
        return "SeekUI", label[len("SeekUI_"):]
    return "", label


def split_from_variant(variant):
    for split in [
        "native_text_color_balanced",
        "native_text_balanced",
        "native_image_balanced",
        "native_all_cues_balanced",
    ]:
        if split in variant:
            return split
    return "native"


def family_from_path_and_variant(path, variant):
    name = path.name
    if name.startswith("vlm_presence_predictions_"):
        return "vlm_presence"
    if name.startswith("vlm_evidence_predictions_"):
        return "vlm_evidence"
    if "context_crop_ocr_vlm" in variant:
        return "context_crop_vlm"
    if "crop_ocr_vlm" in variant or "candidate_crop" in variant:
        return "crop_vlm"
    if "status_ensemble" in variant:
        return "ensemble"
    if "native_supervised_calibrated" in variant:
        return "supervised_calibrated"
    if "native_task_routed" in variant:
        return "task_routed"
    if "native_bucket_router" in variant:
        return "bucket_router"
    if "color_aware" in variant:
        return "color_aware"
    if "combined_" in variant:
        return "combined"
    return "seekui_prompt"


def row_from_path(path):
    if "_filtered_status_eval" in path.name:
        return None
    label = None
    for pattern in STATUS_PATTERNS:
        match = pattern.match(path.name)
        if match:
            label = match.group("label")
            break
    if label is None:
        return None
    metrics = read_json(path)
    confusion = metrics.get("confusion", {})
    model, variant = model_from_label(label)
    return {
        "label": label,
        "model": model,
        "family": family_from_path_and_variant(path, variant),
        "variant": variant,
        "split": split_from_variant(variant),
        "num_examples": metrics.get("num_examples", ""),
        "accuracy": metrics.get("accuracy", ""),
        "absent_precision": metrics.get("absent_precision", ""),
        "absent_recall": metrics.get("absent_recall", ""),
        "absent_f1": metrics.get("absent_f1", ""),
        "present_absent": confusion.get("present->absent", ""),
        "absent_present": confusion.get("absent->present", ""),
        "source": str(path),
    }


def as_float(value, default=-1.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def fmt(value):
    try:
        return f"{float(value):.4f}"
    except (TypeError, ValueError):
        return ""


def write_md(path, rows):
    lines = [
        "# Native VSGUI10K Results",
        "",
        "Rows are collected from `*native*_status_eval.json` files.",
        "",
        "| Split | Model | Family | Variant | N | Acc | Precision | Recall | F1 | P->A | A->P |",
        "|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['split']} | {row['model']} | {row['family']} | {row['variant']} | "
            f"{row['num_examples']} | {fmt(row['accuracy'])} | {fmt(row['absent_precision'])} | "
            f"{fmt(row['absent_recall'])} | {fmt(row['absent_f1'])} | "
            f"{row['present_absent']} | {row['absent_present']} |"
        )
    lines.extend([
        "",
        "Notes:",
        "",
        "- `native_text_balanced` is the closest native counterpart to the current text-target absent setting.",
        "- `native_text_color_balanced` adds target color as part of the query cue.",
        "- `native_image_balanced` requires image-cue aware prompting before it should be treated as a main result.",
        "",
    ])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Summarize native VSGUI10K status results.")
    parser.add_argument("--work-dir", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--output-md", required=True)
    parser.add_argument("--label-contains", default="native")
    args = parser.parse_args()

    outputs = Path(args.work_dir) / "outputs"
    rows = []
    for pattern in [
        "present_absent_predictions_*native*_status_eval.json",
        "vlm_presence_predictions_*native*_status_eval.json",
        "vlm_evidence_predictions_*native*_status_eval.json",
    ]:
        for path in sorted(outputs.glob(pattern)):
            row = row_from_path(path)
            if row and args.label_contains in row["label"]:
                rows.append(row)
    rows.sort(
        key=lambda row: (
            row["split"],
            row["model"],
            {
                "seekui_prompt": 0,
                "combined": 1,
                "color_aware": 2,
                "ensemble": 3,
                "supervised_calibrated": 4,
                "task_routed": 5,
                "bucket_router": 6,
                "vlm_presence": 7,
                "vlm_evidence": 8,
            }.get(row["family"], 9),
            -as_float(row["absent_f1"]),
        )
    )
    write_json(Path(args.output_json), {"rows": rows})
    write_csv(Path(args.output_csv), rows)
    write_md(Path(args.output_md), rows)
    print(json.dumps({"rows": len(rows), "output_md": args.output_md}, indent=2))


if __name__ == "__main__":
    main()
