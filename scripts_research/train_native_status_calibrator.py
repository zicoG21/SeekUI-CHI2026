#!/usr/bin/env python
import argparse
import csv
import json
import math
import random
from collections import Counter
from pathlib import Path


ABSENT_STATUSES = {"absent", "not_found", "not found", "no object", "no target", "not present"}
CONFLICT_BUCKETS = {
    "exact_text_visible",
    "substring_text_visible",
    "strong_ocr_match",
    "color_ignored_exact_text_visible",
    "color_ignored_substring_visible",
}
COLOR_INSTANCE_BUCKETS = {
    "color_ignored_exact_text_visible",
    "color_ignored_substring_visible",
}


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


def safe_float(value, default=0.0):
    try:
        if value in {"", None}:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_div(num, den):
    return num / den if den else 0.0


def audit_by_index(path):
    data = load_json(Path(path))
    return {int(row["index"]): row for row in data.get("rows", [])}


def retasked_gold(original_gold, bucket, view):
    if view == "native_original":
        return original_gold, True
    if original_gold == "present":
        return "present", True
    if view == "clean_absent_only":
        return ("absent", True) if bucket not in CONFLICT_BUCKETS else ("absent", False)
    if view == "color_instance_as_present":
        return ("present", True) if bucket in COLOR_INSTANCE_BUCKETS else ("absent", True)
    if view == "all_visible_conflicts_as_present":
        return ("present", True) if bucket in CONFLICT_BUCKETS else ("absent", True)
    if view == "color_instance_only":
        return ("absent", True) if bucket in COLOR_INSTANCE_BUCKETS else ("absent", False)
    raise ValueError(f"Unknown view: {view}")


def sigmoid(value):
    if value >= 0:
        z = math.exp(-value)
        return 1.0 / (1.0 + z)
    z = math.exp(value)
    return z / (1.0 + z)


def status_feature(example):
    return 1.0 if predicted_status(example) == "absent" else 0.0


def query_color_feature(example):
    text = str(example.get("query_text") or example.get("target") or example.get("original_target") or "").casefold()
    return 1.0 if text.split()[:1] and text.split()[0] in {
        "red", "blue", "green", "yellow", "black", "white", "gray", "grey", "orange", "purple",
        "pink", "brown", "cyan", "magenta", "teal", "violet", "gold", "silver",
    } else 0.0


def features_for(idx, base, primary, secondary, tertiary):
    return [
        1.0,
        status_feature(base),
        status_feature(primary),
        status_feature(secondary),
        status_feature(tertiary),
        safe_float(primary.get("path_best_evidence"), -1.0),
        safe_float(primary.get("color_aware_score"), -1.0),
        safe_float(primary.get("color_aware_text_score"), -1.0),
        safe_float(primary.get("color_aware_color_score"), -1.0),
        safe_float(secondary.get("candidate_crop_count"), 0.0),
        safe_float(secondary.get("candidate_crop_present_count"), 0.0),
        query_color_feature(base),
    ]


def standardize(train_x, test_x):
    if not train_x:
        return train_x, test_x
    dims = len(train_x[0])
    means = [0.0] * dims
    stds = [1.0] * dims
    for dim in range(1, dims):
        values = [row[dim] for row in train_x]
        mean = sum(values) / len(values)
        var = sum((value - mean) ** 2 for value in values) / max(1, len(values))
        std = math.sqrt(var) or 1.0
        means[dim] = mean
        stds[dim] = std
    def transform(rows):
        out = []
        for row in rows:
            new = list(row)
            for dim in range(1, dims):
                new[dim] = (new[dim] - means[dim]) / stds[dim]
            out.append(new)
        return out
    return transform(train_x), transform(test_x)


def fit_logistic(x_rows, y_rows, epochs, lr, l2):
    dims = len(x_rows[0])
    weights = [0.0] * dims
    n = len(x_rows)
    for _ in range(epochs):
        grad = [0.0] * dims
        for x, y in zip(x_rows, y_rows):
            pred = sigmoid(sum(w * value for w, value in zip(weights, x)))
            error = pred - y
            for dim, value in enumerate(x):
                grad[dim] += error * value
        for dim in range(dims):
            penalty = l2 * weights[dim] if dim else 0.0
            weights[dim] -= lr * ((grad[dim] / n) + penalty)
    return weights


def predict_probs(weights, x_rows):
    return [sigmoid(sum(w * value for w, value in zip(weights, x))) for x in x_rows]


def metric_for_threshold(y_true, probs, threshold):
    confusion = Counter()
    for y, prob in zip(y_true, probs):
        gold = "absent" if y == 1 else "present"
        pred = "absent" if prob >= threshold else "present"
        confusion[(gold, pred)] += 1
    tp = confusion[("absent", "absent")]
    fp = confusion[("present", "absent")]
    fn = confusion[("absent", "present")]
    tn = confusion[("present", "present")]
    total = tp + fp + fn + tn
    precision = safe_div(tp, tp + fp)
    recall = safe_div(tp, tp + fn)
    f1 = safe_div(2 * precision * recall, precision + recall)
    return {
        "threshold": threshold,
        "num_examples": total,
        "accuracy": safe_div(tp + tn, total),
        "absent_precision": precision,
        "absent_recall": recall,
        "absent_f1": f1,
        "present_absent": fp,
        "absent_present": fn,
    }


def select_threshold(y_true, probs):
    best = None
    for step in range(0, 101):
        threshold = step / 100
        metrics = metric_for_threshold(y_true, probs, threshold)
        if best is None or (
            metrics["absent_f1"],
            metrics["accuracy"],
            -metrics["present_absent"],
        ) > (
            best["absent_f1"],
            best["accuracy"],
            -best["present_absent"],
        ):
            best = metrics
    return best["threshold"]


def build_dataset(base, primary, secondary, tertiary, audit_rows, view):
    rows = []
    for idx, examples in enumerate(zip(base, primary, secondary, tertiary)):
        b, p, s, t = examples
        bucket = audit_rows.get(idx, {}).get("visibility_bucket", "")
        gold, keep = retasked_gold(gold_status(b), bucket, view)
        if not keep:
            continue
        rows.append({
            "index": idx,
            "x": features_for(idx, b, p, s, t),
            "y": 1 if gold == "absent" else 0,
            "gold": gold,
            "bucket": bucket,
        })
    return rows


def cross_validate(rows, folds, seed, epochs, lr, l2):
    rng = random.Random(seed)
    shuffled = list(rows)
    rng.shuffle(shuffled)
    predictions = []
    fold_summaries = []
    for fold in range(folds):
        test = [row for pos, row in enumerate(shuffled) if pos % folds == fold]
        train = [row for pos, row in enumerate(shuffled) if pos % folds != fold]
        if not test or not train:
            continue
        train_x = [row["x"] for row in train]
        test_x = [row["x"] for row in test]
        train_y = [row["y"] for row in train]
        train_x, test_x = standardize(train_x, test_x)
        weights = fit_logistic(train_x, train_y, epochs, lr, l2)
        train_probs = predict_probs(weights, train_x)
        threshold = select_threshold(train_y, train_probs)
        test_probs = predict_probs(weights, test_x)
        fold_metrics = metric_for_threshold([row["y"] for row in test], test_probs, threshold)
        fold_metrics["fold"] = fold
        fold_summaries.append(fold_metrics)
        for row, prob in zip(test, test_probs):
            predictions.append({**row, "prob_absent": prob, "pred": 1 if prob >= threshold else 0, "threshold": threshold, "fold": fold})
    metrics = metric_for_threshold([row["y"] for row in predictions], [row["prob_absent"] for row in predictions], 0.5)
    # Use per-row fold thresholds, not a global 0.5 threshold.
    confusion = Counter()
    for row in predictions:
        gold = "absent" if row["y"] else "present"
        pred = "absent" if row["pred"] else "present"
        confusion[(gold, pred)] += 1
    tp = confusion[("absent", "absent")]
    fp = confusion[("present", "absent")]
    fn = confusion[("absent", "present")]
    tn = confusion[("present", "present")]
    total = tp + fp + fn + tn
    precision = safe_div(tp, tp + fp)
    recall = safe_div(tp, tp + fn)
    f1 = safe_div(2 * precision * recall, precision + recall)
    metrics.update({
        "num_examples": total,
        "accuracy": safe_div(tp + tn, total),
        "absent_precision": precision,
        "absent_recall": recall,
        "absent_f1": f1,
        "present_absent": fp,
        "absent_present": fn,
    })
    return metrics, fold_summaries, predictions


def sweep_rows_for_predictions(view, predictions):
    y_true = [row["y"] for row in predictions]
    probs = [row["prob_absent"] for row in predictions]
    rows = []
    for step in range(0, 101):
        metrics = metric_for_threshold(y_true, probs, step / 100)
        rows.append({"view": view, **metrics})
    return rows


def compact_prediction_rows(view, predictions):
    rows = []
    for row in sorted(predictions, key=lambda item: int(item["index"])):
        rows.append({
            "view": view,
            "index": row["index"],
            "gold": row["gold"],
            "bucket": row["bucket"],
            "fold": row["fold"],
            "fold_threshold": row["threshold"],
            "prob_absent": row["prob_absent"],
            "predicted_status": "absent" if row["pred"] else "present",
        })
    return rows


def constraint_summary_rows(sweep_rows):
    constraints = [
        ("max_f1", lambda row: True),
        ("precision_ge_0.55", lambda row: row["absent_precision"] >= 0.55),
        ("precision_ge_0.60", lambda row: row["absent_precision"] >= 0.60),
        ("precision_ge_0.65", lambda row: row["absent_precision"] >= 0.65),
        ("pa_le_150", lambda row: row["present_absent"] <= 150),
        ("pa_le_100", lambda row: row["present_absent"] <= 100),
        ("pa_le_75", lambda row: row["present_absent"] <= 75),
    ]
    views = sorted({row["view"] for row in sweep_rows})
    out = []
    for view in views:
        view_rows = [row for row in sweep_rows if row["view"] == view]
        for name, keep in constraints:
            candidates = [row for row in view_rows if keep(row)]
            if not candidates:
                continue
            best = max(
                candidates,
                key=lambda row: (
                    row["absent_f1"],
                    row["accuracy"],
                    row["absent_precision"],
                    -row["present_absent"],
                ),
            )
            out.append({"view": view, "constraint": name, **best})
    return out


def write_md(path, rows):
    lines = [
        "# Native Supervised Status Calibration",
        "",
        "K-fold logistic calibration over existing status/evidence features. This is a CPU supervised calibration baseline, not a new VLM run.",
        "",
        "| View | N | Acc | Prec. | Rec. | F1 | P->A | A->P |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['view']} | {row['num_examples']} | {row['accuracy']:.4f} | "
            f"{row['absent_precision']:.4f} | {row['absent_recall']:.4f} | {row['absent_f1']:.4f} | "
            f"{row['present_absent']} | {row['absent_present']} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_constraint_md(path, rows):
    lines = [
        "# Native Supervised Calibration Threshold Tradeoff",
        "",
        "Rows are selected from cross-validated calibrated probabilities. This shows whether the high-F1 calibrator is still useful under precision or present-rejection constraints.",
        "",
        "| View | Constraint | Threshold | Acc | Prec. | Rec. | F1 | P->A | A->P |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['view']} | {row['constraint']} | {row['threshold']:.2f} | "
            f"{row['accuracy']:.4f} | {row['absent_precision']:.4f} | "
            f"{row['absent_recall']:.4f} | {row['absent_f1']:.4f} | "
            f"{row['present_absent']} | {row['absent_present']} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Train/evaluate a CPU supervised native status calibrator.")
    parser.add_argument("--base-predictions", required=True)
    parser.add_argument("--primary-predictions", required=True)
    parser.add_argument("--secondary-predictions", required=True)
    parser.add_argument("--tertiary-predictions", required=True)
    parser.add_argument("--audit-json", required=True)
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument("--seed", type=int, default=20260614)
    parser.add_argument("--epochs", type=int, default=800)
    parser.add_argument("--lr", type=float, default=0.15)
    parser.add_argument("--l2", type=float, default=0.01)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--output-md", required=True)
    parser.add_argument("--prediction-output-csv", default="")
    parser.add_argument("--sweep-output-csv", default="")
    parser.add_argument("--constraint-output-md", default="")
    args = parser.parse_args()

    base = load_json(Path(args.base_predictions))
    primary = load_json(Path(args.primary_predictions))
    secondary = load_json(Path(args.secondary_predictions))
    tertiary = load_json(Path(args.tertiary_predictions))
    lengths = {len(base), len(primary), len(secondary), len(tertiary)}
    if len(lengths) != 1:
        raise ValueError(f"Prediction lengths differ: {sorted(lengths)}")
    audit_rows = audit_by_index(Path(args.audit_json))
    views = [
        "native_original",
        "clean_absent_only",
        "color_instance_as_present",
        "all_visible_conflicts_as_present",
        "color_instance_only",
    ]
    rows = []
    details = {}
    all_predictions = []
    all_sweeps = []
    for view in views:
        dataset = build_dataset(base, primary, secondary, tertiary, audit_rows, view)
        metrics, folds, predictions = cross_validate(dataset, args.folds, args.seed, args.epochs, args.lr, args.l2)
        metrics["view"] = view
        rows.append(metrics)
        details[view] = {"folds": folds, "num_rows": len(dataset)}
        all_predictions.extend(compact_prediction_rows(view, predictions))
        all_sweeps.extend(sweep_rows_for_predictions(view, predictions))
    rows.sort(key=lambda row: (-row["absent_f1"], -row["accuracy"], row["view"]))
    write_json(Path(args.output_json), {"rows": rows, "details": details})
    write_csv(Path(args.output_csv), rows)
    write_md(Path(args.output_md), rows)
    constraint_rows = constraint_summary_rows(all_sweeps)
    if args.prediction_output_csv:
        write_csv(Path(args.prediction_output_csv), all_predictions)
    if args.sweep_output_csv:
        write_csv(Path(args.sweep_output_csv), all_sweeps)
    if args.constraint_output_md:
        write_constraint_md(Path(args.constraint_output_md), constraint_rows)
    print(json.dumps({"rows": len(rows), "output_md": args.output_md}, indent=2))


if __name__ == "__main__":
    main()
