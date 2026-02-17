"""
Stage 1: AI Query Generator

Instead of maintaining hardcoded boolean queries and city maps,
we give Gemini the raw keywords from the Google Doc and ask it
to generate effective search queries for each target site.

Why this is better than boolean_search_builder.py:
- No hardcoded city map to maintain
- Gemini knows Japanese — handles bilingual terms automatically
- Adapts to whatever keywords are in the doc
- Can generate smarter queries than simple OR chains

Model: gemini-2.5-flash-lite (cheapest, 1000 RPD free tier)
Token cap: 1024 output tokens per call — enough for ~8 queries
"""

import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# gemini-2.5-flash-lite: cheapest model, highest free-tier quota (15 RPM, 1000 RPD)
# gemini-2.0-flash retires March 3, 2026 — don't use it
GEMINI_MODEL = "gemini-2.5-flash-lite"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"

# Safety: max output tokens per Gemini call
# 1024 tokens ≈ 600-800 words — plenty for a list of search queries
MAX_OUTPUT_TOKENS = 1024

# Sites we want to search — grouped by purpose
# These replace SITE_FILTERS in boolean_search_builder.py
# AND SITE_BATCHES in search_queries.py (conference scraper)
TARGET_SITES = {
    "professional_profiles": [
        "jp.linkedin.com",
        "bizreach.jp",
        "daijob.com",
        "careercross.com",
        "youtrust.jp",
    ],
    "conference_and_events": [
        "connpass.com",
        "peatix.com",
        "kokuchpro.com",
        "doorkeeper.jp",
        "jinjibu.jp",
        "hrpro.co.jp",
    ],
    "content_and_signals": [
        "speakerdeck.com",
        "slideshare.net",
        "note.com",
        "prtimes.jp",
    ],
    "social": [
        "wantedly.com",
        "twitter.com",
        "facebook.com",
    ],
}


def call_gemini(prompt: str) -> str:
    """
    Call Gemini API and return the text response.

    Uses gemini-2.5-flash-lite with a 1024-token output cap.
    Free tier: 15 requests/min, 1000 requests/day.
    """
    if not GEMINI_API_KEY:
        raise ValueError("No GEMINI_API_KEY in .env")

    response = requests.post(
        f"{GEMINI_URL}?key={GEMINI_API_KEY}",
        headers={"Content-Type": "application/json"},
        json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.2,  # low creativity — we want precise queries
                "maxOutputTokens": MAX_OUTPUT_TOKENS,
                "responseMimeType": "application/json",
            },
        },
        timeout=30,
    )
    response.raise_for_status()

    data = response.json()
    usage = data.get("usageMetadata", {})
    in_tokens = usage.get("promptTokenCount", "?")
    out_tokens = usage.get("candidatesTokenCount", "?")
    print(f"  [Gemini {GEMINI_MODEL}] {in_tokens} in / {out_tokens} out tokens")

    text = data["candidates"][0]["content"]["parts"][0]["text"]
    return text


def generate_queries(keywords_text: str, site_group: str = None) -> list[dict]:
    """
    Ask Gemini to generate search queries based on keywords and target sites.

    Args:
        keywords_text: Raw text from Google Doc (keywords, one per line)
        site_group: Which site group to target (None = all groups)

    Returns:
        List of dicts: [{"query": "...", "site_group": "...", "sites": [...]}]

    Cost: 1 Gemini call (~500 input tokens, ~500 output tokens)
    """
    if site_group and site_group in TARGET_SITES:
        groups = {site_group: TARGET_SITES[site_group]}
    else:
        groups = TARGET_SITES

    sites_description = json.dumps(groups, indent=2)

    prompt = f"""You are a search query expert for executive recruiting in Japan.

Given these keywords describing the type of candidate we're looking for:

---
{keywords_text.strip()}
---

And these target website groups:
{sites_description}

Generate effective Google search queries to find these people across the sites.

Rules:
- Use site: operators to target specific sites (e.g., site:jp.linkedin.com)
- Batch multiple sites from the same group using OR (e.g., site:connpass.com OR site:peatix.com)
- Include both English AND Japanese versions of job titles and locations
  (e.g., "Tokyo" OR "東京", "HR Director" OR "人事部長")
- Keep queries under 200 characters each (search engines truncate long queries)
- Generate 1-2 queries per site group — enough to cover the keywords without being too broad
- For conference/event sites, include words like 登壇, 講演, speaker — but don't limit to ONLY speakers
- Focus on finding PEOPLE, not job listings or generic articles

Return a JSON array where each item has:
- "query": the search query string
- "site_group": which group this targets
- "sites": list of site domains included
- "intent": one-line description of what this query is looking for
"""

    raw = call_gemini(prompt)
    queries = json.loads(raw)

    # Gemini might wrap the array in an object
    if isinstance(queries, dict) and "queries" in queries:
        queries = queries["queries"]

    return queries


# --- Test ---
if __name__ == "__main__":
    test_keywords = """
    Country Manager
    General Manager
    VP Human Resources
    Head of HR
    HRBP
    HR Director
    CHRO
    Tokyo
    Osaka
    """

    print("=== AI Query Generator ===\n")
    print(f"Keywords:\n{test_keywords.strip()}\n")
    print("Generating queries with Gemini...\n")

    try:
        queries = generate_queries(test_keywords)
        print(f"\nGenerated {len(queries)} queries:\n")
        for i, q in enumerate(queries, 1):
            print(f"{i}. [{q.get('site_group', '?')}]")
            print(f"   Intent: {q.get('intent', '?')}")
            print(f"   Query:  {q['query']}")
            print(f"   Sites:  {', '.join(q.get('sites', []))}")
            print()
    except Exception as e:
        print(f"Error: {e}")
