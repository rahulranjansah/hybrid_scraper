# IO — Full Runtime Architecture

Top-to-bottom view of how the sourcing system runs. Two entry paths
(automated pipeline + interactive chat), one shared judge + one shared
master ledger.

---

## 1. Architecture (10 000 ft)

```
                    ┌────────────────────────────────────────────┐
                    │ STATIC CONFIG (read-only per run)          │
                    │ ─────────────────────────────────────────  │
                    │ .env                     → API keys        │
                    │ judge/IO/step3_dspy/     → crocs_brief.txt │
                    │ step3_dspy_judge.py      → 30-tag rubric   │
                    │                            + derive_label  │
                    │ ~/.claude/.../memory/    → user rules      │
                    └────────┬───────────────────────┬───────────┘
                             │                       │
                             ▼                       ▼
       ┌─────────────────────────────┐     ┌──────────────────────────┐
       │ [A] AUTOMATED PIPELINE      │     │ [B] CHAT / INTERACTIVE   │
       │ judge/run_crocs_hr.py       │     │ (this chat session)      │
       │                             │     │                          │
       │ Runs unattended, daily      │     │ On-demand per candidate  │
       │ cost ~$0.65 / run           │     │ cost $0 (chat sub)       │
       │ finds 10-15 net-new         │     │ verifies / deep-dives    │
       └────────┬────────────────────┘     └──────────┬───────────────┘
                │                                      │
                ▼                                      ▼
       ┌──────────────────────────────────────────────────────────────┐
       │ SHARED DEDUPE + LEDGER                                       │
       │ judge/master_ledger.py                                       │
       │                                                              │
       │ exclusion_keys()  = Crocs(164) ∪ untagged(32) ∪ preds(30)    │
       │                   = 196 keys, match by name OR LinkedIn URL  │
       │                                                              │
       │ add_untagged()    dedupe-append to untagged.xlsx + .json     │
       │ add_predictions() dedupe-append to predictions.xlsx + .json  │
       └──────────────────────────────┬───────────────────────────────┘
                                      │
                                      ▼
       ┌──────────────────────────────────────────────────────────────┐
       │ STORAGE                                                      │
       │                                                              │
       │ judge/IO/step1_parse/human_labels.jsonl   ← Crocs source     │
       │                                             (read-only, 164) │
       │                                                              │
       │ judge/IO/master/untagged.xlsx + .json     ← all NET-NEW seen │
       │ judge/IO/master/predictions.xlsx + .json  ← all NET-NEW rated│
       │                                                              │
       │ judge/IO/step5d_pipeline/results_<ts>.xlsx ← per-run top 20  │
       │ judge/IO/step5e_chat_found/*.json          ← per-chat snap   │
       └──────────────────────────────┬───────────────────────────────┘
                                      │
                                      ▼
       ┌──────────────────────────────────────────────────────────────┐
       │ SINKS (currently manual upload)                              │
       │                                                              │
       │ Google Sheet at PREDICTION_FINAL (in .env)                   │
       │ Google Sheet at UNTAGGED_DATA    (in .env)                   │
       │                                                              │
       │ Auto-sync code ready at judge/sync_sheets.py — activates     │
       │ when user drops credentials.json (see Plans/GOOGLE_SHEETS_   │
       │ SETUP.md); parked in Plans/BACKLOG.md                        │
       └──────────────────────────────────────────────────────────────┘
```

---

## 2. Path [A] — Automated pipeline stage-by-stage

Tracing ONE candidate (**Ryoko Kashiwagura**) through every function call.

```
 ENTRY: uv run python judge/run_crocs_hr.py --top 20 --results-per-query 10
 ─────────────────────────────────────────────────────────────────────────

 [0] load_brief()                                   judge/run_crocs_hr.py
     reads IO/step3_dspy/crocs_brief.txt
     OUT: full JD string (target roles, 5-10yr rule, etc.)

     ┌──────────────────────────────────────────────┐
     │                                              │
     ▼                                              │
 [1] generate_queries(keywords)   combined_scraper/query_generator.py
     └ Gemini flash-lite × 1                    ~2k tokens  ~$0.001
     IN : keywords string
     OUT: [{query: 'site:jp.linkedin.com "HR Manager" OR "人事部長" -recruiter',
            site_group, sites, intent}, ... 8 queries]

     │
     ▼
 [2] harvest_urls(queries, ["brave","serper"], results_per_query=10)
                                      combined_scraper/url_harvester.py
     └ Brave API × 80  +  Serper API × 80                  ~$0.50
     └ drops JOB_BOARD_DOMAINS (indeed, glassdoor, robertwalters, ...)
     └ dedupes by URL
     OUT: [{url, title, snippet, site_group, engine}, ...] ~60-100 rows

     EXAMPLE after this stage (Ryoko's row):
       url:     https://www.linkedin.com/in/ryoko-kashiwagura-b2369829
       title:   "Ryoko Kashiwagura - Head of HR / Senior HR Leader / ..."
       snippet: "Head of HR / Senior HR Leader / Strategic HRBP"

     │
     ▼
 [3] extract_people(results)      combined_scraper/ai_extractor.py
     └ Gemini flash-lite batched 10/call  × 6-10 calls    ~$0.05
     IN : title + snippet per URL
     OUT: +people=[{name, title, company, seniority, employment_type}]
          +is_person_result boolean

     EXAMPLE after this stage:
       people: [{ name: "Ryoko Kashiwagura",
                  title: "Head of HR",
                  company: null,
                  seniority: "head",
                  employment_type: "employee" }]
       is_person_result: true

     │
     ▼
 [3.1] filter_already_reviewed(results)        judge/run_crocs_hr.py
     └ master_ledger.exclusion_keys()  (196-key union, no API)
     └ match by normalised name OR LinkedIn URL
     OUT: only survivors — judge never pays for dupes

     Ryoko's row passes (not in any of Crocs/untagged/predictions).

     │
     ▼
 [3.5] find_linkedin_urls(results)    combined_scraper/linkedin_finder.py
     └ Serper "site:linkedin.com <name>" × ~20 calls        ~$0.02
     OUT: per person adds linkedin_url

     Ryoko's LinkedIn URL already present — no-op for her.

     │
     ▼
 [4] score_results(results, keywords, brief=crocs_brief)
                                      combined_scraper/ai_scorer.py
     └ DSPy Predict(ExplainThenLabel)  via step3_dspy_judge.py
     └ Gemini 2.5 flash × 1 per person-result (~20 calls)   ~$0.10
     └ temperature=0.0, max_tokens=4000, reasoning_effort="disable"

     PROMPT inputs:
       brief     = full crocs_brief.txt content
       candidate = format_candidate_for_judge(result, person) →
         """
         Name: Ryoko Kashiwagura
         Current role: Head of HR @ ?
         LinkedIn: https://www.linkedin.com/in/ryoko-kashiwagura-b2369829
         Seniority signal: head
         Employment type: employee
         Source URL: ...
         Page title: ...
         Snippet: ...
         """

     LLM OUTPUT (parsed by DSPy):
       reasoning_tags      : [golden_profile, level_matches_brief,
                              multinational_hr_experience, ...]
       reasoning_text      : 1-sentence grounding
       strengths           : 3-5 bullets
       weaknesses          : 2-4 bullets
       missing_data        : 2-3 verify-this items
       actionable_insights : 2-3 first-call questions

     CODE-LEVEL post-process:
       label = derive_label(tags)     → "golden"
       route = route_red(tags)        → N/A (not red)

     OUT (added to row): flag, reasoning_tags, reasoning_text,
                         strengths, weaknesses, missing_data,
                         actionable_insights, relevance_score,
                         [red_bucket, reapproach_after if red]

     │
     ▼
 [5] take_top_candidates(judged, top=20)  judge/run_crocs_hr.py
     └ sort by LABEL_RANK (golden > green > yellow > red)
     └ cap at top 20

     │
     ▼
 [6] master ledger writes                 master_ledger.py
     add_untagged(all_people, source=f"pipeline_{ts}")
     add_predictions(rated,   source=f"pipeline_{ts}")
     └ openpyxl append, dedupe in-sheet
     └ _sync_json() keeps .json twins in sync

     │
     ▼
 [7] per-run outputs                      judge/run_crocs_hr.py
     write_jsonl(top, f"results_{ts}.jsonl")
     write_xlsx(top,  f"results_{ts}.xlsx")   ← color-coded, 16 columns
```

---

## 3. Path [B] — Chat / interactive

Same judge rubric, different sourcing and verification. Runs entirely
in this chat session — no Python main, no API-key for LLM (chat sub
covers it).

```
 ENTRY: user asks "find more candidates"
 ─────────────────────────────────────────────────────────────────

 [C1] WebSearch  (×3-5 queries)             chat tool, no cost
      Uses same bilingual Japan patterns as query_generator.py:
        site:jp.linkedin.com "HR Manager" OR "HRBP" Tokyo retail
        site:jp.linkedin.com "Head of HR" OR "人事部長" consumer goods
        ...
      OUT: [{title, url, snippet}, ...]

      │
      ▼
 [C2] dedupe            master_ledger.exclusion_keys()
      Same 196-key set as pipeline. Run in chat via:
        from master_ledger import exclusion_keys, _key

      │
      ▼
 [C3] WebFetch (per candidate, when Japan-location unverified)
      URL: jp.linkedin.com/in/<slug>  (follow www→jp redirect)
      Prompt: location, current role, HR tenure, language signals,
              HR→non-HR transition check

      Verification rule — memory project_chat_search_japan_verify.md:
        Reliable   : www→jp redirect + profile location field
        Unreliable : jp.linkedin.com alone, snippet keywords alone

      │
      ▼
 [C4] apply rubric mentally          same 30 tags + v7 derive_label
      I produce the same output structure as stage [4] above,
      by hand in chat.

      │
      ▼
 [C5] master ledger writes           master_ledger.add_untagged +
                                     add_predictions
      source="chat_search_<date>"    so provenance is tracked.
```

**Same end state, different path.** Both paths hit the same xlsx files
and same dedupe. A candidate found in chat can't be re-surfaced by
tomorrow's pipeline run.

---

## 4. Runtime numbers — one pipeline day, seen so far

| Stage | Calls | Cost |
|---|---:|---:|
| [1] query gen (Gemini) | 1 | ~$0.001 |
| [2] URL harvest (Brave + Serper) | ~160 | ~$0.50 |
| [3] extraction (Gemini) | ~10 batches | ~$0.05 |
| [3.5] LinkedIn lookup (Serper) | ~20 | ~$0.02 |
| [4] judge (Gemini) | ~20 | ~$0.10 |
| **Total per run** | | **~$0.65** |

Chat path: $0 in API spend; uses your chat subscription.

---

## 5. Commands

```bash
# Full pipeline run, defaults (top=20, results-per-query=10)
cd /mnt/hardisk/sourcing
uv run python judge/run_crocs_hr.py

# Dry-run — generate queries only
uv run python judge/run_crocs_hr.py --dry-run

# Smaller / cheaper
uv run python judge/run_crocs_hr.py --top 10 --results-per-query 5

# Just sync xlsx to .json (no pipeline)
uv run python -c "from judge.master_ledger import _sync_json; _sync_json()"

# (future) push to Google Sheets
uv run python judge/sync_sheets.py
```

---

## 6. Invariants (what must always hold)

- `untagged.xlsx` and `predictions.xlsx` contain **only net-new** people — **never** Crocs rows
- The Crocs sheet (`human_labels.jsonl`) is **read-only** from the system's perspective; editing happens in Google Sheets and we re-fetch it when stale
- `exclusion_keys()` is the **single source of truth** for "have we seen this person"; both pipeline and chat paths go through it
- Judge output is **auditable**: label is derived in code from tags, tags are a closed `Literal` set, reasoning text grounds every tag
- `predictions` ⊆ `untagged` in steady state — every rated person is also in the seen-list
- Scores (the old `relevance_score`) are **slop** per user directive; `flag` is the only label we trust
