# Held-Out Image Split Result

Image split is the cleaner headline because it avoids shared images across dev/test.

| Model | Split | Prompt F1 | Combined F1 | Delta F1 95% CI | Prompt Acc | Combined Acc | Delta Acc 95% CI |
|---|---|---:|---:|---:|---:|---:|---:|
| SeekUI | image | 0.7347 | 0.8804 | [0.1167, 0.1739] | 0.7708 | 0.8692 | [0.0720, 0.1220] |
| SeekUI-SFT | image | 0.6744 | 0.8279 | [0.1232, 0.1834] | 0.7325 | 0.8148 | [0.0558, 0.1080] |
