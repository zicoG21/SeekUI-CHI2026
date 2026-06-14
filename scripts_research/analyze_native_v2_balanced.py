#!/usr/bin/env python
import argparse
import csv
import json
import random
from collections import Counter, defaultdict
from pathlib import Path


ABSENT_STATUSES = {"absent", "not_found", "not found", "no object", "no target", "not present"}
DEFAULT_SPLITS = [
    "native_v2_main_text_balanced",
    "native_v2_main_text_color_balanced",
    "native_v2_clean_text_all_balanced",
    "native_v2_color_instance_balanced",
]
METHOD_SPECS = [
    ("prompt", "seekui_prompt", "present_absent_predictions_{model}_{split}.json"),
    ("combined_best_f1", "combined", "present_absent_predictions_{model}_{split}_combined_and_present_only_best_f1.json"),
    ("combined_default", "combined", "present_absent_predictions_{model}_{split}_combined_and_present_only.json"),
    ("color_aware", "color_aware", "present_absent_predictions_{model}_{split}_color_aware_native_tuned_absent_f1.json"),
    ("context_crop", "context_crop_vlm", "present_absent_predictions_{model}_{split}_context_crop_ocr_vlm.json"),
    ("vlm_presence_ocr_aware", "vlm_presence", "vlm_presence_predictions_{model}_vlm_presence_{split}_ocr_aware.json"),
    ("vlm_evidence", "vlm_evidence", "vlm_evidence_predictions_{model}_vlm_evidence_{split}_evidence_aware.json"),
    ("ensemble", "ensemble", "present_absent_predictions_{model}_{split}_status_ensemble_absent_f1.json"),
    ("cv_vote_router", "cv_vote_router", "present_absent_predictions_{model}_{split}_native_v2_cv_vote_router.json"),
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


def target_text(example):
    return str(example.get("query_text") or example.get("target") or example.get("original_target") or "")


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
        "present_absent": fp_absent,
        "absent_present": fn_absent,
        "present_present": tn_absent,
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


def load_records(path):
    rows = []
    for idx, example in enumerate(read_json(path)):
        rows.append({
            "index": idx,
            "key": example_key(example, idx),
            "gold_status": gold_status(example),
            "image": example.get("image", ""),
            "target": target_text(example),
            "cue_type": example.get("cue_type", example.get("cue", "")),
            "native_v2_task": example.get("native_v2_task", ""),
            "native_v2_visibility_bucket": example.get("native_v2_visibility_bucket", ""),
            "img_usr_tgt": example.get("img_usr_tgt", ""),
        })
    return rows


def load_prediction_map(path):
    mapping = {}
    for idx, example in enumerate(read_json(path)):
        mapping[example_key(example, idx)] = predicted_status(example)
    return mapping


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


def bootstrap_delta(records, baseline_predictions, method_predictions, n_bootstrap, seed):
    rng = random.Random(seed)
    n = len(records)
    delta_f1 = []
    delta_acc = []
    for _ in range(n_bootstrap):
        sample = [records[rng.randrange(n)] for _ in range(n)]
        baseline = evaluate(sample, baseline_predictions)
        method = evaluate(sample, method_predictions)
        delta_f1.append(method["absent_f1"] - baseline["absent_f1"])
        delta_acc.append(method["accuracy"] - baseline["accuracy"])

    def ci(values):
        return {
            "mean": sum(values) / len(values) if values else 0.0,
            "low": percentile(values, 0.025),
            "high": percentile(values, 0.975),
        }

    return {"delta_f1": ci(delta_f1), "delta_acc": ci(delta_acc)}


def method_paths(outputs_dir, model, split):
    paths = []
    for name, family, template in METHOD_SPECS:
        path = outputs_dir / template.format(model=model, split=split)
        if path.exists():
            paths.append({"name": name, "family": family, "path": path})
    return paths


def case_row(record, predictions, case_type):
    row = {
        "index": record["index"],
        "case_type": case_type,
        "key": record["key"],
        "image": record["image"],
        "target": record["target"],
        "gold_status": record["gold_status"],
        "cue_type": record["cue_type"],
        "native_v2_task": record["native_v2_task"],
        "visibility_bucket": record["native_v2_visibility_bucket"],
    }
    for name, pred_map in predictions.items():
        row[f"{name}_status"] = pred_map.get(record["key"], "missing")
    return row


def mine_cases(records, predictions, best_name, case_limit):
    prompt = predictions["prompt"]
    best = predictions[best_name]
    groups = defaultdict(list)
    for record in records:
        key = record["key"]
        gold = record["gold_status"]
        prompt_pred = prompt.get(key, "missing")
        best_pred = best.get(key, "missing")
        prompt_ok = prompt_pred == gold
        best_ok = best_pred == gold

        if gold == "absent" and prompt_pred == "present" and best_pred == "absent":
            groups["prompt_forced_choice_fixed"].append(case_row(record, predictions, "prompt_forced_choice_fixed"))
        if gold == "absent" and prompt_pred == "present" and best_pred == "present":
            groups["forced_choice_kept"].append(case_row(record, predictions, "forced_choice_kept"))
        if gold == "present" and prompt_pred == "present" and best_pred == "absent":
            groups["verifier_overreject_present"].append(case_row(record, predictions, "verifier_overreject_present"))
        if gold == "present" and prompt_pred == "absent" and best_pred == "present":
            groups["verifier_rescues_present"].append(case_row(record, predictions, "verifier_rescues_present"))
        if not prompt_ok and best_ok:
            groups["prompt_wrong_best_correct"].append(case_row(record, predictions, "prompt_wrong_best_correct"))
        if prompt_ok and not best_ok:
            groups["prompt_correct_best_wrong"].append(case_row(record, predictions, "prompt_correct_best_wrong"))
        if not prompt_ok and not best_ok and gold == "absent":
            groups["both_wrong_absent"].append(case_row(record, predictions, "both_wrong_absent"))
        if not prompt_ok and not best_ok and gold == "present":
            groups["both_wrong_present"].append(case_row(record, predictions, "both_wrong_present"))

    summary = []
    selected = {}
    for case_type in [
        "prompt_forced_choice_fixed",
        "forced_choice_kept",
        "verifier_overreject_present",
        "verifier_rescues_present",
        "prompt_wrong_best_correct",
        "prompt_correct_best_wrong",
        "both_wrong_absent",
        "both_wrong_present",
    ]:
        rows = groups.get(case_type, [])
        selected_rows = rows[:case_limit]
        selected[case_type] = selected_rows
        summary.append({"case_type": case_type, "count": len(rows), "selected": len(selected_rows)})
    return summary, selected


def analyze_split(outputs_dir, split_dir, model, split, n_bootstrap, seed, case_limit, out_dir):
    split_path = split_dir / f"{split}.json"
    if not split_path.exists():
        return {"split": split, "status": "missing_split", "path": str(split_path)}

    records = load_records(split_path)
    specs = method_paths(outputs_dir, model, split)
    prediction_maps = {}
    paths = {}
    for spec in specs:
        prediction_maps[spec["name"]] = load_prediction_map(spec["path"])
        paths[spec["name"]] = str(spec["path"])

    if "prompt" not in prediction_maps:
        return {"split": split, "status": "missing_prompt", "path": str(outputs_dir / f"present_absent_predictions_{model}_{split}.json")}

    baseline = prediction_maps["prompt"]
    rows = []
    for spec in specs:
        name = spec["name"]
        metrics = evaluate(records, prediction_maps[name])
        row = {
            "split": split,
            "method": name,
            "family": spec["family"],
            **metrics,
            "delta_f1_mean": "",
            "delta_f1_low": "",
            "delta_f1_high": "",
            "delta_acc_mean": "",
            "delta_acc_low": "",
            "delta_acc_high": "",
            "source": str(spec["path"]),
        }
        if name != "prompt":
            ci = bootstrap_delta(records, baseline, prediction_maps[name], n_bootstrap, seed)
            row.update({
                "delta_f1_mean": ci["delta_f1"]["mean"],
                "delta_f1_low": ci["delta_f1"]["low"],
                "delta_f1_high": ci["delta_f1"]["high"],
                "delta_acc_mean": ci["delta_acc"]["mean"],
                "delta_acc_low": ci["delta_acc"]["low"],
                "delta_acc_high": ci["delta_acc"]["high"],
            })
        rows.append(row)

    best = max((row for row in rows if row["method"] != "prompt"), key=lambda row: row["absent_f1"], default=None)
    case_summary = []
    if best:
        case_summary, selected_cases = mine_cases(records, prediction_maps, best["method"], case_limit)
        case_dir = out_dir / "cases" / split / best["method"]
        for case_type, case_rows in selected_cases.items():
            write_csv(case_dir / f"{case_type}.csv", case_rows)
        write_csv(case_dir / "case_summary.csv", case_summary)

    return {
        "split": split,
        "status": "ok",
        "num_records": len(records),
        "prediction_paths": paths,
        "rows": rows,
        "best_method": best["method"] if best else "",
        "best_absent_f1": best["absent_f1"] if best else "",
        "case_summary": case_summary,
    }


def write_md(path, payload):
    lines = [
        "# Native VSGUI10K v2 Balanced Analysis",
        "",
        "This table compares processed native VSGUI10K balanced splits against prompt-only SeekUI.",
        "Bootstrap confidence intervals are paired deltas against prompt-only on the same split.",
        "",
        "## Method Deltas",
        "",
        "| Split | Method | Family | N | Acc | Prec. | Rec. | F1 | P->A | A->P | Delta F1 | 95% CI | Delta Acc | 95% CI | Missing |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---|---:|",
    ]
    for row in payload["method_rows"]:
        f1_ci = ""
        acc_ci = ""
        if row["method"] != "prompt":
            f1_ci = f"[{fmt(row['delta_f1_low'])}, {fmt(row['delta_f1_high'])}]"
            acc_ci = f"[{fmt(row['delta_acc_low'])}, {fmt(row['delta_acc_high'])}]"
        lines.append(
            f"| {row['split']} | {row['method']} | {row['family']} | {row['num_examples']} | "
            f"{fmt(row['accuracy'])} | {fmt(row['absent_precision'])} | {fmt(row['absent_recall'])} | "
            f"{fmt(row['absent_f1'])} | {row['present_absent']} | {row['absent_present']} | "
            f"{fmt(row['delta_f1_mean'])} | {f1_ci} | {fmt(row['delta_acc_mean'])} | {acc_ci} | "
            f"{row['missing_predictions']} |"
        )

    lines.extend([
        "",
        "## Best Method By Split",
        "",
        "| Split | Best Method | F1 | Prompt F1 | Delta F1 | Main Reading |",
        "|---|---|---:|---:|---:|---|",
    ])
    for split in payload["splits"]:
        if split.get("status") != "ok":
            lines.append(f"| {split['split']} | {split['status']} |  |  |  | {split.get('path', '')} |")
            continue
        rows = split["rows"]
        prompt = next((row for row in rows if row["method"] == "prompt"), None)
        best = max((row for row in rows if row["method"] != "prompt"), key=lambda row: row["absent_f1"], default=None)
        if not prompt or not best:
            continue
        reading = "clean text/text+color absence improves over forced-choice baseline"
        if "color_instance" in split["split"]:
            reading = "color/instance matching remains the hardest native condition"
        elif best["method"] in {"color_aware", "context_crop"}:
            reading = "localized OCR/visual evidence is currently stronger than generic VLM prompting"
        lines.append(
            f"| {split['split']} | {best['method']} | {fmt(best['absent_f1'])} | "
            f"{fmt(prompt['absent_f1'])} | {fmt(best['absent_f1'] - prompt['absent_f1'])} | {reading} |"
        )

    lines.extend([
        "",
        "## Case Taxonomy For Best Method",
        "",
        "| Split | Best Method | Case Type | Count | Selected |",
        "|---|---|---|---:|---:|",
    ])
    for split in payload["splits"]:
        if split.get("status") != "ok" or not split.get("best_method"):
            continue
        for row in split["case_summary"]:
            lines.append(
                f"| {split['split']} | {split['best_method']} | {row['case_type']} | "
                f"{row['count']} | {row['selected']} |"
            )

    lines.extend([
        "",
        "## Reading",
        "",
        "- Processed native VSGUI10K v2 should be framed as an external stress test, not as the same clean task as the synthetic absent benchmark.",
        "- Strong deltas over prompt-only support the forced-choice failure claim outside the synthetic benchmark.",
        "- Lower absolute F1 than synthetic/realistic validation reflects native target-definition noise, color/instance ambiguity, and unresolved image-cue rows.",
        "- Treat color/instance splits separately from clean text absence; they require richer target representation rather than only a better stopping threshold.",
        "",
    ])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Analyze processed native VSGUI10K v2 balanced splits with bootstrap deltas and case mining.")
    parser.add_argument("--work-dir", required=True)
    parser.add_argument("--model-name", default="SeekUI")
    parser.add_argument("--splits", nargs="+", default=DEFAULT_SPLITS)
    parser.add_argument("--bootstrap", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--case-limit", type=int, default=80)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()

    work_dir = Path(args.work_dir)
    outputs_dir = work_dir / "outputs"
    split_dir = outputs_dir / "native_vsgui10k" / "processed_v2" / "splits"
    out_dir = Path(args.out_dir)

    split_payloads = []
    method_rows = []
    for idx, split in enumerate(args.splits):
        payload = analyze_split(
            outputs_dir,
            split_dir,
            args.model_name,
            split,
            args.bootstrap,
            args.seed + idx * 101,
            args.case_limit,
            out_dir,
        )
        split_payloads.append(payload)
        method_rows.extend(payload.get("rows", []))

    method_rows.sort(key=lambda row: (row["split"], row["method"] != "prompt", -row["absent_f1"]))
    payload = {
        "work_dir": str(work_dir),
        "model_name": args.model_name,
        "bootstrap": args.bootstrap,
        "seed": args.seed,
        "splits": split_payloads,
        "method_rows": method_rows,
    }

    write_json(out_dir / "native_v2_balanced_analysis.json", payload)
    write_csv(out_dir / "native_v2_balanced_metrics_ci.csv", method_rows)
    write_md(out_dir / "native_v2_balanced_analysis.md", payload)
    print(json.dumps({
        "splits": len(split_payloads),
        "method_rows": len(method_rows),
        "output_md": str(out_dir / "native_v2_balanced_analysis.md"),
    }, indent=2))


if __name__ == "__main__":
    main()
