#!/usr/bin/env python
import argparse
import csv
import json
from collections import Counter
from pathlib import Path


ABSENT_STATUSES = {"absent", "not_found", "not found", "no object", "no target", "not present"}


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "split",
        "model",
        "family",
        "variant",
        "num_examples",
        "excluded_examples",
        "excluded_absent_conflicts",
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


def normalize_status(value, default="present"):
    text = str(value or default).casefold()
    return "absent" if text in ABSENT_STATUSES else "present"


def gold_status(example):
    if "target_present" in example:
        return "present" if example["target_present"] else "absent"
    return normalize_status(example.get("status"), default="present")


def predicted_status(example):
    status = str(example.get("predicted_status", "") or "").casefold()
    if status in ABSENT_STATUSES:
        return "absent"
    if status == "present":
        return "present"
    return "present" if example.get("prediction", []) else "absent"


def safe_div(num, den):
    return num / den if den else 0.0


def evaluate(examples):
    confusion = Counter()
    for example in examples:
        confusion[(gold_status(example), predicted_status(example))] += 1
    tp_absent = confusion[("absent", "absent")]
    fp_absent = confusion[("present", "absent")]
    fn_absent = confusion[("absent", "present")]
    tn_absent = confusion[("present", "present")]
    total = tp_absent + fp_absent + fn_absent + tn_absent
    precision = safe_div(tp_absent, tp_absent + fp_absent)
    recall = safe_div(tp_absent, tp_absent + fn_absent)
    f1 = safe_div(2 * precision * recall, precision + recall)
    return {
        "num_examples": total,
        "confusion": {
            "present->present": tn_absent,
            "present->absent": fp_absent,
            "absent->present": fn_absent,
            "absent->absent": tp_absent,
        },
        "accuracy": safe_div(tp_absent + tn_absent, total),
        "absent_precision": precision,
        "absent_recall": recall,
        "absent_f1": f1,
    }


def conflict_indices(audit_json):
    data = load_json(audit_json)
    return {int(row["index"]) for row in data.get("conflict_rows", [])}


def candidate_prediction_files(outputs, model, split, vlm_variant):
    rows = [
        (
            "seekui_prompt",
            split,
            outputs / f"present_absent_predictions_{model}_{split}.json",
        ),
        (
            "combined",
            f"{split}_combined_and_present_only_best_f1",
            outputs / f"present_absent_predictions_{model}_{split}_combined_and_present_only_best_f1.json",
        ),
        (
            "combined",
            f"{split}_combined_and_present_only_native_tuned_absent_f1",
            outputs / f"present_absent_predictions_{model}_{split}_combined_and_present_only_native_tuned_absent_f1.json",
        ),
        (
            "combined",
            f"{split}_combined_and_present_only",
            outputs / f"present_absent_predictions_{model}_{split}_combined_and_present_only.json",
        ),
        (
            "crop_vlm",
            f"{split}_crop_ocr_vlm",
            outputs / f"present_absent_predictions_{model}_{split}_crop_ocr_vlm.json",
        ),
        (
            "context_crop_vlm",
            f"{split}_context_crop_ocr_vlm",
            outputs / f"present_absent_predictions_{model}_{split}_context_crop_ocr_vlm.json",
        ),
        (
            "vlm_presence",
            f"vlm_presence_{split}_{vlm_variant}",
            outputs / f"vlm_presence_predictions_{model}_vlm_presence_{split}_{vlm_variant}.json",
        ),
    ]
    for path in sorted(outputs.glob(f"present_absent_predictions_{model}_{split}_color_aware_*.json")):
        if (
            path.name.endswith("_status_eval.json")
            or path.name.endswith("_selected_threshold.json")
        ):
            continue
        variant = path.name.removeprefix(f"present_absent_predictions_{model}_").removesuffix(".json")
        item = ("color_aware", variant, path)
        if item not in rows:
            rows.append(item)
    for path in sorted(outputs.glob(f"vlm_presence_predictions_{model}_vlm_presence_{split}_*.json")):
        if path.name.endswith("_status_eval.json"):
            continue
        variant = path.name.removeprefix(f"vlm_presence_predictions_{model}_").removesuffix(".json")
        item = ("vlm_presence", variant, path)
        if item not in rows:
            rows.append(item)
    for path in sorted(outputs.glob(f"vlm_evidence_predictions_{model}_vlm_evidence_{split}_*.json")):
        if path.name.endswith("_status_eval.json"):
            continue
        variant = path.name.removeprefix(f"vlm_evidence_predictions_{model}_").removesuffix(".json")
        item = ("vlm_evidence", variant, path)
        if item not in rows:
            rows.append(item)
    return rows


def row_for(split, model, family, variant, path, data, excluded, excluded_absent_conflicts):
    kept = [example for idx, example in enumerate(data) if idx not in excluded]
    metrics = evaluate(kept)
    confusion = metrics["confusion"]
    return {
        "split": split,
        "model": model,
        "family": family,
        "variant": variant,
        "num_examples": metrics["num_examples"],
        "excluded_examples": len(data) - len(kept),
        "excluded_absent_conflicts": excluded_absent_conflicts,
        "accuracy": metrics["accuracy"],
        "absent_precision": metrics["absent_precision"],
        "absent_recall": metrics["absent_recall"],
        "absent_f1": metrics["absent_f1"],
        "present_absent": confusion["present->absent"],
        "absent_present": confusion["absent->present"],
        "source": str(path),
    }


def fmt(value):
    try:
        return f"{float(value):.4f}"
    except (TypeError, ValueError):
        return ""


def write_md(path, rows, audit_json, skipped_partial):
    lines = [
        "# Filtered Native VSGUI Evaluation",
        "",
        f"- Label/text-visibility audit: `{audit_json}`",
        "- Excludes gold-absent rows with strong OCR-visible target-text evidence.",
        "- This estimates performance on a cleaner text-absence subset; it is not a replacement for manual relabeling.",
        "",
        "| Split | Model | Family | Variant | N | Excluded | Acc | Precision | Recall | F1 | P->A | A->P |",
        "|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['split']} | {row['model']} | {row['family']} | {row['variant']} | "
            f"{row['num_examples']} | {row['excluded_examples']} | {fmt(row['accuracy'])} | "
            f"{fmt(row['absent_precision'])} | {fmt(row['absent_recall'])} | {fmt(row['absent_f1'])} | "
            f"{row['present_absent']} | {row['absent_present']} |"
        )
    lines.extend([
        "",
    ])
    if skipped_partial:
        lines.extend([
            "## Skipped Partial Prediction Files",
            "",
            "| Variant | Rows | Expected Rows | Source |",
            "|---|---:|---:|---|",
        ])
        for item in skipped_partial:
            lines.append(
                f"| {item.get('variant', '')} | {item.get('rows', '')} | "
                f"{item.get('expected_rows', '')} | `{item.get('source', '')}` |"
            )
        lines.append("")
    lines.extend([
        "## Interpretation",
        "",
        "- If filtered scores rise substantially, the raw native split is partly measuring target-definition conflicts rather than simple absence.",
        "- If many absent false-present errors remain after filtering, native VSGUI still exposes a hard external forced-choice setting.",
        "",
    ])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Evaluate native VSGUI predictions after excluding OCR-visible absent conflicts.")
    parser.add_argument("--work-dir", required=True)
    parser.add_argument("--split-name", required=True)
    parser.add_argument("--model-name", default="SeekUI")
    parser.add_argument("--vlm-prompt-variant", default="ocr_aware")
    parser.add_argument("--audit-json", default="")
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--output-md", required=True)
    parser.add_argument("--include-partial", action="store_true", help="Include prediction files whose row count does not match the split.")
    args = parser.parse_args()

    outputs = Path(args.work_dir) / "outputs"
    split_json = outputs / "native_vsgui10k" / "eval_splits" / f"{args.split_name}.json"
    expected_rows = len(load_json(split_json)) if split_json.exists() else 0
    audit_json = Path(args.audit_json) if args.audit_json else (
        outputs / "native_vsgui10k" / "label_conflict_audit" /
        f"{args.split_name}_combined_and_present_only_best_f1.json"
    )
    excluded = conflict_indices(audit_json)
    rows = []
    missing = []
    skipped_partial = []
    for family, variant, path in candidate_prediction_files(outputs, args.model_name, args.split_name, args.vlm_prompt_variant):
        if path.exists():
            data = load_json(path)
            if expected_rows and len(data) != expected_rows and not args.include_partial:
                skipped_partial.append({
                    "variant": variant,
                    "rows": len(data),
                    "expected_rows": expected_rows,
                    "source": str(path),
                })
                continue
            rows.append(row_for(args.split_name, args.model_name, family, variant, path, data, excluded, len(excluded)))
        else:
            missing.append(str(path))

    write_json(Path(args.output_json), {
        "split": args.split_name,
        "model": args.model_name,
        "audit_json": str(audit_json),
        "excluded_indices": sorted(excluded),
        "missing_prediction_files": missing,
        "skipped_partial_prediction_files": skipped_partial,
        "rows": rows,
    })
    write_csv(Path(args.output_csv), rows)
    write_md(Path(args.output_md), rows, audit_json, skipped_partial)
    print(json.dumps({
        "split": args.split_name,
        "rows": len(rows),
        "excluded": len(excluded),
        "missing": len(missing),
        "skipped_partial": len(skipped_partial),
        "output_md": args.output_md,
    }, indent=2))


if __name__ == "__main__":
    main()
