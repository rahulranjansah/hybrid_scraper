# Rubric Draft — Reasoning Tags for the LLM Judge

Workflow: **Explain-then-Label**. The judge first picks 0+
reasoning tags from the closed set below, then derives a single
label from them.

Each tag has a direction:
- `→ GREEN`: positive signal, pushes toward RELEVANT
- `→ YELLOW`: soft concern, not a deal-breaker
- `→ RED`: hard exclusion from the brief

Final label is derived:
- any `→ RED` tag ⇒ **red**
- else any `→ YELLOW` and no counter-balancing positive ⇒ **yellow**
- else at least one `→ GREEN` and no concerns ⇒ **green**
- default ⇒ **yellow**

## Draft tags (edit this list — add/remove/rename)

### Positive (→ GREEN)

| tag | meaning | evidence in data |
|---|---|---|
| `level_matches_brief` | person's seniority matches the JD level (e.g. HR Manager for an HR Manager brief) | all greens, esp. low-score greens like Fumiko Ogame (6.5) |
| `multinational_hr_experience` | HR leadership at a global/multinational | Mami Arakawa (IBM), Shiho Saito (Baker McKenzie), Jun Higuchi (Takeda) |
| `clean_long_tenure` | avg tenure in recent roles ≥ ~2 years, no hopping | shows up implicitly in all greens |
| `relevant_industry_adjacency` | consumer-goods / retail / fashion / lifestyle — matches Crocs' sector | to be annotated |
| `bilingual_en_ja` | fluent in both English and Japanese | common green trait |

### Soft concerns (→ YELLOW)

| tag | meaning | evidence |
|---|---|---|
| `sector_mismatch` | HR experience but in a very different sector (e.g. chemical manufacturing for a consumer-goods brief) | Shingo Ono (10.0 YELLOW, chemical) |
| `scope_mismatch` | right level but different scope (regional vs global, or vice versa) | Yoko Sato (9.6 YELLOW) |
| `age_concern_55plus` | appears to be 55+ but no other red flags | 2× `'already 55 though'` → yellow |
| `short_current_tenure` | current role 6-18 months old (may be too fresh but not a clear no) | Marvin M, Yuichi Sakamoto |
| `job_hopper_profile` | multiple sub-2-year roles in a row | 2× `'quite job hopper profile'` → yellow |
| `not_strong_enough` | meets criteria on paper but weak signal overall | 1× `'not strong enough'` → yellow |
| `only_some_hr_experience` | <3 years of genuine HR in an otherwise-senior profile | 1× `'only 2 tears hr'` → yellow |
| `client_conflict_soft` | at a client company but open to approach | 2× `'client, but open to approach'` → yellow |
| `approaching_but_interesting` | not fit for this brief, worth keeping warm | 4× `'Not fit for the search but interesting to connect'` → yellow |

### Hard exclusions (→ RED)

| tag | meaning | evidence |
|---|---|---|
| `is_recruiter` | profile is a recruiter / headhunter / exec search | `'It is a recruiter'` → red |
| `is_founder_or_self_employed` | runs their own firm, consultant | from scorer rule, not yet in this sheet |
| `is_client_employee` | currently at the client company — conflict of interest | 3× `'client'` → red |
| `just_changed_jobs` | started a new role very recently — can't be approached | 7× `'just changed jobs'` → red |
| `level_too_senior_for_brief` | CHRO/VP for an HR-Manager brief — overqualified | Tatsuo Kinoshita (10 RED), Akiko Shirasawa (9.8 RED `'Too senior'`) |
| `graduation_before_1989` | tenure / age signal → too senior by career length | 2× `'graduation year 1987/1988'` → red |
| `not_hr_role` | not actually an HR professional | 1× `'Not HR'` → red |
| `insufficient_japanese` | limited Japanese / no Japan work experience | 2× `'No JP'` / `'limited Japanese'` → red |
| `very_short_current_tenure` | current role ≤ 5 months — can't move again so soon | Shinichiroh Yamamoto (10 RED), Hiroe Onishi (9.5 RED) |
| `interim_or_consulting_recent` | recent roles are interim / advisory / consulting | Kazuo Koiso (9.5 RED) |
| `country_manager_not_hr` | regional GM role, not an HR function | 1× `'country manager'` → red |
| `dnc_internal` | internal flag (e.g. DNC on loxo) | 1× `'DNC on loxo'` → red |

## Output schema for the judge (to be wired into DSPy)

```python
class ExplainThenLabel(dspy.Signature):
    """Classify a candidate for a sourcing brief."""
    brief: str = dspy.InputField(desc='the client-facing JD summary')
    candidate: str = dspy.InputField(desc='formatted candidate info')
    reasoning_tags: list[Literal[...all rubric tags...]] = dspy.OutputField()
    reasoning_text: str = dspy.OutputField(desc='one sentence grounding the tags in the candidate info')
    label: Literal['green','yellow','red'] = dspy.OutputField()
```

Label derivation is done in *code*, not by the LLM — so the LLM
can only affect the outcome by choosing tags honestly. This
keeps the rubric auditable.

---

## User annotation pass

Please walk through this list and edit in place:

1. **Strike** any tag that's not real / shouldn't exist.
2. **Rename** any tag whose wording is off.
3. **Re-color** any tag whose direction is wrong (move → YELLOW / RED / GREEN).
4. **Add** tags I missed — one row per tag.
5. **Answer** the four "Q for user" questions in ambiguity_report.md.

Once this file is frozen, Step 3 wires the tag list into the
DSPy signature as a Literal type, and Step 4 runs the optimizer.