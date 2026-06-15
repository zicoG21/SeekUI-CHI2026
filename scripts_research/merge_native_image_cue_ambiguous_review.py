#!/usr/bin/env python
import argparse
import csv
import json
import shutil
from collections import Counter
from pathlib import Path

import resolve_native_vsgui10k_image_cues as resolver


def load_json(path, default=None):
    path = Path(path)
    if not path.exists():
        return default if default is not None else []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def read_csv(path):
    with open(path, "r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


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
        writer = csv.DictWriter(f, fieldnames=fieldnames or ["empty"], lineterminator="\n", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def choose_candidate(row):
    if str(row.get("review_decision", "")).strip().casefold() != "use":
        return ""
    try:
        rank = int(str(row.get("use_candidate_rank", "")).strip())
    except ValueError:
        return ""
    paths = [item for item in str(row.get("candidate_local_paths", "")).split(";") if item]
    if rank < 0 or rank >= len(paths):
        return ""
    return paths[rank]


def compact_row(row):
    return {
        "img_usr_tgt": row.get("img_usr_tgt", ""),
        "image": row.get("image", ""),
        "target_crop": row.get("target_crop", ""),
        "status": row.get("status", ""),
        "query_text": row.get("query_text", ""),
        "native_new_img_name": row.get("native_new_img_name", ""),
        "native_image_cue_review_source": row.get("native_image_cue_review_source", ""),
    }


def balanced_rows(rows):
    present = sorted([row for row in rows if resolver.gold_status(row) == "present"], key=lambda row: str(row.get("img_usr_tgt", "")))
    absent = sorted([row for row in rows if resolver.gold_status(row) == "absent"], key=lambda row: str(row.get("img_usr_tgt", "")))
    keep = min(len(present), len(absent))
    return sorted(present[:keep] + absent[:keep], key=lambda row: str(row.get("img_usr_tgt", "")))


def write_summary(path, base_rows, added_rows, merged_rows, balanced):
    status = Counter(resolver.gold_status(row) for row in merged_rows)
    added_status = Counter(resolver.gold_status(row) for row in added_rows)
    balanced_status = Counter(resolver.gold_status(row) for row in balanced)
    lines = [
        "# Merged Native Image-Cue Ambiguous Review",
        "",
        f"- Base eval rows: {len(base_rows)}",
        f"- Added reviewed rows: {len(added_rows)}",
        f"- Merged eval rows: {len(merged_rows)}",
        f"- Balanced eval rows: {len(balanced)}",
        "",
        "| Split | Present | Absent | Rows |",
        "|---|---:|---:|---:|",
        f"| added reviewed | {added_status.get('present', 0)} | {added_status.get('absent', 0)} | {len(added_rows)} |",
        f"| merged eval | {status.get('present', 0)} | {status.get('absent', 0)} | {len(merged_rows)} |",
        f"| balanced eval | {balanced_status.get('present', 0)} | {balanced_status.get('absent', 0)} | {len(balanced)} |",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Merge manually reviewed ambiguous native image-cue assets into eval JSON.")
    parser.add_argument("--trials-json", required=True)
    parser.add_argument("--base-eval-json", required=True)
    parser.add_argument("--review-csv", required=True)
    parser.add_argument("--image-root", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()

    trials = load_json(args.trials_json)
    base_rows = load_json(args.base_eval_json, default=[])
    existing = {row.get("img_usr_tgt") for row in base_rows}
    out_dir = Path(args.out_dir)
    cue_dir = out_dir / "reviewed_cue_images"
    cue_dir.mkdir(parents=True, exist_ok=True)

    added = []
    for row in read_csv(Path(args.review_csv)):
        selected = choose_candidate(row)
        if not selected or not Path(selected).exists():
            continue
        try:
            trial_index = int(row.get("index", ""))
        except ValueError:
            continue
        if trial_index < 0 or trial_index >= len(trials):
            continue
        example = dict(trials[trial_index])
        if example.get("img_usr_tgt") in existing:
            continue
        dst = cue_dir / f"{trial_index:05d}_{Path(selected).name}"
        shutil.copy2(selected, dst)
        merged = resolver.compatible_example(example, dst, args.image_root, f"reviewed_{trial_index:05d}")
        merged["native_image_cue_resolved"] = 1
        merged["native_image_cue_review_source"] = row.get("review_id", "")
        merged["native_image_cue_review_notes"] = row.get("notes", "")
        added.append(merged)
        existing.add(merged.get("img_usr_tgt"))

    merged_rows = sorted(base_rows + added, key=lambda row: str(row.get("img_usr_tgt", "")))
    balanced = balanced_rows(merged_rows)
    write_json(out_dir / "native_image_cue_eval_review_merged.json", merged_rows)
    write_json(out_dir / "native_image_cue_balanced_eval_review_merged.json", balanced)
    write_csv(out_dir / "native_image_cue_eval_review_merged.csv", [compact_row(row) for row in merged_rows])
    write_summary(out_dir / "native_image_cue_review_merge.md", base_rows, added, merged_rows, balanced)
    print(json.dumps({
        "base_rows": len(base_rows),
        "added_rows": len(added),
        "merged_rows": len(merged_rows),
        "balanced_rows": len(balanced),
        "summary_md": str(out_dir / "native_image_cue_review_merge.md"),
    }, indent=2))


if __name__ == "__main__":
    main()
