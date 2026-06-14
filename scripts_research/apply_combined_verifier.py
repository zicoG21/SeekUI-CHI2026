#!/usr/bin/env python
import argparse
import csv
import difflib
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
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def normalize(text):
    return " ".join(str(text or "").casefold().replace("_", " ").replace("-", " ").split())


def similarity(a, b):
    a = normalize(a)
    b = normalize(b)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    if min(len(a), len(b)) >= 4 and (a in b or b in a):
        return min(len(a), len(b)) / max(len(a), len(b))
    return difflib.SequenceMatcher(None, a, b).ratio()


def target_key(example):
    target_id = str(example.get("target_id", "") or "")
    return target_id[4:] if target_id.startswith("txt_") else target_id


def get_target_text(example, target2text):
    for key in ["query_text", "target", "original_target"]:
        text = str(example.get(key, "") or "")
        if text:
            return text
    return str(target2text.get(target_key(example), "") or "")


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


def load_evidence(path):
    rows = {}
    with open(path, "r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            rows[int(row["index"])] = row
    return rows


def load_ocr_candidates(path):
    raw = load_json(path)
    rows = raw.get("images", raw if isinstance(raw, list) else [])
    return {
        row.get("image", ""): row.get("candidates", []) or []
        for row in rows
        if row.get("image")
    }


def best_ocr_score(query, candidates, min_conf):
    best_score = 0.0
    best_text = ""
    best_conf = ""
    for candidate in candidates:
        conf = safe_float(candidate.get("conf"), 0.0)
        if conf < min_conf:
            continue
        score = similarity(query, candidate.get("text", ""))
        if score > best_score:
            best_score = score
            best_text = candidate.get("text", "")
            best_conf = conf
    return best_score, best_text, best_conf


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


def combined_absent(cog_score, ocr_score, cog_threshold, ocr_threshold, rule):
    cog_absent = cog_score < cog_threshold
    ocr_absent = ocr_score < ocr_threshold
    if rule == "or":
        return cog_absent or ocr_absent
    if rule == "and":
        return cog_absent and ocr_absent
    raise ValueError(f"Unknown rule: {rule}")


def score_records(predictions, target2text, evidence, ocr_by_image, min_ocr_conf):
    records = []
    missing_evidence = 0
    missing_ocr_images = 0
    for idx, example in enumerate(predictions):
        evidence_row = evidence.get(idx)
        if evidence_row is None:
            missing_evidence += 1
            cog_score = 0.0
        else:
            cog_score = safe_float(evidence_row.get("path_best_evidence"))
        image = example.get("image", "")
        candidates = ocr_by_image.get(image)
        if candidates is None:
            missing_ocr_images += 1
            candidates = []
        query = get_target_text(example, target2text)
        ocr_score, ocr_text, ocr_conf = best_ocr_score(query, candidates, min_ocr_conf)
        records.append({
            "index": idx,
            "example": example,
            "original_status": predicted_status(example),
            "gold_status": gold_status(example),
            "cog_score": cog_score,
            "ocr_score": ocr_score,
            "ocr_text": ocr_text,
            "ocr_conf": ocr_conf,
            "ocr_candidate_count": len(candidates),
            "query": query,
        })
    return records, missing_evidence, missing_ocr_images


def apply_thresholds(records, cog_threshold, ocr_threshold, rule, mode):
    adjusted = []
    detail_rows = []
    changed = 0
    for record in records:
        result = dict(record["example"])
        original = record["original_status"]
        new_status = "absent" if combined_absent(
            record["cog_score"],
            record["ocr_score"],
            cog_threshold,
            ocr_threshold,
            rule,
        ) else "present"
        if mode == "present_only" and original == "absent":
            new_status = original
        if new_status != original:
            changed += 1
        result["original_predicted_status"] = original
        result["predicted_status"] = new_status
        result["combined_verifier_applied"] = new_status != original
        result["combined_verifier_rule"] = rule
        result["combined_verifier_mode"] = mode
        result["combined_cognitive_threshold"] = cog_threshold
        result["combined_ocr_threshold"] = ocr_threshold
        result["path_best_evidence"] = record["cog_score"]
        result["ocr_candidate_verifier_score"] = record["ocr_score"]
        result["ocr_candidate_verifier_text"] = record["ocr_text"]
        result["ocr_candidate_verifier_conf"] = record["ocr_conf"]
        adjusted.append(result)
        detail_rows.append({
            "index": record["index"],
            "img_usr_tgt": record["example"].get("img_usr_tgt", record["index"]),
            "image": record["example"].get("image", ""),
            "target": record["query"],
            "gold_status": record["gold_status"],
            "original_status": original,
            "verified_status": new_status,
            "cog_score": record["cog_score"],
            "ocr_score": record["ocr_score"],
            "ocr_text": record["ocr_text"],
            "ocr_conf": record["ocr_conf"],
            "ocr_candidate_count": record["ocr_candidate_count"],
            "changed": int(new_status != original),
        })
    metrics = evaluate(adjusted)
    metrics.update({
        "rule": rule,
        "mode": mode,
        "cognitive_threshold": cog_threshold,
        "ocr_threshold": ocr_threshold,
        "changed_predictions": changed,
    })
    return adjusted, metrics, detail_rows


def threshold_values(start, stop, step):
    values = []
    value = start
    while value <= stop + 1e-9:
        values.append(round(value, 4))
        value += step
    return values


def sweep(records, rule, mode, cog_values, ocr_values):
    rows = []
    for cog_threshold in cog_values:
        for ocr_threshold in ocr_values:
            _, metrics, _ = apply_thresholds(records, cog_threshold, ocr_threshold, rule, mode)
            confusion = metrics["confusion"]
            rows.append({
                "rule": rule,
                "mode": mode,
                "cognitive_threshold": cog_threshold,
                "ocr_threshold": ocr_threshold,
                "accuracy": metrics["accuracy"],
                "absent_precision": metrics["absent_precision"],
                "absent_recall": metrics["absent_recall"],
                "absent_f1": metrics["absent_f1"],
                "changed_predictions": metrics["changed_predictions"],
                "present_present": confusion["present->present"],
                "present_absent": confusion["present->absent"],
                "absent_present": confusion["absent->present"],
                "absent_absent": confusion["absent->absent"],
            })
    return rows


def select_best_threshold(rows, metric):
    if not rows:
        raise ValueError("Cannot select threshold from an empty sweep.")
    if metric not in rows[0]:
        raise ValueError(f"Unknown threshold-selection metric: {metric}")

    def key(row):
        return (
            safe_float(row.get(metric), -1.0),
            safe_float(row.get("accuracy"), -1.0),
            safe_float(row.get("absent_precision"), -1.0),
            -safe_float(row.get("present_absent"), 0.0),
            -safe_float(row.get("absent_present"), 0.0),
        )

    return max(rows, key=key)


def main():
    parser = argparse.ArgumentParser(description="Combine cognitive stopping and OCR candidate verification.")
    parser.add_argument("--predictions", required=True)
    parser.add_argument("--evidence", required=True)
    parser.add_argument("--ocr-candidates", required=True)
    parser.add_argument("--target2text", default="")
    parser.add_argument("--rule", choices=["or", "and"], required=True)
    parser.add_argument("--mode", choices=["override", "present_only"], default="present_only")
    parser.add_argument("--cognitive-threshold", type=float, default=0.05)
    parser.add_argument("--ocr-threshold", type=float, default=0.4)
    parser.add_argument("--min-ocr-conf", type=float, default=35.0)
    parser.add_argument("--threshold-step", type=float, default=0.05)
    parser.add_argument("--cognitive-threshold-max", type=float, default=0.3)
    parser.add_argument("--ocr-threshold-max", type=float, default=0.8)
    parser.add_argument(
        "--select-threshold-metric",
        default="",
        choices=["", "accuracy", "absent_precision", "absent_recall", "absent_f1"],
        help="If set, select cognitive/OCR thresholds from the generated sweep before applying.",
    )
    parser.add_argument("--selected-threshold-output", default="")
    parser.add_argument("--output", default="")
    parser.add_argument("--metrics-output", default="")
    parser.add_argument("--detail-output", default="")
    parser.add_argument("--sweep-output", default="")
    args = parser.parse_args()

    predictions = load_json(Path(args.predictions))
    target2text = load_json(Path(args.target2text)) if args.target2text else {}
    evidence = load_evidence(Path(args.evidence))
    ocr_by_image = load_ocr_candidates(Path(args.ocr_candidates))
    records, missing_evidence, missing_ocr_images = score_records(
        predictions,
        target2text,
        evidence,
        ocr_by_image,
        args.min_ocr_conf,
    )

    if args.sweep_output:
        rows = sweep(
            records,
            args.rule,
            args.mode,
            threshold_values(0.0, args.cognitive_threshold_max, args.threshold_step),
            threshold_values(0.0, args.ocr_threshold_max, args.threshold_step),
        )
        write_csv(Path(args.sweep_output), rows)
        if args.select_threshold_metric:
            selected = select_best_threshold(rows, args.select_threshold_metric)
            args.cognitive_threshold = safe_float(selected.get("cognitive_threshold"), args.cognitive_threshold)
            args.ocr_threshold = safe_float(selected.get("ocr_threshold"), args.ocr_threshold)
            selected = {
                **selected,
                "selected_metric": args.select_threshold_metric,
            }
            if args.selected_threshold_output:
                write_json(Path(args.selected_threshold_output), selected)
            print(json.dumps({
                "selected_metric": args.select_threshold_metric,
                "cognitive_threshold": args.cognitive_threshold,
                "ocr_threshold": args.ocr_threshold,
                "selected_absent_f1": selected.get("absent_f1"),
                "selected_accuracy": selected.get("accuracy"),
            }, indent=2))

    if args.output or args.metrics_output or args.detail_output:
        adjusted, metrics, details = apply_thresholds(
            records,
            args.cognitive_threshold,
            args.ocr_threshold,
            args.rule,
            args.mode,
        )
        metrics.update({
            "missing_evidence": missing_evidence,
            "missing_ocr_images": missing_ocr_images,
            "min_ocr_conf": args.min_ocr_conf,
            "input_predictions": str(Path(args.predictions)),
            "input_evidence": str(Path(args.evidence)),
            "input_ocr_candidates": str(Path(args.ocr_candidates)),
            "output": str(Path(args.output)) if args.output else "",
        })
        if args.output:
            write_json(Path(args.output), adjusted)
        if args.metrics_output:
            write_json(Path(args.metrics_output), metrics)
        if args.detail_output:
            write_csv(Path(args.detail_output), details)
        print(json.dumps(metrics, indent=2))
    elif args.sweep_output:
        print(json.dumps({
            "rule": args.rule,
            "mode": args.mode,
            "sweep_output": str(Path(args.sweep_output)),
        }, indent=2))
    else:
        raise ValueError("Set output paths or --sweep-output")


if __name__ == "__main__":
    main()
