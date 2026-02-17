# Combined Scraper

AI-powered executive sourcing pipeline for HR professionals in Japan.
Uses Gemini for query generation, person extraction, and relevance scoring.
Uses Brave + Serper for URL discovery.

---

## Setup

```bash
source ~/.pyenv/versions/venv3.10/bin/activate
```

### Required `.env` keys (in project root)

| Key | What | Free tier |
|-----|------|-----------|
| `GEMINI_API_KEY` | Query gen, extraction, scoring | 15 RPM / 1000 RPD |
| `BRAVE_API_KEY` | Broad keyword search | 2000/month |
| `SERPER_API_KEY` | Targeted site: searches | 2500 on signup |

---

## How to run

```bash
# From the sourcing/ directory:

# Full run with both engines (best results)
python -m combined_scraper.run --keywords "CHRO, HR Director, Tokyo, Osaka" --engines brave serper

# Brave only (cheaper)
python -m combined_scraper.run --keywords "CHRO, HR Director, Tokyo"

# Dry run — generate queries only, no API calls
python -m combined_scraper.run --keywords "CHRO, HR Director, Tokyo" --dry-run

# Google Doc keywords instead of inline
python -m combined_scraper.run --doc-url "https://docs.google.com/document/d/.../edit" --engines brave serper

# Only specific site groups
python -m combined_scraper.run --keywords "..." --groups professional_profiles social
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

## Output

Files saved to `combined_scraper/results/`:
- `hybrid_results_YYYYMMDD_HHMMSS.csv`
- `hybrid_results_YYYYMMDD_HHMMSS.json`

### CSV columns

| Column | Example |
|--------|---------|
| `relevance_score` | 9 |
| `score_reason` | "CHRO at major Japanese company, Tokyo based" |
| `url` | https://jp.linkedin.com/in/person |
| `title` | Page title |
| `snippet` | Search snippet |
| `site_group` | professional_profiles |
| `engine` | serper |
| `people_names` | Koji Date; Ryo Konno |
| `people_titles` | HR Country Manager; Head of HR |
| `people_companies` | Momentive; Biogen |
| `people_linkedin` | https://jp.linkedin.com/in/... |

---

## Typical API cost per run

- ~8 Gemini calls (free tier: 1000/day)
- ~3-6 Brave calls (free tier: 2000/month)
- ~2-14 Serper calls (2500 on signup)
