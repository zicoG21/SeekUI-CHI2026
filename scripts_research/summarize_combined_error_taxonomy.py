#!/usr/bin/env python
import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path


def read_csv(path):
    if not path.exists() or path.stat().st_size == 0:
        return []
    with open(path, "r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path, rows, fieldnames=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = list(rows[0].keys()) if rows else []
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def safe_float(value, default=0.0):
    try:
        if value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(value, default=0):
    try:
        if value == "":
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def safe_div(num, den):
    return num / den if den else 0.0


def parse_model(case_dir):
    name = case_dir.name
    if name.startswith("SeekUI_sft"):
        return "SeekUI_sft"
    if name.startswith("SeekUI"):
        return "SeekUI"
    return name.split("_", 1)[0]


def tag_row(row):
    case_type = row.get("case_type", "")
    pred_len = safe_int(row.get("prediction_len"))
    evidence = safe_float(row.get("path_best_evidence"))
    similarity = safe_float(row.get("path_best_similarity"))
    distance = safe_float(row.get("path_best_distance_px"), default=-1.0)
    ocr_score = safe_float(row.get("ocr_candidate_verifier_score"))
    ocr_text = str(row.get("ocr_candidate_verifier_text", "") or "").strip()
    ocr_conf = safe_float(row.get("ocr_candidate_verifier_conf"))
    cog_threshold = safe_float(row.get("combined_cognitive_threshold"), default=0.0)
    ocr_threshold = safe_float(row.get("combined_ocr_threshold"), default=0.0)

    tags = []
    if pred_len <= 2:
        tags.append("short_scanpath")
    elif pred_len >= 6:
        tags.append("long_scanpath")

    if evidence < cog_threshold:
        tags.append("low_path_evidence")
    else:
        tags.append("path_evidence_present")

    if ocr_score < ocr_threshold:
        tags.append("low_ocr_match")
    else:
        tags.append("ocr_match_present")

    if ocr_text:
        tags.append("has_ocr_match_text")
    else:
        tags.append("no_ocr_match_text")

    if similarity >= 0.8:
        tags.append("high_text_similarity_candidate")
    elif similarity <= 0.25:
        tags.append("low_text_similarity_candidate")

    if distance >= 0:
        if distance <= 120:
            tags.append("near_candidate")
        elif distance >= 400:
            tags.append("far_candidate")

    if ocr_conf and ocr_conf < 50:
        tags.append("low_ocr_confidence")

    if case_type == "corrected_absent_false_present":
        if "low_path_evidence" in tags and "low_ocr_match" in tags:
            tags.append("two_signal_rejection")
        elif "low_path_evidence" in tags:
            tags.append("cognitive_driven_correction")
        elif "low_ocr_match" in tags:
            tags.append("ocr_driven_correction")
    elif case_type == "new_present_false_absent":
        if "low_path_evidence" in tags and "low_ocr_match" in tags:
            tags.append("over_rejected_by_both_signals")
        if "no_ocr_match_text" in tags or "low_ocr_match" in tags:
            tags.append("possible_ocr_miss")
        if "short_scanpath" in tags:
            tags.append("possible_under_search")
    elif case_type == "kept_absent_false_present":
        if "path_evidence_present" in tags and "ocr_match_present" in tags:
            tags.append("two_signal_distractor")
        elif "path_evidence_present" in tags:
            tags.append("path_distractor")
        elif "ocr_match_present" in tags:
            tags.append("ocr_text_distractor")

    return tags


def summarize(rows):
    by_case = defaultdict(list)
    tag_counts = Counter()
    case_tag_counts = Counter()
    for row in rows:
        case_type = row.get("case_type", "")
        by_case[case_type].append(row)
        tags = row.get("taxonomy_tags", "").split(";") if row.get("taxonomy_tags") else []
        for tag in tags:
            tag_counts[tag] += 1
            case_tag_counts[(case_type, tag)] += 1

    case_rows = []
    for case_type, case_rows_raw in sorted(by_case.items()):
        case_rows.append({
            "case_type": case_type,
            "count": len(case_rows_raw),
            "mean_prediction_len": sum(safe_float(r.get("prediction_len")) for r in case_rows_raw) / len(case_rows_raw),
            "mean_path_best_evidence": sum(safe_float(r.get("path_best_evidence")) for r in case_rows_raw) / len(case_rows_raw),
            "mean_ocr_score": sum(safe_float(r.get("ocr_candidate_verifier_score")) for r in case_rows_raw) / len(case_rows_raw),
        })

    tag_rows = [
        {"tag": tag, "count": count, "rate": safe_div(count, len(rows))}
        for tag, count in tag_counts.most_common()
    ]
    case_tag_rows = [
        {
            "case_type": case_type,
            "tag": tag,
            "count": count,
            "rate_within_case": safe_div(count, len(by_case[case_type])),
        }
        for (case_type, tag), count in sorted(case_tag_counts.items())
    ]
    return case_rows, tag_rows, case_tag_rows


def write_md(path, model_summaries):
    lines = ["# Combined Verifier Error Taxonomy", ""]
    lines.append("Heuristic tags are computed from case-mining metadata, path evidence, OCR score, and prediction length.")
    lines.append("")
    for model, summary in model_summaries.items():
        lines.extend([
            f"## {model}",
            "",
            "| Case Type | Count | Mean Pred Len | Mean Path Evidence | Mean OCR Score |",
            "|---|---:|---:|---:|---:|",
        ])
        for row in summary["case_rows"]:
            lines.append(
                f"| {row['case_type']} | {row['count']} | {row['mean_prediction_len']:.2f} | "
                f"{row['mean_path_best_evidence']:.4f} | {row['mean_ocr_score']:.4f} |"
            )
        lines.extend(["", "Top tags:", "", "| Tag | Count | Rate |", "|---|---:|---:|"])
        for row in summary["tag_rows"][:15]:
            lines.append(f"| {row['tag']} | {row['count']} | {row['rate']:.4f} |")
        lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Summarize heuristic taxonomy for combined verifier case-mining outputs.")
    parser.add_argument("--case-dir", action="append", required=True, help="Directory containing stopping_cases_index.csv.")
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    all_tagged = []
    model_summaries = {}
    for raw_case_dir in args.case_dir:
        case_dir = Path(raw_case_dir)
        model = parse_model(case_dir)
        rows = read_csv(case_dir / "stopping_cases_index.csv")
        tagged = []
        for row in rows:
            row = dict(row)
            row["model"] = model
            row["source_case_dir"] = str(case_dir)
            row["taxonomy_tags"] = ";".join(tag_row(row))
            tagged.append(row)
        if not tagged:
            continue
        fieldnames = list(tagged[0].keys())
        write_csv(out_dir / f"{model}_combined_error_taxonomy_rows.csv", tagged, fieldnames)
        case_rows, tag_rows, case_tag_rows = summarize(tagged)
        write_csv(out_dir / f"{model}_combined_error_taxonomy_cases.csv", case_rows)
        write_csv(out_dir / f"{model}_combined_error_taxonomy_tags.csv", tag_rows)
        write_csv(out_dir / f"{model}_combined_error_taxonomy_case_tags.csv", case_tag_rows)
        model_summaries[model] = {
            "case_dir": str(case_dir),
            "num_rows": len(tagged),
            "case_rows": case_rows,
            "tag_rows": tag_rows,
            "case_tag_rows": case_tag_rows,
        }
        all_tagged.extend(tagged)

    if all_tagged:
        write_csv(out_dir / "combined_error_taxonomy_rows.csv", all_tagged, list(all_tagged[0].keys()))
    write_json(out_dir / "combined_error_taxonomy_summary.json", model_summaries)
    write_md(out_dir / "combined_error_taxonomy_summary.md", model_summaries)
    print(json.dumps({
        "models": sorted(model_summaries),
        "summary_md": str(out_dir / "combined_error_taxonomy_summary.md"),
        "rows_csv": str(out_dir / "combined_error_taxonomy_rows.csv"),
    }, indent=2))


if __name__ == "__main__":
    main()
