#!/usr/bin/env python
import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def target_key(example):
    target_id = example.get("target_id", "")
    return target_id[4:] if target_id.startswith("txt_") else target_id


def target_text(example, target2text):
    explicit = str(example.get("target", "") or "")
    if explicit:
        return explicit
    return str(target2text.get(target_key(example), "") or "")


def norm(text):
    return " ".join(str(text or "").casefold().strip().split())


def status(example):
    if "target_present" in example:
        return "present" if example["target_present"] else "absent"
    return "absent" if str(example.get("status", "")).casefold() == "absent" else "present"


def main():
    parser = argparse.ArgumentParser(description="Validate synthetic present/absent VSGUI benchmark.")
    parser.add_argument("--reference", required=True, help="Original present-target JSON.")
    parser.add_argument("--dataset", required=True, help="Synthetic absent or mixed dataset JSON.")
    parser.add_argument("--target2text", default="")
    parser.add_argument("--output", default="", help="Optional JSON report output.")
    parser.add_argument("--fail-on-conflict", action="store_true")
    args = parser.parse_args()

    reference = load_json(Path(args.reference))
    dataset = load_json(Path(args.dataset))
    target2text = load_json(Path(args.target2text)) if args.target2text else {}

    image_to_target_ids = defaultdict(set)
    image_to_target_texts = defaultdict(set)
    for example in reference:
        image_to_target_ids[example["image"]].add(example.get("target_id", ""))
        text = norm(target_text(example, target2text))
        if text:
            image_to_target_texts[example["image"]].add(text)

    id_counts = Counter(example.get("img_usr_tgt", "") for example in dataset)
    duplicate_ids = [item for item, count in id_counts.items() if item and count > 1]
    status_counts = Counter(status(example) for example in dataset)

    conflicts = []
    missing_required_fields = []
    for idx, example in enumerate(dataset):
        missing = [field for field in ["img_usr_tgt", "image", "target_id", "target"] if field not in example]
        if missing:
            missing_required_fields.append({"index": idx, "missing": missing})

        if status(example) != "absent":
            continue

        image = example.get("image", "")
        text = norm(target_text(example, target2text))
        target_id = example.get("target_id", "")
        conflict_reasons = []
        if target_id in image_to_target_ids[image]:
            conflict_reasons.append("target_id_seen_in_destination_image")
        if text and text in image_to_target_texts[image]:
            conflict_reasons.append("target_text_seen_in_destination_image")
        if conflict_reasons:
            conflicts.append({
                "index": idx,
                "img_usr_tgt": example.get("img_usr_tgt"),
                "image": image,
                "target_id": target_id,
                "target": example.get("target"),
                "reasons": conflict_reasons,
            })

    report = {
        "num_examples": len(dataset),
        "status_counts": dict(status_counts),
        "duplicate_img_usr_tgt": len(duplicate_ids),
        "missing_required_fields": len(missing_required_fields),
        "annotation_conflicts": len(conflicts),
        "duplicate_examples": duplicate_ids[:20],
        "missing_required_field_examples": missing_required_fields[:20],
        "conflict_examples": conflicts[:20],
    }

    print(json.dumps(report, indent=2, ensure_ascii=False))
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        with open(output, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

    if args.fail_on_conflict and (conflicts or duplicate_ids or missing_required_fields):
        raise SystemExit("Validation failed")


if __name__ == "__main__":
    main()
