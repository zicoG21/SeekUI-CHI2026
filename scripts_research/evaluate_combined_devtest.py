#!/usr/bin/env python
import argparse
import json
import random
from collections import Counter, defaultdict
from pathlib import Path

from apply_combined_verifier import (
    apply_thresholds,
    load_evidence,
    load_json,
    load_ocr_candidates,
    score_records,
    threshold_values,
    write_csv,
    write_json,
)


def gold_status_from_record(record):
    return record["gold_status"]


def safe_div(num, den):
    return num / den if den else 0.0


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


def split_random_indices(records, dev_fraction, seed):
    rng = random.Random(seed)
    by_gold = defaultdict(list)
    for idx, record in enumerate(records):
        by_gold[record["gold_status"]].append(idx)

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


def image_majority_status(records, indices):
    counts = Counter(records[idx]["gold_status"] for idx in indices)
    return counts.most_common(1)[0][0]


def split_image_indices(records, dev_fraction, seed):
    rng = random.Random(seed)
    image_to_indices = defaultdict(list)
    for idx, record in enumerate(records):
        image_to_indices[record["example"].get("image", "")].append(idx)

    by_status = defaultdict(list)
    for image, indices in image_to_indices.items():
        by_status[image_majority_status(records, indices)].append((image, indices))

    dev = []
    test = []
    for groups in by_status.values():
        groups = list(groups)
        rng.shuffle(groups)
        n_dev = round(len(groups) * dev_fraction)
        for _, indices in groups[:n_dev]:
            dev.extend(indices)
        for _, indices in groups[n_dev:]:
            test.extend(indices)
    dev.sort()
    test.sort()
    return dev, test


def split_indices(records, dev_fraction, seed, split_by):
    if split_by == "image":
        return split_image_indices(records, dev_fraction, seed)
    return split_random_indices(records, dev_fraction, seed)


def subset_records(records, indices):
    return [records[idx] for idx in indices]


def evaluate_prompt(records):
    return metric_from_pairs((record["gold_status"], record["original_status"]) for record in records)


def evaluate_combined(records, cog_threshold, ocr_threshold, rule, mode):
    _, metrics, _ = apply_thresholds(records, cog_threshold, ocr_threshold, rule, mode)
    confusion = metrics.get("confusion", {})
    metrics["present_present"] = confusion.get("present->present", 0)
    metrics["present_absent"] = confusion.get("present->absent", 0)
    metrics["absent_present"] = confusion.get("absent->present", 0)
    metrics["absent_absent"] = confusion.get("absent->absent", 0)
    return metrics


def tune_thresholds(records, cog_values, ocr_values, rule, mode, optimize_metric):
    rows = []
    for cog_threshold in cog_values:
        for ocr_threshold in ocr_values:
            metrics = evaluate_combined(records, cog_threshold, ocr_threshold, rule, mode)
            rows.append({
                "cognitive_threshold": cog_threshold,
                "ocr_threshold": ocr_threshold,
                **metrics,
            })
    best = max(
        rows,
        key=lambda row: (
            row[optimize_metric],
            row["accuracy"],
            -row["changed_predictions"],
        ),
    )
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


def bootstrap_ci(records, cog_threshold, ocr_threshold, rule, mode, n_bootstrap, seed):
    rng = random.Random(seed)
    prompt_f1 = []
    combined_f1 = []
    delta_f1 = []
    prompt_acc = []
    combined_acc = []
    delta_acc = []
    n = len(records)
    for _ in range(n_bootstrap):
        sample = [records[rng.randrange(n)] for _ in range(n)]
        prompt = evaluate_prompt(sample)
        combined = evaluate_combined(sample, cog_threshold, ocr_threshold, rule, mode)
        prompt_f1.append(prompt["absent_f1"])
        combined_f1.append(combined["absent_f1"])
        delta_f1.append(combined["absent_f1"] - prompt["absent_f1"])
        prompt_acc.append(prompt["accuracy"])
        combined_acc.append(combined["accuracy"])
        delta_acc.append(combined["accuracy"] - prompt["accuracy"])

    def ci(values):
        return {
            "mean": sum(values) / len(values) if values else 0.0,
            "ci_low": percentile(values, 0.025),
            "ci_high": percentile(values, 0.975),
        }

    return {
        "prompt_absent_f1": ci(prompt_f1),
        "combined_absent_f1": ci(combined_f1),
        "delta_absent_f1": ci(delta_f1),
        "prompt_accuracy": ci(prompt_acc),
        "combined_accuracy": ci(combined_acc),
        "delta_accuracy": ci(delta_acc),
    }


def compact_metrics(name, split, variant, thresholds, metrics):
    return {
        "name": name,
        "split": split,
        "variant": variant,
        "cognitive_threshold": thresholds.get("cognitive", ""),
        "ocr_threshold": thresholds.get("ocr", ""),
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
    lines = ["# Dev/Test Combined Verifier Evaluation", ""]
    for summary in summaries:
        lines.extend([
            f"## {summary['name']} ({summary['rule']}, {summary['mode']})",
            "",
            f"- Split by: {summary['split_by']}",
            f"- Dev examples: {summary['num_dev']}",
            f"- Test examples: {summary['num_test']}",
            f"- Dev images: {summary['num_dev_images']}",
            f"- Test images: {summary['num_test_images']}",
            f"- Selected cognitive threshold on dev: {summary['selected_cognitive_threshold']}",
            f"- Selected OCR threshold on dev: {summary['selected_ocr_threshold']}",
            f"- Optimize metric: {summary['optimize_metric']}",
            "",
            "| Split | Variant | Cog Thresh | OCR Thresh | Accuracy | Absent Precision | Absent Recall | Absent F1 | Changed | Present->Absent | Absent->Present |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ])
        for row in summary["metric_rows"]:
            lines.append(
                f"| {row['split']} | {row['variant']} | {row['cognitive_threshold']} | {row['ocr_threshold']} | "
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
    parser = argparse.ArgumentParser(description="Dev/test evaluation for combined cognitive + OCR verifier.")
    parser.add_argument("--model", action="append", required=True, help="NAME=PREDICTIONS:EVIDENCE. Can repeat.")
    parser.add_argument("--ocr-candidates", required=True)
    parser.add_argument("--target2text", default="")
    parser.add_argument("--rule", choices=["or", "and"], default="and")
    parser.add_argument("--mode", choices=["override", "present_only"], default="present_only")
    parser.add_argument("--split-by", choices=["random", "image"], default="random")
    parser.add_argument("--dev-fraction", type=float, default=0.5)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--threshold-step", type=float, default=0.05)
    parser.add_argument("--cognitive-threshold-max", type=float, default=0.3)
    parser.add_argument("--ocr-threshold-max", type=float, default=0.8)
    parser.add_argument("--min-ocr-conf", type=float, default=35.0)
    parser.add_argument("--optimize-metric", default="absent_f1", choices=["absent_f1", "accuracy", "absent_recall"])
    parser.add_argument("--bootstrap", type=int, default=1000)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--output-md", required=True)
    args = parser.parse_args()

    target2text = load_json(Path(args.target2text)) if args.target2text else {}
    ocr_by_image = load_ocr_candidates(Path(args.ocr_candidates))
    cog_values = threshold_values(0.0, args.cognitive_threshold_max, args.threshold_step)
    ocr_values = threshold_values(0.0, args.ocr_threshold_max, args.threshold_step)

    all_rows = []
    summaries = []
    for spec in args.model:
        if "=" not in spec or ":" not in spec:
            raise ValueError(f"Model spec must be NAME=PREDICTIONS:EVIDENCE, got: {spec}")
        name, rest = spec.split("=", 1)
        predictions_path, evidence_path = rest.split(":", 1)
        records, missing_evidence, missing_ocr_images = score_records(
            load_json(Path(predictions_path)),
            target2text,
            load_evidence(Path(evidence_path)),
            ocr_by_image,
            args.min_ocr_conf,
        )
        dev_indices, test_indices = split_indices(records, args.dev_fraction, args.seed, args.split_by)
        dev_records = subset_records(records, dev_indices)
        test_records = subset_records(records, test_indices)

        best_dev, dev_sweep = tune_thresholds(
            dev_records,
            cog_values,
            ocr_values,
            args.rule,
            args.mode,
            args.optimize_metric,
        )
        cog_threshold = best_dev["cognitive_threshold"]
        ocr_threshold = best_dev["ocr_threshold"]

        prompt_dev = evaluate_prompt(dev_records)
        combined_dev = evaluate_combined(dev_records, cog_threshold, ocr_threshold, args.rule, args.mode)
        prompt_test = evaluate_prompt(test_records)
        combined_test = evaluate_combined(test_records, cog_threshold, ocr_threshold, args.rule, args.mode)
        ci = bootstrap_ci(
            test_records,
            cog_threshold,
            ocr_threshold,
            args.rule,
            args.mode,
            args.bootstrap,
            args.seed + 17,
        )

        metric_rows = [
            compact_metrics(name, "dev", "prompt_only", {}, prompt_dev),
            compact_metrics(name, "dev", f"combined_{args.rule}", {"cognitive": cog_threshold, "ocr": ocr_threshold}, combined_dev),
            compact_metrics(name, "test", "prompt_only", {}, prompt_test),
            compact_metrics(name, "test", f"combined_{args.rule}", {"cognitive": cog_threshold, "ocr": ocr_threshold}, combined_test),
        ]
        all_rows.extend(metric_rows)
        summaries.append({
            "name": name,
            "rule": args.rule,
            "mode": args.mode,
            "split_by": args.split_by,
            "num_dev": len(dev_records),
            "num_test": len(test_records),
            "num_dev_images": len({record["example"].get("image", "") for record in dev_records}),
            "num_test_images": len({record["example"].get("image", "") for record in test_records}),
            "selected_cognitive_threshold": cog_threshold,
            "selected_ocr_threshold": ocr_threshold,
            "optimize_metric": args.optimize_metric,
            "missing_evidence": missing_evidence,
            "missing_ocr_images": missing_ocr_images,
            "metric_rows": metric_rows,
            "bootstrap_ci": ci,
            "dev_sweep": dev_sweep,
        })

    write_json(Path(args.output_json), {
        "rule": args.rule,
        "mode": args.mode,
        "split_by": args.split_by,
        "seed": args.seed,
        "summaries": summaries,
    })
    write_csv(Path(args.output_csv), all_rows)
    write_summary_md(Path(args.output_md), summaries)
    print(json.dumps({
        "output_json": args.output_json,
        "output_csv": args.output_csv,
        "output_md": args.output_md,
        "models": [summary["name"] for summary in summaries],
    }, indent=2))


if __name__ == "__main__":
    main()
