#!/usr/bin/env python
import argparse
import csv
import json
import math
import shutil
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import resolve_native_vsgui10k_image_cues as resolver


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


def resolve_screen(image_root, image):
    image_root = Path(image_root)
    candidates = [
        image_root / str(image or ""),
        image_root / "vsgui10k-images" / Path(str(image or "")).name,
    ]
    stem = Path(str(image or "")).stem
    for ext in [".png", ".jpg", ".jpeg"]:
        if stem:
            candidates.append(image_root / "vsgui10k-images" / f"{stem}{ext}")
    for path in candidates:
        if path.exists():
            return path
    return None


def materialize_match(match, out_dir, prefix):
    if not match:
        return ""
    out_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(match["name"]).suffix or ".png"
    dst = out_dir / f"{prefix}_{Path(match['name']).stem}{suffix}"
    if match["kind"] == "file":
        shutil.copy2(match["path"], dst)
    else:
        with resolver.zipfile.ZipFile(match["root"]) as zf:
            with zf.open(match["path"]) as src, open(dst, "wb") as out:
                shutil.copyfileobj(src, out)
    return str(dst)


def fit_image(path, size):
    if not path or not Path(path).exists():
        return Image.new("RGB", size, (242, 242, 242))
    with Image.open(path) as image:
        image = image.convert("RGB")
        image.thumbnail(size, Image.Resampling.LANCZOS)
        canvas = Image.new("RGB", size, "white")
        x = (size[0] - image.width) // 2
        y = (size[1] - image.height) // 2
        canvas.paste(image, (x, y))
        return canvas


def draw_wrapped(draw, xy, text, width, font, fill=(0, 0, 0), line_gap=4):
    x, y = xy
    words = str(text or "").split()
    lines = []
    current = ""
    for word in words:
        trial = f"{current} {word}".strip()
        if len(trial) > width and current:
            lines.append(current)
            current = word
        else:
            current = trial
    if current:
        lines.append(current)
    for line in lines[:4]:
        draw.text((x, y), line, font=font, fill=fill)
        y += font.size + line_gap
    return y


def make_review_contact_sheet(groups, output, cols=2):
    font = ImageFont.load_default()
    cell_w, cell_h = 760, 430
    rows = math.ceil(len(groups) / cols) if groups else 1
    sheet = Image.new("RGB", (cols * cell_w, rows * cell_h), "white")
    draw = ImageDraw.Draw(sheet)
    for idx, group in enumerate(groups):
        x = (idx % cols) * cell_w
        y = (idx // cols) * cell_h
        draw.rectangle((x, y, x + cell_w - 1, y + cell_h - 1), outline=(170, 170, 170), width=2)
        draw.text((x + 10, y + 8), f"{group['review_id']} {group['gold_status']} {group['native_new_img_name']}", font=font, fill=(0, 0, 0))
        draw_wrapped(draw, (x + 10, y + 28), group.get("key", ""), 100, font, fill=(55, 55, 55))
        screen = fit_image(group.get("screen_local"), (330, 250))
        sheet.paste(screen, (x + 10, y + 90))
        draw.text((x + 10, y + 344), "screen", font=font, fill=(0, 0, 0))
        for rank, path in enumerate(group.get("candidate_local_paths", [])[:4]):
            col = rank % 2
            row = rank // 2
            cx = x + 360 + col * 195
            cy = y + 80 + row * 150
            cue = fit_image(path, (180, 120))
            sheet.paste(cue, (cx, cy))
            draw.text((cx, cy + 124), f"candidate {rank}", font=font, fill=(0, 0, 0))
        draw_wrapped(
            draw,
            (x + 360, y + 380),
            "Pick candidate rank if exactly one is the cue; mark exclude if unsure.",
            58,
            font,
            fill=(80, 80, 80),
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output, quality=92)


def build_review_groups(args):
    trials = resolver.load_json(Path(args.trials_json))
    raw_by_key = resolver.load_raw_fixation_rows(args.fixations_csv, args.visual_img_type)
    search_roots = [Path(args.image_root)] + [Path(path) for path in args.search_root]
    zip_paths = [Path(path) for path in args.zip_path]
    records = resolver.index_files(search_roots, zip_paths)
    indexes = resolver.make_indexes(records)
    groups = []
    for idx, example in enumerate(trials):
        if resolver.cue_type(example) not in {"image", "i"}:
            continue
        raw_row = raw_by_key.get(str(example.get("img_usr_tgt", "")), {})
        merged = dict(raw_row)
        merged.update(example)
        values = resolver.candidate_values(merged)
        matched = []
        matched_field = ""
        matched_value = ""
        for field, value in values:
            if not resolver.is_cue_side_field(field):
                continue
            matches = resolver.match_records(value, indexes)
            if matches:
                matched = matches
                matched_field = field
                matched_value = value
                break
        chosen, resolution = resolver.choose_match(matched, example.get("image", ""), {})
        if not resolution.startswith("ambiguous"):
            continue
        groups.append({
            "review_id": len(groups),
            "index": idx,
            "key": example.get("img_usr_tgt", idx),
            "image": example.get("image", ""),
            "gold_status": resolver.gold_status(example),
            "native_new_img_name": example.get("native_new_img_name", "") or raw_row.get("new_img_name", ""),
            "matched_cue_field": matched_field,
            "matched_cue_value": matched_value,
            "resolution_status": resolution,
            "num_matches": len(matched),
            "_example": example,
            "_matches": matched,
            "_chosen": chosen,
        })
    return groups[: args.limit] if args.limit else groups


def main():
    parser = argparse.ArgumentParser(description="Export review package for ambiguous native image-cue asset matches.")
    parser.add_argument("--trials-json", required=True)
    parser.add_argument("--image-root", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--search-root", action="append", default=[])
    parser.add_argument("--zip-path", action="append", default=[])
    parser.add_argument("--fixations-csv", default="")
    parser.add_argument("--visual-img-type", default="2")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    screen_dir = out_dir / "screens"
    candidate_dir = out_dir / "candidates"
    screen_dir.mkdir(parents=True, exist_ok=True)
    candidate_dir.mkdir(parents=True, exist_ok=True)

    groups = build_review_groups(args)
    review_rows = []
    public_groups = []
    for group in groups:
        screen_path = resolve_screen(args.image_root, group["image"])
        screen_local = ""
        if screen_path:
            screen_local = str(screen_dir / f"{group['review_id']:03d}_{screen_path.name}")
            shutil.copy2(screen_path, screen_local)
        local_candidates = []
        match_paths = []
        for rank, match in enumerate(group["_matches"][:6]):
            local = materialize_match(match, candidate_dir, f"{group['review_id']:03d}_{rank:02d}")
            local_candidates.append(local)
            match_paths.append(f"{rank}:{match.get('kind')}:{match.get('match_source')}:{match.get('path')}")
        row = {
            "review_id": group["review_id"],
            "index": group["index"],
            "key": group["key"],
            "gold_status": group["gold_status"],
            "image": group["image"],
            "screen_local": screen_local,
            "native_new_img_name": group["native_new_img_name"],
            "matched_cue_field": group["matched_cue_field"],
            "matched_cue_value": group["matched_cue_value"],
            "resolution_status": group["resolution_status"],
            "num_matches": group["num_matches"],
            "candidate_local_paths": ";".join(local_candidates),
            "match_paths": "; ".join(match_paths),
            "review_decision": "",
            "use_candidate_rank": "",
            "notes": "",
        }
        review_rows.append(row)
        public = dict(row)
        public["candidate_local_paths"] = local_candidates
        public_groups.append(public)

    review_csv = out_dir / "native_image_cue_ambiguous_review.csv"
    review_json = out_dir / "native_image_cue_ambiguous_review.json"
    contact_sheet = out_dir / "native_image_cue_ambiguous_review.jpg"
    write_csv(review_csv, review_rows)
    write_json(review_json, public_groups)
    make_review_contact_sheet(public_groups, contact_sheet)
    lines = [
        "# Native Image-Cue Ambiguous Review",
        "",
        f"- Rows: {len(review_rows)}",
        f"- Review CSV: `{review_csv}`",
        f"- Contact sheet: `{contact_sheet}`",
        "",
        "Fill `review_decision` as `use`, `exclude`, or `uncertain`.",
        "If `use`, set `use_candidate_rank` to the candidate number shown in the contact sheet.",
        "",
    ]
    (out_dir / "native_image_cue_ambiguous_review.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({
        "rows": len(review_rows),
        "review_csv": str(review_csv),
        "contact_sheet": str(contact_sheet),
    }, indent=2))


if __name__ == "__main__":
    main()
