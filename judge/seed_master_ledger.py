"""
One-shot: seed master untagged.xlsx + predictions.xlsx from existing data.

Sources:
  1. Crocs sheet (judge/IO/step1_parse/human_labels.jsonl) - 174 people
     -> added to untagged (seen). Their human_flag (where present) goes
     to predictions if the flag is green/yellow/red (i.e. not unflagged).
  2. step5a predictions (rows 68-81) - 14 rated people -> predictions.
  3. step5c predictions (new candidates) - 19 rated people -> predictions.

Safe to re-run: dedupe is by LinkedIn URL + name, already-present rows
are skipped.
"""

from __future__ import annotations

import json
from pathlib import Path

from master_ledger import (
    add_untagged, add_predictions, stats,
    UNTAGGED, PREDICTIONS,
)

HERE = Path(__file__).parent
CROCS = HERE / "IO" / "step1_parse" / "human_labels.jsonl"
STEP5A = HERE / "IO" / "step5a_predict_unflagged" / "predictions_68_81.jsonl"
STEP5A_HUMAN = HERE / "IO" / "step5a_predict_unflagged" / "human_labels.jsonl"
STEP5C = HERE / "IO" / "step5c_new_candidates" / "predictions.jsonl"


def seed_crocs() -> None:
    rows = [json.loads(l) for l in CROCS.open()]

    # Seed ALL 174 Crocs people into untagged (seen list).
    add = add_untagged(
        ({"name": r["name"], "linkedin_url": r.get("linkedin_url"),
          "email": r.get("email")} for r in rows),
        source="crocs_sheet",
    )
    print(f"  crocs -> untagged: +{add} rows")

    # Human-flagged rows (green/yellow/red) go to predictions as "human" source.
    flagged = [r for r in rows if r.get("human_flag") in {"green", "yellow", "red"}]
    pred_entries = [{
        "name": r["name"],
        "linkedin_url": r.get("linkedin_url"),
        "email": r.get("email"),
        "predicted_label": r["human_flag"],
        "reasoning_tags": [],
        "reasoning_text": (r.get("remark") or "").strip() or "human-labeled (no remark)",
        "red_bucket": "",
        "reapproach_after": "",
    } for r in flagged]
    add = add_predictions(pred_entries, source="crocs_sheet_human")
    print(f"  crocs -> predictions: +{add} rows (human-flagged)")


def seed_step5a() -> None:
    if not STEP5A.exists():
        print("  step5a predictions not found, skipping")
        return
    preds = [json.loads(l) for l in STEP5A.open()]
    # Seen list
    add = add_untagged(
        ({"name": r["name"], "linkedin_url": r.get("linkedin_url"),
          "email": r.get("email")} for r in preds if "error" not in r),
        source="step5a",
    )
    print(f"  step5a -> untagged: +{add} rows")
    # Rated list
    add = add_predictions(
        (r for r in preds if "error" not in r and r.get("predicted_label")),
        source="step5a",
    )
    print(f"  step5a -> predictions: +{add} rows")

    # If the human-labels file exists, also seed predictions with the
    # human labels (overrides the judge prediction where they differ).
    if STEP5A_HUMAN.exists():
        humans = [json.loads(l) for l in STEP5A_HUMAN.open()]
        # These names are already in untagged via crocs; only add
        # predictions for the ones with a human flag.
        entries = [{
            "name": r["name"],
            "linkedin_url": "",  # keyed only on name here
            "predicted_label": r["human_flag"],
            "reasoning_tags": [],
            "reasoning_text": r.get("human_justification") or "human-labelled",
        } for r in humans]
        add = add_predictions(entries, source="step5a_human")
        print(f"  step5a humans -> predictions: +{add} rows")


def seed_step5c() -> None:
    if not STEP5C.exists():
        print("  step5c predictions not found, skipping")
        return
    preds = [json.loads(l) for l in STEP5C.open()]
    add = add_untagged(
        ({"name": r["name"], "linkedin_url": r.get("linkedin_url"),
          "email": r.get("email")} for r in preds if "error" not in r),
        source="step5c",
    )
    print(f"  step5c -> untagged: +{add} rows")
    add = add_predictions(
        (r for r in preds if "error" not in r and r.get("predicted_label")),
        source="step5c",
    )
    print(f"  step5c -> predictions: +{add} rows")


if __name__ == "__main__":
    print("Seeding master ledger from existing sources...\n")
    seed_crocs()
    seed_step5a()
    seed_step5c()
    print("\nFinal stats:")
    import json as _j
    print(_j.dumps(stats(), indent=2, default=str))
    print(f"\nFiles:\n  {UNTAGGED}\n  {PREDICTIONS}")
