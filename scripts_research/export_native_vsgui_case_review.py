#!/usr/bin/env python
import argparse
import csv
import json
from pathlib import Path


ABSENT_STATUSES = {"absent", "not_found", "not found", "no object", "no target", "not present"}
CASE_TYPES = [
    "prompt_absent_false_present",
    "combined_corrected_absent_false_present",
    "combined_kept_absent_false_present",
    "combined_new_present_false_absent",
    "vlm_wrong_combined_correct",
    "combined_wrong_vlm_correct",
    "both_wrong_absent",
    "both_wrong_present",
]


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


def correct(gold, pred):
    return gold == pred


def key_for(example, idx):
    return str(example.get("img_usr_tgt") or example.get("key") or idx)


def prediction_len(example):
    return len(example.get("prediction", []) or [])


def row_for(idx, prompt, combined, vlm, case_type):
    gold = gold_status(prompt)
    prompt_pred = predicted_status(prompt)
    combined_pred = predicted_status(combined)
    vlm_pred = predicted_status(vlm) if vlm else ""
    return {
        "index": idx,
        "case_type": case_type,
        "key": key_for(prompt, idx),
        "image": prompt.get("image", ""),
        "target": prompt.get("query_text") or prompt.get("target") or prompt.get("original_target", ""),
        "cue": prompt.get("cue", ""),
        "gold_status": gold,
        "prompt_status": prompt_pred,
        "combined_status": combined_pred,
        "vlm_status": vlm_pred,
        "prompt_correct": int(correct(gold, prompt_pred)),
        "combined_correct": int(correct(gold, combined_pred)),
        "vlm_correct": int(correct(gold, vlm_pred)) if vlm else "",
        "prompt_prediction_len": prediction_len(prompt),
        "combined_prediction_len": prediction_len(combined),
        "path_best_evidence": combined.get("path_best_evidence", ""),
        "ocr_score": combined.get("ocr_candidate_verifier_score", ""),
        "ocr_text": combined.get("ocr_candidate_verifier_text", ""),
        "ocr_conf": combined.get("ocr_candidate_verifier_conf", ""),
    }


def classify(prompt, combined, vlm):
    gold = gold_status(prompt)
    prompt_pred = predicted_status(prompt)
    combined_pred = predicted_status(combined)
    vlm_pred = predicted_status(vlm) if vlm else ""

    labels = []
    if gold == "absent" and prompt_pred == "present":
        labels.append("prompt_absent_false_present")
    if gold == "absent" and prompt_pred == "present" and combined_pred == "absent":
        labels.append("combined_corrected_absent_false_present")
    if gold == "absent" and prompt_pred == "present" and combined_pred == "present":
        labels.append("combined_kept_absent_false_present")
    if gold == "present" and prompt_pred == "present" and combined_pred == "absent":
        labels.append("combined_new_present_false_absent")
    if vlm:
        combined_ok = correct(gold, combined_pred)
        vlm_ok = correct(gold, vlm_pred)
        if not vlm_ok and combined_ok:
            labels.append("vlm_wrong_combined_correct")
        if not combined_ok and vlm_ok:
            labels.append("combined_wrong_vlm_correct")
        if not combined_ok and not vlm_ok and gold == "absent":
            labels.append("both_wrong_absent")
        if not combined_ok and not vlm_ok and gold == "present":
            labels.append("both_wrong_present")
    return labels


def example_for(prompt, combined, vlm, row):
    example = dict(combined)
    example.update({
        "case_type": row["case_type"],
        "prompt_status_before_verifier": row["prompt_status"],
        "combined_status_after_verifier": row["combined_status"],
        "vlm_status": row["vlm_status"],
        "case_review_target": row["target"],
    })
    if "prediction" not in example and prompt.get("prediction"):
        example["prediction"] = prompt["prediction"]
    return example


def main():
    parser = argparse.ArgumentParser(description="Export review cases for native VSGUI present/absent results.")
    parser.add_argument("--prompt-predictions", required=True)
    parser.add_argument("--combined-predictions", required=True)
    parser.add_argument("--vlm-predictions", default="")
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--limit", type=int, default=30)
    args = parser.parse_args()

    prompt_data = load_json(Path(args.prompt_predictions))
    combined_data = load_json(Path(args.combined_predictions))
    vlm_data = load_json(Path(args.vlm_predictions)) if args.vlm_predictions else [None] * len(prompt_data)
    if len(prompt_data) != len(combined_data):
        raise ValueError("Prompt and combined prediction files must have the same length.")
    if len(prompt_data) != len(vlm_data):
        raise ValueError("Prompt and VLM prediction files must have the same length.")

    grouped_rows = {case_type: [] for case_type in CASE_TYPES}
    grouped_examples = {case_type: [] for case_type in CASE_TYPES}
    for idx, (prompt, combined, vlm) in enumerate(zip(prompt_data, combined_data, vlm_data)):
        for case_type in classify(prompt, combined, vlm):
            row = row_for(idx, prompt, combined, vlm, case_type)
            grouped_rows[case_type].append(row)
            grouped_examples[case_type].append(example_for(prompt, combined, vlm, row))

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = []
    combined_index = []
    for case_type in CASE_TYPES:
        rows = grouped_rows[case_type]
        examples = grouped_examples[case_type]
        selected_rows = rows[: args.limit]
        selected_examples = examples[: args.limit]
        write_csv(out_dir / f"{case_type}.csv", selected_rows)
        write_json(out_dir / f"{case_type}.json", selected_examples)
        combined_index.extend(selected_rows)
        manifest.append({
            "case_type": case_type,
            "count": len(rows),
            "selected": len(selected_rows),
            "csv": str(out_dir / f"{case_type}.csv"),
            "json": str(out_dir / f"{case_type}.json"),
        })

    write_csv(out_dir / "native_case_review_index.csv", combined_index)
    write_json(out_dir / "native_case_review_manifest.json", manifest)
    lines = [
        "# Native VSGUI Case Review",
        "",
        f"- Output directory: `{out_dir}`",
        "",
        "| Case Type | Count | Selected |",
        "|---|---:|---:|",
    ]
    for item in manifest:
        lines.append(f"| {item['case_type']} | {item['count']} | {item['selected']} |")
    lines.extend([
        "",
        "Use these cases to decide whether native VSGUI failures come from target-query mapping, true native absent difficulty, or verifier over-rejection.",
    ])
    (out_dir / "native_case_review_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"out_dir": str(out_dir), "groups": len(manifest)}, indent=2))


if __name__ == "__main__":
    main()
