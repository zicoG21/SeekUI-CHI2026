#!/usr/bin/env python
import argparse
import csv
import json
import sys
import tarfile
import tempfile
import textwrap
from collections import Counter
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts_research.apply_combined_verifier import (
    apply_thresholds,
    evaluate,
    load_evidence,
    load_ocr_candidates,
    score_records,
)


GROUPS = [
    ("prompt_wrong_combined_correct", "Prompt wrong, combined correct"),
    ("prompt_correct_combined_wrong", "Prompt correct, combined wrong"),
    ("both_wrong", "Both wrong"),
    ("both_correct", "Both correct"),
    ("absent_false_present_corrected", "Absent false-present corrected by combined"),
    ("new_present_false_absent", "New present false-absent from combined"),
    ("kept_absent_false_present", "Absent false-present kept by combined"),
]


def read_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def read_csv(path):
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


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


def safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def is_correct(gold, pred):
    return gold == pred


def normalize_image_name(path):
    return Path(str(path)).name


def load_review_rows(review_csv):
    rows = {}
    for row in read_csv(review_csv):
        rid = str(row.get("review_id", ""))
        if rid:
            rows[rid] = row
    return rows


def resolve_real_absent_dir(path):
    path = Path(path)
    if path.is_dir():
        return path, None
    if path.suffixes[-2:] == [".tar", ".gz"] or path.suffix == ".tgz":
        tmp = tempfile.TemporaryDirectory()
        with tarfile.open(path, "r:gz") as tar:
            try:
                tar.extractall(tmp.name, filter="data")
            except TypeError:
                tar.extractall(tmp.name)
        extracted = Path(tmp.name) / "real_absent_validation"
        return extracted, tmp
    raise ValueError(f"Expected directory or .tgz archive: {path}")


def attach_prompt_status(examples, evidence):
    for idx, example in enumerate(examples):
        row = evidence.get(idx, {})
        example["predicted_status"] = row.get("predicted_status", "present")
        example["prompt_error_type"] = row.get("error_type", "")
    return examples


def build_methods(real_absent_dir):
    examples = read_json(real_absent_dir / "real_absent_validation_eval.json")
    evidence = load_evidence(real_absent_dir / "stopping_evidence" / "SeekUI_real_absent_stopping_evidence.csv")
    attach_prompt_status(examples, evidence)
    prompt_metrics = evaluate(examples)

    ocr_by_image = load_ocr_candidates(real_absent_dir / "ocr_candidates_tesseract.json")
    records, missing_evidence, missing_ocr_images = score_records(examples, {}, evidence, ocr_by_image, min_ocr_conf=35.0)
    combined_default, default_metrics, default_details = apply_thresholds(
        records,
        cog_threshold=0.05,
        ocr_threshold=0.40,
        rule="and",
        mode="present_only",
    )
    combined_best, best_metrics, best_details = apply_thresholds(
        records,
        cog_threshold=0.20,
        ocr_threshold=0.60,
        rule="and",
        mode="present_only",
    )
    return {
        "examples": examples,
        "prompt_metrics": prompt_metrics,
        "combined_default": combined_default,
        "combined_default_metrics": default_metrics,
        "combined_default_details": default_details,
        "combined_best": combined_best,
        "combined_best_metrics": best_metrics,
        "combined_best_details": best_details,
        "missing_evidence": missing_evidence,
        "missing_ocr_images": missing_ocr_images,
    }


def classify_case(gold, prompt, combined):
    tags = []
    prompt_ok = is_correct(gold, prompt)
    combined_ok = is_correct(gold, combined)
    if not prompt_ok and combined_ok:
        tags.append("prompt_wrong_combined_correct")
    if prompt_ok and not combined_ok:
        tags.append("prompt_correct_combined_wrong")
    if not prompt_ok and not combined_ok:
        tags.append("both_wrong")
    if prompt_ok and combined_ok:
        tags.append("both_correct")
    if gold == "absent" and prompt == "present" and combined == "absent":
        tags.append("absent_false_present_corrected")
    if gold == "present" and prompt == "present" and combined == "absent":
        tags.append("new_present_false_absent")
    if gold == "absent" and prompt == "present" and combined == "present":
        tags.append("kept_absent_false_present")
    return tags


def build_case_rows(methods, review_rows):
    examples = methods["examples"]
    combined = methods["combined_best"]
    details = {int(row["index"]): row for row in methods["combined_best_details"]}
    rows = []
    grouped = {name: [] for name, _ in GROUPS}
    for idx, (example, combined_example) in enumerate(zip(examples, combined)):
        gold = "present" if example.get("target_present") else "absent"
        prompt = example.get("predicted_status", "present")
        combined_status = combined_example.get("predicted_status", "present")
        detail = details.get(idx, {})
        review_id = str(example.get("manual_review_id", ""))
        review = review_rows.get(review_id, {})
        tags = classify_case(gold, prompt, combined_status)
        row = {
            "index": idx,
            "review_id": review_id,
            "image": example.get("image", ""),
            "image_basename": normalize_image_name(example.get("image", "")),
            "target": example.get("query_text") or example.get("target", ""),
            "gold_status": gold,
            "prompt_status": prompt,
            "combined_status": combined_status,
            "prompt_correct": int(gold == prompt),
            "combined_correct": int(gold == combined_status),
            "case_tags": ";".join(tags),
            "path_best_evidence": detail.get("cog_score", ""),
            "ocr_score": detail.get("ocr_score", ""),
            "ocr_text": detail.get("ocr_text", ""),
            "ocr_conf": detail.get("ocr_conf", ""),
            "ambiguity_level": example.get("manual_ambiguity_level", ""),
            "manual_notes": example.get("manual_notes", "") or review.get("notes", ""),
        }
        rows.append(row)
        for tag in tags:
            grouped[tag].append(row)
    return rows, grouped


def fmt_metric(value):
    return f"{float(value):.4f}"


def metrics_rows(methods):
    rows = []
    for label, variant, metrics in [
        ("SeekUI", "prompt_only_real_absent", methods["prompt_metrics"]),
        ("SeekUI", "combined_and_present_only", methods["combined_default_metrics"]),
        ("SeekUI", "combined_and_present_only_best_f1", methods["combined_best_metrics"]),
    ]:
        confusion = metrics["confusion"]
        rows.append({
            "model": label,
            "variant": variant,
            "n": metrics["num_examples"],
            "accuracy": metrics["accuracy"],
            "absent_precision": metrics["absent_precision"],
            "absent_recall": metrics["absent_recall"],
            "absent_f1": metrics["absent_f1"],
            "present_to_absent": confusion["present->absent"],
            "absent_to_present": confusion["absent->present"],
        })
    return rows


def write_summary_md(path, methods, grouped, aggregate_results_path):
    metric_rows = metrics_rows(methods)
    lines = [
        "# Real Absent Case Analysis",
        "",
        "This analysis reconstructs prompt-only and combined-AND decisions from the real-absent eval set, stopping evidence, and OCR candidates.",
        "",
        "## Method Metrics",
        "",
        "| Method | N | Acc | Precision | Recall | F1 | Present->Absent | Absent->Present |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in metric_rows:
        lines.append(
            f"| {row['variant']} | {row['n']} | {fmt_metric(row['accuracy'])} | "
            f"{fmt_metric(row['absent_precision'])} | {fmt_metric(row['absent_recall'])} | "
            f"{fmt_metric(row['absent_f1'])} | {row['present_to_absent']} | {row['absent_to_present']} |"
        )
    lines.extend([
        "",
        "## Case Groups",
        "",
        "| Group | Count | Interpretation |",
        "|---|---:|---|",
    ])
    interpretations = {
        "prompt_wrong_combined_correct": "Combined fixes prompt-only mistakes; mostly absent safety gains.",
        "prompt_correct_combined_wrong": "Cost of the verifier; visible targets may be over-rejected.",
        "both_wrong": "Hard residual cases where both methods miss the label.",
        "both_correct": "Stable cases where verifier preserves the correct decision.",
        "absent_false_present_corrected": "Target-absent queries that prompt-only hallucinated but combined rejected.",
        "new_present_false_absent": "Present targets newly rejected by combined.",
        "kept_absent_false_present": "Residual target-absent hallucinations after combined.",
    }
    for key, label in GROUPS:
        lines.append(f"| {label} | {len(grouped.get(key, []))} | {interpretations[key]} |")
    lines.extend([
        "",
        "## Key Takeaways",
        "",
        f"- Combined best-F1 reduces absent->present errors from {methods['prompt_metrics']['confusion']['absent->present']} to {methods['combined_best_metrics']['confusion']['absent->present']} on the 100-row realistic validation set.",
        f"- The main tradeoff is present->absent errors, increasing from {methods['prompt_metrics']['confusion']['present->absent']} to {methods['combined_best_metrics']['confusion']['present->absent']}.",
        "- Per-example VLM predictions are not included in the local archive, so this file reports VLM only through aggregate tables elsewhere.",
        "",
        f"Aggregate real-absent VLM results source: `{aggregate_results_path}`",
        "",
    ])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def load_font(size):
    for candidate in [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default()


def find_review_image(review_image_dir, row):
    review_id = str(row.get("review_id", ""))
    basename = Path(row.get("image", "")).stem
    candidates = list(Path(review_image_dir).glob(f"{int(review_id):03d}_{basename}.png")) if review_id.isdigit() else []
    if candidates:
        return candidates[0]
    candidates = list(Path(review_image_dir).glob(f"*_{basename}.png"))
    return candidates[0] if candidates else None


def make_contact_sheet(rows, title, review_image_dir, out_path, limit=24):
    image_rows = [row for row in rows if row.get("gold_status") == "absent"]
    image_rows = image_rows[:limit]
    if not image_rows:
        return False
    thumb_w, thumb_h = 390, 260
    header_h = 90
    label_h = 108
    cols = 3
    rows_n = (len(image_rows) + cols - 1) // cols
    canvas = Image.new("RGB", (cols * thumb_w, header_h + rows_n * (thumb_h + label_h)), "white")
    draw = ImageDraw.Draw(canvas)
    draw.text((18, 18), title, fill="#111111", font=load_font(30))
    draw.text((18, 56), "Realistic absent validation cases", fill="#333333", font=load_font(20))
    small = load_font(15)
    tiny = load_font(13)
    for i, row in enumerate(image_rows):
        x = (i % cols) * thumb_w
        y = header_h + (i // cols) * (thumb_h + label_h)
        img_path = find_review_image(review_image_dir, row)
        if img_path and img_path.exists():
            img = Image.open(img_path).convert("RGB")
            img.thumbnail((thumb_w - 12, thumb_h), Image.Resampling.LANCZOS)
            canvas.paste(img, (x + (thumb_w - img.width) // 2, y))
        else:
            draw.rectangle((x + 8, y + 8, x + thumb_w - 8, y + thumb_h - 8), outline="#888888")
            draw.text((x + 20, y + 40), "image missing", fill="#333333", font=small)
        label = (
            f"#{row['review_id']} {row['target']} | "
            f"p:{row['prompt_status']} c:{row['combined_status']}"
        )
        draw.text((x + 8, y + thumb_h + 8), label[:52], fill="#111111", font=small)
        note = str(row.get("manual_notes", ""))
        wrapped = "\n".join(textwrap.wrap(note, width=46)[:3])
        draw.multiline_text((x + 8, y + thumb_h + 34), wrapped, fill="#444444", font=tiny, spacing=2)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path, quality=92)
    return True


def export_outputs(out_dir, methods, case_rows, grouped, review_image_dir, aggregate_results_path):
    write_csv(out_dir / "real_absent_case_index.csv", case_rows)
    write_json(out_dir / "real_absent_case_index.json", case_rows)
    write_summary_md(out_dir / "real_absent_case_analysis.md", methods, grouped, aggregate_results_path)
    write_csv(out_dir / "real_absent_reconstructed_method_metrics.csv", metrics_rows(methods))

    group_rows = []
    for key, label in GROUPS:
        rows = grouped.get(key, [])
        write_csv(out_dir / "groups" / f"{key}.csv", rows)
        write_json(out_dir / "groups" / f"{key}.json", rows)
        group_rows.append({"group": key, "label": label, "count": len(rows)})
        make_contact_sheet(
            rows,
            label,
            review_image_dir,
            out_dir / "figures" / f"{key}_contact_sheet.jpg",
        )
    write_csv(out_dir / "real_absent_case_group_counts.csv", group_rows)
    manifest = [
        "# Real Absent Case Analysis Manifest",
        "",
        "- `real_absent_case_analysis.md`: metric and case-group summary.",
        "- `real_absent_case_index.csv`: all 100 examples with prompt/combined status and evidence fields.",
        "- `real_absent_reconstructed_method_metrics.csv`: reconstructed prompt/default-combined/best-combined metrics.",
        "- `real_absent_case_group_counts.csv`: compact group counts.",
        "- `groups/*.csv`: per-group case tables.",
        "- `figures/*_contact_sheet.jpg`: image sheets for absent-case groups with available local images.",
        "",
        "Note: local archive includes aggregate VLM metrics but not per-example VLM predictions, so VLM case overlap is not reconstructed here.",
        "",
    ]
    (out_dir / "manifest.md").write_text("\n".join(manifest), encoding="utf-8")
    return group_rows


def write_audit_appendix(appendix_dir, case_rows):
    appendix_dir.mkdir(parents=True, exist_ok=True)
    columns = [
        "index",
        "review_id",
        "image",
        "target",
        "gold_status",
        "prompt_status",
        "combined_status",
        "case_tags",
        "path_best_evidence",
        "ocr_score",
        "ocr_text",
        "ambiguity_level",
        "manual_notes",
    ]
    rows = [{key: row.get(key, "") for key in columns} for row in case_rows]
    csv_path = appendix_dir / "real_absent_100row_audit_appendix.csv"
    md_path = appendix_dir / "real_absent_100row_audit_appendix.md"
    write_csv(csv_path, rows)
    lines = [
        "# Real Absent 100-Row Audit Appendix",
        "",
        "Each row records the manually reviewed query, gold target-presence label, prompt-only status, combined best-F1 status, and evidence fields.",
        "",
        "| Index | Review ID | Image | Query | Gold | Prompt | Combined | Tags | Path Evidence | OCR Score | OCR Text | Ambiguity | Notes |",
        "|---:|---:|---|---|---|---|---|---|---:|---:|---|---|---|",
    ]
    for row in rows:
        note = str(row["manual_notes"]).replace("|", "/")
        ocr_text = str(row["ocr_text"]).replace("|", "/")
        lines.append(
            f"| {row['index']} | {row['review_id']} | {row['image']} | {row['target']} | "
            f"{row['gold_status']} | {row['prompt_status']} | {row['combined_status']} | "
            f"{row['case_tags']} | {safe_float(row['path_best_evidence']):.4f} | "
            f"{safe_float(row['ocr_score']):.4f} | {ocr_text} | {row['ambiguity_level']} | {note} |"
        )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return [csv_path, md_path]


def main():
    parser = argparse.ArgumentParser(description="Export real-absent prompt-vs-combined case analysis.")
    parser.add_argument("--real-absent-source", required=True, help="Directory or .tgz containing real_absent_validation outputs.")
    parser.add_argument("--review-csv", default="research_notes/real_absent_validation/real_absent_rows_to_fill_filled_by_codex.csv")
    parser.add_argument("--review-image-dir", default="/home/perzival/HCI_Research/seekui_real_absent_review/review_package/images")
    parser.add_argument("--aggregate-results", default="paper_assets/tables/realistic_absent_validation.md")
    parser.add_argument("--out-dir", default="paper_assets/real_absent_case_analysis")
    parser.add_argument("--appendix-dir", default="paper_assets/appendix")
    args = parser.parse_args()

    real_absent_dir, tmp = resolve_real_absent_dir(args.real_absent_source)
    try:
        methods = build_methods(real_absent_dir)
        review_rows = load_review_rows(Path(args.review_csv))
        case_rows, grouped = build_case_rows(methods, review_rows)
        group_rows = export_outputs(
            Path(args.out_dir),
            methods,
            case_rows,
            grouped,
            Path(args.review_image_dir),
            args.aggregate_results,
        )
        appendix_paths = write_audit_appendix(Path(args.appendix_dir), case_rows)
        print(json.dumps({
            "out_dir": args.out_dir,
            "appendix": [str(path) for path in appendix_paths],
            "num_cases": len(case_rows),
            "groups": group_rows,
            "missing_evidence": methods["missing_evidence"],
            "missing_ocr_images": methods["missing_ocr_images"],
        }, indent=2))
    finally:
        if tmp is not None:
            tmp.cleanup()


if __name__ == "__main__":
    main()
