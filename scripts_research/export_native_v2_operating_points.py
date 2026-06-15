#!/usr/bin/env python
import argparse
import csv
import json
from pathlib import Path


CV_METHODS = {
    "cv_vote_router",
    "cv_vote_utility",
    "cv_vote_precision60",
    "cv_vote_pa25",
}


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
        "role",
        "method",
        "family",
        "num_examples",
        "accuracy",
        "absent_precision",
        "absent_recall",
        "absent_f1",
        "present_absent",
        "absent_present",
        "present_absent_rate",
        "delta_f1_mean",
        "delta_f1_low",
        "delta_f1_high",
        "delta_accuracy_mean",
        "delta_accuracy_low",
        "delta_accuracy_high",
        "reading",
    ]
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def as_float(row, key, default=0.0):
    try:
        return float(row.get(key, ""))
    except (TypeError, ValueError):
        return default


def as_int(row, key):
    try:
        return int(float(row.get(key, 0)))
    except (TypeError, ValueError):
        return 0


def fmt(value):
    try:
        return f"{float(value):.4f}"
    except (TypeError, ValueError):
        return ""


def present_absent_rate(row):
    present_absent = as_int(row, "present_absent")
    present_present = as_int(row, "present_present")
    if not present_present:
        total = as_int(row, "num_examples")
        present_present = max(total // 2 - present_absent, 0)
    return present_absent / (present_absent + present_present) if present_absent + present_present else 0.0


def normalize_row(row, role, reading):
    out = dict(row)
    out["role"] = role
    out["present_absent_rate"] = present_absent_rate(row)
    out["reading"] = reading
    return out


def max_by(rows, key):
    return max(rows, key=key) if rows else None


def role_rows(split, rows):
    prompt = next((row for row in rows if row["method"] == "prompt"), None)
    cv_rows = [row for row in rows if row["method"] in CV_METHODS]
    single_rows = [row for row in rows if row["method"] != "prompt" and row["method"] not in CV_METHODS]
    selected = []

    if prompt:
        selected.append(normalize_row(prompt, "baseline", "Forced-choice baseline; low recall indicates many absent targets are still grounded as present."))

    best_single = max_by(single_rows, lambda row: (as_float(row, "absent_f1"), as_float(row, "accuracy")))
    if best_single:
        selected.append(normalize_row(best_single, "best_single", "Best single verifier; easiest to explain as an interpretable method."))

    best_cv = max_by(cv_rows, lambda row: (as_float(row, "absent_f1"), as_float(row, "accuracy")))
    if best_cv:
        selected.append(normalize_row(best_cv, "best_cv_aggressive", "Best cross-validated router; strongest F1 but may over-reject visible targets."))

    precision_cv = next((row for row in rows if row["method"] == "cv_vote_precision60"), None)
    if precision_cv:
        selected.append(normalize_row(precision_cv, "precision_constrained_cv", "Cross-validated router with absent precision constraint."))

    pa25_cv = next((row for row in rows if row["method"] == "cv_vote_pa25"), None)
    if pa25_cv:
        selected.append(normalize_row(pa25_cv, "present_rejection_constrained_cv", "Conservative operating point that limits present-target over-rejection."))

    if "color_instance" in split:
        recommended = max_by(
            rows,
            lambda row: (
                as_float(row, "accuracy") >= as_float(prompt or {}, "accuracy"),
                as_float(row, "absent_f1"),
                as_float(row, "accuracy"),
            ),
        )
        reading = "Diagnostic only: color/instance matching remains a separate unresolved task."
    else:
        eligible = [row for row in rows if row["method"] != "prompt" and as_float(row, "absent_precision") >= 0.60]
        recommended = max_by(eligible, lambda row: (as_float(row, "absent_f1"), as_float(row, "accuracy"))) or best_cv or best_single
        reading = "Recommended paper operating point: strong F1 while keeping absent precision near or above 0.60."
    if recommended:
        selected.append(normalize_row(recommended, "recommended", reading))

    seen = set()
    deduped = []
    for row in selected:
        key = (row["split"], row["role"], row["method"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped


def write_md(path, rows):
    lines = [
        "# Native VSGUI10K v2 Operating Points",
        "",
        "This table compresses the balanced native v2 analysis into paper-facing operating points.",
        "",
        "| Split | Role | Method | Acc | Prec. | Rec. | F1 | P->A | A->P | P->A Rate | Delta F1 CI | Reading |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|",
    ]
    for row in rows:
        ci = ""
        if row["method"] != "prompt":
            ci = f"[{fmt(row.get('delta_f1_low'))}, {fmt(row.get('delta_f1_high'))}]"
        lines.append(
            f"| {row['split']} | {row['role']} | {row['method']} | "
            f"{fmt(row['accuracy'])} | {fmt(row['absent_precision'])} | {fmt(row['absent_recall'])} | "
            f"{fmt(row['absent_f1'])} | {row['present_absent']} | {row['absent_present']} | "
            f"{fmt(row['present_absent_rate'])} | {ci} | {row['reading']} |"
        )

    lines.extend([
        "",
        "## Paper Reading",
        "",
        "- Use `recommended` rows for the main native-v2 table.",
        "- Use `best_cv_aggressive` to show the upper range of current verifier complementarity.",
        "- Use `present_rejection_constrained_cv` when discussing conservative UI-evaluation settings where false absence is costly.",
        "- Do not headline `native_v2_color_instance_balanced` as solved; it is evidence that color/instance target definitions need richer modeling.",
        "",
    ])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Export paper-facing operating points from native v2 balanced analysis.")
    parser.add_argument("--input-csv", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--output-md", required=True)
    args = parser.parse_args()

    rows = read_csv(Path(args.input_csv))
    by_split = {}
    for row in rows:
        by_split.setdefault(row["split"], []).append(row)

    selected = []
    for split in sorted(by_split):
        selected.extend(role_rows(split, by_split[split]))

    write_json(Path(args.output_json), {"rows": selected})
    write_csv(Path(args.output_csv), selected)
    write_md(Path(args.output_md), selected)
    print(json.dumps({"rows": len(selected), "output_md": args.output_md}, indent=2))


if __name__ == "__main__":
    main()
