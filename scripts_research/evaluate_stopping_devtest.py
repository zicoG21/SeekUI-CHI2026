#!/usr/bin/env python
import argparse
import csv
import json
import random
from collections import Counter, defaultdict
from pathlib import Path


ABSENT_STATUSES = {"absent", "not_found", "not found", "no object", "no target", "not present"}


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_evidence(path):
    rows = {}
    with open(path, "r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            rows[int(row["index"])] = row
    return rows


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
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
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_div(num, den):
    return num / den if den else 0.0


def threshold_values(step):
    values = []
    value = 0.0
    while value <= 1.000001:
        values.append(round(value, 4))
        value += step
    return values


def stopping_status(original_status, score, threshold, mode):
    stopped = "absent" if score < threshold else "present"
    if mode == "present_only" and original_status == "absent":
        return original_status
    return stopped


def metric_from_pairs(pairs):
    confusion = Counter(pairs)
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
        "accuracy": safe_div(tp_absent + tn_absent, total),
        "absent_precision": precision,
        "absent_recall": recall,
        "absent_f1": f1,
        "present_present": tn_absent,
        "present_absent": fp_absent,
        "absent_present": fn_absent,
        "absent_absent": tp_absent,
    }


def model_records(predictions, evidence):
    records = []
    for idx, example in enumerate(predictions):
        row = evidence.get(idx, {})
        original = predicted_status(example)
        records.append({
            "index": idx,
            "gold": gold_status(example),
            "original": original,
            "score": safe_float(row.get("path_best_evidence")),
        })
    return records


def split_indices(records, dev_fraction, seed):
    rng = random.Random(seed)
    by_gold = defaultdict(list)
    for idx, record in enumerate(records):
        by_gold[record["gold"]].append(idx)

    dev = []
    test = []
    for indices in by_gold.values():
        indices = list(indices)
        rng.shuffle(indices)
        n_dev = round(len(indices) * dev_fraction)
        dev.extend(indices[:n_dev])
        test.extend(indices[n_dev:])
    dev.sort()
    test.sort()
    return dev, test


def evaluate_indices(records, indices, mode="prompt_only", threshold=None):
    pairs = []
    changed = 0
    for idx in indices:
        record = records[idx]
        if mode == "prompt_only":
            pred = record["original"]
        else:
            pred = stopping_status(record["original"], record["score"], threshold, mode)
        if pred != record["original"]:
            changed += 1
        pairs.append((record["gold"], pred))
    metrics = metric_from_pairs(pairs)
    metrics["changed_predictions"] = changed
    return metrics


def tune_threshold(records, indices, mode, step, optimize_metric):
    rows = []
    for threshold in threshold_values(step):
        metrics = evaluate_indices(records, indices, mode=mode, threshold=threshold)
        rows.append({"threshold": threshold, "mode": mode, **metrics})
    best = max(rows, key=lambda row: (row[optimize_metric], row["accuracy"], -row["changed_predictions"]))
    return best, rows


def percentile(values, q):
    if not values:
        return 0.0
    values = sorted(values)
    pos = (len(values) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(values) - 1)
    weight = pos - lo
    return values[lo] * (1 - weight) + values[hi] * weight


def bootstrap_ci(records, indices, threshold, mode, n_bootstrap, seed):
    rng = random.Random(seed)
    prompt_f1 = []
    stop_f1 = []
    delta_f1 = []
    prompt_acc = []
    stop_acc = []
    delta_acc = []
    n = len(indices)
    for _ in range(n_bootstrap):
        sample = [indices[rng.randrange(n)] for _ in range(n)]
        prompt = evaluate_indices(records, sample, mode="prompt_only")
        stop = evaluate_indices(records, sample, mode=mode, threshold=threshold)
        prompt_f1.append(prompt["absent_f1"])
        stop_f1.append(stop["absent_f1"])
        delta_f1.append(stop["absent_f1"] - prompt["absent_f1"])
        prompt_acc.append(prompt["accuracy"])
        stop_acc.append(stop["accuracy"])
        delta_acc.append(stop["accuracy"] - prompt["accuracy"])

    def ci(values):
        return {
            "mean": sum(values) / len(values) if values else 0.0,
            "ci_low": percentile(values, 0.025),
            "ci_high": percentile(values, 0.975),
        }

    return {
        "prompt_absent_f1": ci(prompt_f1),
        "stopping_absent_f1": ci(stop_f1),
        "delta_absent_f1": ci(delta_f1),
        "prompt_accuracy": ci(prompt_acc),
        "stopping_accuracy": ci(stop_acc),
        "delta_accuracy": ci(delta_acc),
    }


def compact_metrics(name, split, variant, threshold, metrics):
    return {
        "name": name,
        "split": split,
        "variant": variant,
        "threshold": "" if threshold is None else threshold,
        "num_examples": metrics["num_examples"],
        "accuracy": metrics["accuracy"],
        "absent_precision": metrics["absent_precision"],
        "absent_recall": metrics["absent_recall"],
        "absent_f1": metrics["absent_f1"],
        "changed_predictions": metrics.get("changed_predictions", 0),
        "present_absent": metrics["present_absent"],
        "absent_present": metrics["absent_present"],
    }


def write_summary_md(path, summaries):
    lines = ["# Dev/Test Cognitive Stopping Evaluation", ""]
    for summary in summaries:
        lines.extend([
            f"## {summary['name']} ({summary['mode']})",
            "",
            f"- Dev examples: {summary['num_dev']}",
            f"- Test examples: {summary['num_test']}",
            f"- Selected threshold on dev: {summary['selected_threshold']}",
            f"- Optimize metric: {summary['optimize_metric']}",
            "",
            "| Split | Variant | Threshold | Accuracy | Absent Precision | Absent Recall | Absent F1 | Changed | Present->Absent | Absent->Present |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ])
        for row in summary["metric_rows"]:
            lines.append(
                f"| {row['split']} | {row['variant']} | {row['threshold']} | "
                f"{row['accuracy']:.4f} | {row['absent_precision']:.4f} | "
                f"{row['absent_recall']:.4f} | {row['absent_f1']:.4f} | "
                f"{row['changed_predictions']} | {row['present_absent']} | {row['absent_present']} |"
            )
        ci = summary["bootstrap_ci"]
        lines.extend([
            "",
            "Bootstrap 95% CI on test:",
            "",
            "| Metric | Mean | CI Low | CI High |",
            "|---|---:|---:|---:|",
            (
                f"| Delta absent F1 | {ci['delta_absent_f1']['mean']:.4f} | "
                f"{ci['delta_absent_f1']['ci_low']:.4f} | {ci['delta_absent_f1']['ci_high']:.4f} |"
            ),
            (
                f"| Delta accuracy | {ci['delta_accuracy']['mean']:.4f} | "
                f"{ci['delta_accuracy']['ci_low']:.4f} | {ci['delta_accuracy']['ci_high']:.4f} |"
            ),
            "",
        ])

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Dev/test evaluation and bootstrap CI for cognitive stopping.")
    parser.add_argument("--model", action="append", required=True, help="NAME=PREDICTIONS:EVIDENCE. Can repeat.")
    parser.add_argument("--mode", choices=["override", "present_only"], default="present_only")
    parser.add_argument("--dev-fraction", type=float, default=0.5)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--threshold-step", type=float, default=0.05)
    parser.add_argument("--optimize-metric", default="absent_f1", choices=["absent_f1", "accuracy", "absent_recall"])
    parser.add_argument("--bootstrap", type=int, default=1000)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--output-md", required=True)
    args = parser.parse_args()

    all_rows = []
    summaries = []
    for spec in args.model:
        if "=" not in spec or ":" not in spec:
            raise ValueError(f"Model spec must be NAME=PREDICTIONS:EVIDENCE, got: {spec}")
        name, rest = spec.split("=", 1)
        predictions_path, evidence_path = rest.split(":", 1)
        records = model_records(load_json(Path(predictions_path)), load_evidence(Path(evidence_path)))
        dev_indices, test_indices = split_indices(records, args.dev_fraction, args.seed)

        best_dev, dev_sweep = tune_threshold(records, dev_indices, args.mode, args.threshold_step, args.optimize_metric)
        threshold = best_dev["threshold"]

        prompt_dev = evaluate_indices(records, dev_indices, mode="prompt_only")
        stop_dev = evaluate_indices(records, dev_indices, mode=args.mode, threshold=threshold)
        prompt_test = evaluate_indices(records, test_indices, mode="prompt_only")
        stop_test = evaluate_indices(records, test_indices, mode=args.mode, threshold=threshold)
        ci = bootstrap_ci(records, test_indices, threshold, args.mode, args.bootstrap, args.seed + 17)

        metric_rows = [
            compact_metrics(name, "dev", "prompt_only", None, prompt_dev),
            compact_metrics(name, "dev", args.mode, threshold, stop_dev),
            compact_metrics(name, "test", "prompt_only", None, prompt_test),
            compact_metrics(name, "test", args.mode, threshold, stop_test),
        ]
        all_rows.extend(metric_rows)
        summaries.append({
            "name": name,
            "mode": args.mode,
            "num_dev": len(dev_indices),
            "num_test": len(test_indices),
            "selected_threshold": threshold,
            "optimize_metric": args.optimize_metric,
            "prediction_file": predictions_path,
            "evidence_file": evidence_path,
            "metric_rows": metric_rows,
            "dev_sweep": dev_sweep,
            "bootstrap_ci": ci,
        })

    write_json(Path(args.output_json), {
        "mode": args.mode,
        "dev_fraction": args.dev_fraction,
        "seed": args.seed,
        "threshold_step": args.threshold_step,
        "bootstrap": args.bootstrap,
        "models": summaries,
    })
    write_csv(Path(args.output_csv), all_rows)
    write_summary_md(Path(args.output_md), summaries)
    print(f"Wrote {args.output_json}")
    print(f"Wrote {args.output_csv}")
    print(f"Wrote {args.output_md}")


if __name__ == "__main__":
    main()
