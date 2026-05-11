# Step 4b — Softer label-derivation rules (re-scoring baseline predictions)

Same 92 LLM tag-predictions, different ways of collapsing tags into a label.
No new API calls.

## Headline

| rule | accuracy | green-P | green-R | green-F1 |
|---|---:|---:|---:|---:|
| v1_any_red_wins (baseline) | 0.435 | 0.533 | 0.276 | **0.364** |
| v2_hard_vs_soft | 0.380 | 0.370 | 0.345 | **0.357** |
| v3_weighted | 0.446 | 0.450 | 0.621 | **0.522** |
| v4_greedy_green | 0.446 | 0.450 | 0.621 | **0.522** |
| v5_green_dominant | 0.435 | 0.439 | 0.621 | **0.514** |

## Best rule: `v3_weighted`

Confusion matrix (rows=human, cols=judge):

| human \ judge | green | yellow | red |
|---|---:|---:|---:|
| **green** | 18 | 3 | 8 |
| **yellow** | 9 | 5 | 12 |
| **red** | 13 | 6 | 18 |

## All confusion matrices

### `v1_any_red_wins (baseline)`

| human \ judge | green | yellow | red |
|---|---:|---:|---:|
| **green** | 8 | 8 | 13 |
| **yellow** | 3 | 5 | 18 |
| **red** | 4 | 6 | 27 |

### `v2_hard_vs_soft`

| human \ judge | green | yellow | red |
|---|---:|---:|---:|
| **green** | 10 | 11 | 8 |
| **yellow** | 7 | 10 | 9 |
| **red** | 10 | 12 | 15 |

### `v3_weighted`

| human \ judge | green | yellow | red |
|---|---:|---:|---:|
| **green** | 18 | 3 | 8 |
| **yellow** | 9 | 5 | 12 |
| **red** | 13 | 6 | 18 |

### `v4_greedy_green`

| human \ judge | green | yellow | red |
|---|---:|---:|---:|
| **green** | 18 | 3 | 8 |
| **yellow** | 9 | 8 | 9 |
| **red** | 13 | 9 | 15 |

### `v5_green_dominant`

| human \ judge | green | yellow | red |
|---|---:|---:|---:|
| **green** | 18 | 3 | 8 |
| **yellow** | 10 | 7 | 9 |
| **red** | 13 | 9 | 15 |
