#!/usr/bin/env python
import argparse
import csv
import json
import math
import random
import shutil
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def read_csv(path):
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path, rows, fieldnames=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = []
        for row in rows:
            for key in row:
                if key not in fieldnames:
                    fieldnames.append(key)
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def row_key(row):
    for field in ("review_id", "img_usr_tgt", "key", "id"):
        value = row.get(field)
        if value not in {"", None}:
            return str(value)
    return "|".join([
        str(row.get("image", "")),
        str(row.get("query_text", row.get("target", ""))),
        str(row.get("gold_status", "")),
    ])


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
    items = []
    for row in rows:
        path = resolve_image(image_root, row.get("image"))
        if path:
            items.append((row, path))
    if not items:
        return 0

    rows_count = math.ceil(len(items) / cols)
    cell_w = thumb_width
    cell_h = thumb_height + label_height
    sheet = Image.new("RGB", (cols * cell_w, rows_count * cell_h), "white")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()

    for idx, (row, path) in enumerate(items):
        gx = idx % cols
        gy = idx // cols
        x = gx * cell_w
        y = gy * cell_h
        with Image.open(path) as image:
            thumb = fit_image(image, (thumb_width, thumb_height))
        sheet.paste(thumb, (x, y))
        label = f"{row.get('audit_id', idx)} {row.get('case_source', '')} {Path(row.get('image', '')).name}"
        draw.rectangle((x, y + thumb_height, x + cell_w, y + cell_h), fill=(245, 245, 245))
        draw.text((x + 4, y + thumb_height + 6), label[:80], fill=(0, 0, 0), font=font)
        draw.rectangle((x, y, x + cell_w - 1, y + cell_h - 1), outline=(180, 180, 180))

    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)
    return len(items)


def copy_images(rows, image_root, out_dir):
    out_dir.mkdir(parents=True, exist_ok=True)
    copied = 0
    for row in rows:
        src = resolve_image(image_root, row.get("image"))
        if not src:
            row["_resolved_image"] = ""
            row["_local_image"] = ""
            continue
        dst = out_dir / f"{int(row.get('audit_id', copied)):03d}_{src.name}"
        if not dst.exists():
            shutil.copy2(src, dst)
        row["_resolved_image"] = str(src)
        row["_local_image"] = str(dst)
        copied += 1
    return copied


def sample_rows(rows, predicate, n, rng):
    candidates = [row for row in rows if predicate(row)]
    rng.shuffle(candidates)
    return candidates[:n], len(candidates)


def load_case_keys(cases_dir, case_type):
    keys = []
    for row in read_csv(cases_dir / f"{case_type}.csv"):
        key = row_key(row)
        if key:
            keys.append(key)
    return keys


def rows_by_key(rows):
    mapping = {}
    for row in rows:
        mapping[row_key(row)] = row
    return mapping


def add_selected(selected, seen, source, rows, limit):
    added = 0
    for row in rows:
        key = row_key(row)
        if key in seen:
            continue
        item = dict(row)
        item["case_source"] = source
        selected.append(item)
        seen.add(key)
        added += 1
        if added >= limit:
            break
    return added


def compact_row(row, audit_id):
    return {
        "audit_id": audit_id,
        "case_source": row.get("case_source", ""),
        "review_id": row.get("review_id", ""),
        "img_usr_tgt": row.get("img_usr_tgt", ""),
        "image": row.get("image", ""),
        "local_image": row.get("_local_image", ""),
        "query_text": row.get("query_text") or row.get("target", ""),
        "gold_status": row.get("gold_status", ""),
        "original_target_visible": row.get("target_visible", ""),
        "original_query_realistic": row.get("query_realistic", ""),
        "original_ambiguity_level": row.get("ambiguity_level", ""),
        "original_notes": row.get("notes", ""),
        "prompt_status": row.get("prompt_status", ""),
        "combined_status": row.get("combined_best_f1_status", row.get("combined_status", "")),
        "ocr_aware_status": row.get("vlm_ocr_aware_status", ""),
        "evidence_status": row.get("vlm_evidence_status", ""),
        "audit_target_visible": "",
        "audit_query_realistic": "",
        "audit_gold_status": "",
        "audit_ambiguity_level": "",
        "audit_notes": "",
    }


def write_protocol(path, total_rows, counts, output_csv, contact_sheet):
    lines = [
        "# Realistic Absent Validation Protocol and Second-Pass Audit",
        "",
        "## Dataset Construction",
        "",
        "- Present rows are sampled from released target-present SeekUI/VSGUI examples.",
        "- Realistic absent rows use the same GUI screenshots but manually written plausible user goals that are not visible on that screen.",
        "- Review fields record whether the target is visible, whether the query is realistic for the screen, ambiguity level, and notes.",
        "- Evaluation includes only internally consistent rows: present rows should be visible; absent rows should be invisible and realistic.",
        "",
        "## Second-Pass Audit Instructions",
        "",
        "For each sampled row, inspect the screenshot and query without looking at the model prediction first.",
        "",
        "- `audit_target_visible`: `yes` if the queried target or an unambiguous equivalent is visible; otherwise `no`.",
        "- `audit_query_realistic`: `yes` if a user might reasonably search for this target/action on this screen.",
        "- `audit_gold_status`: `present`, `absent`, or `exclude` if the row is too ambiguous/invalid.",
        "- `audit_ambiguity_level`: `low`, `medium`, or `high`.",
        "- `audit_notes`: short explanation for any disagreement, invalid row, or ambiguity.",
        "",
        "## Audit Sample",
        "",
        f"- Rows selected: {total_rows}",
        f"- Review CSV: `{output_csv}`",
        f"- Contact sheet: `{contact_sheet}`",
        "",
        "| Source | Count | Candidate Pool |",
        "|---|---:|---:|",
    ]
    for row in counts:
        lines.append(f"| {row['source']} | {row['selected']} | {row['candidate_pool']} |")
    lines.extend([
        "",
        "Use this audit as a defensibility check for the 500-row realistic validation protocol, not as a replacement for the full reviewed sheet.",
        "",
    ])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Export a second-pass audit package for the 500-row realistic absent validation set.")
    parser.add_argument("--filled-csv", required=True)
    parser.add_argument("--analysis-cases-dir", required=True)
    parser.add_argument("--image-root", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--random-present", type=int, default=25)
    parser.add_argument("--random-absent", type=int, default=25)
    parser.add_argument("--case-limit", type=int, default=15)
    parser.add_argument("--seed", type=int, default=29)
    parser.add_argument("--cols", type=int, default=5)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    filled_rows = read_csv(Path(args.filled_csv))
    by_key = rows_by_key(filled_rows)
    selected = []
    seen = set()
    counts = []

    present_rows, present_pool = sample_rows(filled_rows, lambda row: row.get("gold_status") == "present", args.random_present, rng)
    added = add_selected(selected, seen, "random_present", present_rows, args.random_present)
    counts.append({"source": "random_present", "selected": added, "candidate_pool": present_pool})

    absent_rows, absent_pool = sample_rows(filled_rows, lambda row: row.get("gold_status") == "absent", args.random_absent, rng)
    added = add_selected(selected, seen, "random_absent", absent_rows, args.random_absent)
    counts.append({"source": "random_absent", "selected": added, "candidate_pool": absent_pool})

    cases_dir = Path(args.analysis_cases_dir)
    for case_type in [
        "combined_corrected_absent_false_present",
        "combined_new_present_false_absent",
        "combined_kept_absent_false_present",
        "combined_vs_ocr_aware_disagreement",
        "evidence_overreject_present",
    ]:
        case_keys = load_case_keys(cases_dir, case_type)
        case_rows = [by_key[key] for key in case_keys if key in by_key]
        added = add_selected(selected, seen, case_type, case_rows, args.case_limit)
        counts.append({"source": case_type, "selected": added, "candidate_pool": len(case_rows)})

    for audit_id, row in enumerate(selected):
        row["audit_id"] = audit_id

    out_dir = Path(args.out_dir)
    image_root = Path(args.image_root)
    copied = copy_images(selected, image_root, out_dir / "images")
    audit_rows = [compact_row(row, idx) for idx, row in enumerate(selected)]
    audit_csv = out_dir / "real_absent_second_pass_audit.csv"
    fieldnames = list(audit_rows[0].keys()) if audit_rows else []
    write_csv(audit_csv, audit_rows, fieldnames)

    contact_sheet = out_dir / "real_absent_second_pass_audit_contact_sheet.jpg"
    sheet_count = make_contact_sheet(audit_rows, image_root, contact_sheet, args.cols, 360, 300, 34)
    protocol_md = out_dir / "real_absent_validation_protocol.md"
    write_protocol(protocol_md, len(audit_rows), counts, audit_csv, contact_sheet)
    write_csv(out_dir / "second_pass_audit_source_counts.csv", counts, ["source", "selected", "candidate_pool"])
    write_json(out_dir / "second_pass_audit_manifest.json", {
        "filled_csv": args.filled_csv,
        "analysis_cases_dir": args.analysis_cases_dir,
        "rows_selected": len(audit_rows),
        "images_copied": copied,
        "contact_sheet_images": sheet_count,
        "audit_csv": str(audit_csv),
        "contact_sheet": str(contact_sheet),
        "protocol_md": str(protocol_md),
        "counts": counts,
    })
    print(json.dumps({
        "rows_selected": len(audit_rows),
        "images_copied": copied,
        "contact_sheet_images": sheet_count,
        "audit_csv": str(audit_csv),
        "protocol_md": str(protocol_md),
    }, indent=2))


if __name__ == "__main__":
    main()
