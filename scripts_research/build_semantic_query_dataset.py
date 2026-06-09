#!/usr/bin/env python
import argparse
import json
import random
from pathlib import Path


FUNCTIONAL_TEMPLATES = [
    "find the UI element for {target}",
    "look for the control labeled or meaning {target}",
    "find where a user would choose {target}",
    "locate the option related to {target}",
]

HANDWRITTEN_ASSOCIATIONS = {
    "login": ["sign in", "access my account", "enter the account"],
    "log in": ["sign in", "access my account", "enter the account"],
    "search": ["look for something", "type a query", "find the search field"],
    "cart": ["shopping basket", "saved shopping items", "checkout items"],
    "checkout": ["pay for the order", "finish the purchase", "complete shopping"],
    "settings": ["preferences", "configuration", "change options"],
    "delete": ["remove", "trash", "discard"],
    "back": ["return to the previous screen", "go back", "previous page"],
    "next": ["continue", "go forward", "advance"],
    "home": ["main page", "start page", "go to the homepage"],
    "profile": ["account page", "user information", "personal account"],
}


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def target_key(example):
    target_id = example.get("target_id", "")
    return target_id[4:] if target_id.startswith("txt_") else target_id


def get_target_text(example, target2text):
    explicit = str(example.get("target", "") or "")
    if explicit:
        return explicit
    return str(target2text.get(target_key(example), "") or "")


def normalize_key(text):
    return " ".join(str(text or "").casefold().replace("_", " ").replace("-", " ").split())


def build_queries(target, mapping):
    normalized = normalize_key(target)
    queries = [{"query_text": target, "query_type": "exact"}]

    if target and target.upper() != target:
        queries.append({"query_text": target.upper(), "query_type": "case_variant"})
    if target and target.lower() != target:
        queries.append({"query_text": target.lower(), "query_type": "case_variant"})

    for template in FUNCTIONAL_TEMPLATES:
        queries.append({"query_text": template.format(target=target), "query_type": "functional_template"})

    for query in mapping.get(normalized, []):
        queries.append({"query_text": query, "query_type": "association_mapping"})

    deduped = []
    seen = set()
    for query in queries:
        key = normalize_key(query["query_text"])
        if key in seen or not key:
            continue
        seen.add(key)
        deduped.append(query)
    return deduped


def main():
    parser = argparse.ArgumentParser(description="Build semantic/query-variant VSGUI benchmark.")
    parser.add_argument("--scanpath", required=True)
    parser.add_argument("--target2text", default="")
    parser.add_argument("--output", required=True)
    parser.add_argument("--mapping", default="", help="Optional JSON mapping from normalized target text to query variants.")
    parser.add_argument("--variants-per-example", type=int, default=2)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    examples = load_json(Path(args.scanpath))
    target2text = load_json(Path(args.target2text)) if args.target2text else {}
    mapping = dict(HANDWRITTEN_ASSOCIATIONS)
    if args.mapping:
        user_mapping = load_json(Path(args.mapping))
        for key, values in user_mapping.items():
            mapping[normalize_key(key)] = values

    output_examples = []
    source_examples = examples[: args.limit] if args.limit else examples
    for example in source_examples:
        target = get_target_text(example, target2text)
        queries = build_queries(target, mapping)
        exact = [query for query in queries if query["query_type"] == "exact"]
        non_exact = [query for query in queries if query["query_type"] != "exact"]
        rng.shuffle(non_exact)
        selected = exact + non_exact[: max(0, args.variants_per_example - len(exact))]

        for variant_index, query in enumerate(selected):
            result = dict(example)
            result["original_target"] = target
            result["query_text"] = query["query_text"]
            result["query_type"] = query["query_type"]
            result["img_usr_tgt"] = f"{example.get('img_usr_tgt', 'sample')}_query{variant_index}_{query['query_type']}"
            result.pop("conversations", None)
            output_examples.append(result)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w", encoding="utf-8") as f:
        json.dump(output_examples, f, indent=2, ensure_ascii=False)

    counts = {}
    for example in output_examples:
        counts[example["query_type"]] = counts.get(example["query_type"], 0) + 1
    print(f"Input examples : {len(source_examples)}")
    print(f"Output examples: {len(output_examples)}")
    print(f"Query types    : {counts}")
    print(f"Output         : {output}")


if __name__ == "__main__":
    main()
