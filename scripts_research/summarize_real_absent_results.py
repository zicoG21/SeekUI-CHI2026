#!/usr/bin/env python
import argparse
import csv
import json
import re
from pathlib import Path


STATUS_RE = re.compile(
    r"^(?P<family>vlm_presence|vlm_evidence)_predictions_(?P<label>.+)_status_eval\.json$"
)


def read_json(path):
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "model",
        "family",
        "variant",
        "label",
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


def model_and_variant(label):
    if label.startswith("SeekUI_sft_"):
        return "SeekUI_sft", label[len("SeekUI_sft_"):]
    if label.startswith("SeekUI_"):
        return "SeekUI", label[len("SeekUI_"):]
    return "", label


def row_from_eval(path):
    match = STATUS_RE.match(path.name)
    if not match or "real_absent" not in match.group("label"):
        return None
    metrics = read_json(path)
    if not metrics:
        return None
    confusion = metrics.get("confusion", {})
    label = match.group("label")
    model, variant = model_and_variant(label)
    return {
        "model": model,
        "family": match.group("family"),
        "variant": variant,
        "label": label,
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


def sort_rows(rows):
    family_order = {"vlm_presence": 0, "vlm_evidence": 1}
    return sorted(
        rows,
        key=lambda row: (
            row.get("model", ""),
            family_order.get(row.get("family", ""), 99),
            -as_float(row.get("absent_f1")),
            row.get("variant", ""),
        ),
    )


def write_md(path, rows, prep_summary):
    lines = [
        "# Realistic Absent Validation Results",
        "",
    ]
    if prep_summary:
        lines.extend([
            "## Dataset",
            "",
            f"- Input rows: {prep_summary.get('input_rows', '')}",
            f"- Included rows: {prep_summary.get('included_rows', '')}",
            f"- Present rows: {prep_summary.get('present_rows', '')}",
            f"- Absent rows: {prep_summary.get('absent_rows', '')}",
            "",
        ])
    else:
        lines.extend([
            "## Dataset",
            "",
            "Pending: missing prep summary JSON/MD. If the eval JSON exists, this table can still be used.",
            "",
        ])

    lines.extend([
        "## Metrics",
        "",
    ])
    if not rows:
        lines.append("Pending: no `*real_absent*_status_eval.json` files found.")
    else:
        lines.extend([
            "| Model | Family | Variant | N | Acc | Precision | Recall | F1 | Present->Absent | Absent->Present |",
            "|---|---|---|---:|---:|---:|---:|---:|---:|---:|",
        ])
        for row in rows:
            lines.append(
                f"| {row.get('model', '')} | {row.get('family', '')} | {row.get('variant', '')} | "
                f"{row.get('num_examples', '')} | {fmt(row.get('accuracy'))} | "
                f"{fmt(row.get('absent_precision'))} | {fmt(row.get('absent_recall'))} | "
                f"{fmt(row.get('absent_f1'))} | {row.get('present_absent', '')} | "
                f"{row.get('absent_present', '')} |"
            )
    lines.extend([
        "",
        "## Notes",
        "",
        "- This is a small manually reviewed external-validity check, not a replacement for the full synthetic benchmark.",
        "- Presence-only VLM rows do not use scanpath or OCR evidence.",
        "- Evidence-aware rows should be interpreted carefully unless their input JSON contains real scanpath/OCR evidence for this validation set.",
        "",
    ])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_prep_md(path):
    if not path.exists():
        return {}
    summary = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        for key, label in [
            ("input_rows", "- Input rows:"),
            ("included_rows", "- Included rows:"),
            ("present_rows", "- Present rows:"),
            ("absent_rows", "- Absent rows:"),
        ]:
            if line.startswith(label):
                summary[key] = line.split(":", 1)[1].strip()
    return summary


def main():
    parser = argparse.ArgumentParser(description="Summarize VLM results on the small realistic absent validation set.")
    parser.add_argument("--work-dir", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--output-md", required=True)
    args = parser.parse_args()

    work_dir = Path(args.work_dir)
    outputs = work_dir / "outputs"
    rows = []
    for pattern in [
        "vlm_presence_predictions_*real_absent*_status_eval.json",
        "vlm_evidence_predictions_*real_absent*_status_eval.json",
    ]:
        for path in outputs.glob(pattern):
            row = row_from_eval(path)
            if row:
                rows.append(row)
    rows = sort_rows(rows)
    prep_summary = parse_prep_md(outputs / "real_absent_validation" / "real_absent_validation_prep.md")

    payload = {
        "work_dir": str(work_dir),
        "prep_summary": prep_summary,
        "rows": rows,
    }
    write_json(Path(args.output_json), payload)
    write_csv(Path(args.output_csv), rows)
    write_md(Path(args.output_md), rows, prep_summary)
    print(json.dumps({
        "rows": len(rows),
        "output_md": args.output_md,
        "output_csv": args.output_csv,
    }, indent=2))


if __name__ == "__main__":
    main()
