#!/usr/bin/env python
import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path


def read_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def read_csv(path):
    if not path.exists() or path.stat().st_size == 0:
        return []
    with open(path, "r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def write_csv(path, rows, fieldnames=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = sorted({key for row in rows for key in row}) if rows else []
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def to_float(value):
    try:
        if value == "" or value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def mean(values):
    nums = [value for value in values if value is not None]
    return sum(nums) / len(nums) if nums else ""


def collect_rows(manifest_path):
    manifest = read_json(manifest_path)
    rows = []
    for item in manifest:
        csv_path = Path(item.get("csv", ""))
        if csv_path.exists():
            rows.extend(read_csv(csv_path))
    return manifest, rows


def summarize_group(rows):
    by_group = defaultdict(list)
    for row in rows:
        key = (row.get("case_source", ""), row.get("case_type", ""))
        by_group[key].append(row)

    summary_rows = []
    for (case_source, case_type), group_rows in sorted(by_group.items()):
        gold_counts = Counter(row.get("gold_status", "") for row in group_rows)
        combined_counts = Counter(row.get("combined_status", "") for row in group_rows)
        vlm_counts = Counter(row.get("vlm_status", "") for row in group_rows)
        summary_rows.append({
            "case_source": case_source,
            "case_type": case_type,
            "count": len(group_rows),
            "gold_counts": dict(gold_counts),
            "combined_counts": dict(combined_counts),
            "vlm_counts": dict(vlm_counts),
            "mean_path_best_evidence": mean(to_float(row.get("path_best_evidence")) for row in group_rows),
            "mean_ocr_score": mean(to_float(row.get("ocr_candidate_verifier_score")) for row in group_rows),
            "top_ocr_texts": dict(Counter(
                row.get("ocr_candidate_verifier_text", "")
                for row in group_rows
                if row.get("ocr_candidate_verifier_text", "")
            ).most_common(8)),
        })
    return summary_rows


def write_markdown(path, title, summary_rows):
    lines = [f"# {title}", ""]
    if not summary_rows:
        lines.append("No rows found.")
    else:
        lines.extend([
            "| Case Source | Case Type | Count | Mean Path Evidence | Mean OCR Score |",
            "|---|---|---:|---:|---:|",
        ])
        for row in summary_rows:
            path_ev = row["mean_path_best_evidence"]
            ocr = row["mean_ocr_score"]
            lines.append(
                f"| {row['case_source']} | {row['case_type']} | {row['count']} | "
                f"{path_ev:.4f} | {ocr:.4f} |"
                if path_ev != "" and ocr != ""
                else f"| {row['case_source']} | {row['case_type']} | {row['count']} | {path_ev} | {ocr} |"
            )
        lines.extend(["", "## Interpretation Prompts", ""])
        lines.extend([
            "- `vlm_wrong_combined_correct__absent_case`: VLM was fooled into present; combined preserved not-found safety.",
            "- `combined_wrong_vlm_correct__present_case`: combined over-rejected a present target; VLM preserved the visible target.",
            "- `both_wrong__absent_case`: both methods were fooled by hard distractors.",
            "- `both_wrong__present_case`: both methods missed a difficult visible target.",
        ])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Summarize VLM-vs-combined hard-case exports.")
    parser.add_argument("--manifest", action="append", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--output-md", required=True)
    args = parser.parse_args()

    all_results = {}
    combined_rows = []
    for manifest in args.manifest:
        manifest_path = Path(manifest)
        _, rows = collect_rows(manifest_path)
        summary_rows = summarize_group(rows)
        label = manifest_path.parent.name
        all_results[label] = {
            "manifest": str(manifest_path),
            "num_rows": len(rows),
            "summary": summary_rows,
        }
        for row in summary_rows:
            combined_rows.append({"label": label, **row})

    write_json(Path(args.output_json), all_results)
    write_csv(Path(args.output_csv), combined_rows)
    write_markdown(Path(args.output_md), "VLM Hard-Case Summary", combined_rows)
    print(json.dumps({
        "manifests": len(args.manifest),
        "summary_rows": len(combined_rows),
        "output_md": args.output_md,
    }, indent=2))


if __name__ == "__main__":
    main()
