# Combined Scraper

AI-powered executive sourcing pipeline for HR professionals in Japan.
Uses Gemini for query generation, person extraction, and relevance scoring.
Uses Brave + Serper for URL discovery.

---

## Setup

### 1. Create `.env` in the project root (`sourcing/.env`)

```env
GEMINI_API_KEY=your_key_here
BRAVE_API_KEY=your_key_here
SERPER_API_KEY=your_key_here
```

Get the keys from:

| Key | Where to get it | Free tier |
|-----|-----------------|-----------|
| `GEMINI_API_KEY` | [aistudio.google.com](https://aistudio.google.com) | 15 RPM / 1000 RPD |
| `BRAVE_API_KEY` | [brave.com/search/api](https://brave.com/search/api/) | 2000 queries/month |
| `SERPER_API_KEY` | [serper.dev](https://serper.dev) | 2500 queries on signup |

### 2. Install dependencies

```bash
uv sync
```

Or without uv:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

---

## How to run

All commands run from the `sourcing/` project root.

### First run — initial search

```bash
# Dry run first — preview generated queries, no API calls, free
python -m combined_scraper.run \
  --keywords "CHRO, HR Director, Head of HR, VP Human Resources, HRBP Director, Country HR Manager, Head of People, CPO, Tokyo, Osaka, Japan" \
  --engines brave serper \
  --dry-run

# Full run with both engines (best results)
python -m combined_scraper.run \
  --keywords "CHRO, HR Director, Head of HR, VP Human Resources, HRBP Director, Country HR Manager, Head of People, CPO, Tokyo, Osaka, Japan" \
  --engines brave serper
```

### Follow-up runs — find MORE candidates

Use `--exclude-csv` to skip already-found people and URLs. This avoids duplicates across runs.

```bash
python -m combined_scraper.run \
  --keywords "CHRO, HR Director, Head of HR, VP Human Resources, HRBP Director, Country HR Manager, Head of People, CPO, Tokyo, Osaka, Japan" \
  --engines brave serper \
  --exclude-csv combined_scraper/results/hybrid_results_20260216_022720.csv \
  --output-name hr_candidates_round2
```

### Other examples

```bash
# Brave only (cheaper, no site: targeting)
python -m combined_scraper.run --keywords "CHRO, HR Director, Tokyo"

# Google Doc keywords instead of inline
python -m combined_scraper.run --doc-url "https://docs.google.com/document/d/.../edit" --engines brave serper

# Only specific site groups
python -m combined_scraper.run --keywords "CHRO, Tokyo" --groups professional_profiles social

# Custom results count per query
python -m combined_scraper.run --keywords "CHRO, Tokyo" --engines brave serper --results-per-query 20
```

### CLI flags

| Flag | Default | What |
|------|---------|------|
| `--keywords` | — | Comma-separated keywords |
| `--doc-url` | — | Google Doc URL (alternative to --keywords) |
| `--engines` | `brave` | `brave`, `serper`, or both |
| `--groups` | all | `professional_profiles`, `conference_and_events`, `content_and_signals`, `social` |
| `--results-per-query` | 10 | Results per query per engine |
| `--dry-run` | off | Preview queries, no API calls |
| `--output-name` | timestamped | Custom output filename |
| `--exclude-csv` | — | Path to previous results CSV — skips already-found people/URLs |

---

## Pipeline stages

```
Keywords → [1] Gemini generates queries
         → [2] Brave/Serper harvest URLs (job listings filtered)
         → [3] Gemini extracts people from snippets
         → [3.5] Look up LinkedIn URLs for found people
         → [4] Gemini scores relevance (0-10)
         → [5] Export CSV + JSON
```

| Stage | Module | What |
|-------|--------|------|
| 1 | `query_generator.py` | Gemini generates search queries from keywords |
| 2 | `url_harvester.py` | Brave/Serper URL harvest, job board filter, query interleaving |
| 3 | `ai_extractor.py` | Gemini extracts name/title/company from snippets |
| 3.5 | `linkedin_finder.py` | Looks up LinkedIn profile URLs for found people |
| 4 | `ai_scorer.py` | Gemini scores relevance 0-10 against keywords |
| 5 | `run.py` | Export to `results/` as CSV + JSON |

---

### CSV columns

| Column | Example |
|--------|---------|
| `relevance_score` | 9 |
| `score_reason` | "CHRO at major Japanese company, Tokyo based" |
| `flag` | green / yellow / red |
| `url` | https://jp.linkedin.com/in/person |
| `title` | Page title |
| `snippet` | Search snippet |
| `site_group` | professional_profiles |
| `engine` | serper |
| `people_names` | Koji Date; Ryo Konno |
| `people_titles` | HR Country Manager; Head of HR |
| `people_companies` | Momentive; Biogen |
| `people_linkedin` | https://jp.linkedin.com/in/... |
| `people_employment_types` | employee; employee |
| `people_seniorities` | c_level; head |

### Flag colors

| Flag | Meaning |
|------|---------|
| **green** | Strong match — good candidate to approach |
| **yellow** | Recently changed jobs or minor concerns (domestic company, unclear scope) |
| **red** | Excluded — recruiter, founder, too senior age, below target seniority |

---