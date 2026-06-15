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
    parser = argparse.ArgumentParser(description="VLM target-presence baseline for image-cue UI search.")
    parser.add_argument("--model_path", required=True)
    parser.add_argument("--cache_dir", default="")
    parser.add_argument("--input_json", required=True)
    parser.add_argument("--image_root", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--max_new_tokens", type=int, default=32)
    parser.add_argument("--save_every", type=int, default=25)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--attn_implementation", default="auto", choices=["auto", "flash_attention_2", "sdpa"])
    parser.add_argument(
        "--prompt_variant",
        default="conservative",
        choices=["direct", "conservative", "search_behavior"],
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


def build_prompt(variant, width, height):
    common = (
        f"The first image is a GUI screenshot with width {width} and height {height}. "
        "The second image is the visual target cue. "
    )
    output_rule = (
        "Answer only in this format: <answer>status: present</answer> or "
        "<answer>status: absent</answer>. Do not provide coordinates."
    )
    if variant == "direct":
        instruction = "Check whether the target cue is visibly present in the GUI screenshot. "
    elif variant == "conservative":
        instruction = (
            "You are a conservative UI target-presence verifier. "
            "Only answer present if the visual target cue itself, or an unambiguous equivalent, "
            "is clearly visible in the GUI screenshot. If it is missing, hidden, ambiguous, or only weakly similar, "
            "answer absent. "
        )
    elif variant == "search_behavior":
        instruction = (
            "Imagine a user searching this UI screenshot for the visual target cue. "
            "Answer present only if the user would likely be able to find that target on this screen. "
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

        if not example.get("target_crop"):
            raise ValueError(f"Example {idx} is missing target_crop")

        width, height = int(example.get("width", 0)), int(example.get("height", 0))
        gui_image_path = os.path.join(args.image_root, example["image"])
        target_crop_path = os.path.join(args.image_root, example["target_crop"])
        prompt = build_prompt(args.prompt_variant, width, height)
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image", "image": gui_image_path},
                    {"type": "image", "image": target_crop_path},
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
        result["vlm_image_cue_presence_answer"] = answer
        result["raw_output"] = content
        results.append(result)
        newly_processed += 1

        if args.save_every > 0 and newly_processed % args.save_every == 0:
            save_results(results, args.output)
            print(f"Partial predictions saved to {args.output} ({len(results)} results)")

    save_results(results, args.output)
    print(f"VLM image-cue presence predictions saved to {args.output}")


if __name__ == "__main__":
    main()
