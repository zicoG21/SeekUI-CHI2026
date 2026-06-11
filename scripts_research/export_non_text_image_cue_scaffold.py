#!/usr/bin/env python
import argparse
import csv
import json
from pathlib import Path


EXPERIMENTS = [
    {
        "id": "image_crop_proxy",
        "priority": "P0",
        "cue_type": "target_crop_image",
        "data_source": "existing present targets cropped from VSGUI10K",
        "input": "GUI screenshot + target crop",
        "output": "scanpath/status",
        "metric": "last-to-target distance, scanpath metrics, absent-status rate",
        "purpose": "Feasibility check for multimodal target cues without new annotation.",
        "risk": "Proxy remains text-derived; does not prove native non-text search.",
    },
    {
        "id": "icon_category_pilot",
        "priority": "P1",
        "cue_type": "category_text",
        "data_source": "manual 100-200 row icon/category pilot",
        "input": "GUI screenshot + category cue such as settings icon, profile picture, cart",
        "output": "scanpath/status",
        "metric": "hit rate, absent F1, error taxonomy",
        "purpose": "Test non-exact visual/semantic target search.",
        "risk": "Requires manual confirmation of valid targets.",
    },
    {
        "id": "functional_query_pilot",
        "priority": "P1",
        "cue_type": "functional_text",
        "data_source": "manual realistic GUI query pilot",
        "input": "GUI screenshot + functional query such as change language or recover password",
        "output": "scanpath/status",
        "metric": "grounding accuracy, ambiguity rate, absent F1",
        "purpose": "Separate exact text grounding from task/function understanding.",
        "risk": "Ambiguity can dominate unless annotation rules are strict.",
    },
    {
        "id": "non_text_absent_pilot",
        "priority": "P1",
        "cue_type": "icon_or_function_absent",
        "data_source": "manual real absent validation extension",
        "input": "GUI screenshot + non-text or functional absent cue",
        "output": "present/absent + scanpath",
        "metric": "absent precision/recall/F1",
        "purpose": "External-validity check for absent-aware non-text search.",
        "risk": "Small pilot only; needs balanced present/absent rows.",
    },
    {
        "id": "candidate_crop_vlm_verifier",
        "priority": "P2",
        "cue_type": "candidate_crop_verification",
        "data_source": "model predictions + candidate crops",
        "input": "target cue + candidate crop + optional full screenshot",
        "output": "candidate contains target yes/no",
        "metric": "verification accuracy, rescue rate, over-rejection rate",
        "purpose": "Replace brittle OCR-only evidence for icons and stylized UI targets.",
        "risk": "Requires reliable candidate proposal/cropping.",
    },
]


ANNOTATION_SCHEMA = {
    "row_id": "stable integer or UUID",
    "image": "relative screenshot path",
    "cue_type": "target_crop_image | category_text | functional_text | icon_or_function_absent",
    "query_text": "text cue when applicable",
    "query_image": "target crop path when applicable",
    "gold_status": "present | absent",
    "target_bbox": "x,y,w,h for present rows; empty for absent rows",
    "target_visible": "yes | no",
    "query_realistic": "yes | no",
    "ambiguity_level": "low | medium | high",
    "primary_target_modality": "text | icon | image | layout | function",
    "notes": "short reason for ambiguity/invalidity",
}


COMMANDS = [
    {
        "step": "Regenerate current image-cue proxy benchmark",
        "command": "bash scripts_research/run_offline_research_prep.sh",
    },
    {
        "step": "Summarize current image-cue proxy results",
        "command": "python scripts_research/summarize_research_outputs.py --work-dir \"$SEEKUI_WORK\" --output \"$SEEKUI_WORK/outputs/research_summary.md\" --tables-dir \"$SEEKUI_WORK/outputs/research_summary_tables\"",
    },
    {
        "step": "Create manual non-text annotation sheet",
        "command": "python scripts_research/export_non_text_image_cue_scaffold.py --out-dir paper_assets/non_text_image_cue_scaffold",
    },
]


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_md(out_dir):
    def esc(value):
        return str(value).replace("|", "&#124;")

    lines = [
        "# Non-Text and Image-Cue Experiment Scaffold",
        "",
        "This scaffold turns the non-text/image-cue direction into concrete experiments that can be run after the current absent-aware pipeline.",
        "",
        "## Experiment Matrix",
        "",
        "| ID | Priority | Cue Type | Data Source | Metric | Purpose | Risk |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in EXPERIMENTS:
        lines.append(
            f"| {esc(row['id'])} | {esc(row['priority'])} | {esc(row['cue_type'])} | {esc(row['data_source'])} | "
            f"{esc(row['metric'])} | {esc(row['purpose'])} | {esc(row['risk'])} |"
        )
    lines.extend([
        "",
        "## Annotation Schema",
        "",
        "| Field | Meaning |",
        "|---|---|",
    ])
    for key, value in ANNOTATION_SCHEMA.items():
        lines.append(f"| `{key}` | {esc(value)} |")
    lines.extend([
        "",
        "## Commands",
        "",
    ])
    for item in COMMANDS:
        lines.extend([f"### {item['step']}", "", "```bash", item["command"], "```", ""])
    lines.extend([
        "## Immediate Recommendation",
        "",
        "Use `image_crop_proxy` as the current feasibility result, then build a 100-200 row `icon_category_pilot` with balanced present/absent labels. Keep functional queries separate because ambiguity is higher.",
        "",
    ])
    (out_dir / "non_text_image_cue_scaffold.md").write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Export a concrete scaffold for non-text/image-cue follow-up experiments.")
    parser.add_argument("--out-dir", default="paper_assets/non_text_image_cue_scaffold")
    args = parser.parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(out_dir / "experiment_matrix.csv", EXPERIMENTS)
    write_json = {
        "experiments": EXPERIMENTS,
        "annotation_schema": ANNOTATION_SCHEMA,
        "commands": COMMANDS,
    }
    (out_dir / "experiment_matrix.json").write_text(json.dumps(write_json, indent=2), encoding="utf-8")
    (out_dir / "annotation_schema.json").write_text(json.dumps(ANNOTATION_SCHEMA, indent=2), encoding="utf-8")
    write_md(out_dir)
    print(json.dumps({
        "out_dir": str(out_dir),
        "experiments": len(EXPERIMENTS),
        "schema_fields": len(ANNOTATION_SCHEMA),
    }, indent=2))


if __name__ == "__main__":
    main()
