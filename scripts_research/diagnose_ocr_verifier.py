#!/usr/bin/env python
import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path


def read_csv(path):
    if not path or not Path(path).exists() or Path(path).stat().st_size == 0:
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


def bucket_score(score):
    if score >= 0.8:
        return "very_high_0.80+"
    if score >= 0.6:
        return "high_0.60_0.80"
    if score >= 0.4:
        return "medium_0.40_0.60"
    if score > 0:
        return "low_0_0.40"
    return "zero"


def model_from_path(path):
    name = Path(path).name
    if "SeekUI_sft" in name:
        return "SeekUI_sft"
    if "SeekUI" in name:
        return "SeekUI"
    return Path(path).stem


def diagnose_ocr_rows(model, rows, threshold):
    summary = Counter()
    score_buckets = Counter()
    examples = defaultdict(list)
    for row in rows:
        gold = row.get("gold_status", "")
        original = row.get("original_status", "")
        verified = row.get("verified_status", "")
        score = safe_float(row.get("score"))
        text = str(row.get("best_ocr_text", "") or "")
        n_candidates = safe_int(row.get("num_ocr_candidates"))
        score_buckets[(gold, bucket_score(score))] += 1

        if gold == "present" and verified == "absent":
            key = "present_rejected_by_ocr"
            if n_candidates == 0:
                key = "present_rejected_no_ocr_candidates"
            elif not text:
                key = "present_rejected_no_best_text"
            elif score < threshold:
                key = "present_rejected_low_match"
            summary[key] += 1
            if len(examples[key]) < 20:
                examples[key].append(row)
        elif gold == "absent" and verified == "present":
            key = "absent_kept_by_ocr"
            if score >= threshold:
                key = "absent_kept_high_ocr_match"
            summary[key] += 1
            if len(examples[key]) < 20:
                examples[key].append(row)
        elif gold == "absent" and verified == "absent":
            summary["absent_rejected_by_ocr"] += 1
        elif gold == "present" and verified == "present":
            summary["present_kept_by_ocr"] += 1

        if original == "present" and verified == "absent":
            summary["changed_present_to_absent"] += 1

    total = len(rows)
    summary_rows = [
        {"model": model, "category": key, "count": count, "rate": safe_div(count, total)}
        for key, count in sorted(summary.items())
    ]
    bucket_rows = [
        {"model": model, "gold_status": gold, "score_bucket": bucket, "count": count}
        for (gold, bucket), count in sorted(score_buckets.items())
    ]
    return summary_rows, bucket_rows, examples


def summarize_ocr_leaks(path):
    rows = read_csv(path)
    leaks = [row for row in rows if str(row.get("ocr_leak_flag", "")).strip() in {"1", "true", "True"}]
    by_bucket = Counter(bucket_score(safe_float(row.get("best_ocr_score"))) for row in leaks)
    return {
        "num_absent_rows": len(rows),
        "num_ocr_leaks": len(leaks),
        "ocr_leak_rate": safe_div(len(leaks), len(rows)),
        "leak_score_buckets": dict(by_bucket),
        "top_leaks": sorted(leaks, key=lambda r: -safe_float(r.get("best_ocr_score")))[:30],
    }


def compare_combined_guard(model, ocr_rows, combined_rows):
    ocr_by_index = {safe_int(row.get("index")): row for row in ocr_rows}
    guard = Counter()
    examples = defaultdict(list)
    for row in combined_rows:
        idx = safe_int(row.get("index"))
        ocr = ocr_by_index.get(idx)
        if not ocr:
            continue
        gold = row.get("gold_status", "")
        ocr_verified = ocr.get("verified_status", "")
        combined_verified = row.get("verified_status", "")
        if gold == "present" and ocr_verified == "absent" and combined_verified == "present":
            key = "combined_guard_saved_present_from_ocr_rejection"
            guard[key] += 1
            if len(examples[key]) < 20:
                examples[key].append({**row, "ocr_only_score": ocr.get("score", ""), "ocr_only_text": ocr.get("best_ocr_text", "")})
        elif gold == "absent" and ocr_verified == "present" and combined_verified == "absent":
            key = "combined_cognitive_rejected_absent_despite_ocr_match"
            guard[key] += 1
            if len(examples[key]) < 20:
                examples[key].append({**row, "ocr_only_score": ocr.get("score", ""), "ocr_only_text": ocr.get("best_ocr_text", "")})
    total = len(combined_rows)
    rows = [
        {"model": model, "category": key, "count": count, "rate": safe_div(count, total)}
        for key, count in sorted(guard.items())
    ]
    return rows, examples


def write_md(path, report):
    lines = [
        "# OCR Verifier Diagnosis",
        "",
        "OCR is treated as a non-oracle guard signal. These diagnostics describe where it rejects present targets, where it preserves absent false-present errors, and how the combined AND rule changes that behavior.",
        "",
    ]
    if report.get("ocr_leaks"):
        leaks = report["ocr_leaks"]
        lines.extend([
            "## Synthetic Absent OCR Leaks",
            "",
            f"- Absent rows audited: {leaks['num_absent_rows']}",
            f"- OCR leak rows: {leaks['num_ocr_leaks']} ({leaks['ocr_leak_rate']:.4f})",
            "",
            "| Score Bucket | Count |",
            "|---|---:|",
        ])
        for bucket, count in sorted(leaks["leak_score_buckets"].items()):
            lines.append(f"| {bucket} | {count} |")
        lines.append("")

    for model, model_report in report["models"].items():
        lines.extend([
            f"## {model}",
            "",
            "OCR-only categories:",
            "",
            "| Category | Count | Rate |",
            "|---|---:|---:|",
        ])
        for row in model_report["ocr_summary"]:
            lines.append(f"| {row['category']} | {row['count']} | {row['rate']:.4f} |")
        lines.extend(["", "OCR score buckets by gold status:", "", "| Gold Status | Score Bucket | Count |", "|---|---|---:|"])
        for row in model_report["score_buckets"]:
            lines.append(f"| {row['gold_status']} | {row['score_bucket']} | {row['count']} |")
        if model_report["combined_guard"]:
            lines.extend(["", "Combined AND guard effects:", "", "| Category | Count | Rate |", "|---|---:|---:|"])
            for row in model_report["combined_guard"]:
                lines.append(f"| {row['category']} | {row['count']} | {row['rate']:.4f} |")
        lines.append("")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Diagnose OCR verifier behavior and combined-AND guard effects.")
    parser.add_argument("--ocr-detail", action="append", required=True, help="OCR detail CSV. Can repeat.")
    parser.add_argument("--combined-detail", action="append", default=[], help="Combined verifier detail CSV. Can repeat.")
    parser.add_argument("--absent-ocr-leaks", default="")
    parser.add_argument("--threshold", type=float, default=0.4)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    combined_by_model = {model_from_path(path): read_csv(path) for path in args.combined_detail}
    report = {"threshold": args.threshold, "models": {}}
    all_summary = []
    all_buckets = []
    all_guard = []

    for path in args.ocr_detail:
        model = model_from_path(path)
        rows = read_csv(path)
        summary_rows, bucket_rows, examples = diagnose_ocr_rows(model, rows, args.threshold)
        guard_rows, guard_examples = compare_combined_guard(model, rows, combined_by_model.get(model, []))
        report["models"][model] = {
            "ocr_detail": path,
            "num_rows": len(rows),
            "ocr_summary": summary_rows,
            "score_buckets": bucket_rows,
            "combined_guard": guard_rows,
            "example_previews": {key: value for key, value in examples.items()},
            "combined_guard_previews": {key: value for key, value in guard_examples.items()},
        }
        all_summary.extend(summary_rows)
        all_buckets.extend(bucket_rows)
        all_guard.extend(guard_rows)

    if args.absent_ocr_leaks:
        report["ocr_leaks"] = summarize_ocr_leaks(Path(args.absent_ocr_leaks))

    write_json(out_dir / "ocr_verifier_diagnosis.json", report)
    write_csv(out_dir / "ocr_verifier_diagnosis_summary.csv", all_summary)
    write_csv(out_dir / "ocr_verifier_score_buckets.csv", all_buckets)
    write_csv(out_dir / "combined_guard_effects.csv", all_guard)
    write_md(out_dir / "ocr_verifier_diagnosis.md", report)
    print(json.dumps({
        "models": sorted(report["models"]),
        "summary_md": str(out_dir / "ocr_verifier_diagnosis.md"),
        "summary_csv": str(out_dir / "ocr_verifier_diagnosis_summary.csv"),
    }, indent=2))


if __name__ == "__main__":
    main()
