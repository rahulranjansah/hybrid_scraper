# Hybrid Scrape — Changelog

---

## v0.1 — 2026-02-16

**What changed:** Rebuilt the sourcing pipeline as a hybrid (search APIs + AI).

| Decision | Old way | New way | Why |
|----------|---------|---------|-----|
| Query generation | Hardcoded boolean builder + city map | Gemini generates queries from keywords | No more code changes for new roles/cities |
| Person extraction | Regex on Japanese name patterns | Gemini reads snippets, extracts people | Regex missed most names |
| Ranking | BM25 keyword frequency | Gemini scores relevance | BM25 can't judge seniority/fit |
| Conference focus | Separate scraper, speakers only | One of four site groups, not a filter | Want all qualified execs, not just speakers |
| Model choice | N/A | gemini-2.5-flash-lite, 1024 token cap | Cheapest, 1000 RPD free tier. 2.0-flash retires March 3 |
| Page scraping | N/A | Snippets only for now | Faster iteration, add full pages later |

**Kept:** Brave + Serper for URL harvesting — AI can't replace a search index.

**Engine notes:**
- Brave can't handle `site:` — we strip it and search keywords + "Japan" instead. AI filters quality
- Serper handles `site:` natively (Google proxy) — better for targeted domain searches
- Brave free tier rate-limits fast — need 1.5s delay between calls, still hits 429s on 7+ queries
- Default is Brave-only (cheaper), use `--engines brave serper` for better results

**First run stats (v0.1):**
- 7 queries → 50 raw results → 29 unique → 5 people extracted → 1 high-relevance candidate
- Cost: 1 Gemini (queries) + 5 Brave (2 rate-limited) + 3 Gemini (extract) + 1 Gemini (score) = 5 Gemini + 5 Brave calls
- Snippet-only extraction found names from LinkedIn/corporate pages but missed event speakers (names hidden in page body)

**Fallback:** All old modules still work. See [RUNBOOK.md](../RUNBOOK.md).

---

## v0.1.1 — 2026-02-16

**Fixes after first run.**

- **Job listing filter:** Block 20 job board domains (glassdoor, robertwalters, michaelpage, etc.) + path patterns (`/jobs/`, `/career/`, `/求人/`). First run had ~15/29 results as job board noise
- **Rate limit retry:** 429s now retry twice with backoff (3s, 6s) instead of silently failing. Last run lost 2/7 queries to Brave rate limits
- **Smart engine routing:** Social/profile queries auto-route to Serper (handles `site:`) when `--engines brave serper` is used. Brave stays default for broad searches
- **Early exit:** Stop harvesting at 50 raw results — no point waiting for all queries when we have enough data

**v0.1.1 run stats (Brave + Serper):**
- 8 queries → 50 raw → 21 job listings dropped → 29 usable → 10 people → 8 high-relevance (score ≥ 7)
- Top finds: Koji Date (HR Country Manager, Momentive), Chiharu I. (Head of Japan HR, Analog Devices), Ryo Konno (Head of HR Japan, Biogen)
- Cost: 4 Gemini + 6 Brave + 2 Serper calls

**Scraping feasibility note:**
- Conference sites (jinjibu, connpass, peatix) = public HTML, scrapable
- LinkedIn = auth wall, needs Apify (~$5/1K profiles), skip for now
- Decision: quick wins first (explainer filter, recruiter detection), full page scraping as v0.2

---

## v0.2 — 2026-02-16

**Social media coverage + LinkedIn enrichment.**

- **Query interleaving:** Queries now round-robin across groups (profiles→conference→content→social→profiles→...) so every group gets at least one shot before MAX_RESULTS early exit. Previously social queries always came last and never ran.
- **LinkedIn URL finder (Stage 3.5):** After extracting people, looks up their LinkedIn profile URL via Serper. People already found on LinkedIn get the source URL attached for free. Others get a `"Name" site:linkedin.com` lookup (1 Serper call each).
- **CSV output:** New `people_linkedin` column with LinkedIn URLs for each candidate.
- **Summary output:** LinkedIn URLs shown alongside top candidates.
