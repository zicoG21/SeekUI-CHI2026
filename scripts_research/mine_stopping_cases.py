#!/usr/bin/env python
import argparse
import csv
import json
from pathlib import Path


ABSENT_STATUSES = {"absent", "not_found", "not found", "no object", "no target", "not present"}


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
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


def safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def load_evidence(path):
    rows = {}
    with open(path, "r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            rows[int(row["index"])] = row
    return rows


def prediction_len(example):
    return len(example.get("prediction", []) or [])


def row_for(idx, original, adjusted, evidence, case_type):
    return {
        "index": idx,
        "case_type": case_type,
        "img_usr_tgt": original.get("img_usr_tgt", idx),
        "image": original.get("image", ""),
        "target": original.get("target", ""),
        "original_target": original.get("original_target", ""),
        "gold_status": gold_status(original),
        "original_predicted_status": predicted_status(original),
        "adjusted_predicted_status": predicted_status(adjusted),
        "prediction_len": prediction_len(original),
        "path_best_evidence": evidence.get("path_best_evidence", ""),
        "path_best_candidate": evidence.get("path_best_candidate", ""),
        "path_best_similarity": evidence.get("path_best_similarity", ""),
        "path_best_distance_px": evidence.get("path_best_distance_px", ""),
        "threshold": adjusted.get("cognitive_stopping_threshold", ""),
        "combined_verifier_rule": adjusted.get("combined_verifier_rule", ""),
        "combined_cognitive_threshold": adjusted.get("combined_cognitive_threshold", ""),
        "combined_ocr_threshold": adjusted.get("combined_ocr_threshold", ""),
        "ocr_candidate_verifier_score": adjusted.get("ocr_candidate_verifier_score", ""),
        "ocr_candidate_verifier_text": adjusted.get("ocr_candidate_verifier_text", ""),
        "ocr_candidate_verifier_conf": adjusted.get("ocr_candidate_verifier_conf", ""),
    }


def add_case(case_rows, case_examples, idx, original, adjusted, evidence, case_type):
    row = row_for(idx, original, adjusted, evidence, case_type)
    example = dict(adjusted)
    example["case_type"] = case_type
    example["original_predicted_status_before_stopping"] = predicted_status(original)
    for key in [
        "path_best_evidence",
        "path_best_candidate",
        "path_best_similarity",
        "path_best_distance_px",
        "ocr_candidate_verifier_score",
        "ocr_candidate_verifier_text",
        "ocr_candidate_verifier_conf",
    ]:
        if key in row:
            example[key] = row[key]
    case_rows[case_type].append(row)
    case_examples[case_type].append(example)


def case_priority(row):
    evidence = safe_float(row.get("path_best_evidence"))
    if row["case_type"] in {"corrected_absent_false_present", "kept_absent_false_present"}:
        return evidence
    if row["case_type"] in {"new_present_false_absent", "corrected_present_false_absent"}:
        return -evidence
    return evidence


def main():
    parser = argparse.ArgumentParser(description="Mine success and failure cases for cognitive stopping.")
    parser.add_argument("--original", required=True)
    parser.add_argument("--adjusted", required=True)
    parser.add_argument("--evidence", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--limit", type=int, default=40)
    args = parser.parse_args()

    original_data = load_json(Path(args.original))
    adjusted_data = load_json(Path(args.adjusted))
    evidence = load_evidence(Path(args.evidence))
    if len(original_data) != len(adjusted_data):
        raise ValueError("Original and adjusted predictions must have the same length.")

    case_rows = {
        "corrected_absent_false_present": [],
        "new_present_false_absent": [],
        "corrected_present_false_absent": [],
        "kept_absent_false_present": [],
    }
    case_examples = {key: [] for key in case_rows}

    for idx, (original, adjusted) in enumerate(zip(original_data, adjusted_data)):
        gold = gold_status(original)
        before = predicted_status(original)
        after = predicted_status(adjusted)
        ev = evidence.get(idx, {})

        if gold == "absent" and before == "present" and after == "absent":
            add_case(case_rows, case_examples, idx, original, adjusted, ev, "corrected_absent_false_present")
        elif gold == "present" and before == "present" and after == "absent":
            add_case(case_rows, case_examples, idx, original, adjusted, ev, "new_present_false_absent")
        elif gold == "present" and before == "absent" and after == "present":
            add_case(case_rows, case_examples, idx, original, adjusted, ev, "corrected_present_false_absent")
        elif gold == "absent" and before == "present" and after == "present":
            add_case(case_rows, case_examples, idx, original, adjusted, ev, "kept_absent_false_present")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = []
    combined_rows = []
    for case_type, rows in case_rows.items():
        paired = sorted(zip(rows, case_examples[case_type]), key=lambda item: case_priority(item[0]))
        selected = paired[:args.limit]
        selected_rows = [row for row, _ in selected]
        selected_examples = [example for _, example in selected]
        write_csv(out_dir / f"{case_type}.csv", selected_rows)
        write_json(out_dir / f"{case_type}.json", selected_examples)
        combined_rows.extend(selected_rows)
        manifest.append({
            "case_type": case_type,
            "count": len(case_rows[case_type]),
            "selected": len(selected_rows),
            "csv": str(out_dir / f"{case_type}.csv"),
            "json": str(out_dir / f"{case_type}.json"),
        })

    write_csv(out_dir / "stopping_cases_index.csv", combined_rows)
    write_json(out_dir / "stopping_cases_manifest.json", manifest)

    lines = [
        "# Cognitive Stopping Case Mining",
        "",
        f"- Output directory: `{out_dir}`",
        "",
        "| Case type | Count | Selected |",
        "|---|---:|---:|",
    ]
    for item in manifest:
        lines.append(f"| {item['case_type']} | {item['count']} | {item['selected']} |")
    (out_dir / "stopping_cases_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Output directory: {out_dir}")
    print(f"Summary         : {out_dir / 'stopping_cases_summary.md'}")
    print(f"Combined CSV    : {out_dir / 'stopping_cases_index.csv'}")


if __name__ == "__main__":
    main()
