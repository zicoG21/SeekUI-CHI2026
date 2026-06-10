#!/usr/bin/env python
import argparse
import csv
import json
import math
from pathlib import Path


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def prediction_len(example):
    return len(example.get("prediction", []) or [])


def target_present(example):
    if "target_present" in example:
        return bool(example["target_present"])
    status = str(example.get("status", "") or "").casefold()
    return status != "absent"


def predicted_status(example):
    status = str(example.get("predicted_status", "") or "").casefold()
    if status in {"present", "absent"}:
        return status
    return "present" if prediction_len(example) else "absent"


def target_center(example):
    keys = ["target_x", "target_y", "target_width", "target_height"]
    values = [example.get(key) for key in keys]
    if any(value is None for value in values):
        return None
    try:
        x, y, w, h = [float(value) for value in values]
    except (TypeError, ValueError):
        return None
    if w <= 0 or h <= 0:
        return None
    return x + w / 2, y + h / 2


def last_to_target(example):
    points = example.get("prediction", []) or []
    center = target_center(example)
    if not points or center is None:
        return None
    try:
        x, y = [float(value) for value in points[-1][:2]]
    except (TypeError, ValueError, IndexError):
        return None
    return math.dist((x, y), center)


def first_to_gt(example):
    pred = example.get("prediction", []) or []
    xs = example.get("x", []) or []
    ys = example.get("y", []) or []
    if not pred or not xs or not ys:
        return None
    try:
        return math.dist((float(pred[0][0]), float(pred[0][1])), (float(xs[0]), float(ys[0])))
    except (TypeError, ValueError, IndexError):
        return None


def row_for(example, source, failure_type, score):
    distance = last_to_target(example)
    first_distance = first_to_gt(example)
    return {
        "source": source,
        "failure_type": failure_type,
        "score": "" if score is None else f"{score:.6f}",
        "img_usr_tgt": example.get("img_usr_tgt", ""),
        "image": example.get("image", ""),
        "target": example.get("target", ""),
        "original_target": example.get("original_target", ""),
        "query_text": example.get("query_text", ""),
        "query_type": example.get("query_type", ""),
        "target_present": target_present(example),
        "predicted_status": predicted_status(example),
        "prediction_len": prediction_len(example),
        "last_to_target": "" if distance is None else f"{distance:.6f}",
        "first_to_gt": "" if first_distance is None else f"{first_distance:.6f}",
        "raw_response": str(example.get("raw_response", ""))[:500],
    }


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "source",
        "failure_type",
        "score",
        "img_usr_tgt",
        "image",
        "target",
        "original_target",
        "query_text",
        "query_type",
        "target_present",
        "predicted_status",
        "prediction_len",
        "last_to_target",
        "first_to_gt",
        "raw_response",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def first_n(data, limit, predicate, score_fn=None):
    selected = []
    for example in data:
        if predicate(example):
            score = score_fn(example) if score_fn else None
            selected.append((score, example))
            if len(selected) >= limit:
                break
    return selected


def top_by_distance(data, limit, predicate):
    scored = []
    for example in data:
        if not predicate(example):
            continue
        score = last_to_target(example)
        if score is not None:
            scored.append((score, example))
    scored.sort(key=lambda item: item[0], reverse=True)
    return scored[:limit]


def prediction_paths(outputs, limit, variants):
    return {
        "SeekUI_present_absent": outputs / "present_absent_predictions_SeekUI.json",
        "SeekUI_sft_present_absent": outputs / "present_absent_predictions_SeekUI_sft.json",
        "SeekUI_image_cue": outputs / f"image_cue_predictions_SeekUI_{limit}.json",
        "SeekUI_sft_image_cue": outputs / f"image_cue_predictions_SeekUI_sft_{limit}.json",
        "SeekUI_semantic": outputs / f"semantic_query_predictions_SeekUI_{limit}_v{variants}.json",
        "SeekUI_sft_semantic": outputs / f"semantic_query_predictions_SeekUI_sft_{limit}_v{variants}.json",
    }


def add_bundle(bundles, combined_rows, name, out_prefix, examples, failure_type):
    rows = [row_for(example, name, failure_type, score) for score, example in examples]
    write_json(out_prefix.with_suffix(".json"), [example for _, example in examples])
    write_csv(out_prefix.with_suffix(".csv"), rows)
    combined_rows.extend(rows)
    bundles.append({
        "name": out_prefix.name,
        "failure_type": failure_type,
        "count": len(rows),
        "json": str(out_prefix.with_suffix(".json")),
        "csv": str(out_prefix.with_suffix(".csv")),
    })


def main():
    parser = argparse.ArgumentParser(description="Mine high-value failure cases from SeekUI follow-up predictions.")
    parser.add_argument("--work-dir", required=True)
    parser.add_argument("--limit", type=int, default=1362)
    parser.add_argument("--variants-per-example", type=int, default=2)
    parser.add_argument("--case-limit", type=int, default=30)
    parser.add_argument("--out-dir", default="")
    args = parser.parse_args()

    work_dir = Path(args.work_dir)
    outputs = work_dir / "outputs"
    out_dir = Path(args.out_dir) if args.out_dir else outputs / "failure_cases"
    out_dir.mkdir(parents=True, exist_ok=True)

    bundles = []
    combined_rows = []
    sources = []

    for name, path in prediction_paths(outputs, args.limit, args.variants_per_example).items():
        if not path.exists():
            sources.append({"source": name, "status": "missing", "path": str(path)})
            continue

        data = load_json(path)
        sources.append({"source": name, "status": "loaded", "path": str(path), "num_examples": len(data)})

        if "present_absent" in name:
            add_bundle(
                bundles,
                combined_rows,
                name,
                out_dir / f"{name}_absent_false_present",
                first_n(data, args.case_limit, lambda ex: not target_present(ex) and predicted_status(ex) == "present"),
                "absent_false_present",
            )
            add_bundle(
                bundles,
                combined_rows,
                name,
                out_dir / f"{name}_present_false_absent",
                first_n(data, args.case_limit, lambda ex: target_present(ex) and predicted_status(ex) == "absent"),
                "present_false_absent",
            )

        if "image_cue" in name:
            add_bundle(
                bundles,
                combined_rows,
                name,
                out_dir / f"{name}_far_from_target",
                top_by_distance(data, args.case_limit, lambda ex: target_present(ex)),
                "far_from_target",
            )

        if "semantic" in name:
            add_bundle(
                bundles,
                combined_rows,
                name,
                out_dir / f"{name}_association_predicted_absent",
                first_n(
                    data,
                    args.case_limit,
                    lambda ex: ex.get("query_type") == "association_mapping" and predicted_status(ex) == "absent",
                ),
                "association_predicted_absent",
            )
            add_bundle(
                bundles,
                combined_rows,
                name,
                out_dir / f"{name}_association_far_from_target",
                top_by_distance(
                    data,
                    args.case_limit,
                    lambda ex: ex.get("query_type") == "association_mapping" and predicted_status(ex) == "present",
                ),
                "association_far_from_target",
            )
            add_bundle(
                bundles,
                combined_rows,
                name,
                out_dir / f"{name}_one_fixation_present",
                first_n(data, args.case_limit, lambda ex: target_present(ex) and prediction_len(ex) <= 1),
                "one_fixation_present",
            )

    write_csv(out_dir / "failure_cases_index.csv", combined_rows)
    write_json(out_dir / "failure_cases_manifest.json", {
        "sources": sources,
        "bundles": bundles,
        "num_rows": len(combined_rows),
    })

    lines = [
        "# Failure Case Mining",
        "",
        f"- Output directory: `{out_dir}`",
        f"- Total indexed rows: {len(combined_rows)}",
        "",
        "| Bundle | Failure type | Count |",
        "|---|---|---:|",
    ]
    for bundle in bundles:
        lines.append(f"| {bundle['name']} | {bundle['failure_type']} | {bundle['count']} |")
    (out_dir / "failure_cases_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Output directory: {out_dir}")
    print(f"Combined CSV    : {out_dir / 'failure_cases_index.csv'}")
    print(f"Manifest        : {out_dir / 'failure_cases_manifest.json'}")
    print(f"Summary         : {out_dir / 'failure_cases_summary.md'}")


if __name__ == "__main__":
    main()
