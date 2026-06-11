#!/usr/bin/env python
import argparse
import csv
import json
from pathlib import Path


ABSENT_STATUSES = {"absent", "not_found", "not found", "no object", "no target", "not present"}
CASE_TYPES = [
    "forced_choice_overestimate_corrected",
    "forced_choice_overestimate_kept",
    "conservative_cost_present_rejected",
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


def safe_float(value, default=0.0):
    try:
        if value in {"", None}:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def prediction_len(example):
    return len(example.get("prediction", []) or [])


def classify(gold, prompt, adjusted):
    if gold == "absent" and prompt == "present" and adjusted == "absent":
        return "forced_choice_overestimate_corrected"
    if gold == "absent" and prompt == "present" and adjusted == "present":
        return "forced_choice_overestimate_kept"
    if gold == "present" and prompt == "present" and adjusted == "absent":
        return "conservative_cost_present_rejected"
    return ""


def row_for(idx, prompt_example, adjusted_example, case_type):
    path_evidence = adjusted_example.get("path_best_evidence", "")
    ocr_score = adjusted_example.get("ocr_candidate_verifier_score", "")
    return {
        "index": idx,
        "case_type": case_type,
        "img_usr_tgt": prompt_example.get("img_usr_tgt", idx),
        "image": prompt_example.get("image", ""),
        "target": prompt_example.get("query_text") or prompt_example.get("target") or prompt_example.get("original_target", ""),
        "gold_status": gold_status(prompt_example),
        "prompt_status": predicted_status(prompt_example),
        "adjusted_status": predicted_status(adjusted_example),
        "prompt_prediction_len": prediction_len(prompt_example),
        "adjusted_prediction_len": prediction_len(adjusted_example),
        "path_best_evidence": path_evidence,
        "ocr_score": ocr_score,
        "ocr_text": adjusted_example.get("ocr_candidate_verifier_text", ""),
        "ocr_conf": adjusted_example.get("ocr_candidate_verifier_conf", ""),
        "combined_rule": adjusted_example.get("combined_verifier_rule", ""),
        "combined_mode": adjusted_example.get("combined_verifier_mode", ""),
        "combined_cognitive_threshold": adjusted_example.get("combined_cognitive_threshold", ""),
        "combined_ocr_threshold": adjusted_example.get("combined_ocr_threshold", ""),
    }


def example_for(prompt_example, adjusted_example, row):
    example = dict(adjusted_example)
    example.update({
        "case_type": row["case_type"],
        "prompt_status_before_verifier": row["prompt_status"],
        "adjusted_status_after_verifier": row["adjusted_status"],
        "case_study_target": row["target"],
        "path_best_evidence": row["path_best_evidence"],
        "ocr_candidate_verifier_score": row["ocr_score"],
        "ocr_candidate_verifier_text": row["ocr_text"],
        "ocr_candidate_verifier_conf": row["ocr_conf"],
    })
    if "prediction" not in example and prompt_example.get("prediction"):
        example["prediction"] = prompt_example["prediction"]
    return example


def priority(row):
    path_evidence = safe_float(row.get("path_best_evidence"))
    ocr_score = safe_float(row.get("ocr_score"))
    pred_len = safe_float(row.get("prompt_prediction_len"))
    case_type = row.get("case_type")
    if case_type == "forced_choice_overestimate_corrected":
        return (path_evidence + ocr_score, pred_len)
    if case_type == "forced_choice_overestimate_kept":
        return (-(path_evidence + ocr_score), -pred_len)
    if case_type == "conservative_cost_present_rejected":
        return (-(path_evidence + ocr_score), -pred_len)
    return (0.0, 0.0)


def select_cases(prompt_data, adjusted_data, limit):
    if len(prompt_data) != len(adjusted_data):
        raise ValueError("Prompt and adjusted prediction files must have the same length.")
    grouped_rows = {case_type: [] for case_type in CASE_TYPES}
    grouped_examples = {case_type: [] for case_type in CASE_TYPES}
    counts = {case_type: 0 for case_type in CASE_TYPES}
    all_rows = []
    for idx, (prompt_example, adjusted_example) in enumerate(zip(prompt_data, adjusted_data)):
        gold = gold_status(prompt_example)
        prompt = predicted_status(prompt_example)
        adjusted = predicted_status(adjusted_example)
        case_type = classify(gold, prompt, adjusted)
        if not case_type:
            continue
        counts[case_type] += 1
        row = row_for(idx, prompt_example, adjusted_example, case_type)
        all_rows.append(row)
        grouped_rows[case_type].append(row)
        grouped_examples[case_type].append(example_for(prompt_example, adjusted_example, row))

    selected = {}
    selected_examples = {}
    for case_type in CASE_TYPES:
        paired = sorted(
            zip(grouped_rows[case_type], grouped_examples[case_type]),
            key=lambda item: priority(item[0]),
        )
        selected[case_type] = [row for row, _ in paired[:limit]]
        selected_examples[case_type] = [example for _, example in paired[:limit]]
    return counts, selected, selected_examples, all_rows


def write_summary(path, out_dir, counts, selected):
    lines = [
        "# GUI Evaluation Case Study Candidates",
        "",
        "These cases are selected to show how a forced-choice synthetic GUI user can overestimate findability, and what cost the verifier introduces.",
        "",
        f"- Output directory: `{out_dir}`",
        "",
        "| Case Type | Count | Selected | Paper Use |",
        "|---|---:|---:|---|",
    ]
    uses = {
        "forced_choice_overestimate_corrected": "Main case-study evidence: prompt-only grounds a missing target, verifier reports absence.",
        "forced_choice_overestimate_kept": "Residual failure: both prompt-only and verifier still overestimate findability.",
        "conservative_cost_present_rejected": "Cost case: verifier rejects a visible target; use for precision/recall tradeoff.",
    }
    for case_type in CASE_TYPES:
        lines.append(f"| {case_type} | {counts[case_type]} | {len(selected[case_type])} | {uses[case_type]} |")
    lines.extend([
        "",
        "Recommended main-text figure: choose one large example from each case type rather than using dense contact sheets.",
        "",
    ])
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Export GUI evaluation case-study candidates from prompt-only and verifier outputs.")
    parser.add_argument("--prompt-predictions", required=True)
    parser.add_argument("--adjusted-predictions", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--limit", type=int, default=12)
    args = parser.parse_args()

    prompt_data = load_json(Path(args.prompt_predictions))
    adjusted_data = load_json(Path(args.adjusted_predictions))
    counts, selected, selected_examples, all_rows = select_cases(prompt_data, adjusted_data, args.limit)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = []
    for case_type in CASE_TYPES:
        csv_path = out_dir / f"{case_type}.csv"
        json_path = out_dir / f"{case_type}.json"
        write_csv(csv_path, selected[case_type])
        write_json(json_path, selected_examples[case_type])
        manifest.append({
            "case_type": case_type,
            "count": counts[case_type],
            "selected": len(selected[case_type]),
            "csv": str(csv_path),
            "json": str(json_path),
        })
    write_csv(out_dir / "case_study_index.csv", all_rows)
    write_json(out_dir / "case_study_manifest.json", manifest)
    write_summary(out_dir / "case_study_summary.md", out_dir, counts, selected)
    print(json.dumps({
        "out_dir": str(out_dir),
        "case_types": len(CASE_TYPES),
        "total_indexed": len(all_rows),
        "summary": str(out_dir / "case_study_summary.md"),
    }, indent=2))


if __name__ == "__main__":
    main()
