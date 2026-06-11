#!/usr/bin/env python
import argparse
import csv
import json
import shutil
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
from PIL import Image, ImageDraw, ImageFont


SOURCE_NOTE = "CHPC paper checkpoint and research notes, 2026-06-11"


MAIN_ROWS = [
    {
        "model": "SeekUI",
        "family": "seekui_prompt",
        "variant": "prompt_only",
        "n": 2724,
        "accuracy": 0.7684,
        "absent_precision": 0.8749,
        "absent_recall": 0.6263,
        "absent_f1": 0.7300,
        "present_to_absent": 122,
        "absent_to_present": 509,
    },
    {
        "model": "SeekUI",
        "family": "cognitive",
        "variant": "cognitive_stop_present_only",
        "n": 2724,
        "accuracy": 0.8414,
        "absent_precision": 0.7981,
        "absent_recall": 0.9141,
        "absent_f1": 0.8522,
        "present_to_absent": 315,
        "absent_to_present": 117,
    },
    {
        "model": "SeekUI",
        "family": "combined",
        "variant": "combined_and_present_only_best_f1",
        "n": 2724,
        "accuracy": 0.8711,
        "absent_precision": 0.8115,
        "absent_recall": 0.9670,
        "absent_f1": 0.8824,
        "present_to_absent": 306,
        "absent_to_present": 45,
    },
    {
        "model": "SeekUI",
        "family": "vlm_presence",
        "variant": "vlm_presence_direct",
        "n": 2724,
        "accuracy": 0.8510,
        "absent_precision": 0.9142,
        "absent_recall": 0.7746,
        "absent_f1": 0.8386,
        "present_to_absent": 99,
        "absent_to_present": 307,
    },
    {
        "model": "SeekUI",
        "family": "vlm_evidence",
        "variant": "vlm_evidence_evidence_aware",
        "n": 2724,
        "accuracy": 0.8891,
        "absent_precision": 0.8308,
        "absent_recall": 0.9772,
        "absent_f1": 0.8981,
        "present_to_absent": 271,
        "absent_to_present": 31,
    },
    {
        "model": "SeekUI_sft",
        "family": "seekui_prompt",
        "variant": "prompt_only",
        "n": 2724,
        "accuracy": 0.7430,
        "absent_precision": 0.8761,
        "absent_recall": 0.5661,
        "absent_f1": 0.6878,
        "present_to_absent": 109,
        "absent_to_present": 591,
    },
    {
        "model": "SeekUI_sft",
        "family": "combined",
        "variant": "combined_and_present_only_best_f1",
        "n": 2724,
        "accuracy": 0.8278,
        "absent_precision": 0.7853,
        "absent_recall": 0.9023,
        "absent_f1": 0.8398,
        "present_to_absent": 336,
        "absent_to_present": 133,
    },
]


REALISTIC_ROWS = [
    {
        "model": "SeekUI",
        "family": "seekui_prompt",
        "variant": "prompt_only_real_absent",
        "n": 100,
        "accuracy": 0.8200,
        "absent_precision": 0.9444,
        "absent_recall": 0.6800,
        "absent_f1": 0.7907,
        "present_to_absent": 2,
        "absent_to_present": 16,
    },
    {
        "model": "SeekUI",
        "family": "combined",
        "variant": "combined_and_present_only_best_f1",
        "n": 100,
        "accuracy": 0.9100,
        "absent_precision": 0.8596,
        "absent_recall": 0.9800,
        "absent_f1": 0.9159,
        "present_to_absent": 8,
        "absent_to_present": 1,
    },
    {
        "model": "SeekUI",
        "family": "combined",
        "variant": "combined_and_present_only",
        "n": 100,
        "accuracy": 0.8600,
        "absent_precision": 0.9091,
        "absent_recall": 0.8000,
        "absent_f1": 0.8511,
        "present_to_absent": 4,
        "absent_to_present": 10,
    },
    {
        "model": "SeekUI",
        "family": "vlm_presence",
        "variant": "vlm_presence_real_absent_conservative",
        "n": 100,
        "accuracy": 0.8800,
        "absent_precision": 0.8276,
        "absent_recall": 0.9600,
        "absent_f1": 0.8889,
        "present_to_absent": 10,
        "absent_to_present": 2,
    },
    {
        "model": "SeekUI",
        "family": "vlm_presence",
        "variant": "vlm_presence_real_absent_ocr_aware",
        "n": 100,
        "accuracy": 0.8800,
        "absent_precision": 0.8654,
        "absent_recall": 0.9000,
        "absent_f1": 0.8824,
        "present_to_absent": 7,
        "absent_to_present": 5,
    },
    {
        "model": "SeekUI",
        "family": "vlm_presence",
        "variant": "vlm_presence_real_absent_search_behavior",
        "n": 100,
        "accuracy": 0.8800,
        "absent_precision": 0.9130,
        "absent_recall": 0.8400,
        "absent_f1": 0.8750,
        "present_to_absent": 4,
        "absent_to_present": 8,
    },
    {
        "model": "SeekUI",
        "family": "vlm_presence",
        "variant": "vlm_presence_real_absent_direct",
        "n": 100,
        "accuracy": 0.8600,
        "absent_precision": 0.8913,
        "absent_recall": 0.8200,
        "absent_f1": 0.8542,
        "present_to_absent": 5,
        "absent_to_present": 9,
    },
]


HELDOUT_ROWS = [
    {
        "model": "SeekUI",
        "split": "image",
        "prompt_f1": 0.7347,
        "combined_f1": 0.8804,
        "delta_f1_ci": "[0.1167, 0.1739]",
        "prompt_accuracy": 0.7708,
        "combined_accuracy": 0.8692,
        "delta_accuracy_ci": "[0.0720, 0.1220]",
    },
    {
        "model": "SeekUI-SFT",
        "split": "image",
        "prompt_f1": 0.6744,
        "combined_f1": 0.8279,
        "delta_f1_ci": "[0.1232, 0.1834]",
        "prompt_accuracy": 0.7325,
        "combined_accuracy": 0.8148,
        "delta_accuracy_ci": "[0.0558, 0.1080]",
    },
]


TAXONOMY_ROWS = [
    {
        "model": "SeekUI + combined AND",
        "case_type": "Corrected absent false-present",
        "count": 464,
        "patterns": "weak-evidence forced-choice; no clear target match",
    },
    {
        "model": "SeekUI + combined AND",
        "case_type": "New present false-absent",
        "count": 184,
        "patterns": "small, edge, low-contrast, stylized, or cluttered targets",
    },
    {
        "model": "SeekUI + combined AND",
        "case_type": "Kept absent false-present",
        "count": 45,
        "patterns": "strong text/button/function distractors",
    },
    {
        "model": "SeekUI-SFT + combined AND",
        "case_type": "Corrected absent false-present",
        "count": 458,
        "patterns": "weak target evidence; short-path evidence absence",
    },
    {
        "model": "SeekUI-SFT + combined AND",
        "case_type": "New present false-absent",
        "count": 227,
        "patterns": "short/off-target paths; small or peripheral targets",
    },
    {
        "model": "SeekUI-SFT + combined AND",
        "case_type": "Kept absent false-present",
        "count": 133,
        "patterns": "strong distractors plus brittle evidence accumulation",
    },
]

METHOD_STRENGTH_ROWS = [
    {
        "method": "SeekUI prompt-only",
        "family": "base model",
        "synthetic_f1": 0.7300,
        "realistic_f1": 0.7907,
        "main_strength": "High absent precision; few present targets rejected.",
        "main_weakness": "Forced-choice absent errors remain common.",
        "recommended_role": "Baseline showing target-present assumption.",
    },
    {
        "method": "Cognitive stopping",
        "family": "scanpath evidence",
        "synthetic_f1": 0.8522,
        "realistic_f1": "",
        "main_strength": "Large absent-recall gain from path evidence.",
        "main_weakness": "Can over-reject present targets without OCR support.",
        "recommended_role": "Behaviorally motivated mechanism.",
    },
    {
        "method": "Combined AND best-F1",
        "family": "path + OCR rule",
        "synthetic_f1": 0.8824,
        "realistic_f1": 0.9159,
        "main_strength": "Best real-absent validation result; strong not-found safety.",
        "main_weakness": "Conservative threshold creates present false-absent errors.",
        "recommended_role": "Main interpretable practical method.",
    },
    {
        "method": "VLM yes/no direct",
        "family": "generic VLM",
        "synthetic_f1": 0.8386,
        "realistic_f1": 0.8542,
        "main_strength": "Strong simple reviewer-risk baseline.",
        "main_weakness": "Still misses many absent cases on synthetic benchmark.",
        "recommended_role": "Simple baseline to rule out trivial prompting.",
    },
    {
        "method": "VLM yes/no OCR-aware",
        "family": "generic VLM",
        "synthetic_f1": 0.8939,
        "realistic_f1": 0.8824,
        "main_strength": "Best generic prompt on synthetic benchmark.",
        "main_weakness": "Prompt-sensitive and not scanpath-grounded.",
        "recommended_role": "Strong VLM baseline.",
    },
    {
        "method": "Evidence-aware VLM",
        "family": "screenshot + evidence VLM",
        "synthetic_f1": 0.8981,
        "realistic_f1": "",
        "main_strength": "Best practical synthetic result; combines VLM with evidence.",
        "main_weakness": "Needs real-absent evidence-aware validation before headline.",
        "recommended_role": "Promising next-stage verifier.",
    },
]


CASE_SHEETS = [
    (
        "A. Corrected absent false-present",
        "Weak-evidence forced-choice predictions rejected as absent",
        "SeekUI_and_corrected_absent_false_present_contact_sheet.jpg",
    ),
    (
        "B. New present false-absent",
        "Small, edge, low-contrast, or cluttered present targets over-rejected",
        "SeekUI_and_new_present_false_absent_contact_sheet.jpg",
    ),
    (
        "C. Kept absent false-present",
        "Residual absent errors with strong text or functional distractors",
        "SeekUI_and_kept_absent_false_present_contact_sheet.jpg",
    ),
]


def fmt(value):
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def latex_escape(value):
    return str(value).replace("_", "\\_").replace("%", "\\%").replace("&", "\\&")


def ensure_dirs(out_dir):
    for name in ["tables", "figures", "figures/case_sources", "manifest"]:
        (out_dir / name).mkdir(parents=True, exist_ok=True)


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys()) if rows else []
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_md_table(path, title, rows, columns, note=None):
    text_columns = {
        "model",
        "family",
        "variant",
        "split",
        "case_type",
        "patterns",
        "method",
        "main_strength",
        "main_weakness",
        "recommended_role",
    }
    lines = [f"# {title}", ""]
    if note:
        lines.extend([note, ""])
    lines.append("| " + " | ".join(label for _, label in columns) + " |")
    lines.append("|" + "|".join("---" if key in text_columns else "---:" for key, _ in columns) + "|")
    for row in rows:
        values = [fmt(row.get(key, "")) for key, _ in columns]
        lines.append("| " + " | ".join(values) + " |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_latex_table(path, rows, columns, caption, label):
    text_columns = {
        "model",
        "family",
        "variant",
        "split",
        "case_type",
        "patterns",
        "method",
        "main_strength",
        "main_weakness",
        "recommended_role",
    }
    colspec = "".join("l" if key in text_columns else "r" for key, _ in columns)
    lines = [
        "\\begin{table}[t]",
        "\\centering",
        "\\small",
        "\\begin{tabular}{" + colspec + "}",
        "\\toprule",
        " & ".join(latex_escape(label) for _, label in columns) + " \\\\",
        "\\midrule",
    ]
    for row in rows:
        lines.append(" & ".join(latex_escape(fmt(row.get(key, ""))) for key, _ in columns) + " \\\\")
    lines.extend([
        "\\bottomrule",
        "\\end{tabular}",
        f"\\caption{{{latex_escape(caption)}}}",
        f"\\label{{{label}}}",
        "\\end{table}",
        "",
    ])
    path.write_text("\n".join(lines), encoding="utf-8")


def export_tables(out_dir):
    table_specs = [
        (
            "main_results",
            "Main Present/Absent Results",
            MAIN_ROWS,
            [
                ("model", "Model"),
                ("family", "Family"),
                ("variant", "Variant"),
                ("n", "N"),
                ("accuracy", "Acc"),
                ("absent_precision", "Precision"),
                ("absent_recall", "Recall"),
                ("absent_f1", "F1"),
                ("present_to_absent", "Present->Absent"),
                ("absent_to_present", "Absent->Present"),
            ],
            "Full synthetic present/absent benchmark. Rows emphasize practical baselines and verifier variants.",
        ),
        (
            "realistic_absent_validation",
            "Realistic Absent Validation",
            REALISTIC_ROWS,
            [
                ("model", "Model"),
                ("family", "Family"),
                ("variant", "Variant"),
                ("n", "N"),
                ("accuracy", "Acc"),
                ("absent_precision", "Precision"),
                ("absent_recall", "Recall"),
                ("absent_f1", "F1"),
                ("present_to_absent", "Present->Absent"),
                ("absent_to_present", "Absent->Present"),
            ],
            "Small manually reviewed external-validity check with 50 present and 50 realistic absent examples.",
        ),
        (
            "heldout_image_split",
            "Held-Out Image Split Result",
            HELDOUT_ROWS,
            [
                ("model", "Model"),
                ("split", "Split"),
                ("prompt_f1", "Prompt F1"),
                ("combined_f1", "Combined F1"),
                ("delta_f1_ci", "Delta F1 95% CI"),
                ("prompt_accuracy", "Prompt Acc"),
                ("combined_accuracy", "Combined Acc"),
                ("delta_accuracy_ci", "Delta Acc 95% CI"),
            ],
            "Image split is the cleaner headline because it avoids shared images across dev/test.",
        ),
        (
            "error_taxonomy_counts",
            "Error Taxonomy Counts",
            TAXONOMY_ROWS,
            [
                ("model", "Model"),
                ("case_type", "Case Type"),
                ("count", "Count"),
                ("patterns", "Dominant Patterns"),
            ],
            "Counts come from mined combined-verifier cases; patterns come from local contact-sheet review.",
        ),
        (
            "method_strength_summary",
            "Method Strength Summary",
            METHOD_STRENGTH_ROWS,
            [
                ("method", "Method"),
                ("family", "Family"),
                ("synthetic_f1", "Synthetic F1"),
                ("realistic_f1", "Realistic F1"),
                ("main_strength", "Main Strength"),
                ("main_weakness", "Main Weakness"),
                ("recommended_role", "Recommended Role"),
            ],
            "Compact narrative table for choosing the paper's main method and baselines.",
        ),
    ]
    generated = []
    for stem, title, rows, columns, note in table_specs:
        csv_path = out_dir / "tables" / f"{stem}.csv"
        md_path = out_dir / "tables" / f"{stem}.md"
        tex_path = out_dir / "tables" / f"{stem}.tex"
        write_csv(csv_path, rows)
        write_md_table(md_path, title, rows, columns, note)
        write_latex_table(tex_path, rows, columns, title, f"tab:{stem}")
        generated.extend([csv_path, md_path, tex_path])
    return generated


def strip_trailing_whitespace(path):
    text = path.read_text(encoding="utf-8")
    cleaned = "\n".join(line.rstrip() for line in text.splitlines()) + "\n"
    path.write_text(cleaned, encoding="utf-8")


def add_box(ax, xy, width, height, text, facecolor, edgecolor="#333333"):
    box = FancyBboxPatch(
        xy,
        width,
        height,
        boxstyle="round,pad=0.02,rounding_size=0.025",
        linewidth=1.4,
        edgecolor=edgecolor,
        facecolor=facecolor,
    )
    ax.add_patch(box)
    ax.text(
        xy[0] + width / 2,
        xy[1] + height / 2,
        text,
        ha="center",
        va="center",
        fontsize=10,
        color="#111111",
        wrap=True,
    )


def export_method_diagram(out_dir):
    fig, ax = plt.subplots(figsize=(13.5, 5.2))
    ax.set_xlim(0, 1.12)
    ax.set_ylim(0, 1)
    ax.axis("off")
    boxes = [
        ((0.02, 0.60), 0.15, 0.22, "GUI screenshot\n+\ntarget cue", "#e8f4f8"),
        ((0.22, 0.60), 0.15, 0.22, "SeekUI\nscanpath + status", "#eef0ff"),
        ((0.43, 0.73), 0.16, 0.18, "Cognitive\npath evidence", "#f4f0ff"),
        ((0.43, 0.45), 0.16, 0.18, "OCR candidate\nevidence", "#fff2df"),
        ((0.65, 0.60), 0.13, 0.22, "Combined AND\nstopping rule", "#eaf7ea"),
        ((0.82, 0.60), 0.13, 0.22, "Evidence-aware\nVLM verifier", "#edf2ff"),
        ((0.99, 0.60), 0.10, 0.22, "Present\nscanpath\nor absent", "#f7eeee"),
    ]
    for xy, width, height, text, color in boxes:
        add_box(ax, xy, width, height, text, color)
    arrows = [
        ((0.17, 0.71), (0.22, 0.71)),
        ((0.37, 0.71), (0.43, 0.81)),
        ((0.37, 0.71), (0.43, 0.54)),
        ((0.59, 0.81), (0.65, 0.73)),
        ((0.59, 0.54), (0.65, 0.67)),
        ((0.78, 0.71), (0.82, 0.71)),
        ((0.95, 0.71), (0.99, 0.71)),
    ]
    for start, end in arrows:
        ax.annotate("", xy=end, xytext=start, arrowprops={"arrowstyle": "->", "lw": 1.6, "color": "#333333"})
    ax.text(0.5, 0.25, "The verifier can inspect the screenshot plus path/OCR evidence, keeping not-found safety while rescuing visible targets.", ha="center", fontsize=11)
    ax.text(0.5, 0.13, "Key idea: convert forced-choice GUI grounding into uncertainty-aware target search without retraining SeekUI.", ha="center", fontsize=11, weight="bold")

    png_path = out_dir / "figures" / "method_diagram.png"
    svg_path = out_dir / "figures" / "method_diagram.svg"
    fig.savefig(png_path, dpi=220, bbox_inches="tight")
    fig.savefig(svg_path, bbox_inches="tight")
    plt.close(fig)
    strip_trailing_whitespace(svg_path)
    caption = (
        "# Method Diagram Caption\n\n"
        "Post-hoc target-presence verification for GUI visual search. SeekUI first produces a scanpath and status. "
        "A cognitive stopping layer computes path evidence, OCR supplies candidate evidence, and a combined stopping rule "
        "or evidence-aware VLM turns forced-choice predictions into present/absent decisions.\n"
    )
    caption_path = out_dir / "figures" / "method_diagram_caption.md"
    caption_path.write_text(caption, encoding="utf-8")
    return [png_path, svg_path, caption_path]


def find_case_sheet(case_root, filename):
    matches = list(case_root.glob(f"**/{filename}"))
    if matches:
        return matches[0]
    return None


def load_font(size):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def export_case_figure(out_dir, case_root):
    target_width = 1500
    header_h = 120
    gap = 28
    panels = []
    compact_panels = []
    generated = []
    for title, subtitle, filename in CASE_SHEETS:
        src = find_case_sheet(case_root, filename)
        if src is None:
            panel = Image.new("RGB", (target_width, 420), "#f5f5f5")
            draw = ImageDraw.Draw(panel)
            draw.text((32, 32), f"Missing source: {filename}", fill="#222222", font=load_font(30))
        else:
            source_copy = out_dir / "figures" / "case_sources" / filename
            shutil.copy2(src, source_copy)
            generated.append(source_copy)
            image = Image.open(src).convert("RGB")
            scale = target_width / image.width
            sheet_h = int(image.height * scale)
            resized = image.resize((target_width, sheet_h), Image.Resampling.LANCZOS)
            panel = Image.new("RGB", (target_width, header_h + sheet_h), "white")
            draw = ImageDraw.Draw(panel)
            draw.text((18, 14), title, fill="#111111", font=load_font(38))
            draw.text((20, 62), subtitle, fill="#333333", font=load_font(24))
            panel.paste(resized, (0, header_h))

            compact_crop = image.crop((0, 0, image.width, min(image.height, 940)))
            compact_h = int(compact_crop.height * scale)
            compact_resized = compact_crop.resize((target_width, compact_h), Image.Resampling.LANCZOS)
            compact = Image.new("RGB", (target_width, header_h + compact_h), "white")
            compact_draw = ImageDraw.Draw(compact)
            compact_draw.text((18, 14), title, fill="#111111", font=load_font(38))
            compact_draw.text((20, 62), subtitle, fill="#333333", font=load_font(24))
            compact.paste(compact_resized, (0, header_h))
            compact_panels.append(compact)
        panels.append(panel)

    def stack(panels_to_stack):
        total_h = sum(p.height for p in panels_to_stack) + gap * (len(panels_to_stack) - 1)
        canvas = Image.new("RGB", (target_width, total_h), "white")
        y = 0
        for panel in panels_to_stack:
            canvas.paste(panel, (0, y))
            y += panel.height + gap
        return canvas

    canvas = stack(panels)
    compact_canvas = stack(compact_panels or panels)
    jpg_path = out_dir / "figures" / "case_taxonomy_contact_sheet.jpg"
    png_path = out_dir / "figures" / "case_taxonomy_contact_sheet.png"
    compact_jpg_path = out_dir / "figures" / "case_taxonomy_compact.jpg"
    compact_png_path = out_dir / "figures" / "case_taxonomy_compact.png"
    canvas.save(jpg_path, quality=92)
    canvas.save(png_path)
    compact_canvas.save(compact_jpg_path, quality=92)
    compact_canvas.save(compact_png_path)
    caption = (
        "# Case Taxonomy Figure Caption\n\n"
        "Representative mined contact sheets for the combined AND verifier on SeekUI. "
        "Corrected absent false-present cases show weak-evidence forced-choice behavior, "
        "new present false-absent cases show conservative over-rejection of difficult visible targets, "
        "and kept absent false-present cases contain stronger distractors.\n"
    )
    caption_path = out_dir / "figures" / "case_taxonomy_caption.md"
    caption_path.write_text(caption, encoding="utf-8")
    generated.extend([jpg_path, png_path, compact_jpg_path, compact_png_path, caption_path])
    return generated


def export_error_taxonomy_figure(out_dir):
    case_types = [
        "Corrected absent\nfalse-present",
        "New present\nfalse-absent",
        "Kept absent\nfalse-present",
    ]
    seekui = [464, 184, 45]
    sft = [458, 227, 133]
    x = range(len(case_types))
    width = 0.36
    fig, ax = plt.subplots(figsize=(9.5, 5.2))
    ax.bar([i - width / 2 for i in x], seekui, width, label="SeekUI + combined AND", color="#3b82a0")
    ax.bar([i + width / 2 for i in x], sft, width, label="SeekUI-SFT + combined AND", color="#d0843f")
    ax.set_xticks(list(x))
    ax.set_xticklabels(case_types)
    ax.set_ylabel("Mined case count")
    ax.set_title("Combined-Verifier Error Taxonomy")
    ax.legend(frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    for offset, vals in [(-width / 2, seekui), (width / 2, sft)]:
        for i, val in enumerate(vals):
            ax.text(i + offset, val + 8, str(val), ha="center", va="bottom", fontsize=10)
    ax.text(
        0.02,
        -0.23,
        "Qualitative pattern: corrections remove weak forced-choice errors; residual false-present cases have stronger distractors;\n"
        "new false-absent cases concentrate on small, peripheral, low-contrast, or cluttered present targets.",
        transform=ax.transAxes,
        fontsize=10,
    )
    fig.tight_layout()
    png_path = out_dir / "figures" / "error_taxonomy.png"
    svg_path = out_dir / "figures" / "error_taxonomy.svg"
    fig.savefig(png_path, dpi=220, bbox_inches="tight")
    fig.savefig(svg_path, bbox_inches="tight")
    plt.close(fig)
    strip_trailing_whitespace(svg_path)
    caption_path = out_dir / "figures" / "error_taxonomy_caption.md"
    caption_path.write_text(
        "# Error Taxonomy Figure Caption\n\n"
        "Mined case counts for the combined AND verifier. The method corrects hundreds of absent false-present errors, "
        "but introduces present false-absent errors and leaves a smaller set of difficult absent false-present residuals.\n",
        encoding="utf-8",
    )
    return [png_path, svg_path, caption_path]


def export_manifest(out_dir, generated):
    lines = [
        "# Paper Assets Manifest",
        "",
        f"Source note: {SOURCE_NOTE}",
        "",
        "## Generated Assets",
        "",
    ]
    for path in sorted(generated):
        rel = path.relative_to(out_dir)
        lines.append(f"- `{rel}`")
    lines.extend([
        "",
        "## Recommended Use",
        "",
        "- `tables/main_results.*`: full synthetic present/absent benchmark baselines and verifier variants.",
        "- `tables/heldout_image_split.*`: cleaner image-split headline result with bootstrap confidence intervals.",
        "- `tables/realistic_absent_validation.*`: small manually reviewed external-validity check.",
        "- `tables/method_strength_summary.*`: compact story table comparing strengths, weaknesses, and paper role.",
        "- `figures/method_diagram.*`: method overview.",
        "- `figures/case_taxonomy_contact_sheet.*`: qualitative case figure from local contact sheets.",
        "- `figures/case_taxonomy_compact.*`: compact qualitative case figure for paper body.",
        "- `figures/error_taxonomy.*`: mined case-count taxonomy figure.",
        "",
        "## Caveat",
        "",
        "Candidate-verifier rows with F1 around 0.95 are diagnostic/oracle-like because they rely on candidate similarity evidence; "
        "the practical paper headline should use combined AND and evidence-aware VLM rows unless the candidate evidence is fully justified.",
        "",
    ])
    manifest = out_dir / "manifest" / "paper_assets_manifest.md"
    manifest.write_text("\n".join(lines), encoding="utf-8")
    json_path = out_dir / "manifest" / "paper_assets_manifest.json"
    json_path.write_text(json.dumps({"source_note": SOURCE_NOTE, "assets": [str(p.relative_to(out_dir)) for p in sorted(generated)]}, indent=2), encoding="utf-8")
    return [manifest, json_path]


def main():
    parser = argparse.ArgumentParser(description="Export paper-ready tables and figures for SeekUI follow-up results.")
    parser.add_argument("--out-dir", default="paper_assets")
    parser.add_argument("--case-root", default="/home/perzival/HCI_Research/seekui_combined_cases")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    case_root = Path(args.case_root)
    ensure_dirs(out_dir)

    generated = []
    generated.extend(export_tables(out_dir))
    generated.extend(export_method_diagram(out_dir))
    generated.extend(export_case_figure(out_dir, case_root))
    generated.extend(export_error_taxonomy_figure(out_dir))
    generated.extend(export_manifest(out_dir, generated))

    print(json.dumps({
        "out_dir": str(out_dir),
        "num_assets": len(generated),
        "manifest": str(out_dir / "manifest" / "paper_assets_manifest.md"),
    }, indent=2))


if __name__ == "__main__":
    main()
