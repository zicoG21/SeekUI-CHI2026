#!/usr/bin/env python
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
    parser = argparse.ArgumentParser(
        description="Evidence-aware VLM target-presence verifier for UI screenshots."
    )
    parser.add_argument("--model_path", required=True)
    parser.add_argument("--cache_dir", default="")
    parser.add_argument("--input_json", required=True)
    parser.add_argument("--target2text", default="")
    parser.add_argument("--image_root", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--max_new_tokens", type=int, default=64)
    parser.add_argument("--save_every", type=int, default=25)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--attn_implementation", default="auto", choices=["auto", "flash_attention_2", "sdpa"])
    parser.add_argument(
        "--prompt_variant",
        default="evidence_aware",
        choices=["evidence_aware", "evidence_conservative", "evidence_rescue_present"],
        help="How strongly the prompt should use scanpath/OCR evidence.",
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


def safe_float(value, default=0.0):
    try:
        if value in {"", None}:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def normalize_status(value, default="present"):
    text = str(value or default).strip().casefold()
    if text in {"absent", "not_found", "not found", "no object", "no target", "not present"}:
        return "absent"
    return "present"


def evidence_summary(example):
    path_score = safe_float(example.get("path_best_evidence"), default=-1.0)
    ocr_score = safe_float(
        example.get("ocr_candidate_verifier_score", example.get("color_aware_score")),
        default=-1.0,
    )
    ocr_text = str(
        example.get("ocr_candidate_verifier_text", example.get("color_aware_ocr_text", "")) or ""
    ).strip()
    color_score = safe_float(example.get("color_aware_color_score"), default=-1.0)
    text_score = safe_float(example.get("color_aware_text_score"), default=-1.0)
    requested_color = str(example.get("color_aware_requested_color", "") or "").strip()
    combined = normalize_status(example.get("predicted_status"), default="present")
    original = normalize_status(example.get("original_predicted_status"), default=combined)
    rule = str(example.get("combined_verifier_rule", "") or example.get("color_aware_verifier_rule", "") or "")
    mode = str(example.get("combined_verifier_mode", "") or "")
    cog_threshold = example.get("combined_cognitive_threshold", example.get("color_aware_cognitive_threshold", ""))
    ocr_threshold = example.get("combined_ocr_threshold", example.get("color_aware_score_threshold", ""))
    if not ocr_text:
        ocr_text = "none"
    return {
        "path_score": path_score,
        "ocr_score": ocr_score,
        "ocr_text": ocr_text,
        "color_score": color_score,
        "text_score": text_score,
        "requested_color": requested_color,
        "combined": combined,
        "original": original,
        "rule": rule,
        "mode": mode,
        "cog_threshold": cog_threshold,
        "ocr_threshold": ocr_threshold,
    }


def build_prompt(variant, target, width, height, evidence):
    common = (
        f"The screenshot width is {width} and height is {height}.\n"
        f'Target cue: "{target}".\n'
        "Additional machine evidence from a previous UI-search model:\n"
        f"- Original scanpath model status: {evidence['original']}\n"
        f"- Combined scanpath/OCR status: {evidence['combined']}\n"
        f"- Scanpath target-evidence score: {evidence['path_score']:.4f}\n"
        f"- OCR target-match score: {evidence['ocr_score']:.4f}\n"
        f"- Best OCR text match: \"{evidence['ocr_text']}\"\n"
    )
    if evidence.get("requested_color") or evidence.get("color_score", -1.0) >= 0 or evidence.get("text_score", -1.0) >= 0:
        common += (
            f"- Requested color, if parsed: \"{evidence['requested_color'] or 'none'}\"\n"
            f"- Color-aware text score: {evidence['text_score']:.4f}\n"
            f"- Color-aware color score: {evidence['color_score']:.4f}\n"
        )
    if evidence["rule"]:
        common += (
            f"- Combined rule: {evidence['rule']} / {evidence['mode']} "
            f"(path threshold={evidence['cog_threshold']}, OCR threshold={evidence['ocr_threshold']})\n"
        )

    output_rule = (
        "Use the screenshot as primary evidence. The machine evidence can help, but it may be wrong.\n"
        "Answer only in this format: <answer>status: present</answer> or "
        "<answer>status: absent</answer>. Do not provide coordinates."
    )

    if variant == "evidence_aware":
        instruction = (
            "You are an evidence-aware UI target-presence verifier. Decide whether the requested target is "
            "visibly present in the screenshot. "
        )
    elif variant == "evidence_conservative":
        instruction = (
            "You are a conservative evidence-aware UI verifier. Answer present only when the screenshot clearly "
            "contains the requested target. If the visual evidence is ambiguous or only weakly related, answer absent. "
        )
    elif variant == "evidence_rescue_present":
        instruction = (
            "You are checking whether a combined scanpath/OCR verifier may have over-rejected a visible target. "
            "If the screenshot visibly contains the requested target despite weak machine evidence, answer present. "
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
        evidence = evidence_summary(example)
        prompt = build_prompt(args.prompt_variant, target, width, height, evidence)
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
        result["previous_predicted_status"] = evidence["combined"]
        result["predicted_status"] = status
        result["prompt_variant"] = args.prompt_variant
        result["vlm_evidence_answer"] = answer
        result["raw_output"] = content
        results.append(result)
        newly_processed += 1

        if args.save_every > 0 and newly_processed % args.save_every == 0:
            save_results(results, args.output)
            print(f"Partial predictions saved to {args.output} ({len(results)} results)")

    save_results(results, args.output)
    print(f"Evidence-aware VLM predictions saved to {args.output}")


if __name__ == "__main__":
    main()
