from transformers import Qwen2_5_VLForConditionalGeneration, AutoTokenizer, AutoProcessor
from qwen_vl_utils import process_vision_info
import torch

from PIL import Image, ImageDraw, ImageFont
import matplotlib.pyplot as plt
import re
import json
import argparse

import csv
import os
import math
from tqdm import tqdm


def save_results(results, output_path):
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    tmp_path = f"{output_path}.tmp"
    with open(tmp_path, "w") as f:
        json.dump(results, f, indent=4)
    os.replace(tmp_path, output_path)


def load_csv(csv_file, target2text, output_path="qwen-vl-finetune/scanpath_test.json"):
    scanpath = {}

    if "text" in os.path.basename(csv_file):
        target_type = "text"
    elif "image" in os.path.basename(csv_file):
        target_type = "image"
    else:
        raise NotImplementedError

    with open(csv_file, 'r') as file:
        reader = csv.DictReader(file)
        for row in reader:
            img_usr_tgt = row['img_usr_tgt']
            image = f"vsgui10k-images/{row['image']}.png"
            width = float(row['width'])
            height = float(row['height'])
            username = row['username']
            target_id = row['target_id']
            target_x = float(row['target_x'])
            target_y = float(row['target_y'])
            target_width = float(row['target_width'])
            target_height = float(row['target_height'])
            x = float(row['x'])
            y = float(row['y'])
            t = float(row['t'])

            if img_usr_tgt not in scanpath:
                scanpath[img_usr_tgt] = {
                    "img_usr_tgt": img_usr_tgt,
                    "image": image,
                    "width": width,
                    "height": height,
                    "username": username,
                    "target_id": target_id,
                    "target_x": target_x,
                    "target_y": target_y,
                    "target_width": target_width,
                    "target_height": target_height,
                    "x": [],
                    "y": [],
                    "t": [],
                    "target": target2text[target_id[4:]] if target_type == "text" else None
                }

            scanpath[img_usr_tgt]["x"].append(math.floor(x))
            scanpath[img_usr_tgt]["y"].append(math.floor(y))
            scanpath[img_usr_tgt]["t"].append(t)

    scanpath = list(scanpath.values())
    json.dump(scanpath, open(output_path, 'w'))
    return scanpath


def parse_args():
    parser = argparse.ArgumentParser(description="Scanpath prediction inference (with thinking)")
    parser.add_argument("--model_path", type=str,
                        default="/mnt/tidal-alsh-share2/dataset/csa_ali/guozixin/private_model/SeekUI2",
                        help="Path to the pretrained model checkpoint")
    parser.add_argument("--cache_dir", type=str,
                        default="",
                        help="Cache directory for the model")
    parser.add_argument("--scanpath_test", type=str,
                        default="vsgui/scanpath_test.json",
                        help="Path to the cached test scanpath JSON file")
    parser.add_argument("--target2text", type=str,
                        default="vsgui/target2text.json",
                        help="Path to the target-to-text mapping JSON file")
    parser.add_argument("--test_data_path", type=str,
                        default="vsgui/length20_test_text.csv",
                        help="Path to the test CSV data file")
    parser.add_argument("--image_root", type=str,
                        default="vsgui",
                        help="Root directory for images")
    parser.add_argument("--output", type=str,
                        default="test_predictions_seekui_test2.json",
                        help="Path to the output prediction JSON file")
    parser.add_argument("--max_new_tokens", type=int,
                        default=512,
                        help="Maximum number of new tokens to generate")
    parser.add_argument("--attn_implementation", type=str,
                        default="auto",
                        choices=["auto", "flash_attention_2", "sdpa"],
                        help="Attention implementation. Use auto to try flash_attention_2, then sdpa.")
    parser.add_argument("--save_every", type=int,
                        default=10,
                        help="Save partial results every N newly processed examples")
    parser.add_argument("--resume", action="store_true",
                        help="Resume from an existing output file by skipping completed img_usr_tgt entries")
    return parser.parse_args()


def main():
    args = parse_args()

    major, _ = torch.cuda.get_device_capability()
    torch_dtype = torch.bfloat16 if major >= 8 else torch.float16
    attn_attempts = (
        ["flash_attention_2", "sdpa"]
        if args.attn_implementation == "auto"
        else [args.attn_implementation]
    )
    last_error = None
    for attn_implementation in attn_attempts:
        try:
            model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
                args.model_path,
                torch_dtype=torch_dtype,
                attn_implementation=attn_implementation,
                device_map="auto",
                cache_dir=args.cache_dir
            )
            print(f"Loaded model with {attn_implementation} and {torch_dtype}")
            break
        except Exception as exc:
            last_error = exc
            if args.attn_implementation != "auto":
                raise
            print(f"Failed to load with {attn_implementation}: {exc}")
    else:
        raise RuntimeError(f"Failed to load model. Last error: {last_error}") from last_error
    processor = AutoProcessor.from_pretrained(args.model_path, cache_dir=args.cache_dir)

    # Load data
    target2txt = json.load(open(args.target2text, "r"))

    if not os.path.exists(args.scanpath_test):
        scanpath_test = load_csv(args.test_data_path, target2txt, output_path=args.scanpath_test)
    else:
        scanpath_test = json.load(open(args.scanpath_test, "r"))

    scanpath_example = scanpath_test

    results = []
    completed_ids = set()
    if args.resume and os.path.exists(args.output):
        results = json.load(open(args.output, "r"))
        completed_ids = {example.get("img_usr_tgt") for example in results if example.get("img_usr_tgt")}
        print(f"Resuming from {args.output}: {len(completed_ids)} completed examples")

    newly_processed = 0
    for idx in tqdm(range(len(scanpath_example)), total=len(scanpath_example)):
        sample_id = scanpath_example[idx].get("img_usr_tgt")
        if sample_id in completed_ids:
            continue

        example_width, example_height = int(scanpath_example[idx]["width"]), int(scanpath_example[idx]["height"])
        example_image = scanpath_example[idx]["image"]
        example_target_id = scanpath_example[idx]["target_id"][4:]
        example_target = target2txt[example_target_id]
        example_target_x = math.floor(scanpath_example[idx]["target_x"] + scanpath_example[idx]["target_width"] / 2)
        example_target_y = math.floor(scanpath_example[idx]["target_y"] + scanpath_example[idx]["target_height"] / 2)

        messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": f"Given the image with width {example_width} and height {example_height}, what is the scanpath for the visual search task on this GUI? The text on the target element is \"{example_target}\".\nOutput the thinking process in <think> </think> and final answer in <answer> </answer> tags. The output answer format should be as follows:\n<think> ... </think> <answer>The scanpath is [x1, y1] [x2, y2] ...</answer>\nPlease strictly follow the format.\n"},
                        {
                            "type": "image",
                            "image": f"{args.image_root}/{example_image}",
                        },
                    ],
                }
            ]

        text = processor.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        image_inputs, video_inputs = process_vision_info(messages)
        inputs = processor(
            text=[text],
            images=image_inputs,
            videos=video_inputs,
            padding=True,
            return_tensors="pt",
        )
        inputs = inputs.to("cuda")

        # Inference: Generation of the output
        with torch.no_grad():
            generated_ids = model.generate(**inputs, max_new_tokens=args.max_new_tokens, do_sample=False)
        generated_ids_trimmed = [
            out_ids[len(in_ids) :] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
        ]
        output_text = processor.batch_decode(
            generated_ids_trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False
        )
        content = output_text[0]

        think_match = re.search(r'<think>(.*?)</think>', content)
        think_answer = think_match.group(1).strip() if think_match else content.strip()

        answer_match = re.search(r'<answer>(.*?)</answer>', content)
        scanpath_answer = answer_match.group(1).strip() if answer_match else content.strip()

        # Load the image using PIL
        image = Image.open(messages[0]["content"][1]["image"]).convert("RGB")

        # Extract scanpath points from the sentence
        sentence = scanpath_answer
        sentence = sentence.replace("[ ", "[")
        sentence = sentence.replace(" ]", "]")
        sentence = sentence.replace(",", " ")
        sentence = sentence.replace("-", " ")
        points = re.findall(r'\[(\d+) \s*(\d+)\]', sentence)
        points = [[int(x), int(y)] for x, y in points]

        cur_example = scanpath_example[idx]
        cur_example["prediction"] = points
        cur_example["think"] = think_answer
        cur_example["raw_output"] = content
        cur_example["answer"] = scanpath_answer
        if len(points) == 0:
            print(f"Warning: no points parsed for index {idx}, sample {cur_example.get('img_usr_tgt', idx)}")
        results.append(cur_example)
        newly_processed += 1

        if args.save_every > 0 and newly_processed % args.save_every == 0:
            save_results(results, args.output)
            print(f"Partial predictions saved to {args.output} ({len(results)} results)")

    save_results(results, args.output)
    print(f"Predictions saved to {args.output}")


if __name__ == "__main__":
    main()
