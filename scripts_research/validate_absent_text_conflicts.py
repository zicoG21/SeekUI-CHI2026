#!/usr/bin/env python
import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from pathlib import Path


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


def target_key(example):
    target_id = example.get("target_id", "")
    return target_id[4:] if target_id.startswith("txt_") else target_id


def target_text(example, target2text):
    explicit = str(example.get("target", "") or "")
    if explicit:
        return explicit
    return str(target2text.get(target_key(example), "") or "")


def norm(text):
    text = str(text or "").casefold().replace("_", " ").replace("-", " ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def tokens(text):
    return {token for token in norm(text).split() if len(token) >= 2 and token not in STOPWORDS}


def status(example):
    if "target_present" in example:
        return "present" if example["target_present"] else "absent"
    return "absent" if str(example.get("status", "")).casefold() == "absent" else "present"


def similarity(a, b):
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def conflict_reason(query, candidate, min_fuzzy, min_token_overlap):
    q = norm(query)
    c = norm(candidate)
    if not q or not c:
        return None, 0.0
    if q == c:
        return "exact_text_match", 1.0
    if min(len(q), len(c)) >= 4 and (q in c or c in q):
        return "substring_text_match", 1.0
    q_tokens = tokens(q)
    c_tokens = tokens(c)
    if q_tokens and c_tokens:
        overlap = len(q_tokens & c_tokens) / len(q_tokens)
        if overlap >= min_token_overlap:
            return "token_overlap_match", overlap
    ratio = similarity(q, c)
    if ratio >= min_fuzzy:
        return "fuzzy_text_match", ratio
    return None, max(similarity(q, c), 0.0)


def build_image_text_index(reference, target2text):
    image_to_targets = defaultdict(list)
    for example in reference:
        text = target_text(example, target2text)
        if not norm(text):
            continue
        image_to_targets[example["image"]].append({
            "img_usr_tgt": example.get("img_usr_tgt", ""),
            "target_id": example.get("target_id", ""),
            "target": text,
            "target_box": [
                example.get("target_x"),
                example.get("target_y"),
                example.get("target_width"),
                example.get("target_height"),
            ],
        })
    return image_to_targets


def suspicious_matches(example, candidates, target2text, min_fuzzy, min_token_overlap, max_matches):
    query = target_text(example, target2text)
    matches = []
    for candidate in candidates:
        reason, score = conflict_reason(query, candidate["target"], min_fuzzy, min_token_overlap)
        if reason:
            matches.append({
                "reason": reason,
                "score": score,
                "candidate_target": candidate["target"],
                "candidate_target_id": candidate["target_id"],
                "candidate_img_usr_tgt": candidate["img_usr_tgt"],
                "candidate_target_box": candidate["target_box"],
            })
    matches.sort(key=lambda item: (item["reason"] != "exact_text_match", -item["score"], item["candidate_target"]))
    return matches[:max_matches]


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "index",
        "img_usr_tgt",
        "image",
        "target_id",
        "target",
        "num_matches",
        "top_reason",
        "top_score",
        "top_candidate_target",
        "top_candidate_target_id",
        "top_candidate_img_usr_tgt",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description="Find likely text conflicts in synthetic absent examples using destination-image annotations.")
    parser.add_argument("--reference", required=True, help="Original present-target JSON.")
    parser.add_argument("--dataset", required=True, help="Synthetic absent or mixed benchmark JSON.")
    parser.add_argument("--target2text", default="")
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--min-fuzzy", type=float, default=0.88)
    parser.add_argument("--min-token-overlap", type=float, default=1.0)
    parser.add_argument("--max-matches", type=int, default=5)
    args = parser.parse_args()

    reference = load_json(Path(args.reference))
    dataset = load_json(Path(args.dataset))
    target2text = load_json(Path(args.target2text)) if args.target2text else {}
    image_to_targets = build_image_text_index(reference, target2text)

    suspicious = []
    clean = []
    csv_rows = []
    reason_counts = Counter()

    for index, example in enumerate(dataset):
        if status(example) != "absent":
            continue
        image = example.get("image", "")
        matches = suspicious_matches(
            example,
            image_to_targets.get(image, []),
            target2text,
            args.min_fuzzy,
            args.min_token_overlap,
            args.max_matches,
        )
        if matches:
            enriched = dict(example)
            enriched["validation_matches"] = matches
            suspicious.append(enriched)
            reason_counts[matches[0]["reason"]] += 1
            csv_rows.append({
                "index": index,
                "img_usr_tgt": example.get("img_usr_tgt", ""),
                "image": image,
                "target_id": example.get("target_id", ""),
                "target": target_text(example, target2text),
                "num_matches": len(matches),
                "top_reason": matches[0]["reason"],
                "top_score": f"{matches[0]['score']:.4f}",
                "top_candidate_target": matches[0]["candidate_target"],
                "top_candidate_target_id": matches[0]["candidate_target_id"],
                "top_candidate_img_usr_tgt": matches[0]["candidate_img_usr_tgt"],
            })
        else:
            clean.append(example)

    out_dir = Path(args.out_dir)
    report = {
        "num_dataset_examples": len(dataset),
        "num_absent_examples": len(suspicious) + len(clean),
        "num_suspicious_absent": len(suspicious),
        "num_clean_absent": len(clean),
        "suspicious_rate": len(suspicious) / (len(suspicious) + len(clean)) if (suspicious or clean) else 0,
        "reason_counts": dict(reason_counts),
        "suspicious_preview": csv_rows[:20],
    }

    write_json(out_dir / "absent_text_conflict_report.json", report)
    write_json(out_dir / "absent_text_conflicts_suspicious.json", suspicious)
    write_json(out_dir / "absent_text_conflicts_clean.json", clean)
    write_csv(out_dir / "absent_text_conflicts_suspicious.csv", csv_rows)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"Report: {out_dir / 'absent_text_conflict_report.json'}")
    print(f"Suspicious CSV: {out_dir / 'absent_text_conflicts_suspicious.csv'}")


if __name__ == "__main__":
    main()
