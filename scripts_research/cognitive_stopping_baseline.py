#!/usr/bin/env python
import argparse
import csv
import difflib
import json
from collections import defaultdict
from pathlib import Path


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def target_key(example):
    target_id = example.get("target_id", "")
    return target_id[4:] if target_id.startswith("txt_") else target_id


def get_target_text(example, target2text):
    explicit = str(example.get("target", "") or "")
    if explicit:
        return explicit
    return str(target2text.get(target_key(example), "") or "")


def normalize(text):
    return " ".join(str(text or "").casefold().replace("_", " ").replace("-", " ").split())


def similarity(a, b):
    a = normalize(a)
    b = normalize(b)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    if a in b or b in a:
        return min(len(a), len(b)) / max(len(a), len(b))
    return difflib.SequenceMatcher(None, a, b).ratio()


def gold_status(example):
    if "target_present" in example:
        return "present" if example["target_present"] else "absent"
    status = str(example.get("status", "present")).casefold()
    return "absent" if status == "absent" else "present"


def safe_div(num, den):
    return num / den if den else 0.0


def score_metrics(rows, threshold):
    tp_absent = fp_absent = fn_absent = tn_absent = 0
    for row in rows:
        pred = "absent" if row["max_similarity"] < threshold else "present"
        gold = row["gold_status"]
        if gold == "absent" and pred == "absent":
            tp_absent += 1
        elif gold == "present" and pred == "absent":
            fp_absent += 1
        elif gold == "absent" and pred == "present":
            fn_absent += 1
        else:
            tn_absent += 1

    total = tp_absent + fp_absent + fn_absent + tn_absent
    precision = safe_div(tp_absent, tp_absent + fp_absent)
    recall = safe_div(tp_absent, tp_absent + fn_absent)
    f1 = safe_div(2 * precision * recall, precision + recall)
    accuracy = safe_div(tp_absent + tn_absent, total)
    return {
        "threshold": threshold,
        "accuracy": accuracy,
        "absent_precision": precision,
        "absent_recall": recall,
        "absent_f1": f1,
        "present_present": tn_absent,
        "present_absent": fp_absent,
        "absent_present": fn_absent,
        "absent_absent": tp_absent,
    }


def main():
    parser = argparse.ArgumentParser(description="Minimal cognitive stopping baseline for target-absent UI search.")
    parser.add_argument("--reference", required=True, help="Present-target JSON used to define candidate texts per image.")
    parser.add_argument("--eval", required=True, help="Evaluation JSON with present/absent examples.")
    parser.add_argument("--target2text", default="")
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--threshold-step", type=float, default=0.05)
    args = parser.parse_args()

    target2text = load_json(Path(args.target2text)) if args.target2text else {}
    reference = load_json(Path(args.reference))
    eval_examples = load_json(Path(args.eval))

    image_to_candidate_texts = defaultdict(set)
    for example in reference:
        text = normalize(get_target_text(example, target2text))
        if text:
            image_to_candidate_texts[example["image"]].add(text)

    rows = []
    for idx, example in enumerate(eval_examples):
        query = get_target_text(example, target2text)
        candidates = sorted(image_to_candidate_texts.get(example["image"], []))
        scores = [(candidate, similarity(query, candidate)) for candidate in candidates]
        best_candidate, max_similarity = ("", 0.0)
        if scores:
            best_candidate, max_similarity = max(scores, key=lambda item: item[1])
        rows.append({
            "index": idx,
            "img_usr_tgt": example.get("img_usr_tgt", idx),
            "image": example.get("image", ""),
            "target": query,
            "gold_status": gold_status(example),
            "best_candidate": best_candidate,
            "max_similarity": max_similarity,
            "num_candidates": len(candidates),
        })

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    detail_path = out_dir / "cognitive_stopping_details.csv"
    with open(detail_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    thresholds = []
    value = 0.0
    while value <= 1.000001:
        thresholds.append(round(value, 4))
        value += args.threshold_step

    metrics = [score_metrics(rows, threshold) for threshold in thresholds]
    best = max(metrics, key=lambda item: item["absent_f1"])

    sweep_path = out_dir / "cognitive_stopping_threshold_sweep.csv"
    with open(sweep_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(metrics[0].keys()))
        writer.writeheader()
        writer.writerows(metrics)

    summary = {
        "num_examples": len(rows),
        "num_present": sum(1 for row in rows if row["gold_status"] == "present"),
        "num_absent": sum(1 for row in rows if row["gold_status"] == "absent"),
        "best_by_absent_f1": best,
        "detail_csv": str(detail_path),
        "threshold_sweep_csv": str(sweep_path),
    }
    with open(out_dir / "cognitive_stopping_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    with open(out_dir / "cognitive_stopping_summary.md", "w", encoding="utf-8") as f:
        f.write("# Cognitive Stopping Baseline\n\n")
        f.write(f"- Examples: {summary['num_examples']}\n")
        f.write(f"- Present: {summary['num_present']}\n")
        f.write(f"- Absent: {summary['num_absent']}\n")
        f.write(f"- Best threshold by absent F1: {best['threshold']}\n")
        f.write(f"- Accuracy: {best['accuracy']:.4f}\n")
        f.write(f"- Absent precision: {best['absent_precision']:.4f}\n")
        f.write(f"- Absent recall: {best['absent_recall']:.4f}\n")
        f.write(f"- Absent F1: {best['absent_f1']:.4f}\n")

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
