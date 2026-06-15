#!/usr/bin/env python
import argparse
import csv
import json
import shutil
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


PANEL_TITLES = {
    "A": "Forced-choice fixed",
    "B": "Conservative cost",
    "C": "Color/instance ambiguity",
}


PANEL_SUMMARIES = {
    "A": "Prompt-only grounds a missing target; the verifier reports absent.",
    "B": "The verifier rejects a visible target, exposing the safety/recall tradeoff.",
    "C": "Visible text can remain while the requested color or instance is absent.",
}


def read_csv(path):
    with open(path, "r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


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


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_font(size, bold=False):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def clean_text(value):
    return str(value or "").replace("\n", " ").strip()


def md_cell(value):
    return clean_text(value).replace("|", "\\|")


def wrap_lines(text, width):
    return textwrap.wrap(clean_text(text), width=width) or [""]


def crop_to_aspect(image, aspect):
    width, height = image.size
    current = width / height
    if current > aspect:
        new_w = int(height * aspect)
        left = (width - new_w) // 2
        return image.crop((left, 0, left + new_w, height))
    new_h = int(width / aspect)
    top = max(0, (height - new_h) // 2)
    return image.crop((0, top, width, top + new_h))


def select_one_per_panel(rows):
    selected = []
    seen = set()
    for row in rows:
        panel = clean_text(row.get("panel"))
        if panel and panel not in seen:
            selected.append(dict(row))
            seen.add(panel)
    return sorted(selected, key=lambda row: clean_text(row.get("panel")))


def copy_selected_images(rows, out_dir):
    image_dir = out_dir / "images"
    image_dir.mkdir(parents=True, exist_ok=True)
    copied = []
    for row in rows:
        out_row = dict(row)
        src = Path(clean_text(row.get("figure_image")))
        out_row["main_figure_image"] = ""
        if src.exists():
            dst = image_dir / f"{clean_text(row.get('panel'))}_{src.name}"
            shutil.copy2(src, dst)
            out_row["main_figure_image"] = str(dst)
        copied.append(out_row)
    return copied


def draw_wrapped(draw, xy, text, font, fill, width, line_gap=5, max_lines=None):
    x, y = xy
    lines = []
    for line in wrap_lines(text, width):
        lines.append(line)
    if max_lines is not None:
        lines = lines[:max_lines]
    for line in lines:
        draw.text((x, y), line, fill=fill, font=font)
        y += font.size + line_gap
    return y


def draw_panel(canvas, draw, row, x, y, w, h, fonts):
    panel = clean_text(row.get("panel"))
    title = PANEL_TITLES.get(panel, clean_text(row.get("case_type")))
    summary = PANEL_SUMMARIES.get(panel, clean_text(row.get("panel_reading")))

    draw.rounded_rectangle((x, y, x + w, y + h), radius=10, fill="white", outline=(198, 204, 211), width=2)
    draw.text((x + 18, y + 16), f"{panel}. {title}", fill=(18, 24, 38), font=fonts["title"])
    draw_wrapped(draw, (x + 18, y + 50), summary, fonts["small"], (60, 67, 80), 44, max_lines=2)

    image_top = y + 105
    image_h = int(h * 0.52)
    image_box = (x + 16, image_top, x + w - 16, image_top + image_h)
    draw.rectangle(image_box, fill=(241, 243, 245), outline=(220, 224, 229))

    image_path = Path(clean_text(row.get("main_figure_image") or row.get("figure_image")))
    if image_path.exists():
        img = Image.open(image_path).convert("RGB")
        img = crop_to_aspect(img, (w - 32) / image_h)
        img = img.resize((w - 32, image_h), Image.Resampling.LANCZOS)
        canvas.paste(img, (x + 16, image_top))
    else:
        draw.text((x + 30, image_top + 24), "image missing", fill=(90, 90, 90), font=fonts["body"])

    meta_y = image_top + image_h + 18
    target = clean_text(row.get("target"))
    status = (
        f"Gold: {clean_text(row.get('gold_status'))}  |  "
        f"Prompt: {clean_text(row.get('prompt_status'))}  |  "
        f"Method: {clean_text(row.get('method_status'))}"
    )
    bucket = f"Evidence bucket: {clean_text(row.get('visibility_bucket'))}"
    split = f"Split/method: {clean_text(row.get('split'))} / {clean_text(row.get('method'))}"

    meta_y = draw_wrapped(draw, (x + 18, meta_y), f"Target: {target}", fonts["body_bold"], (20, 25, 35), 42, max_lines=2)
    meta_y += 3
    meta_y = draw_wrapped(draw, (x + 18, meta_y), status, fonts["body"], (33, 42, 55), 48, max_lines=2)
    meta_y += 3
    meta_y = draw_wrapped(draw, (x + 18, meta_y), bucket, fonts["small"], (77, 86, 102), 50, max_lines=2)
    draw_wrapped(draw, (x + 18, meta_y + 3), split, fonts["small"], (77, 86, 102), 50, max_lines=2)


def make_figure(rows, out_path):
    fonts = {
        "suptitle": load_font(30, bold=True),
        "title": load_font(20, bold=True),
        "body_bold": load_font(16, bold=True),
        "body": load_font(15),
        "small": load_font(13),
    }
    panel_w, panel_h = 430, 610
    gap = 24
    margin = 32
    header_h = 70
    width = margin * 2 + panel_w * len(rows) + gap * (len(rows) - 1)
    height = margin + header_h + panel_h + margin
    canvas = Image.new("RGB", (width, height), (248, 249, 251))
    draw = ImageDraw.Draw(canvas)
    draw.text((margin, 24), "Native VSGUI10K target-absence cases", fill=(16, 24, 39), font=fonts["suptitle"])
    draw.text(
        (margin, 58),
        "Three readable cases from the processed native benchmark: correction, cost, and unresolved target definition.",
        fill=(71, 82, 98),
        font=fonts["body"],
    )
    y = margin + header_h
    for idx, row in enumerate(rows):
        x = margin + idx * (panel_w + gap)
        draw_panel(canvas, draw, row, x, y, panel_w, panel_h, fonts)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path)
    jpg_path = out_path.with_suffix(".jpg")
    canvas.save(jpg_path, quality=94)
    return jpg_path


def write_md(path, rows, png_path, jpg_path):
    lines = [
        "# Native VSGUI10K v2 Main Figure",
        "",
        f"- PNG: `{png_path}`",
        f"- JPG: `{jpg_path}`",
        "",
        "| Panel | Case Type | Target | Gold | Prompt | Method | Reading |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        panel = clean_text(row.get("panel"))
        reading = PANEL_SUMMARIES.get(panel, clean_text(row.get("panel_reading")))
        lines.append(
            f"| {md_cell(panel)} | {md_cell(row.get('case_type'))} | {md_cell(row.get('target'))} | "
            f"{md_cell(row.get('gold_status'))} | {md_cell(row.get('prompt_status'))} | "
            f"{md_cell(row.get('method_status'))} | {md_cell(reading)} |"
        )
    lines.extend([
        "",
        "## Caption",
        "",
        "Native VSGUI10K reproduces forced-choice grounding outside the synthetic absent benchmark. "
        "Panel A shows a missing text target that prompt-only SeekUI grounds but the verifier rejects. "
        "Panel B shows the conservative cost: a visible target can be over-rejected. "
        "Panel C shows why native text+color and instance-level rows should be treated as a harder "
        "target-definition setting rather than simple text absence.",
        "",
    ])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Build a compact three-panel native VSGUI main-text figure.")
    parser.add_argument("--candidates-csv", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()

    rows = read_csv(Path(args.candidates_csv))
    selected = copy_selected_images(select_one_per_panel(rows), Path(args.out_dir))
    out_dir = Path(args.out_dir)
    png_path = out_dir / "native_v2_main_figure.png"
    jpg_path = make_figure(selected, png_path)
    write_csv(out_dir / "native_v2_main_figure_cases.csv", selected)
    write_json(out_dir / "native_v2_main_figure_cases.json", selected)
    write_md(out_dir / "native_v2_main_figure.md", selected, png_path, jpg_path)
    print(json.dumps({
        "selected": len(selected),
        "png": str(png_path),
        "jpg": str(jpg_path),
        "summary_md": str(out_dir / "native_v2_main_figure.md"),
    }, indent=2))


if __name__ == "__main__":
    main()
