#!/usr/bin/env python
import argparse
import json
import os
import re
from tqdm import tqdm


ABSENT_PATTERNS = [r"\babsent\b", r"\bnot\s*present\b", r"\bnot\s*visible\b", r"\bnot\s*found\b", r"\bno\b"]
PRESENT_PATTERNS = [r"\bpresent\b", r"\bvisible\b", r"\bfound\b", r"\byes\b"]


def parse_args():
    parser = argparse.ArgumentParser(description="Crop-level VLM verifier for annotation-free UI candidates.")
    parser.add_argument("--model_path", required=True)
    parser.add_argument("--cache_dir", default="")
    parser.add_argument("--crop_json", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--max_new_tokens", type=int, default=48)
    parser.add_argument("--save_every", type=int, default=50)
    parser.add_argument("--limit", type=int, default=0)
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
    from transformers import Qwen2_5_VLForConditionalGeneration
    import torch

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


def build_prompt(row):
    target = row.get("query_text", "")
    candidate_text = row.get("candidate_text", "")
    source = row.get("candidate_source", "")
    return (
        "You are verifying whether a cropped UI region contains a requested target.\n"
        f'Target cue: "{target}".\n'
        f'Candidate source: {source}. Candidate OCR text, if any: "{candidate_text}".\n'
        "Use the crop image as primary evidence. If the crop clearly contains the exact target, a near text variant, "
        "or an unambiguous icon/action equivalent, answer present. Otherwise answer absent.\n"
        "Answer only in this format: <answer>status: present</answer> or <answer>status: absent</answer>."
    )


def parse_status(content):
    answer = content.strip()
    match = re.search(r"<answer>(.*?)</answer>", content, flags=re.S | re.I)
    if match:
        answer = match.group(1).strip()
    lowered = answer.casefold()
    for pattern in ABSENT_PATTERNS:
        if re.search(pattern, lowered):
            return "absent", answer
    for pattern in PRESENT_PATTERNS:
        if re.search(pattern, lowered):
            return "present", answer
    return "absent", answer


def main():
    args = parse_args()
    from transformers import AutoProcessor
    from qwen_vl_utils import process_vision_info
    import torch

    model = load_model(args)
    processor = AutoProcessor.from_pretrained(args.model_path, cache_dir=args.cache_dir or None)
    rows = load_json(args.crop_json)
    if args.limit > 0:
        rows = rows[:args.limit]

    results = []
    completed = set()
    if args.resume and os.path.exists(args.output):
        results = load_json(args.output)
        completed = {row.get("candidate_uid") for row in results if row.get("candidate_uid")}
        print(f"Resuming from {args.output}: {len(completed)} completed candidates")

    newly_processed = 0
    for row in tqdm(rows, total=len(rows)):
        uid = row.get("candidate_uid")
        if uid in completed:
            continue
        prompt = build_prompt(row)
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image", "image": row["crop_image"]},
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
        status, answer = parse_status(content)
        result = dict(row)
        result["predicted_status"] = status
        result["crop_vlm_answer"] = answer
        result["raw_output"] = content
        results.append(result)
        newly_processed += 1

        if args.save_every > 0 and newly_processed % args.save_every == 0:
            save_results(results, args.output)
            print(f"Partial crop VLM predictions saved to {args.output} ({len(results)} results)")

    save_results(results, args.output)
    print(f"Crop VLM predictions saved to {args.output}")


if __name__ == "__main__":
    main()
