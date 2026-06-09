#!/usr/bin/env python
import argparse
import json
import os
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Build a small VSGUI subset with images that exist locally.")
    parser.add_argument("--data_dir", default=os.environ.get("SEEKUI_DATA_DIR", ""))
    parser.add_argument("--input", default="")
    parser.add_argument("--output", default="")
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()

    data_dir = Path(args.data_dir or Path(os.environ["SEEKUI_WORK"]) / "data")
    input_path = Path(args.input) if args.input else data_dir / "scanpath_train_explanation.json"
    output_path = Path(args.output) if args.output else data_dir / f"subset_available_{args.limit}.json"

    examples = json.loads(input_path.read_text(encoding="utf-8"))
    selected = []
    missing = 0

    for example in examples:
        image_path = data_dir / example["image"]
        if image_path.exists():
            selected.append(example)
            if len(selected) >= args.limit:
                break
        else:
            missing += 1

    if not selected:
        raise SystemExit(
            f"No examples with local images found. Checked {input_path}; "
            f"expected images under {data_dir / 'vsgui10k-images'}."
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(selected, indent=2), encoding="utf-8")

    print(f"Input examples : {len(examples)}")
    print(f"Missing skipped: {missing}")
    print(f"Subset size    : {len(selected)}")
    print(f"Output         : {output_path}")
    print("Images:")
    for example in selected:
        print(f"  {example['image']} target={example.get('target', example.get('target_id'))}")


if __name__ == "__main__":
    main()
