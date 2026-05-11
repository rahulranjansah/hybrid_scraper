"""
Step 4b: Soften derive_label and re-score baseline predictions.

The Step-4 optimizer returned zero lift because the failure mode is in
the label-derivation rule, not in the prompt. v1 rule says ANY red tag
wins, which causes yellow->red collapse: if the LLM picks
`sector_mismatch` or `level_too_senior_for_brief` by accident, a
candidate with 4 strong positive tags gets labeled red.

This script tries several softer rules on the cached
`baseline_predictions.jsonl` (no new API calls) and picks the one with
the best green-F1 and overall accuracy.

Input:  judge/IO/step3_dspy/baseline_predictions.jsonl (92 rows)
Output: judge/IO/step4b_rederive/comparison.md  -- which rule wins
        judge/IO/step4b_rederive/best_predictions.jsonl  -- re-labeled
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from step3_dspy_judge import (
    GREEN_TAGS, YELLOW_TAGS, RED_TAGS_PERMANENT, RED_TAGS_TIMING,
)
from step3b_baseline import confusion_matrix

HERE = Path(__file__).parent
IN = HERE / "IO" / "step3_dspy" / "baseline_predictions.jsonl"
OUT_DIR = HERE / "IO" / "step4b_rederive"

# Hard-red tags per user directive: inherent-mismatch + age cutoffs.
# User refined 2026-04-21: HR + bilingual + 5-10yr + not 55+ is GREEN,
# timing concerns (job_hopper / recently_changed_jobs) become secondary.
# So timing tags are demoted from HARD_RED to TIMING_CONCERN.
HARD_RED = {
    "is_recruiter", "is_founder_or_self_employed", "is_client_employee",
    "dnc_internal", "not_hr_role", "country_manager_not_hr",
    "insufficient_japanese",
    "age_56_plus", "graduation_before_1989",
    "level_too_senior_for_brief",
}
TIMING_CONCERN = {
    "just_changed_jobs", "short_current_tenure", "recently_joined",
    "interim_or_consulting_recent",
}
# Whatever's left is "soft red" — judgment calls that can be outweighed.
SOFT_RED = (RED_TAGS_PERMANENT | RED_TAGS_TIMING) - HARD_RED - TIMING_CONCERN


# --------------- Rule variants ---------------


def rule_v1_any_red_wins(tags: set[str]) -> str:
    """Current rule. Any red fires red, any yellow fires yellow."""
    if tags & (RED_TAGS_PERMANENT | RED_TAGS_TIMING):
        return "red"
    if tags & GREEN_TAGS and not (tags & YELLOW_TAGS):
        return "green"
    if tags & YELLOW_TAGS:
        return "yellow"
    if tags & GREEN_TAGS:
        return "yellow"
    return "yellow"


def rule_v2_hard_vs_soft(tags: set[str]) -> str:
    """Hard reds auto-fire. Soft reds can be outweighed by >=2 greens."""
    if tags & HARD_RED:
        return "red"
    g = len(tags & GREEN_TAGS)
    y = len(tags & YELLOW_TAGS)
    sr = len(tags & SOFT_RED)
    if sr >= 1 and g < 2:
        return "red"
    if sr >= 1 and g >= 2:
        return "yellow"  # strong positives soften soft-red to yellow
    if y >= 1:
        return "yellow"
    if g >= 2:
        return "green"
    if g == 1:
        return "yellow"  # lone positive is not strong enough
    return "yellow"


def rule_v3_weighted(tags: set[str]) -> str:
    """Hard reds auto-fire. Everything else sums: +1 green, -1 yellow, -2 soft-red."""
    if tags & HARD_RED:
        return "red"
    score = 0
    for t in tags:
        if t in GREEN_TAGS: score += 1
        elif t in YELLOW_TAGS: score -= 1
        elif t in SOFT_RED: score -= 2
    if score >= 2:
        return "green"
    if score <= -2:
        return "red"
    return "yellow"


def rule_v4_greedy_green(tags: set[str]) -> str:
    """Hard reds auto-fire. If >=2 green tags, green unless >=2 concerns outweigh."""
    if tags & HARD_RED:
        return "red"
    g = len(tags & GREEN_TAGS)
    y = len(tags & YELLOW_TAGS)
    sr = len(tags & SOFT_RED)
    concerns = y + sr
    if g >= 3 and concerns <= 1:
        return "green"
    if g >= 2 and concerns == 0:
        return "green"
    if sr >= 1 and g < 2:
        return "red"
    if concerns >= 1:
        return "yellow"
    if g >= 1:
        return "yellow"
    return "yellow"


def rule_v5_green_dominant(tags: set[str]) -> str:
    """User directive 2026-04-21: if HR+bilingual+5-10yr and not 55+,
    that's green regardless of timing concerns. Timing concerns are
    secondary — they nudge, they don't override.

    Only hard-red disqualifiers fire automatically:
      - age 56+, graduation <= 1988
      - category mismatches (recruiter, client, not-HR, country-mgr, etc.)
      - level-too-senior (CHRO/VP for an HR Mgr brief)
      - insufficient Japanese

    Timing concerns route to red_reapproach_later IF the overall label
    is red for other reasons — they never force red on their own.
    """
    if tags & HARD_RED:
        return "red"
    g = len(tags & GREEN_TAGS)
    y = len(tags & YELLOW_TAGS)
    sr = len(tags & SOFT_RED)
    t = len(tags & TIMING_CONCERN)

    # Strong green dominates timing concerns entirely.
    if g >= 3:
        return "green"
    if g >= 2 and (y + sr) == 0:
        # Even with timing concerns, a solid green stays green.
        return "green"
    # Genuine soft-red concern with weak positives
    if sr >= 1 and g < 2:
        return "red"
    # Weak green + concerns → yellow
    if g >= 1 and (y + t) >= 1:
        return "yellow"
    if y >= 1 or t >= 1:
        return "yellow"
    if g >= 1:
        return "yellow"
    return "yellow"


RULES: dict[str, Callable[[set[str]], str]] = {
    "v1_any_red_wins (baseline)": rule_v1_any_red_wins,
    "v2_hard_vs_soft": rule_v2_hard_vs_soft,
    "v3_weighted": rule_v3_weighted,
    "v4_greedy_green": rule_v4_greedy_green,
    "v5_green_dominant": rule_v5_green_dominant,
}


# --------------- Scoring ---------------


def score_rule(preds: list[dict], rule: Callable) -> dict:
    relabeled = []
    for p in preds:
        if "error" in p:
            continue
        tags = set(p.get("reasoning_tags", []))
        new_label = rule(tags)
        relabeled.append({**p, "predicted_label": new_label})
    correct = sum(1 for p in relabeled if p["predicted_label"] == p["human_flag"])
    pred_green = sum(1 for p in relabeled if p["predicted_label"] == "green")
    true_green = sum(1 for p in relabeled if p["human_flag"] == "green")
    tp_green = sum(1 for p in relabeled
                   if p["predicted_label"] == "green" and p["human_flag"] == "green")
    gp = tp_green / pred_green if pred_green else 0.0
    gr = tp_green / true_green if true_green else 0.0
    return {
        "n": len(relabeled),
        "correct": correct,
        "accuracy": correct / len(relabeled),
        "green_precision": gp,
        "green_recall": gr,
        "green_f1": 2 * gp * gr / (gp + gr) if (gp + gr) else 0.0,
        "confusion": confusion_matrix(relabeled),
        "relabeled": relabeled,
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    preds = [json.loads(l) for l in IN.open()]
    print(f"Loaded {len(preds)} baseline predictions")

    results: dict[str, dict] = {}
    for name, rule in RULES.items():
        results[name] = score_rule(preds, rule)

    lines = [
        "# Step 4b — Softer label-derivation rules (re-scoring baseline predictions)",
        "",
        "Same 92 LLM tag-predictions, different ways of collapsing tags into a label.",
        "No new API calls.",
        "",
        "## Headline",
        "",
        "| rule | accuracy | green-P | green-R | green-F1 |",
        "|---|---:|---:|---:|---:|",
    ]
    for name, r in results.items():
        lines.append(
            f"| {name} | {r['accuracy']:.3f} | {r['green_precision']:.3f} | "
            f"{r['green_recall']:.3f} | **{r['green_f1']:.3f}** |"
        )

    # Best by green-F1 then accuracy
    best_name = max(results, key=lambda n: (results[n]["green_f1"], results[n]["accuracy"]))
    best = results[best_name]
    lines += [
        "",
        f"## Best rule: `{best_name}`",
        "",
        "Confusion matrix (rows=human, cols=judge):",
        "",
        "| human \\ judge | green | yellow | red |",
        "|---|---:|---:|---:|",
    ]
    for h in ["green", "yellow", "red"]:
        row = best["confusion"][h]
        lines.append(f"| **{h}** | {row['green']} | {row['yellow']} | {row['red']} |")

    # Per-rule confusion matrices for reference
    lines += ["", "## All confusion matrices", ""]
    for name, r in results.items():
        lines += [f"### `{name}`", "",
                  "| human \\ judge | green | yellow | red |",
                  "|---|---:|---:|---:|"]
        for h in ["green", "yellow", "red"]:
            row = r["confusion"][h]
            lines.append(f"| **{h}** | {row['green']} | {row['yellow']} | {row['red']} |")
        lines.append("")

    (OUT_DIR / "comparison.md").write_text("\n".join(lines))

    # Save the best rule's per-candidate predictions
    best_file = OUT_DIR / "best_predictions.jsonl"
    with best_file.open("w") as f:
        for p in best["relabeled"]:
            # drop the giant reasoning_text from this dump to keep it readable
            slim = {k: v for k, v in p.items() if k != "reasoning_text"}
            f.write(json.dumps(slim, ensure_ascii=False) + "\n")

    print("\n" + "\n".join(lines[:12]))
    print(f"\nBest rule: {best_name}")
    print(f"Full report -> {OUT_DIR / 'comparison.md'}")
    print(f"Relabeled predictions -> {best_file}")


if __name__ == "__main__":
    main()
