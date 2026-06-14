#!/usr/bin/env python
import argparse
import csv
import json
import random
from collections import Counter, defaultdict
from pathlib import Path


ABSENT_STATUSES = {"absent", "not_found", "not found", "no object", "no target", "not present"}
VISIBLE_TEXT_BUCKETS = {"exact_text_visible", "substring_text_visible", "strong_ocr_match"}
COLOR_INSTANCE_BUCKETS = {"color_ignored_exact_text_visible", "color_ignored_substring_visible"}
CONFLICT_BUCKETS = VISIBLE_TEXT_BUCKETS | COLOR_INSTANCE_BUCKETS


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys()) if rows else ["empty"]
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


def evaluate_rows(rows):
    confusion = Counter((row["gold"], row["pred"]) for row in rows)
    tp = confusion[("absent", "absent")]
    fp = confusion[("present", "absent")]
    fn = confusion[("absent", "present")]
    tn = confusion[("present", "present")]
    total = tp + fp + fn + tn
    precision = safe_div(tp, tp + fp)
    recall = safe_div(tp, tp + fn)
    f1 = safe_div(2 * precision * recall, precision + recall)
    return {
        "num_examples": total,
        "accuracy": safe_div(tp + tn, total),
        "absent_precision": precision,
        "absent_recall": recall,
        "absent_f1": f1,
        "present_absent": fp,
        "absent_present": fn,
        "present_present": tn,
        "absent_absent": tp,
    }


def retasked_gold(original_gold, bucket, view):
    if view == "native_original":
        return original_gold, True
    if original_gold == "present":
        return "present", True
    if view == "clean_absent_only":
        return ("absent", True) if bucket not in CONFLICT_BUCKETS else ("absent", False)
    if view == "visible_text_as_present":
        return ("present", True) if bucket in VISIBLE_TEXT_BUCKETS else ("absent", True)
    if view == "color_instance_as_present":
        return ("present", True) if bucket in COLOR_INSTANCE_BUCKETS else ("absent", True)
    if view == "all_visible_conflicts_as_present":
        return ("present", True) if bucket in CONFLICT_BUCKETS else ("absent", True)
    if view == "color_instance_only":
        return ("absent", True) if bucket in COLOR_INSTANCE_BUCKETS else ("absent", False)
    raise ValueError(f"Unknown view: {view}")


def audit_by_index(path):
    data = load_json(Path(path))
    return {int(row["index"]): row for row in data.get("rows", [])}


def candidate_prediction_files(outputs, model, split):
    patterns = [
        (f"present_absent_predictions_{model}_{split}.json", "prompt"),
        (f"present_absent_predictions_{model}_{split}_combined_*.json", "combined"),
        (f"present_absent_predictions_{model}_{split}_color_aware_*.json", "color_aware"),
        (f"present_absent_predictions_{model}_{split}_crop_ocr_vlm.json", "crop_vlm"),
        (f"present_absent_predictions_{model}_{split}_context_crop_ocr_vlm.json", "context_crop_vlm"),
        (f"present_absent_predictions_{model}_{split}_status_ensemble_*.json", "ensemble"),
        (f"present_absent_predictions_{model}_{split}_native_supervised_calibrated_*.json", "supervised_calibrated"),
        (f"present_absent_predictions_{model}_{split}_native_task_routed_*.json", "task_routed"),
        (f"vlm_presence_predictions_{model}_vlm_presence_{split}_*.json", "vlm_presence"),
        (f"vlm_evidence_predictions_{model}_vlm_evidence_{split}_*.json", "vlm_evidence"),
    ]
    skip_suffixes = (
        "_status_eval.json",
        "_selected_threshold.json",
        "_selected_profile.json",
        "_selected_rule.json",
        "_mapping.json",
    )
    rows = []
    for pattern, family in patterns:
        for path in sorted(outputs.glob(pattern)):
            if path.name.endswith(skip_suffixes):
                continue
            if path.name.startswith("present_absent_predictions_"):
                variant = path.name.removeprefix(f"present_absent_predictions_{model}_").removesuffix(".json")
            elif path.name.startswith("vlm_presence_predictions_"):
                variant = path.name.removeprefix(f"vlm_presence_predictions_{model}_").removesuffix(".json")
            else:
                variant = path.name.removeprefix(f"vlm_evidence_predictions_{model}_").removesuffix(".json")
            item = {"family": family, "variant": variant, "path": path}
            if item not in rows:
                rows.append(item)
    return rows


def build_rows(base, candidates, audit_rows, view):
    rows = []
    for idx, example in enumerate(base):
        bucket = audit_rows.get(idx, {}).get("visibility_bucket", "") or "present_or_missing"
        gold, keep = retasked_gold(gold_status(example), bucket, view)
        if not keep:
            continue
        for candidate in candidates:
            rows.append({
                "index": idx,
                "bucket": bucket,
                "gold": gold,
                "variant": candidate["variant"],
                "family": candidate["family"],
                "pred": predicted_status(candidate["data"][idx]),
            })
    return rows


def select_mapping(train_rows, metric, fallback_variant):
    grouped = defaultdict(list)
    for row in train_rows:
        grouped[(row["bucket"], row["variant"], row["family"])].append(row)
    by_bucket = defaultdict(list)
    for (bucket, variant, family), rows in grouped.items():
        metrics = evaluate_rows(rows)
        by_bucket[bucket].append({"bucket": bucket, "variant": variant, "family": family, **metrics})
    mapping = {}
    score_rows = []
    for bucket, candidates in by_bucket.items():
        score_rows.extend(candidates)
        best = max(
            candidates,
            key=lambda row: (
                row.get(metric, -1),
                row["absent_f1"],
                row["accuracy"],
                -row["present_absent"],
            ),
        )
        mapping[bucket] = best
    if "present_or_missing" not in mapping:
        mapping["present_or_missing"] = {"bucket": "present_or_missing", "variant": fallback_variant, "family": "fallback"}
    return mapping, score_rows


def apply_mapping(test_indices, base, candidates_by_variant, audit_rows, view, mapping, fallback_variant):
    rows = []
    output_examples = []
    route_counts = Counter()
    for idx in test_indices:
        example = base[idx]
        bucket = audit_rows.get(idx, {}).get("visibility_bucket", "") or "present_or_missing"
        gold, keep = retasked_gold(gold_status(example), bucket, view)
        if not keep:
            continue
        variant = mapping.get(bucket, {}).get("variant", fallback_variant)
        chosen = candidates_by_variant[variant][idx]
        pred = predicted_status(chosen)
        rows.append({"index": idx, "bucket": bucket, "gold": gold, "pred": pred, "variant": variant})
        result = dict(example)
        result["predicted_status"] = pred
        result["native_cv_bucket_router_view"] = view
        result["native_cv_bucket_router_bucket"] = bucket
        result["native_cv_bucket_router_variant"] = variant
        output_examples.append(result)
        route_counts[variant] += 1
    return rows, output_examples, route_counts


def cross_validate(base, candidates, audit_rows, view, metric, folds, seed, fallback_variant):
    rng = random.Random(seed)
    indices = list(range(len(base)))
    rng.shuffle(indices)
    candidates_by_variant = {candidate["variant"]: candidate["data"] for candidate in candidates}
    all_eval_rows = []
    all_output_examples = []
    all_score_rows = []
    route_counts = Counter()
    fold_summaries = []
    for fold in range(folds):
        test_indices = [idx for pos, idx in enumerate(indices) if pos % folds == fold]
        train_indices = set(indices) - set(test_indices)
        train_candidates = []
        for candidate in candidates:
            train_candidates.append(candidate)
        train_rows = [row for row in build_rows(base, train_candidates, audit_rows, view) if row["index"] in train_indices]
        mapping, score_rows = select_mapping(train_rows, metric, fallback_variant)
        test_rows, output_examples, counts = apply_mapping(
            test_indices,
            base,
            candidates_by_variant,
            audit_rows,
            view,
            mapping,
            fallback_variant,
        )
        fold_metrics = evaluate_rows(test_rows)
        fold_metrics["fold"] = fold
        fold_summaries.append(fold_metrics)
        all_eval_rows.extend({**row, "fold": fold} for row in test_rows)
        all_output_examples.extend(output_examples)
        all_score_rows.extend({**row, "fold": fold} for row in score_rows)
        route_counts.update(counts)
    metrics = evaluate_rows(all_eval_rows)
    return metrics, fold_summaries, all_eval_rows, all_output_examples, all_score_rows, route_counts


def write_md(path, rows):
    lines = [
        "# Native Cross-Validated Bucket Router",
        "",
        "Each fold selects the best verifier per OCR-visibility bucket on train rows and evaluates on held-out rows.",
        "",
        "| View | N | Acc | Prec. | Rec. | F1 | P->A | A->P |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['view']} | {row['num_examples']} | {row['accuracy']:.4f} | "
            f"{row['absent_precision']:.4f} | {row['absent_recall']:.4f} | "
            f"{row['absent_f1']:.4f} | {row['present_absent']} | {row['absent_present']} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Evaluate a cross-validated native bucket router.")
    parser.add_argument("--work-dir", required=True)
    parser.add_argument("--split-name", default="native_text_color_balanced")
    parser.add_argument("--model-name", default="SeekUI")
    parser.add_argument("--audit-json", required=True)
    parser.add_argument("--selection-metric", default="absent_f1", choices=["absent_f1", "accuracy", "absent_precision", "absent_recall"])
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument("--seed", type=int, default=20260614)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--output-md", required=True)
    args = parser.parse_args()

    outputs = Path(args.work_dir) / "outputs"
    base = load_json(outputs / f"present_absent_predictions_{args.model_name}_{args.split_name}.json")
    audit_rows = audit_by_index(Path(args.audit_json))
    candidates = []
    for item in candidate_prediction_files(outputs, args.model_name, args.split_name):
        data = load_json(item["path"])
        if len(data) == len(base):
            candidates.append({**item, "data": data})
    fallback_variant = args.split_name
    views = [
        "native_original",
        "clean_absent_only",
        "visible_text_as_present",
        "color_instance_as_present",
        "all_visible_conflicts_as_present",
        "color_instance_only",
    ]
    rows = []
    details = {}
    for view in views:
        metrics, folds, eval_rows, output_examples, score_rows, route_counts = cross_validate(
            base,
            candidates,
            audit_rows,
            view,
            args.selection_metric,
            args.folds,
            args.seed,
            fallback_variant,
        )
        row = {"view": view, **metrics}
        rows.append(row)
        details[view] = {
            "folds": folds,
            "route_counts": dict(route_counts),
            "eval_rows": eval_rows,
            "bucket_score_rows": score_rows[:500],
        }
        out_base = outputs / f"present_absent_predictions_{args.model_name}_{args.split_name}_native_cv_bucket_router_{view}_{args.selection_metric}"
        write_json(out_base.with_suffix(".json"), output_examples)
        write_json(Path(str(out_base) + "_status_eval.json"), {
            "num_examples": metrics["num_examples"],
            "confusion": {
                "present->present": metrics["present_present"],
                "present->absent": metrics["present_absent"],
                "absent->present": metrics["absent_present"],
                "absent->absent": metrics["absent_absent"],
            },
            "accuracy": metrics["accuracy"],
            "absent_precision": metrics["absent_precision"],
            "absent_recall": metrics["absent_recall"],
            "absent_f1": metrics["absent_f1"],
            "view": view,
            "selection_metric": args.selection_metric,
        })
    rows.sort(key=lambda row: (-row["absent_f1"], -row["accuracy"], row["view"]))
    write_json(Path(args.output_json), {"rows": rows, "details": details})
    write_csv(Path(args.output_csv), rows)
    write_md(Path(args.output_md), rows)
    print(json.dumps({"rows": len(rows), "output_md": args.output_md}, indent=2))


if __name__ == "__main__":
    main()
