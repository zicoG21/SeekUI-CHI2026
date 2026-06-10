#!/usr/bin/env python
import argparse
import csv
import json
import random
import re
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from pathlib import Path


ABSENT_STATUSES = {"absent", "not_found", "not found", "no object", "no target", "not present"}
STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "by", "for", "from", "in", "is", "it",
    "of", "on", "or", "the", "to", "with", "your", "you",
}


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def normalize(text):
    text = str(text or "").casefold().replace("_", " ").replace("-", " ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def target_key(example):
    target_id = str(example.get("target_id", "") or "")
    return target_id[4:] if target_id.startswith("txt_") else target_id


def target_text(example, target2text):
    for key in ["query_text", "target", "original_target"]:
        text = str(example.get(key, "") or "")
        if text:
            return text
    return str(target2text.get(target_key(example), "") or "")


def status(example):
    if "target_present" in example:
        return "present" if example["target_present"] else "absent"
    return "absent" if str(example.get("status", "present")).casefold() in ABSENT_STATUSES else "present"


def tokens(text):
    return {token for token in normalize(text).split() if len(token) >= 2 and token not in STOPWORDS}


def text_similarity(a, b):
    a = normalize(a)
    b = normalize(b)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    if min(len(a), len(b)) >= 4 and (a in b or b in a):
        return min(len(a), len(b)) / max(len(a), len(b))
    return SequenceMatcher(None, a, b).ratio()


def load_ocr(path):
    if not path or not Path(path).exists():
        return {}
    raw = load_json(Path(path))
    rows = raw.get("images", raw if isinstance(raw, list) else [])
    return {
        row.get("image", ""): row.get("candidates", []) or []
        for row in rows
        if row.get("image")
    }


def best_ocr_match(query, candidates, min_conf):
    best = {"score": 0.0, "text": "", "conf": ""}
    for candidate in candidates:
        try:
            conf = float(candidate.get("conf", 0.0))
        except (TypeError, ValueError):
            conf = 0.0
        if conf < min_conf:
            continue
        score = text_similarity(query, candidate.get("text", ""))
        if score > best["score"]:
            best = {"score": score, "text": candidate.get("text", ""), "conf": conf}
    return best


def build_reference_indices(reference, target2text):
    image_to_targets = defaultdict(list)
    target_text_counts = Counter()
    target_id_counts = Counter()
    for example in reference:
        text = target_text(example, target2text)
        norm_text = normalize(text)
        if norm_text:
            target_text_counts[norm_text] += 1
        target_id = example.get("target_id", "")
        if target_id:
            target_id_counts[target_id] += 1
        image_to_targets[example.get("image", "")].append({
            "target_id": target_id,
            "target": text,
            "norm_target": norm_text,
            "img_usr_tgt": example.get("img_usr_tgt", ""),
        })
    return image_to_targets, target_text_counts, target_id_counts


def split_random(examples, seed):
    rng = random.Random(seed)
    by_status = defaultdict(list)
    for idx, example in enumerate(examples):
        by_status[status(example)].append(idx)
    dev = set()
    test = set()
    for indices in by_status.values():
        rng.shuffle(indices)
        n_dev = round(len(indices) * 0.5)
        dev.update(indices[:n_dev])
        test.update(indices[n_dev:])
    return dev, test


def split_image(examples, seed):
    rng = random.Random(seed)
    image_to_indices = defaultdict(list)
    for idx, example in enumerate(examples):
        image_to_indices[example.get("image", "")].append(idx)
    images = list(image_to_indices)
    rng.shuffle(images)
    n_dev = round(len(images) * 0.5)
    dev_images = set(images[:n_dev])
    dev = set()
    test = set()
    for image, indices in image_to_indices.items():
        if image in dev_images:
            dev.update(indices)
        else:
            test.update(indices)
    return dev, test


def leakage_report(examples, dev, test):
    dev_images = {examples[idx].get("image", "") for idx in dev}
    test_images = {examples[idx].get("image", "") for idx in test}
    dev_targets = {normalize(target_text(examples[idx], {})) for idx in dev}
    test_targets = {normalize(target_text(examples[idx], {})) for idx in test}
    dev_pairs = {(examples[idx].get("image", ""), normalize(target_text(examples[idx], {}))) for idx in dev}
    test_pairs = {(examples[idx].get("image", ""), normalize(target_text(examples[idx], {}))) for idx in test}
    return {
        "dev_examples": len(dev),
        "test_examples": len(test),
        "dev_images": len(dev_images),
        "test_images": len(test_images),
        "shared_images": len(dev_images & test_images),
        "shared_target_texts": len(dev_targets & test_targets),
        "shared_image_target_pairs": len(dev_pairs & test_pairs),
    }


def main():
    parser = argparse.ArgumentParser(description="Audit synthetic present/absent benchmark sanity.")
    parser.add_argument("--reference", required=True)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--target2text", default="")
    parser.add_argument("--ocr-candidates", default="")
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--ocr-threshold", type=float, default=0.5)
    parser.add_argument("--min-ocr-conf", type=float, default=35.0)
    args = parser.parse_args()

    reference = load_json(Path(args.reference))
    dataset = load_json(Path(args.dataset))
    target2text = load_json(Path(args.target2text)) if args.target2text else {}
    ocr_by_image = load_ocr(args.ocr_candidates)
    image_to_targets, reference_text_counts, reference_id_counts = build_reference_indices(reference, target2text)

    status_counts = Counter(status(example) for example in dataset)
    image_status = defaultdict(Counter)
    target_status = defaultdict(Counter)
    absent_target_counts = Counter()
    absent_rows = []
    ocr_rows = []
    annotation_conflicts = []

    for idx, example in enumerate(dataset):
        st = status(example)
        image = example.get("image", "")
        text = target_text(example, target2text)
        norm_text = normalize(text)
        image_status[image][st] += 1
        target_status[norm_text][st] += 1
        if st == "absent":
            absent_target_counts[norm_text] += 1

        if st != "absent":
            continue

        candidates = image_to_targets.get(image, [])
        exact_id = [cand for cand in candidates if cand["target_id"] == example.get("target_id", "")]
        text_matches = [
            cand for cand in candidates
            if norm_text and (
                cand["norm_target"] == norm_text
                or text_similarity(norm_text, cand["norm_target"]) >= 0.88
                or (tokens(norm_text) and tokens(norm_text) <= tokens(cand["norm_target"]))
            )
        ]
        if exact_id or text_matches:
            annotation_conflicts.append({
                "index": idx,
                "img_usr_tgt": example.get("img_usr_tgt", ""),
                "image": image,
                "target": text,
                "target_id": example.get("target_id", ""),
                "exact_id_matches": len(exact_id),
                "text_matches": len(text_matches),
                "top_text_match": text_matches[0]["target"] if text_matches else "",
            })

        best_ocr = best_ocr_match(text, ocr_by_image.get(image, []), args.min_ocr_conf)
        ocr_rows.append({
            "index": idx,
            "img_usr_tgt": example.get("img_usr_tgt", ""),
            "image": image,
            "target": text,
            "best_ocr_score": best_ocr["score"],
            "best_ocr_text": best_ocr["text"],
            "best_ocr_conf": best_ocr["conf"],
            "ocr_leak_flag": int(best_ocr["score"] >= args.ocr_threshold),
        })
        absent_rows.append({
            "index": idx,
            "img_usr_tgt": example.get("img_usr_tgt", ""),
            "image": image,
            "target": text,
            "target_id": example.get("target_id", ""),
            "reference_target_text_frequency": reference_text_counts[norm_text],
            "reference_target_id_frequency": reference_id_counts[example.get("target_id", "")],
            "destination_image_annotated_targets": len(candidates),
            "annotation_conflict_flag": int(bool(exact_id or text_matches)),
            "ocr_leak_flag": int(best_ocr["score"] >= args.ocr_threshold),
        })

    images_with_both = sum(1 for counts in image_status.values() if counts["present"] and counts["absent"])
    present_images = {image for image, counts in image_status.items() if counts["present"]}
    absent_images = {image for image, counts in image_status.items() if counts["absent"]}
    random_dev, random_test = split_random(dataset, args.seed)
    image_dev, image_test = split_image(dataset, args.seed)

    ocr_leaks = [row for row in ocr_rows if row["ocr_leak_flag"]]
    report = {
        "num_examples": len(dataset),
        "status_counts": dict(status_counts),
        "unique_images": len(image_status),
        "present_unique_images": len(present_images),
        "absent_unique_images": len(absent_images),
        "shared_present_absent_images": len(present_images & absent_images),
        "images_with_both_present_and_absent": images_with_both,
        "unique_target_texts": len(target_status),
        "targets_with_both_present_and_absent": sum(1 for counts in target_status.values() if counts["present"] and counts["absent"]),
        "annotation_conflicts": len(annotation_conflicts),
        "ocr_candidate_file": str(Path(args.ocr_candidates)) if args.ocr_candidates else "",
        "ocr_leak_threshold": args.ocr_threshold,
        "ocr_leak_absent_examples": len(ocr_leaks),
        "ocr_leak_absent_rate": len(ocr_leaks) / status_counts["absent"] if status_counts["absent"] else 0.0,
        "random_split_leakage": leakage_report(dataset, random_dev, random_test),
        "image_split_leakage": leakage_report(dataset, image_dev, image_test),
        "top_absent_targets": absent_target_counts.most_common(20),
        "annotation_conflict_preview": annotation_conflicts[:20],
        "ocr_leak_preview": sorted(ocr_leaks, key=lambda row: -row["best_ocr_score"])[:20],
    }

    out_dir = Path(args.out_dir)
    write_json(out_dir / "absent_benchmark_sanity.json", report)
    write_csv(out_dir / "absent_examples_sanity.csv", absent_rows)
    write_csv(out_dir / "absent_ocr_leaks.csv", ocr_rows)
    write_csv(out_dir / "annotation_conflicts.csv", annotation_conflicts)

    md = [
        "# Synthetic Absent Benchmark Sanity Check",
        "",
        f"- Examples: {report['num_examples']}",
        f"- Status counts: {report['status_counts']}",
        f"- Unique images: {report['unique_images']}",
        f"- Present unique images: {report['present_unique_images']}",
        f"- Absent unique images: {report['absent_unique_images']}",
        f"- Shared present/absent images: {report['shared_present_absent_images']}",
        f"- Annotation conflicts: {report['annotation_conflicts']}",
        f"- OCR leak absent examples: {report['ocr_leak_absent_examples']} ({report['ocr_leak_absent_rate']:.4f})",
        "",
        "## Split Leakage",
        "",
        "| Split | Dev examples | Test examples | Shared images | Shared target texts | Shared image-target pairs |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for name, leakage in [("random", report["random_split_leakage"]), ("image", report["image_split_leakage"])]:
        md.append(
            f"| {name} | {leakage['dev_examples']} | {leakage['test_examples']} | "
            f"{leakage['shared_images']} | {leakage['shared_target_texts']} | {leakage['shared_image_target_pairs']} |"
        )
    md.extend([
        "",
        "## Outputs",
        "",
        f"- JSON: `{out_dir / 'absent_benchmark_sanity.json'}`",
        f"- Absent rows: `{out_dir / 'absent_examples_sanity.csv'}`",
        f"- OCR leaks: `{out_dir / 'absent_ocr_leaks.csv'}`",
        f"- Annotation conflicts: `{out_dir / 'annotation_conflicts.csv'}`",
    ])
    (out_dir / "absent_benchmark_sanity.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    print(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"Summary: {out_dir / 'absent_benchmark_sanity.md'}")


if __name__ == "__main__":
    main()
