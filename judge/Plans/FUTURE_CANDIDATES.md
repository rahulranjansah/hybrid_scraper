# Plan — Future-candidates postprocess (separate timing-reds from permanent-reds)

Status: **not implemented yet** — captured here before the DSPy work so we
don't lose it.

## Why

Not all REDs are equal. Some are permanent exclusions (recruiter, client,
wrong function) — those people will never be candidates for this brief.
Others are **timing exclusions** — the person fits, but they just moved
jobs / have very short current tenure, so they can't be approached now.
Those people are valuable **future-candidates**: approach them again in
~12 months and the `just_changed_jobs` concern is gone.

User directive (2026-04-21):
> "we will develop a preprocess for RED which has people just changed
> jobs separately ... they might be relevant in a year"

## The split

After the judge assigns a label + tags, a postprocess routes red rows
into two sub-buckets:

### `red_permanent`
The person is genuinely not a fit for the brief. Any of:
- `is_recruiter`
- `is_founder_or_self_employed`
- `is_client_employee`
- `level_too_senior_for_brief`
- `age_56_plus`
- `graduation_before_1989`
- `country_manager_not_hr`
- `not_hr_role`
- `insufficient_japanese`
- `dnc_internal`
- `interim_or_consulting_recent`

### `red_reapproach_later`
The person likely fits, but timing makes them unreachable *now*. Any of:
- `just_changed_jobs`
- `short_current_tenure`
- `recently_joined`

These rows get an additional field `reapproach_after` — an ISO date,
default **today + 12 months**. A future backlog job can re-ingest the
`red_reapproach_later` list on or after that date and resubmit to the
judge; if the timing tags no longer apply (based on current tenure in
the LinkedIn profile), they upgrade to green / yellow / red-permanent
automatically.

## Routing rule

```python
TIMING_REDS = {"just_changed_jobs", "short_current_tenure", "recently_joined"}
PERMANENT_REDS = { ... all other red tags ... }

def route_red(tags: set[str]) -> str:
    if tags & PERMANENT_REDS:
        return "red_permanent"          # permanent wins if both are present
    if tags & TIMING_REDS:
        return "red_reapproach_later"
    return "red_permanent"              # safe default
```

*Permanent wins if both categories fire.* A recruiter who also just
changed jobs is still a recruiter; timing doesn't help.

## Output fields (added to judge output)

```json
{
  "name": "...",
  "label": "red",
  "red_bucket": "red_reapproach_later",
  "reapproach_after": "2027-04-21",
  "reasoning_tags": ["just_changed_jobs", "multinational_hr_experience"],
  "reasoning_text": "..."
}
```

Green/yellow rows have `red_bucket: null` and `reapproach_after: null`.

## Where it fits in the pipeline

```
candidate ──► [Judge: ExplainThenLabel (DSPy)]
                       │
                       ├──► green/yellow rows → final output as-is
                       │
                       └──► red rows ──► [Postprocess: route_red]
                                              │
                                              ├──► red_permanent
                                              │    (final output)
                                              │
                                              └──► red_reapproach_later
                                                   + reapproach_after date
                                                   (stored for later rerun)
```

## Implementation notes

- The judge itself stays unchanged — it still emits a single `label` and
  tags. The split is postprocessing only, so this doesn't complicate the
  DSPy signature or the rubric.
- Store the `red_reapproach_later` bucket in a dedicated CSV
  (`IO/stepN_output/red_reapproach_later.csv`) — easy to cron against.
- `reapproach_after` default is 12 months; make the window configurable
  in case the user wants different thresholds per tag
  (e.g. 6 months for `short_current_tenure`, 12 months for
  `just_changed_jobs`).

## TODOs (for when we implement)

- [ ] Decide per-tag reapproach windows (default 12 mo for all, or
      per-tag different values?)
- [ ] Add `route_red` to `judge/step4_judge.py` (once that exists)
      as a pure function called after label derivation
- [ ] Persist the future-candidate list in a stable schema (CSV or
      JSONL) with headers: name, linkedin_url, email, tags,
      reapproach_after, original_brief
- [ ] Plan the re-ingestion loop — Step 6 (future): a script that
      filters the future-candidate list by `reapproach_after <= today`
      and resubmits to the judge with a fresh LinkedIn scrape
