from transformers import AutoProcessor, Qwen2_5_VLForConditionalGeneration
from qwen_vl_utils import process_vision_info
import torch

import argparse
import json
import math
import os
import re
from tqdm import tqdm


def parse_args():
    parser = argparse.ArgumentParser(description="Multi-sample target-present/absent scanpath prediction.")
    parser.add_argument("--model_path", required=True)
    parser.add_argument("--cache_dir", default="")
    parser.add_argument("--scanpath_test", required=True)
    parser.add_argument("--target2text", default="")
    parser.add_argument("--image_root", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--samples_per_example", type=int, default=5)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument("--top_p", type=float, default=0.9)
    parser.add_argument("--top_k", type=int, default=50)
    parser.add_argument("--max_new_tokens", type=int, default=256)
    parser.add_argument("--save_every", type=int, default=10)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--attn_implementation", default="auto", choices=["auto", "flash_attention_2", "sdpa"])
    return parser.parse_args()


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_results(results, output_path):
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    tmp_path = f"{output_path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    os.replace(tmp_path, output_path)


def load_model(args):
    major, _ = torch.cuda.get_device_capability()
    torch_dtype = torch.bfloat16 if major >= 8 else torch.float16
    attempts = ["flash_attention_2", "sdpa"] if args.attn_implementation == "auto" else [args.attn_implementation]
    last_error = None
    for attn in attempts:
        try:
            model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
                args.model_path,
                torch_dtype=torch_dtype,
                attn_implementation=attn,
                device_map="auto",
                cache_dir=args.cache_dir or None,
            )
            print(f"Loaded model with {attn} and {torch_dtype}")
            return model
        except Exception as exc:
            last_error = exc
            if args.attn_implementation != "auto":
                raise
            print(f"Failed to load with {attn}: {exc}")
    raise RuntimeError(f"Failed to load model. Last error: {last_error}") from last_error


def target_key(example):
    target_id = str(example.get("target_id", "") or "")
    return target_id[4:] if target_id.startswith("txt_") else target_id


def get_target_text(example, target2text):
    for key in ["query_text", "target", "original_target"]:
        text = str(example.get(key, "") or "")
        if text:
            return text
    return str(target2text.get(target_key(example), example.get("target_id", "")))


def example_key(example, idx):
    return str(example.get("img_usr_tgt") or example.get("key") or example.get("id") or idx)


def parse_answer(content):
    answer_match = re.search(r"<answer>(.*?)</answer>", content, flags=re.S | re.I)
    answer = answer_match.group(1).strip() if answer_match else content.strip()
    think_match = re.search(r"<think>(.*?)</think>", content, flags=re.S | re.I)
    thinking = think_match.group(1).strip() if think_match else ""

    status = "present"
    if re.search(r"\b(absent|not[ _-]?found|no object|no target|not present)\b", answer, flags=re.I):
        status = "absent"

    normalized = answer.replace("[ ", "[").replace(" ]", "]").replace(",", " ").replace("-", " ")
    points = [[int(x), int(y)] for x, y in re.findall(r"\[(\d+)\s+(\d+)\]", normalized)]
    return thinking, answer, status, points


def build_prompt(width, height, target):
    return (
        f"Given the image with width {width} and height {height}, perform a visual search task on this GUI. "
        f'The target cue is "{target}". The target may or may not be present in the GUI.\n'
        "Output the thinking process in <think> </think> and the final answer in <answer> </answer> tags.\n"
        "If the target is present, answer exactly: status: present; scanpath: [x1, y1] [x2, y2] ...\n"
        "If the target is absent, answer exactly: status: absent; scanpath: [x1, y1] [x2, y2] ...\n"
        "Please strictly follow the format.\n"
    )


def majority_status(samples):
    absent = sum(1 for sample in samples if sample.get("predicted_status") == "absent")
    return "absent" if absent > len(samples) / 2 else "present"


def representative_prediction(samples, width, height):
    for sample in samples:
        if sample.get("prediction"):
            return sample["prediction"]
    return [[math.floor(width / 2), math.floor(height / 2)]]


def main():
    args = parse_args()
    model = load_model(args)
    processor = AutoProcessor.from_pretrained(args.model_path, cache_dir=args.cache_dir or None)
    examples = load_json(args.scanpath_test)
    if args.limit > 0:
        examples = examples[:args.limit]
    target2text = load_json(args.target2text) if args.target2text else {}

    results = []
    completed = set()
    if args.resume and os.path.exists(args.output):
        results = load_json(args.output)
        completed = {str(item.get("multisample_key")) for item in results if item.get("multisample_key") is not None}
        print(f"Resuming from {args.output}: {len(completed)} completed examples")

    newly_processed = 0
    for idx, example in tqdm(list(enumerate(examples)), total=len(examples)):
        key = example_key(example, idx)
        if key in completed:
            continue

        width, height = int(example["width"]), int(example["height"])
        target = get_target_text(example, target2text)
        image_path = os.path.join(args.image_root, example["image"])
        prompt = build_prompt(width, height, target)
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image", "image": image_path},
                ],
            }
        ]
        text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        image_inputs, video_inputs = process_vision_info(messages)
        inputs = processor(
            text=[text],
            images=image_inputs,
            videos=video_inputs,
            padding=True,
            return_tensors="pt",
        ).to("cuda")

        samples = []
        for sample_idx in range(args.samples_per_example):
            with torch.no_grad():
                generated_ids = model.generate(
                    **inputs,
                    max_new_tokens=args.max_new_tokens,
                    do_sample=True,
                    temperature=args.temperature,
                    top_p=args.top_p,
                    top_k=args.top_k,
                )
            generated_ids_trimmed = [
                out_ids[len(in_ids):] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
            ]
            content = processor.batch_decode(
                generated_ids_trimmed,
                skip_special_tokens=True,
                clean_up_tokenization_spaces=False,
            )[0]
            thinking, answer, predicted_status, points = parse_answer(content)
            if not points:
                points = [[math.floor(width / 2), math.floor(height / 2)]]
            samples.append({
                "sample_index": sample_idx,
                "prediction": points,
                "predicted_status": predicted_status,
                "think": thinking,
                "answer": answer,
                "raw_output": content,
            })

        result = dict(example)
        result["multisample_key"] = key
        result["samples_per_example"] = args.samples_per_example
        result["multisample_samples"] = samples
        result["predicted_status"] = majority_status(samples)
        result["prediction"] = representative_prediction(samples, width, height)
        result["multisample_absent_votes"] = sum(1 for sample in samples if sample["predicted_status"] == "absent")
        results.append(result)
        newly_processed += 1

        if args.save_every > 0 and newly_processed % args.save_every == 0:
            save_results(results, args.output)
            print(f"Partial multi-sample predictions saved to {args.output} ({len(results)} results)")

    save_results(results, args.output)
    print(f"Multi-sample predictions saved to {args.output}")


if __name__ == "__main__":
    main()
