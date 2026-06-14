#!/usr/bin/env python
import argparse
import csv
import json
from pathlib import Path


KEY_VARIANTS = [
    "native_text_balanced",
    "native_text_balanced_combined_and_present_only_native_tuned_absent_f1",
    "native_text_color_balanced",
    "native_text_color_balanced_combined_and_present_only_native_tuned_absent_f1",
    "native_text_color_balanced_color_aware_native_tuned_absent_f1",
    "native_text_color_balanced_color_aware_filtered_tuned_absent_f1",
    "native_text_color_balanced_crop_ocr_vlm",
    "native_text_color_balanced_context_crop_ocr_vlm",
    "vlm_evidence_native_text_color_balanced_evidence_aware",
    "vlm_evidence_native_text_color_balanced_evidence_rescue_present",
    "native_text_color_balanced_status_ensemble_filtered_absent_f1",
    "native_text_color_balanced_native_supervised_calibrated_native_original_max_f1",
    "native_text_color_balanced_native_supervised_calibrated_native_original_precision_ge_0p55",
    "native_text_color_balanced_native_supervised_calibrated_native_original_pa_le_100",
    "native_text_color_balanced_native_supervised_calibrated_clean_absent_only_max_f1",
    "native_text_color_balanced_native_supervised_calibrated_color_instance_only_max_f1",
    "native_text_color_balanced_native_supervised_calibrated_color_instance_only_precision_ge_0p55",
    "native_text_color_balanced_native_task_routed_clean_vs_color",
    "native_text_color_balanced_native_task_routed_conflict_present_guard",
    "native_text_color_balanced_native_task_routed_color_instance_focus",
    "native_text_color_balanced_native_bucket_router_native_original_absent_f1",
    "native_text_color_balanced_native_bucket_router_clean_absent_only_absent_f1",
    "native_text_color_balanced_native_bucket_router_visible_text_as_present_absent_f1",
    "native_text_color_balanced_native_bucket_router_color_instance_as_present_absent_f1",
    "native_text_color_balanced_native_bucket_router_all_visible_conflicts_as_present_absent_f1",
    "native_text_color_balanced_native_bucket_router_color_instance_only_absent_f1",
    "native_text_color_balanced_native_cv_bucket_router_native_original_absent_f1",
    "native_text_color_balanced_native_cv_bucket_router_clean_absent_only_absent_f1",
    "native_text_color_balanced_native_cv_bucket_router_color_instance_as_present_absent_f1",
    "native_text_color_balanced_native_cv_bucket_router_all_visible_conflicts_as_present_absent_f1",
    "native_text_color_balanced_native_cv_bucket_router_color_instance_only_absent_f1",
]


def is_key_row(row):
    variant = row.get("variant", "")
    split = row.get("split", "")
    if variant in KEY_VARIANTS:
        return True
    if split.startswith("native_v2_"):
        return True
    return False


def read_csv(path):
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "view",
        "split",
        "family",
        "variant",
        "num_examples",
        "excluded_examples",
        "accuracy",
        "absent_precision",
        "absent_recall",
        "absent_f1",
        "present_absent",
        "absent_present",
        "takeaway",
    ]
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def as_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def fmt(value):
    number = as_float(value)
    return f"{number:.4f}" if number is not None else ""


def normalize_row(row, view):
    return {
        "view": view,
        "split": row.get("split", ""),
        "family": row.get("family", ""),
        "variant": row.get("variant", ""),
        "num_examples": row.get("num_examples", ""),
        "excluded_examples": row.get("excluded_examples", "0" if view == "raw" else ""),
        "accuracy": row.get("accuracy", ""),
        "absent_precision": row.get("absent_precision", ""),
        "absent_recall": row.get("absent_recall", ""),
        "absent_f1": row.get("absent_f1", ""),
        "present_absent": row.get("present_absent", ""),
        "absent_present": row.get("absent_present", ""),
        "takeaway": "",
    }


def add_takeaways(rows):
    by_key = {(row["view"], row["variant"]): row for row in rows}
    for row in rows:
        split = row.get("split", "")
        variant = row.get("variant", "")
        family = row.get("family", "")
        if not split.startswith("native_v2_"):
            continue
        if family == "seekui_prompt":
            row["takeaway"] = "Processed VSGUI v2 prompt-only baseline for this task split."
        elif family == "combined":
            row["takeaway"] = "Interpretable scanpath/OCR verifier on processed VSGUI v2."
        elif family == "vlm_presence":
            row["takeaway"] = "Generic screenshot-level VLM presence baseline on processed VSGUI v2."
        elif family == "vlm_evidence":
            row["takeaway"] = "Evidence-aware VLM using processed VSGUI v2 verifier evidence."
        elif family == "color_aware":
            row["takeaway"] = "Color-aware text verifier; most relevant for text+color v2 splits."
        elif family in {"context_crop_vlm", "crop_vlm"}:
            row["takeaway"] = "Crop/context VLM verifier; tests whether localized visual evidence helps."
        elif family == "ensemble":
            row["takeaway"] = "Simple rule ensemble over v2 verifier decisions."
        elif "image_cue_unresolved" in variant:
            row["takeaway"] = "Diagnostic only; image-cue assets are unresolved."
    if ("raw", "native_text_balanced_combined_and_present_only_native_tuned_absent_f1") in by_key:
        by_key[("raw", "native_text_balanced_combined_and_present_only_native_tuned_absent_f1")]["takeaway"] = (
            "Best native text verifier; large gain over prompt-only."
        )
    if ("raw", "native_text_color_balanced_combined_and_present_only_native_tuned_absent_f1") in by_key:
        by_key[("raw", "native_text_color_balanced_combined_and_present_only_native_tuned_absent_f1")]["takeaway"] = (
            "Best raw text+color verifier, but trades many present targets for absent recall."
        )
    if ("filtered", "native_text_color_balanced_color_aware_filtered_tuned_absent_f1") in by_key:
        by_key[("filtered", "native_text_color_balanced_color_aware_filtered_tuned_absent_f1")]["takeaway"] = (
            "Best cleaner text+color subset result; supports color-aware verification after conflict filtering."
        )
    if ("raw", "native_text_color_balanced_crop_ocr_vlm") in by_key:
        by_key[("raw", "native_text_color_balanced_crop_ocr_vlm")]["takeaway"] = (
            "Negative result: OCR-only crops lose too much context for native text+color."
        )
    if ("raw", "native_text_color_balanced_context_crop_ocr_vlm") in by_key:
        by_key[("raw", "native_text_color_balanced_context_crop_ocr_vlm")]["takeaway"] = (
            "Tests whether full screenshot context rescues the crop-level VLM verifier."
        )
    if ("raw", "vlm_evidence_native_text_color_balanced_evidence_aware") in by_key:
        by_key[("raw", "vlm_evidence_native_text_color_balanced_evidence_aware")]["takeaway"] = (
            "Tests whether screenshot reasoning can use path/OCR/color-aware evidence on native text+color."
        )
    if ("raw", "vlm_evidence_native_text_color_balanced_evidence_rescue_present") in by_key:
        by_key[("raw", "vlm_evidence_native_text_color_balanced_evidence_rescue_present")]["takeaway"] = (
            "Tests whether VLM evidence can reduce conservative present-target over-rejection."
        )
    if ("raw", "native_text_color_balanced_status_ensemble_filtered_absent_f1") in by_key:
        by_key[("raw", "native_text_color_balanced_status_ensemble_filtered_absent_f1")]["takeaway"] = (
            "CPU ensemble over color-aware, context-crop, and evidence-aware status decisions."
        )
    for variant in [
        "native_text_color_balanced_native_supervised_calibrated_native_original_max_f1",
        "native_text_color_balanced_native_supervised_calibrated_native_original_precision_ge_0p55",
        "native_text_color_balanced_native_supervised_calibrated_native_original_pa_le_100",
        "native_text_color_balanced_native_supervised_calibrated_clean_absent_only_max_f1",
        "native_text_color_balanced_native_supervised_calibrated_color_instance_only_max_f1",
        "native_text_color_balanced_native_supervised_calibrated_color_instance_only_precision_ge_0p55",
    ]:
        if ("raw", variant) in by_key:
            by_key[("raw", variant)]["takeaway"] = (
                "Applies cross-validated supervised calibration as a real status verifier."
            )
    for variant in [
        "native_text_color_balanced_native_task_routed_clean_vs_color",
        "native_text_color_balanced_native_task_routed_conflict_present_guard",
        "native_text_color_balanced_native_task_routed_color_instance_focus",
    ]:
        if ("raw", variant) in by_key:
            by_key[("raw", variant)]["takeaway"] = (
                "Routes native cases by OCR-visible text/color-instance bucket."
            )
    for variant in [
        "native_text_color_balanced_native_bucket_router_native_original_absent_f1",
        "native_text_color_balanced_native_bucket_router_clean_absent_only_absent_f1",
        "native_text_color_balanced_native_bucket_router_visible_text_as_present_absent_f1",
        "native_text_color_balanced_native_bucket_router_color_instance_as_present_absent_f1",
        "native_text_color_balanced_native_bucket_router_all_visible_conflicts_as_present_absent_f1",
        "native_text_color_balanced_native_bucket_router_color_instance_only_absent_f1",
    ]:
        if ("raw", variant) in by_key:
            by_key[("raw", variant)]["takeaway"] = (
                "Bucket-tuned router over all available native verifiers; use as an analysis upper bound, not a deployed model."
            )
    for variant in [
        "native_text_color_balanced_native_cv_bucket_router_native_original_absent_f1",
        "native_text_color_balanced_native_cv_bucket_router_clean_absent_only_absent_f1",
        "native_text_color_balanced_native_cv_bucket_router_color_instance_as_present_absent_f1",
        "native_text_color_balanced_native_cv_bucket_router_all_visible_conflicts_as_present_absent_f1",
        "native_text_color_balanced_native_cv_bucket_router_color_instance_only_absent_f1",
    ]:
        if ("raw", variant) in by_key:
            by_key[("raw", variant)]["takeaway"] = (
                "Cross-validated bucket router; more defensible than the same-data bucket upper bound."
            )
    return rows


def write_md(path, rows):
    lines = [
        "# Native VSGUI Extension Summary",
        "",
        "This summary focuses on native VSGUI10K text and text+color target-absence experiments.",
        "",
        "| View | Split | Family | Variant | N | Excl. | Acc | Prec. | Rec. | F1 | P->A | A->P | Takeaway |",
        "|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row['view']} | {row['split']} | {row['family']} | {row['variant']} | "
            f"{row['num_examples']} | {row['excluded_examples']} | {fmt(row['accuracy'])} | "
            f"{fmt(row['absent_precision'])} | {fmt(row['absent_recall'])} | {fmt(row['absent_f1'])} | "
            f"{row['present_absent']} | {row['absent_present']} | {row['takeaway']} |"
        )
    lines.extend([
        "",
        "## Reading",
        "",
        "- Native VSGUI is not a clean target-absent benchmark: many gold-absent rows contain visible target text or color/instance conflicts.",
        "- Processed `native_v2_*` rows should be read as stratified task splits, not as one pooled benchmark.",
        "- The native-tuned combined verifier is the strongest raw native result.",
        "- On the filtered text+color subset, the filtered-tuned color-aware verifier is strongest, which suggests color-aware evidence is useful once obvious label/text conflicts are removed.",
        "- The current crop-level VLM verifier is not competitive; OCR candidate crops likely lose screenshot context and color/instance semantics.",
        "",
    ])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Export a compact native VSGUI extension summary.")
    parser.add_argument("--work-dir", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--output-md", required=True)
    args = parser.parse_args()

    native_dir = Path(args.work_dir) / "outputs" / "native_vsgui10k"
    raw_rows = read_csv(native_dir / "native_vsgui_results.csv")
    filtered_rows = read_csv(native_dir / "filtered_eval" / "native_text_color_balanced_ocr_aware.csv")

    rows = []
    for row in raw_rows:
        if is_key_row(row):
            rows.append(normalize_row(row, "raw"))
    for row in filtered_rows:
        if is_key_row(row):
            rows.append(normalize_row(row, "filtered"))
    rows = add_takeaways(rows)

    write_json(Path(args.output_json), {"rows": rows})
    write_csv(Path(args.output_csv), rows)
    write_md(Path(args.output_md), rows)
    print(json.dumps({"rows": len(rows), "output_md": args.output_md}, indent=2))


if __name__ == "__main__":
    main()
