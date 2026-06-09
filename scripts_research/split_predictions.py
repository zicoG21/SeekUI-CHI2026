#!/usr/bin/env python
import argparse
import json
import re
from collections import defaultdict
from pathlib import Path


def safe_value(value):
    text = str(value if value is not None else "missing")
    text = text.strip() or "missing"
    text = re.sub(r"[^A-Za-z0-9_.-]+", "_", text)
    return text[:120]


def nested_get(item, field):
    current = item
    for part in field.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def main():
    parser = argparse.ArgumentParser(description="Split prediction JSON by a field such as query_type or target_cue_type.")
    parser.add_argument("--predictions", required=True)
    parser.add_argument("--field", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--prefix", default="")
    parser.add_argument("--min-count", type=int, default=1)
    parser.add_argument("--manifest", default="")
    args = parser.parse_args()

    predictions_path = Path(args.predictions)
    data = json.load(open(predictions_path, "r", encoding="utf-8"))
    groups = defaultdict(list)
    for item in data:
        value = nested_get(item, args.field)
        groups[safe_value(value)].append(item)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    prefix = args.prefix or predictions_path.stem
    manifest = []
    for value, items in sorted(groups.items()):
        if len(items) < args.min_count:
            continue
        output = out_dir / f"{prefix}_{args.field.replace('.', '_')}_{value}.json"
        with open(output, "w", encoding="utf-8") as f:
            json.dump(items, f, indent=2, ensure_ascii=False)
        manifest.append({
            "field": args.field,
            "value": value,
            "count": len(items),
            "path": str(output),
        })

    manifest_path = Path(args.manifest) if args.manifest else out_dir / f"{prefix}_{args.field.replace('.', '_')}_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print(f"Input examples : {len(data)}")
    print(f"Groups written : {len(manifest)}")
    print(f"Manifest       : {manifest_path}")
    for row in manifest:
        print(f"  {row['value']}: {row['count']} -> {row['path']}")


if __name__ == "__main__":
    main()
