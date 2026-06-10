#!/usr/bin/env python
import argparse
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def image_paths(input_dir, pattern, limit):
    paths = sorted(Path(input_dir).glob(pattern))
    return paths[:limit] if limit else paths


def fit_image(image, size):
    image = image.convert("RGB")
    image.thumbnail(size, Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", size, "white")
    x = (size[0] - image.width) // 2
    y = (size[1] - image.height) // 2
    canvas.paste(image, (x, y))
    return canvas


def main():
    parser = argparse.ArgumentParser(description="Create a contact sheet from visualization PNGs.")
    parser.add_argument("--input-dir", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--pattern", default="*.png")
    parser.add_argument("--limit", type=int, default=40)
    parser.add_argument("--cols", type=int, default=5)
    parser.add_argument("--thumb-width", type=int, default=360)
    parser.add_argument("--thumb-height", type=int, default=300)
    parser.add_argument("--label-height", type=int, default=26)
    args = parser.parse_args()

    paths = image_paths(args.input_dir, args.pattern, args.limit)
    if not paths:
        raise SystemExit(f"No images found in {args.input_dir} matching {args.pattern}")

    cols = max(1, args.cols)
    rows = math.ceil(len(paths) / cols)
    cell_w = args.thumb_width
    cell_h = args.thumb_height + args.label_height
    sheet = Image.new("RGB", (cols * cell_w, rows * cell_h), "white")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()

    for idx, path in enumerate(paths):
        row = idx // cols
        col = idx % cols
        x = col * cell_w
        y = row * cell_h
        with Image.open(path) as image:
            thumb = fit_image(image, (args.thumb_width, args.thumb_height))
        sheet.paste(thumb, (x, y))
        label = f"{idx:02d} {path.stem[:42]}"
        draw.rectangle((x, y + args.thumb_height, x + cell_w, y + cell_h), fill=(245, 245, 245))
        draw.text((x + 4, y + args.thumb_height + 6), label, fill=(0, 0, 0), font=font)
        draw.rectangle((x, y, x + cell_w - 1, y + cell_h - 1), outline=(180, 180, 180))

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)
    print(f"Wrote contact sheet: {output}")
    print(f"Images: {len(paths)}")


if __name__ == "__main__":
    main()
