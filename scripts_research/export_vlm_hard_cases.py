#!/usr/bin/env python
import argparse
import csv
import json
from pathlib import Path


def read_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def read_csv(path):
    with open(path, "r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def write_csv(path, rows, fieldnames):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def by_id(rows):
    return {row.get("img_usr_tgt"): row for row in rows if row.get("img_usr_tgt")}


def normalize_status(row):
    return str(row.get("predicted_status") or row.get("adjusted_predicted_status") or "").strip()


def export_subset(rows, output_json, output_csv):
    fields = [
        "case_source",
        "case_type",
        "img_usr_tgt",
        "image",
        "target",
        "gold_status",
        "combined_status",
        "vlm_status",
        "path_best_evidence",
        "ocr_candidate_verifier_score",
        "ocr_candidate_verifier_text",
        "notes",
    ]
    write_csv(output_csv, rows, fields)
    write_json(output_json, rows)


def main():
    parser = argparse.ArgumentParser(description="Export hard-case lists for VLM-vs-combined analysis.")
    parser.add_argument("--combined-predictions", required=True)
    parser.add_argument("--vlm-predictions", required=True)
    parser.add_argument("--combined-case-index", action="append", default=[])
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--limit-per-type", type=int, default=100)
    args = parser.parse_args()

    combined = by_id(read_json(Path(args.combined_predictions)))
    vlm = by_id(read_json(Path(args.vlm_predictions)))
    out_dir = Path(args.out_dir)

    rows = []
    for sample_id, c_row in combined.items():
        v_row = vlm.get(sample_id)
        if not v_row:
            continue
        gold = str(c_row.get("gold_status") or c_row.get("status") or "").strip()
        c_status = normalize_status(c_row)
        v_status = normalize_status(v_row)
        if not gold or not c_status or not v_status:
            continue
        base = {
            "img_usr_tgt": sample_id,
            "image": c_row.get("image", ""),
            "target": c_row.get("target") or c_row.get("query_text") or c_row.get("original_target", ""),
            "gold_status": gold,
            "combined_status": c_status,
            "vlm_status": v_status,
            "path_best_evidence": c_row.get("path_best_evidence", ""),
            "ocr_candidate_verifier_score": c_row.get("ocr_candidate_verifier_score", ""),
            "ocr_candidate_verifier_text": c_row.get("ocr_candidate_verifier_text", ""),
            "notes": "",
        }
        if c_status == gold and v_status != gold:
            rows.append({"case_source": "vlm_wrong_combined_correct", "case_type": f"{gold}_case", **base})
        if c_status != gold and v_status == gold:
            rows.append({"case_source": "combined_wrong_vlm_correct", "case_type": f"{gold}_case", **base})
        if c_status != gold and v_status != gold:
            rows.append({"case_source": "both_wrong", "case_type": f"{gold}_case", **base})

    case_index_rows = []
    for index_path in args.combined_case_index:
        for row in read_csv(Path(index_path)):
            sample_id = row.get("img_usr_tgt")
            c_row = combined.get(sample_id, {})
            v_row = vlm.get(sample_id, {})
            case_index_rows.append({
                "case_source": "combined_mined_case",
                "case_type": row.get("case_type", ""),
                "img_usr_tgt": sample_id,
                "image": row.get("image", c_row.get("image", "")),
                "target": row.get("target") or row.get("original_target") or c_row.get("target", ""),
                "gold_status": row.get("gold_status", c_row.get("gold_status", "")),
                "combined_status": row.get("adjusted_predicted_status", normalize_status(c_row)),
                "vlm_status": normalize_status(v_row),
                "path_best_evidence": row.get("path_best_evidence", c_row.get("path_best_evidence", "")),
                "ocr_candidate_verifier_score": row.get(
                    "ocr_candidate_verifier_score",
                    c_row.get("ocr_candidate_verifier_score", ""),
                ),
                "ocr_candidate_verifier_text": row.get(
                    "ocr_candidate_verifier_text",
                    c_row.get("ocr_candidate_verifier_text", ""),
                ),
                "notes": "",
            })

    grouped = {}
    for row in rows + case_index_rows:
        key = row["case_source"] + "__" + row["case_type"]
        grouped.setdefault(key, [])
        if len(grouped[key]) < args.limit_per_type:
            grouped[key].append(row)

    manifest = []
    for key, subset in sorted(grouped.items()):
        output_json = out_dir / f"{key}.json"
        output_csv = out_dir / f"{key}.csv"
        export_subset(subset, output_json, output_csv)
        manifest.append({
            "group": key,
            "count": len(subset),
            "json": str(output_json),
            "csv": str(output_csv),
        })

    write_json(out_dir / "manifest.json", manifest)
    print(json.dumps({"groups": len(manifest), "out_dir": str(out_dir)}, indent=2))


if __name__ == "__main__":
    main()
