#!/usr/bin/env python
import argparse
import csv
import json
import math
from collections import defaultdict
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


def write_csv(path, rows, fieldnames=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = list(rows[0].keys()) if rows else []
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def safe_float(value, default=None):
    try:
        if value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_div(num, den):
    return num / den if den else 0.0


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


def parse_point(point):
    if not isinstance(point, (list, tuple)) or len(point) < 2:
        return None
    x = safe_float(point[0])
    y = safe_float(point[1])
    if x is None or y is None:
        return None
    return x, y


def target_center(example):
    x = safe_float(example.get("target_x"))
    y = safe_float(example.get("target_y"))
    w = safe_float(example.get("target_width"))
    h = safe_float(example.get("target_height"))
    if x is None or y is None or w is None or h is None or w <= 0 or h <= 0:
        return None
    return x + w / 2.0, y + h / 2.0


def image_size(image_root, rel_path, fallback):
    if not image_root or Image is None:
        return fallback
    path = image_root / rel_path
    if not path.exists():
        return fallback
    with Image.open(path) as im:
        return im.size


def diagonal(size):
    width, height = size
    return math.sqrt(width * width + height * height) or 1.0


def path_length(points):
    if len(points) < 2:
        return 0.0
    return sum(math.dist(a, b) for a, b in zip(points, points[1:]))


def revisit_count(points, radius_px):
    revisits = 0
    for i, point in enumerate(points):
        if any(math.dist(point, previous) <= radius_px for previous in points[:i]):
            revisits += 1
    return revisits


def grid_coverage(points, size, grid):
    width, height = size
    cells = set()
    for x, y in points:
        if width <= 0 or height <= 0:
            continue
        gx = min(grid - 1, max(0, int((x / width) * grid)))
        gy = min(grid - 1, max(0, int((y / height) * grid)))
        cells.add((gx, gy))
    return len(cells), safe_div(len(cells), grid * grid)


def centroid(points):
    if not points:
        return None
    return sum(p[0] for p in points) / len(points), sum(p[1] for p in points) / len(points)


def convergence_score(points, size):
    if len(points) < 2:
        return 1.0 if points else 0.0
    diag = diagonal(size)
    first_half = points[: max(1, len(points) // 2)]
    last_half = points[len(points) // 2 :]
    first_centroid = centroid(first_half)
    last_centroid = centroid(last_half)
    if first_centroid is None or last_centroid is None:
        return 0.0
    movement = math.dist(first_centroid, last_centroid) / diag
    last_spread = sum(math.dist(p, last_centroid) for p in last_half) / len(last_half) / diag
    return max(0.0, 1.0 - movement - last_spread)


def error_type(gold, pred):
    if gold == "present" and pred == "present":
        return "correct_present"
    if gold == "absent" and pred == "absent":
        return "correct_absent"
    if gold == "present" and pred == "absent":
        return "present_false_absent"
    return "absent_false_present"


def analyze_example(index, model, example, image_root, args):
    points = [parse_point(p) for p in (example.get("prediction", []) or [])]
    points = [p for p in points if p is not None]
    size = image_size(image_root, example.get("image", ""), (args.fallback_width, args.fallback_height))
    diag = diagonal(size)
    target = target_center(example)
    length_px = path_length(points)
    revisit_radius = args.revisit_radius_px if args.revisit_radius_px > 0 else args.revisit_radius_norm * diag
    revisits = revisit_count(points, revisit_radius)
    cells, coverage = grid_coverage(points, size, args.grid)
    gold = gold_status(example)
    pred = predicted_status(example)

    first_to_target = ""
    last_to_target = ""
    min_to_target = ""
    if gold == "present" and target and points:
        distances = [math.dist(p, target) for p in points]
        first_to_target = distances[0]
        last_to_target = distances[-1]
        min_to_target = min(distances)

    return {
        "model": model,
        "index": index,
        "img_usr_tgt": example.get("img_usr_tgt", index),
        "image": example.get("image", ""),
        "target": example.get("target", example.get("original_target", "")),
        "gold_status": gold,
        "predicted_status": pred,
        "error_type": error_type(gold, pred),
        "prediction_len": len(points),
        "path_length_px": length_px,
        "path_length_norm": length_px / diag,
        "grid_cells_visited": cells,
        "grid_coverage": coverage,
        "revisit_count": revisits,
        "revisit_rate": safe_div(revisits, len(points)),
        "convergence_score": convergence_score(points, size),
        "first_to_target_px": first_to_target,
        "last_to_target_px": last_to_target,
        "min_to_target_px": min_to_target,
        "status_changed": int(str(example.get("original_predicted_status", "")) not in {"", pred}),
    }


def mean(values):
    clean = [v for v in values if isinstance(v, (int, float))]
    return sum(clean) / len(clean) if clean else 0.0


def count_numeric(values):
    return sum(1 for v in values if isinstance(v, (int, float)))


def summarize(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[(row["model"], "all", "all")].append(row)
        groups[(row["model"], "gold_status", row["gold_status"])].append(row)
        groups[(row["model"], "predicted_status", row["predicted_status"])].append(row)
        groups[(row["model"], "error_type", row["error_type"])].append(row)

    metrics = [
        "prediction_len",
        "path_length_norm",
        "grid_coverage",
        "revisit_rate",
        "convergence_score",
        "first_to_target_px",
        "last_to_target_px",
        "min_to_target_px",
    ]
    summary_rows = []
    for (model, group_field, group_value), group_rows in sorted(groups.items()):
        out = {
            "model": model,
            "group_field": group_field,
            "group_value": group_value,
            "count": len(group_rows),
        }
        for metric in metrics:
            values = [row.get(metric) for row in group_rows]
            out[f"mean_{metric}"] = mean(values)
            out[f"n_{metric}"] = count_numeric(values)
        summary_rows.append(out)
    return summary_rows


def write_md(path, summary_rows):
    lines = [
        "# Behavioral Search Metrics",
        "",
        "Target-distance metrics are computed only for gold-present examples.",
        "",
        "| Model | Group | Value | Count | Pred Len | Path Len Norm | Coverage | Revisit Rate | Convergence | Last Target Dist | Target Dist N |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in summary_rows:
        if row["group_field"] not in {"all", "gold_status", "error_type"}:
            continue
        lines.append(
            f"| {row['model']} | {row['group_field']} | {row['group_value']} | {row['count']} | "
            f"{row['mean_prediction_len']:.2f} | {row['mean_path_length_norm']:.4f} | "
            f"{row['mean_grid_coverage']:.4f} | {row['mean_revisit_rate']:.4f} | "
            f"{row['mean_convergence_score']:.4f} | {row['mean_last_to_target_px']:.2f} | "
            f"{row['n_last_to_target_px']} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Compute behavioral scanpath metrics for present/absent predictions.")
    parser.add_argument("--prediction", action="append", required=True, help="NAME=PATH. Can repeat.")
    parser.add_argument("--image-root", default="")
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--grid", type=int, default=4)
    parser.add_argument("--revisit-radius-px", type=float, default=0.0)
    parser.add_argument("--revisit-radius-norm", type=float, default=0.04)
    parser.add_argument("--fallback-width", type=float, default=1280)
    parser.add_argument("--fallback-height", type=float, default=720)
    args = parser.parse_args()

    image_root = Path(args.image_root) if args.image_root else None
    out_dir = Path(args.out_dir)
    all_rows = []
    for spec in args.prediction:
        if "=" not in spec:
            raise ValueError(f"Prediction must be NAME=PATH, got {spec}")
        model, raw_path = spec.split("=", 1)
        examples = load_json(Path(raw_path))
        rows = [analyze_example(idx, model, example, image_root, args) for idx, example in enumerate(examples)]
        write_csv(out_dir / f"{model}_behavioral_metrics.csv", rows)
        all_rows.extend(rows)

    summary_rows = summarize(all_rows)
    write_csv(out_dir / "behavioral_metrics_rows.csv", all_rows)
    write_csv(out_dir / "behavioral_metrics_summary.csv", summary_rows)
    write_json(out_dir / "behavioral_metrics_summary.json", {
        "num_rows": len(all_rows),
        "grid": args.grid,
        "revisit_radius_px": args.revisit_radius_px,
        "revisit_radius_norm": args.revisit_radius_norm,
        "summary": summary_rows,
    })
    write_md(out_dir / "behavioral_metrics_summary.md", summary_rows)
    print(json.dumps({
        "num_rows": len(all_rows),
        "summary_md": str(out_dir / "behavioral_metrics_summary.md"),
        "summary_csv": str(out_dir / "behavioral_metrics_summary.csv"),
    }, indent=2))


if __name__ == "__main__":
    main()
