#!/usr/bin/env python
import argparse
import csv
import json
from pathlib import Path


MAIN_CASES = [
    "forced_choice_fixed",
    "method_overreject_present",
    "forced_choice_kept",
    "both_wrong_absent",
]


def read_csv(path):
    with open(path, "r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "split",
        "method",
        "case_type",
        "count",
        "selected",
        "suggested_use",
        "csv",
    ]
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def read_manifest(path):
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def suggested_use(split, case_type):
    if "color_instance" in split:
        return "Use as unresolved color/instance diagnostic, not as a solved absence example."
    if case_type == "forced_choice_fixed":
        return "Main positive case: prompt-only forced a present grounding; verifier reports absent."
    if case_type == "method_overreject_present":
        return "Tradeoff case: verifier rejects a visible target."
    if case_type in {"forced_choice_kept", "both_wrong_absent"}:
        return "Residual failure case: remaining distractor or native target-definition issue."
    return ""


def collect_rows(case_root):
    rows = []
    for manifest_path in sorted(case_root.glob("*/recommended/native_v2_case_manifest.json")):
        manifest = read_manifest(manifest_path)
        if not manifest:
            continue
        split = manifest.get("split", manifest_path.parents[1].name)
        method = manifest.get("method", "")
        by_case = {row["case_type"]: row for row in manifest.get("manifest", [])}
        for case_type in MAIN_CASES:
            row = by_case.get(case_type)
            if not row:
                continue
            rows.append({
                "split": split,
                "method": method,
                "case_type": case_type,
                "count": row.get("count", 0),
                "selected": row.get("selected", 0),
                "csv": row.get("csv", ""),
                "suggested_use": suggested_use(split, case_type),
            })
    return rows


def write_md(path, rows):
    lines = [
        "# Native VSGUI10K v2 Case Figure Plan",
        "",
        "Use this compact plan to choose main-text qualitative examples from the recommended operating points.",
        "",
        "| Split | Method | Case Type | Count | Selected | Suggested Use |",
        "|---|---|---|---:|---:|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row['split']} | {row['method']} | {row['case_type']} | "
            f"{row['count']} | {row['selected']} | {row['suggested_use']} |"
        )
    lines.extend([
        "",
        "## Recommended Main Figure",
        "",
        "Choose three large examples rather than a dense contact sheet:",
        "",
        "1. `forced_choice_fixed` from `native_v2_main_text_balanced` or `native_v2_clean_text_all_balanced`.",
        "2. `method_overreject_present` from the same split to show the conservative cost.",
        "3. `forced_choice_kept` or `both_wrong_absent` from `native_v2_color_instance_balanced` to show unresolved color/instance or target-definition ambiguity.",
        "",
        "Caption framing: native VSGUI10K confirms forced-choice behavior outside the synthetic benchmark, while also exposing harder target-definition cases that require richer target representations.",
        "",
    ])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Export a compact case-figure plan for native v2 recommended cases.")
    parser.add_argument("--case-root", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--output-md", required=True)
    args = parser.parse_args()

    rows = collect_rows(Path(args.case_root))
    write_json(Path(args.output_json), {"rows": rows})
    write_csv(Path(args.output_csv), rows)
    write_md(Path(args.output_md), rows)
    print(json.dumps({"rows": len(rows), "output_md": args.output_md}, indent=2))


if __name__ == "__main__":
    main()
