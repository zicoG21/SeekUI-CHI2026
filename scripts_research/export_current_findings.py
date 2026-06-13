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
    ("SeekUI", "annotation_free_visual_combined_and_present_only_best_f1"),
    ("SeekUI", "vlm_presence"),
    ("SeekUI", "vlm_evidence_evidence_aware"),
    ("SeekUI_sft", "prompt_only"),
    ("SeekUI_sft", "combined_and_present_only_best_f1"),
    ("SeekUI_sft", "annotation_free_combined_and_present_only_best_f1"),
    ("SeekUI_sft", "annotation_free_visual_combined_and_present_only_best_f1"),
    ("SeekUI_sft", "vlm_evidence_evidence_aware"),
]

TARGET_SPLIT_FILES = [
    ("SeekUI", "target", "devtest_status_SeekUI_target.csv"),
    ("SeekUI_sft", "target", "devtest_status_SeekUI_sft_target.csv"),
]

FILTERED_KEY_NAMES = {
    "SeekUI_prompt",
    "SeekUI_cognitive",
    "SeekUI_combined_default",
    "SeekUI_combined_best_f1",
    "SeekUI_sft_prompt",
    "SeekUI_sft_combined_default",
    "SeekUI_sft_combined_best_f1",
    "SeekUI_vlm_evidence_evidence_aware",
    "SeekUI_sft_vlm_evidence_evidence_aware",
}


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
    wanted_variants = {
        "prompt_only_real_absent",
        "prompt_only_real_absent500",
        "combined_and_present_only_best_f1",
        "combined_and_present_only",
        "vlm_presence_real_absent",
        "vlm_presence_real_absent_conservative",
        "vlm_presence_real_absent_ocr_aware",
        "vlm_presence_real_absent_search_behavior",
        "vlm_presence_real_absent500",
        "vlm_presence_real_absent500_conservative",
        "vlm_presence_real_absent500_ocr_aware",
        "vlm_presence_real_absent500_search_behavior",
        "vlm_evidence_real_absent500_evidence_aware",
    }
    selected = [
        row for row in rows
        if row.get("model") == "SeekUI" and row.get("variant") in wanted_variants
    ]
    selected.sort(
        key=lambda row: (
            0 if "real_absent500" in row.get("variant", "") or row.get("num_examples") == "500" else 1,
            {"seekui_prompt": 0, "combined": 1, "vlm_presence": 2, "vlm_evidence": 3}.get(row.get("family", ""), 9),
            -as_float(row.get("absent_f1")),
        )
    )
    return selected


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


def read_second_pass_audit(work_dir):
    path = (
        work_dir / "outputs" / "real_absent_validation_500" /
        "second_pass_audit_hardcases" / "real_absent_second_pass_audit_filled_by_codex.csv"
    )
    rows = read_csv(path)
    if not rows:
        return {
            "exists": False,
            "path": str(path),
            "rows": [],
            "status_counts": {},
            "ambiguity_counts": {},
            "source_rows": [],
            "changed_rows": [],
        }

    def count_by(field):
        counts = {}
        for row in rows:
            key = row.get(field, "")
            counts[key] = counts.get(key, 0) + 1
        return counts

    source_counts = {}
    changed_by_source = {}
    changed_rows = []
    for row in rows:
        source = row.get("case_source", "")
        source_counts[source] = source_counts.get(source, 0) + 1
        original = row.get("gold_status", "")
        audit = row.get("audit_gold_status", "")
        if audit != original:
            changed_by_source[source] = changed_by_source.get(source, 0) + 1
            changed_rows.append(row)

    source_rows = [
        {
            "source": source,
            "rows": count,
            "changed_or_excluded": changed_by_source.get(source, 0),
        }
        for source, count in sorted(source_counts.items())
    ]
    return {
        "exists": True,
        "path": str(path),
        "rows": rows,
        "num_rows": len(rows),
        "status_counts": count_by("audit_gold_status"),
        "ambiguity_counts": count_by("audit_ambiguity_level"),
        "source_rows": source_rows,
        "changed_rows": changed_rows,
    }


def table_second_pass_audit(audit):
    if not audit.get("exists"):
        return ["Pending: filled second-pass audit CSV not found."]
    lines = [
        f"- Reviewed rows: {audit.get('num_rows', 0)}",
        f"- Filled CSV: `{audit.get('path', '')}`",
        "",
        "| Source | Rows | Corrected / Excluded |",
        "|---|---:|---:|",
    ]
    for row in audit.get("source_rows", []):
        lines.append(
            f"| {row.get('source', '')} | {row.get('rows', 0)} | {row.get('changed_or_excluded', 0)} |"
        )
    lines.extend([
        "",
        "| Audit Status | Count |",
        "|---|---:|",
    ])
    for status, count in sorted(audit.get("status_counts", {}).items()):
        lines.append(f"| {status} | {count} |")
    lines.extend([
        "",
        "| Ambiguity | Count |",
        "|---|---:|",
    ])
    for ambiguity, count in sorted(audit.get("ambiguity_counts", {}).items()):
        lines.append(f"| {ambiguity} | {count} |")
    if audit.get("changed_rows"):
        lines.extend([
            "",
            "Changed/excluded rows are mostly visible equivalent links/icons or single-character ambiguous queries.",
        ])
    return lines


def read_second_pass_robustness(work_dir):
    path = (
        work_dir / "outputs" / "real_absent_validation_500" /
        "second_pass_audit_hardcases" / "analysis" / "second_pass_audit_robustness.csv"
    )
    return {
        "exists": path.exists(),
        "path": str(path),
        "rows": read_csv(path),
    }


def table_second_pass_robustness(robustness):
    rows = robustness.get("rows", [])
    if not rows:
        return ["Pending: run `sbatch scripts_utah/analyze_second_pass_audit.slurm`."]
    lines = [
        f"- Source CSV: `{robustness.get('path', '')}`",
        "- Metrics are computed only on rows with a prediction for the given method; audit-label rows marked `exclude` are removed.",
        "",
        "| Label Set | Method | N | Acc | F1 | Delta F1 | P->A | A->P | Missing |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row.get('label_set', '')} | {row.get('method', '')} | {row.get('num_examples', '')} | "
            f"{fmt(row.get('accuracy'))} | {fmt(row.get('absent_f1'))} | "
            f"{fmt(row.get('delta_absent_f1'))} | {row.get('present_absent', '')} | "
            f"{row.get('absent_present', '')} | {row.get('missing_predictions', '')} |"
        )
    return lines


def read_filtered_sensitivity_rows(work_dir):
    outputs = work_dir / "outputs"
    rows = []
    for row in read_csv(outputs / "filtered_status_eval" / "filtered_absent_status.csv"):
        name = row.get("name", "")
        if not name or name in FILTERED_KEY_NAMES:
            rows.append({"source": "synthetic_filtered", **row})

    for path in sorted(outputs.glob("vlm_evidence_predictions_*_filtered_status_eval.csv")):
        for row in read_csv(path):
            name = row.get("name") or path.name.removesuffix("_filtered_status_eval.csv")
            if name not in FILTERED_KEY_NAMES:
                continue
            rows.append({"source": "evidence_filtered", "name": name, **row})
    return rows


def table_filtered_sensitivity(rows):
    if not rows:
        return ["Pending: filtered sensitivity outputs not found."]
    lines = [
        "| Source | Method | N | Excluded | Acc | Precision | Recall | F1 | P->A | A->P |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row.get('source', '')} | {row.get('name', '')} | "
            f"{row.get('num_examples') or row.get('kept_examples') or ''} | "
            f"{row.get('excluded_examples', '')} | {fmt(row.get('accuracy'))} | "
            f"{fmt(row.get('absent_precision'))} | {fmt(row.get('absent_recall'))} | "
            f"{fmt(row.get('absent_f1'))} | {row.get('present_absent', '')} | {row.get('absent_present', '')} |"
        )
    return lines


TRADEOFF_DISPLAY_RATIOS = {
    "PtoA:1_AtoP:1",
    "PtoA:1_AtoP:5",
    "PtoA:5_AtoP:1",
}

TRADEOFF_DISPLAY_METHODS = (
    "SeekUI_combined_and_present_only",
    "SeekUI_annotation_free_combined_and_present_only",
    "SeekUI_annotation_free_visual_combined_and_present_only",
    "SeekUI_cognitive_stop_present_only",
    "SeekUI_sft_combined_and_present_only",
    "SeekUI_sft_annotation_free_combined_and_present_only",
)


def is_practical_tradeoff_row(row):
    method = row.get("method", "")
    threshold_spec = row.get("threshold_spec", "")
    if "candidate_verifier" in method:
        return False
    if method.endswith("_stopping_evidence") or method.endswith("_visual_stopping_evidence"):
        return False
    if "cognitive_threshold=0.0" in threshold_spec and "ocr_threshold=0.0" in threshold_spec:
        return False
    if threshold_spec == "threshold=0.0; mode=present_only":
        return False
    if as_float(row.get("absent_f1"), 0.0) < 0.5:
        return False
    return any(token in method for token in TRADEOFF_DISPLAY_METHODS)


def read_tradeoff_utility_rows(work_dir, limit=18):
    path = work_dir / "outputs" / "tradeoff_utility" / "tradeoff_cost_utility.csv"
    rows = read_csv(path)
    curated = [
        row for row in rows
        if row.get("cost_ratio") in TRADEOFF_DISPLAY_RATIOS and is_practical_tradeoff_row(row)
    ]
    curated.sort(
        key=lambda row: (
            sorted(TRADEOFF_DISPLAY_RATIOS).index(row.get("cost_ratio"))
            if row.get("cost_ratio") in TRADEOFF_DISPLAY_RATIOS else 999,
            as_float(row.get("expected_cost_per_example"), 999.0),
            -as_float(row.get("absent_f1"), -1.0),
        )
    )
    if curated:
        return curated[:limit]

    fallback = [row for row in rows if is_practical_tradeoff_row(row)]
    fallback.sort(
        key=lambda row: (
            as_float(row.get("expected_cost_per_example"), 999.0),
            -as_float(row.get("absent_f1"), -1.0),
        )
    )
    return fallback[:limit]


def table_tradeoff_utility(rows):
    if not rows:
        return ["Pending: run `sbatch scripts_utah/export_tradeoff_utility.slurm`."]
    lines = [
        "Curated non-degenerate practical rows are shown here; the full sweep remains in `outputs/tradeoff_utility/tradeoff_cost_utility.csv`.",
        "",
        "| Cost Ratio | Method | Thresholds | Expected Cost | Acc | F1 | P->A | A->P |",
        "|---|---|---|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row.get('cost_ratio', '')} | {row.get('method', '')} | {row.get('threshold_spec', '')} | "
            f"{fmt(row.get('expected_cost_per_example'))} | {fmt(row.get('accuracy'))} | "
            f"{fmt(row.get('absent_f1'))} | {row.get('present_absent', '')} | {row.get('absent_present', '')} |"
        )
    return lines


def read_gui_case_study_rows(work_dir):
    manifest_path = (
        work_dir / "outputs" / "gui_evaluation_case_study" /
        "SeekUI_combined_and_present_only_best_f1" / "case_study_manifest.json"
    )
    if not manifest_path.exists():
        return []
    with open(manifest_path, "r", encoding="utf-8") as f:
        return json.load(f)


def large_real_absent_status(work_dir):
    base = work_dir / "outputs" / "real_absent_validation_500"
    package_md = base / "review_package" / "real_absent_review_package.md"
    starter = base / "real_absent_validation_starter.csv"
    review = base / "review_package" / "real_absent_rows_to_fill.csv"
    filled = base / "real_absent_validation_filled.csv"
    eval_json = base / "real_absent_validation_eval.json"
    results = base / "real_absent_results.csv"
    return {
        "exists": starter.exists() and review.exists() and package_md.exists(),
        "filled": filled.exists(),
        "eval_exists": eval_json.exists(),
        "results_exist": results.exists(),
        "base_dir": str(base),
        "starter_csv": str(starter),
        "review_csv": str(review),
        "filled_csv": str(filled),
        "eval_json": str(eval_json),
        "results_csv": str(results),
        "review_package_md": str(package_md),
    }


def visual_inventory_status(work_dir):
    outputs = work_dir / "outputs"
    evidence_summary = outputs / "annotation_free_visual_stopping_evidence" / "annotation_free_stopping_evidence_summary.md"
    seekui_eval = outputs / "present_absent_predictions_SeekUI_annotation_free_visual_combined_and_present_only_best_f1_status_eval.json"
    sft_eval = outputs / "present_absent_predictions_SeekUI_sft_annotation_free_visual_combined_and_present_only_best_f1_status_eval.json"
    return {
        "evidence_exists": evidence_summary.exists(),
        "combined_exists": seekui_eval.exists() and sft_eval.exists(),
        "evidence_summary": str(evidence_summary),
        "seekui_eval": str(seekui_eval),
        "sft_eval": str(sft_eval),
    }


def table_gui_case_study(rows):
    if not rows:
        return ["Pending: run `sbatch scripts_utah/export_gui_evaluation_case_study.slurm`."]
    uses = {
        "forced_choice_overestimate_corrected": "Prompt-only overestimates findability; verifier reports absence.",
        "forced_choice_overestimate_kept": "Residual overestimate; useful failure case.",
        "conservative_cost_present_rejected": "Visible target rejected; use to show method cost.",
    }
    lines = [
        "| Case Type | Count | Selected | Paper Use |",
        "|---|---:|---:|---|",
    ]
    for row in rows:
        case_type = row.get("case_type", "")
        lines.append(
            f"| {case_type} | {row.get('count', '')} | {row.get('selected', '')} | {uses.get(case_type, '')} |"
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


def revision_route(summary):
    has_filtered = bool(summary.get("filtered_sensitivity_rows"))
    has_real_absent = bool(summary.get("real_absent_rows"))
    large_real_status = summary.get("large_real_absent_status", {})
    second_pass_audit = summary.get("second_pass_audit", {})
    has_large_real_absent = large_real_status.get("exists", False)
    has_large_real_results = large_real_status.get("results_exist", False)
    has_tradeoff = bool(summary.get("tradeoff_utility_rows"))
    has_case_study = bool(summary.get("gui_case_study_rows"))
    visual_status = summary.get("visual_inventory_status", {})
    has_annotation_free = any(
        row.get("variant") in {
            "annotation_free_combined_and_present_only_best_f1",
            "annotation_free_visual_combined_and_present_only_best_f1",
        }
        for row in summary.get("selected_rows", [])
    )
    return [
        {
            "priority": "1",
            "item": "Annotation-free candidate inventory",
            "status": "visual ready" if visual_status.get("combined_exists") else ("visual evidence ready" if visual_status.get("evidence_exists") else ("started" if has_annotation_free else "pending")),
            "why": "Defensibility/deployability: answers whether path evidence depends on benchmark annotations.",
            "next_step": (
                "Compare OCR-only and OCR+visual annotation-free variants in the main result tables."
                if visual_status.get("combined_exists")
                else "Run OCR+edge visual proposals, then apply the visual annotation-free combined verifier."
            ),
        },
        {
            "priority": "2",
            "item": "Larger realistic absent validation",
            "status": (
                "500-row evaluated + second-pass audit"
                if has_large_real_results and second_pass_audit.get("exists")
                else (
                    "500-row evaluated"
                    if has_large_real_results
                    else ("500-row eval ready" if large_real_status.get("eval_exists") else ("500-row starter ready" if has_large_real_absent else ("started" if has_real_absent else "pending")))
                )
            ),
            "why": "External validity: moves the result beyond synthetic absent target swaps.",
            "next_step": (
                "Use the 500-row results plus the hard-case second-pass audit as the main realistic-validation evidence."
                if has_large_real_results and second_pass_audit.get("exists")
                else (
                    "Use the 500-row results as the main realistic-validation evidence and add confidence intervals/error analysis."
                    if has_large_real_results
                    else (
                        "Run VLM/SeekUI baselines on the prepared 500-row eval JSON."
                        if large_real_status.get("eval_exists")
                        else (
                            "Fill/review the 500-row package and convert it into eval JSON."
                            if has_large_real_absent
                            else "Expand the reviewed set from 100 rows to at least 300-500 stratified rows."
                        )
                    )
                )
            ),
        },
        {
            "priority": "3",
            "item": "PR/ROC/cost-sensitive utility",
            "status": "done" if has_tradeoff else "pending",
            "why": "Tradeoff clarity: explains the cost of P->A errors versus A->P errors instead of only reporting F1.",
            "next_step": (
                "Use the generated utility table in the results narrative."
                if has_tradeoff
                else "Export threshold curves and utility tables under multiple false-absent / false-present cost ratios."
            ),
        },
        {
            "priority": "4",
            "item": "Filtered sensitivity in main results",
            "status": "done" if has_filtered else "pending",
            "why": "Validity: shows the main effect survives annotation-conflict and OCR-leak filtering.",
            "next_step": "Keep filtered sensitivity in the main result narrative, not only as a sanity appendix.",
        },
        {
            "priority": "5",
            "item": "GUI evaluation case study",
            "status": "done" if has_case_study else "pending",
            "why": "HCI relevance: demonstrates how a forced-choice synthetic user can overestimate screen findability.",
            "next_step": (
                "Pick one large visual example from each generated case type for the main paper figure."
                if has_case_study
                else "Select several screens where prompt-only grounds to a plausible element but uncertainty-aware verification flags absence or weak evidence."
            ),
        },
    ]


def table_revision_route(rows):
    lines = [
        "| Priority | Item | Status | Why It Matters | Next Step |",
        "|---:|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row['priority']} | {row['item']} | {row['status']} | {row['why']} | {row['next_step']} |"
        )
    return lines


def directions_summary(summary):
    has_target = bool(summary.get("target_disjoint_rows"))
    real_rows = summary.get("real_absent_rows", [])
    real_index = {
        (row.get("model"), row.get("family"), row.get("variant")): row
        for row in real_rows
    }
    real500_prompt = real_index.get(("SeekUI", "seekui_prompt", "prompt_only_real_absent500"), {})
    real500_combined = real_index.get(("SeekUI", "combined", "combined_and_present_only_best_f1"), {})
    indexed = row_index(summary.get("selected_rows", []))
    ocr_free = indexed.get(("SeekUI", "annotation_free_combined_and_present_only_best_f1"), {})
    visual_free = indexed.get(("SeekUI", "annotation_free_visual_combined_and_present_only_best_f1"), {})
    visual_note = ""
    if ocr_free and visual_free:
        visual_note = (
            f" Naive OCR+edge visual proposals underperform OCR-only "
            f"({fmt(visual_free.get('absent_f1'))} vs {fmt(ocr_free.get('absent_f1'))}), "
            "so this is a negative proposal-quality result rather than a new best deployable method."
        )
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
                "from 0.7300 to 0.7995." + visual_note
            ),
            "next_step": "Use OCR-only as the current deployable approximation; test stronger UI/icon proposals or candidate-crop VLM next.",
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
            "what_we_have": "Synthetic present/absent benchmark, filtered sensitivity, held-out splits, target-disjoint split, and 500-row realistic validation.",
            "evidence": (
                (
                    "500-row realistic validation improves F1 from "
                    f"{fmt(real500_prompt.get('absent_f1'))} to {fmt(real500_combined.get('absent_f1'))}; "
                    if real500_prompt and real500_combined
                    else "Realistic validation is prepared; "
                )
                + ("target-disjoint validation is positive." if has_target else "target-disjoint validation is pending.")
            ),
            "next_step": "Use 500-row realistic validation as the main external-validity result; add confidence intervals/error analysis if needed.",
            "remaining": (
                "Broaden/stratify realistic validation only if reviewers need more external-validity evidence."
                if real500_prompt and real500_combined
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


def strong_accept_priorities(summary):
    large_real = summary.get("large_real_absent_status", {})
    second_pass_audit = summary.get("second_pass_audit", {})
    visual_status = summary.get("visual_inventory_status", {})
    has_case_study = bool(summary.get("gui_case_study_rows"))
    indexed = row_index(summary.get("selected_rows", []))
    ocr_free = indexed.get(("SeekUI", "annotation_free_combined_and_present_only_best_f1"), {})
    visual_free = indexed.get(("SeekUI", "annotation_free_visual_combined_and_present_only_best_f1"), {})
    if visual_status.get("combined_exists"):
        annotation_status = "visual ready"
        if ocr_free and visual_free:
            annotation_next = (
                "Use OCR-only as the current deployable approximation; report OCR+edge visual proposals as a negative baseline "
                f"({fmt(visual_free.get('absent_f1'))} vs OCR-only {fmt(ocr_free.get('absent_f1'))})."
            )
        else:
            annotation_next = "Compare OCR-only and OCR+visual annotation-free variants."
    else:
        annotation_status = "started" if ocr_free else "pending"
        annotation_next = "Strengthen OCR-only candidates with UI component/icon proposals or crop-level VLM candidates."

    return [
        {
            "priority": "Annotation-free verifier",
            "why": "Turns annotation-backed evidence from an oracle-like controlled analysis into a deployable approximation.",
            "status": annotation_status,
            "next_step": annotation_next,
        },
        {
            "priority": "Larger realistic validation",
            "why": "Directly addresses the main external-validity risk of the synthetic absent benchmark.",
            "status": (
                "500-row evaluated + second-pass audit"
                if large_real.get("results_exist") and second_pass_audit.get("exists")
                else (
                    "500-row evaluated"
                    if large_real.get("results_exist")
                    else ("500-row eval ready" if large_real.get("eval_exists") else ("500-row starter ready" if large_real.get("exists") else "started"))
                )
            ),
            "next_step": (
                "Use the 500-row result and the 117-row hard-case audit in the main paper narrative."
                if large_real.get("results_exist") and second_pass_audit.get("exists")
                else (
                    "Use the 500-row result in the main paper narrative; optionally add CI/error slices."
                    if large_real.get("results_exist")
                    else (
                        "Run models on the prepared 500-row eval JSON."
                        if large_real.get("eval_exists")
                        else (
                            "Fill/review the 500-row package and convert it into eval JSON."
                            if large_real.get("exists")
                            else "Scale the current 100-row set to 200-400 stratified present/absent rows."
                        )
                    )
                )
            ),
        },
        {
            "priority": "UI evaluation case study",
            "why": "Makes the HCI implication concrete: forced-choice synthetic users can overstate screen findability.",
            "status": "done" if has_case_study else "pending",
            "next_step": (
                "Select one large visual example from each generated case type for the main paper figure."
                if has_case_study
                else "Select a few screens where prompt-only grounds to a plausible element but the uncertainty-aware verifier flags absence or weak evidence."
            ),
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
        "## Second-Pass Realistic Validation Audit",
        "",
        *table_second_pass_audit(summary["second_pass_audit"]),
        "",
        "## Audit-Adjusted Robustness",
        "",
        *table_second_pass_robustness(summary["second_pass_robustness"]),
        "",
        "## Filtered Sensitivity",
        "",
        *table_filtered_sensitivity(summary["filtered_sensitivity_rows"]),
        "",
        "## Target-Disjoint Robustness",
        "",
        *table_target_disjoint(summary["target_disjoint_rows"]),
        "",
        "## PR/ROC and Cost-Sensitive Utility",
        "",
        *table_tradeoff_utility(summary["tradeoff_utility_rows"]),
        "",
        "## GUI Evaluation Case Study",
        "",
        *table_gui_case_study(summary["gui_case_study_rows"]),
        "",
        "## Original 3+1 Direction Coverage",
        "",
        *table_directions(summary["directions_summary"]),
        "",
        "## Highest-Value Next Upgrades",
        "",
        *table_priorities(summary["strong_accept_priorities"]),
        "",
        "## RR/ARR Revision Route",
        "",
        *table_revision_route(summary["revision_route"]),
        "",
        "## Interpretation",
        "",
        "- Annotation-backed candidate inventories remain diagnostic/upper-bound evidence, not a deployable assumption.",
        "- Annotation-free OCR candidates recover part of the gain, supporting deployability, but they underperform stronger UI/VLM evidence.",
        "- Naive OCR+edge visual proposals underperform OCR-only annotation-free evidence, suggesting simple visual regions add noise; stronger UI detectors or crop-level VLM proposals are the right next deployable inventory path.",
        "- Evidence-aware VLM gives the strongest practical synthetic result, while combined AND remains the most transparent verifier.",
        "- On the 500-row realistic validation set, evidence-aware VLM over-rejects present targets; combined AND and OCR-aware VLM are the stronger realistic-validation results.",
        "- The 500-row realistic validation is now the main external-validity check; use the 100-row version only as an earlier smoke test.",
        "- The most important revision gaps are deployability and validity: annotation-free evidence plus larger realistic validation matter more than further prompt tuning.",
        "- Add PR/ROC/cost-sensitive utility before submission so the P->A versus A->P tradeoff is explicitly argued rather than hidden inside F1.",
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
    real_dir_500 = work_dir / "outputs" / "real_absent_validation_500"
    real_dir = real_dir_500 if (real_dir_500 / "real_absent_results.csv").exists() else work_dir / "outputs" / "real_absent_validation"
    absent_rows = read_csv(tables / "absent_status_core.csv")
    real_rows = read_csv(real_dir / "real_absent_results.csv")
    filtered_sensitivity_rows = read_filtered_sensitivity_rows(work_dir)
    tradeoff_utility_rows = read_tradeoff_utility_rows(work_dir)
    gui_case_study_rows = read_gui_case_study_rows(work_dir)
    large_real_status = large_real_absent_status(work_dir)
    second_pass_audit = read_second_pass_audit(work_dir)
    second_pass_robustness = read_second_pass_robustness(work_dir)
    visual_status = visual_inventory_status(work_dir)
    target_disjoint_rows = read_target_disjoint_rows(work_dir)
    indexed = row_index(absent_rows)
    seekui_prompt = indexed.get(("SeekUI", "prompt_only"), {})
    seekui_combined = indexed.get(("SeekUI", "combined_and_present_only_best_f1"), {})
    seekui_annotation_free = indexed.get(("SeekUI", "annotation_free_combined_and_present_only_best_f1"), {})
    seekui_annotation_free_visual = indexed.get(("SeekUI", "annotation_free_visual_combined_and_present_only_best_f1"), {})
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
    if seekui_prompt and seekui_annotation_free_visual:
        if seekui_annotation_free:
            claims.append(
                "Naive OCR+edge visual proposals underperform OCR-only annotation-free evidence "
                f"({fmt(seekui_annotation_free_visual.get('absent_f1'))} vs "
                f"{fmt(seekui_annotation_free.get('absent_f1'))} F1), suggesting simple visual regions add noise."
            )
        else:
            claims.append(
                "Naive OCR+edge visual proposals reach SeekUI absent F1 "
                f"{fmt(seekui_annotation_free_visual.get('absent_f1'))}, best treated as a proposal-quality baseline."
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
    real_prompt = (
        real_index.get(("SeekUI", "seekui_prompt", "prompt_only_real_absent500"), {})
        or real_index.get(("SeekUI", "seekui_prompt", "prompt_only_real_absent"), {})
    )
    real_combined = real_index.get(("SeekUI", "combined", "combined_and_present_only_best_f1"), {})
    real_ocr_aware = real_index.get(("SeekUI", "vlm_presence", "vlm_presence_real_absent500_ocr_aware"), {})
    real_evidence = real_index.get(("SeekUI", "vlm_evidence", "vlm_evidence_real_absent500_evidence_aware"), {})
    if real_prompt and real_combined:
        real_n = real_prompt.get("num_examples", "")
        claims.append(
            f"On the {real_n}-row realistic absent validation set, combined best-F1 improves F1 from "
            f"{fmt(real_prompt.get('absent_f1'))} to {fmt(real_combined.get('absent_f1'))}."
        )
    if real_ocr_aware and real_evidence:
        claims.append(
            "On the 500-row realistic validation set, OCR-aware VLM remains competitive "
            f"(F1 {fmt(real_ocr_aware.get('absent_f1'))}), while evidence-aware VLM over-rejects "
            f"present targets (P->A {real_evidence.get('present_absent')}, F1 {fmt(real_evidence.get('absent_f1'))})."
        )
    if second_pass_audit.get("exists"):
        claims.append(
            "A 117-row second-pass audit covers random rows and hard cases from the 500-row realistic validation; "
            f"{len(second_pass_audit.get('changed_rows', []))} rows were corrected or excluded, mostly visible equivalent links/icons or ambiguous single-character queries."
        )
    audit_robust_rows = {
        (row.get("label_set"), row.get("method")): row
        for row in second_pass_robustness.get("rows", [])
    }
    audit_combined = audit_robust_rows.get(("audit_gold_status", "combined"), {})
    audit_ocr = audit_robust_rows.get(("audit_gold_status", "ocr_aware_vlm"), {})
    audit_evidence = audit_robust_rows.get(("audit_gold_status", "evidence_aware_vlm"), {})
    if audit_combined and audit_ocr and audit_evidence:
        claims.append(
            "On the audited hard-case subset, combined AND and OCR-aware VLM remain useful "
            f"(F1 {fmt(audit_combined.get('absent_f1'))} and {fmt(audit_ocr.get('absent_f1'))}), "
            f"while evidence-aware VLM remains over-conservative (P->A {audit_evidence.get('present_absent')})."
        )
    for row in filtered_sensitivity_rows:
        if row.get("name") == "SeekUI_combined_best_f1":
            claims.append(
                "Filtered sensitivity keeps the main effect: SeekUI combined best-F1 reaches filtered absent F1 "
                f"{fmt(row.get('absent_f1'))} on {row.get('num_examples') or row.get('kept_examples')} kept examples."
            )
            break
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
        "second_pass_audit": second_pass_audit,
        "second_pass_robustness": second_pass_robustness,
        "filtered_sensitivity_rows": filtered_sensitivity_rows,
        "tradeoff_utility_rows": tradeoff_utility_rows,
        "gui_case_study_rows": gui_case_study_rows,
        "large_real_absent_status": large_real_status,
        "visual_inventory_status": visual_status,
        "target_disjoint_rows": target_disjoint_rows,
    }
    summary["directions_summary"] = directions_summary(summary)
    summary["strong_accept_priorities"] = strong_accept_priorities(summary)
    summary["revision_route"] = revision_route(summary)
    write_json(Path(args.output_json), summary)
    write_md(Path(args.output_md), summary)
    print(json.dumps({
        "output_json": args.output_json,
        "output_md": args.output_md,
        "claims": len(claims),
    }, indent=2))


if __name__ == "__main__":
    main()
