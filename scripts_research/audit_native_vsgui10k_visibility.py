#!/usr/bin/env python
import argparse
import csv
import difflib
import json
from collections import Counter
from pathlib import Path


ABSENT_STATUSES = {"absent", "not_found", "not found", "no object", "no target", "not present"}
TEXT_CUES = {"text", "text+color", "t", "tc"}
COLOR_WORDS = {
    "red", "blue", "green", "yellow", "black", "white", "gray", "grey", "orange", "purple",
    "pink", "brown", "cyan", "magenta", "teal", "violet", "gold", "silver",
}
STRONG_VISIBLE_BUCKETS = {
    "exact_text_visible",
    "color_ignored_exact_text_visible",
    "substring_text_visible",
    "color_ignored_substring_visible",
    "strong_ocr_match",
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
    fieldnames = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames or ["empty"])
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


def is_absent(example):
    if "target_present" in example:
        return not bool(example.get("target_present"))
    return normalize(example.get("status")) in ABSENT_STATUSES


def cue_type(example):
    cue = normalize(example.get("cue_type") or example.get("cue") or example.get("native_cue"))
    return {"t": "text", "tc": "text+color", "i": "image"}.get(cue, cue or "unknown")


def target_text(example):
    return str(example.get("query_text") or example.get("target") or example.get("original_target") or "")


def load_ocr_by_image(path):
    data = load_json(Path(path))
    rows = data.get("images", data if isinstance(data, list) else [])
    out = {}
    for row in rows:
        image = row.get("image", "")
        if image:
            out[image] = row
    return out


def best_ocr_match(query, candidates):
    query_norm = normalize(query)
    query_no_color = strip_color_prefix(query)
    best = {
        "ocr_text": "",
        "ocr_conf": "",
        "similarity_full": 0.0,
        "similarity_without_color": 0.0,
        "best_text_visibility_score": 0.0,
    }
    for candidate in candidates:
        text = str(candidate.get("text", "") or "")
        sim_full = similarity(query_norm, text)
        sim_no_color = similarity(query_no_color, text)
        score = max(sim_full, sim_no_color)
        if score > best["best_text_visibility_score"]:
            best = {
                "ocr_text": text,
                "ocr_conf": candidate.get("conf", ""),
                "similarity_full": sim_full,
                "similarity_without_color": sim_no_color,
                "best_text_visibility_score": score,
            }
    return best


def visibility_bucket(query, match, strong_threshold):
    query_norm = normalize(query)
    query_no_color = strip_color_prefix(query)
    ocr_norm = normalize(match["ocr_text"])
    sim_full = match["similarity_full"]
    sim_no_color = match["similarity_without_color"]
    best_sim = match["best_text_visibility_score"]
    if query_norm and query_norm == ocr_norm:
        return "exact_text_visible"
    if query_no_color and query_no_color != query_norm and query_no_color == ocr_norm:
        return "color_ignored_exact_text_visible"
    if query_norm and ocr_norm and (query_norm in ocr_norm or ocr_norm in query_norm):
        return "substring_text_visible"
    if query_no_color and ocr_norm and query_no_color != query_norm and (
        query_no_color in ocr_norm or ocr_norm in query_no_color
    ):
        return "color_ignored_substring_visible"
    if max(sim_full, sim_no_color, best_sim) >= strong_threshold:
        return "strong_ocr_match"
    if match["ocr_text"]:
        return "weak_or_distractor_ocr_match"
    return "no_ocr_match"


def audit_row(index, example, ocr_by_image, strong_threshold):
    cue = cue_type(example)
    query = target_text(example)
    image = example.get("image", "")
    ocr_row = ocr_by_image.get(image, {})
    candidates = ocr_row.get("candidates", [])
    match = best_ocr_match(query, candidates)
    if cue not in TEXT_CUES:
        bucket = "not_text_cue"
    elif not query:
        bucket = "missing_query_text"
    else:
        bucket = visibility_bucket(query, match, strong_threshold)
    status = "absent" if is_absent(example) else "present"
    return {
        "index": index,
        "key": example.get("img_usr_tgt", index),
        "image": image,
        "cue": cue,
        "gold_status": status,
        "target": query,
        "target_without_color_prefix": strip_color_prefix(query),
        "target_color": example.get("target_color", ""),
        "category": example.get("category", ""),
        "ocr_status": ocr_row.get("status", "missing_ocr_row"),
        "ocr_text": match["ocr_text"],
        "ocr_conf": match["ocr_conf"],
        "similarity_full": match["similarity_full"],
        "similarity_without_color": match["similarity_without_color"],
        "best_text_visibility_score": match["best_text_visibility_score"],
        "visibility_bucket": bucket,
        "num_ocr_candidates": len(candidates),
    }


def write_summary(path, rows, conflict_rows):
    absent_rows = [row for row in rows if row["gold_status"] == "absent"]
    text_absent_rows = [row for row in absent_rows if row["cue"] in {"text", "text+color"}]
    status_counts = Counter(row["gold_status"] for row in rows)
    cue_counts = Counter(row["cue"] for row in rows)
    role_counts = Counter((row["gold_status"], row["cue"], row["visibility_bucket"]) for row in rows)
    absent_bucket_counts = Counter(row["visibility_bucket"] for row in text_absent_rows)
    absent_cue_bucket_counts = Counter((row["cue"], row["visibility_bucket"]) for row in text_absent_rows)
    lines = [
        "# Native VSGUI10K OCR Visibility Audit",
        "",
        f"- Rows audited: {len(rows)}",
        f"- Gold-absent rows: {len(absent_rows)}",
        f"- Text/text+color gold-absent rows: {len(text_absent_rows)}",
        f"- Text/text+color gold-absent rows with strong visible-text evidence: {len(conflict_rows)}",
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
    lines.extend([
        "",
        "## Text/Text+Color Absent Visibility Buckets",
        "",
        "| Bucket | Count |",
        "|---|---:|",
    ])
    for key, count in absent_bucket_counts.most_common():
        lines.append(f"| {key} | {count} |")
    lines.extend([
        "",
        "## Text/Text+Color Absent Visibility By Cue",
        "",
        "| Cue | Bucket | Count |",
        "|---|---|---:|",
    ])
    for (cue, bucket), count in sorted(absent_cue_bucket_counts.items()):
        lines.append(f"| {cue} | {bucket} | {count} |")
    lines.extend([
        "",
        "## Full Status x Cue x Bucket",
        "",
        "| Status | Cue | Bucket | Count |",
        "|---|---|---|---:|",
    ])
    for (status, cue, bucket), count in sorted(role_counts.items()):
        lines.append(f"| {status} | {cue} | {bucket} | {count} |")
    lines.extend([
        "",
        "## Interpretation",
        "",
        "- Use exact/substring/strong OCR matches as visible-text conflicts, not clean absent examples.",
        "- For text+color rows, color-ignored matches often represent color or instance matching rather than simple text absence.",
        "- Rows with no or weak OCR matches can be promoted into clean native text/text+color absent splits, with manual audit as a later validation layer.",
        "",
    ])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Audit native VSGUI10K trials against OCR-visible target text.")
    parser.add_argument("--trials-json", required=True)
    parser.add_argument("--ocr-candidates", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--output-md", required=True)
    parser.add_argument("--strong-threshold", type=float, default=0.8)
    args = parser.parse_args()

    trials = load_json(Path(args.trials_json))
    ocr_by_image = load_ocr_by_image(Path(args.ocr_candidates))
    rows = [audit_row(idx, example, ocr_by_image, args.strong_threshold) for idx, example in enumerate(trials)]
    conflict_rows = [
        row for row in rows
        if row["gold_status"] == "absent"
        and row["cue"] in {"text", "text+color"}
        and row["visibility_bucket"] in STRONG_VISIBLE_BUCKETS
    ]
    write_json(Path(args.output_json), {
        "trials_json": args.trials_json,
        "ocr_candidates": args.ocr_candidates,
        "strong_threshold": args.strong_threshold,
        "num_rows": len(rows),
        "num_absent_visible_conflicts": len(conflict_rows),
        "rows": rows,
        "conflict_rows": conflict_rows,
    })
    write_csv(Path(args.output_csv), conflict_rows)
    write_summary(Path(args.output_md), rows, conflict_rows)
    print(json.dumps({
        "rows": len(rows),
        "absent_visible_conflicts": len(conflict_rows),
        "output_md": args.output_md,
    }, indent=2))


if __name__ == "__main__":
    main()
