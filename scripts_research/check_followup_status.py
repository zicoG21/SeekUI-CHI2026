#!/usr/bin/env python
import argparse
import json
import os
from pathlib import Path


def status_for(outputs, data, item):
    required = [Path(template.format(outputs=outputs, data=data)) for template in item.get("required", [])]
    optional = [Path(template.format(outputs=outputs, data=data)) for template in item.get("optional", [])]
    missing = [str(path) for path in required if not path.exists()]
    present = [str(path) for path in required if path.exists()]
    optional_present = [str(path) for path in optional if path.exists()]

    if not missing:
        state = "done"
    else:
        state = "pending"

    return {
        "id": item["id"],
        "title": item["title"],
        "state": state,
        "present": present,
        "missing": missing,
        "optional_present": optional_present,
        "command": item.get("command", ""),
    }


def build_items(limit, variants):
    return [
        {
            "id": "base_data",
            "title": "Base VSGUI data files",
            "required": [
                "{data}/scanpath_train_explanation.json",
                "{data}/target2text.json",
                "{data}/vsgui10k-images",
            ],
            "command": "bash scripts_utah/download_data.sh",
        },
        {
            "id": "data_audit",
            "title": "Data audit outputs",
            "required": [
                "{outputs}/data_audit/audit_summary.json",
                "{outputs}/data_audit/audit_summary.md",
            ],
            "command": "bash scripts_research/run_offline_research_prep.sh",
        },
        {
            "id": "absent_dataset",
            "title": "Synthetic present/absent benchmark",
            "required": [
                f"{{data}}/absent_synthetic_{limit}.json",
                f"{{data}}/present_absent_synthetic_{limit * 2}.json",
                "{outputs}/absent_validation.json",
            ],
            "command": "bash scripts_research/run_offline_research_prep.sh",
        },
        {
            "id": "cognitive_stopping",
            "title": "Cognitive stopping baseline",
            "required": [
                "{outputs}/cognitive_stopping/cognitive_stopping_summary.json",
                "{outputs}/cognitive_stopping/cognitive_stopping_threshold_sweep.csv",
            ],
            "command": "bash scripts_research/run_offline_research_prep.sh",
        },
        {
            "id": "image_cue_dataset",
            "title": "Target-crop image-cue benchmark",
            "required": [
                f"{{data}}/image_cue_{limit}.json",
                "{data}/target_crops",
            ],
            "command": "bash scripts_research/run_offline_research_prep.sh",
        },
        {
            "id": "semantic_dataset",
            "title": "Semantic query benchmark",
            "required": [
                f"{{data}}/semantic_queries_{limit}_v{variants}.json",
            ],
            "command": "bash scripts_research/run_offline_research_prep.sh",
        },
        {
            "id": "manual_review_sheets",
            "title": "Manual review sheets",
            "required": [
                "{outputs}/review_cases/absent_label_review.csv",
                "{outputs}/review_cases/semantic_query_review.csv",
            ],
            "command": "bash scripts_research/run_offline_research_prep.sh",
        },
        {
            "id": "base_predictions",
            "title": "Base SeekUI and SeekUI-SFT predictions",
            "required": [
                f"{{outputs}}/predictions_SeekUI_{limit}.json",
                f"{{outputs}}/predictions_SeekUI_sft_{limit}.json",
            ],
            "command": "bash scripts_utah/reproduce_seekui_and_sft.sh",
        },
        {
            "id": "base_eval",
            "title": "Base SeekUI and SeekUI-SFT evaluations",
            "required": [
                f"{{outputs}}/eval_SeekUI_{limit}.txt",
                f"{{outputs}}/eval_SeekUI_sft_{limit}.txt",
            ],
            "command": "bash scripts_utah/reproduce_seekui_and_sft.sh",
        },
        {
            "id": "absent_predictions",
            "title": "Present/absent prompt-only predictions",
            "required": [
                "{outputs}/present_absent_predictions_SeekUI.json",
                "{outputs}/present_absent_predictions_SeekUI_sft.json",
                "{outputs}/present_absent_predictions_SeekUI_status_eval.json",
                "{outputs}/present_absent_predictions_SeekUI_sft_status_eval.json",
            ],
            "command": "SKIP_PREP=1 RUN_SFT=1 bash scripts_utah/submit_followup_experiments.sh",
        },
        {
            "id": "image_cue_predictions",
            "title": "Image-cue predictions",
            "required": [
                f"{{outputs}}/image_cue_predictions_SeekUI_{limit}.json",
                f"{{outputs}}/image_cue_predictions_SeekUI_sft_{limit}.json",
            ],
            "command": "SKIP_PREP=1 RUN_SFT=1 bash scripts_utah/submit_followup_experiments.sh",
        },
        {
            "id": "semantic_predictions",
            "title": "Semantic-query predictions and split evaluations",
            "required": [
                f"{{outputs}}/semantic_query_predictions_SeekUI_{limit}_v{variants}.json",
                f"{{outputs}}/semantic_query_predictions_SeekUI_sft_{limit}_v{variants}.json",
                "{outputs}/split_eval/semantic_query_SeekUI_query_type/manifest_with_logs.json",
                "{outputs}/split_eval/semantic_query_SeekUI_sft_query_type/manifest_with_logs.json",
            ],
            "command": "SKIP_PREP=1 RUN_SFT=1 bash scripts_utah/submit_followup_experiments.sh",
        },
        {
            "id": "comparisons",
            "title": "SeekUI vs SFT comparison tables",
            "required": [
                f"{{outputs}}/comparisons/base_SeekUI_vs_SeekUI_sft_{limit}.csv",
                "{outputs}/comparisons/present_absent_SeekUI_vs_SeekUI_sft.csv",
                f"{{outputs}}/comparisons/image_cue_SeekUI_vs_SeekUI_sft_{limit}.csv",
                f"{{outputs}}/comparisons/semantic_query_SeekUI_vs_SeekUI_sft_{limit}_v{variants}.csv",
            ],
            "command": "sbatch scripts_utah/summarize_research_outputs.slurm",
        },
        {
            "id": "manual_review_summary",
            "title": "Filled manual review summary",
            "required": [
                "{outputs}/review_cases/manual_review_summary.json",
                "{outputs}/review_cases/manual_review_summary.md",
            ],
            "command": "python scripts_research/summarize_manual_review.py --input $SEEKUI_WORK/outputs/review_cases/*.csv --output-json $SEEKUI_WORK/outputs/review_cases/manual_review_summary.json",
        },
        {
            "id": "research_summary",
            "title": "Final rolling research summary and CSV tables",
            "required": [
                "{outputs}/research_summary.md",
                "{outputs}/research_summary.json",
                "{outputs}/research_summary_tables/prediction_health.csv",
                "{outputs}/research_summary_tables/overall_metrics.csv",
                "{outputs}/research_summary_tables/absent_status.csv",
                "{outputs}/research_summary_tables/semantic_query_summary.csv",
                "{outputs}/research_summary_tables/split_metrics.csv",
            ],
            "command": "sbatch scripts_utah/summarize_research_outputs.slurm",
        },
    ]


def write_markdown(path, work_dir, rows):
    lines = [
        "# SeekUI Follow-Up Status",
        "",
        f"Work dir: `{work_dir}`",
        "",
        "| State | ID | Task | Missing | Next command |",
        "|---|---|---|---:|---|",
    ]
    for row in rows:
        missing = len(row["missing"])
        command = row["command"].replace("|", "\\|")
        lines.append(f"| {row['state']} | {row['id']} | {row['title']} | {missing} | `{command}` |")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Check SeekUI follow-up experiment artifacts and next commands.")
    parser.add_argument("--work-dir", default=os.environ.get("SEEKUI_WORK", ""))
    parser.add_argument("--limit", type=int, default=int(os.environ.get("SUBSET_LIMIT", "1362")))
    parser.add_argument("--variants-per-example", type=int, default=int(os.environ.get("VARIANTS_PER_EXAMPLE", "2")))
    parser.add_argument("--output-json", default="")
    parser.add_argument("--output-md", default="")
    args = parser.parse_args()

    work_dir = Path(args.work_dir) if args.work_dir else Path(".scratch/seekui")
    outputs = work_dir / "outputs"
    data = work_dir / "data"
    rows = [status_for(outputs, data, item) for item in build_items(args.limit, args.variants_per_example)]

    summary = {
        "work_dir": str(work_dir),
        "counts": {
            "done": sum(1 for row in rows if row["state"] == "done"),
            "pending": sum(1 for row in rows if row["state"] == "pending"),
        },
        "items": rows,
    }

    output_json = Path(args.output_json) if args.output_json else outputs / "followup_status.json"
    output_json.parent.mkdir(parents=True, exist_ok=True)
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    output_md = Path(args.output_md) if args.output_md else output_json.with_suffix(".md")
    write_markdown(output_md, work_dir, rows)

    print(json.dumps(summary["counts"], indent=2))
    print(f"Status JSON: {output_json}")
    print(f"Status MD  : {output_md}")
    first_pending = next((row for row in rows if row["state"] == "pending"), None)
    if first_pending:
        print(f"Next pending: {first_pending['id']} - {first_pending['title']}")
        print(f"Command     : {first_pending['command']}")


if __name__ == "__main__":
    main()
