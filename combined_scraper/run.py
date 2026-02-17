"""
Hybrid Scrape Pipeline — Runner

Ties all stages together:
  Stage 1: Gemini generates search queries from keywords
  Stage 2: Brave/Serper harvests URLs
  Stage 3: Gemini extracts person data from snippets
  Stage 3.5: Look up LinkedIn URLs for found people
  Stage 4: Gemini scores relevance (replaces BM25)
  Stage 5: Export to CSV + JSON

Usage:
    # Full run with Google Doc keywords
    python -m combined_scraper.run --doc-url "https://docs.google.com/document/d/.../edit"

    # Full run with inline keywords
    python -m combined_scraper.run --keywords "CHRO, HR Director, Tokyo"

    # Dry run — generate queries only, no search API calls
    python -m combined_scraper.run --keywords "CHRO, HR Director, Tokyo" --dry-run

    # Use both search engines
    python -m combined_scraper.run --keywords "..." --engines brave serper

    # Only search specific site groups
    python -m combined_scraper.run --keywords "..." --groups professional_profiles conference_and_events
"""

import argparse
import csv
import json
import os
import sys
from datetime import datetime

# Add project root so we can import src/ modules
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

from combined_scraper.query_generator import generate_queries, TARGET_SITES
from combined_scraper.url_harvester import harvest_urls
from combined_scraper.ai_extractor import extract_people
from combined_scraper.linkedin_finder import find_linkedin_urls
from combined_scraper.ai_scorer import score_results

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")


def fetch_keywords_from_doc(doc_url: str) -> str:
    """Reuse the existing Google Doc fetcher."""
    from src.google_doc_fetcher import fetch_google_doc
    return fetch_google_doc(doc_url)


def save_csv(results: list[dict], filepath: str) -> None:
    """Save results to CSV."""
    if not results:
        return

    fieldnames = [
        "relevance_score", "score_reason", "url", "title", "snippet",
        "site_group", "engine", "people_names", "people_titles", "people_companies",
        "people_linkedin",
    ]

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for r in results:
            row = dict(r)
            people = r.get("people", [])
            row["people_names"] = "; ".join(p.get("name", "") for p in people if p.get("name"))
            row["people_titles"] = "; ".join(p.get("title", "") for p in people if p.get("title"))
            row["people_companies"] = "; ".join(p.get("company", "") for p in people if p.get("company"))
            row["people_linkedin"] = "; ".join(p.get("linkedin_url", "") for p in people if p.get("linkedin_url"))
            writer.writerow(row)

    print(f"Saved CSV: {filepath}")


def save_json(results: list[dict], filepath: str) -> None:
    """Save results to JSON (preserves all fields)."""
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"Saved JSON: {filepath}")


def main():
    parser = argparse.ArgumentParser(description="Hybrid sourcing pipeline (search + AI)")
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--doc-url", help="Google Doc URL with keywords")
    input_group.add_argument("--keywords", help="Comma-separated keywords (inline)")

    parser.add_argument("--engines", nargs="+", default=["brave"],
                        choices=["brave", "serper"],
                        help="Search engines to use (default: brave)")
    parser.add_argument("--groups", nargs="+", default=None,
                        choices=list(TARGET_SITES.keys()),
                        help="Site groups to search (default: all)")
    parser.add_argument("--results-per-query", type=int, default=10,
                        help="Results per query per engine (default: 10)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Generate queries only, no searching")
    parser.add_argument("--output-name", type=str, default=None,
                        help="Custom output filename (without extension)")
    args = parser.parse_args()

    # --- Stage 0: Get keywords ---
    print("=" * 60)
    print("HYBRID SOURCING PIPELINE")
    print("=" * 60)

    if args.doc_url:
        print(f"\n[Stage 0] Fetching keywords from Google Doc...")
        keywords_text = fetch_keywords_from_doc(args.doc_url)
    else:
        # Convert comma-separated to newline-separated
        keywords_text = "\n".join(k.strip() for k in args.keywords.split(","))

    print(f"\nKeywords:\n  {keywords_text.strip()}\n")

    # --- Stage 1: AI generates search queries ---
    print("[Stage 1] Generating search queries with Gemini...")
    if args.groups:
        # Generate queries for each requested group
        all_queries = []
        for group in args.groups:
            all_queries.extend(generate_queries(keywords_text, site_group=group))
    else:
        all_queries = generate_queries(keywords_text)

    print(f"\n  Generated {len(all_queries)} queries:")
    for i, q in enumerate(all_queries, 1):
        print(f"    {i}. [{q.get('site_group')}] {q['query'][:80]}...")

    if args.dry_run:
        print("\n--- DRY RUN — stopping before search ---")
        print(f"Would make ~{len(all_queries) * len(args.engines)} search API calls")
        return

    # --- Stage 2: URL harvesting ---
    print(f"\n[Stage 2] Harvesting URLs via {', '.join(args.engines)}...")
    results = harvest_urls(all_queries, engines=args.engines, results_per_query=args.results_per_query)

    if not results:
        print("\nNo results found. Try different keywords or engines.")
        return

    # --- Stage 3: AI person extraction ---
    print(f"\n[Stage 3] Extracting people with Gemini...")
    results = extract_people(results)

    # --- Stage 3.5: LinkedIn URL lookup ---
    print(f"\n[Stage 3.5] Looking up LinkedIn URLs...")
    results = find_linkedin_urls(results)

    # --- Stage 4: AI relevance scoring ---
    print(f"\n[Stage 4] Scoring relevance with Gemini...")
    results = score_results(results, keywords_text)

    # --- Stage 5: Export ---
    print(f"\n[Stage 5] Exporting results...")
    os.makedirs(RESULTS_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = args.output_name or f"hybrid_results_{timestamp}"

    csv_path = os.path.join(RESULTS_DIR, f"{base_name}.csv")
    json_path = os.path.join(RESULTS_DIR, f"{base_name}.json")

    save_csv(results, csv_path)
    save_json(results, json_path)

    # --- Summary ---
    person_results = [r for r in results if r.get("is_person_result")]
    high_score = [r for r in results if r.get("relevance_score", 0) >= 7]

    print(f"\n{'=' * 60}")
    print(f"PIPELINE COMPLETE")
    print(f"{'=' * 60}")
    print(f"  Total results:     {len(results)}")
    print(f"  With people:       {len(person_results)}")
    print(f"  High relevance:    {len(high_score)} (score >= 7)")

    if high_score:
        print(f"\n  Top candidates:")
        for r in high_score[:10]:
            for p in r.get("people", []):
                name = p.get("name", "Unknown")
                title = p.get("title", "")
                company = p.get("company", "")
                score = r.get("relevance_score", 0)
                li = p.get("linkedin_url", "")
                print(f"    [{score}/10] {name} — {title} @ {company}")
                print(f"           {r['url']}")
                if li:
                    print(f"           LinkedIn: {li}")


if __name__ == "__main__":
    main()
