#!/usr/bin/env python
import argparse
import csv
import json
import os
import re
import shutil
import zipfile
from collections import Counter
from pathlib import Path


IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
CUE_FIELDS = [
    "native_new_img_name",
    "new_img_name",
    "target_image",
    "target_crop",
    "cue_image",
    "cue_image_path",
]


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
        writer = csv.DictWriter(f, fieldnames=fieldnames or ["empty"], lineterminator="\n", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def is_image(value):
    return Path(str(value or "")).suffix.casefold() in IMAGE_SUFFIXES


def norm_token(value):
    value = Path(str(value or "")).name
    value = re.sub(r"\.[A-Za-z0-9]+$", "", value)
    value = re.sub(r"[^A-Za-z0-9]+", "", value)
    return value.casefold()


def cue_type(example):
    return str(example.get("cue_type") or example.get("cue") or example.get("native_cue") or "").casefold()


def gold_status(example):
    if str(example.get("status", "")).casefold() in {"present", "absent"}:
        return str(example.get("status")).casefold()
    if "target_present" in example:
        return "present" if example.get("target_present") else "absent"
    return ""


def safe_rel(path, root):
    try:
        return str(Path(path).resolve().relative_to(Path(root).resolve()))
    except Exception:
        return str(path)


def index_files(search_roots, zip_paths):
    records = []
    for root in search_roots:
        root = Path(root)
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.is_file() and path.suffix.casefold() in IMAGE_SUFFIXES:
                records.append({
                    "kind": "file",
                    "root": str(root),
                    "path": str(path),
                    "name": path.name,
                    "stem": path.stem,
                    "token": norm_token(path.name),
                })
    for zip_path in zip_paths:
        zip_path = Path(zip_path)
        if not zip_path.exists():
            continue
        with zipfile.ZipFile(zip_path) as zf:
            for member in zf.infolist():
                if member.is_dir():
                    continue
                path = Path(member.filename)
                if path.suffix.casefold() not in IMAGE_SUFFIXES:
                    continue
                records.append({
                    "kind": "zip",
                    "root": str(zip_path),
                    "path": member.filename,
                    "name": path.name,
                    "stem": path.stem,
                    "token": norm_token(path.name),
                })
    return records


def make_indexes(records):
    by_name = {}
    by_stem = {}
    by_token = {}
    for record in records:
        by_name.setdefault(record["name"].casefold(), []).append(record)
        by_stem.setdefault(record["stem"].casefold(), []).append(record)
        by_token.setdefault(record["token"], []).append(record)
    return by_name, by_stem, by_token


def candidate_values(example):
    values = []
    for field in CUE_FIELDS:
        value = str(example.get(field, "") or "").strip()
        if value:
            values.append((field, value))
    native = str(example.get("native_new_img_name", "") or "").strip()
    if native:
        # OSF rows sometimes contain nested names such as foo.png_123.jpg.
        for piece in re.split(r"[\s,;|]+", native):
            piece = piece.strip()
            if piece and piece != native:
                values.append(("native_new_img_name_piece", piece))
    return values


def match_records(value, indexes):
    by_name, by_stem, by_token = indexes
    path = Path(value)
    name = path.name.casefold()
    stem = path.stem.casefold()
    token = norm_token(value)
    matches = []
    for source, found in [
        ("name", by_name.get(name, [])),
        ("stem", by_stem.get(stem, [])),
        ("token", by_token.get(token, [])),
    ]:
        for record in found:
            item = dict(record)
            item["match_source"] = source
            matches.append(item)

    deduped = []
    seen = set()
    for item in matches:
        key = (item["kind"], item["root"], item["path"])
        if key in seen:
            continue
        deduped.append(item)
        seen.add(key)
    return deduped


def choose_match(matches, screen_image):
    if not matches:
        return None, "missing"
    screen_name = Path(str(screen_image or "")).name.casefold()
    non_screen = [m for m in matches if m["name"].casefold() != screen_name]
    candidates = non_screen or matches
    file_matches = [m for m in candidates if m["kind"] == "file"]
    if len(file_matches) == 1:
        return file_matches[0], "resolved"
    if len(file_matches) > 1:
        return file_matches[0], "ambiguous_file"
    if len(candidates) == 1:
        return candidates[0], "resolved_zip_only"
    return candidates[0], "ambiguous_zip"


def extract_zip_member(record, out_dir):
    zip_path = Path(record["root"])
    member = record["path"]
    dst = Path(out_dir) / Path(member).name
    dst.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        with zf.open(member) as src, open(dst, "wb") as out:
            shutil.copyfileobj(src, out)
    return dst


def copy_or_extract(match, out_dir, prefix):
    if not match:
        return ""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(match["name"]).suffix or ".png"
    dst = out_dir / f"{prefix}_{Path(match['name']).stem}{suffix}"
    if match["kind"] == "file":
        shutil.copy2(match["path"], dst)
    else:
        extracted = extract_zip_member(match, out_dir)
        if extracted != dst:
            os.replace(extracted, dst)
    return str(dst)


def compatible_example(example, copied_cue_path, image_root, cue_prefix):
    out = dict(example)
    out["target_crop"] = safe_rel(copied_cue_path, image_root)
    out["target_cue_type"] = "native_image"
    out["native_image_cue_resolved"] = 1
    out["native_image_cue_path"] = out["target_crop"]
    if not out.get("query_text"):
        out["query_text"] = out.get("target") or "image target"
    if not out.get("target"):
        out["target"] = out["query_text"]
    out["target_id"] = f"native_image_{cue_prefix}"
    return out


def write_summary(path, rows, eval_rows, indexed_files, search_roots, zip_paths):
    status_counts = Counter(row["gold_status"] for row in rows)
    resolution_counts = Counter(row["resolution_status"] for row in rows)
    cue_field_counts = Counter(row["matched_cue_field"] or "(none)" for row in rows)
    lines = [
        "# Native VSGUI10K Image-Cue Resolution",
        "",
        f"- Image-cue rows: {len(rows)}",
        f"- Inference-ready rows: {len(eval_rows)}",
        f"- Indexed image files/members: {indexed_files}",
        f"- Search roots: `{'; '.join(str(x) for x in search_roots)}`",
        f"- Zip paths: `{'; '.join(str(x) for x in zip_paths)}`",
        "",
        "## Status Counts",
        "",
        "| Gold status | Count |",
        "|---|---:|",
    ]
    for key, count in sorted(status_counts.items()):
        lines.append(f"| {key or '(missing)'} | {count} |")
    lines.extend(["", "## Resolution Counts", "", "| Resolution | Count |", "|---|---:|"])
    for key, count in resolution_counts.most_common():
        lines.append(f"| {key} | {count} |")
    lines.extend(["", "## Matched Cue Fields", "", "| Field | Count |", "|---|---:|"])
    for key, count in cue_field_counts.most_common():
        lines.append(f"| {key} | {count} |")
    lines.extend([
        "",
        "## Interpretation",
        "",
        "- `resolved` rows have a local cue image copied into the exported cue-image directory and can be used for image-cue inference.",
        "- `resolved_zip_only` rows can also be used because the resolver extracted the cue image from the OSF zip.",
        "- `ambiguous_*` rows need manual checking before headline evaluation because multiple assets match the same cue token.",
        "- `missing` rows are evidence that the released fixation rows reference cue names not available in the extracted assets currently present on disk.",
        "",
    ])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Resolve native VSGUI10K image-cue assets and export inference-ready rows.")
    parser.add_argument("--trials-json", required=True)
    parser.add_argument("--image-root", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--search-root", action="append", default=[])
    parser.add_argument("--zip-path", action="append", default=[])
    parser.add_argument("--include-ambiguous", action="store_true")
    args = parser.parse_args()

    trials = load_json(Path(args.trials_json))
    search_roots = [Path(args.image_root)] + [Path(path) for path in args.search_root]
    zip_paths = [Path(path) for path in args.zip_path]
    records = index_files(search_roots, zip_paths)
    indexes = make_indexes(records)
    out_dir = Path(args.out_dir)
    cue_out_dir = out_dir / "resolved_cue_images"

    rows = []
    eval_rows = []
    for idx, example in enumerate(trials):
        if cue_type(example) not in {"image", "i"}:
            continue
        values = candidate_values(example)
        matched = []
        matched_field = ""
        matched_value = ""
        for field, value in values:
            matches = match_records(value, indexes)
            if matches:
                matched = matches
                matched_field = field
                matched_value = value
                break
        chosen, resolution = choose_match(matched, example.get("image", ""))
        copied = ""
        usable = resolution in {"resolved", "resolved_zip_only"} or (
            args.include_ambiguous and resolution.startswith("ambiguous")
        )
        if usable and chosen:
            prefix = f"{idx:05d}_{gold_status(example)}"
            copied = copy_or_extract(chosen, cue_out_dir, prefix)
            eval_rows.append(compatible_example(example, copied, args.image_root, prefix))
        rows.append({
            "index": idx,
            "key": example.get("img_usr_tgt", idx),
            "image": example.get("image", ""),
            "gold_status": gold_status(example),
            "target": example.get("target", ""),
            "query_text": example.get("query_text", ""),
            "native_img_name": example.get("native_img_name", ""),
            "native_new_img_name": example.get("native_new_img_name", ""),
            "matched_cue_field": matched_field,
            "matched_cue_value": matched_value,
            "resolution_status": resolution,
            "num_matches": len(matched),
            "chosen_kind": chosen.get("kind", "") if chosen else "",
            "chosen_path": chosen.get("path", "") if chosen else "",
            "copied_cue_path": copied,
            "inference_ready": int(bool(copied)),
        })

    balanced = []
    present = [row for row in eval_rows if gold_status(row) == "present"]
    absent = [row for row in eval_rows if gold_status(row) == "absent"]
    keep = min(len(present), len(absent))
    if keep:
        balanced = sorted(present[:keep] + absent[:keep], key=lambda row: str(row.get("img_usr_tgt", "")))

    write_json(out_dir / "native_image_cue_resolution.json", {
        "trials_json": args.trials_json,
        "image_root": args.image_root,
        "search_roots": [str(path) for path in search_roots],
        "zip_paths": [str(path) for path in zip_paths],
        "rows": rows,
    })
    write_csv(out_dir / "native_image_cue_resolution.csv", rows)
    write_json(out_dir / "native_image_cue_eval.json", eval_rows)
    write_json(out_dir / "native_image_cue_balanced_eval.json", balanced)
    write_csv(out_dir / "native_image_cue_eval.csv", [
        {
            "img_usr_tgt": row.get("img_usr_tgt", ""),
            "image": row.get("image", ""),
            "target_crop": row.get("target_crop", ""),
            "status": row.get("status", ""),
            "query_text": row.get("query_text", ""),
            "native_new_img_name": row.get("native_new_img_name", ""),
        }
        for row in eval_rows
    ])
    write_summary(
        out_dir / "native_image_cue_resolution.md",
        rows,
        eval_rows,
        len(records),
        search_roots,
        zip_paths,
    )
    print(json.dumps({
        "image_cue_rows": len(rows),
        "inference_ready": len(eval_rows),
        "balanced_eval": len(balanced),
        "summary_md": str(out_dir / "native_image_cue_resolution.md"),
    }, indent=2))


if __name__ == "__main__":
    main()
