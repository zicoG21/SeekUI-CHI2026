#!/usr/bin/env python
import argparse
import csv
import json
import random
from pathlib import Path


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def status(example):
    if "predicted_status" in example:
        return str(example.get("predicted_status") or "")
    if "target_present" in example:
        return "present" if example["target_present"] else "absent"
    return str(example.get("status") or "")


def prediction_len(example):
    return len(example.get("prediction", []) or [])


def matches(example, mode):
    pred_len = prediction_len(example)
    if mode == "all":
        return True
    if mode == "empty_prediction":
        return pred_len == 0
    if mode == "short_prediction":
        return pred_len <= 2
    if mode == "long_prediction":
        return pred_len >= 8
    if mode == "predicted_absent":
        return status(example) == "absent"
    if mode == "fallback":
        return bool(example.get("prediction_fallback"))
    if mode == "semantic_non_exact":
        return example.get("query_type") not in {None, "", "exact"}
    if mode == "prediction_edge_cases":
        return pred_len in {0, 1, 2} or status(example) == "absent" or bool(example.get("prediction_fallback"))
    return False


def sample_cases(data, mode, limit, seed):
    rng = random.Random(seed)
    candidates = [example for example in data if matches(example, mode)]
    rng.shuffle(candidates)
    return candidates[:limit], len(candidates)


def target_box(example):
    keys = ["target_x", "target_y", "target_width", "target_height"]
    values = [example.get(key) for key in keys]
    if any(value is None for value in values):
        return ""
    return ",".join(str(value) for value in values)


def review_row(example, source_name, review_type):
    return {
        "review_source": source_name,
        "review_type": review_type,
        "img_usr_tgt": example.get("img_usr_tgt", ""),
        "image": example.get("image", ""),
        "status": example.get("status", ""),
        "target_id": example.get("target_id", ""),
        "target": example.get("target", ""),
        "original_target": example.get("original_target", ""),
        "query_text": example.get("query_text", ""),
        "query_type": example.get("query_type", ""),
        "target_box": target_box(example),
        "predicted_status": example.get("predicted_status", ""),
        "prediction_len": prediction_len(example),
        "prediction_fallback": example.get("prediction_fallback", ""),
        "raw_response": str(example.get("raw_response", ""))[:500],
        "review_target_visible": "",
        "review_query_valid": "",
        "review_prediction_reasonable": "",
        "review_error_category": "",
        "review_notes": "",
    }


def write_review_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "review_source",
        "review_type",
        "img_usr_tgt",
        "image",
        "status",
        "target_id",
        "target",
        "original_target",
        "query_text",
        "query_type",
        "target_box",
        "predicted_status",
        "prediction_len",
        "prediction_fallback",
        "raw_response",
        "review_target_visible",
        "review_query_valid",
        "review_prediction_reasonable",
        "review_error_category",
        "review_notes",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_index_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "review_source",
        "img_usr_tgt",
        "image",
        "target",
        "query_text",
        "query_type",
        "status",
        "predicted_status",
        "prediction_len",
        "prediction_fallback",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def configs(outputs, limit, variants):
    return [
        {
            "name": "base_short_SeekUI",
            "path": outputs / f"predictions_SeekUI_{limit}.json",
            "mode": "short_prediction",
            "review_type": "prediction_quality_check",
        },
        {
            "name": "base_short_SeekUI_sft",
            "path": outputs / f"predictions_SeekUI_sft_{limit}.json",
            "mode": "short_prediction",
            "review_type": "prediction_quality_check",
        },
        {
            "name": "present_absent_predicted_absent_SeekUI",
            "path": outputs / "present_absent_predictions_SeekUI.json",
            "mode": "predicted_absent",
            "review_type": "absent_prediction_check",
        },
        {
            "name": "present_absent_predicted_absent_SeekUI_sft",
            "path": outputs / "present_absent_predictions_SeekUI_sft.json",
            "mode": "predicted_absent",
            "review_type": "absent_prediction_check",
        },
        {
            "name": "semantic_non_exact_SeekUI",
            "path": outputs / f"semantic_query_predictions_SeekUI_{limit}_v{variants}.json",
            "mode": "semantic_non_exact",
            "review_type": "semantic_prediction_check",
        },
        {
            "name": "semantic_non_exact_SeekUI_sft",
            "path": outputs / f"semantic_query_predictions_SeekUI_sft_{limit}_v{variants}.json",
            "mode": "semantic_non_exact",
            "review_type": "semantic_prediction_check",
        },
    ]


def main():
    parser = argparse.ArgumentParser(description="Generate qualitative review samples from available SeekUI predictions.")
    parser.add_argument("--work-dir", required=True)
    parser.add_argument("--limit", type=int, default=1362)
    parser.add_argument("--variants-per-example", type=int, default=2)
    parser.add_argument("--review-limit", type=int, default=50)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out-dir", default="")
    args = parser.parse_args()

    work_dir = Path(args.work_dir)
    outputs = work_dir / "outputs"
    out_dir = Path(args.out_dir) if args.out_dir else outputs / "review_cases"
    out_dir.mkdir(parents=True, exist_ok=True)

    combined_review_rows = []
    manifest = []
    for config in configs(outputs, args.limit, args.variants_per_example):
        path = config["path"]
        if not path.exists():
            manifest.append({"name": config["name"], "status": "missing", "path": str(path)})
            continue
        data = load_json(path)
        selected, candidate_count = sample_cases(data, config["mode"], args.review_limit, args.seed)
        sample_json = out_dir / f"{config['name']}.json"
        write_json(sample_json, selected)
        rows = [review_row(example, config["name"], config["review_type"]) for example in selected]
        write_index_csv(out_dir / f"{config['name']}.csv", rows)
        combined_review_rows.extend(rows)
        manifest.append({
            "name": config["name"],
            "status": "written",
            "path": str(path),
            "mode": config["mode"],
            "candidate_count": candidate_count,
            "selected_count": len(selected),
            "sample_json": str(sample_json),
            "index_csv": str(out_dir / f"{config['name']}.csv"),
        })

    if combined_review_rows:
        write_review_csv(out_dir / "prediction_edge_cases_review.csv", combined_review_rows)

    manifest_path = out_dir / "review_artifacts_manifest.json"
    write_json(manifest_path, manifest)

    print(f"Manifest: {manifest_path}")
    print(f"Combined review rows: {len(combined_review_rows)}")
    if combined_review_rows:
        print(f"Combined review CSV : {out_dir / 'prediction_edge_cases_review.csv'}")


if __name__ == "__main__":
    main()
