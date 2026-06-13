#!/usr/bin/env python
import argparse
import csv
import json
import random
from collections import Counter, defaultdict
from pathlib import Path


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


def simple_row(example):
    return {
        "img_usr_tgt": example.get("img_usr_tgt", ""),
        "image": example.get("image", ""),
        "status": example.get("status", ""),
        "target_present": example.get("target_present", ""),
        "cue_type": example.get("cue_type", ""),
        "query_text": example.get("query_text", ""),
        "target": example.get("target", ""),
        "target_color": example.get("target_color", ""),
        "category": example.get("category", ""),
        "fixation_count": example.get("fixation_count", ""),
    }


def balanced_subset(examples, cue_type, seed, max_per_status):
    rows = [row for row in examples if cue_type == "all" or row.get("cue_type") == cue_type]
    by_status = defaultdict(list)
    for row in rows:
        by_status[row.get("status", "present")].append(row)
    rng = random.Random(seed)
    present = list(by_status.get("present", []))
    absent = list(by_status.get("absent", []))
    rng.shuffle(present)
    rng.shuffle(absent)
    n = min(len(present), len(absent))
    if max_per_status > 0:
        n = min(n, max_per_status)
    selected = present[:n] + absent[:n]
    selected.sort(key=lambda row: (row.get("cue_type", ""), row.get("status", ""), row.get("img_usr_tgt", "")))
    return selected


def summary_for(name, examples):
    return {
        "name": name,
        "num_examples": len(examples),
        "status_counts": dict(Counter(row.get("status", "") for row in examples).most_common()),
        "cue_counts": dict(Counter(row.get("cue_type", "") for row in examples).most_common()),
        "category_counts": dict(Counter(row.get("category", "") for row in examples).most_common()),
    }


def write_markdown(path, summaries):
    lines = [
        "# Native VSGUI10K Evaluation Splits",
        "",
        "These splits are balanced present/absent subsets exported from the native OSF VSGUI10K visual-search trials.",
        "",
        "| Split | Examples | Present | Absent | Cues |",
        "|---|---:|---:|---:|---|",
    ]
    for item in summaries:
        status = item["status_counts"]
        cue = ", ".join(f"{key}:{value}" for key, value in item["cue_counts"].items())
        lines.append(
            f"| {item['name']} | {item['num_examples']} | {status.get('present', 0)} | "
            f"{status.get('absent', 0)} | {cue} |"
        )
    lines.extend([
        "",
        "Suggested use:",
        "",
        "- `native_text_balanced`: closest native counterpart to current text-target absent evaluation.",
        "- `native_text_color_balanced`: target cue includes text plus color, useful for multimodal attribute grounding.",
        "- `native_image_balanced`: native non-text/image-cue direction; requires image-cue prompting or crop-based target input.",
        "- `native_all_cues_balanced`: native mixed-cue present/absent stress test.",
        "",
    ])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Export balanced native VSGUI10K evaluation splits.")
    parser.add_argument("--trials-json", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--seed", type=int, default=20260613)
    parser.add_argument("--max-per-status", type=int, default=0)
    args = parser.parse_args()

    trials = load_json(args.trials_json)
    out_dir = Path(args.out_dir)
    split_specs = [
        ("native_text_balanced", "text"),
        ("native_text_color_balanced", "text+color"),
        ("native_image_balanced", "image"),
        ("native_all_cues_balanced", "all"),
    ]
    summaries = []
    for name, cue_type in split_specs:
        selected = balanced_subset(trials, cue_type, args.seed, args.max_per_status)
        write_json(out_dir / f"{name}.json", selected)
        write_csv(out_dir / f"{name}.csv", [simple_row(row) for row in selected])
        summaries.append({
            **summary_for(name, selected),
            "json": str(out_dir / f"{name}.json"),
            "csv": str(out_dir / f"{name}.csv"),
        })

    write_json(out_dir / "native_eval_splits_summary.json", summaries)
    write_markdown(out_dir / "native_eval_splits_summary.md", summaries)
    print(json.dumps({
        "splits": len(summaries),
        "out_dir": str(out_dir),
        "summary_md": str(out_dir / "native_eval_splits_summary.md"),
    }, indent=2))


if __name__ == "__main__":
    main()
