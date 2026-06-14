#!/usr/bin/env python
import argparse
import colorsys
import csv
import difflib
import json
from collections import Counter
from pathlib import Path

from PIL import Image


ABSENT_STATUSES = {"absent", "not_found", "not found", "no object", "no target", "not present"}
COLOR_WORDS = {
    "red", "blue", "green", "yellow", "black", "white", "gray", "grey", "orange", "purple",
    "pink", "brown", "cyan", "magenta", "teal", "violet", "gold", "silver",
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


def split_color_query(query):
    parts = normalize(query).split()
    if parts and parts[0] in COLOR_WORDS:
        color = "gray" if parts[0] == "grey" else parts[0]
        return color, " ".join(parts[1:])
    return "", " ".join(parts)


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


def target_key(example):
    target_id = str(example.get("target_id", "") or "")
    return target_id[4:] if target_id.startswith("txt_") else target_id


def get_target_text(example, target2text):
    for key in ["query_text", "target", "original_target"]:
        text = str(example.get(key, "") or "")
        if text:
            return text
    return str(target2text.get(target_key(example), "") or "")


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


def resolve_image(image_root, image):
    image_root = Path(image_root)
    image = str(image or "")
    candidates = [
        image_root / image,
        image_root / "vsgui10k-images" / Path(image).name,
    ]
    for path in candidates:
        if path.exists():
            return path
    basename = Path(image).name
    if basename:
        for path in image_root.rglob(basename):
            if path.is_file():
                return path
    return None


def color_match_pixel(color, rgb):
    r, g, b = [value / 255.0 for value in rgb]
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    if color == "white":
        return s < 0.25 and v > 0.72
    if color == "black":
        return v < 0.28
    if color in {"gray", "silver"}:
        return s < 0.22 and 0.25 <= v <= 0.88
    if color == "red":
        return (h <= 0.04 or h >= 0.94) and s > 0.28 and v > 0.20
    if color == "orange":
        return 0.04 < h <= 0.11 and s > 0.25 and v > 0.25
    if color in {"yellow", "gold"}:
        return 0.11 < h <= 0.19 and s > 0.22 and v > 0.30
    if color == "green":
        return 0.20 < h <= 0.45 and s > 0.22 and v > 0.20
    if color in {"cyan", "teal"}:
        return 0.45 < h <= 0.56 and s > 0.22 and v > 0.20
    if color == "blue":
        return 0.56 < h <= 0.72 and s > 0.22 and v > 0.20
    if color in {"purple", "violet"}:
        return 0.72 < h <= 0.83 and s > 0.22 and v > 0.20
    if color in {"pink", "magenta"}:
        return 0.83 < h <= 0.96 and s > 0.18 and v > 0.35
    if color == "brown":
        return 0.04 < h <= 0.12 and s > 0.25 and 0.18 <= v <= 0.70
    return False


def candidate_color_score(image, candidate, color, pad):
    if not color:
        return 1.0
    width, height = image.size
    left = max(0, int(round(safe_float(candidate.get("left")) - pad)))
    top = max(0, int(round(safe_float(candidate.get("top")) - pad)))
    right = min(width, int(round(safe_float(candidate.get("left")) + safe_float(candidate.get("width")) + pad)))
    bottom = min(height, int(round(safe_float(candidate.get("top")) + safe_float(candidate.get("height")) + pad)))
    if right <= left or bottom <= top:
        return 0.0
    crop = image.crop((left, top, right, bottom)).convert("RGB")
    pixels = list(crop.getdata())
    if not pixels:
        return 0.0
    fraction = sum(1 for pixel in pixels if color_match_pixel(color, pixel)) / len(pixels)
    # Text pixels occupy a small fraction of OCR boxes, so amplify modest fractions.
    return min(1.0, fraction / 0.08)


def best_color_aware_score(query, image, candidates, min_conf, pad):
    color, stripped_query = split_color_query(query)
    text_query = stripped_query or normalize(query)
    best = {
        "score": 0.0,
        "text_score": 0.0,
        "color_score": 1.0 if not color else 0.0,
        "text": "",
        "conf": "",
        "requested_color": color,
        "stripped_query": text_query,
    }
    for candidate in candidates:
        conf = safe_float(candidate.get("conf"), 0.0)
        if conf < min_conf:
            continue
        text_score = similarity(text_query, candidate.get("text", ""))
        color_score = candidate_color_score(image, candidate, color, pad)
        score = text_score if not color else text_score * color_score
        if score > best["score"]:
            best = {
                "score": score,
                "text_score": text_score,
                "color_score": color_score,
                "text": candidate.get("text", ""),
                "conf": conf,
                "requested_color": color,
                "stripped_query": text_query,
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


def conflict_indices(audit_json):
    if not audit_json:
        return set()
    data = load_json(Path(audit_json))
    return {int(row["index"]) for row in data.get("conflict_rows", [])}


def filtered_metrics(examples, excluded):
    if not excluded:
        return {}
    kept = [example for idx, example in enumerate(examples) if idx not in excluded]
    metrics = evaluate(kept)
    return {
        "filtered_num_examples": metrics["num_examples"],
        "filtered_accuracy": metrics["accuracy"],
        "filtered_absent_precision": metrics["absent_precision"],
        "filtered_absent_recall": metrics["absent_recall"],
        "filtered_absent_f1": metrics["absent_f1"],
        "filtered_present_absent": metrics["confusion"]["present->absent"],
        "filtered_absent_present": metrics["confusion"]["absent->present"],
    }


def threshold_values(start, stop, step):
    values = []
    value = start
    while value <= stop + 1e-9:
        values.append(round(value, 4))
        value += step
    return values


def score_records(predictions, target2text, evidence, ocr_by_image, image_root, min_conf, pad):
    records = []
    missing_images = 0
    missing_evidence = 0
    for idx, example in enumerate(predictions):
        ev = evidence.get(idx)
        if ev is None:
            missing_evidence += 1
        cog_score = safe_float((ev or {}).get("path_best_evidence"))
        image_key = example.get("image", "")
        image_path = resolve_image(image_root, image_key)
        if image_path is None:
            missing_images += 1
            best = {"score": 0.0, "text_score": 0.0, "color_score": 0.0, "text": "", "conf": "", "requested_color": "", "stripped_query": ""}
        else:
            with Image.open(image_path) as image:
                image = image.convert("RGB")
                best = best_color_aware_score(
                    get_target_text(example, target2text),
                    image,
                    ocr_by_image.get(image_key, []) or ocr_by_image.get(Path(image_key).name, []),
                    min_conf,
                    pad,
                )
        records.append({
            "index": idx,
            "example": example,
            "gold_status": gold_status(example),
            "original_status": predicted_status(example),
            "cog_score": cog_score,
            "color_aware_score": best["score"],
            "text_score": best["text_score"],
            "color_score": best["color_score"],
            "ocr_text": best["text"],
            "ocr_conf": best["conf"],
            "requested_color": best["requested_color"],
            "stripped_query": best["stripped_query"],
        })
    return records, missing_evidence, missing_images


def apply_thresholds(records, cog_threshold, score_threshold, mode, selection_excluded=None):
    adjusted = []
    details = []
    changed = 0
    for record in records:
        result = dict(record["example"])
        original = record["original_status"]
        new_status = "absent" if (
            record["cog_score"] < cog_threshold
            and record["color_aware_score"] < score_threshold
        ) else "present"
        if mode == "present_only" and original == "absent":
            new_status = original
        changed += int(new_status != original)
        result["original_predicted_status"] = original
        result["predicted_status"] = new_status
        result["color_aware_verifier_applied"] = new_status != original
        result["color_aware_cognitive_threshold"] = cog_threshold
        result["color_aware_score_threshold"] = score_threshold
        result["path_best_evidence"] = record["cog_score"]
        result["color_aware_score"] = record["color_aware_score"]
        result["color_aware_text_score"] = record["text_score"]
        result["color_aware_color_score"] = record["color_score"]
        result["color_aware_ocr_text"] = record["ocr_text"]
        result["color_aware_requested_color"] = record["requested_color"]
        adjusted.append(result)
        details.append({
            "index": record["index"],
            "img_usr_tgt": record["example"].get("img_usr_tgt", record["index"]),
            "image": record["example"].get("image", ""),
            "gold_status": record["gold_status"],
            "original_status": original,
            "verified_status": new_status,
            "cog_score": record["cog_score"],
            "color_aware_score": record["color_aware_score"],
            "text_score": record["text_score"],
            "color_score": record["color_score"],
            "ocr_text": record["ocr_text"],
            "ocr_conf": record["ocr_conf"],
            "requested_color": record["requested_color"],
            "stripped_query": record["stripped_query"],
            "changed": int(new_status != original),
        })
    metrics = evaluate(adjusted)
    metrics.update(filtered_metrics(adjusted, selection_excluded or set()))
    metrics.update({
        "mode": mode,
        "cognitive_threshold": cog_threshold,
        "score_threshold": score_threshold,
        "changed_predictions": changed,
    })
    return adjusted, metrics, details


def sweep(records, mode, cog_values, score_values, selection_excluded=None):
    rows = []
    for cog_threshold in cog_values:
        for score_threshold in score_values:
            _, metrics, _ = apply_thresholds(records, cog_threshold, score_threshold, mode, selection_excluded)
            confusion = metrics["confusion"]
            row = {
                "mode": mode,
                "cognitive_threshold": cog_threshold,
                "score_threshold": score_threshold,
                "accuracy": metrics["accuracy"],
                "absent_precision": metrics["absent_precision"],
                "absent_recall": metrics["absent_recall"],
                "absent_f1": metrics["absent_f1"],
                "changed_predictions": metrics["changed_predictions"],
                "present_present": confusion["present->present"],
                "present_absent": confusion["present->absent"],
                "absent_present": confusion["absent->present"],
                "absent_absent": confusion["absent->absent"],
            }
            for key in [
                "filtered_num_examples",
                "filtered_accuracy",
                "filtered_absent_precision",
                "filtered_absent_recall",
                "filtered_absent_f1",
                "filtered_present_absent",
                "filtered_absent_present",
            ]:
                if key in metrics:
                    row[key] = metrics[key]
            rows.append(row)
    return rows


def select_best(rows, metric):
    return max(
        rows,
        key=lambda row: (
            safe_float(row.get(metric), -1.0),
            safe_float(row.get("accuracy"), -1.0),
            safe_float(row.get("absent_precision"), -1.0),
            -safe_float(row.get("present_absent"), 0.0),
        ),
    )


def main():
    parser = argparse.ArgumentParser(description="Apply native color-aware OCR + path verifier.")
    parser.add_argument("--predictions", required=True)
    parser.add_argument("--evidence", required=True)
    parser.add_argument("--ocr-candidates", required=True)
    parser.add_argument("--image-root", required=True)
    parser.add_argument("--target2text", default="")
    parser.add_argument("--mode", choices=["present_only", "override"], default="present_only")
    parser.add_argument("--cognitive-threshold", type=float, default=0.2)
    parser.add_argument("--score-threshold", type=float, default=0.5)
    parser.add_argument("--threshold-step", type=float, default=0.025)
    parser.add_argument("--cognitive-threshold-max", type=float, default=0.6)
    parser.add_argument("--score-threshold-max", type=float, default=1.0)
    parser.add_argument(
        "--select-threshold-metric",
        choices=[
            "",
            "accuracy",
            "absent_f1",
            "absent_precision",
            "absent_recall",
            "filtered_accuracy",
            "filtered_absent_f1",
            "filtered_absent_precision",
            "filtered_absent_recall",
        ],
        default="",
    )
    parser.add_argument("--selection-audit-json", default="", help="Optional native label-conflict audit JSON used only for threshold selection.")
    parser.add_argument("--min-ocr-conf", type=float, default=35.0)
    parser.add_argument("--color-pad", type=int, default=2)
    parser.add_argument("--output", required=True)
    parser.add_argument("--metrics-output", required=True)
    parser.add_argument("--detail-output", required=True)
    parser.add_argument("--sweep-output", required=True)
    parser.add_argument("--selected-threshold-output", required=True)
    args = parser.parse_args()

    predictions = load_json(Path(args.predictions))
    target2text = load_json(Path(args.target2text)) if args.target2text else {}
    evidence = load_evidence(Path(args.evidence))
    ocr_by_image = load_ocr_candidates(Path(args.ocr_candidates))
    records, missing_evidence, missing_images = score_records(
        predictions,
        target2text,
        evidence,
        ocr_by_image,
        Path(args.image_root),
        args.min_ocr_conf,
        args.color_pad,
    )
    selection_excluded = conflict_indices(args.selection_audit_json)
    sweep_rows = sweep(
        records,
        args.mode,
        threshold_values(0.0, args.cognitive_threshold_max, args.threshold_step),
        threshold_values(0.0, args.score_threshold_max, args.threshold_step),
        selection_excluded,
    )
    write_csv(Path(args.sweep_output), sweep_rows)
    if args.select_threshold_metric:
        selected = select_best(sweep_rows, args.select_threshold_metric)
        args.cognitive_threshold = safe_float(selected.get("cognitive_threshold"), args.cognitive_threshold)
        args.score_threshold = safe_float(selected.get("score_threshold"), args.score_threshold)
        selected = {**selected, "selected_metric": args.select_threshold_metric}
    else:
        selected = {
            "selected_metric": "",
            "cognitive_threshold": args.cognitive_threshold,
            "score_threshold": args.score_threshold,
        }
    write_json(Path(args.selected_threshold_output), selected)
    adjusted, metrics, details = apply_thresholds(
        records,
        args.cognitive_threshold,
        args.score_threshold,
        args.mode,
        selection_excluded,
    )
    metrics.update({
        "missing_evidence": missing_evidence,
        "missing_images": missing_images,
        "selection_audit_json": args.selection_audit_json,
        "selection_excluded_examples": len(selection_excluded),
        "min_ocr_conf": args.min_ocr_conf,
        "color_pad": args.color_pad,
        "input_predictions": args.predictions,
        "input_evidence": args.evidence,
        "input_ocr_candidates": args.ocr_candidates,
        "output": args.output,
    })
    write_json(Path(args.output), adjusted)
    write_json(Path(args.metrics_output), metrics)
    write_csv(Path(args.detail_output), details)
    print(json.dumps({"selected": selected, "metrics": metrics}, indent=2))


if __name__ == "__main__":
    main()
