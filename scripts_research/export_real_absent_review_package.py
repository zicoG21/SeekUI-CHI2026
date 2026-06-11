#!/usr/bin/env python
import argparse
import csv
import json
import math
import shutil
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def read_csv(path):
    with open(path, "r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path, rows, fieldnames):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def resolve_image(image_root, image):
    image = str(image or "")
    candidates = [
        image_root / image,
        image_root / "vsgui10k-images" / Path(image).name,
    ]
    for path in candidates:
        if path.exists():
            return path
    basename = Path(image).name
    if basename:
        for path in image_root.rglob(basename):
            if path.is_file():
                return path
    return None


def fit_image(image, size):
    image = image.convert("RGB")
    image.thumbnail(size, Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", size, "white")
    x = (size[0] - image.width) // 2
    y = (size[1] - image.height) // 2
    canvas.paste(image, (x, y))
    return canvas


def make_contact_sheet(rows, image_root, output, cols, thumb_width, thumb_height, label_height):
    paths = []
    for row in rows:
        path = resolve_image(image_root, row.get("image"))
        if path:
            paths.append((row, path))
    if not paths:
        return 0

    rows_count = math.ceil(len(paths) / cols)
    cell_w = thumb_width
    cell_h = thumb_height + label_height
    sheet = Image.new("RGB", (cols * cell_w, rows_count * cell_h), "white")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()

    for idx, (row, path) in enumerate(paths):
        grid_y = idx // cols
        grid_x = idx % cols
        x = grid_x * cell_w
        y = grid_y * cell_h
        with Image.open(path) as image:
            thumb = fit_image(image, (thumb_width, thumb_height))
        sheet.paste(thumb, (x, y))
        label = f"{row.get('review_id', idx)} {Path(row.get('image', '')).name}"
        draw.rectangle((x, y + thumb_height, x + cell_w, y + cell_h), fill=(245, 245, 245))
        draw.text((x + 4, y + thumb_height + 6), label[:60], fill=(0, 0, 0), font=font)
        draw.rectangle((x, y, x + cell_w - 1, y + cell_h - 1), outline=(180, 180, 180))

    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)
    return len(paths)


def export_images(rows, image_root, out_dir):
    out_dir.mkdir(parents=True, exist_ok=True)
    copied = 0
    for row in rows:
        src = resolve_image(image_root, row.get("image"))
        if not src:
            row["_resolved_image"] = ""
            row["_local_image"] = ""
            continue
        dst = out_dir / f"{int(row.get('review_id', copied)):03d}_{src.name}"
        if not dst.exists():
            shutil.copy2(src, dst)
        row["_resolved_image"] = str(src)
        row["_local_image"] = str(dst)
        copied += 1
    return copied


def missing_rows(rows):
    result = []
    for row in rows:
        if row.get("_resolved_image"):
            continue
        image = str(row.get("image", "") or "")
        result.append({
            "review_id": row.get("review_id", ""),
            "image": image,
            "basename": Path(image).name,
            "tried_relative": str(Path(image)),
            "tried_flat": str(Path("vsgui10k-images") / Path(image).name),
        })
    return result


def compact_rows(rows):
    result = []
    for row in rows:
        result.append({
            "review_id": row.get("review_id", ""),
            "image": row.get("image", ""),
            "local_image": row.get("_local_image", ""),
            "query_text": row.get("query_text", ""),
            "gold_status": row.get("gold_status", ""),
            "target_visible": row.get("target_visible", ""),
            "query_realistic": row.get("query_realistic", ""),
            "ambiguity_level": row.get("ambiguity_level", ""),
            "suggested_absent_query": row.get("suggested_absent_query", ""),
            "notes": row.get("notes", ""),
        })
    return result


def write_md(path, rows, copied, sheet_path, review_csv, missing_csv):
    missing = sum(1 for row in rows if not row.get("_resolved_image"))
    lines = [
        "# Realistic Absent Review Package",
        "",
        f"- Absent rows: {len(rows)}",
        f"- Images copied: {copied}",
        f"- Missing images: {missing}",
        f"- Contact sheet: `{sheet_path}`",
        f"- Review CSV: `{review_csv}`",
        f"- Missing-image CSV: `{missing_csv}`",
        "",
        "Fill the review CSV columns:",
        "",
        "- `query_text`: a plausible missing target for the UI screen.",
        "- `target_visible`: usually `no`, unless the query accidentally appears.",
        "- `query_realistic`: `yes` if a user might reasonably search for it on this screen.",
        "- `ambiguity_level`: `low`, `medium`, or `high`.",
        "- `notes`: short explanation for invalid or ambiguous rows.",
        "",
        "After filling, merge these rows back into the prefilled CSV or use the review CSV as the source for absent rows.",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Export images/contact sheet for realistic absent validation review.")
    parser.add_argument("--input-csv", required=True)
    parser.add_argument("--image-root", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--cols", type=int, default=5)
    parser.add_argument("--thumb-width", type=int, default=360)
    parser.add_argument("--thumb-height", type=int, default=300)
    args = parser.parse_args()

    rows = [
        row for row in read_csv(Path(args.input_csv))
        if row.get("source_type") == "realistic_absent_placeholder" or row.get("gold_status") == "absent"
    ]
    if args.limit:
        rows = rows[:args.limit]
    out_dir = Path(args.out_dir)
    image_root = Path(args.image_root)
    review_csv = out_dir / "real_absent_rows_to_fill.csv"
    contact_sheet = out_dir / "real_absent_review_contact_sheet.jpg"
    copied_dir = out_dir / "images"

    copied = export_images(rows, image_root, copied_dir)
    review_rows = compact_rows(rows)
    write_csv(review_csv, review_rows, list(review_rows[0].keys()) if review_rows else [])
    missing_csv = out_dir / "missing_images.csv"
    missing = missing_rows(rows)
    write_csv(
        missing_csv,
        missing,
        ["review_id", "image", "basename", "tried_relative", "tried_flat"],
    )
    sheet_count = make_contact_sheet(rows, image_root, contact_sheet, args.cols, args.thumb_width, args.thumb_height, 26)
    write_md(out_dir / "real_absent_review_package.md", rows, copied, contact_sheet, review_csv, missing_csv)

    print(json.dumps({
        "absent_rows": len(rows),
        "images_copied": copied,
        "missing_images": len(missing),
        "contact_sheet_images": sheet_count,
        "review_csv": str(review_csv),
        "contact_sheet": str(contact_sheet),
        "missing_csv": str(missing_csv),
        "summary_md": str(out_dir / "real_absent_review_package.md"),
    }, indent=2))


if __name__ == "__main__":
    main()
