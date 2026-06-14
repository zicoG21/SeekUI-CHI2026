#!/usr/bin/env python
import argparse
import csv
import json
from collections import Counter
from pathlib import Path

from PIL import Image, ImageDraw


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


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
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames or ["empty"])
        writer.writeheader()
        writer.writerows(rows)


def safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def resolve_path(root, value):
    root = Path(root)
    value = str(value or "")
    if not value:
        return None
    candidates = [
        root / value,
        root / "vsgui10k-images" / Path(value).name,
        root / "segmentation" / Path(value).name,
    ]
    for path in candidates:
        if path.exists():
            return path
    basename = Path(value).name
    if basename:
        for path in root.rglob(basename):
            if path.is_file():
                return path
    return None


def is_image_cue(example):
    return str(example.get("cue_type") or example.get("cue") or example.get("native_cue")).casefold() in {"image", "i"}


def status(example):
    if "target_present" in example:
        return "present" if example["target_present"] else "absent"
    return "absent" if str(example.get("status", "")).casefold() == "absent" else "present"


def bbox_pixels(example, image_width, image_height):
    x = safe_float(example.get("target_x"))
    y = safe_float(example.get("target_y"))
    w = safe_float(example.get("target_width"))
    h = safe_float(example.get("target_height"))
    if 0 <= x <= 1 and 0 <= y <= 1 and 0 <= w <= 1 and 0 <= h <= 1:
        x *= image_width
        y *= image_height
        w *= image_width
        h *= image_height
    return int(round(x)), int(round(y)), int(round(w)), int(round(h))


def export_sample_images(rows, out_dir, max_samples, thumb_size):
    image_dir = out_dir / "samples"
    image_dir.mkdir(parents=True, exist_ok=True)
    exported = []
    for row in rows[:max_samples]:
        image_path = row.get("_resolved_screen_path")
        if not image_path:
            continue
        path = Path(image_path)
        if not path.exists():
            continue
        try:
            with Image.open(path) as image:
                image = image.convert("RGB")
                width, height = image.size
                box = bbox_pixels(row["_example"], width, height)
                x, y, w, h = box
                x1, y1 = max(0, x), max(0, y)
                x2, y2 = min(width, x + w), min(height, y + h)
                if x2 <= x1 or y2 <= y1:
                    continue
                boxed = image.copy()
                draw = ImageDraw.Draw(boxed)
                draw.rectangle((x1, y1, x2, y2), outline="red", width=max(3, width // 400))
                crop = image.crop((x1, y1, x2, y2))
                base = f"{row['index']:05d}_{row['gold_status']}_{Path(row['image']).stem}"
                boxed.thumbnail(thumb_size)
                boxed_path = image_dir / f"{base}_boxed.jpg"
                crop_path = image_dir / f"{base}_crop.png"
                boxed.save(boxed_path)
                crop.save(crop_path)
                exported.append({**row, "boxed_image": str(boxed_path), "crop_image": str(crop_path)})
        except Exception as exc:
            exported.append({**row, "export_error": str(exc)})
    return exported


def row_for(idx, example, image_root):
    screen_path = resolve_path(image_root, example.get("image", ""))
    cue_name = example.get("native_new_img_name") or example.get("new_img_name") or ""
    cue_path = resolve_path(image_root, cue_name)
    return {
        "index": idx,
        "key": example.get("img_usr_tgt", idx),
        "gold_status": status(example),
        "image": example.get("image", ""),
        "native_img_name": example.get("native_img_name", ""),
        "native_new_img_name": cue_name,
        "query_text": example.get("query_text", ""),
        "target": example.get("target", ""),
        "target_color": example.get("target_color", ""),
        "category": example.get("category", ""),
        "screen_image_available": int(screen_path is not None),
        "cue_image_available": int(cue_path is not None),
        "resolved_screen_path": str(screen_path or ""),
        "resolved_cue_path": str(cue_path or ""),
        "_resolved_screen_path": str(screen_path or ""),
        "_example": example,
    }


def strip_internal(row):
    return {key: value for key, value in row.items() if not key.startswith("_")}


def write_summary(path, rows, exported):
    status_counts = Counter(row["gold_status"] for row in rows)
    category_counts = Counter(row["category"] for row in rows)
    cue_available = Counter(row["cue_image_available"] for row in rows)
    screen_available = Counter(row["screen_image_available"] for row in rows)
    lines = [
        "# Native VSGUI10K Image-Cue Asset Audit",
        "",
        f"- Image-cue rows: {len(rows)}",
        f"- Sample visualizations exported: {len(exported)}",
        "",
        "## Status Counts",
        "",
        "| Status | Count |",
        "|---|---:|",
    ]
    for key, count in sorted(status_counts.items()):
        lines.append(f"| {key} | {count} |")
    lines.extend(["", "## Asset Availability", "", "| Asset | Available | Missing |", "|---|---:|---:|"])
    lines.append(f"| screen image | {screen_available.get(1, 0)} | {screen_available.get(0, 0)} |")
    lines.append(f"| cue image (`native_new_img_name`) | {cue_available.get(1, 0)} | {cue_available.get(0, 0)} |")
    lines.extend(["", "## Category Counts", "", "| Category | Count |", "|---|---:|"])
    for key, count in category_counts.most_common():
        lines.append(f"| {key or '(missing)'} | {count} |")
    lines.extend([
        "",
        "## Interpretation",
        "",
        "- If cue images are missing, native image-cue rows should be treated as unresolved rather than a clean image-target absent benchmark.",
        "- Bbox crops from the current screenshot are useful for diagnosis but are not a substitute for the original image cue on absent trials.",
        "- Use this audit before deciding whether to run image-aware VLM methods on native image-cue rows.",
        "",
    ])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Audit native VSGUI10K image-cue asset availability.")
    parser.add_argument("--trials-json", required=True)
    parser.add_argument("--image-root", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--max-samples", type=int, default=80)
    args = parser.parse_args()

    trials = load_json(Path(args.trials_json))
    rows = [row_for(idx, example, args.image_root) for idx, example in enumerate(trials) if is_image_cue(example)]
    out_dir = Path(args.out_dir)
    exported = export_sample_images(rows, out_dir, args.max_samples, (420, 320))
    public_rows = [strip_internal(row) for row in rows]
    public_exported = [strip_internal(row) for row in exported]
    write_json(out_dir / "native_vsgui10k_image_cue_audit.json", {
        "trials_json": args.trials_json,
        "image_root": args.image_root,
        "num_rows": len(rows),
        "rows": public_rows,
        "sample_visualizations": public_exported,
    })
    write_csv(out_dir / "native_vsgui10k_image_cue_audit.csv", public_rows)
    write_csv(out_dir / "native_vsgui10k_image_cue_samples.csv", public_exported)
    write_summary(out_dir / "native_vsgui10k_image_cue_audit.md", rows, exported)
    print(json.dumps({
        "rows": len(rows),
        "sample_visualizations": len(exported),
        "summary_md": str(out_dir / "native_vsgui10k_image_cue_audit.md"),
    }, indent=2))


if __name__ == "__main__":
    main()
