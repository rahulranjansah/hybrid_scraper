"""
Universal sourcing web app — V1 single-user.

Streamlit UI:
  - paste OR upload a JD (PDF / txt)
  - tweak target roles & options
  - click "Source"
  - get a color-coded shortlist of NET-NEW candidates (deduped against
    the global master ledger)

Same underlying components as the CLI pipeline:
  - combined_scraper stages 1, 2, 3, 3.5  (query gen → harvest →
    extract → linkedin)
  - judge/step3_dspy_judge.py for the rubric (5-class: gold > blue >
    green > yellow > red)
  - judge/master_ledger.py for global dedupe + persistence

Run:
  cd /mnt/hardisk/sourcing
  uv run streamlit run judge/web_app.py
"""

from __future__ import annotations

import datetime as dt
import io
import json
import os
import sys
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

HERE = Path(__file__).parent
PROJECT_ROOT = HERE.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(HERE))

# Lazy imports so the streamlit page renders even if API keys are missing.
from combined_scraper.query_generator import generate_queries, TARGET_SITES  # noqa: E402
from combined_scraper.url_harvester import harvest_urls  # noqa: E402
from combined_scraper.ai_extractor import extract_people  # noqa: E402
from combined_scraper.linkedin_finder import find_linkedin_urls  # noqa: E402
from combined_scraper.ai_scorer import score_results  # noqa: E402
from master_ledger import (  # noqa: E402
    exclusion_keys, add_untagged, add_predictions, _key,
    UNTAGGED, PREDICTIONS,
)

load_dotenv(PROJECT_ROOT / ".env")

LABEL_RANK = {"golden": 0, "blue": 1, "green": 2, "yellow": 3, "red": 4, "error": 5}
LABEL_COLORS = {
    "golden": "#FFD700",
    "blue":   "#4285F4",
    "green":  "#00C853",
    "yellow": "#FFEB3B",
    "red":    "#FF1744",
}
LABEL_EMOJI = {"golden": "🟨", "blue": "🟦", "green": "🟢", "yellow": "🟡", "red": "🔴"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def read_pdf_text(uploaded_file) -> str:
    """Extract text from an uploaded PDF using pypdf."""
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(uploaded_file.read()))
    return "\n\n".join(page.extract_text() or "" for page in reader.pages)


def brief_to_keywords(brief: str, target_cluster: str) -> str:
    """Build a compact keywords string for the scraper's query generator
    from the brief + the target role cluster."""
    return f"{target_cluster}, Tokyo Japan, bilingual English Japanese"


def run_pipeline(
    brief: str,
    target_cluster: str,
    results_per_query: int,
    engines: list[str],
    top_n: int,
    progress_cb,
) -> list[dict]:
    """End-to-end pipeline; same logic as run_crocs_hr.py but parameterised
    and with a progress callback for the Streamlit UI."""
    keywords = brief_to_keywords(brief, target_cluster)

    progress_cb("[1/6] Generating search queries with Gemini...")
    queries = generate_queries(keywords)
    progress_cb(f"      {len(queries)} queries generated")

    progress_cb(f"[2/6] Harvesting URLs ({', '.join(engines)})...")
    raw = harvest_urls(queries, engines=engines, results_per_query=results_per_query)
    progress_cb(f"      {len(raw)} URLs harvested")

    progress_cb("[3/6] Extracting people from snippets...")
    raw = extract_people(raw)
    n_people = sum(1 for r in raw if r.get("is_person_result"))
    progress_cb(f"      {n_people} person-results")

    # Dedupe against the global ledger
    keys = exclusion_keys()
    survivors: list[dict] = []
    dropped = 0
    for r in raw:
        people = r.get("people") or []
        if not people:
            survivors.append(r)
            continue
        hit = False
        for p in people:
            k = _key(p.get("name"), p.get("linkedin_url"))
            for ek in keys:
                if (k[1] and k[1] == ek[1]) or (k[0] and k[0] == ek[0]):
                    hit = True
                    break
            if hit:
                break
        if hit:
            dropped += 1
        else:
            survivors.append(r)
    progress_cb(f"[3.1] Deduped against ledger: dropped {dropped} known, kept {len(survivors)}")

    progress_cb("[3.5] Looking up LinkedIn URLs...")
    survivors = find_linkedin_urls(survivors)

    progress_cb("[4/6] Judging candidates with DSPy rubric...")
    judged = score_results(survivors, keywords_text=keywords, brief=brief)

    progress_cb("[5/6] Writing to master ledger...")
    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    src = f"webapp_{ts}"

    all_person_rows = [r for r in judged if r.get("is_person_result") and r.get("people")]
    seen = []
    rated = []
    for r in all_person_rows:
        for p in r["people"]:
            seen.append({"name": p.get("name") or "",
                         "linkedin_url": p.get("linkedin_url") or "",
                         "email": ""})
        p = r["people"][0]
        rated.append({
            "name": p.get("name") or "",
            "linkedin_url": p.get("linkedin_url") or "",
            "email": "",
            "predicted_label": r.get("flag") or "",
            "reasoning_tags": r.get("reasoning_tags") or [],
            "reasoning_text": r.get("score_reason") or "",
            "red_bucket": r.get("red_bucket") or "",
            "reapproach_after": r.get("reapproach_after") or "",
        })
    n_seen = add_untagged(seen, source=src)
    n_rated = add_predictions(rated, source=src)
    progress_cb(f"      +{n_seen} new in untagged.xlsx, +{n_rated} new in predictions.xlsx")

    all_person_rows.sort(key=lambda x: LABEL_RANK.get(x.get("flag", ""), 9))
    return all_person_rows[:top_n]


# ---------------------------------------------------------------------------
# Streamlit UI
# ---------------------------------------------------------------------------


st.set_page_config(page_title="Sourcing — Source new candidates", layout="wide")


# --- Password gate -----------------------------------------------------------
# Set APP_PASSWORD in Streamlit Cloud secrets (or .env locally). If unset,
# the gate is disabled (local dev). When set, app requires the password
# before any UI renders.
def _expected_password() -> str | None:
    try:
        v = st.secrets.get("APP_PASSWORD")
        if v:
            return v
    except Exception:
        pass
    return os.environ.get("APP_PASSWORD")


_pw_required = _expected_password()
if _pw_required:
    if "auth_ok" not in st.session_state:
        st.session_state.auth_ok = False
    if not st.session_state.auth_ok:
        st.title("🔒 Sourcing")
        with st.form("pw_form", clear_on_submit=False):
            entered = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Unlock")
        if submitted:
            if entered == _pw_required:
                st.session_state.auth_ok = True
                st.rerun()
            else:
                st.error("Incorrect password.")
        st.stop()
# ----------------------------------------------------------------------------


st.title("🎯 Sourcing — Source new candidates")
st.caption(
    "Universal LLM-judge candidate sourcing. Paste / upload a JD → click "
    "Source → get color-coded shortlist of net-new people, deduped against "
    "the global master ledger."
)

# Sidebar config
st.sidebar.header("Settings")
results_per_query = st.sidebar.slider(
    "Results per query", min_value=3, max_value=20, value=10,
    help="More results → more candidates → more cost (~$0.05 per additional result).",
)
top_n = st.sidebar.slider(
    "Show top N candidates", min_value=5, max_value=50, value=20,
    help="Just the per-run shortlist size. ALL net-new are saved to the ledger regardless.",
)
engines = st.sidebar.multiselect(
    "Search engines", ["brave", "serper"], default=["brave", "serper"],
    help="Both = most coverage, ~2x cost.",
)

# Show ledger state
keys = exclusion_keys()
st.sidebar.markdown("---")
st.sidebar.markdown(f"**Ledger:** {len(keys)} known people")
if UNTAGGED.exists():
    st.sidebar.caption(f"untagged.xlsx · {UNTAGGED}")
if PREDICTIONS.exists():
    st.sidebar.caption(f"predictions.xlsx · {PREDICTIONS}")

# Main inputs
col_brief, col_cluster = st.columns([2, 1])

with col_brief:
    st.subheader("1. Job description")
    jd_source = st.radio(
        "JD input", ["Paste text", "Upload PDF", "Upload .txt"],
        horizontal=True, label_visibility="collapsed",
    )
    brief_text = ""
    if jd_source == "Paste text":
        brief_text = st.text_area(
            "Paste the JD here", height=240,
            placeholder="Crocs - HR Manager\nLocation: Tokyo\n...",
        )
    elif jd_source == "Upload PDF":
        up = st.file_uploader("Upload JD PDF", type=["pdf"])
        if up:
            brief_text = read_pdf_text(up)
            with st.expander("Extracted text"):
                st.text(brief_text[:3000])
    elif jd_source == "Upload .txt":
        up = st.file_uploader("Upload JD .txt", type=["txt"])
        if up:
            brief_text = up.read().decode("utf-8")
            with st.expander("Extracted text"):
                st.text(brief_text[:3000])

with col_cluster:
    st.subheader("2. Target role cluster")
    target_cluster = st.text_area(
        "Role keywords (comma-separated)",
        value="HR Manager, HRBP, HR Business Partner, Senior HR Manager, "
              "HR Director, Head of HR, People Solutions Manager",
        height=160,
        help="These guide the search query generator. The full JD above is "
             "what the JUDGE uses to evaluate fit.",
    )

st.markdown("---")
sourced = st.button("🔍 Source", type="primary", disabled=not brief_text.strip())

# Run
if sourced:
    if not os.environ.get("GEMINI_API_KEY"):
        st.error("GEMINI_API_KEY missing in .env. Add it and reload.")
        st.stop()

    progress_box = st.empty()
    progress_log: list[str] = []

    def cb(msg: str):
        progress_log.append(msg)
        progress_box.code("\n".join(progress_log), language="text")

    try:
        with st.spinner("Sourcing candidates — 3-10 min..."):
            top = run_pipeline(
                brief=brief_text,
                target_cluster=target_cluster,
                results_per_query=results_per_query,
                engines=engines or ["brave"],
                top_n=top_n,
                progress_cb=cb,
            )
    except Exception as e:
        st.error(f"Pipeline error: {e}")
        st.stop()

    st.success(f"Done — {len(top)} net-new candidates")

    # Results table
    st.subheader(f"Shortlist (top {len(top)})")
    rows_for_df = []
    for r in top:
        p = (r.get("people") or [{}])[0]
        label = r.get("flag") or ""
        rows_for_df.append({
            "Label": f"{LABEL_EMOJI.get(label, '')} {label}",
            "Name": p.get("name") or "",
            "Title": p.get("title") or "",
            "Company": p.get("company") or "",
            "LinkedIn": p.get("linkedin_url") or "",
            "Tags": ", ".join(r.get("reasoning_tags") or []),
            "Why": r.get("score_reason") or "",
            "Strengths": "\n".join(f"• {s}" for s in (r.get("strengths") or [])),
            "Weaknesses": "\n".join(f"• {s}" for s in (r.get("weaknesses") or [])),
            "Missing data": "\n".join(f"• {s}" for s in (r.get("missing_data") or [])),
            "Actionable insights": "\n".join(f"• {s}" for s in (r.get("actionable_insights") or [])),
            "Source URL": r.get("url") or "",
        })

    st.dataframe(rows_for_df, use_container_width=True, hide_index=True)

    # Distribution
    from collections import Counter
    tally = Counter(r.get("flag") for r in top)
    st.subheader("Distribution")
    cols = st.columns(5)
    for col, label in zip(cols, ["golden", "blue", "green", "yellow", "red"]):
        col.metric(f"{LABEL_EMOJI[label]} {label}", tally.get(label, 0))

    st.caption(
        "Saved to master ledger — same data also available in "
        f"`{UNTAGGED.relative_to(PROJECT_ROOT)}` and "
        f"`{PREDICTIONS.relative_to(PROJECT_ROOT)}` (xlsx + .json)."
    )
