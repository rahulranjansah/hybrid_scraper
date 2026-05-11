# Rubric v1 — Reasoning Tags for the LLM Judge

Frozen after user annotation pass on 2026-04-21. Supersedes `rubric_draft.md`.

Workflow: **Explain-then-Label**. The judge picks 0+ reasoning tags from
the closed set below, writes one sentence grounding them in the candidate
info, then the label is *derived in code* from the tags (not by the LLM).

Labels: `red = MISMATCH`, `yellow = OK`, `green = RELEVANT`. Target is
green; both yellow and red are penalised.

## Decisions locked from user (2026-04-21)

1. **CHRO is dropped** as a target. The Crocs brief wants HR Manager
   cluster roles:
   - HRBP · HR Business Partner · HR Manager · HRBP Manager
   - HR Director · Senior HRBP · Senior HR Manager · Head of HR
   Profiles at CHRO / VP HR / C-suite level are **overqualified**
   → tag `level_too_senior_for_brief` → RED.

2. **Scores are ignored.** The 0-10 score column in the sheet was AI-
   auto-generated slop; it is not a human signal. Training and eval
   look only at cell colour + remark.

3. **Approachability rules are hard red** (not yellow):
   - `just_changed_jobs` → RED (always; the one previous yellow outlier
     was a mistake)
   - `short_current_tenure` (under ~6 months in current role) → RED
   - `recently_joined` → RED (subsumed by the above)
   *Reason: a person who just moved will not move again.*

4. **Age 56+ is hard red** (not yellow). Threshold is 56, not 55.
   *Reason: Japanese retirement norms — too senior by tenure.*

5. **JD is a judge input.** The rubric is brief-agnostic
   (e.g. `level_matches_brief`), the brief text is passed in at call
   time. For Crocs, the target-role cluster in #1 is the brief.

## Tags — Positive (→ GREEN)

| tag | meaning |
|---|---|
| `level_matches_brief` | seniority fits the brief (HRBP / HR Mgr / HR Dir / Head of HR cluster for Crocs) |
| `multinational_hr_experience` | HR leadership at a global / multinational employer |
| `clean_long_tenure` | recent roles average ≥ ~2 years, no hopping |
| `relevant_industry_adjacency` | consumer-goods / retail / fashion / lifestyle for Crocs |
| `bilingual_en_ja` | fluent in both English and Japanese |

## Tags — Soft concerns (→ YELLOW)

| tag | meaning | origin |
|---|---|---|
| `sector_mismatch` | HR experience but wrong sector (e.g. chemicals for consumer goods) | Shingo Ono (chem mfg) → yellow |
| `scope_mismatch` | right level but different scope (regional vs global etc.) | Yoko Sato → yellow |
| `job_hopper_profile` | multiple sub-2-year roles in a row | `'quite job hopper profile'` → yellow |
| `not_strong_enough` | meets criteria on paper but weak overall signal | `'not strong enough'` → yellow |
| `only_some_hr_experience` | <3 years genuine HR in an otherwise-senior profile | `'only 2 tears hr'` → yellow |
| `client_conflict_soft` | at a client company but open to approach | `'client, but open to approach'` → yellow |
| `approachable_but_wrong_fit` | not fit for this brief, worth keeping warm for other briefs | `'Not fit for the search but interesting to connect'` → yellow |

## Tags — Hard exclusions (→ RED)

| tag | meaning | origin |
|---|---|---|
| `level_too_senior_for_brief` | CHRO / VP / C-suite for an HR-Manager brief | Tatsuo Kinoshita, Akiko Shirasawa `'Too senior'` |
| `is_recruiter` | recruiter / headhunter / exec search professional | `'It is a recruiter'` |
| `is_founder_or_self_employed` | runs own firm, consultant | from original ai_scorer rule |
| `is_client_employee` | currently at the client company (conflict of interest) | `'client'` (3×) |
| `just_changed_jobs` | started a new role recently → low chance of moving | `'just changed jobs'` (8× → all red) |
| `short_current_tenure` | current role under ~6 months | Shinichiroh Yamamoto (5 mos at Google), Hiroe Onishi (5 mos) |
| `recently_joined` | alias of the above — treat as hard red | same |
| `age_56_plus` | 56+ years old or career signals indicating so | `'already 55'` / `'too old'` → red above threshold |
| `graduation_before_1989` | graduation year ≤ 1988 (≈ 35+ years tenure, typically 57+) | `'graduation year 1987/1988'` → red |
| `interim_or_consulting_recent` | recent roles are interim / advisory / consulting | Kazuo Koiso → red |
| `country_manager_not_hr` | regional GM, not an HR function | `'country manager'` → red |
| `not_hr_role` | not actually an HR professional | `'Not HR'` → red |
| `insufficient_japanese` | limited Japanese or no Japan work experience | `'No JP'` / `'limited Japanese'` → red |
| `dnc_internal` | internal no-contact flag | `'DNC on loxo'` → red |

## Label derivation (code-level, not LLM)

```python
def derive_label(tags: set[str]) -> str:
    RED_TAGS = { ... all red tags above ... }
    YELLOW_TAGS = { ... all yellow tags above ... }
    GREEN_TAGS = { ... all green tags above ... }

    if tags & RED_TAGS:
        return "red"
    if tags & YELLOW_TAGS and not (tags & GREEN_TAGS):
        return "yellow"
    if tags & GREEN_TAGS:
        return "green"
    return "yellow"  # no signal → conservative default
```

## DSPy signature (to implement in Step 3)

```python
from typing import Literal

import dspy

ALL_TAGS = Literal[
    # green
    "level_matches_brief", "multinational_hr_experience",
    "clean_long_tenure", "relevant_industry_adjacency", "bilingual_en_ja",
    # yellow
    "sector_mismatch", "scope_mismatch", "job_hopper_profile",
    "not_strong_enough", "only_some_hr_experience",
    "client_conflict_soft", "approachable_but_wrong_fit",
    # red
    "level_too_senior_for_brief", "is_recruiter",
    "is_founder_or_self_employed", "is_client_employee",
    "just_changed_jobs", "short_current_tenure", "recently_joined",
    "age_56_plus", "graduation_before_1989",
    "interim_or_consulting_recent", "country_manager_not_hr",
    "not_hr_role", "insufficient_japanese", "dnc_internal",
]

class ExplainThenLabel(dspy.Signature):
    """Classify a candidate for a sourcing brief: green=RELEVANT, yellow=OK, red=MISMATCH."""

    brief: str = dspy.InputField(desc="the client-facing JD / sourcing brief")
    candidate: str = dspy.InputField(desc="formatted candidate profile text")

    reasoning_tags: list[ALL_TAGS] = dspy.OutputField(
        desc="pick 0+ tags from the rubric that apply to this candidate"
    )
    reasoning_text: str = dspy.OutputField(
        desc="one sentence grounding the tags in the candidate info"
    )
    # Note: no `score` output. The score column in the training data is
    # AI-auto-generated slop and must not be learned or predicted.

# Label is derived in code from reasoning_tags — the LLM does not emit it.
```

The 3-token label is computed from `reasoning_tags` by the `derive_label`
function above. This makes the judge auditable: every label is
traceable to a concrete rubric tag plus a grounding sentence.
