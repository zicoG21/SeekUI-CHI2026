#!/usr/bin/env python
import argparse
import json
import re
from pathlib import Path

import torch
from PIL import Image
from qwen_vl_utils import process_vision_info
from transformers import AutoProcessor, Qwen2_5_VLForConditionalGeneration


def parse_points(text):
    normalized = text.replace(",", " ").replace("[ ", "[").replace(" ]", "]")
    return [[int(x), int(y)] for x, y in re.findall(r"\[(\d+)\s+(\d+)\]", normalized)]


def load_model(model_path, cache_dir, attn_implementation):
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is not available. Run this script inside a GPU job.")

    major, _ = torch.cuda.get_device_capability()
    dtype = torch.bfloat16 if major >= 8 else torch.float16

    attempts = []
    if attn_implementation == "auto":
        attempts = ["flash_attention_2", "sdpa"]
    else:
        attempts = [attn_implementation]

    last_error = None
    for attn in attempts:
        try:
            model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
                model_path,
                torch_dtype=dtype,
                attn_implementation=attn,
                device_map="auto",
                cache_dir=cache_dir or None,
            )
            return model, attn, str(dtype)
        except Exception as exc:
            last_error = exc
            if attn_implementation != "auto":
                break

    raise RuntimeError(f"Failed to load model. Last error: {last_error}") from last_error


def main():
    parser = argparse.ArgumentParser(description="SeekUI one-image inference smoke test")
    parser.add_argument("--model_path", required=True)
    parser.add_argument("--image_path", default="demo/c3f5f9.png")
    parser.add_argument("--target_text", default="WOMEN")
    parser.add_argument("--cache_dir", default="")
    parser.add_argument("--output", default="demo_prediction.json")
    parser.add_argument("--max_new_tokens", type=int, default=256)
    parser.add_argument("--attn_implementation", default="auto", choices=["auto", "flash_attention_2", "sdpa"])
    args = parser.parse_args()

    image_path = Path(args.image_path)
    image = Image.open(image_path)
    image_width, image_height = image.size

    model, attn_used, dtype_used = load_model(args.model_path, args.cache_dir, args.attn_implementation)
    processor = AutoProcessor.from_pretrained(args.model_path, cache_dir=args.cache_dir or None)

    prompt = (
        f"Given the image with width {image_width} and height {image_height}, "
        f"what is the scanpath for the visual search task on this GUI? "
        f'The text on the target element is "{args.target_text}".\n'
        "Output the thinking process in <think> </think> and final answer in <answer> </answer> tags. "
        "The output answer format should be as follows:\n"
        "<think> ... </think> <answer>The scanpath is [x1, y1] [x2, y2] ...</answer>\n"
        "Please strictly follow the format.\n"
    )

    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image", "image": str(image_path)},
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
        generated_ids = model.generate(
            **inputs,
            max_new_tokens=args.max_new_tokens,
            do_sample=False,
        )

    generated_ids_trimmed = [
        out_ids[len(in_ids) :] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
    ]
    content = processor.batch_decode(
        generated_ids_trimmed,
        skip_special_tokens=True,
        clean_up_tokenization_spaces=False,
    )[0]

    think_match = re.search(r"<think>(.*?)</think>", content, flags=re.S)
    answer_match = re.search(r"<answer>(.*?)</answer>", content, flags=re.S)
    thinking = think_match.group(1).strip() if think_match else ""
    answer = answer_match.group(1).strip() if answer_match else content.strip()

    result = {
        "image": str(image_path),
        "target_text": args.target_text,
        "image_size": [image_width, image_height],
        "attn_implementation": attn_used,
        "dtype": dtype_used,
        "raw_output": content,
        "think": thinking,
        "answer": answer,
        "prediction": parse_points(answer),
    }

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")

    print(f"Saved smoke-test prediction to {output}")
    print(f"Parsed points: {result['prediction']}")


if __name__ == "__main__":
    main()
