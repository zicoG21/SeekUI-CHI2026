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


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def normalize_status(value, default="present"):
    text = str(value or default).strip().casefold()
    return "absent" if text in ABSENT_STATUSES else "present"


def normalize_text(text):
    return " ".join(str(text or "").casefold().replace("_", " ").replace("-", " ").split())


def target_key(example):
    target_id = str(example.get("target_id", "") or "")
    return target_id[4:] if target_id.startswith("txt_") else target_id


def get_target_text(example, target2text):
    for key in ["query_text", "target", "original_target"]:
        text = str(example.get(key, "") or "")
        if text:
            return text
    return str(target2text.get(target_key(example), "") or "")


def gold_status(example):
    if "target_present" in example:
        return "present" if example["target_present"] else "absent"
    return normalize_status(example.get("status"), default="present")


def predicted_status(example):
    status = str(example.get("predicted_status", "") or "").strip().casefold()
    if status in ABSENT_STATUSES:
        return "absent"
    if status == "present":
        return "present"
    return "present" if example.get("prediction", []) else "absent"


def example_key(example, fallback_index=None):
    for field in ("img_usr_tgt", "review_id", "id"):
        value = example.get(field)
        if value not in {"", None}:
            return str(value)
    parts = [
        str(example.get("image", "")),
        str(example.get("target_id", "")),
        str(example.get("query_text", example.get("target", ""))),
        str(example.get("gold_status", example.get("status", ""))),
    ]
    if any(parts):
        return "|".join(parts)
    return f"index:{fallback_index}"


def split_records_from_examples(examples, target2text):
    records = []
    seen = set()
    for idx, example in enumerate(examples):
        key = example_key(example, idx)
        if key in seen:
            raise ValueError(f"Duplicate split key: {key}")
        seen.add(key)
        target_text = normalize_text(get_target_text(example, target2text))
        records.append({
            "key": key,
            "gold_status": gold_status(example),
            "image": str(example.get("image", "")),
            "target_text": target_text or f"target_key:{target_key(example)}",
        })
    return records


def prediction_map(examples):
    mapping = {}
    for idx, example in enumerate(examples):
        key = example_key(example, idx)
        if key in mapping:
            raise ValueError(f"Duplicate prediction key: {key}")
        mapping[key] = predicted_status(example)
    return mapping


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
    return sorted(dev), sorted(test)


def image_majority_status(records, indices):
    counts = Counter(records[idx]["gold_status"] for idx in indices)
    return counts.most_common(1)[0][0]


def split_image_indices(records, dev_fraction, seed):
    rng = random.Random(seed)
    image_to_indices = defaultdict(list)
    for idx, record in enumerate(records):
        image_to_indices[record["image"]].append(idx)

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
    return sorted(dev), sorted(test)


def split_group_indices(records, dev_fraction, seed, field):
    rng = random.Random(seed)
    group_to_indices = defaultdict(list)
    for idx, record in enumerate(records):
        group_to_indices[record[field]].append(idx)

    by_status = defaultdict(list)
    for group, indices in group_to_indices.items():
        by_status[image_majority_status(records, indices)].append((group, indices))

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
    return sorted(dev), sorted(test)


class UnionFind:
    def __init__(self):
        self.parent = {}

    def find(self, item):
        self.parent.setdefault(item, item)
        if self.parent[item] != item:
            self.parent[item] = self.find(self.parent[item])
        return self.parent[item]

    def union(self, a, b):
        ra = self.find(a)
        rb = self.find(b)
        if ra != rb:
            self.parent[rb] = ra


def split_image_target_indices(records, dev_fraction, seed):
    rng = random.Random(seed)
    uf = UnionFind()
    for idx, record in enumerate(records):
        node = f"example:{idx}"
        image = f"image:{record['image']}"
        target = f"target:{record['target_text']}"
        uf.union(node, image)
        uf.union(node, target)

    component_to_indices = defaultdict(list)
    for idx in range(len(records)):
        component_to_indices[uf.find(f"example:{idx}")].append(idx)

    by_status = defaultdict(list)
    for component, indices in component_to_indices.items():
        by_status[image_majority_status(records, indices)].append((component, indices))

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
    return sorted(dev), sorted(test)


def image_target_component_count(records):
    uf = UnionFind()
    for idx, record in enumerate(records):
        node = f"example:{idx}"
        uf.union(node, f"image:{record['image']}")
        uf.union(node, f"target:{record['target_text']}")
    return len({uf.find(f"example:{idx}") for idx in range(len(records))})


def split_diagnostics(records, split_by):
    if split_by == "random":
        return {"split_units": len(records), "split_unit_type": "example"}
    if split_by == "image":
        return {"split_units": len({record["image"] for record in records}), "split_unit_type": "image"}
    if split_by == "target":
        return {"split_units": len({record["target_text"] for record in records}), "split_unit_type": "target"}
    if split_by == "image_target":
        return {
            "split_units": image_target_component_count(records),
            "split_unit_type": "image_target_connected_component",
        }
    return {"split_units": "", "split_unit_type": ""}


def split_indices(records, dev_fraction, seed, split_by):
    if split_by == "image":
        return split_image_indices(records, dev_fraction, seed)
    if split_by == "target":
        return split_group_indices(records, dev_fraction, seed, "target_text")
    if split_by == "image_target":
        return split_image_target_indices(records, dev_fraction, seed)
    return split_random_indices(records, dev_fraction, seed)


def evaluate(records, indices, predictions):
    missing = 0
    pairs = []
    for idx in indices:
        record = records[idx]
        pred = predictions.get(record["key"])
        if pred is None:
            missing += 1
            pred = "present"
        pairs.append((record["gold_status"], pred))
    metrics = metric_from_pairs(pairs)
    metrics["missing_predictions"] = missing
    return metrics


def percentile(values, q):
    if not values:
        return 0.0
    values = sorted(values)
    pos = (len(values) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(values) - 1)
    weight = pos - lo
    return values[lo] * (1 - weight) + values[hi] * weight


def bootstrap_ci(records, indices, baseline_predictions, model_predictions, n_bootstrap, seed):
    rng = random.Random(seed)
    n = len(indices)
    delta_f1 = []
    delta_acc = []
    for _ in range(n_bootstrap):
        sample = [indices[rng.randrange(n)] for _ in range(n)]
        baseline = evaluate(records, sample, baseline_predictions)
        model = evaluate(records, sample, model_predictions)
        delta_f1.append(model["absent_f1"] - baseline["absent_f1"])
        delta_acc.append(model["accuracy"] - baseline["accuracy"])

    def ci(values):
        return {
            "mean": sum(values) / len(values) if values else 0.0,
            "ci_low": percentile(values, 0.025),
            "ci_high": percentile(values, 0.975),
        }

    return {
        "delta_absent_f1": ci(delta_f1),
        "delta_accuracy": ci(delta_acc),
    }


def compact_row(name, split, metrics, baseline_name="", ci=None):
    row = {
        "name": name,
        "split": split,
        "baseline": baseline_name,
        "num_examples": metrics["num_examples"],
        "accuracy": metrics["accuracy"],
        "absent_precision": metrics["absent_precision"],
        "absent_recall": metrics["absent_recall"],
        "absent_f1": metrics["absent_f1"],
        "present_absent": metrics["present_absent"],
        "absent_present": metrics["absent_present"],
        "missing_predictions": metrics.get("missing_predictions", 0),
        "delta_absent_f1_mean": "",
        "delta_absent_f1_ci_low": "",
        "delta_absent_f1_ci_high": "",
        "delta_accuracy_mean": "",
        "delta_accuracy_ci_low": "",
        "delta_accuracy_ci_high": "",
    }
    if ci:
        row.update({
            "delta_absent_f1_mean": ci["delta_absent_f1"]["mean"],
            "delta_absent_f1_ci_low": ci["delta_absent_f1"]["ci_low"],
            "delta_absent_f1_ci_high": ci["delta_absent_f1"]["ci_high"],
            "delta_accuracy_mean": ci["delta_accuracy"]["mean"],
            "delta_accuracy_ci_low": ci["delta_accuracy"]["ci_low"],
            "delta_accuracy_ci_high": ci["delta_accuracy"]["ci_high"],
        })
    return row


def write_markdown(path, summary):
    if summary.get("status") == "infeasible":
        lines = [
            "# Dev/Test Status Prediction Evaluation",
            "",
            f"- Split by: {summary['split_by']}",
            "- Status: infeasible",
            f"- Reason: {summary['reason']}",
            f"- Examples: {summary['num_examples']}",
            f"- Images: {summary['num_images']}",
            f"- Targets: {summary['num_targets']}",
            f"- Split units: {summary['split_units']} ({summary['split_unit_type']})",
            "",
            "No dev/test metrics are reported for this split.",
            "",
        ]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines), encoding="utf-8")
        return

    lines = [
        "# Dev/Test Status Prediction Evaluation",
        "",
        f"- Split by: {summary['split_by']}",
        f"- Dev examples: {summary['num_dev']}",
        f"- Test examples: {summary['num_test']}",
        f"- Dev images: {summary['num_dev_images']}",
        f"- Test images: {summary['num_test_images']}",
        f"- Dev targets: {summary['num_dev_targets']}",
        f"- Test targets: {summary['num_test_targets']}",
        f"- Baseline: {summary['baseline_name']}",
        "",
        "| Split | Model | Accuracy | Absent Precision | Absent Recall | Absent F1 | Present->Absent | Absent->Present | Missing |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in summary["rows"]:
        lines.append(
            f"| {row['split']} | {row['name']} | {row['accuracy']:.4f} | "
            f"{row['absent_precision']:.4f} | {row['absent_recall']:.4f} | "
            f"{row['absent_f1']:.4f} | {row['present_absent']} | "
            f"{row['absent_present']} | {row['missing_predictions']} |"
        )

    ci_rows = [row for row in summary["rows"] if row["split"] == "test" and row["baseline"]]
    if ci_rows:
        lines.extend([
            "",
            "Bootstrap 95% CI on test vs baseline:",
            "",
            "| Model | Delta F1 Mean | CI Low | CI High | Delta Acc Mean | CI Low | CI High |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ])
        for row in ci_rows:
            lines.append(
                f"| {row['name']} | {row['delta_absent_f1_mean']:.4f} | "
                f"{row['delta_absent_f1_ci_low']:.4f} | {row['delta_absent_f1_ci_high']:.4f} | "
                f"{row['delta_accuracy_mean']:.4f} | {row['delta_accuracy_ci_low']:.4f} | "
                f"{row['delta_accuracy_ci_high']:.4f} |"
            )
    lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Matched dev/test evaluation for status prediction JSON files.")
    parser.add_argument("--prediction", action="append", required=True, help="NAME=PATH. First item is baseline unless --baseline-name is set.")
    parser.add_argument("--split-source", default="", help="Optional JSON used only to define keys, gold labels, images, and splits.")
    parser.add_argument("--baseline-name", default="")
    parser.add_argument("--target2text", default="")
    parser.add_argument("--split-by", choices=["random", "image", "target", "image_target"], default="image")
    parser.add_argument("--dev-fraction", type=float, default=0.5)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--bootstrap", type=int, default=1000)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--output-md", required=True)
    args = parser.parse_args()

    specs = []
    for spec in args.prediction:
        if "=" not in spec:
            raise ValueError(f"Prediction must be NAME=PATH, got {spec}")
        name, raw_path = spec.split("=", 1)
        specs.append((name, Path(raw_path)))
    if not specs:
        raise ValueError("At least one --prediction is required")

    split_source_path = Path(args.split_source) if args.split_source else specs[0][1]
    target2text = load_json(Path(args.target2text)) if args.target2text else {}
    records = split_records_from_examples(load_json(split_source_path), target2text)
    dev_indices, test_indices = split_indices(records, args.dev_fraction, args.seed, args.split_by)
    diagnostics = split_diagnostics(records, args.split_by)

    if not dev_indices or not test_indices:
        reason = (
            "The requested split produced an empty dev or test set. For image_target, this usually means "
            "the synthetic benchmark forms too few image-target connected components because absent-target "
            "swaps connect many screenshots and target texts."
        )
        summary = {
            "status": "infeasible",
            "reason": reason,
            "split_by": args.split_by,
            "seed": args.seed,
            "dev_fraction": args.dev_fraction,
            "num_examples": len(records),
            "num_images": len({record["image"] for record in records}),
            "num_targets": len({record["target_text"] for record in records}),
            **diagnostics,
        }
        write_json(Path(args.output_json), summary)
        write_csv(Path(args.output_csv), [{
            "status": "infeasible",
            "split_by": args.split_by,
            "reason": reason,
            "num_examples": len(records),
            "num_images": summary["num_images"],
            "num_targets": summary["num_targets"],
            "split_units": summary["split_units"],
            "split_unit_type": summary["split_unit_type"],
        }])
        write_markdown(Path(args.output_md), summary)
        print(json.dumps({
            "status": "infeasible",
            "split_by": args.split_by,
            "reason": reason,
            "output_md": args.output_md,
        }, indent=2))
        return

    predictions = {name: prediction_map(load_json(path)) for name, path in specs}
    baseline_name = args.baseline_name or specs[0][0]
    if baseline_name not in predictions:
        raise ValueError(f"Baseline {baseline_name} not found in predictions: {sorted(predictions)}")

    rows = []
    detailed = {}
    for split_name, indices in [("dev", dev_indices), ("test", test_indices)]:
        baseline_predictions = predictions[baseline_name]
        for name, pred_map in predictions.items():
            metrics = evaluate(records, indices, pred_map)
            ci = None
            baseline = ""
            if split_name == "test" and name != baseline_name:
                baseline = baseline_name
                ci = bootstrap_ci(records, indices, baseline_predictions, pred_map, args.bootstrap, args.seed + 17)
            row = compact_row(name, split_name, metrics, baseline, ci)
            rows.append(row)
            detailed[f"{split_name}:{name}"] = metrics

    summary = {
        "split_by": args.split_by,
        "seed": args.seed,
        "dev_fraction": args.dev_fraction,
        "baseline_name": baseline_name,
        "num_dev": len(dev_indices),
        "num_test": len(test_indices),
        "num_dev_images": len({records[idx]["image"] for idx in dev_indices}),
        "num_test_images": len({records[idx]["image"] for idx in test_indices}),
        "num_dev_targets": len({records[idx]["target_text"] for idx in dev_indices}),
        "num_test_targets": len({records[idx]["target_text"] for idx in test_indices}),
        **diagnostics,
        "prediction_files": {name: str(path) for name, path in specs},
        "rows": rows,
        "metrics": detailed,
    }

    write_json(Path(args.output_json), summary)
    write_csv(Path(args.output_csv), rows)
    write_markdown(Path(args.output_md), summary)
    print(json.dumps({
        "output_json": args.output_json,
        "output_csv": args.output_csv,
        "output_md": args.output_md,
        "split_by": args.split_by,
        "models": [name for name, _ in specs],
    }, indent=2))


if __name__ == "__main__":
    main()
