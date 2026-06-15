#!/usr/bin/env python
import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path


ABSENT_STATUSES = {"absent", "not_found", "not found", "no object", "no target", "not present"}
ROLES = [
    "recommended",
    "best_cv_aggressive",
    "best_single",
    "present_rejection_constrained_cv",
]
CASE_TYPES = [
    "forced_choice_fixed",
    "forced_choice_kept",
    "method_overreject_present",
    "method_rescues_present",
    "prompt_wrong_method_correct",
    "prompt_correct_method_wrong",
    "both_wrong_absent",
    "both_wrong_present",
]
METHOD_TEMPLATES = {
    "prompt": "present_absent_predictions_{model}_{split}.json",
    "combined_best_f1": "present_absent_predictions_{model}_{split}_combined_and_present_only_best_f1.json",
    "combined_default": "present_absent_predictions_{model}_{split}_combined_and_present_only.json",
    "color_aware": "present_absent_predictions_{model}_{split}_color_aware_native_tuned_absent_f1.json",
    "context_crop": "present_absent_predictions_{model}_{split}_context_crop_ocr_vlm.json",
    "vlm_presence_ocr_aware": "vlm_presence_predictions_{model}_vlm_presence_{split}_ocr_aware.json",
    "vlm_evidence": "vlm_evidence_predictions_{model}_vlm_evidence_{split}_evidence_aware.json",
    "cv_vote_router": "present_absent_predictions_{model}_{split}_native_v2_cv_vote_router.json",
    "cv_vote_precision60": "present_absent_predictions_{model}_{split}_native_v2_cv_vote_router_precision_ge_0p60.json",
    "cv_vote_pa25": "present_absent_predictions_{model}_{split}_native_v2_cv_vote_router_pa_rate_le_0p25.json",
    "cv_vote_utility": "present_absent_predictions_{model}_{split}_native_v2_cv_vote_router_utility_ap2_pa1.json",
}


def read_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def read_csv(path):
    with open(path, "r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def write_csv(path, rows, fieldnames=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = []
        for row in rows:
            for key in row:
                if key not in fieldnames:
                    fieldnames.append(key)
        if not fieldnames:
            fieldnames = ["empty"]
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def normalize_status(value, default="present"):
    text = str(value or default).strip().casefold()
    return "absent" if text in ABSENT_STATUSES else "present"


def gold_status(example):
    if "target_present" in example:
        return "present" if example["target_present"] else "absent"
    if "gold_status" in example:
        return normalize_status(example.get("gold_status"), default="present")
    return normalize_status(example.get("status"), default="present")


def predicted_status(example):
    status = str(example.get("predicted_status", "") or example.get("adjusted_predicted_status", "")).strip().casefold()
    if status in ABSENT_STATUSES:
        return "absent"
    if status == "present":
        return "present"
    return "present" if example.get("prediction", []) else "absent"


def example_key(example, fallback_index=None):
    for field in ("img_usr_tgt", "key", "id", "review_id"):
        value = example.get(field)
        if value not in {"", None}:
            return str(value)
    parts = [
        str(example.get("image", "")),
        str(example.get("target_id", "")),
        str(example.get("query_text", example.get("target", example.get("original_target", "")))),
        str(example.get("status", example.get("gold_status", ""))),
    ]
    if any(parts):
        return "|".join(parts)
    return f"index:{fallback_index}"


def target_text(example):
    return str(example.get("query_text") or example.get("target") or example.get("original_target") or "")


def method_path(outputs_dir, model, split, method):
    template = METHOD_TEMPLATES.get(method)
    if not template:
        return None
    return outputs_dir / template.format(model=model, split=split)


def load_by_key(path):
    return {example_key(example, idx): example for idx, example in enumerate(read_json(path))}


def classify(gold, prompt_status, method_status):
    labels = []
    prompt_ok = prompt_status == gold
    method_ok = method_status == gold
    if gold == "absent" and prompt_status == "present" and method_status == "absent":
        labels.append("forced_choice_fixed")
    if gold == "absent" and prompt_status == "present" and method_status == "present":
        labels.append("forced_choice_kept")
    if gold == "present" and prompt_status == "present" and method_status == "absent":
        labels.append("method_overreject_present")
    if gold == "present" and prompt_status == "absent" and method_status == "present":
        labels.append("method_rescues_present")
    if not prompt_ok and method_ok:
        labels.append("prompt_wrong_method_correct")
    if prompt_ok and not method_ok:
        labels.append("prompt_correct_method_wrong")
    if not prompt_ok and not method_ok and gold == "absent":
        labels.append("both_wrong_absent")
    if not prompt_ok and not method_ok and gold == "present":
        labels.append("both_wrong_present")
    return labels


def evidence_fields(example):
    fields = {}
    for key in [
        "path_best_evidence",
        "ocr_candidate_verifier_score",
        "ocr_candidate_verifier_text",
        "ocr_candidate_verifier_conf",
        "color_aware_score",
        "color_aware_text_score",
        "color_aware_color_score",
        "color_aware_ocr_text",
        "candidate_crop_count",
        "candidate_crop_present_count",
        "native_v2_cv_vote_router_objective",
    ]:
        fields[key] = example.get(key, "")
    return fields


def row_for(idx, base, prompt, method, role, method_name, case_type):
    gold = gold_status(base)
    prompt_pred = predicted_status(prompt)
    method_pred = predicted_status(method)
    row = {
        "index": idx,
        "case_type": case_type,
        "role": role,
        "method": method_name,
        "key": example_key(base, idx),
        "image": base.get("image", ""),
        "target": target_text(base),
        "cue_type": base.get("cue_type", base.get("cue", "")),
        "gold_status": gold,
        "prompt_status": prompt_pred,
        "method_status": method_pred,
        "prompt_correct": int(prompt_pred == gold),
        "method_correct": int(method_pred == gold),
        "native_v2_task": base.get("native_v2_task", ""),
        "visibility_bucket": base.get("native_v2_visibility_bucket", ""),
        "text_visibility_score": base.get("native_v2_text_visibility_score", ""),
    }
    row.update(evidence_fields(method))
    return row


def selected_operating_points(rows):
    selected = []
    for row in rows:
        if row.get("role") in ROLES:
            selected.append(row)
    selected.sort(key=lambda row: (row.get("split", ""), ROLES.index(row.get("role", "recommended"))))
    return selected


def export_cases(work_dir, model, op_row, limit, out_dir):
    outputs_dir = work_dir / "outputs"
    split = op_row["split"]
    role = op_row["role"]
    method = op_row["method"]
    split_path = outputs_dir / "native_vsgui10k" / "processed_v2" / "splits" / f"{split}.json"
    prompt_path = method_path(outputs_dir, model, split, "prompt")
    method_predictions_path = method_path(outputs_dir, model, split, method)
    if not split_path.exists() or not prompt_path or not prompt_path.exists() or not method_predictions_path or not method_predictions_path.exists():
        return {
            "split": split,
            "role": role,
            "method": method,
            "status": "missing_input",
            "split_path": str(split_path),
            "prompt_path": str(prompt_path) if prompt_path else "",
            "method_path": str(method_predictions_path) if method_predictions_path else "",
        }, []

    base_examples = read_json(split_path)
    prompt_by_key = load_by_key(prompt_path)
    method_by_key = load_by_key(method_predictions_path)
    groups = {case_type: [] for case_type in CASE_TYPES}
    all_rows = []
    for idx, base in enumerate(base_examples):
        key = example_key(base, idx)
        prompt = prompt_by_key.get(key, base)
        method_example = method_by_key.get(key, base)
        gold = gold_status(base)
        prompt_pred = predicted_status(prompt)
        method_pred = predicted_status(method_example)
        for case_type in classify(gold, prompt_pred, method_pred):
            row = row_for(idx, base, prompt, method_example, role, method, case_type)
            groups[case_type].append(row)
            all_rows.append(row)

    op_dir = out_dir / split / role
    manifest = []
    index_rows = []
    for case_type in CASE_TYPES:
        rows = groups[case_type]
        selected = rows[:limit]
        write_csv(op_dir / f"{case_type}.csv", selected)
        write_json(op_dir / f"{case_type}.json", selected)
        index_rows.extend(selected)
        manifest.append({
            "case_type": case_type,
            "count": len(rows),
            "selected": len(selected),
            "csv": str(op_dir / f"{case_type}.csv"),
            "json": str(op_dir / f"{case_type}.json"),
        })
    write_csv(op_dir / "native_v2_case_index.csv", index_rows)
    write_json(op_dir / "native_v2_case_manifest.json", {
        "split": split,
        "role": role,
        "method": method,
        "operating_point": op_row,
        "manifest": manifest,
    })
    return {
        "split": split,
        "role": role,
        "method": method,
        "status": "ok",
        "manifest": manifest,
        "out_dir": str(op_dir),
    }, all_rows


def write_md(path, manifests):
    lines = [
        "# Native VSGUI10K v2 Recommended Case Analysis",
        "",
        "Cases compare prompt-only SeekUI against each selected operating point.",
        "",
        "## Operating Points",
        "",
        "| Split | Role | Method | Status | Case Type | Count | Selected |",
        "|---|---|---|---|---|---:|---:|",
    ]
    for item in manifests:
        if item["status"] != "ok":
            lines.append(f"| {item['split']} | {item['role']} | {item['method']} | {item['status']} |  |  |  |")
            continue
        for case in item["manifest"]:
            lines.append(
                f"| {item['split']} | {item['role']} | {item['method']} | ok | "
                f"{case['case_type']} | {case['count']} | {case['selected']} |"
            )

    lines.extend([
        "",
        "## Reading",
        "",
        "- `forced_choice_fixed`: missing target was grounded by prompt-only but rejected by the operating point.",
        "- `method_overreject_present`: visible target was preserved by prompt-only but rejected by the operating point; this is the main conservative cost.",
        "- `forced_choice_kept` and `both_wrong_absent`: residual native absent failures, useful for distractor and target-definition analysis.",
        "- Use `recommended` for main paper examples, `best_cv_aggressive` for upper-bound complementarity, and `present_rejection_constrained_cv` for conservative operating-point discussion.",
        "",
    ])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Export case taxonomy for native v2 operating points.")
    parser.add_argument("--work-dir", required=True)
    parser.add_argument("--model-name", default="SeekUI")
    parser.add_argument("--operating-points-csv", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--limit", type=int, default=40)
    args = parser.parse_args()

    work_dir = Path(args.work_dir)
    out_dir = Path(args.out_dir)
    operating_points = selected_operating_points(read_csv(Path(args.operating_points_csv)))
    manifests = []
    combined_rows = []
    for op_row in operating_points:
        manifest, rows = export_cases(work_dir, args.model_name, op_row, args.limit, out_dir)
        manifests.append(manifest)
        combined_rows.extend(rows)

    write_json(out_dir / "native_v2_recommended_case_analysis.json", {"operating_points": manifests})
    write_csv(out_dir / "native_v2_recommended_case_index.csv", combined_rows)
    write_md(out_dir / "native_v2_recommended_case_analysis.md", manifests)
    print(json.dumps({
        "operating_points": len(manifests),
        "case_rows": len(combined_rows),
        "output_md": str(out_dir / "native_v2_recommended_case_analysis.md"),
    }, indent=2))


if __name__ == "__main__":
    main()
