#!/usr/bin/env python
import argparse
import csv
import json
from pathlib import Path


KEY_VARIANTS = [
    ("SeekUI", "prompt_only"),
    ("SeekUI", "cognitive_stop_present_only"),
    ("SeekUI", "combined_and_present_only_best_f1"),
    ("SeekUI", "annotation_free_combined_and_present_only_best_f1"),
    ("SeekUI", "vlm_presence"),
    ("SeekUI", "vlm_evidence_evidence_aware"),
    ("SeekUI_sft", "prompt_only"),
    ("SeekUI_sft", "combined_and_present_only_best_f1"),
    ("SeekUI_sft", "annotation_free_combined_and_present_only_best_f1"),
    ("SeekUI_sft", "vlm_evidence_evidence_aware"),
]


def read_csv(path):
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def as_float(value, default=None):
    if value in {"", None}:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def fmt(value):
    number = as_float(value)
    return "" if number is None else f"{number:.4f}"


def row_index(rows):
    return {(row.get("model", ""), row.get("variant", "")): row for row in rows}


def delta(row, baseline, metric):
    value = as_float(row.get(metric), 0.0)
    base = as_float(baseline.get(metric), 0.0)
    return value - base


def select_rows(rows):
    indexed = row_index(rows)
    return [indexed[key] for key in KEY_VARIANTS if key in indexed]


def best_practical(rows):
    practical = [
        row for row in rows
        if row.get("variant") in {
            "cognitive_stop_present_only",
            "combined_and_present_only_best_f1",
            "annotation_free_combined_and_present_only_best_f1",
            "vlm_presence",
            "vlm_evidence_evidence_aware",
        }
    ]
    practical.sort(key=lambda row: (as_float(row.get("absent_f1"), -1), as_float(row.get("accuracy"), -1)), reverse=True)
    return practical[:5]


def real_absent_key_rows(rows):
    wanted = {
        ("SeekUI", "seekui_prompt", "prompt_only_real_absent"),
        ("SeekUI", "combined", "combined_and_present_only_best_f1"),
        ("SeekUI", "vlm_presence", "vlm_presence_real_absent_conservative"),
        ("SeekUI", "vlm_presence", "vlm_presence_real_absent_ocr_aware"),
    }
    return [
        row for row in rows
        if (row.get("model"), row.get("family"), row.get("variant")) in wanted
    ]


def table_status(rows):
    lines = [
        "| Model | Variant | Acc | Precision | Recall | F1 | P->A | A->P |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row.get('model', '')} | {row.get('variant', '')} | {fmt(row.get('accuracy'))} | "
            f"{fmt(row.get('absent_precision'))} | {fmt(row.get('absent_recall'))} | "
            f"{fmt(row.get('absent_f1'))} | {row.get('present_to_absent', '')} | "
            f"{row.get('absent_to_present', '')} |"
        )
    return lines


def table_real_absent(rows):
    if not rows:
        return ["Pending: no realistic absent validation results found."]
    lines = [
        "| Model | Family | Variant | N | Acc | Precision | Recall | F1 | P->A | A->P |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row.get('model', '')} | {row.get('family', '')} | {row.get('variant', '')} | "
            f"{row.get('num_examples', '')} | {fmt(row.get('accuracy'))} | "
            f"{fmt(row.get('absent_precision'))} | {fmt(row.get('absent_recall'))} | "
            f"{fmt(row.get('absent_f1'))} | {row.get('present_absent', '')} | {row.get('absent_present', '')} |"
        )
    return lines


def write_md(path, summary):
    lines = [
        "# Current SeekUI Follow-Up Findings",
        "",
        "## Core Claims",
        "",
    ]
    for claim in summary["claims"]:
        lines.append(f"- {claim}")
    lines.extend([
        "",
        "## Key Synthetic Benchmark Results",
        "",
        *table_status(summary["selected_rows"]),
        "",
        "## Top Practical Methods",
        "",
        *table_status(summary["top_practical_rows"]),
        "",
        "## Realistic Absent Validation",
        "",
        *table_real_absent(summary["real_absent_rows"]),
        "",
        "## Interpretation",
        "",
        "- Annotation-backed candidate inventories remain diagnostic/upper-bound evidence, not a deployable assumption.",
        "- Annotation-free OCR candidates recover part of the gain, supporting deployability, but they underperform stronger UI/VLM evidence.",
        "- Evidence-aware VLM gives the strongest practical synthetic result, while combined AND remains the most transparent verifier.",
        "- The 100-row realistic validation is an external-validity smoke test; expanding it is the next data-facing priority.",
        "",
    ])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Export a compact current-findings memo from generated result tables.")
    parser.add_argument("--work-dir", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-md", required=True)
    args = parser.parse_args()

    work_dir = Path(args.work_dir)
    tables = work_dir / "outputs" / "research_summary_tables"
    real_dir = work_dir / "outputs" / "real_absent_validation"
    absent_rows = read_csv(tables / "absent_status_core.csv")
    real_rows = read_csv(real_dir / "real_absent_results.csv")
    indexed = row_index(absent_rows)
    seekui_prompt = indexed.get(("SeekUI", "prompt_only"), {})
    seekui_combined = indexed.get(("SeekUI", "combined_and_present_only_best_f1"), {})
    seekui_annotation_free = indexed.get(("SeekUI", "annotation_free_combined_and_present_only_best_f1"), {})
    seekui_evidence = indexed.get(("SeekUI", "vlm_evidence_evidence_aware"), {})

    claims = []
    if seekui_prompt and seekui_combined:
        claims.append(
            "Combined AND improves SeekUI absent F1 from "
            f"{fmt(seekui_prompt.get('absent_f1'))} to {fmt(seekui_combined.get('absent_f1'))} "
            f"(delta {delta(seekui_combined, seekui_prompt, 'absent_f1'):+.4f})."
        )
    if seekui_prompt and seekui_annotation_free:
        claims.append(
            "Annotation-free OCR candidate inventory still improves SeekUI absent F1 to "
            f"{fmt(seekui_annotation_free.get('absent_f1'))}, showing the effect is not only an annotation-candidate artifact."
        )
    if seekui_prompt and seekui_evidence:
        claims.append(
            "Evidence-aware VLM is the strongest practical synthetic verifier: absent F1 "
            f"{fmt(seekui_evidence.get('absent_f1'))}, delta "
            f"{delta(seekui_evidence, seekui_prompt, 'absent_f1'):+.4f} vs prompt-only."
        )
    real_selected = real_absent_key_rows(real_rows)
    real_index = {
        (row.get("model"), row.get("family"), row.get("variant")): row
        for row in real_selected
    }
    real_prompt = real_index.get(("SeekUI", "seekui_prompt", "prompt_only_real_absent"), {})
    real_combined = real_index.get(("SeekUI", "combined", "combined_and_present_only_best_f1"), {})
    if real_prompt and real_combined:
        claims.append(
            "On the 100-row realistic absent validation set, combined best-F1 improves F1 from "
            f"{fmt(real_prompt.get('absent_f1'))} to {fmt(real_combined.get('absent_f1'))}."
        )

    summary = {
        "work_dir": str(work_dir),
        "claims": claims,
        "selected_rows": select_rows(absent_rows),
        "top_practical_rows": best_practical(absent_rows),
        "real_absent_rows": real_selected,
    }
    write_json(Path(args.output_json), summary)
    write_md(Path(args.output_md), summary)
    print(json.dumps({
        "output_json": args.output_json,
        "output_md": args.output_md,
        "claims": len(claims),
    }, indent=2))


if __name__ == "__main__":
    main()
