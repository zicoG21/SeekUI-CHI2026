# Evidence-Aware VLM Image Split Result

Matched image split evaluation for the evidence-aware VLM verifier.

| Model | Split | Baseline | Verifier | Baseline F1 | Verifier F1 | Delta F1 95% CI | Baseline Acc | Verifier Acc | Delta Acc 95% CI | Present->Absent | Absent->Present |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| SeekUI | image | prompt_only | evidence-aware VLM | 0.7347 | 0.8962 | [0.1299, 0.1925] | 0.7708 | 0.8861 | [0.0867, 0.1433] | 142 | 13 |
