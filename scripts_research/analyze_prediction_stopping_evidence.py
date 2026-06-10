#!/usr/bin/env python
import argparse
import csv
import difflib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    Image = None


ABSENT_STATUSES = {"absent", "not_found", "not found", "no object", "no target", "not present"}


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def write_csv(path, rows, fieldnames):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def target_key(example):
    target_id = str(example.get("target_id", "") or "")
    return target_id[4:] if target_id.startswith("txt_") else target_id


def normalize(text):
    return " ".join(str(text or "").casefold().replace("_", " ").replace("-", " ").split())


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


def gold_status(example):
    if "target_present" in example:
        return "present" if example["target_present"] else "absent"
    status = str(example.get("status", "present") or "present").casefold()
    return "absent" if status in ABSENT_STATUSES else "present"


def predicted_status(example):
    status = str(example.get("predicted_status", "") or "").casefold()
    if status in ABSENT_STATUSES:
        return "absent"
    if status == "present":
        return "present"
    return "present" if example.get("prediction", []) else "absent"


def parse_point(point):
    if not isinstance(point, (list, tuple)) or len(point) < 2:
        return None
    x = safe_float(point[0])
    y = safe_float(point[1])
    if x is None or y is None:
        return None
    return x, y


def diagonal(size):
    width, height = size
    return math.sqrt(width * width + height * height) or 1.0


def normalized_distance(a, b, size):
    return math.dist(a, b) / diagonal(size)


def proximity_weight(distance_px, radius_px):
    if radius_px <= 0:
        return 0.0
    return math.exp(-distance_px / radius_px)


def build_candidates(reference, target2text, image_root, fallback_size):
    by_image = defaultdict(list)
    seen = defaultdict(set)
    for example in reference:
        image = example.get("image", "")
        center = bbox_center(example)
        text = get_target_text(example, target2text)
        norm_text = normalize(text)
        if not image or center is None or not norm_text:
            continue
        key = (norm_text, round(center[0], 2), round(center[1], 2))
        if key in seen[image]:
            continue
        seen[image].add(key)
        size = image_size(image_root, image, fallback_size)
        by_image[image].append({
            "candidate_index": len(by_image[image]),
            "text": text,
            "target_id": example.get("target_id", ""),
            "img_usr_tgt": example.get("img_usr_tgt", ""),
            "x": center[0],
            "y": center[1],
            "norm_x": center[0] / size[0] if size[0] else 0.0,
            "norm_y": center[1] / size[1] if size[1] else 0.0,
        })
    return by_image


def best_evidence_for_point(point, query, candidates, size, radius_px):
    best = {
        "evidence": 0.0,
        "similarity": 0.0,
        "distance_px": "",
        "distance_norm": "",
        "candidate": "",
        "candidate_index": "",
    }
    for candidate in candidates:
        cpoint = (candidate["x"], candidate["y"])
        distance_px = math.dist(point, cpoint)
        sim = similarity(query, candidate["text"])
        evidence = sim * proximity_weight(distance_px, radius_px)
        if evidence > best["evidence"]:
            best = {
                "evidence": evidence,
                "similarity": sim,
                "distance_px": distance_px,
                "distance_norm": normalized_distance(point, cpoint, size),
                "candidate": candidate["text"],
                "candidate_index": candidate["candidate_index"],
            }
    return best


def analyze_example(index, example, candidates, target2text, size, args):
    query = get_target_text(example, target2text)
    points = [parse_point(point) for point in (example.get("prediction", []) or [])]
    points = [point for point in points if point is not None]
    radius_px = args.radius_px if args.radius_px > 0 else args.radius_norm * diagonal(size)

    best = {
        "evidence": 0.0,
        "similarity": 0.0,
        "distance_px": "",
        "distance_norm": "",
        "candidate": "",
        "candidate_index": "",
        "step": "",
    }
    last = best.copy()
    visited = set()
    step_rows = []

    for step, point in enumerate(points, start=1):
        step_best = best_evidence_for_point(point, query, candidates, size, radius_px)
        if step_best["candidate_index"] != "":
            distance_px = step_best["distance_px"]
            if distance_px != "" and distance_px <= radius_px:
                visited.add(step_best["candidate_index"])
        step_rows.append({
            "index": index,
            "img_usr_tgt": example.get("img_usr_tgt", index),
            "step": step,
            "x": point[0],
            "y": point[1],
            "best_evidence": step_best["evidence"],
            "best_similarity": step_best["similarity"],
            "best_distance_px": step_best["distance_px"],
            "best_distance_norm": step_best["distance_norm"],
            "best_candidate": step_best["candidate"],
        })
        if step_best["evidence"] > best["evidence"]:
            best = {**step_best, "step": step}
        last = {**step_best, "step": step}

    max_similarity_all = max((similarity(query, candidate["text"]) for candidate in candidates), default=0.0)
    top_candidate_all = ""
    if candidates:
        top_candidate_all = max(candidates, key=lambda candidate: similarity(query, candidate["text"]))["text"]

    gold = gold_status(example)
    pred = predicted_status(example)
    error_type = "correct"
    if gold == "absent" and pred == "present":
        error_type = "absent_false_present"
    elif gold == "present" and pred == "absent":
        error_type = "present_false_absent"
    elif gold == "absent" and pred == "absent":
        error_type = "correct_absent"
    elif gold == "present" and pred == "present":
        error_type = "correct_present"

    row = {
        "index": index,
        "img_usr_tgt": example.get("img_usr_tgt", index),
        "image": example.get("image", ""),
        "target": query,
        "gold_status": gold,
        "predicted_status": pred,
        "error_type": error_type,
        "prediction_len": len(points),
        "num_candidates": len(candidates),
        "visited_candidate_count": len(visited),
        "visited_candidate_rate": len(visited) / len(candidates) if candidates else 0.0,
        "path_best_evidence": best["evidence"],
        "path_best_similarity": best["similarity"],
        "path_best_distance_px": best["distance_px"],
        "path_best_distance_norm": best["distance_norm"],
        "path_best_candidate": best["candidate"],
        "path_best_step": best["step"],
        "path_last_evidence": last["evidence"],
        "path_last_similarity": last["similarity"],
        "path_last_distance_px": last["distance_px"],
        "path_last_distance_norm": last["distance_norm"],
        "path_last_candidate": last["candidate"],
        "max_candidate_similarity_all": max_similarity_all,
        "top_candidate_all": top_candidate_all,
        "raw_response": str(example.get("raw_response", ""))[:500],
    }
    return row, step_rows


def safe_div(num, den):
    return num / den if den else 0.0


def status_metrics(rows, threshold):
    confusion = Counter()
    for row in rows:
        pred = "absent" if row["path_best_evidence"] < threshold else "present"
        confusion[(row["gold_status"], pred)] += 1
    tp_absent = confusion[("absent", "absent")]
    fp_absent = confusion[("present", "absent")]
    fn_absent = confusion[("absent", "present")]
    tn_absent = confusion[("present", "present")]
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


def mean(values):
    values = [value for value in values if value != ""]
    return sum(values) / len(values) if values else 0.0


def summarize_rows(name, rows, threshold):
    confusion = Counter((row["gold_status"], row["predicted_status"]) for row in rows)
    groups = defaultdict(list)
    for row in rows:
        groups[row["error_type"]].append(row)

    low_evidence_false_present = [
        row for row in groups["absent_false_present"] if row["path_best_evidence"] < threshold
    ]
    high_evidence_false_absent = [
        row for row in groups["present_false_absent"] if row["path_best_evidence"] >= threshold
    ]
    return {
        "name": name,
        "num_examples": len(rows),
        "confusion": {
            "present->present": confusion[("present", "present")],
            "present->absent": confusion[("present", "absent")],
            "absent->present": confusion[("absent", "present")],
            "absent->absent": confusion[("absent", "absent")],
        },
        "mean_path_best_evidence": mean([row["path_best_evidence"] for row in rows]),
        "mean_visited_candidate_rate": mean([row["visited_candidate_rate"] for row in rows]),
        "low_evidence_threshold": threshold,
        "absent_false_present": len(groups["absent_false_present"]),
        "low_evidence_absent_false_present": len(low_evidence_false_present),
        "low_evidence_absent_false_present_rate": safe_div(
            len(low_evidence_false_present),
            len(groups["absent_false_present"]),
        ),
        "present_false_absent": len(groups["present_false_absent"]),
        "high_evidence_present_false_absent": len(high_evidence_false_absent),
        "high_evidence_present_false_absent_rate": safe_div(
            len(high_evidence_false_absent),
            len(groups["present_false_absent"]),
        ),
        "group_means": {
            group: {
                "count": len(group_rows),
                "path_best_evidence": mean([row["path_best_evidence"] for row in group_rows]),
                "visited_candidate_rate": mean([row["visited_candidate_rate"] for row in group_rows]),
                "prediction_len": mean([row["prediction_len"] for row in group_rows]),
            }
            for group, group_rows in sorted(groups.items())
        },
    }


def threshold_sweep(rows, step):
    thresholds = []
    value = 0.0
    while value <= 1.000001:
        thresholds.append(round(value, 4))
        value += step
    return [status_metrics(rows, threshold) for threshold in thresholds]


def write_summary_md(path, summaries, best_sweeps):
    lines = ["# Prediction Stopping Evidence", ""]
    for summary in summaries:
        lines.extend([
            f"## {summary['name']}",
            "",
            f"- Examples: {summary['num_examples']}",
            f"- Mean path-best evidence: {summary['mean_path_best_evidence']:.4f}",
            f"- Mean visited candidate rate: {summary['mean_visited_candidate_rate']:.4f}",
            f"- Low-evidence threshold: {summary['low_evidence_threshold']:.4f}",
            f"- Absent false-present: {summary['absent_false_present']}",
            f"- Low-evidence absent false-present: {summary['low_evidence_absent_false_present']} "
            f"({summary['low_evidence_absent_false_present_rate']:.4f})",
            f"- Present false-absent: {summary['present_false_absent']}",
            f"- High-evidence present false-absent: {summary['high_evidence_present_false_absent']} "
            f"({summary['high_evidence_present_false_absent_rate']:.4f})",
            "",
            "| Gold->Pred | Count |",
            "|---|---:|",
        ])
        for key, value in summary["confusion"].items():
            lines.append(f"| {key} | {value} |")
        best = best_sweeps.get(summary["name"])
        if best:
            lines.extend([
                "",
                "Best path-evidence threshold by absent F1:",
                "",
                "| Threshold | Accuracy | Absent Precision | Absent Recall | Absent F1 |",
                "|---:|---:|---:|---:|---:|",
                (
                    f"| {best['threshold']:.4f} | {best['accuracy']:.4f} | "
                    f"{best['absent_precision']:.4f} | {best['absent_recall']:.4f} | "
                    f"{best['absent_f1']:.4f} |"
                ),
            ])
        lines.extend([
            "",
            "| Group | Count | Mean Evidence | Mean Visited Rate | Mean Pred Len |",
            "|---|---:|---:|---:|---:|",
        ])
        for group, values in summary["group_means"].items():
            lines.append(
                f"| {group} | {values['count']} | {values['path_best_evidence']:.4f} | "
                f"{values['visited_candidate_rate']:.4f} | {values['prediction_len']:.2f} |"
            )
        lines.append("")

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main():
    parser = argparse.ArgumentParser(
        description="Analyze target-present/absent predictions as cognitive stopping evidence."
    )
    parser.add_argument("--reference", required=True, help="Original present VSGUI scanpath JSON.")
    parser.add_argument("--target2text", default="")
    parser.add_argument("--image-root", default="")
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--prediction", action="append", required=True, help="NAME=PATH prediction JSON. Can repeat.")
    parser.add_argument("--radius-px", type=float, default=0.0, help="Fixed evidence radius. Overrides --radius-norm if >0.")
    parser.add_argument("--radius-norm", type=float, default=0.08, help="Evidence radius as image diagonal fraction.")
    parser.add_argument("--low-evidence-threshold", type=float, default=0.2)
    parser.add_argument("--threshold-step", type=float, default=0.05)
    parser.add_argument("--fallback-width", type=float, default=1280)
    parser.add_argument("--fallback-height", type=float, default=720)
    args = parser.parse_args()

    target2text = load_json(Path(args.target2text)) if args.target2text else {}
    reference = load_json(Path(args.reference))
    image_root = Path(args.image_root) if args.image_root else None
    fallback_size = (args.fallback_width, args.fallback_height)
    candidates_by_image = build_candidates(reference, target2text, image_root, fallback_size)
    out_dir = Path(args.out_dir)

    summaries = []
    best_sweeps = {}
    for spec in args.prediction:
        if "=" not in spec:
            raise ValueError(f"Prediction must be NAME=PATH, got: {spec}")
        name, raw_path = spec.split("=", 1)
        prediction_path = Path(raw_path)
        examples = load_json(prediction_path)
        rows = []
        step_rows = []
        for idx, example in enumerate(examples):
            image = example.get("image", "")
            size = image_size(image_root, image, fallback_size)
            row, steps = analyze_example(
                idx,
                example,
                candidates_by_image.get(image, []),
                target2text,
                size,
                args,
            )
            rows.append(row)
            step_rows.extend(steps)

        detail_path = out_dir / f"{name}_stopping_evidence.csv"
        steps_path = out_dir / f"{name}_stopping_evidence_steps.csv"
        sweep_path = out_dir / f"{name}_stopping_evidence_threshold_sweep.csv"
        write_csv(detail_path, rows, list(rows[0].keys()) if rows else [])
        if step_rows:
            write_csv(steps_path, step_rows, list(step_rows[0].keys()))
        sweep = threshold_sweep(rows, args.threshold_step)
        write_csv(sweep_path, sweep, list(sweep[0].keys()) if sweep else [])
        best_sweeps[name] = max(sweep, key=lambda row: row["absent_f1"]) if sweep else None

        summary = summarize_rows(name, rows, args.low_evidence_threshold)
        summary.update({
            "prediction_file": str(prediction_path),
            "detail_csv": str(detail_path),
            "steps_csv": str(steps_path),
            "threshold_sweep_csv": str(sweep_path),
        })
        summaries.append(summary)

    write_json(out_dir / "stopping_evidence_summary.json", {
        "radius_px": args.radius_px,
        "radius_norm": args.radius_norm,
        "low_evidence_threshold": args.low_evidence_threshold,
        "models": summaries,
        "best_thresholds": best_sweeps,
    })
    write_summary_md(out_dir / "stopping_evidence_summary.md", summaries, best_sweeps)
    print(json.dumps({
        "models": [summary["name"] for summary in summaries],
        "summary_md": str(out_dir / "stopping_evidence_summary.md"),
        "summary_json": str(out_dir / "stopping_evidence_summary.json"),
    }, indent=2))


if __name__ == "__main__":
    main()
