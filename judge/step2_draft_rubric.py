"""
Step 2: Ambiguity report + draft rubric.

Input:  judge/IO/step1_parse/human_labels.jsonl
Output:
  judge/IO/step2_rubric/colored_only.jsonl   -- 92 colored rows (training set)
  judge/IO/step2_rubric/ambiguity_report.md  -- clusters for user annotation
  judge/IO/step2_rubric/rubric_draft.md      -- draft reasoning-tag rubric

The rubric is intentionally seeded from observed patterns; the user will
edit rubric_draft.md to freeze the canonical tag set before Step 3 wires
it into DSPy.

The workflow is Explain-then-Label:
  candidate info  ->  [reasoning tags chosen from rubric]  ->  label
"""

import json
from pathlib import Path
from collections import Counter, defaultdict

HERE = Path(__file__).parent
IN = HERE / "IO" / "step1_parse" / "human_labels.jsonl"
OUT_DIR = HERE / "IO" / "step2_rubric"
OUT_COLORED = OUT_DIR / "colored_only.jsonl"
OUT_AMBIG = OUT_DIR / "ambiguity_report.md"
OUT_RUBRIC = OUT_DIR / "rubric_draft.md"


def load_colored() -> list[dict]:
    rows = [json.loads(l) for l in IN.open()]
    return [r for r in rows if r["human_flag"] != "unflagged"]


def write_colored(rows: list[dict]) -> None:
    with OUT_COLORED.open("w") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def score_bucket(s: float | None) -> str:
    if s is None:
        return "unknown"
    if s >= 9.5:
        return "9.5-10"
    if s >= 9:
        return "9.0-9.4"
    if s >= 8:
        return "8.0-8.9"
    if s >= 7:
        return "7.0-7.9"
    return "<7.0"


def ambiguity_report(rows: list[dict]) -> str:
    lines: list[str] = []
    lines.append("# Ambiguity Report — 92 colored Crocs-HR-Manager rows")
    lines.append("")
    lines.append("Label semantics: **red=MISMATCH, yellow=OK, green=RELEVANT**.")
    lines.append("Target = green. Red and yellow are both penalized.")
    lines.append("")
    lines.append("## The big one: JD is 'HR Manager', not CHRO")
    lines.append("")
    lines.append("`combined_scraper/ai_scorer.py` is tuned for CHRO/Director+ and")
    lines.append("penalizes below-Director. The Crocs brief is an *HR Manager*.")
    lines.append("That's why several perfect-scored CHROs were flagged RED:")
    lines.append("")
    for r in sorted(
        [x for x in rows if x["human_flag"] == "red" and (x["human_score"] or 0) >= 9.2],
        key=lambda x: -(x["human_score"] or 0),
    )[:8]:
        remark = f" — *{r['remark']}*" if r["remark"] else ""
        weakness = r["weaknesses"][0][:120] if r["weaknesses"] else ""
        lines.append(f"- {r['human_score']}  **{r['name']}**{remark}  ·  weakness: _{weakness}_")
    lines.append("")
    lines.append("**Q for user:** is the rubric JD-conditional (`{brief}`")
    lines.append("as an input to the judge), or do we treat every JD as a fresh")
    lines.append("rubric training run? Haiku on 92 examples is cheap enough for")
    lines.append("per-JD retraining, but the rubric tags themselves should be")
    lines.append("brief-agnostic (e.g. `level_matches_brief`, not `is_chro`).")
    lines.append("")

    # Same-remark divergent labels
    lines.append("## Same remark, different flag")
    lines.append("")
    by_remark: dict[str, list[str]] = defaultdict(list)
    for r in rows:
        if r["remark"]:
            by_remark[r["remark"].lower().strip()].append(r["human_flag"])
    any_div = False
    for remark, flags in sorted(by_remark.items()):
        if len(set(flags)) > 1:
            any_div = True
            c = Counter(flags)
            lines.append(f"- `{remark!r}` → {dict(c)}")
    if not any_div:
        lines.append("_(none — remarks are consistent within the colored set)_")
    lines.append("")
    lines.append("**Q for user:** for `'just changed jobs'` the overwhelming label is red")
    lines.append("(7×) with one outlier yellow. Does yellow mean \"just changed jobs BUT")
    lines.append("still approachable / worth keeping warm\" or is that one-off a mistake?")
    lines.append("")

    # Score-flag matrix
    lines.append("## Score × flag matrix (what scores does each color cover?)")
    lines.append("")
    lines.append("| score bucket | green | yellow | red |")
    lines.append("|---|---:|---:|---:|")
    buckets = ["9.5-10", "9.0-9.4", "8.0-8.9", "7.0-7.9", "<7.0", "unknown"]
    mat: dict[tuple[str, str], int] = Counter()
    for r in rows:
        mat[(score_bucket(r["human_score"]), r["human_flag"])] += 1
    for b in buckets:
        g = mat[(b, "green")]
        y = mat[(b, "yellow")]
        rr = mat[(b, "red")]
        if g + y + rr == 0:
            continue
        lines.append(f"| {b} | {g} | {y} | {rr} |")
    lines.append("")
    lines.append("Observation: every score bucket has greens AND reds. **Score does")
    lines.append("not predict flag** — the flag is a fit-to-brief verdict, not a")
    lines.append("quality rating. The judge must learn tags, not thresholds.")
    lines.append("")

    # Low-score greens — why are they the prize?
    lines.append("## Low-score GREENs (what makes them relevant despite low score?)")
    lines.append("")
    for r in sorted(
        [x for x in rows if x["human_flag"] == "green"],
        key=lambda x: (x["human_score"] or 0),
    )[:5]:
        strength = r["strengths"][0][:120] if r["strengths"] else ""
        lines.append(f"- {r['human_score']}  **{r['name']}**  ·  strength: _{strength}_")
    lines.append("")
    lines.append("**Q for user:** what's the minimum criterion for GREEN?")
    lines.append("From the data it looks like: HR Manager-level, clean tenure,")
    lines.append("relevant industry/multinational context, no red flags.")
    lines.append("")

    # Tenure / short-role pattern (appears in many REDs without explicit remark)
    lines.append("## Short-tenure / interim / consulting pattern")
    lines.append("")
    lines.append("Several high-score REDs have no remark but share a weakness:")
    tenure_phrases = [
        "short",
        "interim",
        "consulting",
        "5 months",
        "7 months",
        "1.5 year",
        "1 year",
    ]
    tenure_reds = [
        r for r in rows
        if r["human_flag"] == "red"
        and r["weaknesses"]
        and any(p in " ".join(r["weaknesses"]).lower() for p in tenure_phrases)
    ]
    for r in tenure_reds[:6]:
        w = r["weaknesses"][0][:120]
        lines.append(f"- {r['human_score']}  **{r['name']}**  ·  _{w}_")
    lines.append("")
    lines.append("**Q for user:** is \"short tenure in current role\" a hard red,")
    lines.append("or yellow with a 'recently-joined' caveat? The current data")
    lines.append("suggests hard red when tenure is under ~6 months.")
    lines.append("")

    return "\n".join(lines)


def rubric_draft(rows: list[dict]) -> str:
    lines: list[str] = []
    lines.append("# Rubric Draft — Reasoning Tags for the LLM Judge")
    lines.append("")
    lines.append("Workflow: **Explain-then-Label**. The judge first picks 0+")
    lines.append("reasoning tags from the closed set below, then derives a single")
    lines.append("label from them.")
    lines.append("")
    lines.append("Each tag has a direction:")
    lines.append("- `→ GREEN`: positive signal, pushes toward RELEVANT")
    lines.append("- `→ YELLOW`: soft concern, not a deal-breaker")
    lines.append("- `→ RED`: hard exclusion from the brief")
    lines.append("")
    lines.append("Final label is derived:")
    lines.append("- any `→ RED` tag ⇒ **red**")
    lines.append("- else any `→ YELLOW` and no counter-balancing positive ⇒ **yellow**")
    lines.append("- else at least one `→ GREEN` and no concerns ⇒ **green**")
    lines.append("- default ⇒ **yellow**")
    lines.append("")
    lines.append("## Draft tags (edit this list — add/remove/rename)")
    lines.append("")
    lines.append("### Positive (→ GREEN)")
    lines.append("")
    lines.append("| tag | meaning | evidence in data |")
    lines.append("|---|---|---|")
    lines.append("| `level_matches_brief` | person's seniority matches the JD level (e.g. HR Manager for an HR Manager brief) | all greens, esp. low-score greens like Fumiko Ogame (6.5) |")
    lines.append("| `multinational_hr_experience` | HR leadership at a global/multinational | Mami Arakawa (IBM), Shiho Saito (Baker McKenzie), Jun Higuchi (Takeda) |")
    lines.append("| `clean_long_tenure` | avg tenure in recent roles ≥ ~2 years, no hopping | shows up implicitly in all greens |")
    lines.append("| `relevant_industry_adjacency` | consumer-goods / retail / fashion / lifestyle — matches Crocs' sector | to be annotated |")
    lines.append("| `bilingual_en_ja` | fluent in both English and Japanese | common green trait |")
    lines.append("")
    lines.append("### Soft concerns (→ YELLOW)")
    lines.append("")
    lines.append("| tag | meaning | evidence |")
    lines.append("|---|---|---|")
    lines.append("| `sector_mismatch` | HR experience but in a very different sector (e.g. chemical manufacturing for a consumer-goods brief) | Shingo Ono (10.0 YELLOW, chemical) |")
    lines.append("| `scope_mismatch` | right level but different scope (regional vs global, or vice versa) | Yoko Sato (9.6 YELLOW) |")
    lines.append("| `age_concern_55plus` | appears to be 55+ but no other red flags | 2× `'already 55 though'` → yellow |")
    lines.append("| `short_current_tenure` | current role 6-18 months old (may be too fresh but not a clear no) | Marvin M, Yuichi Sakamoto |")
    lines.append("| `job_hopper_profile` | multiple sub-2-year roles in a row | 2× `'quite job hopper profile'` → yellow |")
    lines.append("| `not_strong_enough` | meets criteria on paper but weak signal overall | 1× `'not strong enough'` → yellow |")
    lines.append("| `only_some_hr_experience` | <3 years of genuine HR in an otherwise-senior profile | 1× `'only 2 tears hr'` → yellow |")
    lines.append("| `client_conflict_soft` | at a client company but open to approach | 2× `'client, but open to approach'` → yellow |")
    lines.append("| `approaching_but_interesting` | not fit for this brief, worth keeping warm | 4× `'Not fit for the search but interesting to connect'` → yellow |")
    lines.append("")
    lines.append("### Hard exclusions (→ RED)")
    lines.append("")
    lines.append("| tag | meaning | evidence |")
    lines.append("|---|---|---|")
    lines.append("| `is_recruiter` | profile is a recruiter / headhunter / exec search | `'It is a recruiter'` → red |")
    lines.append("| `is_founder_or_self_employed` | runs their own firm, consultant | from scorer rule, not yet in this sheet |")
    lines.append("| `is_client_employee` | currently at the client company — conflict of interest | 3× `'client'` → red |")
    lines.append("| `just_changed_jobs` | started a new role very recently — can't be approached | 7× `'just changed jobs'` → red |")
    lines.append("| `level_too_senior_for_brief` | CHRO/VP for an HR-Manager brief — overqualified | Tatsuo Kinoshita (10 RED), Akiko Shirasawa (9.8 RED `'Too senior'`) |")
    lines.append("| `graduation_before_1989` | tenure / age signal → too senior by career length | 2× `'graduation year 1987/1988'` → red |")
    lines.append("| `not_hr_role` | not actually an HR professional | 1× `'Not HR'` → red |")
    lines.append("| `insufficient_japanese` | limited Japanese / no Japan work experience | 2× `'No JP'` / `'limited Japanese'` → red |")
    lines.append("| `very_short_current_tenure` | current role ≤ 5 months — can't move again so soon | Shinichiroh Yamamoto (10 RED), Hiroe Onishi (9.5 RED) |")
    lines.append("| `interim_or_consulting_recent` | recent roles are interim / advisory / consulting | Kazuo Koiso (9.5 RED) |")
    lines.append("| `country_manager_not_hr` | regional GM role, not an HR function | 1× `'country manager'` → red |")
    lines.append("| `dnc_internal` | internal flag (e.g. DNC on loxo) | 1× `'DNC on loxo'` → red |")
    lines.append("")
    lines.append("## Output schema for the judge (to be wired into DSPy)")
    lines.append("")
    lines.append("```python")
    lines.append("class ExplainThenLabel(dspy.Signature):")
    lines.append("    \"\"\"Classify a candidate for a sourcing brief.\"\"\"")
    lines.append("    brief: str = dspy.InputField(desc='the client-facing JD summary')")
    lines.append("    candidate: str = dspy.InputField(desc='formatted candidate info')")
    lines.append("    reasoning_tags: list[Literal[...all rubric tags...]] = dspy.OutputField()")
    lines.append("    reasoning_text: str = dspy.OutputField(desc='one sentence grounding the tags in the candidate info')")
    lines.append("    label: Literal['green','yellow','red'] = dspy.OutputField()")
    lines.append("```")
    lines.append("")
    lines.append("Label derivation is done in *code*, not by the LLM — so the LLM")
    lines.append("can only affect the outcome by choosing tags honestly. This")
    lines.append("keeps the rubric auditable.")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## User annotation pass")
    lines.append("")
    lines.append("Please walk through this list and edit in place:")
    lines.append("")
    lines.append("1. **Strike** any tag that's not real / shouldn't exist.")
    lines.append("2. **Rename** any tag whose wording is off.")
    lines.append("3. **Re-color** any tag whose direction is wrong (move → YELLOW / RED / GREEN).")
    lines.append("4. **Add** tags I missed — one row per tag.")
    lines.append("5. **Answer** the four \"Q for user\" questions in ambiguity_report.md.")
    lines.append("")
    lines.append("Once this file is frozen, Step 3 wires the tag list into the")
    lines.append("DSPy signature as a Literal type, and Step 4 runs the optimizer.")
    return "\n".join(lines)


def main() -> None:
    rows = load_colored()
    write_colored(rows)
    OUT_AMBIG.write_text(ambiguity_report(rows))
    OUT_RUBRIC.write_text(rubric_draft(rows))
    print(f"Colored rows: {len(rows)} -> {OUT_COLORED}")
    print(f"Ambiguity report -> {OUT_AMBIG}")
    print(f"Rubric draft     -> {OUT_RUBRIC}")


if __name__ == "__main__":
    main()
