#!/usr/bin/env python
import argparse
import csv
import json
import random
from collections import Counter, defaultdict
from pathlib import Path


ABSENT_STATUSES = {"absent", "not_found", "not found", "no object", "no target", "not present"}


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
        keys = []
        for row in rows:
            for key in row:
                if key not in keys:
                    keys.append(key)
        fieldnames = keys
    with open(path, "w", newline="", encoding="utf-8") as f:
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


def safe_div(num, den):
    return num / den if den else 0.0


def metrics_from_pairs(pairs):
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


def percentile(values, q):
    if not values:
        return 0.0
    values = sorted(values)
    pos = (len(values) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(values) - 1)
    weight = pos - lo
    return values[lo] * (1 - weight) + values[hi] * weight


def fmt(value):
    try:
        return f"{float(value):.4f}"
    except (TypeError, ValueError):
        return ""


def parse_prediction_arg(arg):
    if "=" not in arg:
        raise ValueError(f"Prediction must be NAME=PATH: {arg}")
    name, path = arg.split("=", 1)
    return name, Path(path)


def load_examples(path):
    examples = read_json(path)
    rows = []
    for idx, example in enumerate(examples):
        key = example_key(example, idx)
        rows.append({
            "index": idx,
            "key": key,
            "gold_status": gold_status(example),
            "image": example.get("image", ""),
            "query_text": example.get("query_text") or example.get("target") or example.get("original_target", ""),
            "source_type": example.get("source_type", ""),
            "review_id": example.get("review_id", ""),
            "img_usr_tgt": example.get("img_usr_tgt", ""),
        })
    return rows


def load_prediction_map(path):
    examples = read_json(path)
    mapping = {}
    raw = {}
    for idx, example in enumerate(examples):
        key = example_key(example, idx)
        mapping[key] = predicted_status(example)
        raw[key] = example
    return mapping, raw


def evaluate(records, predictions):
    missing = 0
    pairs = []
    for record in records:
        pred = predictions.get(record["key"])
        if pred is None:
            missing += 1
            pred = "present"
        pairs.append((record["gold_status"], pred))
    metrics = metrics_from_pairs(pairs)
    metrics["missing_predictions"] = missing
    return metrics


def bootstrap_delta(records, baseline_predictions, model_predictions, n_bootstrap, seed):
    rng = random.Random(seed)
    n = len(records)
    delta_f1 = []
    delta_acc = []
    for _ in range(n_bootstrap):
        sample = [records[rng.randrange(n)] for _ in range(n)]
        baseline = evaluate(sample, baseline_predictions)
        model = evaluate(sample, model_predictions)
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


def method_rows(records, prediction_maps, baseline_name, n_bootstrap, seed):
    baseline = prediction_maps[baseline_name]
    rows = []
    for name, predictions in prediction_maps.items():
        metrics = evaluate(records, predictions)
        row = {
            "name": name,
            **metrics,
            "baseline": "" if name == baseline_name else baseline_name,
            "delta_absent_f1_mean": "",
            "delta_absent_f1_ci_low": "",
            "delta_absent_f1_ci_high": "",
            "delta_accuracy_mean": "",
            "delta_accuracy_ci_low": "",
            "delta_accuracy_ci_high": "",
        }
        if name != baseline_name:
            ci = bootstrap_delta(records, baseline, predictions, n_bootstrap, seed)
            row.update({
                "delta_absent_f1_mean": ci["delta_absent_f1"]["mean"],
                "delta_absent_f1_ci_low": ci["delta_absent_f1"]["ci_low"],
                "delta_absent_f1_ci_high": ci["delta_absent_f1"]["ci_high"],
                "delta_accuracy_mean": ci["delta_accuracy"]["mean"],
                "delta_accuracy_ci_low": ci["delta_accuracy"]["ci_low"],
                "delta_accuracy_ci_high": ci["delta_accuracy"]["ci_high"],
            })
        rows.append(row)
    return rows


def case_base(record, predictions):
    row = {
        "index": record["index"],
        "key": record["key"],
        "review_id": record.get("review_id", ""),
        "img_usr_tgt": record.get("img_usr_tgt", ""),
        "image": record.get("image", ""),
        "query_text": record.get("query_text", ""),
        "source_type": record.get("source_type", ""),
        "gold_status": record["gold_status"],
    }
    for name, pred_map in predictions.items():
        row[f"{name}_status"] = pred_map.get(record["key"], "missing")
    return row


def mine_cases(records, prediction_maps, baseline_name, combined_name, ocr_name="", evidence_name="", limit=100):
    groups = defaultdict(list)
    baseline = prediction_maps[baseline_name]
    combined = prediction_maps.get(combined_name, {})
    ocr = prediction_maps.get(ocr_name, {}) if ocr_name else {}
    evidence = prediction_maps.get(evidence_name, {}) if evidence_name else {}

    for record in records:
        key = record["key"]
        gold = record["gold_status"]
        base = baseline.get(key, "missing")
        combo = combined.get(key, "missing")
        ocr_status = ocr.get(key, "missing") if ocr else ""
        evidence_status = evidence.get(key, "missing") if evidence else ""
        row = case_base(record, prediction_maps)

        if gold == "absent" and base == "present" and combo == "absent":
            groups["combined_corrected_absent_false_present"].append(row)
        if gold == "present" and base == "present" and combo == "absent":
            groups["combined_new_present_false_absent"].append(row)
        if gold == "absent" and base == "present" and combo == "present":
            groups["combined_kept_absent_false_present"].append(row)
        if ocr and combo != "missing" and ocr_status != "missing" and combo != ocr_status:
            groups["combined_vs_ocr_aware_disagreement"].append(row)
            if combo == gold and ocr_status != gold:
                groups["ocr_wrong_combined_correct"].append(row)
            if combo != gold and ocr_status == gold:
                groups["combined_wrong_ocr_correct"].append(row)
        if evidence:
            if evidence_status == "absent" and gold == "present":
                groups["evidence_overreject_present"].append(row)
            if evidence_status != gold and combo == gold:
                groups["evidence_wrong_combined_correct"].append(row)
            if evidence_status == gold and combo != gold:
                groups["combined_wrong_evidence_correct"].append(row)

    summary = []
    selected = {}
    for case_type, rows in sorted(groups.items()):
        selected_rows = rows[:limit]
        selected[case_type] = selected_rows
        summary.append({
            "case_type": case_type,
            "count": len(rows),
            "selected": len(selected_rows),
        })
    return summary, selected


def write_markdown(path, payload):
    lines = [
        "# Realistic Absent Validation Analysis",
        "",
        f"- Evaluation rows: {payload['num_examples']}",
        f"- Baseline: `{payload['baseline_name']}`",
        "",
        "## Metrics and Bootstrap CI",
        "",
        "| Method | Acc | Precision | Recall | F1 | P->A | A->P | Delta F1 | 95% CI | Delta Acc | 95% CI | Missing |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---|---:|",
    ]
    for row in payload["method_rows"]:
        f1_ci = ""
        acc_ci = ""
        if row.get("baseline"):
            f1_ci = f"[{fmt(row['delta_absent_f1_ci_low'])}, {fmt(row['delta_absent_f1_ci_high'])}]"
            acc_ci = f"[{fmt(row['delta_accuracy_ci_low'])}, {fmt(row['delta_accuracy_ci_high'])}]"
        lines.append(
            f"| {row['name']} | {fmt(row['accuracy'])} | {fmt(row['absent_precision'])} | "
            f"{fmt(row['absent_recall'])} | {fmt(row['absent_f1'])} | {row['present_absent']} | "
            f"{row['absent_present']} | {fmt(row['delta_absent_f1_mean'])} | {f1_ci} | "
            f"{fmt(row['delta_accuracy_mean'])} | {acc_ci} | {row['missing_predictions']} |"
        )

    lines.extend([
        "",
        "## Error and Disagreement Case Counts",
        "",
        "| Case Type | Count | Selected |",
        "|---|---:|---:|",
    ])
    for row in payload["case_summary"]:
        lines.append(f"| {row['case_type']} | {row['count']} | {row['selected']} |")

    lines.extend([
        "",
        "## Interpretation",
        "",
        "- `combined_corrected_absent_false_present`: prompt-only forced-choice errors that the combined verifier fixes.",
        "- `combined_new_present_false_absent`: visible targets rejected by the combined verifier; this is the main conservative-cost bucket.",
        "- `combined_vs_ocr_aware_disagreement`: cases where the transparent verifier and OCR-aware VLM make different status decisions.",
        "- `evidence_overreject_present`: evidence-aware VLM false-absent cases; useful for diagnosing over-conservative prompting/evidence use.",
        "",
    ])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Analyze realistic absent validation predictions with bootstrap CIs and case mining.")
    parser.add_argument("--input-json", required=True)
    parser.add_argument("--prediction", action="append", default=[], help="NAME=PATH prediction JSON. First one is baseline unless --baseline is set.")
    parser.add_argument("--baseline", default="")
    parser.add_argument("--combined", default="")
    parser.add_argument("--ocr-aware", default="")
    parser.add_argument("--evidence-aware", default="")
    parser.add_argument("--bootstrap", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--case-limit", type=int, default=100)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()

    if not args.prediction:
        raise SystemExit("At least one --prediction NAME=PATH is required.")

    records = load_examples(Path(args.input_json))
    prediction_maps = {}
    raw_paths = {}
    for item in args.prediction:
        name, path = parse_prediction_arg(item)
        prediction_maps[name], _ = load_prediction_map(path)
        raw_paths[name] = str(path)

    baseline_name = args.baseline or next(iter(prediction_maps))
    if baseline_name not in prediction_maps:
        raise SystemExit(f"Baseline not found among predictions: {baseline_name}")

    method_summary = method_rows(records, prediction_maps, baseline_name, args.bootstrap, args.seed)

    combined_name = args.combined or ("combined_best_f1" if "combined_best_f1" in prediction_maps else "")
    ocr_name = args.ocr_aware or ("vlm_ocr_aware" if "vlm_ocr_aware" in prediction_maps else "")
    evidence_name = args.evidence_aware or ("vlm_evidence" if "vlm_evidence" in prediction_maps else "")
    case_summary, selected_cases = mine_cases(
        records,
        prediction_maps,
        baseline_name,
        combined_name,
        ocr_name,
        evidence_name,
        args.case_limit,
    )

    out_dir = Path(args.out_dir)
    cases_dir = out_dir / "cases"
    case_fieldnames = [
        "index", "key", "review_id", "img_usr_tgt", "image", "query_text", "source_type", "gold_status",
        *[f"{name}_status" for name in prediction_maps],
    ]
    for case_type, rows in selected_cases.items():
        write_csv(cases_dir / f"{case_type}.csv", rows, case_fieldnames)
        write_json(cases_dir / f"{case_type}.json", rows)

    payload = {
        "input_json": args.input_json,
        "num_examples": len(records),
        "prediction_paths": raw_paths,
        "baseline_name": baseline_name,
        "combined_name": combined_name,
        "ocr_aware_name": ocr_name,
        "evidence_aware_name": evidence_name,
        "bootstrap": args.bootstrap,
        "seed": args.seed,
        "method_rows": method_summary,
        "case_summary": case_summary,
        "case_outputs": {
            row["case_type"]: {
                "csv": str(cases_dir / f"{row['case_type']}.csv"),
                "json": str(cases_dir / f"{row['case_type']}.json"),
            }
            for row in case_summary
        },
    }

    write_json(out_dir / "real_absent_validation_analysis.json", payload)
    write_csv(out_dir / "real_absent_validation_metrics_ci.csv", method_summary)
    write_csv(out_dir / "real_absent_validation_case_summary.csv", case_summary)
    write_markdown(out_dir / "real_absent_validation_analysis.md", payload)
    print(json.dumps({
        "num_examples": len(records),
        "methods": len(method_summary),
        "case_groups": len(case_summary),
        "output_md": str(out_dir / "real_absent_validation_analysis.md"),
    }, indent=2))


if __name__ == "__main__":
    main()
