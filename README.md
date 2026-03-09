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

### 1. Add API keys

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

### 3. Run

```bash
# Dry run first — preview queries, no API calls, free
python -m combined_scraper.run \
  --keywords "CHRO, HR Director, Head of HR, VP Human Resources, HRBP Director, Country HR Manager, Head of People, CPO, Tokyo, Osaka, Japan" \
  --engines brave serper \
  --dry-run

# Full run with both engines (best results)
python -m combined_scraper.run \
  --keywords "CHRO, HR Director, Head of HR, VP Human Resources, HRBP Director, Country HR Manager, Head of People, CPO, Tokyo, Osaka, Japan" \
  --engines brave serper

# Follow-up run — exclude already-found candidates
python -m combined_scraper.run \
  --keywords "CHRO, HR Director, Head of HR, VP Human Resources, HRBP Director, Country HR Manager, Head of People, CPO, Tokyo, Osaka, Japan" \
  --engines brave serper \
  --exclude-csv combined_scraper/results/hybrid_results_20260216_022720.csv \
  --output-name hr_candidates_round2
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
| `--exclude-csv` | — | Previous results CSV — skips already-found people/URLs

### CSV columns

| Column | What |
|--------|------|
| `relevance_score` | 0-10 relevance score |
| `score_reason` | Why this score was given |
| `flag` | `green` (strong match), `yellow` (minor concerns), `red` (excluded) |
| `url` | Source URL |
| `people_names` | Extracted names (semicolon-separated) |
| `people_titles` | Job titles |
| `people_companies` | Companies |
| `people_linkedin` | LinkedIn profile URLs |
| `people_employment_types` | employee / founder / recruiter / etc. |
| `people_seniorities` | c_level / vp / director / head / etc. |

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