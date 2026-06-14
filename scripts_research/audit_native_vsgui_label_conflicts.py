#!/usr/bin/env python
import argparse
import csv
import difflib
import json
from collections import Counter
from pathlib import Path


ABSENT_STATUSES = {"absent", "not_found", "not found", "no object", "no target", "not present"}
COLOR_WORDS = {
    "red", "blue", "green", "yellow", "black", "white", "gray", "grey", "orange", "purple",
    "pink", "brown", "cyan", "magenta", "teal", "violet", "gold", "silver",
}


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


def normalize(text):
    return " ".join(str(text or "").casefold().replace("_", " ").replace("-", " ").split())


def strip_color_prefix(text):
    parts = normalize(text).split()
    if parts and parts[0] in COLOR_WORDS:
        return " ".join(parts[1:])
    return " ".join(parts)


def similarity(a, b):
    a = normalize(a)
    b = normalize(b)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    if min(len(a), len(b)) >= 4 and (a in b or b in a):
        return min(len(a), len(b)) / max(len(a), len(b))
    return difflib.SequenceMatcher(None, a, b).ratio()


def gold_status(example):
    if "target_present" in example:
        return "present" if example["target_present"] else "absent"
    return "absent" if normalize(example.get("status")) in ABSENT_STATUSES else "present"


def predicted_status(example):
    status = normalize(example.get("predicted_status"))
    if status in ABSENT_STATUSES:
        return "absent"
    if status == "present":
        return "present"
    return "present" if example.get("prediction", []) else "absent"


def target_text(example):
    return str(example.get("query_text") or example.get("target") or example.get("original_target") or "")


def safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def cue_from_example(example, key):
    cue = str(example.get("cue") or "").strip()
    if cue:
        return cue
    parts = str(key).rsplit("_", 1)
    return parts[-1] if len(parts) == 2 and parts[-1] in {"t", "tc", "i"} else ""


def conflict_bucket(query, ocr_text, ocr_score, strong_threshold):
    query_norm = normalize(query)
    query_no_color = strip_color_prefix(query)
    ocr_norm = normalize(ocr_text)
    sim_full = similarity(query_norm, ocr_norm)
    sim_no_color = similarity(query_no_color, ocr_norm)
    best_sim = max(sim_full, sim_no_color, ocr_score)
    if query_norm and query_norm == ocr_norm:
        return "exact_text_visible", sim_full, sim_no_color, best_sim
    if query_no_color and query_no_color == ocr_norm and query_no_color != query_norm:
        return "color_ignored_exact_text_visible", sim_full, sim_no_color, best_sim
    if query_norm and ocr_norm and (query_norm in ocr_norm or ocr_norm in query_norm):
        return "substring_text_visible", sim_full, sim_no_color, best_sim
    if query_no_color and ocr_norm and (query_no_color in ocr_norm or ocr_norm in query_no_color):
        return "color_ignored_substring_visible", sim_full, sim_no_color, best_sim
    if best_sim >= strong_threshold:
        return "strong_ocr_match", sim_full, sim_no_color, best_sim
    if ocr_text:
        return "weak_or_distractor_ocr_match", sim_full, sim_no_color, best_sim
    return "no_ocr_match", sim_full, sim_no_color, best_sim


def row_for(idx, example, key, strong_threshold):
    query = target_text(example)
    ocr_text = str(example.get("ocr_candidate_verifier_text", "") or "")
    ocr_score = safe_float(example.get("ocr_candidate_verifier_score"))
    bucket, sim_full, sim_no_color, best_sim = conflict_bucket(query, ocr_text, ocr_score, strong_threshold)
    return {
        "index": idx,
        "key": key,
        "image": example.get("image", ""),
        "cue": cue_from_example(example, key),
        "gold_status": gold_status(example),
        "predicted_status": predicted_status(example),
        "target": query,
        "target_without_color_prefix": strip_color_prefix(query),
        "ocr_text": ocr_text,
        "ocr_score": ocr_score,
        "ocr_conf": example.get("ocr_candidate_verifier_conf", ""),
        "similarity_full": sim_full,
        "similarity_without_color": sim_no_color,
        "best_text_visibility_score": best_sim,
        "visibility_bucket": bucket,
        "path_best_evidence": example.get("path_best_evidence", ""),
    }


def write_summary(path, rows, absent_rows, strong_visible_buckets):
    status_counts = Counter(row["gold_status"] for row in rows)
    cue_counts = Counter(row["cue"] for row in rows)
    absent_bucket_counts = Counter(row["visibility_bucket"] for row in absent_rows)
    absent_cue_bucket_counts = Counter((row["cue"], row["visibility_bucket"]) for row in absent_rows)
    visible_conflicts = [row for row in absent_rows if row["visibility_bucket"] in strong_visible_buckets]

    lines = [
        "# Native VSGUI Label/Text-Visibility Audit",
        "",
        f"- Rows audited: {len(rows)}",
        f"- Gold-absent rows: {len(absent_rows)}",
        f"- Gold-absent rows with strong visible-text evidence: {len(visible_conflicts)}",
        "",
        "## Status Counts",
        "",
        "| Status | Count |",
        "|---|---:|",
    ]
    for key, count in sorted(status_counts.items()):
        lines.append(f"| {key} | {count} |")
    lines.extend(["", "## Cue Counts", "", "| Cue | Count |", "|---|---:|"])
    for key, count in sorted(cue_counts.items()):
        lines.append(f"| {key or '(missing)'} | {count} |")
    lines.extend(["", "## Gold-Absent Visibility Buckets", "", "| Bucket | Count |", "|---|---:|"])
    for key, count in absent_bucket_counts.most_common():
        lines.append(f"| {key} | {count} |")
    lines.extend(["", "## Gold-Absent Visibility By Cue", "", "| Cue | Bucket | Count |", "|---|---|---:|"])
    for (cue, bucket), count in sorted(absent_cue_bucket_counts.items()):
        lines.append(f"| {cue or '(missing)'} | {bucket} | {count} |")
    lines.extend([
        "",
        "## Interpretation",
        "",
        "- Rows in exact/substring/color-ignored visible buckets should not be treated as clean target-not-visible examples without manual checking.",
        "- For text+color cues, color-ignored matches often mean the text appears but the requested color may differ; this is a different task than text absence.",
        "- Use this audit to decide whether native VSGUI is a native absent benchmark, a color/instance matching benchmark, or a noisy external stress test.",
        "",
    ])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Audit native VSGUI labels against OCR-visible target text.")
    parser.add_argument("--predictions", required=True, help="Prediction JSON with OCR verifier fields.")
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--output-md", required=True)
    parser.add_argument("--strong-threshold", type=float, default=0.8)
    args = parser.parse_args()

    data = load_json(Path(args.predictions))
    rows = [row_for(idx, example, str(example.get("img_usr_tgt") or idx), args.strong_threshold) for idx, example in enumerate(data)]
    absent_rows = [row for row in rows if row["gold_status"] == "absent"]
    strong_visible_buckets = {
        "exact_text_visible",
        "color_ignored_exact_text_visible",
        "substring_text_visible",
        "color_ignored_substring_visible",
        "strong_ocr_match",
    }
    conflict_rows = [row for row in absent_rows if row["visibility_bucket"] in strong_visible_buckets]

    write_json(Path(args.output_json), {
        "num_rows": len(rows),
        "num_absent": len(absent_rows),
        "num_absent_visible_conflicts": len(conflict_rows),
        "rows": rows,
        "conflict_rows": conflict_rows,
    })
    write_csv(Path(args.output_csv), conflict_rows)
    write_summary(Path(args.output_md), rows, absent_rows, strong_visible_buckets)
    print(json.dumps({
        "rows": len(rows),
        "absent": len(absent_rows),
        "absent_visible_conflicts": len(conflict_rows),
        "output_md": args.output_md,
    }, indent=2))


if __name__ == "__main__":
    main()
