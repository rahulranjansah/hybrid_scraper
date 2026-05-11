"""
Stage 2: URL Harvester

Takes the queries from Stage 1 (query_generator) and runs them through
Brave and/or Serper to collect URLs.

This is the one stage where search APIs beat AI — they have the web index,
we just need the URLs + snippets they return.

Engine routing:
- Brave: broad keyword search (can't do site:, so we strip it)
- Serper: used for social/profile queries where site: targeting matters
"""

import os
import re
import time
import requests
from dotenv import load_dotenv

load_dotenv()

SERPER_API_KEY = os.getenv("SERPER_API_KEY")
BRAVE_API_KEY = os.getenv("BRAVE_API_KEY")

SERPER_URL = "https://google.serper.dev/search"
BRAVE_URL = "https://api.search.brave.com/res/v1/web/search"

# Delay between API calls — Brave free tier rate-limits at ~1 req/sec
REQUEST_DELAY = 1.5

# Retry config for 429 rate limits
MAX_RETRIES = 2
RETRY_BACKOFF = 3  # seconds — doubles each retry (3s, 6s)

# Job board / recruiter domains — these match keywords but never contain people profiles
JOB_BOARD_DOMAINS = {
    "glassdoor.com",
    "indeed.com",
    "robertwalters.co.jp",
    "robertwalters.com",
    "michaelpage.co.jp",
    "michaelpage.com",
    "roberthalf.com",
    "roberthalf.jp",
    "randstad.co.jp",
    "hays.co.jp",
    "enworld.com",
    "builtin.com",
    "ziprecruiter.com",
    "monster.com",
    "jac-recruitment.jp",
    "recruit.co.jp",
    "en-japan.com",
    "mynavi.jp",
    "rikunabi.com",
    "doda.jp",
    "makanapartners.com",
}

# URL path patterns that indicate job listings, not people
JOB_PATH_PATTERNS = ["/jobs/", "/job/", "/careers/", "/career/", "/vacancies/", "/求人/"]

# Groups that need site: targeting — route to Serper when available
SITE_TARGETING_GROUPS = {"social", "professional_profiles"}


def _is_job_listing(url: str) -> bool:
    """Check if a URL is a job board or job listing page."""
    url_lower = url.lower()

    # Check domain
    for domain in JOB_BOARD_DOMAINS:
        if domain in url_lower:
            return True

    # Check path patterns
    for pattern in JOB_PATH_PATTERNS:
        if pattern in url_lower:
            return True

    return False


def _request_with_retry(method, url, retries=MAX_RETRIES, **kwargs) -> requests.Response:
    """Make an HTTP request with retry on 429 rate limits."""
    for attempt in range(retries + 1):
        resp = method(url, timeout=15, **kwargs)
        if resp.status_code == 429 and attempt < retries:
            wait = RETRY_BACKOFF * (2 ** attempt)
            print(f"    Rate limited (429). Waiting {wait}s before retry {attempt + 1}/{retries}...")
            time.sleep(wait)
            continue
        resp.raise_for_status()
        return resp
    return resp  # shouldn't reach here, but just in case


def _search_brave(query: str, num_results: int = 10) -> list[dict]:
    """
    Search Brave. Returns list of {url, title, snippet}.

    Brave can't handle site: operators — so we strip them and search
    with just the keywords + "Japan" for relevance.
    """
    if not BRAVE_API_KEY:
        return []

    # Strip all site: operators — Brave can't use them
    clean_q = re.sub(r'\(?\s*site:\S+\s*(?:OR\s*)?', '', query).strip()
    clean_q = re.sub(r'\s+OR\s+(?=\))', '', clean_q)  # clean leftover OR
    clean_q = clean_q.strip("() ")

    # Add Japan context if not already present — keeps Brave results relevant
    if "japan" not in clean_q.lower() and "日本" not in clean_q:
        clean_q = f"{clean_q} Japan"

    resp = _request_with_retry(
        requests.get, BRAVE_URL,
        headers={"X-Subscription-Token": BRAVE_API_KEY, "Accept": "application/json"},
        params={"q": clean_q, "count": min(num_results, 20)},
    )

    results = resp.json().get("web", {}).get("results", [])
    return [
        {"url": r.get("url", ""), "title": r.get("title", ""), "snippet": r.get("description", "")}
        for r in results
    ][:num_results]


def _search_serper(query: str, num_results: int = 10) -> list[dict]:
    """Search Serper. Handles site: operators natively (Google proxy)."""
    if not SERPER_API_KEY:
        return []

    resp = _request_with_retry(
        requests.post, SERPER_URL,
        headers={"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"},
        json={"q": query, "num": min(num_results, 10)},
    )

    results = resp.json().get("organic", [])
    return [
        {"url": r.get("link", ""), "title": r.get("title", ""), "snippet": r.get("snippet", "")}
        for r in results
    ][:num_results]


def _pick_engine(query: dict, engines: list[str]) -> str:
    """
    Pick the best engine for a query.

    Social/profile queries need site: targeting → use Serper if available.
    Everything else → use Brave (cheaper, broader).
    """
    group = query.get("site_group", "")
    if group in SITE_TARGETING_GROUPS and "serper" in engines:
        return "serper"
    return engines[0]


MAX_RESULTS = 100  # increased to find 15+ new profiles after filtering


def _interleave_queries(queries: list[dict]) -> list[dict]:
    """
    Interleave queries across site groups so each group gets a fair shot
    before early exit kicks in.

    Without this, social queries always come last and never run.
    With this: [profiles_1, conference_1, content_1, social_1, profiles_2, ...]
    """
    by_group = {}
    for q in queries:
        group = q.get("site_group", "other")
        if group not in by_group:
            by_group[group] = []
        by_group[group].append(q)

    interleaved = []
    groups = list(by_group.values())
    max_len = max((len(g) for g in groups), default=0)
    for i in range(max_len):
        for group_queries in groups:
            if i < len(group_queries):
                interleaved.append(group_queries[i])

    return interleaved


def harvest_urls(
    queries: list[dict],
    engines: list[str] = None,
    results_per_query: int = 10,
) -> list[dict]:
    """
    Run a list of queries through search engines and collect deduplicated results.

    Smart routing: uses Serper for queries that need site: targeting (social, profiles),
    Brave for everything else. Falls back to whatever is available.

    Args:
        queries: List from Stage 1 — each has "query", "site_group", "intent", "sites"
        engines: Available engines. Default: ["brave"]. Add "serper" for social targeting.
        results_per_query: Results to request per query per engine

    Returns:
        List of deduplicated result dicts (job listings filtered out):
        {url, title, snippet, site_group, intent, engine}
    """
    if engines is None:
        engines = ["brave"]

    # Interleave queries so each group gets at least one shot before early exit
    queries = _interleave_queries(queries)

    all_results = []
    total_api_calls = 0

    for i, q in enumerate(queries, 1):
        query_str = q["query"]
        group = q.get("site_group", "unknown")
        intent = q.get("intent", "")

        engine = _pick_engine(q, engines)
        print(f"[{i}/{len(queries)}] {group} ({engine}): {query_str[:70]}...")

        try:
            if engine == "brave":
                raw = _search_brave(query_str, results_per_query)
            elif engine == "serper":
                raw = _search_serper(query_str, results_per_query)
            else:
                raw = []

            total_api_calls += 1

            for r in raw:
                r["site_group"] = group
                r["intent"] = intent
                r["engine"] = engine

            all_results.extend(raw)
            print(f"  [{engine}] {len(raw)} results")

        except Exception as e:
            print(f"  [{engine}] Error: {e}")

        # Early exit if we have enough raw results
        if len(all_results) >= MAX_RESULTS:
            print(f"\n  Hit {MAX_RESULTS} raw results — stopping early to save API calls.")
            break

        time.sleep(REQUEST_DELAY)

    # Deduplicate by URL + filter out job listings
    seen = set()
    unique = []
    skipped_jobs = 0
    for r in all_results:
        clean_url = r["url"].split("?")[0].rstrip("/").lower()
        if not clean_url or clean_url in seen:
            continue
        if _is_job_listing(r["url"]):
            skipped_jobs += 1
            continue
        seen.add(clean_url)
        unique.append(r)

    print(f"\n--- Harvest summary ---")
    print(f"  Queries run:      {len(queries)}")
    print(f"  API calls made:   {total_api_calls}")
    print(f"  Raw results:      {len(all_results)}")
    if skipped_jobs:
        print(f"  Job listings dropped: {skipped_jobs}")
    print(f"  Usable results:   {len(unique)}")

    return unique


# --- Test ---
if __name__ == "__main__":
    test_queries = [
        {
            "query": 'site:jp.linkedin.com ("HR Director" OR "HRBP" or "Head of HR") ("Tokyo" OR "東京")',
            "site_group": "professional_profiles",
            "intent": "Find HR leaders on LinkedIn Japan",
            "sites": ["jp.linkedin.com"],
        },
        {
            "query": 'site:connpass.com OR site:peatix.com ("HR" OR "人事") (登壇 OR speaker)',
            "site_group": "conference_and_events",
            "intent": "Find HR professionals at events",
            "sites": ["connpass.com", "peatix.com"],
        },
    ]

    print("=== URL Harvester Test ===\n")
    results = harvest_urls(test_queries, engines=["brave"])

    print(f"\nTop results:")
    for r in results[:5]:
        print(f"  [{r['site_group']}] {r['title'][:60]}")
        print(f"    {r['url']}")
