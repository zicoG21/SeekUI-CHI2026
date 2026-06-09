from transformers import Qwen2_5_VLForConditionalGeneration, AutoProcessor
from qwen_vl_utils import process_vision_info
import torch

import argparse
import json
import math
import os
import re
from tqdm import tqdm


def parse_args():
    parser = argparse.ArgumentParser(description="Scanpath prediction with target-present/absent status.")
    parser.add_argument("--model_path", required=True)
    parser.add_argument("--cache_dir", default="")
    parser.add_argument("--scanpath_test", required=True)
    parser.add_argument("--target2text", default="")
    parser.add_argument("--image_root", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--max_new_tokens", type=int, default=256)
    parser.add_argument("--save_every", type=int, default=10)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--attn_implementation", default="auto", choices=["auto", "flash_attention_2", "sdpa"])
    return parser.parse_args()


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


def save_results(results, output_path):
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    tmp_path = f"{output_path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    os.replace(tmp_path, output_path)


def get_target_text(example, target2text):
    if example.get("query_text"):
        return str(example["query_text"])
    if example.get("target"):
        return str(example["target"])
    target_id = example.get("target_id", "")
    target_key = target_id[4:] if target_id.startswith("txt_") else target_id
    return str(target2text.get(target_key, target_id))


def parse_answer(content):
    answer_match = re.search(r"<answer>(.*?)</answer>", content, flags=re.S)
    answer = answer_match.group(1).strip() if answer_match else content.strip()
    think_match = re.search(r"<think>(.*?)</think>", content, flags=re.S)
    thinking = think_match.group(1).strip() if think_match else ""

    status = "present"
    if re.search(r"\b(absent|not[ _-]?found|no object|no target|not present)\b", answer, flags=re.I):
        status = "absent"

    normalized = answer.replace("[ ", "[").replace(" ]", "]").replace(",", " ").replace("-", " ")
    points = [[int(x), int(y)] for x, y in re.findall(r"\[(\d+)\s+(\d+)\]", normalized)]
    return thinking, answer, status, points


def main():
    args = parse_args()
    model = load_model(args)
    processor = AutoProcessor.from_pretrained(args.model_path, cache_dir=args.cache_dir or None)
    examples = json.load(open(args.scanpath_test, "r", encoding="utf-8"))
    target2text = json.load(open(args.target2text, "r", encoding="utf-8")) if args.target2text else {}

    results = []
    completed = set()
    if args.resume and os.path.exists(args.output):
        results = json.load(open(args.output, "r", encoding="utf-8"))
        completed = {example.get("img_usr_tgt") for example in results if example.get("img_usr_tgt")}
        print(f"Resuming from {args.output}: {len(completed)} completed examples")

    newly_processed = 0
    for idx in tqdm(range(len(examples)), total=len(examples)):
        example = examples[idx]
        sample_id = example.get("img_usr_tgt")
        if sample_id in completed:
            continue

        width, height = int(example["width"]), int(example["height"])
        target = get_target_text(example, target2text)
        image_path = os.path.join(args.image_root, example["image"])

        prompt = (
            f"Given the image with width {width} and height {height}, perform a visual search task on this GUI. "
            f'The target cue is "{target}". The target may or may not be present in the GUI.\n'
            "Output the thinking process in <think> </think> and the final answer in <answer> </answer> tags.\n"
            "If the target is present, answer exactly: status: present; scanpath: [x1, y1] [x2, y2] ...\n"
            "If the target is absent, answer exactly: status: absent; scanpath: [x1, y1] [x2, y2] ...\n"
            "Please strictly follow the format.\n"
        )

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

        with torch.no_grad():
            generated_ids = model.generate(**inputs, max_new_tokens=args.max_new_tokens, do_sample=False)
        generated_ids_trimmed = [
            out_ids[len(in_ids):] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
        ]
        content = processor.batch_decode(
            generated_ids_trimmed,
            skip_special_tokens=True,
            clean_up_tokenization_spaces=False,
        )[0]

        thinking, answer, predicted_status, points = parse_answer(content)
        result = dict(example)
        result["prediction"] = points
        result["predicted_status"] = predicted_status
        result["think"] = thinking
        result["answer"] = answer
        result["raw_output"] = content
        if len(points) == 0:
            result["prediction"] = [[math.floor(width / 2), math.floor(height / 2)]]
            result["prediction_fallback"] = "image_center"
        results.append(result)
        newly_processed += 1

        if args.save_every > 0 and newly_processed % args.save_every == 0:
            save_results(results, args.output)
            print(f"Partial predictions saved to {args.output} ({len(results)} results)")

    save_results(results, args.output)
    print(f"Predictions saved to {args.output}")


if __name__ == "__main__":
    main()
