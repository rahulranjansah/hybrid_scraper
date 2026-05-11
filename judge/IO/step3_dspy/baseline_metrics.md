# Zero-shot baseline — 92 colored Crocs rows

Model: `gemini/gemini-2.5-flash` · rubric: v1 · JD: Crocs HR Manager
No training, no few-shot, no DSPy optimization. Pure prompt + rubric.

- Total candidates: **92**
- Errored calls: **0**
- Valid predictions: **92**
- Overall flag agreement: **40/92 = 43.5%**

## Confusion matrix (rows = human, cols = judge)

| human \ judge | green | yellow | red |
|---|---:|---:|---:|
| **green** | 8 | 8 | 13 |
| **yellow** | 3 | 5 | 18 |
| **red** | 4 | 6 | 27 |

## Green metrics (primary — aim for green)

- Green predictions: **15**
- True greens in data: **29**
- True positives: **8**
- **Green precision:** 0.533  (of predicted-green, how many were really green)
- **Green recall:** 0.276     (of real greens, how many did we find)
- **Green F1:** 0.364

## Per-flag agreement

| human | n | correct | rate |
|---|---:|---:|---:|
| green | 29 | 8 | 27.6% |
| yellow | 26 | 5 | 19.2% |
| red | 37 | 27 | 73.0% |

## Tag frequency across all 92 predictions

| tag | count |
|---|---:|
| `multinational_hr_experience` | 78 |
| `clean_long_tenure` | 47 |
| `level_matches_brief` | 39 |
| `relevant_industry_adjacency` | 34 |
| `level_too_senior_for_brief` | 29 |
| `bilingual_en_ja` | 29 |
| `sector_mismatch` | 25 |
| `recently_joined` | 24 |
| `short_current_tenure` | 15 |
| `job_hopper_profile` | 14 |
| `scope_mismatch` | 6 |
| `only_some_hr_experience` | 5 |
| `not_strong_enough` | 5 |
| `approachable_but_wrong_fit` | 2 |
| `age_56_plus` | 2 |
| `graduation_before_1989` | 2 |
| `interim_or_consulting_recent` | 2 |
| `not_hr_role` | 2 |
| `is_founder_or_self_employed` | 2 |
| `is_recruiter` | 1 |
| `just_changed_jobs` | 1 |
| `insufficient_japanese` | 1 |
