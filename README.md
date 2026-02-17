# Combined Scraper

AI-powered executive sourcing pipeline for HR professionals in Japan. Uses Gemini for intelligence (query generation, person extraction, relevance scoring) and Brave/Serper for web search.

## What it does

Given keywords like `CHRO, HR Director, Tokyo` it:

1. Generates smart search queries with Gemini (bilingual EN/JP)
2. Harvests URLs from Brave and Serper (filters out job boards)
3. Extracts people (name, title, company) from search snippets
4. Looks up LinkedIn profile URLs for found people
5. Scores each person's relevance (0-10)
6. Exports results as CSV + JSON

## Quick start

```bash
git clone https://github.com/rahulranjansah/hybrid_scraper.git
cd hybrid_scraper
```

### Install uv (if you don't have it)

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# Or via pip
pip install uv
```

### Install dependencies

```bash
uv sync
```

This creates a `.venv` and installs everything from `pyproject.toml`.

Without uv:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

### API keys

Create a `.env` file in the project root:

```env
GEMINI_API_KEY=your_key_here
BRAVE_API_KEY=your_key_here
SERPER_API_KEY=your_key_here
```

| Key | Where to get it | Free tier |
|-----|-----------------|-----------|
| `GEMINI_API_KEY` | [aistudio.google.com](https://aistudio.google.com) | 15 RPM / 1000 RPD |
| `BRAVE_API_KEY` | [brave.com/search/api](https://brave.com/search/api/) | 2000 queries/month |
| `SERPER_API_KEY` | [serper.dev](https://serper.dev) | 2500 queries on signup |

### Run

#### With uv

```bash
uv run scrape --keywords "CHRO, HR Director, Tokyo" --dry-run          # preview queries, no API calls
uv run scrape --keywords "CHRO, HR Director, Tokyo"                    # brave only
uv run scrape --keywords "CHRO, HR Director, Tokyo" --engines brave serper  # both engines (best)
```

#### Without uv

```bash
source .venv/bin/activate

# Dry run — preview generated queries, no API calls, free
python -m combined_scraper.run --keywords "CHRO, HR Director, Tokyo" --dry-run

# Brave only
python -m combined_scraper.run --keywords "CHRO, HR Director, Tokyo"

# Both engines
python -m combined_scraper.run --keywords "CHRO, HR Director, Tokyo, Osaka" --engines brave serper

# Only specific site groups
python -m combined_scraper.run --keywords "CHRO, Tokyo" --groups professional_profiles social

# Custom results count per query
python -m combined_scraper.run --keywords "CHRO, Tokyo" --engines brave serper --results-per-query 20

# Google Doc as keyword source
python -m combined_scraper.run --doc-url "https://docs.google.com/document/d/.../edit" --engines brave serper
```

### CLI flags

| Flag | Default | What |
|------|---------|------|
| `--keywords` | — | Comma-separated search keywords |
| `--doc-url` | — | Google Doc URL with keywords (alternative) |
| `--engines` | `brave` | `brave`, `serper`, or both |
| `--groups` | all | `professional_profiles`, `conference_and_events`, `content_and_signals`, `social` |
| `--results-per-query` | 10 | Results per query per engine |
| `--dry-run` | off | Preview queries only |
| `--output-name` | timestamped | Custom output filename |

## Output

Results saved to `combined_scraper/results/`:

- `hybrid_results_YYYYMMDD_HHMMSS.csv`
- `hybrid_results_YYYYMMDD_HHMMSS.json`

CSV columns: `relevance_score`, `score_reason`, `url`, `title`, `snippet`, `site_group`, `engine`, `people_names`, `people_titles`, `people_companies`, `people_linkedin`

## Pipeline

```
Keywords
  → [1] Gemini generates search queries (query_generator.py)
  → [2] Brave/Serper harvest URLs, filter job boards (url_harvester.py)
  → [3] Gemini extracts people from snippets (ai_extractor.py)
  → [3.5] LinkedIn URL lookup for found people (linkedin_finder.py)
  → [4] Gemini scores relevance 0-10 (ai_scorer.py)
  → [5] Export CSV + JSON (run.py)
```

## Cost per run

Stays within free tiers:

- ~8 Gemini calls
- ~3-6 Brave calls
- ~2-14 Serper calls

## Tech

- Python 3.10+
- Gemini 2.5 Flash Lite (cheapest model, free tier)
- Brave Search API + Serper (Google proxy)
- No scraping — snippet-based extraction + LinkedIn URL lookup
