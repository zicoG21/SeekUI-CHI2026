#!/usr/bin/env python
import argparse
import csv
import difflib
import json
import math
from collections import defaultdict
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    Image = None


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


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
    if min(len(a), len(b)) >= 4 and (a in b or b in a):
        return min(len(a), len(b)) / max(len(a), len(b))
    return difflib.SequenceMatcher(None, a, b).ratio()


def gold_status(example):
    if "target_present" in example:
        return "present" if example["target_present"] else "absent"
    status = str(example.get("status", "present")).casefold()
    return "absent" if status == "absent" else "present"


def safe_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def bbox_center(example):
    x = safe_float(example.get("target_x"))
    y = safe_float(example.get("target_y"))
    w = safe_float(example.get("target_width"))
    h = safe_float(example.get("target_height"))
    if x is None or y is None or w is None or h is None or w <= 0 or h <= 0:
        return None
    return x + w / 2, y + h / 2


def image_size(image_root, rel_path, fallback):
    if not image_root or Image is None:
        return fallback
    path = image_root / rel_path
    if not path.exists():
        return fallback
    with Image.open(path) as im:
        return im.size


def layout_prior(point, size):
    width, height = size
    if width <= 0 or height <= 0:
        return 0.0
    x, y = point
    # Human/UI search often starts near the upper-left and high central content.
    top_left = 1.0 - min(1.0, math.dist((x / width, y / height), (0.0, 0.0)) / math.sqrt(2))
    center = 1.0 - min(1.0, math.dist((x / width, y / height), (0.5, 0.45)) / math.sqrt(2))
    return 0.65 * top_left + 0.35 * center


def norm_distance(a, b, size):
    width, height = size
    diagonal = math.sqrt(width * width + height * height) or 1.0
    return min(1.0, math.dist(a, b) / diagonal)


def build_candidates(reference, target2text, image_root, fallback_size):
    image_to_candidates = defaultdict(list)
    seen = defaultdict(set)
    for example in reference:
        center = bbox_center(example)
        text = get_target_text(example, target2text)
        image = example.get("image", "")
        if center is None or not normalize(text):
            continue
        dedupe_key = (normalize(text), round(center[0], 2), round(center[1], 2))
        if dedupe_key in seen[image]:
            continue
        seen[image].add(dedupe_key)
        size = image_size(image_root, image, fallback_size)
        image_to_candidates[image].append({
            "text": text,
            "target_id": example.get("target_id", ""),
            "img_usr_tgt": example.get("img_usr_tgt", ""),
            "point": center,
            "layout_prior": layout_prior(center, size),
        })
    return image_to_candidates


def simulate_search(example, candidates, target2text, size, args):
    query = get_target_text(example, target2text)
    if candidates:
        current = (size[0] / 2, size[1] / 2)
    else:
        current = (0.0, 0.0)
    visited = set()
    path = []
    best_seen = 0.0
    best_candidate = ""

    for step in range(1, min(args.max_steps, len(candidates)) + 1):
        scored = []
        for idx, candidate in enumerate(candidates):
            if idx in visited:
                continue
            sim = similarity(query, candidate["text"])
            move_cost = norm_distance(current, candidate["point"], size)
            score = (
                args.target_weight * sim
                + args.layout_weight * candidate["layout_prior"]
                - args.distance_weight * move_cost
            )
            scored.append((score, sim, move_cost, idx, candidate))
        if not scored:
            break
        score, sim, move_cost, idx, candidate = max(scored, key=lambda item: item[0])
        visited.add(idx)
        current = candidate["point"]
        best_seen = max(best_seen, sim)
        if sim >= best_seen:
            best_candidate = candidate["text"]
        path.append({
            "step": step,
            "candidate": candidate["text"],
            "similarity": sim,
            "score": score,
            "movement_cost": move_cost,
            "layout_prior": candidate["layout_prior"],
            "x": candidate["point"][0],
            "y": candidate["point"][1],
        })

    max_similarity_all = max((similarity(query, candidate["text"]) for candidate in candidates), default=0.0)
    return {
        "query": query,
        "num_candidates": len(candidates),
        "steps": len(path),
        "coverage": len(path) / len(candidates) if candidates else 0.0,
        "best_similarity_seen": best_seen,
        "max_similarity_all": max_similarity_all,
        "best_candidate_seen": best_candidate,
        "path": path,
    }


def safe_div(num, den):
    return num / den if den else 0.0


def score_metrics(rows, threshold):
    tp_absent = fp_absent = fn_absent = tn_absent = 0
    for row in rows:
        pred = "absent" if row["best_similarity_seen"] < threshold else "present"
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
    return {
        "threshold": threshold,
        "accuracy": safe_div(tp_absent + tn_absent, total),
        "absent_precision": precision,
        "absent_recall": recall,
        "absent_f1": f1,
        "present_present": tn_absent,
        "present_absent": fp_absent,
        "absent_present": fn_absent,
        "absent_absent": tp_absent,
    }


def write_csv(path, rows, fieldnames):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description="Cognitive process-style stopping baseline for target-absent UI search.")
    parser.add_argument("--reference", required=True)
    parser.add_argument("--eval", required=True)
    parser.add_argument("--target2text", default="")
    parser.add_argument("--image-root", default="")
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--max-steps", type=int, default=6)
    parser.add_argument("--threshold-step", type=float, default=0.05)
    parser.add_argument("--target-weight", type=float, default=1.0)
    parser.add_argument("--layout-weight", type=float, default=0.2)
    parser.add_argument("--distance-weight", type=float, default=0.15)
    parser.add_argument("--fallback-width", type=float, default=1280)
    parser.add_argument("--fallback-height", type=float, default=720)
    args = parser.parse_args()

    target2text = load_json(Path(args.target2text)) if args.target2text else {}
    reference = load_json(Path(args.reference))
    eval_examples = load_json(Path(args.eval))
    image_root = Path(args.image_root) if args.image_root else None
    fallback_size = (args.fallback_width, args.fallback_height)
    candidates_by_image = build_candidates(reference, target2text, image_root, fallback_size)

    rows = []
    path_records = []
    for idx, example in enumerate(eval_examples):
        image = example.get("image", "")
        size = image_size(image_root, image, fallback_size)
        result = simulate_search(example, candidates_by_image.get(image, []), target2text, size, args)
        row = {
            "index": idx,
            "img_usr_tgt": example.get("img_usr_tgt", idx),
            "image": image,
            "target": result["query"],
            "gold_status": gold_status(example),
            "num_candidates": result["num_candidates"],
            "steps": result["steps"],
            "coverage": result["coverage"],
            "best_similarity_seen": result["best_similarity_seen"],
            "max_similarity_all": result["max_similarity_all"],
            "best_candidate_seen": result["best_candidate_seen"],
        }
        rows.append(row)
        for step in result["path"]:
            path_records.append({
                "index": idx,
                "img_usr_tgt": row["img_usr_tgt"],
                "gold_status": row["gold_status"],
                **step,
            })

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(out_dir / "cognitive_process_details.csv", rows, list(rows[0].keys()))
    write_csv(
        out_dir / "cognitive_process_paths.csv",
        path_records,
        ["index", "img_usr_tgt", "gold_status", "step", "candidate", "similarity", "score", "movement_cost", "layout_prior", "x", "y"],
    )

    thresholds = []
    value = 0.0
    while value <= 1.000001:
        thresholds.append(round(value, 4))
        value += args.threshold_step
    metrics = [score_metrics(rows, threshold) for threshold in thresholds]
    best = max(metrics, key=lambda item: item["absent_f1"])
    write_csv(out_dir / "cognitive_process_threshold_sweep.csv", metrics, list(metrics[0].keys()))

    summary = {
        "num_examples": len(rows),
        "num_present": sum(1 for row in rows if row["gold_status"] == "present"),
        "num_absent": sum(1 for row in rows if row["gold_status"] == "absent"),
        "max_steps": args.max_steps,
        "weights": {
            "target": args.target_weight,
            "layout": args.layout_weight,
            "distance": args.distance_weight,
        },
        "avg_steps": sum(row["steps"] for row in rows) / len(rows) if rows else 0.0,
        "best_by_absent_f1": best,
        "detail_csv": str(out_dir / "cognitive_process_details.csv"),
        "paths_csv": str(out_dir / "cognitive_process_paths.csv"),
        "threshold_sweep_csv": str(out_dir / "cognitive_process_threshold_sweep.csv"),
    }
    write_json(out_dir / "cognitive_process_summary.json", summary)
    with open(out_dir / "cognitive_process_summary.md", "w", encoding="utf-8") as f:
        f.write("# Cognitive Process Stopping Baseline\n\n")
        f.write(f"- Examples: {summary['num_examples']}\n")
        f.write(f"- Present: {summary['num_present']}\n")
        f.write(f"- Absent: {summary['num_absent']}\n")
        f.write(f"- Max simulated steps: {summary['max_steps']}\n")
        f.write(f"- Avg simulated steps: {summary['avg_steps']:.2f}\n")
        f.write(f"- Best threshold by absent F1: {best['threshold']}\n")
        f.write(f"- Accuracy: {best['accuracy']:.4f}\n")
        f.write(f"- Absent precision: {best['absent_precision']:.4f}\n")
        f.write(f"- Absent recall: {best['absent_recall']:.4f}\n")
        f.write(f"- Absent F1: {best['absent_f1']:.4f}\n")

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
