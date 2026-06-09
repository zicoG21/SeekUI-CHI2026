#!/usr/bin/env python
import argparse
import json
import random
from collections import defaultdict
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


def strip_ground_truth(example):
    result = dict(example)
    result["x"] = []
    result["y"] = []
    result["t"] = []
    result["target_x"] = None
    result["target_y"] = None
    result["target_width"] = None
    result["target_height"] = None
    result["target_present"] = False
    result["status"] = "absent"
    result.pop("conversations", None)
    return result


def mark_present(example):
    result = dict(example)
    result["target_present"] = True
    result["status"] = "present"
    result.pop("conversations", None)
    return result


def make_unique_id(base, used_ids):
    candidate = base
    suffix = 1
    while candidate in used_ids:
        candidate = f"{base}_{suffix}"
        suffix += 1
    used_ids.add(candidate)
    return candidate


def main():
    parser = argparse.ArgumentParser(description="Build synthetic target-absent VSGUI trials.")
    parser.add_argument("--scanpath", required=True, help="Present-target scanpath JSON.")
    parser.add_argument("--target2text", default="", help="Optional target2text.json.")
    parser.add_argument("--output", required=True, help="Output absent-trial JSON.")
    parser.add_argument("--mixed-output", default="", help="Optional output with matched present and synthetic absent trials.")
    parser.add_argument("--limit", type=int, default=0, help="Maximum absent examples. 0 means all possible source examples.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-tries-per-example", type=int, default=200)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    examples = load_json(Path(args.scanpath))
    target2text = load_json(Path(args.target2text)) if args.target2text else {}

    image_to_examples = defaultdict(list)
    image_to_target_ids = defaultdict(set)
    image_to_target_texts = defaultdict(set)
    for example in examples:
        image = example["image"]
        image_to_examples[image].append(example)
        image_to_target_ids[image].add(example.get("target_id", ""))
        text = target_text(example, target2text).casefold().strip()
        if text:
            image_to_target_texts[image].add(text)

    images = list(image_to_examples)
    source_examples = list(examples)
    rng.shuffle(source_examples)
    if args.limit > 0:
        source_examples = source_examples[: args.limit]

    absent_examples = []
    present_examples = []
    used_img_usr_tgt = {example.get("img_usr_tgt", "") for example in examples if example.get("img_usr_tgt")}
    skipped = 0
    for source in source_examples:
        source_target_id = source.get("target_id", "")
        source_target_text = target_text(source, target2text)
        source_target_text_norm = source_target_text.casefold().strip()

        destination = None
        for _ in range(args.max_tries_per_example):
            candidate_image = rng.choice(images)
            if candidate_image == source.get("image"):
                continue
            if source_target_id in image_to_target_ids[candidate_image]:
                continue
            if source_target_text_norm and source_target_text_norm in image_to_target_texts[candidate_image]:
                continue
            destination = rng.choice(image_to_examples[candidate_image])
            break

        if destination is None:
            skipped += 1
            continue

        present_examples.append(mark_present(source))
        absent = strip_ground_truth(destination)
        destination_stem = destination["image"].split("/")[-1].split(".")[0]
        source_key = source.get("img_usr_tgt") or f"source_{len(absent_examples)}"
        absent_id_base = f"{destination_stem}_{destination.get('username', 'synthetic')}_{source_target_id}_{source_key}_absent"
        absent["img_usr_tgt"] = make_unique_id(absent_id_base, used_img_usr_tgt)
        absent["target_id"] = source_target_id
        absent["target"] = source_target_text
        absent["absent_source_img_usr_tgt"] = source.get("img_usr_tgt")
        absent["absent_source_image"] = source.get("image")
        absent["absent_destination_img_usr_tgt"] = destination.get("img_usr_tgt")
        absent["absent_construction"] = "cross_image_target_swap"
        absent_examples.append(absent)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w", encoding="utf-8") as f:
        json.dump(absent_examples, f, indent=2, ensure_ascii=False)

    if args.mixed_output:
        mixed = []
        for present, absent in zip(present_examples, absent_examples):
            mixed.append(present)
            mixed.append(absent)
        mixed_output = Path(args.mixed_output)
        mixed_output.parent.mkdir(parents=True, exist_ok=True)
        with open(mixed_output, "w", encoding="utf-8") as f:
            json.dump(mixed, f, indent=2, ensure_ascii=False)
        print(f"Mixed examples written : {len(mixed)}")
        print(f"Mixed output           : {mixed_output}")

    print(f"Input present examples : {len(examples)}")
    print(f"Requested sources      : {len(source_examples)}")
    print(f"Absent examples written: {len(absent_examples)}")
    print(f"Skipped sources        : {skipped}")
    print(f"Output                 : {output}")


if __name__ == "__main__":
    main()
