#!/usr/bin/env python
import argparse
import csv
import json
import shutil
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


PANEL_SPECS = [
    {
        "panel": "A",
        "title": "Forced-choice fixed",
        "split": "native_v2_main_text_balanced",
        "role": "recommended",
        "case_type": "forced_choice_fixed",
        "reading": "Prompt-only grounds a missing target; the verifier reports absent.",
    },
    {
        "panel": "B",
        "title": "Conservative cost",
        "split": "native_v2_main_text_balanced",
        "role": "recommended",
        "case_type": "method_overreject_present",
        "reading": "The verifier rejects a visible target, showing the present-target cost.",
    },
    {
        "panel": "C",
        "title": "Unresolved color/instance",
        "split": "native_v2_color_instance_balanced",
        "role": "recommended",
        "case_type": "forced_choice_kept",
        "reading": "Native labels can require color/instance matching rather than simple text absence.",
    },
]


def read_csv(path):
    if not path.exists():
        return []
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
    if not fieldnames:
        fieldnames = ["empty"]
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def load_font(size):
    for path in [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    ]:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def resolve_image(data_dir, image):
    data_dir = Path(data_dir)
    image = str(image or "")
    candidates = [
        data_dir / image,
        data_dir / "vsgui10k-images" / Path(image).name,
    ]
    stem = Path(image).stem
    for ext in [".png", ".jpg", ".jpeg"]:
        if stem:
            candidates.append(data_dir / "vsgui10k-images" / f"{stem}{ext}")
    for path in candidates:
        if path.exists():
            return path
    if stem:
        for ext in [".png", ".jpg", ".jpeg"]:
            matches = list((data_dir / "vsgui10k-images").glob(f"{stem}{ext}"))
            if matches:
                return matches[0]
    return None


def score_row(row):
    case_type = row.get("case_type", "")
    visibility = safe_float(row.get("text_visibility_score"))
    target_len = len(row.get("target", ""))
    if case_type == "forced_choice_fixed":
        # Prefer clean absent examples with weak OCR visibility and readable targets.
        return (row.get("visibility_bucket") == "weak_or_distractor_ocr_match", -visibility, target_len)
    if case_type == "method_overreject_present":
        # Prefer plausible visible targets where text visibility is not trivially zero.
        return (visibility > 0.25, visibility, target_len)
    if case_type == "forced_choice_kept":
        # Prefer clear color/instance conflicts.
        return (row.get("visibility_bucket") == "color_ignored_exact_text_visible", visibility, target_len)
    return (0, visibility, target_len)


def first_nonempty(row, fields):
    for field in fields:
        value = str(row.get(field, "")).strip()
        if value:
            return value
    return ""


def image_key(row):
    value = first_nonempty(row, ["image", "screenshot", "img", "image_path", "resolved_image", "figure_image"])
    if not value:
        return ""
    return Path(value).stem.casefold()


def target_key(row):
    value = first_nonempty(row, ["target", "query_text", "target_text", "target_cue", "cue"])
    return value.casefold()


def image_target_key(row):
    return (image_key(row), target_key(row))


def select_rows(rows, limit):
    sorted_rows = sorted(rows, key=score_row, reverse=True)
    selected = []
    seen_image_target = set()
    seen_images = set()

    # First pass: maximize visual variety by requiring a unique screenshot.
    for row in sorted_rows:
        row_image_key = image_key(row)
        row_image_target_key = image_target_key(row)
        if row_image_target_key in seen_image_target or row_image_key in seen_images:
            continue
        selected.append(row)
        seen_image_target.add(row_image_target_key)
        seen_images.add(row_image_key)
        if len(selected) >= limit:
            return selected

    # Second pass: allow a repeated screenshot only if the target differs.
    seen_targets = {target_key(row) for row in selected}
    for row in sorted_rows:
        row_image_target_key = image_target_key(row)
        row_target_key = target_key(row)
        if row_image_target_key in seen_image_target or row_target_key in seen_targets:
            continue
        selected.append(row)
        seen_image_target.add(row_image_target_key)
        seen_targets.add(row_target_key)
        if len(selected) >= limit:
            return selected

    # Last pass: fill with any remaining non-identical screenshot-target pair.
    for row in sorted_rows:
        row_image_target_key = image_target_key(row)
        if row_image_target_key in seen_image_target:
            continue
        selected.append(row)
        seen_image_target.add(row_image_target_key)
        if len(selected) >= limit:
            break
    return selected


def case_csv(case_root, spec):
    return Path(case_root) / spec["split"] / spec["role"] / f"{spec['case_type']}.csv"


def copy_images(rows, data_dir, out_dir, panel):
    copied = []
    image_dir = out_dir / "images"
    image_dir.mkdir(parents=True, exist_ok=True)
    for old in image_dir.glob(f"{panel}_*"):
        if old.is_file():
            old.unlink()
    for idx, row in enumerate(rows):
        src = resolve_image(data_dir, row.get("image", ""))
        out_row = dict(row)
        out_row["panel"] = panel
        out_row["dedupe_image_key"] = image_key(row)
        out_row["dedupe_target_key"] = target_key(row)
        out_row["resolved_image"] = str(src) if src else ""
        out_row["figure_image"] = ""
        if src:
            dst = image_dir / f"{panel}_{idx:02d}_{Path(src).name}"
            shutil.copy2(src, dst)
            out_row["figure_image"] = str(dst)
        copied.append(out_row)
    return copied


def wrap(draw, text, font, width):
    if not text:
        return [""]
    chars_per_line = max(18, width // max(7, font.size // 2))
    return textwrap.wrap(str(text), width=chars_per_line)[:4]


def draw_card(canvas, draw, xy, size, row, title_font, body_font):
    x, y = xy
    w, h = size
    draw.rectangle((x, y, x + w, y + h), fill=(255, 255, 255), outline=(190, 190, 190), width=2)
    image_path = row.get("figure_image", "")
    image_h = int(h * 0.62)
    if image_path and Path(image_path).exists():
        img = Image.open(image_path).convert("RGB")
        img.thumbnail((w - 24, image_h - 18))
        ix = x + (w - img.width) // 2
        iy = y + 10
        draw.rectangle((x + 10, y + 10, x + w - 10, y + image_h), fill=(244, 244, 244))
        canvas.paste(img, (ix, iy))
    else:
        draw.rectangle((x + 10, y + 10, x + w - 10, y + image_h), fill=(238, 238, 238))
        draw.text((x + 18, y + 24), "image missing", fill=(90, 90, 90), font=body_font)

    ty = y + image_h + 10
    lines = [
        f"Target: {row.get('target', '')}",
        f"Gold: {row.get('gold_status', '')} | Prompt: {row.get('prompt_status', '')} | Method: {row.get('method_status', '')}",
        f"Bucket: {row.get('visibility_bucket', '')}",
    ]
    for line in lines:
        for wrapped in wrap(draw, line, body_font, w - 24):
            draw.text((x + 12, ty), wrapped, fill=(30, 30, 30), font=body_font)
            ty += body_font.size + 6


def make_contact_sheet(panel_rows, out_path, title):
    title_font = load_font(24)
    label_font = load_font(18)
    body_font = load_font(14)
    card_w, card_h = 360, 360
    gap = 18
    panels = len(panel_rows)
    rows_per_panel = max(len(rows) for rows in panel_rows.values()) if panel_rows else 0
    width = panels * card_w + (panels + 1) * gap
    height = 86 + rows_per_panel * (card_h + gap) + gap
    canvas = Image.new("RGB", (width, height), (246, 246, 246))
    draw = ImageDraw.Draw(canvas)
    draw.text((gap, 18), title, fill=(20, 20, 20), font=title_font)

    for panel_idx, (panel, rows) in enumerate(panel_rows.items()):
        x = gap + panel_idx * (card_w + gap)
        draw.text((x, 58), f"Panel {panel}", fill=(40, 40, 40), font=label_font)
        for row_idx, row in enumerate(rows):
            y = 86 + row_idx * (card_h + gap)
            draw_card(canvas, draw, (x, y), (card_w, card_h), row, label_font, body_font)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path, quality=92)


def write_md(path, selected, contact_sheet):
    def md_cell(value):
        return str(value or "").replace("|", "\\|").replace("\n", " ")

    lines = [
        "# Native VSGUI10K v2 Main-Figure Candidates",
        "",
        f"- Contact sheet: `{contact_sheet}`",
        "",
        "| Panel | Case Type | Split | Method | Target | Gold | Prompt | Method | Visibility Bucket | Figure Image |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for row in selected:
        lines.append(
            f"| {md_cell(row['panel'])} | {md_cell(row['case_type'])} | {md_cell(row['split'])} | "
            f"{md_cell(row['method'])} | {md_cell(row.get('target', ''))} | "
            f"{md_cell(row.get('gold_status', ''))} | {md_cell(row.get('prompt_status', ''))} | "
            f"{md_cell(row.get('method_status', ''))} | {md_cell(row.get('visibility_bucket', ''))} | "
            f"{md_cell(row.get('figure_image', ''))} |"
        )
    lines.extend([
        "",
        "## Suggested Caption",
        "",
        "Native VSGUI10K reproduces forced-choice grounding outside the synthetic absent benchmark. "
        "The verifier can reject missing targets that prompt-only SeekUI grounds, but it can also "
        "over-reject visible targets. Color/instance rows reveal a harder target-definition problem "
        "where visible text may be present but the requested color or instance is not.",
        "",
    ])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Export native v2 main-figure candidate images and contact sheet.")
    parser.add_argument("--case-root", required=True)
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--per-panel", type=int, default=3)
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    selected = []
    panel_rows = {}
    for spec in PANEL_SPECS:
        rows = read_csv(case_csv(args.case_root, spec))
        picked = select_rows(rows, args.per_panel)
        copied = copy_images(picked, args.data_dir, out_dir, spec["panel"])
        for row in copied:
            row.update({
                "panel_title": spec["title"],
                "panel_reading": spec["reading"],
                "split": spec["split"],
            })
        selected.extend(copied)
        panel_rows[spec["panel"]] = copied

    contact_sheet = out_dir / "native_v2_main_figure_candidates.jpg"
    make_contact_sheet(panel_rows, contact_sheet, "Native VSGUI10K v2 qualitative candidates")
    write_csv(out_dir / "native_v2_main_figure_candidates.csv", selected)
    write_json(out_dir / "native_v2_main_figure_candidates.json", selected)
    write_md(out_dir / "native_v2_main_figure_candidates.md", selected, contact_sheet)
    print(json.dumps({
        "selected": len(selected),
        "contact_sheet": str(contact_sheet),
        "summary_md": str(out_dir / "native_v2_main_figure_candidates.md"),
    }, indent=2))


if __name__ == "__main__":
    main()
