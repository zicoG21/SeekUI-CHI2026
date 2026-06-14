#!/usr/bin/env python
import argparse
import csv
import json
from pathlib import Path


SWEEP_GLOBS = [
    "present_absent_predictions_*_combined_*_threshold_sweep.csv",
    "present_absent_predictions_*_color_aware_*_threshold_sweep.csv",
    "present_absent_predictions_*_annotation_free_combined_*_threshold_sweep.csv",
    "present_absent_predictions_*_cognitive_stop_*_threshold_sweep.csv",
    "present_absent_predictions_*_ocr_candidate_verifier_*_threshold_sweep.csv",
    "present_absent_predictions_*_candidate_verifier_*_threshold_sweep.csv",
    "stopping_evidence/*_stopping_evidence_threshold_sweep.csv",
    "annotation_free_stopping_evidence/*_annotation_free_stopping_evidence_threshold_sweep.csv",
    "cognitive_process/cognitive_process_threshold_sweep.csv",
]

STATUS_EVAL_GLOBS = [
    "*_status_eval.json",
    "real_absent_validation*/**/*_status_eval.json",
    "candidate_crop_verifier/**/status_eval.json",
]

THRESHOLD_FIELDS = [
    "threshold",
    "cognitive_threshold",
    "ocr_threshold",
    "candidate_threshold",
    "score_threshold",
]


def read_csv(path):
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def as_float(value, default=0.0):
    try:
        if value in {"", None}:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def as_int(value, default=0):
    try:
        if value in {"", None}:
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def safe_div(num, den):
    return num / den if den else 0.0


def fmt(value):
    return f"{as_float(value):.4f}"


def parse_cost_ratios(raw):
    ratios = []
    for item in raw.replace(";", ",").split(","):
        item = item.strip()
        if not item:
            continue
        if ":" in item:
            p_to_a, a_to_p = item.split(":", 1)
        elif "/" in item:
            p_to_a, a_to_p = item.split("/", 1)
        else:
            p_to_a, a_to_p = item, "1"
        ratios.append({
            "label": f"PtoA:{as_float(p_to_a):g}_AtoP:{as_float(a_to_p):g}",
            "present_false_absent_cost": as_float(p_to_a),
            "absent_false_present_cost": as_float(a_to_p),
        })
    if not ratios:
        raise ValueError("No valid cost ratios provided")
    return ratios


def discover_sweeps(outputs):
    paths = []
    seen = set()
    for pattern in SWEEP_GLOBS:
        for path in sorted(outputs.glob(pattern)):
            if path in seen:
                continue
            seen.add(path)
            paths.append(path)
    return paths


def discover_status_evals(outputs):
    paths = []
    seen = set()
    for pattern in STATUS_EVAL_GLOBS:
        for path in sorted(outputs.glob(pattern)):
            if path in seen:
                continue
            name = path.name
            if "_filtered_status_eval" in name:
                continue
            seen.add(path)
            paths.append(path)
    return paths


def infer_method(path, outputs):
    rel = path.relative_to(outputs)
    stem = path.name.removesuffix("_threshold_sweep.csv")
    if stem.startswith("present_absent_predictions_"):
        stem = stem.removeprefix("present_absent_predictions_")
    model = ""
    if stem.startswith("SeekUI_sft_"):
        model = "SeekUI_sft"
        variant = stem.removeprefix("SeekUI_sft_")
    elif stem.startswith("SeekUI_"):
        model = "SeekUI"
        variant = stem.removeprefix("SeekUI_")
    elif "SeekUI_sft" in stem:
        model = "SeekUI_sft"
        variant = stem
    elif "SeekUI" in stem:
        model = "SeekUI"
        variant = stem
    else:
        variant = stem
    return {
        "model": model,
        "variant": variant,
        "method": f"{model}_{variant}" if model else variant,
        "sweep_path": str(rel),
    }


def infer_status_eval_method(path, outputs):
    rel = path.relative_to(outputs)
    parent = path.parent.name
    stem = path.name.removesuffix("_status_eval.json")
    if stem == "status_eval":
        stem = parent
    if stem.startswith("present_absent_predictions_"):
        stem = stem.removeprefix("present_absent_predictions_")
    elif stem.startswith("vlm_presence_predictions_"):
        stem = stem.removeprefix("vlm_presence_predictions_")
    elif stem.startswith("vlm_evidence_predictions_"):
        stem = stem.removeprefix("vlm_evidence_predictions_")

    model = ""
    if stem.startswith("SeekUI_sft_"):
        model = "SeekUI_sft"
        variant = stem.removeprefix("SeekUI_sft_")
    elif stem.startswith("SeekUI_"):
        model = "SeekUI"
        variant = stem.removeprefix("SeekUI_")
    else:
        variant = stem

    return {
        "model": model,
        "variant": variant,
        "method": f"{model}_{variant}" if model else variant,
        "sweep_path": str(rel),
    }


def threshold_spec(row):
    parts = []
    for field in THRESHOLD_FIELDS:
        if row.get(field) not in {"", None}:
            parts.append(f"{field}={row[field]}")
    for field in ["rule", "mode"]:
        if row.get(field):
            parts.append(f"{field}={row[field]}")
    return "; ".join(parts)


def point_from_row(method_info, row):
    pp = as_int(row.get("present_present"))
    pa = as_int(row.get("present_absent"))
    ap = as_int(row.get("absent_present"))
    aa = as_int(row.get("absent_absent"))
    present_total = pp + pa
    absent_total = ap + aa
    total = present_total + absent_total
    absent_precision = as_float(row.get("absent_precision"), safe_div(aa, aa + pa))
    absent_recall = as_float(row.get("absent_recall"), safe_div(aa, absent_total))
    accuracy = as_float(row.get("accuracy"), safe_div(pp + aa, total))
    absent_f1 = as_float(
        row.get("absent_f1"),
        safe_div(2 * absent_precision * absent_recall, absent_precision + absent_recall),
    )
    return {
        **method_info,
        "point_type": method_info.get("point_type", "threshold"),
        "threshold_spec": threshold_spec(row),
        "accuracy": accuracy,
        "absent_precision": absent_precision,
        "absent_recall": absent_recall,
        "absent_f1": absent_f1,
        "roc_tpr": absent_recall,
        "roc_fpr": safe_div(pa, present_total),
        "specificity": safe_div(pp, present_total),
        "present_false_absent_rate": safe_div(pa, present_total),
        "absent_false_present_rate": safe_div(ap, absent_total),
        "predicted_absent_rate": safe_div(pa + aa, total),
        "total": total,
        "present_total": present_total,
        "absent_total": absent_total,
        "present_present": pp,
        "present_absent": pa,
        "absent_present": ap,
        "absent_absent": aa,
        "changed_predictions": row.get("changed_predictions", ""),
    }


def point_from_status_eval(method_info, summary):
    confusion = summary.get("confusion", {})
    row = {
        "present_present": confusion.get("present->present", 0),
        "present_absent": confusion.get("present->absent", 0),
        "absent_present": confusion.get("absent->present", 0),
        "absent_absent": confusion.get("absent->absent", 0),
        "accuracy": summary.get("accuracy", ""),
        "absent_precision": summary.get("absent_precision", ""),
        "absent_recall": summary.get("absent_recall", ""),
        "absent_f1": summary.get("absent_f1", ""),
    }
    info = {**method_info, "point_type": "fixed_status_eval"}
    point = point_from_row(info, row)
    point["threshold_spec"] = "fixed"
    return point


def collect_points(outputs):
    points = []
    for path in discover_sweeps(outputs):
        method_info = infer_method(path, outputs)
        for row in read_csv(path):
            point = point_from_row(method_info, row)
            if point["total"] <= 0:
                continue
            points.append(point)
    return points


def collect_status_eval_points(outputs):
    points = []
    for path in discover_status_evals(outputs):
        try:
            with open(path, "r", encoding="utf-8") as f:
                summary = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        if "confusion" not in summary:
            continue
        point = point_from_status_eval(infer_status_eval_method(path, outputs), summary)
        if point["total"] > 0:
            points.append(point)
    return points


def best_by_f1(points):
    best = {}
    for point in points:
        key = point["method"]
        current = best.get(key)
        if current is None or (
            point["absent_f1"],
            point["accuracy"],
            point["absent_precision"],
        ) > (
            current["absent_f1"],
            current["accuracy"],
            current["absent_precision"],
        ):
            best[key] = point
    return sorted(best.values(), key=lambda row: (row["absent_f1"], row["accuracy"]), reverse=True)


def utility_rows(points, ratios):
    rows = []
    by_method = {}
    for point in points:
        by_method.setdefault(point["method"], []).append(point)
    for ratio in ratios:
        p_cost = ratio["present_false_absent_cost"]
        a_cost = ratio["absent_false_present_cost"]
        for method, method_points in by_method.items():
            enriched = []
            for point in method_points:
                total_cost = p_cost * point["present_absent"] + a_cost * point["absent_present"]
                enriched.append({
                    **point,
                    "cost_ratio": ratio["label"],
                    "present_false_absent_cost": p_cost,
                    "absent_false_present_cost": a_cost,
                    "weighted_error_cost": total_cost,
                    "expected_cost_per_example": safe_div(total_cost, point["total"]),
                })
            best = min(
                enriched,
                key=lambda row: (
                    row["expected_cost_per_example"],
                    -row["absent_f1"],
                    -row["accuracy"],
                ),
            )
            rows.append(best)
    return sorted(rows, key=lambda row: (row["cost_ratio"], row["expected_cost_per_example"], -row["absent_f1"]))


def compact_row(row):
    keep = [
        "point_type",
        "method",
        "model",
        "variant",
        "threshold_spec",
        "accuracy",
        "absent_precision",
        "absent_recall",
        "absent_f1",
        "roc_tpr",
        "roc_fpr",
        "present_false_absent_rate",
        "absent_false_present_rate",
        "predicted_absent_rate",
        "present_absent",
        "absent_present",
        "total",
    ]
    return {key: row.get(key, "") for key in keep}


def compact_utility_row(row):
    data = compact_row(row)
    data.update({
        "cost_ratio": row.get("cost_ratio", ""),
        "present_false_absent_cost": row.get("present_false_absent_cost", ""),
        "absent_false_present_cost": row.get("absent_false_present_cost", ""),
        "weighted_error_cost": row.get("weighted_error_cost", ""),
        "expected_cost_per_example": row.get("expected_cost_per_example", ""),
    })
    return data


def write_markdown(path, points, best_rows, utilities, ratios, title="PR/ROC and Cost-Sensitive Utility"):
    threshold_count = sum(1 for row in points if row.get("point_type") == "threshold")
    fixed_count = sum(1 for row in points if row.get("point_type") == "fixed_status_eval")
    lines = [
        f"# {title}",
        "",
        f"- Threshold points: {threshold_count}",
        f"- Fixed status-eval points: {fixed_count}",
        f"- Methods included: {len({row['method'] for row in points})}",
        f"- Cost ratios: {', '.join(ratio['label'] for ratio in ratios)}",
        "",
        "Interpretation: `P->A` is a visible target rejected as absent; `A->P` is a missing target incorrectly grounded as present.",
        "",
        "## Best by Absent F1",
        "",
        "| Method | Type | Thresholds | Acc | Precision | Recall | F1 | FPR | P->A | A->P |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in best_rows[:12]:
        lines.append(
            f"| {row['method']} | {row.get('point_type', '')} | {row['threshold_spec']} | {fmt(row['accuracy'])} | "
            f"{fmt(row['absent_precision'])} | {fmt(row['absent_recall'])} | {fmt(row['absent_f1'])} | "
            f"{fmt(row['roc_fpr'])} | {row['present_absent']} | {row['absent_present']} |"
        )

    lines.extend([
        "",
        "## Cost-Sensitive Optima",
        "",
        "| Cost Ratio | Method | Thresholds | Expected Cost | Acc | F1 | P->A | A->P |",
        "|---|---|---|---:|---:|---:|---:|---:|",
    ])
    for row in utilities[:40]:
        lines.append(
            f"| {row['cost_ratio']} | {row['method']} | {row['threshold_spec']} | "
            f"{fmt(row['expected_cost_per_example'])} | {fmt(row['accuracy'])} | "
            f"{fmt(row['absent_f1'])} | {row['present_absent']} | {row['absent_present']} |"
        )

    lines.extend([
        "",
        "## Writing Notes",
        "",
        "- Use the PR/ROC CSV to show that improvements are not a single hand-picked F1 point.",
        "- Use the utility table to make the conservative stopping tradeoff explicit.",
        "- If missing-target grounding is more costly than false absence, choose rows where `AtoP` cost is high.",
        "- If false absence is more costly, choose rows where `PtoA` cost is high and compare how much not-found safety remains.",
        "",
    ])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Export PR/ROC points and cost-sensitive utility summaries.")
    parser.add_argument("--work-dir", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--include-status-evals", action="store_true", default=True)
    parser.add_argument(
        "--cost-ratios",
        default="1:1,2:1,5:1,10:1,1:2,1:5,1:10",
        help="Comma-separated P->A:A->P error costs. Example: 2:1,1:5",
    )
    parser.add_argument("--method-contains", default="", help="Keep only methods whose name contains this substring.")
    parser.add_argument("--title", default="PR/ROC and Cost-Sensitive Utility")
    args = parser.parse_args()

    work_dir = Path(args.work_dir)
    out_dir = Path(args.out_dir)
    outputs = work_dir / "outputs"
    ratios = parse_cost_ratios(args.cost_ratios)
    points = collect_points(outputs)
    if args.include_status_evals:
        points.extend(collect_status_eval_points(outputs))
    if args.method_contains:
        points = [point for point in points if args.method_contains in point.get("method", "")]
    best_rows = best_by_f1(points)
    utilities = utility_rows(points, ratios) if points else []

    write_csv(out_dir / "tradeoff_points.csv", [compact_row(row) for row in points])
    write_csv(out_dir / "tradeoff_best_by_f1.csv", [compact_row(row) for row in best_rows])
    write_csv(out_dir / "tradeoff_cost_utility.csv", [compact_utility_row(row) for row in utilities])
    write_json(out_dir / "tradeoff_summary.json", {
        "work_dir": str(work_dir),
        "threshold_points": len(points),
        "methods": sorted({row["method"] for row in points}),
        "cost_ratios": ratios,
        "best_by_f1": [compact_row(row) for row in best_rows[:20]],
        "utility_rows": [compact_utility_row(row) for row in utilities[:80]],
    })
    write_markdown(out_dir / "tradeoff_summary.md", points, best_rows, utilities, ratios, args.title)
    print(json.dumps({
        "threshold_points": len(points),
        "methods": len({row["method"] for row in points}),
        "out_dir": str(out_dir),
    }, indent=2))


if __name__ == "__main__":
    main()
