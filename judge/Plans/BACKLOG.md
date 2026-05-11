# Backlog

Ordered. One baby step per line. Mark done with `[x]`.

Label semantics: **red=MISMATCH, yellow=OK, green=RELEVANT**
(see Plans/DONE.md — do not confuse with "bad/ok/best").

**Objective:** always aim for GREEN. Penalize both RED and YELLOW.
Green is the only hit. Primary metrics should be green-precision and
green-recall, not overall flag accuracy.

## Now

- [ ] **Step 2 — Align AI scores with humans.**
      Join latest `combined_scraper/results/hybrid_results_*.csv` to
      `human_labels.jsonl` on LinkedIn URL (preferred) or normalized name.
      Output: `IO/step2_align/ai_vs_human.csv` with one row per match plus
      rows for "human-only" (candidates the scraper missed) and "ai-only"
      (scraper finds the scorer rated but humans never saw).
      No new model calls yet — this is just bookkeeping.

- [ ] **Step 3 — Disagreement report.**
      From the aligned CSV, pull the top 20 rows where AI and human
      disagree most (big score delta, or flag mismatch). This is the
      qualitative signal that shapes the judge prompt in Step 4.

- [ ] **Step 4 — LLM-judge prompt.**
      New module under `judge/`. Rubric = `IO/step2_rubric/rubric_v1.md`
      (25 frozen tags). Output per candidate: `{reasoning_tags,
      reasoning_text, label}` — NO score (scores discarded by user
      directive).

- [ ] **Step 4b — Future-candidates postprocess.** After the judge
      assigns a red label, split into `red_permanent` vs
      `red_reapproach_later` based on tags. Timing-reds
      (`just_changed_jobs`, `short_current_tenure`, `recently_joined`)
      get `reapproach_after = today + 12mo`. Full plan:
      [Plans/FUTURE_CANDIDATES.md](FUTURE_CANDIDATES.md).

- [ ] **Step 5 — Metrics.**
      Primary: **green precision** and **green recall** (is the judge
      picking out the 29 green rows and not over-picking?).
      Secondary: confusion matrix across red/yellow/green/unflagged,
      Cohen's kappa, MAE on score.
      Write to `IO/step5_report/report.md`. Keep old reports so we can
      see improvement across prompt iterations.

## Later / maybe

- [ ] **Variety mechanisms for daily-run drift.** As the ledger grows
      past ~200-300 entries, net-new per run will drop because most
      HR-Manager profiles in Japan are on a finite set of indexable
      pages. Mitigations when we hit that wall:
        - **Keyword drift:** rotate search terms per day (English
          labels one day, Japanese 人事 terms another, adjacent
          industries, etc.).
        - **Site-group rotation:** cycle which target groups get
          queried (conferences only Mondays, social-posts Tuesdays).
        - **Freshness re-crawl:** after 3-6 months, re-ingest the
          ledger — people's roles change, former-timing-reds may be
          reapproachable now.
        - **Expand TARGET_SITES:** add Japanese HR publication sites,
          specific conference series, etc. Current list is small.

- [ ] **Google Sheets auto-sync.** Code ready at `judge/sync_sheets.py`
      (gspread + OAuth); deferred because manual copy-paste works for
      now. To flip on: user drops `credentials.json` at
      `judge/IO/master/credentials.json`, runs `uv run python
      judge/sync_sheets.py` once for browser consent. Setup steps
      documented in `judge/Plans/GOOGLE_SHEETS_SETUP.md`.
      The `.env` already has `PREDICTION_FINAL` and `UNTAGGED_DATA`
      URLs pointing to the destination sheets.


- [ ] **LinkedIn scraping fallback (human-in-the-loop).** Real LinkedIn
      scraping is aggressively rate-limited, CAPTCHA-gated, and ToS-risky.
      Current pipeline uses snippet-level search (Brave/Serper) to locate
      profiles — that returns a URL + a ~150-char snippet, not a full
      profile. For candidates where we want full signal (tenure per role,
      language, education dates), we may need a human-assisted flow:
      the tool surfaces a LinkedIn URL, a human opens it in a browser,
      copy-pastes the profile text into a text box, the tool feeds that
      into the AI extractor. Plan this after the automated pipeline is
      producing results so we know which candidates warrant the manual
      step. For now, operate within the snippet-only pathway.


- [ ] Calibrate: does human "score 9" mean the same thing as AI "score 9"?
      Might need to rescale or score relatively (rank candidates, not
      assign absolute numbers).
- [ ] Handle ties and "client"/"was our candidate" — these aren't judgment
      of quality, they're business-state. Judge shouldn't mimic them.
- [ ] Consider a second-pass judge that takes the LinkedIn snippet as extra
      context (currently only title+snippet).
