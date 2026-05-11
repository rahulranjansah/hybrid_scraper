# Streamlit Community Cloud — deploy guide (private app)

Free, ~10 min, requires a Streamlit account (use GitHub login).

## What you'll get

- Private Streamlit app at `https://<your-app-name>.streamlit.app`
- Password-gated (you control who can run searches)
- Auto-redeploys on every `git push` to main
- API keys stored in Streamlit's secrets manager (never in the repo)
- Free tier: 1 private app per account, 1 GB RAM, hibernates after ~7
  days of inactivity (cold-start ~30 s)

## What you give up vs paid

- Ledger writes don't persist across redeploys (filesystem ephemeral)
  → for testing this is fine; for production wire up Google Sheets
  sync (see `Plans/GOOGLE_SHEETS_SETUP.md`).

## Steps

### 1. Push the repo (one-time)

The repo is already at `github.com/rahulranjansah/hybrid_scraper`
(private). Commit and push:

```bash
cd /mnt/hardisk/sourcing
git add -A
git commit -m "..."
git push origin main
```

### 2. Sign up at Streamlit Community Cloud

- Go to <https://streamlit.io/cloud>
- Click **Sign up** → log in with your GitHub account
  (the same account that owns `rahulranjansah/hybrid_scraper`)
- Approve the Streamlit GitHub App's read access to your private repo

### 3. Create the app

- Streamlit Cloud → **New app** → **From existing repo**
- Repository: `rahulranjansah/hybrid_scraper`
- Branch: `main`
- Main file path: `judge/web_app.py`
- Python version: `3.13` (matches the project)
- Click **Deploy**

Wait ~3-5 min for the first build (installs requirements.txt).

### 4. Add secrets

Once the app is deployed, click **Manage app → Settings → Secrets**.
Paste this TOML (substitute your real keys from `.env`):

```toml
APP_PASSWORD = "<pick-a-password-you-share-with-testers>"
GEMINI_API_KEY = "<your-gemini-key>"
BRAVE_API_KEY  = "<your-brave-key>"
SERPER_API_KEY = "<your-serper-key>"
APIFY_API_KEY  = "<your-apify-key>"
```

The app reads them via `st.secrets.get(...)` (with `os.environ`
fallback for local dev). Save → the app auto-reboots.

### 5. Share

URL: `https://<app-name>.streamlit.app`
Password: whatever you set in `APP_PASSWORD`.

Give both only to testers you trust — each search costs you ~$0.65 in
API calls.

## Updating after a code change

```bash
git add -A
git commit -m "fix: ..."
git push origin main
```

Streamlit Cloud detects the push and rebuilds in ~30s. Your app
auto-restarts.

## When ledger persistence becomes blocking

Once you have real candidates accumulated in `untagged.xlsx` and
`predictions.xlsx`, switching from ephemeral to persistent storage:

- **Cheapest**: commit the master xlsx files after each run (a button
  in the app that triggers `git commit + push`).
- **Best**: wire `sync_sheets.py` (Plans/GOOGLE_SHEETS_SETUP.md) so
  every search auto-pushes to the Google Sheet.
- **Production**: move the ledger to S3 / Supabase / a small Postgres.
  Adds ~50 lines to `master_ledger.py`.

## Troubleshooting

| Problem | Fix |
|---|---|
| Build fails on dependencies | Check `requirements.txt` matches your local `uv export` output |
| App boots but Source button does nothing | Confirm all 4 API keys are in Secrets, not just `APP_PASSWORD` |
| "Module not found" for `combined_scraper` | The `sys.path.insert(0, str(PROJECT_ROOT))` at the top of `web_app.py` handles this — verify it's still there |
| Cold start every visit | Expected on free tier. Click and wait ~30s. Pay tier removes this. |
| Password gate doesn't appear | `APP_PASSWORD` is unset in Secrets, or you're running locally without it set in `.env` |
