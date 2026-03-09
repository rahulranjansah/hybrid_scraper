"""
Stage 3: AI Person Extractor

Takes search results (url + title + snippet) and uses Gemini to extract
structured person data. Replaces the regex-based extract_people_hints().

Why AI beats regex here:
- Regex only caught "田中太郎氏" patterns — missed English names, unusual formats
- AI reads context: "Reiko Mukai - CHRO at MetLife Japan" → name, title, company
- AI can tell the difference between a person profile and an event listing

Batches results into groups of 10 to minimize Gemini calls.
Model: gemini-2.5-flash-lite, 1024 token cap per call.
"""

import json
from .query_generator import call_gemini

# How many search results to send to Gemini at once
# 10 results ≈ 300-400 input tokens (titles + snippets are short)
BATCH_SIZE = 10


def _build_extraction_prompt(results_batch: list[dict]) -> str:
    """Build the prompt for Gemini to extract person data from search results."""

    # Format each result as a numbered entry
    entries = []
    for i, r in enumerate(results_batch):
        entries.append(
            f'{i}. URL: {r["url"]}\n'
            f'   Title: {r.get("title", "")}\n'
            f'   Snippet: {r.get("snippet", "")[:200]}'
        )

    results_text = "\n".join(entries)

    return f"""You are analyzing search results from a recruiting pipeline targeting executive HR professionals in Japan.

For each search result below, determine if it contains or references a real person (not a job listing, event page, or generic article).

Results:
{results_text}

For each result, return a JSON array where each item has:
- "index": the result number (0-based)
- "is_person": true if this result references or contains a specific real person
- "name": person's full name (or null if not identifiable)
- "title": their job title (or null)
- "company": their company (or null)
- "source_type": one of "profile", "event_speaker", "press_release", "article", "presentation", "other"
- "employment_type": one of "employee", "founder", "self_employed", "recruiter", "consultant", "unknown"
- "seniority": one of "c_level", "vp", "director", "head", "manager", "senior_manager", "other", "unknown"

Only extract what you can clearly see in the title and snippet. Don't guess or infer.
If a result mentions multiple people, return multiple entries with the same index.
"""


def extract_people(results: list[dict]) -> list[dict]:
    """
    Use Gemini to extract person data from search results.

    Args:
        results: List from Stage 2 — each has url, title, snippet, site_group, etc.

    Returns:
        The same results list, enriched with person extraction data:
        - "people": list of extracted people [{name, title, company, source_type}]
        - "is_person_result": whether this result references a real person

    Cost: 1 Gemini call per 10 results
    """
    if not results:
        return results

    # Process in batches
    total_calls = 0

    for batch_start in range(0, len(results), BATCH_SIZE):
        batch = results[batch_start:batch_start + BATCH_SIZE]
        batch_num = batch_start // BATCH_SIZE + 1
        total_batches = (len(results) + BATCH_SIZE - 1) // BATCH_SIZE

        print(f"  [Extract batch {batch_num}/{total_batches}] Analyzing {len(batch)} results...")

        prompt = _build_extraction_prompt(batch)

        try:
            raw = call_gemini(prompt)
            extractions = json.loads(raw)
            total_calls += 1

            # Handle wrapped response
            if isinstance(extractions, dict):
                extractions = extractions.get("results", extractions.get("data", []))

            # Map extractions back to results by index
            by_index = {}
            for ext in extractions:
                idx = ext.get("index", -1)
                if idx not in by_index:
                    by_index[idx] = []
                by_index[idx].append(ext)

            # Enrich each result in this batch
            for j, result in enumerate(batch):
                entries = by_index.get(j, [])
                people = []
                for e in entries:
                    if e.get("is_person"):
                        people.append({
                            "name": e.get("name"),
                            "title": e.get("title"),
                            "company": e.get("company"),
                            "source_type": e.get("source_type", "other"),
                            "employment_type": e.get("employment_type"),
                            "seniority": e.get("seniority"),
                        })

                result["people"] = people
                result["is_person_result"] = len(people) > 0

        except Exception as e:
            print(f"    Error in batch {batch_num}: {e}")
            for result in batch:
                result["people"] = []
                result["is_person_result"] = False

    person_count = sum(1 for r in results if r.get("is_person_result"))
    total_people = sum(len(r.get("people", [])) for r in results)
    print(f"\n  Gemini calls: {total_calls}")
    print(f"  Results with people: {person_count}/{len(results)}")
    print(f"  Total people extracted: {total_people}")

    return results


# --- Test ---
if __name__ == "__main__":
    # Test with a few realistic results
    test_results = [
        {
            "url": "https://jp.linkedin.com/in/reiko-mukai-10a6b88",
            "title": "Reiko Mukai - CHRO at MetLife Japan | LinkedIn",
            "snippet": "View Reiko Mukai's profile on LinkedIn, a professional community...",
            "site_group": "professional_profiles",
        },
        {
            "url": "https://loglass-tech.connpass.com/event/383783/",
            "title": "胆力あるHRBPへの進化論 〜採用のその先へ。事業と経営を動かす...",
            "snippet": "VP of HR、ラクスル株式会社にてHRBPマネージャー、matsuri technologies株式会社にて人事部長を務める。",
            "site_group": "conference_and_events",
        },
        {
            "url": "https://peatix.com/event/4856062",
            "title": "【レバレジーズ人事責任者登壇】採用人数を50名から1000...",
            "snippet": "人事責任者が徹底解説！マーケティング思考で解く次世代HRBPの実践論",
            "site_group": "conference_and_events",
        },
    ]

    print("=== AI Person Extractor Test ===\n")
    enriched = extract_people(test_results)

    for r in enriched:
        print(f"\n[{r['site_group']}] {r['title'][:60]}")
        print(f"  URL: {r['url']}")
        print(f"  People found: {len(r['people'])}")
        for p in r["people"]:
            print(f"    - {p['name']} | {p['title']} | {p['company']} ({p['source_type']})")
