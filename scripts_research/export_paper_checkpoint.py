#!/usr/bin/env python
import argparse
import csv
import json
from pathlib import Path


PREFERRED_VARIANTS = [
    "prompt_only",
    "cognitive_stop_present_only",
    "combined_and_present_only_best_f1",
    "vlm_presence",
    "vlm_presence_ocr_aware",
    "vlm_evidence_evidence_aware",
]

PAPER_PRACTICAL_VARIANTS = {
    "prompt_only",
    "cognitive_stop_present_only",
    "combined_or_present_only",
    "combined_and_present_only",
    "combined_and_present_only_best_f1",
    "vlm_presence",
    "vlm_presence_conservative",
    "vlm_presence_ocr_aware",
    "vlm_presence_search_behavior",
    "vlm_evidence_evidence_aware",
    "vlm_evidence_evidence_conservative",
    "vlm_evidence_evidence_rescue_present",
}

DIAGNOSTIC_VARIANT_PREFIXES = (
    "candidate_verifier_",
    "ocr_candidate_verifier_",
)


def read_csv(path):
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def read_json(path):
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def as_float(value, default=None):
    if value in ("", None):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def as_int(value, default=0):
    if value in ("", None):
        return default
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def fmt(value, digits=4):
    number = as_float(value)
    if number is None:
        return ""
    return f"{number:.{digits}f}"


def sort_by_f1(rows):
    return sorted(rows, key=lambda row: (as_float(row.get("absent_f1"), -1), as_float(row.get("accuracy"), -1)), reverse=True)


def row_key(row):
    model = row.get("model", "")
    variant = row.get("variant", "")
    return f"{model}:{variant}"


def index_rows(rows):
    return {row_key(row): row for row in rows}


def choose_rows(absent_rows):
    by_key = index_rows(absent_rows)
    chosen = []
    for model in ["SeekUI", "SeekUI_sft"]:
        for variant in PREFERRED_VARIANTS:
            row = by_key.get(f"{model}:{variant}")
            if row:
                chosen.append(row)
    return chosen


def delta(best, baseline, metric):
    best_value = as_float(best.get(metric), 0.0)
    base_value = as_float(baseline.get(metric), 0.0)
    return best_value - base_value


def compact_status(followup):
    if not followup:
        return {"done": "", "pending": "", "pending_items": []}
    items = followup.get("items", [])
    pending_items = [item for item in items if item.get("state") == "pending" and item.get("id") != "paper_checkpoint"]
    done_items = [item for item in items if item.get("state") == "done" or item.get("id") == "paper_checkpoint"]
    counts = followup.get("counts", {})
    done = len(done_items) if items else counts.get("done", "")
    pending_count = len(pending_items) if items else counts.get("pending", "")
    pending = [
        {
            "id": item.get("id"),
            "title": item.get("title"),
            "missing": len(item.get("missing", [])),
            "command": item.get("command", ""),
        }
        for item in pending_items
    ]
    return {
        "done": done,
        "pending": pending_count,
        "pending_items": pending,
    }


def is_diagnostic_variant(row):
    variant = row.get("variant", "")
    return variant.startswith(DIAGNOSTIC_VARIANT_PREFIXES)


def is_paper_practical_variant(row):
    return row.get("variant", "") in PAPER_PRACTICAL_VARIANTS


def best_rows(absent_rows):
    ranked = sort_by_f1(absent_rows)
    by_model = {}
    for row in ranked:
        model = row.get("model", "")
        by_model.setdefault(model, row)
    return ranked, by_model


def best_practical_rows(absent_rows):
    practical = [row for row in absent_rows if is_paper_practical_variant(row)]
    ranked = sort_by_f1(practical)
    by_model = {}
    for row in ranked:
        model = row.get("model", "")
        by_model.setdefault(model, row)
    return ranked, by_model


def build_report(work_dir):
    outputs = work_dir / "outputs"
    tables = outputs / "research_summary_tables"
    comparisons = outputs / "comparisons"
    absent_rows = read_csv(tables / "absent_status_core.csv")
    filtered_rows = read_csv(outputs / "vlm_evidence_predictions_SeekUI_vlm_evidence_evidence_aware_filtered_status_eval.csv")
    hardcase_rows = read_csv(outputs / "vlm_hard_cases" / "vlm_hard_case_comparison.csv")
    vlm_rows = read_csv(outputs / "paper_tables" / "vlm_ablation_table.csv")
    image_cue_summary = None
    image_cue_paths = sorted(comparisons.glob("image_cue_SeekUI_vs_SeekUI_sft_*.json"))
    if image_cue_paths:
        image_cue_summary = read_json(image_cue_paths[-1])
    followup = compact_status(read_json(outputs / "followup_status.json"))

    ranked, best_by_model = best_rows(absent_rows)
    practical_ranked, practical_best_by_model = best_practical_rows(absent_rows)
    chosen = choose_rows(absent_rows)
    seekui_prompt = index_rows(absent_rows).get("SeekUI:prompt_only")
    seekui_best = practical_best_by_model.get("SeekUI")
    headline = {}
    if seekui_prompt and seekui_best:
        headline = {
            "model": seekui_best.get("model"),
            "variant": seekui_best.get("variant"),
            "absent_f1": seekui_best.get("absent_f1"),
            "accuracy": seekui_best.get("accuracy"),
            "delta_absent_f1_vs_prompt": delta(seekui_best, seekui_prompt, "absent_f1"),
            "delta_accuracy_vs_prompt": delta(seekui_best, seekui_prompt, "accuracy"),
        }

    return {
        "work_dir": str(work_dir),
        "headline": headline,
        "ranked_absent_status": ranked,
        "ranked_practical_absent_status": practical_ranked,
        "ranked_diagnostic_absent_status": [row for row in ranked if is_diagnostic_variant(row)],
        "selected_absent_status": chosen,
        "vlm_ablation_rows": vlm_rows,
        "image_cue_proxy": image_cue_summary,
        "image_cue_proxy_path": str(image_cue_paths[-1]) if image_cue_paths else "",
        "evidence_filtered_rows": filtered_rows,
        "hardcase_comparison_rows": hardcase_rows,
        "followup_status": followup,
    }


def md_table_status(rows):
    lines = [
        "| Model | Variant | Acc | Precision | Recall | F1 | Present->Absent | Absent->Present |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row.get('model', '')} | {row.get('variant', '')} | {fmt(row.get('accuracy'))} | "
            f"{fmt(row.get('absent_precision'))} | {fmt(row.get('absent_recall'))} | {fmt(row.get('absent_f1'))} | "
            f"{row.get('present_to_absent', '')} | {row.get('absent_to_present', '')} |"
        )
    return lines


def md_table_filtered(rows):
    if not rows:
        return ["Pending."]
    lines = [
        "| Name | N | Excluded | Acc | Precision | Recall | F1 | Present->Absent | Absent->Present |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row.get('name', '')} | {row.get('num_examples', '')} | {row.get('excluded_examples', '')} | "
            f"{fmt(row.get('accuracy'))} | {fmt(row.get('absent_precision'))} | {fmt(row.get('absent_recall'))} | "
            f"{fmt(row.get('absent_f1'))} | {row.get('present_absent', '')} | {row.get('absent_present', '')} |"
        )
    return lines


def md_table_hardcases(rows):
    if not rows:
        return ["Pending."]
    lines = [
        "| Label | Case Source | Case Type | Count | Mean Path Evidence | Mean OCR Score |",
        "|---|---|---|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row.get('label', '')} | {row.get('case_source', '')} | {row.get('case_type', '')} | "
            f"{row.get('count', '')} | {fmt(row.get('mean_path_best_evidence'))} | {fmt(row.get('mean_ocr_score'))} |"
        )
    return lines


def md_image_cue(summary, source_path):
    if not summary:
        return ["Pending: missing `outputs/comparisons/image_cue_SeekUI_vs_SeekUI_sft_*.json`."]
    a_last = as_float(summary.get("mean_a_last_to_target"))
    b_last = as_float(summary.get("mean_b_last_to_target"))
    delta = b_last - a_last if a_last is not None and b_last is not None else None
    lines = [
        f"- Source: `{source_path}`",
        f"- Matched examples: {summary.get('num_matched', '')}",
        f"- SeekUI mean length: {fmt(summary.get('mean_a_len'))}",
        f"- SeekUI-SFT mean length: {fmt(summary.get('mean_b_len'))}",
        f"- Mean length delta SFT-SeekUI: {fmt(summary.get('mean_len_delta_b_minus_a'))}",
        f"- SeekUI last-to-target: {fmt(summary.get('mean_a_last_to_target'))}",
        f"- SeekUI-SFT last-to-target: {fmt(summary.get('mean_b_last_to_target'))}",
        f"- Last-to-target delta SFT-SeekUI: {delta:+.4f}" if delta is not None else "- Last-to-target delta SFT-SeekUI: n/a",
        f"- SFT closer count: {summary.get('b_closer_to_target_count', '')}",
        f"- SeekUI closer count: {summary.get('a_closer_to_target_count', '')}",
        "",
        "Interpretation: target-crop image cues are a weak multimodal proxy. Use this section as feasibility evidence, not as proof of native non-text target support.",
    ]
    return lines


def write_md(path, report):
    headline = report.get("headline") or {}
    lines = [
        "# SeekUI Paper Checkpoint",
        "",
        f"Work dir: `{report['work_dir']}`",
        "",
        "## Headline",
        "",
    ]
    if headline:
        lines.extend([
            f"- Current best SeekUI variant: `{headline['variant']}`.",
            f"- Absent F1: {fmt(headline['absent_f1'])}.",
            f"- Accuracy: {fmt(headline['accuracy'])}.",
            f"- Delta F1 vs prompt-only: {headline['delta_absent_f1_vs_prompt']:+.4f}.",
            f"- Delta accuracy vs prompt-only: {headline['delta_accuracy_vs_prompt']:+.4f}.",
        ])
    else:
        lines.append("Pending: missing `absent_status_core.csv` or prompt-only baseline.")
    lines.append("")

    lines.extend([
        "## Selected Present/Absent Results",
        "",
        *md_table_status(report["selected_absent_status"]),
        "",
        "## Top Ranked Practical Results",
        "",
        *md_table_status(report["ranked_practical_absent_status"][:8]),
        "",
        "## Diagnostic / Upper-Bound Results",
        "",
        *md_table_status(report["ranked_diagnostic_absent_status"][:8]),
        "",
        "## Evidence-Aware Filtered Sensitivity",
        "",
        *md_table_filtered(report["evidence_filtered_rows"]),
        "",
        "## VLM vs Combined Hard-Case Comparison",
        "",
        *md_table_hardcases(report["hardcase_comparison_rows"]),
        "",
        "## Image-Cue Multimodal Proxy",
        "",
        *md_image_cue(report["image_cue_proxy"], report["image_cue_proxy_path"]),
        "",
        "## Follow-Up Status",
        "",
    ])

    followup = report["followup_status"]
    lines.append(f"- Done: {followup.get('done')}")
    lines.append(f"- Pending: {followup.get('pending')}")
    if followup.get("pending_items"):
        lines.append("")
        lines.append("| ID | Task | Missing | Next command |")
        lines.append("|---|---|---:|---|")
        for item in followup["pending_items"][:10]:
            command = item.get("command", "").replace("|", "\\|")
            lines.append(f"| {item.get('id')} | {item.get('title')} | {item.get('missing')} | `{command}` |")
    lines.append("")

    lines.extend([
        "## Interpretation Checklist",
        "",
        "- Compare best evidence-aware VLM against combined AND and prompt-only.",
        "- Check filtered sensitivity before treating synthetic absent results as robust.",
        "- Use hard-case comparison to separate not-found safety from present-target over-rejection.",
        "- Treat real/manual absent validation as the next external-validity gate.",
        "",
    ])

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Export a compact paper checkpoint from SeekUI research outputs.")
    parser.add_argument("--work-dir", required=True)
    parser.add_argument("--output-md", required=True)
    parser.add_argument("--output-json", required=True)
    args = parser.parse_args()

    report = build_report(Path(args.work_dir))
    write_md(Path(args.output_md), report)
    Path(args.output_json).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output_json, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(json.dumps({
        "output_md": args.output_md,
        "output_json": args.output_json,
        "selected_rows": len(report["selected_absent_status"]),
        "ranked_rows": len(report["ranked_absent_status"]),
        "hardcase_rows": len(report["hardcase_comparison_rows"]),
    }, indent=2))


if __name__ == "__main__":
    main()
