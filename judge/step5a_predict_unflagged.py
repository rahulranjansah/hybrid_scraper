"""
Step 5a: Predict labels for unflagged rows (default: xlsx rows 68-81).

Runs the DSPy judge on rows the human hasn't colored yet so the user
can review and either confirm or correct. Keeps the original `row`
index from human_labels.xlsx for easy reconciliation with the sheet.

Usage:
  uv run python judge/step5a_predict_unflagged.py              # rows 68-81
  uv run python judge/step5a_predict_unflagged.py 100 120      # custom range

Output:
  judge/IO/step5a_predict_unflagged/predictions_<lo>_<hi>.jsonl
  judge/IO/step5a_predict_unflagged/predictions_<lo>_<hi>.md
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import dspy

from step3_dspy_judge import (
    ExplainThenLabel, configure_lm, load_brief, format_candidate,
    derive_label, route_red, reapproach_date,
    TIMING_CONCERN_TAGS,
)

HERE = Path(__file__).parent
IN = HERE / "IO" / "step1_parse" / "human_labels.jsonl"
OUT_DIR = HERE / "IO" / "step5a_predict_unflagged"


def main() -> None:
    lo = int(sys.argv[1]) if len(sys.argv) > 1 else 68
    hi = int(sys.argv[2]) if len(sys.argv) > 2 else 81

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    configure_lm()
    brief = load_brief()
    rows = [json.loads(l) for l in IN.open()]
    target = [r for r in rows if lo <= r["row"] <= hi]
    print(f"Predicting rows {lo}-{hi} ({len(target)} candidates)")

    judge = dspy.Predict(ExplainThenLabel)
    preds: list[dict] = []
    for r in target:
        try:
            p = judge(brief=brief, candidate=format_candidate(r))
            tags = set(p.reasoning_tags or [])
            label = derive_label(tags)
            out = {
                "row": r["row"],
                "name": r["name"],
                "linkedin_url": r.get("linkedin_url", ""),
                "human_flag": r["human_flag"],  # mostly "unflagged" — your ground truth for later
                "predicted_label": label,
                "reasoning_tags": sorted(tags),
                "reasoning_text": p.reasoning_text,
                "strengths": list(p.strengths or []),
                "weaknesses": list(p.weaknesses or []),
                "missing_data": list(p.missing_data or []),
                "actionable_insights": list(p.actionable_insights or []),
            }
            if label == "red":
                bucket = route_red(tags)
                out["red_bucket"] = bucket
                if bucket == "red_reapproach_later":
                    out["reapproach_after"] = reapproach_date()
        except Exception as e:
            out = {"row": r["row"], "name": r["name"], "error": str(e)[:200]}
        preds.append(out)
        label = out.get("predicted_label", "ERROR")
        human = out.get("human_flag", "?")
        tag = "(preset)" if human != "unflagged" else ""
        print(f"  row {out['row']:3d}  pred={label:7}  {tag}  {r['name']}")

    stem = f"predictions_{lo}_{hi}"
    (OUT_DIR / f"{stem}.jsonl").write_text(
        "\n".join(json.dumps(p, ensure_ascii=False) for p in preds) + "\n"
    )
    print(f"\nSaved -> {OUT_DIR / f'{stem}.jsonl'}")


if __name__ == "__main__":
    main()
