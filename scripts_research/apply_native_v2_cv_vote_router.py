#!/usr/bin/env python
import argparse
import csv
import itertools
import json
import random
from collections import Counter, defaultdict
from pathlib import Path


ABSENT_STATUSES = {"absent", "not_found", "not found", "no object", "no target", "not present"}
METHOD_SPECS = [
    ("prompt", "present_absent_predictions_{model}_{split}.json"),
    ("combined_best_f1", "present_absent_predictions_{model}_{split}_combined_and_present_only_best_f1.json"),
    ("combined_default", "present_absent_predictions_{model}_{split}_combined_and_present_only.json"),
    ("color_aware", "present_absent_predictions_{model}_{split}_color_aware_native_tuned_absent_f1.json"),
    ("context_crop", "present_absent_predictions_{model}_{split}_context_crop_ocr_vlm.json"),
    ("vlm_presence_ocr_aware", "vlm_presence_predictions_{model}_vlm_presence_{split}_ocr_aware.json"),
    ("vlm_evidence", "vlm_evidence_predictions_{model}_vlm_evidence_{split}_evidence_aware.json"),
    ("ensemble", "present_absent_predictions_{model}_{split}_status_ensemble_absent_f1.json"),
]


def read_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def write_csv(path, rows, fieldnames=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = []
        for row in rows:
            for key in row:
                if key not in fieldnames:
                    fieldnames.append(key)
        if not fieldnames:
            fieldnames = ["empty"]
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def normalize_status(value, default="present"):
    text = str(value or default).strip().casefold()
    return "absent" if text in ABSENT_STATUSES else "present"


def gold_status(example):
    if "target_present" in example:
        return "present" if example["target_present"] else "absent"
    if "gold_status" in example:
        return normalize_status(example.get("gold_status"), default="present")
    return normalize_status(example.get("status"), default="present")


def predicted_status(example):
    status = str(example.get("predicted_status", "") or example.get("adjusted_predicted_status", "")).strip().casefold()
    if status in ABSENT_STATUSES:
        return "absent"
    if status == "present":
        return "present"
    return "present" if example.get("prediction", []) else "absent"


def example_key(example, fallback_index=None):
    for field in ("img_usr_tgt", "key", "id", "review_id"):
        value = example.get(field)
        if value not in {"", None}:
            return str(value)
    parts = [
        str(example.get("image", "")),
        str(example.get("target_id", "")),
        str(example.get("query_text", example.get("target", example.get("original_target", "")))),
        str(example.get("status", example.get("gold_status", ""))),
    ]
    if any(parts):
        return "|".join(parts)
    return f"index:{fallback_index}"


def safe_div(num, den):
    return num / den if den else 0.0


def metrics_from_pairs(pairs):
    confusion = Counter(pairs)
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


def evaluate(indices, gold, predictions):
    return metrics_from_pairs([(gold[idx], predictions[idx]) for idx in indices])


def load_prediction_statuses(path, keys):
    examples = read_json(path)
    by_key = {example_key(example, idx): predicted_status(example) for idx, example in enumerate(examples)}
    return [by_key.get(key, "present") for key in keys]


def available_methods(outputs_dir, model, split, keys):
    rows = []
    for name, template in METHOD_SPECS:
        path = outputs_dir / template.format(model=model, split=split)
        if path.exists():
            rows.append({
                "name": name,
                "path": path,
                "statuses": load_prediction_statuses(path, keys),
            })
    return rows


def predict_rule(methods, subset, threshold, idx):
    absent_votes = sum(1 for method_idx in subset if methods[method_idx]["statuses"][idx] == "absent")
    return "absent" if absent_votes >= threshold else "present"


def evaluate_rule(indices, gold, methods, subset, threshold):
    predictions = [predict_rule(methods, subset, threshold, idx) for idx in indices]
    return metrics_from_pairs([(gold[idx], pred) for idx, pred in zip(indices, predictions)])


def candidate_rules(methods, max_subset_size):
    n = len(methods)
    max_size = min(max_subset_size, n)
    for size in range(1, max_size + 1):
        for subset in itertools.combinations(range(n), size):
            for threshold in range(1, size + 1):
                yield subset, threshold


def rule_name(methods, subset, threshold):
    names = "+".join(methods[idx]["name"] for idx in subset)
    return f"vote_at_least_{threshold}_of_{len(subset)}::{names}"


def present_absent_rate(row):
    present_total = row["present_absent"] + row["present_present"]
    return safe_div(row["present_absent"], present_total)


def utility(row, present_absent_cost, absent_present_cost):
    total = max(row["num_examples"], 1)
    return -(
        present_absent_cost * row["present_absent"]
        + absent_present_cost * row["absent_present"]
    ) / total


def objective_key(row, objective, present_absent_cost, absent_present_cost):
    if objective == "max_f1":
        return (
            row["absent_f1"],
            row["accuracy"],
            row["absent_precision"],
            -row["present_absent"],
            -row["rule_size"],
        )
    if objective == "precision_ge_0p60":
        ok = row["absent_precision"] >= 0.60
        return (
            int(ok),
            row["absent_f1"] if ok else row["absent_precision"],
            row["accuracy"],
            -row["present_absent"],
            -row["rule_size"],
        )
    if objective == "pa_rate_le_0p25":
        rate = present_absent_rate(row)
        ok = rate <= 0.25
        return (
            int(ok),
            row["absent_f1"] if ok else -rate,
            row["accuracy"],
            -row["present_absent"],
            -row["rule_size"],
        )
    if objective == "utility_ap2_pa1":
        return (
            utility(row, present_absent_cost, absent_present_cost),
            row["absent_f1"],
            row["accuracy"],
            -row["present_absent"],
            -row["rule_size"],
        )
    raise ValueError(f"Unknown objective: {objective}")


def select_best_rule(train_indices, gold, methods, max_subset_size, objective, present_absent_cost, absent_present_cost):
    rows = []
    best = None
    for subset, threshold in candidate_rules(methods, max_subset_size):
        metrics = evaluate_rule(train_indices, gold, methods, subset, threshold)
        row = {
            "rule": rule_name(methods, subset, threshold),
            "subset": list(subset),
            "threshold": threshold,
            "rule_size": len(subset),
            **metrics,
        }
        row["present_absent_rate"] = present_absent_rate(row)
        row["utility"] = utility(row, present_absent_cost, absent_present_cost)
        rows.append(row)
        key = objective_key(row, objective, present_absent_cost, absent_present_cost)
        if best is None or key > best[0]:
            best = (key, row)
    return best[1], rows


def stratified_folds(gold, folds, seed):
    rng = random.Random(seed)
    by_status = defaultdict(list)
    for idx, status in enumerate(gold):
        by_status[status].append(idx)
    fold_rows = [[] for _ in range(folds)]
    for indices in by_status.values():
        rng.shuffle(indices)
        for pos, idx in enumerate(indices):
            fold_rows[pos % folds].append(idx)
    for rows in fold_rows:
        rows.sort()
    return fold_rows


def apply_cv_router(base_examples, gold, methods, folds, seed, max_subset_size, objective, present_absent_cost, absent_present_cost):
    fold_rows = stratified_folds(gold, folds, seed)
    output_statuses = ["present"] * len(base_examples)
    selected_rows = []
    sweep_rows = []
    for fold_idx, test_indices in enumerate(fold_rows):
        test_set = set(test_indices)
        train_indices = [idx for idx in range(len(base_examples)) if idx not in test_set]
        selected, sweep = select_best_rule(
            train_indices,
            gold,
            methods,
            max_subset_size,
            objective,
            present_absent_cost,
            absent_present_cost,
        )
        for row in sweep:
            row = dict(row)
            row["fold"] = fold_idx
            row["objective"] = objective
            row["selected"] = int(row["rule"] == selected["rule"])
            sweep_rows.append(row)
        for idx in test_indices:
            output_statuses[idx] = predict_rule(methods, selected["subset"], selected["threshold"], idx)
        selected_rows.append({
            "fold": fold_idx,
            "test_examples": len(test_indices),
            "train_examples": len(train_indices),
            **selected,
        })
    return output_statuses, selected_rows, sweep_rows


def write_md(path, payload):
    metrics = payload["metrics"]
    lines = [
        "# Native v2 CV Vote Router",
        "",
        f"- Split: `{payload['split']}`",
        f"- Model: `{payload['model']}`",
        f"- Folds: {payload['folds']}",
        f"- Objective: `{payload['objective']}`",
        f"- Available methods: {', '.join(payload['method_names'])}",
        "",
        "## Cross-Validated Metrics",
        "",
        "| Acc | Precision | Recall | F1 | P->A | A->P | P->A Rate | Utility |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|",
        (
            f"| {metrics['accuracy']:.4f} | {metrics['absent_precision']:.4f} | "
            f"{metrics['absent_recall']:.4f} | {metrics['absent_f1']:.4f} | "
            f"{metrics['present_absent']} | {metrics['absent_present']} | "
            f"{payload['present_absent_rate']:.4f} | {payload['utility']:.4f} |"
        ),
        "",
        "## Selected Fold Rules",
        "",
        "| Fold | Rule | Train F1 | Train Acc | Train P->A Rate | Test N |",
        "|---:|---|---:|---:|---:|---:|",
    ]
    for row in payload["selected_rules"]:
        lines.append(
            f"| {row['fold']} | `{row['rule']}` | {row['absent_f1']:.4f} | "
            f"{row['accuracy']:.4f} | {row['present_absent_rate']:.4f} | {row['test_examples']} |"
        )
    lines.extend([
        "",
        "## Reading",
        "",
        "- This is a cross-validated CPU router over already-run method predictions, so it tests method complementarity rather than new VLM capacity.",
        "- If the router does not beat the best single verifier, current errors are mostly shared rather than easily combinable.",
        "- If it improves F1, inspect selected rules before promoting it as a paper method; complex fold-specific rules are better framed as an analysis upper bound.",
        "",
    ])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Apply a cross-validated vote router over native v2 method predictions.")
    parser.add_argument("--work-dir", required=True)
    parser.add_argument("--split-name", required=True)
    parser.add_argument("--model-name", default="SeekUI")
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--max-subset-size", type=int, default=4)
    parser.add_argument(
        "--objective",
        default="max_f1",
        choices=["max_f1", "precision_ge_0p60", "pa_rate_le_0p25", "utility_ap2_pa1"],
    )
    parser.add_argument("--present-absent-cost", type=float, default=1.0)
    parser.add_argument("--absent-present-cost", type=float, default=2.0)
    parser.add_argument("--output", required=True)
    parser.add_argument("--metrics-output", required=True)
    parser.add_argument("--sweep-output", required=True)
    parser.add_argument("--summary-md", required=True)
    args = parser.parse_args()

    outputs_dir = Path(args.work_dir) / "outputs"
    split_path = outputs_dir / "native_vsgui10k" / "processed_v2" / "splits" / f"{args.split_name}.json"
    base_examples = read_json(split_path)
    keys = [example_key(example, idx) for idx, example in enumerate(base_examples)]
    gold = [gold_status(example) for example in base_examples]
    methods = available_methods(outputs_dir, args.model_name, args.split_name, keys)
    if not methods:
        raise SystemExit(f"No prediction methods found for {args.split_name}.")

    statuses, selected_rules, sweep_rows = apply_cv_router(
        base_examples,
        gold,
        methods,
        args.folds,
        args.seed,
        args.max_subset_size,
        args.objective,
        args.present_absent_cost,
        args.absent_present_cost,
    )
    predictions = []
    for idx, (example, status) in enumerate(zip(base_examples, statuses)):
        row = dict(example)
        row["predicted_status"] = status
        row["native_v2_cv_vote_router"] = True
        row["native_v2_cv_vote_router_folds"] = args.folds
        row["native_v2_cv_vote_router_objective"] = args.objective
        predictions.append(row)

    metrics = evaluate(range(len(base_examples)), gold, statuses)
    metrics["present_absent_rate"] = present_absent_rate(metrics)
    metrics["utility"] = utility(metrics, args.present_absent_cost, args.absent_present_cost)
    payload = {
        "split": args.split_name,
        "model": args.model_name,
        "folds": args.folds,
        "seed": args.seed,
        "max_subset_size": args.max_subset_size,
        "objective": args.objective,
        "present_absent_cost": args.present_absent_cost,
        "absent_present_cost": args.absent_present_cost,
        "method_names": [method["name"] for method in methods],
        "selected_rules": selected_rules,
        "metrics": metrics,
        "present_absent_rate": metrics["present_absent_rate"],
        "utility": metrics["utility"],
        "output": args.output,
    }

    write_json(Path(args.output), predictions)
    write_json(Path(args.metrics_output), {
        **metrics,
        "confusion": {
            "present->present": metrics["present_present"],
            "present->absent": metrics["present_absent"],
            "absent->present": metrics["absent_present"],
            "absent->absent": metrics["absent_absent"],
        },
        "selected_rules": selected_rules,
        "output": args.output,
    })
    write_csv(Path(args.sweep_output), sweep_rows)
    write_md(Path(args.summary_md), payload)
    print(json.dumps({
        "split": args.split_name,
        "methods": len(methods),
        "f1": metrics["absent_f1"],
        "output": args.output,
        "summary_md": args.summary_md,
    }, indent=2))


if __name__ == "__main__":
    main()
