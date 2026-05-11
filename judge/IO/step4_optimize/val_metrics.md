# Step 4 — Optimized vs. baseline on 22-row val set

Train: 70 rows (stratified) · Val: 22 rows (7g/6y/9r) · seed=7
Model: `gemini/gemini-2.5-flash`  ·  Optimizer: `BootstrapFewShotWithRandomSearch`

## Headline

| metric | baseline | optimized | delta |
|---|---:|---:|---:|
| accuracy | 0.500 | 0.545 | +0.045 |
| green precision | 0.600 | 0.500 | -0.100 |
| green recall | 0.857 | 1.000 | +0.143 |
| green F1 | 0.706 | 0.667 | -0.039 |

## Confusion matrix — optimized (rows=human, cols=judge)

| human \ judge | green | yellow | red |
|---|---:|---:|---:|
| **green** | 7 | 0 | 0 |
| **yellow** | 5 | 0 | 1 |
| **red** | 2 | 2 | 5 |

## Confusion matrix — baseline on same val set

| human \ judge | green | yellow | red |
|---|---:|---:|---:|
| **green** | 6 | 1 | 0 |
| **yellow** | 3 | 0 | 3 |
| **red** | 1 | 3 | 5 |