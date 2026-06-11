# Realistic Absent Validation

Small manually reviewed external-validity check with 50 present and 50 realistic absent examples.

| Model | Family | Variant | N | Acc | Precision | Recall | F1 | Present->Absent | Absent->Present |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| SeekUI | seekui_prompt | prompt_only_real_absent | 100 | 0.8200 | 0.9444 | 0.6800 | 0.7907 | 2 | 16 |
| SeekUI | combined | combined_and_present_only_best_f1 | 100 | 0.9100 | 0.8596 | 0.9800 | 0.9159 | 8 | 1 |
| SeekUI | combined | combined_and_present_only | 100 | 0.8600 | 0.9091 | 0.8000 | 0.8511 | 4 | 10 |
| SeekUI | vlm_presence | vlm_presence_real_absent_conservative | 100 | 0.8800 | 0.8276 | 0.9600 | 0.8889 | 10 | 2 |
| SeekUI | vlm_presence | vlm_presence_real_absent_ocr_aware | 100 | 0.8800 | 0.8654 | 0.9000 | 0.8824 | 7 | 5 |
| SeekUI | vlm_presence | vlm_presence_real_absent_search_behavior | 100 | 0.8800 | 0.9130 | 0.8400 | 0.8750 | 4 | 8 |
| SeekUI | vlm_presence | vlm_presence_real_absent_direct | 100 | 0.8600 | 0.8913 | 0.8200 | 0.8542 | 5 | 9 |
