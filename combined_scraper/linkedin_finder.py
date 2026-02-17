"""
Stage 3.5: LinkedIn Finder

After extracting people from search results, look up their LinkedIn profiles.
- If the source URL is already LinkedIn → use it directly (free)
- Otherwise → search Serper for "Name site:linkedin.com" (1 API call per person)

No scraping — just the profile URL. Apify would be needed to scrape content.

Cost: 1 Serper call per non-LinkedIn person found. Typically 3-8 calls per run.
"""

import time
from .url_harvester import _search_serper, REQUEST_DELAY


def find_linkedin_urls(results: list[dict]) -> list[dict]:
    """
    Enrich extracted people with LinkedIn profile URLs.

    For people already found on LinkedIn, the source URL is their profile.
    For people found on social/conference/content pages, search for their LinkedIn.

    Args:
        results: Enriched results from Stage 3 (with "people" field)

    Returns:
        Same results with "linkedin_url" added to each person dict.
    """
    already_have = 0
    lookups_needed = []

    for r in results:
        if not r.get("is_person_result"):
            continue

        is_linkedin_source = "linkedin.com" in r.get("url", "").lower()

        for person in r.get("people", []):
            if is_linkedin_source:
                person["linkedin_url"] = r["url"]
                already_have += 1
            elif person.get("name"):
                lookups_needed.append(person)
            else:
                person["linkedin_url"] = None

    if already_have:
        print(f"  {already_have} people already from LinkedIn — URL attached")

    if not lookups_needed:
        print("  No additional LinkedIn lookups needed.")
        return results

    print(f"  Looking up LinkedIn for {len(lookups_needed)} people via Serper...")
    found = 0

    for person in lookups_needed:
        name = person["name"]
        # Search for their LinkedIn profile — Serper handles site: natively
        query = f'"{name}" site:linkedin.com'

        try:
            hits = _search_serper(query, num_results=3)
            # Pick the first result that's actually a LinkedIn profile page
            linkedin_url = None
            for hit in hits:
                url = hit.get("url", "")
                if "linkedin.com/in/" in url or "linkedin.com/pub/" in url:
                    linkedin_url = url
                    break

            person["linkedin_url"] = linkedin_url
            if linkedin_url:
                found += 1
                print(f"    {name} → {linkedin_url}")
            else:
                print(f"    {name} → not found")

        except Exception as e:
            print(f"    {name} → error: {e}")
            person["linkedin_url"] = None

        time.sleep(REQUEST_DELAY)

    print(f"\n  LinkedIn lookups: {found}/{len(lookups_needed)} found")

    return results
