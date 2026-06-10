import argparse
import json
import os
import re
from tqdm import tqdm


ABSENT_PATTERNS = [
    r"\babsent\b",
    r"\bnot\s*present\b",
    r"\bnot\s*visible\b",
    r"\bnot\s*found\b",
    r"\bno\b",
]
PRESENT_PATTERNS = [
    r"\bpresent\b",
    r"\bvisible\b",
    r"\bfound\b",
    r"\byes\b",
]


def parse_args():
    parser = argparse.ArgumentParser(description="VLM yes/no target-presence baseline for UI screenshots.")
    parser.add_argument("--model_path", required=True)
    parser.add_argument("--cache_dir", default="")
    parser.add_argument("--input_json", required=True)
    parser.add_argument("--target2text", default="")
    parser.add_argument("--image_root", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--max_new_tokens", type=int, default=32)
    parser.add_argument("--save_every", type=int, default=25)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--attn_implementation", default="auto", choices=["auto", "flash_attention_2", "sdpa"])
    parser.add_argument(
        "--prompt_variant",
        default="direct",
        choices=["direct", "conservative", "ocr_aware", "search_behavior"],
        help="Presence-check prompt framing to use for VLM baseline ablations.",
    )
    return parser.parse_args()


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


def save_results(results, output_path):
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    tmp_path = f"{output_path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    os.replace(tmp_path, output_path)


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def target_key(example):
    target_id = str(example.get("target_id", "") or "")
    return target_id[4:] if target_id.startswith("txt_") else target_id


def get_target_text(example, target2text):
    for key in ["query_text", "target", "original_target"]:
        text = str(example.get(key, "") or "")
        if text:
            return text
    return str(target2text.get(target_key(example), example.get("target_id", "")))


def build_prompt(variant, target, width, height):
    common = (
        f"The screenshot width is {width} and height is {height}. "
        f'Target cue: "{target}".\n'
    )
    output_rule = (
        "Answer only in this format: <answer>status: present</answer> or "
        "<answer>status: absent</answer>. Do not provide coordinates."
    )
    if variant == "direct":
        instruction = "You are checking whether a UI target is visible in a screenshot. "
    elif variant == "conservative":
        instruction = (
            "You are a conservative UI target-presence verifier. "
            "Only answer present if the target is clearly visible in the screenshot; "
            "if it is missing, ambiguous, hidden, or only weakly related, answer absent. "
        )
    elif variant == "ocr_aware":
        instruction = (
            "You are checking UI text and close visual matches in a screenshot. "
            "Look for exact text, near text variants, or an obvious visual match to the target cue. "
            "If no such visible match appears, answer absent. "
        )
    elif variant == "search_behavior":
        instruction = (
            "Imagine a user searching this UI screenshot for the target. "
            "Answer present only if the user would likely be able to find the requested target on this screen. "
            "If the user would not find it on this screen, answer absent. "
        )
    else:
        raise ValueError(f"Unknown prompt variant: {variant}")
    return instruction + common + output_rule


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
    return "present", answer


def main():
    args = parse_args()
    from transformers import AutoProcessor
    from qwen_vl_utils import process_vision_info
    import torch

    model = load_model(args)
    processor = AutoProcessor.from_pretrained(args.model_path, cache_dir=args.cache_dir or None)
    examples = load_json(args.input_json)
    if args.limit > 0:
        examples = examples[:args.limit]
    target2text = load_json(args.target2text) if args.target2text else {}

    results = []
    completed = set()
    if args.resume and os.path.exists(args.output):
        results = load_json(args.output)
        completed = {example.get("img_usr_tgt") for example in results if example.get("img_usr_tgt")}
        print(f"Resuming from {args.output}: {len(completed)} completed examples")

    newly_processed = 0
    for idx in tqdm(range(len(examples)), total=len(examples)):
        example = examples[idx]
        sample_id = example.get("img_usr_tgt")
        if sample_id in completed:
            continue

        width, height = int(example.get("width", 0)), int(example.get("height", 0))
        target = get_target_text(example, target2text)
        image_path = os.path.join(args.image_root, example["image"])
        prompt = build_prompt(args.prompt_variant, target, width, height)
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
        status, answer = parse_status(content)
        result = dict(example)
        result["prediction"] = []
        result["predicted_status"] = status
        result["prompt_variant"] = args.prompt_variant
        result["vlm_presence_answer"] = answer
        result["raw_output"] = content
        results.append(result)
        newly_processed += 1

        if args.save_every > 0 and newly_processed % args.save_every == 0:
            save_results(results, args.output)
            print(f"Partial predictions saved to {args.output} ({len(results)} results)")

    save_results(results, args.output)
    print(f"VLM presence predictions saved to {args.output}")


if __name__ == "__main__":
    main()
