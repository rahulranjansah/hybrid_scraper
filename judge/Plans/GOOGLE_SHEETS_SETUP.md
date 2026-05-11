# Google Sheets sync — one-time setup

Syncs the master xlsx files to the two Google Sheets whose edit URLs
are in `.env` as `PREDICTION_FINAL` and `UNTAGGED_DATA`. Uses OAuth,
so nothing in `.env` is a secret.

## 1. Create OAuth credentials (5 min, one-time)

1. [console.cloud.google.com](https://console.cloud.google.com) → pick
   or create a project
2. **APIs & Services → Library** → enable both:
   - Google Sheets API
   - Google Drive API
3. **APIs & Services → OAuth consent screen** → fill in app name
   (e.g. "sourcing-sync"), your email. Test users: add your own email.
4. **APIs & Services → Credentials → Create Credentials → OAuth client
   ID** → Application type: **Desktop app** → download JSON
5. Save the downloaded file as:

   ```
   judge/IO/master/credentials.json
   ```

## 2. First run

```bash
cd /mnt/hardisk/sourcing
uv run python judge/sync_sheets.py
```

- Opens a browser → click "Continue" past the "unverified app" screen
  → "Allow"
- On success a `token.json` gets written next to `credentials.json`
- Subsequent runs reuse the token (auto-refreshes when it expires)

## 3. What it does

- Reads `judge/IO/master/untagged.xlsx` → pushes to the sheet at
  `UNTAGGED_DATA`
- Reads `judge/IO/master/predictions.xlsx` → pushes to the sheet at
  `PREDICTION_FINAL`
- Clears the destination sheet's first worksheet and writes fresh
- Cell formatting (colour fills) does NOT carry over automatically —
  gspread uses plain values. TODO in backlog: batch-format labels
  after each push so gold/green/yellow/red fills land.

## 4. Automate it after each pipeline run

To make the Crocs pipeline auto-sync after it finishes, add this to the
bottom of `run_crocs_hr.py` main():

```python
import subprocess
subprocess.run([sys.executable, str(HERE / "sync_sheets.py")], check=False)
```

Hasn't been added yet — waiting until after the auth works to avoid
blocking the pipeline runner on missing credentials.
