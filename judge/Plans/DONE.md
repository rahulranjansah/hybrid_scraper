# Done

Running log of finished steps. Newest on top.

## 2026-04-21

### Label semantics (from user, do NOT confuse)

- **RED = MISMATCH**  — candidate does not fit *this specific search*
- **YELLOW = OK**     — acceptable candidate
- **GREEN = RELEVANT** — strong, prize-pick match

Red is NOT "bad candidate" in the abstract — it's "wrong for this brief".
A recruiter gets red because recruiters aren't candidates, not because
they're low quality. Same for "client" (already placed, not sourceable).
The judge prompt in Step 4 must be framed as *fit for the brief*, not
*candidate quality*.

**Objective: aim for GREEN. Penalize both RED and YELLOW.**
Green is the only "hit" — yellow is "not good enough", red is "wrong person".
Metrics in Step 5 should be green-precision / green-recall primary,
not overall flag accuracy.

### Step 1 — Parsed human labels (final)

- **Source:** Google Sheet `1PTC1fTdjnLtYSgDFTdZDu5JeB48_oRLzdbJvnb4-a38`,
  exported as **.xlsx** via the public `?format=xlsx` endpoint (curl-able,
  no auth needed). The workbook has 18 sheet tabs (one per JD); this step
  parses the active sheet only: "Copy of Crocs — HR Manager".
- **Script:** `step1_parse_human_labels.py` (uses `openpyxl`).
- **Input:** `IO/step1_parse/human_labels.xlsx` (checked in, 296 KB).
  Legacy CSV `human_labels_raw.csv` also kept for reference.
- **Output:** `IO/step1_parse/human_labels.jsonl` (174 candidates).

### Real colour distribution (from xlsx cell fills, not inferred)

| Flag       | Meaning  | Count | Source color             |
|------------|----------|-------|--------------------------|
| green      | RELEVANT | 29    | `FF00FF00`               |
| yellow     | OK       | 26    | `FFFFFF00`               |
| red        | MISMATCH | 37    | `FFFF0000` + `FFCC0000`  |
| unflagged  | undecided| 82    | no fill                  |

Green is **rare** (17 % of rows) — the prize candidates.
47 % of rows are unflagged — treat as "no decision yet",
not as "neutral positive".

### Remark → flag signals (useful for Step 4 judge prompt)

- `"just changed jobs"`     → 7× red, 1× yellow
  (can't poach; mismatch for *sourceability*, not candidate quality)
- `"already 55 though"`     → 2× yellow
  (age is a soft concern, not an auto-mismatch like the scorer assumes)
- `"client"`                → 3× red
  (already on-payroll — conflict-of-interest, hard mismatch)
- `"client, but open to approach"` → 2× yellow
- `"too senior"`            → 1× red, 1× yellow (context-dependent)
- `"graduation year 1987/1988"` → 2× red
  (too senior-by-tenure — matches current scorer rule)
- `"recruiter"`             → 1× red (not a candidate pool at all)

### Scaffolded `judge/` layout

```
judge/
├── Plans/          planning + backlog + pipeline diagram (no data)
├── IO/
│   ├── step1_parse/
│   │   ├── human_labels.xlsx        (input, with colors)
│   │   ├── human_labels_raw.csv     (legacy input, colors stripped)
│   │   └── human_labels.jsonl       (output — 174 rows)
│   └── step2_rubric/
│       ├── colored_only.jsonl       (92 rows — green/yellow/red only)
│       ├── ambiguity_report.md      (4 open questions for user)
│       └── rubric_draft.md          (~26 draft reasoning tags)
├── step1_parse_human_labels.py
└── step2_draft_rubric.py
```

### Step 3 — DSPy judge wired (smoke-test blocked on API key)

- **Script:** `step3_dspy_judge.py`.
- **Dependencies:** `dspy==3.2.0` added via `uv add dspy`.
- **Model:** Claude Haiku (`anthropic/claude-haiku-4-5-20251001`),
  configured via `dspy.LM(...)` + `dspy.configure(...)`.
- **Signature:** `ExplainThenLabel(brief, candidate) -> reasoning_tags, reasoning_text`.
  No label output from the LLM — label is derived in code by
  `derive_label(tags)`. No score output (user directive: scores discarded).
- **Rubric tags hard-coded** into a `Literal` type from `rubric_v1.md`:
  5 green + 7 yellow + 11 red-permanent + 3 red-timing = 26 tags.
- **Future-candidates split:** `route_red(tags)` splits red predictions
  into `red_permanent` vs `red_reapproach_later`; timing-reds get a
  `reapproach_after` 12 months out.
- **Module validated** without API call: imports, derive_label logic,
  route_red logic, candidate formatter all pass sanity tests.
- **Blocker:** `ANTHROPIC_API_KEY` not in `.env` — script fails cleanly
  with a one-line instruction when run.
- **Brief TODO:** the JD text is a stub (`CROCS_BRIEF_STUB`) — user
  should replace with the real Crocs HR-Manager JD once available.

### Step 2 — Rubric v1 frozen

User answered the four ambiguity questions on 2026-04-21 — see
`IO/step2_rubric/ambiguity_resolutions.md`. Rollups into `rubric_v1.md`:

- **CHRO dropped as a target.** Crocs-brief target roles = HRBP /
  HR Business Partner / HR Manager / HRBP Manager / Senior HRBP /
  Senior HR Manager / HR Director / Head of HR. CHRO / VP / C-suite
  ⇒ `level_too_senior_for_brief` (RED).
- **Scores discarded.** The `human_score` column is AI-auto-generated,
  not human signal. Judge emits only a label; metrics are on label only.
- **Approachability = hard RED.** `just_changed_jobs`,
  `short_current_tenure` (<~6 mo), `recently_joined` — all red, no yellow.
- **Age threshold = 56+.** Moved from yellow (wrong) to hard RED.
  Rationale: Japanese retirement norms.
- **JD is a judge input.** Rubric tags stay brief-agnostic; the JD text
  is passed in at call time so the same rubric can serve other briefs.

### Step 2 — Ambiguity report + draft rubric (pre-annotation)

- **Data subset:** 92 colored rows only (dropped the 82 unflagged).
- **Key finding:** score is NOT predictive of flag — every score bucket
  9.5-10 through <7.0 has greens AND reds. The flag is a fit-to-brief
  verdict, not a quality rating. See `IO/step2_rubric/ambiguity_report.md`.
- **Biggest insight:** the JD is "HR Manager" but `ai_scorer.py` is tuned
  for CHRO/Director+ — several 10.0-scored CHROs were flagged RED by
  the human as *overqualified*. Rubric tags must be brief-agnostic
  (e.g. `level_matches_brief`, not `is_chro`).
- **Draft rubric** has 26 tags across 3 directions (green / yellow / red)
  in `IO/step2_rubric/rubric_draft.md`. Awaiting user edit-pass.
- **Configuration decisions (from user, 2026-04-21):**
  Crocs-only, colored-only, Claude Haiku, DSPy framework.
