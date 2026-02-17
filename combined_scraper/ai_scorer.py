"""
Stage 4: AI Relevance Scorer

Replaces BM25 ranking. Instead of keyword-frequency scoring,
Gemini evaluates each person against the sourcing brief.

BM25 problem: "HR trends blog" with 5x "HR" scores higher than
a LinkedIn profile saying "CHRO" once.

AI advantage: understands that CHRO > blog post for recruiting.

Model: gemini-2.5-flash-lite, 1024 token cap per call.
Batches: 10 results per call (same as extractor).
"""

import json
from .query_generator import call_gemini

BATCH_SIZE = 10


def score_results(results: list[dict], keywords_text: str) -> list[dict]:
    """
    Score each result for relevance to the sourcing brief.

    Only scores results where people were extracted (is_person_result=True).
    Non-person results get score=0 automatically.

    Args:
        results: Enriched results from Stage 3 (with "people" field)
        keywords_text: Original keywords from Google Doc (the sourcing brief)

    Returns:
        Same results with added "relevance_score" (0-10) and "score_reason" fields,
        sorted by score descending.

    Cost: 1 Gemini call per 10 person-results
    """
    # Split into person results and non-person results
    person_results = [r for r in results if r.get("is_person_result")]
    non_person_results = [r for r in results if not r.get("is_person_result")]

    # Non-person results get score 0
    for r in non_person_results:
        r["relevance_score"] = 0
        r["score_reason"] = "No person identified in result"

    if not person_results:
        print("  No person results to score.")
        return sorted(results, key=lambda r: r.get("relevance_score", 0), reverse=True)

    # Score person results in batches
    total_calls = 0

    for batch_start in range(0, len(person_results), BATCH_SIZE):
        batch = person_results[batch_start:batch_start + BATCH_SIZE]
        batch_num = batch_start // BATCH_SIZE + 1
        total_batches = (len(person_results) + BATCH_SIZE - 1) // BATCH_SIZE

        print(f"  [Score batch {batch_num}/{total_batches}] Scoring {len(batch)} results...")

        entries = []
        for i, r in enumerate(batch):
            people_str = "; ".join(
                f"{p.get('name', '?')} - {p.get('title', '?')} @ {p.get('company', '?')}"
                for p in r.get("people", [])
            )
            entries.append(
                f"{i}. People: {people_str}\n"
                f"   Source: {r.get('url', '')}\n"
                f"   Context: {r.get('title', '')} | {r.get('snippet', '')[:150]}"
            )

        prompt = f"""You are scoring candidates for an executive recruiting search in Japan.

The client is looking for:
---
{keywords_text.strip()}
---

Rate each candidate result below on a 0-10 scale:
- 10: Perfect match (exact role + location + seniority)
- 7-9: Strong match (right seniority, related role or location)
- 4-6: Possible match (some relevant signals)
- 1-3: Weak match (tangential)
- 0: Not relevant

Results:
{chr(10).join(entries)}

Return a JSON array where each item has:
- "index": result number (0-based)
- "score": integer 0-10
- "reason": one short sentence explaining the score
"""

        try:
            raw = call_gemini(prompt)
            scores = json.loads(raw)
            total_calls += 1

            if isinstance(scores, dict):
                scores = scores.get("results", scores.get("scores", scores.get("data", [])))

            score_map = {s["index"]: s for s in scores}

            for j, result in enumerate(batch):
                s = score_map.get(j, {})
                result["relevance_score"] = s.get("score", 0)
                result["score_reason"] = s.get("reason", "No score returned")

        except Exception as e:
            print(f"    Error in batch {batch_num}: {e}")
            for result in batch:
                result["relevance_score"] = 0
                result["score_reason"] = f"Scoring error: {e}"

    # Sort all results by score (descending)
    all_results = person_results + non_person_results
    all_results.sort(key=lambda r: r.get("relevance_score", 0), reverse=True)

    scored_count = sum(1 for r in all_results if r.get("relevance_score", 0) > 0)
    print(f"\n  Gemini calls: {total_calls}")
    print(f"  Results scored > 0: {scored_count}/{len(all_results)}")

    return all_results
