"""
Step 3: DSPy judge module wired with rubric_v1.

What this file contains:
  - Rubric tag enums (from judge/IO/step2_rubric/rubric_v1.md)
  - ExplainThenLabel DSPy signature (brief + candidate -> tags + reasoning)
  - derive_label() — code-level mapping from tags to the red/yellow/green label
  - route_red()    — splits red rows into permanent vs reapproach-later buckets
                     (see Plans/FUTURE_CANDIDATES.md)
  - A smoke test that runs the judge on a handful of colored rows so we
    can eyeball the prompt and the outputs before running the DSPy
    optimizer in Step 4.

Model: Gemini 2.5 Flash (`gemini/gemini-2.5-flash`) via DSPy + LiteLLM.
Requires GEMINI_API_KEY in the environment or .env (already present for
the rest of the pipeline).

Note: the existing scraper uses `gemini-2.5-flash-lite`. The judge
deliberately uses the stronger `gemini-2.5-flash` variant to reduce
circularity — different prompt, different rubric, different model
variant, and the rubric is grounded in HUMAN labels, not AI scores.

Data scope: Crocs sheet, colored rows only (92 candidates) — per user
directive, unflagged rows are excluded. The numeric score column is
ignored entirely (scores are AI-auto-generated slop).

This step does NOT optimize the prompt yet. Optimization is Step 4.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import sys
from pathlib import Path
from typing import Literal

import dspy
from dotenv import load_dotenv

HERE = Path(__file__).parent
COLORED = HERE / "IO" / "step2_rubric" / "colored_only.jsonl"
OUT_DIR = HERE / "IO" / "step3_dspy"
BRIEF_FILE = OUT_DIR / "crocs_brief.txt"
SMOKE_OUT = OUT_DIR / "smoke_predictions.jsonl"

# ---------------------------------------------------------------------------
# Rubric (frozen in IO/step2_rubric/rubric_v1.md)
# ---------------------------------------------------------------------------

GOLDEN_TAGS = {
    # 15+ yr HR experience, under 58, at Director/Head level (not C-suite).
    # The "prize" tier — deeply experienced but still in the working window.
    "golden_profile",
}

BLUE_TAGS = {
    # HR worker at a tech company (current or recently-transitioned).
    # Special-interest class — the user actively wants to attract this
    # cohort because tech-HR brings scale / systems / data-driven HR
    # practices that consumer-goods companies value. Sits between
    # golden and green in priority (gold > blue > green > yellow > red).
    "tech_hr_experience",
}

GREEN_TAGS = {
    "level_matches_brief",
    "multinational_hr_experience",
    "clean_long_tenure",
    "relevant_industry_adjacency",
    "bilingual_en_ja",
    # Internal promotions at same company — long tenure with role changes
    # inside one employer is a positive signal, not job hopping.
    "internal_mobility_long_tenure",
}

YELLOW_TAGS = {
    "sector_mismatch",
    "scope_mismatch",
    "job_hopper_profile",       # fires only when avg role tenure < ~3 yrs
    "not_strong_enough",
    "only_some_hr_experience",
    "client_conflict_soft",
    "approachable_but_wrong_fit",
    # Senior but still approachable — Head of HR / HR Director level
    # for an HR Manager brief. One rung above, not three rungs.
    "level_senior_but_acceptable",
}

RED_TAGS_PERMANENT = {
    "level_too_senior_for_brief",   # CHRO / VP / C-suite only
    "is_recruiter",
    "is_founder_or_self_employed",
    "is_client_employee",
    "age_56_plus",
    "graduation_before_1989",
    "interim_or_consulting_recent",
    "country_manager_not_hr",
    "not_hr_role",
    "insufficient_japanese",
    "dnc_internal",
    # Candidate was HR earlier but has since moved out of HR
    # (marketing / customer success / sales). Distinct from `not_hr_role`.
    "hr_to_non_hr_transition",
}

RED_TAGS_TIMING = {
    "just_changed_jobs",
    "short_current_tenure",
    "recently_joined",
}

RED_TAGS = RED_TAGS_PERMANENT | RED_TAGS_TIMING
ALL_TAGS = GOLDEN_TAGS | BLUE_TAGS | GREEN_TAGS | YELLOW_TAGS | RED_TAGS

# DSPy currently needs a concrete Literal, not a runtime set.
RubricTag = Literal[
    # golden
    "golden_profile",
    # blue (special-interest: tech-HR)
    "tech_hr_experience",
    # green
    "level_matches_brief", "multinational_hr_experience",
    "clean_long_tenure", "relevant_industry_adjacency", "bilingual_en_ja",
    "internal_mobility_long_tenure",
    # yellow
    "sector_mismatch", "scope_mismatch", "job_hopper_profile",
    "not_strong_enough", "only_some_hr_experience",
    "client_conflict_soft", "approachable_but_wrong_fit",
    "level_senior_but_acceptable",
    # red permanent
    "level_too_senior_for_brief", "is_recruiter",
    "is_founder_or_self_employed", "is_client_employee",
    "age_56_plus", "graduation_before_1989",
    "interim_or_consulting_recent", "country_manager_not_hr",
    "not_hr_role", "insufficient_japanese", "dnc_internal",
    "hr_to_non_hr_transition",
    # red timing
    "just_changed_jobs", "short_current_tenure", "recently_joined",
]

Label = Literal["golden", "blue", "green", "yellow", "red"]
RedBucket = Literal["red_permanent", "red_reapproach_later"]


# ---------------------------------------------------------------------------
# Label derivation (pure code — the LLM never emits the label directly)
# ---------------------------------------------------------------------------


# Per user 2026-04-21: timing reds (just_changed_jobs, short_current_tenure,
# recently_joined, interim_or_consulting_recent) are SECONDARY — they don't
# override a strong green core (HR + bilingual + 5-10yr + not 55+).
# Only the hard-red disqualifiers below auto-fire.
HARD_RED_TAGS = {
    "is_recruiter", "is_founder_or_self_employed", "is_client_employee",
    "dnc_internal", "not_hr_role", "country_manager_not_hr",
    "insufficient_japanese",
    "age_56_plus", "graduation_before_1989",
    "level_too_senior_for_brief",
    "hr_to_non_hr_transition",
}
TIMING_CONCERN_TAGS = {
    "just_changed_jobs", "short_current_tenure", "recently_joined",
    "interim_or_consulting_recent",
}
SOFT_RED_TAGS = RED_TAGS - HARD_RED_TAGS - TIMING_CONCERN_TAGS

# Yellow tags come in two flavours:
#  - MILD yellow: aesthetic/contextual concerns that don't downgrade a
#    strong green core (e.g. sector_mismatch, approachable_but_wrong_fit).
#  - STRONG yellow: genuine downgraders (e.g. level_senior_but_acceptable,
#    scope_mismatch, job_hopper_profile) — these cap at yellow even if
#    the profile has 3+ green tags.
MILD_YELLOW_TAGS = {"sector_mismatch", "approachable_but_wrong_fit", "client_conflict_soft"}
STRONG_YELLOW_TAGS = YELLOW_TAGS - MILD_YELLOW_TAGS


def derive_label(tags: set[str]) -> Label:
    """4-class rule (v7). Labels: golden > green > yellow > red.

    Per user directive 2026-04-21 (refined through the day):

    - HARD RED auto-fires on any disqualifier tag (age 56+, recruiter,
      client, DNC, CHRO-level-too-senior, not-HR, insufficient-Japanese,
      HR-to-non-HR transition, etc.).
    - GOLDEN fires when `golden_profile` is tagged AND no hard-red.
      These are 15+ yr HR pros still under 58 at Director/Head level.
    - Timing concern (just_changed_jobs etc.) with strong green core
      (g >= 2) -> YELLOW (mild concern, worth a chat). Weak -> RED.
    - Soft-red concern (like `level_senior_but_acceptable`) with strong
      core -> YELLOW; with weak -> RED.
    - Pure positive: 3+ green tags -> GREEN; 2 greens + no concerns ->
      GREEN; 2 greens + any concern -> YELLOW; else YELLOW.

    Yellow is a real "mild concern" class, not a fallback.
    """
    if tags & HARD_RED_TAGS:
        return "red"

    # Golden tier: fires only if otherwise clean (no concerns, no
    # strong yellows). Mild yellows soften to green.
    if tags & GOLDEN_TAGS:
        concerns = (tags & SOFT_RED_TAGS) | (tags & TIMING_CONCERN_TAGS)
        strong_y = tags & STRONG_YELLOW_TAGS
        has_any_yellow = bool(tags & YELLOW_TAGS)
        if not concerns and not has_any_yellow:
            return "golden"
        if not concerns and not strong_y:
            return "green"  # golden softened to green by a mild yellow
        # otherwise fall through to normal rules

    # Blue tier (tech-HR special-interest). Fires when tech_hr_experience
    # is tagged AND the candidate has a baseline strong core (>=2 greens
    # OR golden_profile). Without a strong core, tech tag alone isn't
    # enough — drop through to the normal green/yellow path.
    if tags & BLUE_TAGS:
        concerns = (tags & SOFT_RED_TAGS) | (tags & TIMING_CONCERN_TAGS)
        strong_y = tags & STRONG_YELLOW_TAGS
        g_count = len(tags & GREEN_TAGS)
        if not concerns and not strong_y and g_count >= 2:
            return "blue"
        # otherwise fall through

    g = len(tags & GREEN_TAGS)
    y = len(tags & YELLOW_TAGS)
    strong_y = len(tags & STRONG_YELLOW_TAGS)
    sr = len(tags & SOFT_RED_TAGS)
    t = len(tags & TIMING_CONCERN_TAGS)

    if sr >= 1 and g < 2:
        return "red"

    if t >= 1:
        return "yellow" if g >= 2 else "red"

    if sr >= 1:
        return "yellow"

    # Strong yellow always caps at yellow, even with 3+ green tags.
    if strong_y >= 1:
        return "yellow"

    # Only mild yellows from here on.
    if g >= 3:
        return "green"
    if g >= 2:
        return "green"
    if g >= 1:
        return "yellow"
    if y >= 1:
        return "yellow"
    return "yellow"


def route_red(tags: set[str]) -> RedBucket:
    # If any permanent-disqualifier fires, permanent wins over timing.
    perm = RED_TAGS_PERMANENT | (HARD_RED_TAGS - TIMING_CONCERN_TAGS)
    if tags & perm:
        return "red_permanent"
    if tags & (RED_TAGS_TIMING | TIMING_CONCERN_TAGS):
        return "red_reapproach_later"
    return "red_permanent"


REAPPROACH_WINDOW_DAYS = 365


def reapproach_date() -> str:
    return (dt.date.today() + dt.timedelta(days=REAPPROACH_WINDOW_DAYS)).isoformat()


# ---------------------------------------------------------------------------
# DSPy signature — Explain-then-Label
# ---------------------------------------------------------------------------


class ExplainThenLabel(dspy.Signature):
    """Classify a sourcing candidate against a client brief.

    Labels mean fit-to-brief, not candidate quality:
      - golden = deeply-experienced prize (15+yr HR, Director/Head level, <58)
      - blue   = TECH-HR special interest — HR pro at a tech company,
                 current or recently transitioned. Sits above green.
      - green  = RELEVANT (strong match — target of the search)
      - yellow = OK       (acceptable but has a concern)
      - red    = MISMATCH (wrong fit for THIS brief)

    Tag glossary — fire a tag ONLY when the candidate info clearly
    supports it. Don't guess.

    GREEN (positive signals):
      - level_matches_brief: the person's current role IS in the brief's
        target seniority cluster (HRBP / HR Manager / Senior HR Manager /
        HR Director / Head of HR for the Crocs brief).
      - multinational_hr_experience: HR leadership at a global / MNC.
      - clean_long_tenure: recent roles avg >=3 years, stable.
      - relevant_industry_adjacency: consumer-goods / retail / fashion /
        lifestyle for the Crocs brief.
      - bilingual_en_ja: fluent in both English and Japanese.
      - internal_mobility_long_tenure: 5+ years at one employer with
        MULTIPLE ROLE CHANGES inside that company (internal promotions
        are NOT job hopping — they're loyalty + growth).
        When you see phrases like "at Company X: Role A (Y years),
        then Role B (Z years)" — that pattern IS internal mobility,
        fire THIS tag, NOT job_hopper_profile. Also check
        historically: one short current role inside a stable career
        is not hopping; look at the full history.

    GOLDEN (super-green, prize profile):
      - golden_profile: 15-20+ years of HR experience AND the candidate
        is clearly under ~58 AND currently at Director / Head level
        (NOT CHRO, NOT VP). A 20-yr HR Director under 55 is golden.
        Do NOT fire for CHROs / VPs (they're too senior — tag
        level_too_senior_for_brief instead).

    BLUE (tech-HR special interest — actively wanted):
      - tech_hr_experience: candidate is an HR professional currently
        working at a TECH company (SaaS, e-commerce, fintech, gaming,
        consumer tech, cloud, AI, marketplace) OR recently transitioned
        FROM tech HR into another sector. Examples: Mercari, Rakuten,
        Amazon, Google, Microsoft, LINE, Sony Interactive, PayPay,
        Indeed Japan, TikTok, Yahoo Japan, GMO, SmartHR, freee, etc.
        Tech-HR brings scale, systems thinking, and data-driven HR
        practices we want to attract. Fire BOTH for "current tech HR"
        AND for "recently moved out of tech HR into another sector".
        Do NOT fire for HR people at non-tech multinationals (use
        multinational_hr_experience instead).

    YELLOW (soft / mild concerns):
      - sector_mismatch: wrong industry (e.g. pharma for a consumer-
        goods brief). Mild — HR skills transfer across sectors.
      - scope_mismatch: right level but mismatched scope (regional vs
        global, or function-specific vs broad HRBP).
      - job_hopper_profile: AVG role tenure < ~3 years across MULTIPLE
        DIFFERENT EMPLOYERS. Do NOT fire if role changes are within
        the same company (that's internal_mobility_long_tenure). Do
        NOT fire for one short recent role inside an otherwise-stable
        historical career. Require at least 3 employer changes in <6y.
      - not_strong_enough: signals present but shallow / unconvincing.
      - only_some_hr_experience: less than ~3 years of genuine HR in
        an otherwise-senior profile.
      - client_conflict_soft: currently at a client company but open
        to an approach.
      - approachable_but_wrong_fit: not for this brief but worth
        keeping warm for another search.
      - level_senior_but_acceptable: one rung above the brief (e.g.
        VP HR when brief is HR Manager). Fire ONLY when the role is
        ABOVE the brief's target cluster. Do NOT fire for roles
        INSIDE the cluster (HR Director / Head of HR ARE in the
        cluster for this brief).

    RED (hard disqualifiers):
      - level_too_senior_for_brief: CHRO / VP HR / C-suite only. Fire
        for profiles >=2 rungs above the brief's target cluster.
      - is_recruiter: EXTERNAL recruiter / headhunter / executive
        search professional. Do NOT fire for in-house Talent
        Acquisition — that's an HR function, not a recruiting agency.
      - is_founder_or_self_employed: runs their own firm.
      - is_client_employee: currently at the client company
        (no-go / conflict).
      - just_changed_jobs / short_current_tenure / recently_joined:
        started current role within ~6 months (approachability red).
      - age_56_plus: appears to be 56+ years old.
      - graduation_before_1989: graduated on or before 1988.
      - interim_or_consulting_recent: recent roles are interim /
        advisory / consulting.
      - country_manager_not_hr: regional GM, not an HR function.
      - not_hr_role: NEVER was in HR (profile is not an HR person).
      - hr_to_non_hr_transition: WAS in HR (past role had HR in the
        title: HR Manager, HRBP, Talent Acquisition, etc.) AND has
        since moved OUT of HR — current role is marketing, customer
        success, sales, community management, career services,
        product, etc. A profile that has "HR Manager at X (past),
        Customer Success at Y (current)" MUST fire this tag. Distinct
        from not_hr_role (which is "never was in HR"). When this tag
        fires, the candidate is RED regardless of other positives.
      - insufficient_japanese: profile EXPLICITLY signals limited
        Japanese — e.g. remarks about short time in Japan,
        non-native fluency, or English-only profile at a non-Japanese
        company. DO NOT fire just because the candidate has worked
        in multiple geographies. DO NOT fire for people based at a
        Japanese HQ (UNIQLO, Fast Retailing, Rakuten, etc.) unless
        the profile explicitly says their Japanese is limited.
      - dnc_internal: internal do-not-contact flag.

    Pick tags only when the candidate info clearly supports them.
    The label is derived from tags in code, so honest tag selection
    is what matters.
    """

    brief: str = dspy.InputField(
        desc="the client-facing JD / sourcing brief that defines the target role"
    )
    candidate: str = dspy.InputField(
        desc="formatted candidate profile text — name, linkedin url, extracted strengths/weaknesses"
    )
    reasoning_tags: list[RubricTag] = dspy.OutputField(
        desc="pick all rubric tags that apply to this candidate given the brief"
    )
    reasoning_text: str = dspy.OutputField(
        desc="one short sentence grounding the tags in concrete facts from the candidate profile"
    )
    strengths: list[str] = dspy.OutputField(
        desc="3-5 positive signals from the candidate profile relevant to the brief — concrete bullets, not generic HR buzzwords"
    )
    weaknesses: list[str] = dspy.OutputField(
        desc="2-4 concerns or gaps from the candidate profile — concrete bullets, honest, not softened"
    )
    missing_data: list[str] = dspy.OutputField(
        desc="2-3 things we'd need to verify to finalize a decision — e.g. 'exact current tenure', 'Japanese fluency', 'team size managed'"
    )
    actionable_insights: list[str] = dspy.OutputField(
        desc="2-3 next steps or questions a recruiter would ask in a first call — specific to this candidate, not generic"
    )


# ---------------------------------------------------------------------------
# Brief (TODO: replace stub with the real Crocs JD text from the user)
# ---------------------------------------------------------------------------


def load_brief() -> str:
    return BRIEF_FILE.read_text()


# ---------------------------------------------------------------------------
# Candidate formatter — what the judge sees at inference time
# ---------------------------------------------------------------------------


def format_candidate(row: dict) -> str:
    """Build the candidate_info string. Deliberately excludes human_score,
    human_flag, and remark (those are labels, not features)."""
    parts: list[str] = [f"Name: {row['name']}"]
    if row.get("linkedin_url"):
        parts.append(f"LinkedIn: {row['linkedin_url']}")
    if row.get("strengths"):
        parts.append("Strengths:\n  - " + "\n  - ".join(row["strengths"][:10]))
    if row.get("weaknesses"):
        parts.append("Weaknesses:\n  - " + "\n  - ".join(row["weaknesses"][:10]))
    if row.get("missing_data"):
        parts.append("Missing data:\n  - " + "\n  - ".join(row["missing_data"][:5]))
    if row.get("actionable_insights"):
        parts.append(
            "Extracted insights:\n  - "
            + "\n  - ".join(row["actionable_insights"][:5])
        )
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Runtime wiring
# ---------------------------------------------------------------------------


def configure_lm() -> None:
    load_dotenv(HERE.parent / ".env")
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        print("ERROR: GEMINI_API_KEY is not set.", file=sys.stderr)
        sys.exit(2)
    lm = dspy.LM(
        model="gemini/gemini-2.5-flash",
        api_key=key,
        max_tokens=4000,
        temperature=0.0,
        reasoning_effort="disable",
    )
    dspy.configure(lm=lm)


def load_colored() -> list[dict]:
    return [json.loads(l) for l in COLORED.open()]


def run_one(judge: dspy.Predict, brief: str, row: dict) -> dict:
    pred = judge(brief=brief, candidate=format_candidate(row))
    tags = set(pred.reasoning_tags or [])
    label = derive_label(tags)
    out = {
        "name": row["name"],
        "human_flag": row["human_flag"],
        "human_remark": row.get("remark", ""),
        "predicted_label": label,
        "reasoning_tags": sorted(tags),
        "reasoning_text": pred.reasoning_text,
        "strengths": list(pred.strengths or []),
        "weaknesses": list(pred.weaknesses or []),
        "missing_data": list(pred.missing_data or []),
        "actionable_insights": list(pred.actionable_insights or []),
    }
    if label == "red":
        bucket = route_red(tags)
        out["red_bucket"] = bucket
        out["reapproach_after"] = (
            reapproach_date() if bucket == "red_reapproach_later" else None
        )
    return out


def smoke_test(n: int = 6) -> None:
    configure_lm()
    brief = load_brief()
    rows = load_colored()
    # Pick a mix: 2 green, 2 yellow, 2 red for a quick sanity check.
    by_flag: dict[str, list[dict]] = {"green": [], "yellow": [], "red": []}
    for r in rows:
        by_flag[r["human_flag"]].append(r)
    sample = by_flag["green"][:2] + by_flag["yellow"][:2] + by_flag["red"][:2]

    judge = dspy.Predict(ExplainThenLabel)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    preds: list[dict] = []
    for row in sample[:n]:
        print(f"\n=== {row['name']}  (human: {row['human_flag']}) ===")
        try:
            out = run_one(judge, brief, row)
        except Exception as e:
            print(f"  ERROR: {e}")
            continue
        preds.append(out)
        mark = "✓" if out["predicted_label"] == out["human_flag"] else "✗"
        print(f"  {mark} predicted={out['predicted_label']}  tags={out['reasoning_tags']}")
        print(f"    reason: {out['reasoning_text']}")
        if out.get("red_bucket"):
            print(f"    bucket: {out['red_bucket']}  reapproach_after={out.get('reapproach_after')}")

    with SMOKE_OUT.open("w") as f:
        for p in preds:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")

    agree = sum(1 for p in preds if p["predicted_label"] == p["human_flag"])
    print(f"\nSmoke test agreement: {agree}/{len(preds)}")
    print(f"Saved -> {SMOKE_OUT}")


if __name__ == "__main__":
    smoke_test()
