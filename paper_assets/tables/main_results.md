# Main Present/Absent Results

Full synthetic present/absent benchmark. Rows emphasize practical baselines and verifier variants.

| Model | Family | Variant | N | Acc | Precision | Recall | F1 | Present->Absent | Absent->Present |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| SeekUI | seekui_prompt | prompt_only | 2724 | 0.7684 | 0.8749 | 0.6263 | 0.7300 | 122 | 509 |
| SeekUI | cognitive | cognitive_stop_present_only | 2724 | 0.8414 | 0.7981 | 0.9141 | 0.8522 | 315 | 117 |
| SeekUI | combined | combined_and_present_only_best_f1 | 2724 | 0.8711 | 0.8115 | 0.9670 | 0.8824 | 306 | 45 |
| SeekUI | vlm_presence | vlm_presence_direct | 2724 | 0.8510 | 0.9142 | 0.7746 | 0.8386 | 99 | 307 |
| SeekUI | vlm_evidence | vlm_evidence_evidence_aware | 2724 | 0.8891 | 0.8308 | 0.9772 | 0.8981 | 271 | 31 |
| SeekUI_sft | seekui_prompt | prompt_only | 2724 | 0.7430 | 0.8761 | 0.5661 | 0.6878 | 109 | 591 |
| SeekUI_sft | combined | combined_and_present_only_best_f1 | 2724 | 0.8278 | 0.7853 | 0.9023 | 0.8398 | 336 | 133 |
