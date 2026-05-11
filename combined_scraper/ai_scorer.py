"""
Stage 4: DSPy-based relevance judge (replaces the old Gemini 0-10 scorer).

Per user directive 2026-04-22, the prior 0-10 score column was deemed
unreliable. This module now calls the DSPy judge defined in
`judge/step3_dspy_judge.py`, which emits a 4-class label
(golden > green > yellow > red) plus reasoning tags and a grounding
sentence. Label derivation is code-level, not LLM-level, so each
verdict is auditable against the rubric.

Drop-in replacement: same `score_results(results, keywords_text)` signature
that `combined_scraper/run.py` already calls. Downstream CSV/JSON schemas
keep the `flag` / `relevance_score` / `score_reason` fields for back-compat.
The `relevance_score` is a derived rank (golden=10, green=8, yellow=5,
red=1, unknown=0) purely for sorting — do not interpret as an independent
quality metric.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import dspy

# Make the judge module importable.
_JUDGE_DIR = Path(__file__).resolve().parent.parent / "judge"
if str(_JUDGE_DIR) not in sys.path:
    sys.path.insert(0, str(_JUDGE_DIR))

from step3_dspy_judge import (  # noqa: E402
    ExplainThenLabel,
    configure_lm,
    derive_label,
    route_red,
    reapproach_date,
    TIMING_CONCERN_TAGS,
    HARD_RED_TAGS,
)

# Rank used ONLY for sorting/back-compat. Not an independent quality score.
LABEL_TO_RANK = {"golden": 10, "green": 8, "yellow": 5, "red": 1}


def _format_candidate_for_judge(result: dict, person: dict) -> str:
    """Build the candidate string from one scraper result + one extracted person.

    Scraper rows don't carry strengths/weaknesses (those came from the old
    sheet format). The judge has to reason from title / company / snippet /
    source URL, plus any LinkedIn URL we found.
    """
    parts: list[str] = [f"Name: {person.get('name') or '?'}"]
    title = (person.get("title") or "").strip()
    company = (person.get("company") or "").strip()
    if title or company:
        parts.append(f"Current role: {title or '?'} @ {company or '?'}")
    if person.get("linkedin_url"):
        parts.append(f"LinkedIn: {person['linkedin_url']}")
    if person.get("seniority"):
        parts.append(f"Seniority signal: {person['seniority']}")
    if person.get("employment_type"):
        parts.append(f"Employment type: {person['employment_type']}")
    if result.get("url"):
        parts.append(f"Source URL: {result['url']}")
    if result.get("title"):
        parts.append(f"Page title: {result['title'][:200]}")
    snippet = (result.get("snippet") or "").strip()
    if snippet:
        parts.append(f"Snippet: {snippet[:500]}")
    return "\n".join(parts)


def score_results(results: list[dict], keywords_text: str, brief: str | None = None) -> list[dict]:
    """Judge each result's primary person against the sourcing brief.

    Args:
      results: scraper results from stage 3/3.5. Each row may have a
        ``people`` list.
      keywords_text: the sourcing brief text (or a keyword list) used
        as the ``brief`` input to the DSPy judge unless ``brief`` is
        explicitly provided.
      brief: override the judge's brief input (e.g. for Crocs use the
        full JD rather than the short keyword string).

    Returns:
      The same list, sorted by label (golden first), with added fields
      per row: ``flag``, ``reasoning_tags``, ``reasoning_text``,
      ``relevance_score`` (derived rank), and for reds
      ``red_bucket`` + (optional) ``reapproach_after``.
    """
    configure_lm()
    brief_text = (brief or keywords_text or "").strip() or "no brief provided"
    judge = dspy.Predict(ExplainThenLabel)

    non_person = [r for r in results if not r.get("is_person_result")]
    for r in non_person:
        r["flag"] = "red"
        r["score_reason"] = "No person identified in result"
        r["relevance_score"] = 0
        r["reasoning_tags"] = []
        r["red_bucket"] = "red_permanent"

    person_results = [r for r in results if r.get("is_person_result") and r.get("people")]
    print(f"  [judge] scoring {len(person_results)} person-results "
          f"(skipping {len(non_person)} non-person rows)")

    for i, r in enumerate(person_results, 1):
        # Primary person per result. Multi-person pages (events) keep the
        # first one — secondary people can be judged as a future pass.
        person = r["people"][0]
        candidate = _format_candidate_for_judge(r, person)
        try:
            pred = judge(brief=brief_text, candidate=candidate)
            tags = set(pred.reasoning_tags or [])
            label = derive_label(tags)
            r["flag"] = label
            r["reasoning_tags"] = sorted(tags)
            r["score_reason"] = pred.reasoning_text
            r["strengths"] = list(pred.strengths or [])
            r["weaknesses"] = list(pred.weaknesses or [])
            r["missing_data"] = list(pred.missing_data or [])
            r["actionable_insights"] = list(pred.actionable_insights or [])
            r["relevance_score"] = LABEL_TO_RANK.get(label, 0)
            if label == "red":
                r["red_bucket"] = route_red(tags)
                if r["red_bucket"] == "red_reapproach_later":
                    r["reapproach_after"] = reapproach_date()
        except Exception as e:
            r["flag"] = "error"
            r["score_reason"] = f"judge error: {str(e)[:200]}"
            r["relevance_score"] = 0
            r["reasoning_tags"] = []
        if i % 5 == 0 or i == len(person_results):
            print(f"    judged {i}/{len(person_results)}")

    results.sort(key=lambda x: LABEL_TO_RANK.get(x.get("flag", ""), -1), reverse=True)

    from collections import Counter
    tally = Counter(r.get("flag") for r in results if r.get("is_person_result"))
    print(f"  [judge] label distribution: {dict(tally)}")

    return results
