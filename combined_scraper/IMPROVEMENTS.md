# Hybrid Scrape — Improvements

What's not working, what could be better, ordered by impact.

---

## High impact

### 1. Too many "what is CHRO?" articles in results
**Problem:** Brave returns educational articles (kaonavi.jp, jmam.co.jp, alue.co.jp etc.) explaining what a CHRO is. These match keywords but contain zero people.
**Evidence:** 8 of 29 results in v0.1.1 were "CHROとは？" explainer articles.
**Fix options:**
- Add a content-site blocklist (like the job board list but for HR knowledge bases)
- Pre-filter: skip URLs that don't contain any target domain from our site groups
- Smarter Brave queries: add `-"とは" -"解説"` to exclude explainer content
**Status:** Not started

### 2. Conference pages have people buried in page body, not in snippets
**Problem:** jinjibu.jp conference pages list speakers inside the full HTML, but the snippet only shows the event title. AI extraction finds 0 people from these.
**Evidence:** jinjibu.jp/hr-conference/202411/ has the Hajimari CHRO in the snippet but jinjibu.jp/hr-conference/ (landing page) has nothing. 6 jinjibu pages returned 0 people.
**Fix options:**
- Fetch full page HTML for conference/event URLs, feed to Gemini for extraction (the "add full page scraping later" decision from v0.1)
- Or: only keep conference URLs that already have person names in the snippet
**Scraping feasibility:** Conference sites (jinjibu.jp, connpass.com, peatix.com) are public HTML — scrapable with plain requests. LinkedIn is NOT scrapable (auth wall, requires Apify or similar).
**Status:** Not started — planned for v0.2. Do quick wins (#1, #5) first.

### 3. Brave returns generic content because site: is stripped
**Problem:** Without site: operators, Brave just searches "CHRO Japan" and gets whatever Google/Brave thinks is popular — mostly blog posts and explainer articles.
**Evidence:** All 10 Brave results for query 4 (jinjibu/hrpro) were generic HR content, not actual jinjibu.jp pages.
**Fix options:**
- Add domain names as keywords to Brave queries (e.g., "jinjibu.jp CHRO Japan") — partial targeting
- Route more queries to Serper when site targeting matters
- Accept that Brave is best for broad discovery, not targeted site searches
**Status:** Partially addressed — "Japan" keyword added, smart routing routes profiles to Serper

---

## Medium impact

### 4. No Osaka results
**Problem:** All found candidates are in Tokyo. Osaka was in the keywords but no Osaka-based people surfaced.
**Fix options:**
- Generate separate queries per city (not just one combined query)
- Weight Osaka-specific queries higher
**Status:** Not started

### 5. Recruiter profiles in results
**Problem:** Jason Lewis (executive search recruiter) scored 6/10. He's a recruiter, not a candidate.
**Fix options:**
- Add recruiter signal words to the AI scoring prompt ("executive search", "recruiter", "headhunter" → lower score)
- Or add recruiter firms to the blocklist
**Status:** Not started

### 6. Missing company names for some candidates
**Problem:** Hayato Takahashi has no company extracted. 八木洋介 has no company. The Hajimari CHRO has no name.
**Root cause:** Snippet truncation — the info is on the page but not in the 200-char snippet.
**Fix:** Full page scraping for conference/corporate sites (same as #2). LinkedIn profiles need Apify — not worth it yet.
**Status:** Not started

---

## Low impact / future

### 7. Social profiles (Facebook/Twitter) not tested
**Problem:** Early exit at 50 results means social queries (7, 8) never ran.
**Fix:** Run with higher MAX_RESULTS or prioritize query order so social runs earlier.
**Status:** Fixed in v0.2 — query interleaving ensures every group gets at least one query before early exit.

### 8. Dedup across runs
**Problem:** Running the pipeline twice gives duplicate candidates.
**Fix:** Keep a seen-URLs file that persists across runs.
**Status:** Not started

### 9. Full page scraping for richer extraction
**What:** Fetch actual HTML from promising URLs, extract with Gemini.
**Feasibility check (v0.1.1):**
- Conference sites (jinjibu, connpass, peatix) — public HTML, scrapable with `requests`
- Corporate pages (prtimes, nikkei) — public HTML, scrapable
- LinkedIn — NOT scrapable (auth wall). Would need Apify actor (~$5/1000 profiles). Skip for now.
**Decision:** Start with conference/corporate sites only. LinkedIn enrichment deferred until pipeline proves value.
**When:** After quick wins (#1 explainer filter, #5 recruiter detection) are done.
**Status:** Planned for v0.2