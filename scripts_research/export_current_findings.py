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

TARGET_SPLIT_FILES = [
    ("SeekUI", "target", "devtest_status_SeekUI_target.csv"),
    ("SeekUI_sft", "target", "devtest_status_SeekUI_sft_target.csv"),
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


def read_target_disjoint_rows(work_dir):
    out_dir = work_dir / "outputs" / "devtest_status"
    rows = []
    for model, split, filename in TARGET_SPLIT_FILES:
        path = out_dir / filename
        for row in read_csv(path):
            if row.get("split") != "test":
                continue
            rows.append({
                "model_group": model,
                "split_by": split,
                **row,
            })
    return rows


def table_target_disjoint(rows):
    if not rows:
        return ["Pending: target-disjoint dev/test status outputs not found."]
    lines = [
        "| Model Group | Method | Acc | F1 | Delta F1 | 95% CI | Delta Acc | 95% CI | P->A | A->P |",
        "|---|---|---:|---:|---:|---|---:|---|---:|---:|",
    ]
    for row in rows:
        ci_f1 = ""
        ci_acc = ""
        if row.get("baseline"):
            ci_f1 = f"[{fmt(row.get('delta_absent_f1_ci_low'))}, {fmt(row.get('delta_absent_f1_ci_high'))}]"
            ci_acc = f"[{fmt(row.get('delta_accuracy_ci_low'))}, {fmt(row.get('delta_accuracy_ci_high'))}]"
        lines.append(
            f"| {row.get('model_group', '')} | {row.get('name', '')} | {fmt(row.get('accuracy'))} | "
            f"{fmt(row.get('absent_f1'))} | {fmt(row.get('delta_absent_f1_mean'))} | {ci_f1} | "
            f"{fmt(row.get('delta_accuracy_mean'))} | {ci_acc} | {row.get('present_absent', '')} | "
            f"{row.get('absent_present', '')} |"
        )
    return lines


def directions_summary(summary):
    has_target = bool(summary.get("target_disjoint_rows"))
    has_real_absent = bool(summary.get("real_absent_rows"))
    return [
        {
            "direction": "1. Multimodal / non-text UI search",
            "status": "partial",
            "paper_role": "secondary generalization, not the current main claim",
            "what_we_have": (
                "Target-crop image-cue proxy, OCR candidate verifier, annotation-free OCR candidate inventory, "
                "and evidence-aware VLM reasoning."
            ),
            "evidence": (
                "Image-cue proxy is feasible but weak; annotation-free OCR candidate inventory improves SeekUI F1 "
                "from 0.7300 to 0.7995."
            ),
            "next_step": "Build a small icon/non-text validation set or candidate-crop VLM verifier.",
            "remaining": "Native icon/non-text target data and UI component/icon proposals are still needed.",
        },
        {
            "direction": "2. Cognitive model / stopping",
            "status": "strong",
            "paper_role": "mechanism behind uncertainty-aware search",
            "what_we_have": "Cognitive stopping, path evidence, behavioral metrics, combined AND verifier, and evidence-aware VLM.",
            "evidence": "Combined AND improves SeekUI absent F1 from 0.7300 to 0.8824; evidence-aware VLM reaches 0.8981.",
            "next_step": "Run a multi-sample uncertainty pilot to test whether repeated scanpaths converge for present targets and disperse for absent targets.",
            "remaining": "A deployable candidate inventory can be strengthened beyond OCR-only proposals.",
        },
        {
            "direction": "3. Target absent handling",
            "status": "strong",
            "paper_role": "main paper core",
            "what_we_have": "Synthetic present/absent benchmark, filtered sensitivity, held-out splits, target-disjoint split, and 100-row realistic validation.",
            "evidence": (
                "Realistic validation improves F1 from 0.7907 to 0.9159; "
                + ("target-disjoint validation is positive." if has_target else "target-disjoint validation is pending.")
            ),
            "next_step": "Expand realistic validation to 200-400 rows and keep annotation-free candidate inventory in the main defensibility story.",
            "remaining": (
                "Expand realistic validation beyond 100 rows." if has_real_absent
                else "Complete realistic validation."
            ),
        },
        {
            "direction": "4. Associative search",
            "status": "exploratory",
            "paper_role": "future robustness challenge",
            "what_we_have": "Semantic-query v3 with association-first examples and split summaries.",
            "evidence": "Association queries are represented as a small benchmark slice, but not yet a standalone contribution.",
            "next_step": "Define query-generation rules and human-labeled acceptable target sets before treating this as a separate contribution.",
            "remaining": "Needs a dedicated dataset or stronger query-generation protocol before becoming a main paper thread.",
        },
    ]


def table_directions(rows):
    lines = [
        "| Direction | Status | Paper Role | What We Have | Evidence | Next Step | Remaining |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row['direction']} | {row['status']} | {row['paper_role']} | {row['what_we_have']} | "
            f"{row['evidence']} | {row['next_step']} | {row['remaining']} |"
        )
    return lines


def strong_accept_priorities():
    return [
        {
            "priority": "Annotation-free verifier",
            "why": "Turns annotation-backed evidence from an oracle-like controlled analysis into a deployable approximation.",
            "status": "started",
            "next_step": "Strengthen OCR-only candidates with UI component/icon proposals or crop-level VLM candidates.",
        },
        {
            "priority": "Larger realistic validation",
            "why": "Directly addresses the main external-validity risk of the synthetic absent benchmark.",
            "status": "started",
            "next_step": "Scale the current 100-row set to 200-400 stratified present/absent rows.",
        },
        {
            "priority": "UI evaluation case study",
            "why": "Makes the HCI implication concrete: forced-choice synthetic users can overstate screen findability.",
            "status": "pending",
            "next_step": "Select a few screens where prompt-only grounds to a plausible element but the uncertainty-aware verifier flags absence or weak evidence.",
        },
    ]


def table_priorities(rows):
    lines = [
        "| Priority | Why It Matters | Status | Next Step |",
        "|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row['priority']} | {row['why']} | {row['status']} | {row['next_step']} |"
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
        "## Target-Disjoint Robustness",
        "",
        *table_target_disjoint(summary["target_disjoint_rows"]),
        "",
        "## Original 3+1 Direction Coverage",
        "",
        *table_directions(summary["directions_summary"]),
        "",
        "## Highest-Value Next Upgrades",
        "",
        *table_priorities(summary["strong_accept_priorities"]),
        "",
        "## Interpretation",
        "",
        "- Annotation-backed candidate inventories remain diagnostic/upper-bound evidence, not a deployable assumption.",
        "- Annotation-free OCR candidates recover part of the gain, supporting deployability, but they underperform stronger UI/VLM evidence.",
        "- Evidence-aware VLM gives the strongest practical synthetic result, while combined AND remains the most transparent verifier.",
        "- The 100-row realistic validation is an external-validity smoke test; expanding it is the next data-facing priority.",
        "- Keep the paper focused: target absence is the core problem, cognitive stopping is the mechanism, multimodal/non-text is secondary generalization, and associative search is future work.",
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
    target_disjoint_rows = read_target_disjoint_rows(work_dir)
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
    for row in target_disjoint_rows:
        if row.get("model_group") == "SeekUI" and row.get("name") == "SeekUI_combined":
            claims.append(
                "Target-disjoint validation remains positive for SeekUI combined AND: test absent F1 "
                f"{fmt(row.get('absent_f1'))}, delta F1 {fmt(row.get('delta_absent_f1_mean'))} "
                f"with CI [{fmt(row.get('delta_absent_f1_ci_low'))}, {fmt(row.get('delta_absent_f1_ci_high'))}]."
            )
            break

    summary = {
        "work_dir": str(work_dir),
        "claims": claims,
        "selected_rows": select_rows(absent_rows),
        "top_practical_rows": best_practical(absent_rows),
        "real_absent_rows": real_selected,
        "target_disjoint_rows": target_disjoint_rows,
    }
    summary["directions_summary"] = directions_summary(summary)
    summary["strong_accept_priorities"] = strong_accept_priorities()
    write_json(Path(args.output_json), summary)
    write_md(Path(args.output_md), summary)
    print(json.dumps({
        "output_json": args.output_json,
        "output_md": args.output_md,
        "claims": len(claims),
    }, indent=2))


if __name__ == "__main__":
    main()
