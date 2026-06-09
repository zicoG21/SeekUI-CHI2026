#!/usr/bin/env python
import argparse
import csv
import json
from pathlib import Path


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def status(example):
    if "target_present" in example:
        return "present" if example["target_present"] else "absent"
    return str(example.get("status", "") or "")


def prediction_len(example):
    return len(example.get("prediction", []) or [])


def target_box(example):
    keys = ["target_x", "target_y", "target_width", "target_height"]
    values = [example.get(key) for key in keys]
    if any(value is None for value in values):
        return ""
    return ",".join(str(value) for value in values)


def infer_review_type(example):
    if status(example) == "absent":
        return "absent_label_check"
    if example.get("query_type") and example.get("query_type") != "exact":
        return "semantic_query_check"
    if "prediction" in example:
        return "prediction_quality_check"
    return "dataset_check"


def row_for_example(index, example):
    return {
        "review_id": index,
        "review_type": infer_review_type(example),
        "img_usr_tgt": example.get("img_usr_tgt", ""),
        "image": example.get("image", ""),
        "status": status(example),
        "target_id": example.get("target_id", ""),
        "target": example.get("target", ""),
        "original_target": example.get("original_target", ""),
        "query_text": example.get("query_text", ""),
        "query_type": example.get("query_type", ""),
        "target_box": target_box(example),
        "source_image": example.get("absent_source_image", ""),
        "source_img_usr_tgt": example.get("absent_source_img_usr_tgt", ""),
        "destination_img_usr_tgt": example.get("absent_destination_img_usr_tgt", ""),
        "predicted_status": example.get("predicted_status", ""),
        "prediction_len": prediction_len(example),
        "raw_response": example.get("raw_response", "")[:500],
        "review_target_visible": "",
        "review_query_valid": "",
        "review_prediction_reasonable": "",
        "review_error_category": "",
        "review_notes": "",
    }


def main():
    parser = argparse.ArgumentParser(description="Export a CSV sheet for manual review of SeekUI datasets or predictions.")
    parser.add_argument("--input", required=True, help="Dataset or prediction JSON.")
    parser.add_argument("--output", required=True, help="CSV review sheet.")
    parser.add_argument("--status", default="", choices=["", "present", "absent"], help="Optional status filter.")
    parser.add_argument("--query-type", default="", help="Optional query_type filter, e.g. exact or functional_template.")
    parser.add_argument("--mode", default="all", choices=[
        "all",
        "absent",
        "semantic_non_exact",
        "prediction_edge_cases",
    ])
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    data = load_json(Path(args.input))
    rows = []
    for example in data:
        example_status = status(example)
        if args.status and example_status != args.status:
            continue
        if args.query_type and example.get("query_type", "") != args.query_type:
            continue
        if args.mode == "absent" and example_status != "absent":
            continue
        if args.mode == "semantic_non_exact" and example.get("query_type") in {None, "", "exact"}:
            continue
        if args.mode == "prediction_edge_cases":
            pred_len = prediction_len(example)
            predicted_status = str(example.get("predicted_status", "") or "")
            if pred_len not in {0, 1, 2} and predicted_status != "absent":
                continue
        rows.append(row_for_example(len(rows), example))
        if args.limit and len(rows) >= args.limit:
            break

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "review_id",
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
        "source_image",
        "source_img_usr_tgt",
        "destination_img_usr_tgt",
        "predicted_status",
        "prediction_len",
        "raw_response",
        "review_target_visible",
        "review_query_valid",
        "review_prediction_reasonable",
        "review_error_category",
        "review_notes",
    ]
    with open(output, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Input examples : {len(data)}")
    print(f"Review rows    : {len(rows)}")
    print(f"Output         : {output}")


if __name__ == "__main__":
    main()
