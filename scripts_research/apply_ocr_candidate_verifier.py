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


def target_key(example):
    target_id = str(example.get("target_id", "") or "")
    return target_id[4:] if target_id.startswith("txt_") else target_id


def get_target_text(example, target2text):
    for key in ["query_text", "target", "original_target"]:
        text = str(example.get(key, "") or "")
        if text:
            return text
    return str(target2text.get(target_key(example), "") or "")


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


def load_ocr_candidates(path):
    raw = load_json(path)
    rows = raw.get("images", raw if isinstance(raw, list) else [])
    return {
        row.get("image", ""): row.get("candidates", []) or []
        for row in rows
        if row.get("image")
    }


def best_ocr_match(query, candidates, min_conf):
    best = {
        "score": 0.0,
        "text": "",
        "conf": "",
        "source": "",
    }
    for candidate in candidates:
        try:
            conf = float(candidate.get("conf", 0.0))
        except (TypeError, ValueError):
            conf = 0.0
        if conf < min_conf:
            continue
        text = candidate.get("text", "")
        score = similarity(query, text)
        if score > best["score"]:
            best = {
                "score": score,
                "text": text,
                "conf": conf,
                "source": candidate.get("source", ""),
            }
    return best


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


def apply_threshold(predictions, target2text, ocr_by_image, threshold, mode, min_conf):
    adjusted = []
    detail_rows = []
    changed = 0
    missing_ocr_images = 0

    for idx, example in enumerate(predictions):
        result = dict(example)
        original_status = predicted_status(example)
        image = example.get("image", "")
        candidates = ocr_by_image.get(image)
        if candidates is None:
            candidates = []
            missing_ocr_images += 1
        query = get_target_text(example, target2text)
        best = best_ocr_match(query, candidates, min_conf)
        verified_status = "present" if best["score"] >= threshold else "absent"
        new_status = verified_status
        if mode == "present_only" and original_status == "absent":
            new_status = original_status

        result["original_predicted_status"] = original_status
        result["predicted_status"] = new_status
        result["ocr_candidate_verifier_applied"] = new_status != original_status
        result["ocr_candidate_verifier_threshold"] = threshold
        result["ocr_candidate_verifier_score"] = best["score"]
        result["ocr_candidate_verifier_text"] = best["text"]
        result["ocr_candidate_verifier_conf"] = best["conf"]
        result["ocr_candidate_count"] = len(candidates)
        if new_status != original_status:
            changed += 1
        adjusted.append(result)
        detail_rows.append({
            "index": idx,
            "img_usr_tgt": example.get("img_usr_tgt", idx),
            "image": image,
            "target": query,
            "gold_status": gold_status(example),
            "original_status": original_status,
            "verified_status": new_status,
            "score": best["score"],
            "best_ocr_text": best["text"],
            "best_ocr_conf": best["conf"],
            "num_ocr_candidates": len(candidates),
            "changed": int(new_status != original_status),
        })

    metrics = evaluate(adjusted)
    metrics.update({
        "threshold": threshold,
        "mode": mode,
        "changed_predictions": changed,
        "missing_ocr_images": missing_ocr_images,
        "min_ocr_conf": min_conf,
    })
    return adjusted, metrics, detail_rows


def threshold_values(step):
    values = []
    value = 0.0
    while value <= 1.000001:
        values.append(round(value, 4))
        value += step
    return values


def sweep_thresholds(predictions, target2text, ocr_by_image, mode, min_conf, step):
    rows = []
    for threshold in threshold_values(step):
        _, metrics, _ = apply_threshold(predictions, target2text, ocr_by_image, threshold, mode, min_conf)
        confusion = metrics["confusion"]
        rows.append({
            "threshold": threshold,
            "mode": mode,
            "accuracy": metrics["accuracy"],
            "absent_precision": metrics["absent_precision"],
            "absent_recall": metrics["absent_recall"],
            "absent_f1": metrics["absent_f1"],
            "changed_predictions": metrics["changed_predictions"],
            "missing_ocr_images": metrics["missing_ocr_images"],
            "present_present": confusion["present->present"],
            "present_absent": confusion["present->absent"],
            "absent_present": confusion["absent->present"],
            "absent_absent": confusion["absent->absent"],
        })
    return rows


def main():
    parser = argparse.ArgumentParser(description="Apply a non-oracle OCR candidate verifier.")
    parser.add_argument("--predictions", required=True)
    parser.add_argument("--ocr-candidates", required=True)
    parser.add_argument("--target2text", default="")
    parser.add_argument("--threshold", type=float, default=None)
    parser.add_argument("--output", default="")
    parser.add_argument("--metrics-output", default="")
    parser.add_argument("--detail-output", default="")
    parser.add_argument("--sweep-output", default="")
    parser.add_argument("--threshold-step", type=float, default=0.05)
    parser.add_argument("--min-ocr-conf", type=float, default=35.0)
    parser.add_argument(
        "--mode",
        choices=["override", "present_only"],
        default="present_only",
    )
    args = parser.parse_args()

    predictions = load_json(Path(args.predictions))
    target2text = load_json(Path(args.target2text)) if args.target2text else {}
    ocr_by_image = load_ocr_candidates(Path(args.ocr_candidates))

    if args.sweep_output:
        rows = sweep_thresholds(
            predictions,
            target2text,
            ocr_by_image,
            args.mode,
            args.min_ocr_conf,
            args.threshold_step,
        )
        write_csv(Path(args.sweep_output), rows)

    if args.output or args.metrics_output or args.detail_output:
        if args.threshold is None:
            raise ValueError("--threshold is required when writing outputs")
        adjusted, metrics, details = apply_threshold(
            predictions,
            target2text,
            ocr_by_image,
            args.threshold,
            args.mode,
            args.min_ocr_conf,
        )
        metrics.update({
            "input_predictions": str(Path(args.predictions)),
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
            "sweep_output": str(Path(args.sweep_output)),
            "mode": args.mode,
            "threshold_step": args.threshold_step,
        }, indent=2))
    else:
        raise ValueError("Set --output/--metrics-output with --threshold, or set --sweep-output")


if __name__ == "__main__":
    main()
