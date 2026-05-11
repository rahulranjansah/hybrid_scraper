"""
Step 3b: Zero-shot baseline over ALL 92 colored rows.

Runs `dspy.Predict(ExplainThenLabel)` on every candidate in
colored_only.jsonl with the Crocs brief. No training, no few-shot,
no optimization — just the raw prompt + rubric that Step 3 already
wired up.

Produces the honest baseline number that Step 4's DSPy optimizer
needs to beat.

Output:
  judge/IO/step3_dspy/baseline_predictions.jsonl
  judge/IO/step3_dspy/baseline_metrics.md
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import dspy

from step3_dspy_judge import (
    ExplainThenLabel, configure_lm, load_brief, load_colored,
    format_candidate, derive_label, route_red, reapproach_date,
    RED_TAGS_TIMING,
)

HERE = Path(__file__).parent
OUT_DIR = HERE / "IO" / "step3_dspy"
PRED_OUT = OUT_DIR / "baseline_predictions.jsonl"
METRICS_OUT = OUT_DIR / "baseline_metrics.md"


def run_all() -> list[dict]:
    configure_lm()
    brief = load_brief()
    rows = load_colored()
    judge = dspy.Predict(ExplainThenLabel)
    preds: list[dict] = []
    for i, row in enumerate(rows, 1):
        try:
            pred = judge(brief=brief, candidate=format_candidate(row))
            tags = set(pred.reasoning_tags or [])
            label = derive_label(tags)
            out = {
                "name": row["name"],
                "linkedin_url": row.get("linkedin_url", ""),
                "human_flag": row["human_flag"],
                "human_remark": row.get("remark", ""),
                "predicted_label": label,
                "reasoning_tags": sorted(tags),
                "reasoning_text": pred.reasoning_text,
            }
            if label == "red":
                out["red_bucket"] = route_red(tags)
                out["reapproach_after"] = (
                    reapproach_date()
                    if tags & RED_TAGS_TIMING and not tags - RED_TAGS_TIMING
                    else None
                )
        except Exception as e:
            out = {
                "name": row["name"],
                "human_flag": row["human_flag"],
                "error": str(e)[:200],
            }
        preds.append(out)
        correct = out.get("predicted_label") == out.get("human_flag")
        mark = "OK " if correct else "  "
        print(
            f"[{i:3d}/{len(rows)}] {mark} "
            f"human={out.get('human_flag'):7} pred={out.get('predicted_label', 'ERR'):7}"
            f"  {row['name']}"
        )
    return preds


def confusion_matrix(preds: list[dict]) -> dict[str, dict[str, int]]:
    flags = ["green", "yellow", "red"]
    mat = {h: {p: 0 for p in flags} for h in flags}
    for p in preds:
        h = p.get("human_flag")
        g = p.get("predicted_label")
        if h in flags and g in flags:
            mat[h][g] += 1
    return mat


def metric_report(preds: list[dict]) -> str:
    lines: list[str] = []
    total = len(preds)
    errors = [p for p in preds if "error" in p]
    valid = [p for p in preds if "error" not in p]
    correct = sum(1 for p in valid if p["predicted_label"] == p["human_flag"])

    lines.append("# Zero-shot baseline — 92 colored Crocs rows")
    lines.append("")
    lines.append(f"Model: `gemini/gemini-2.5-flash` · rubric: v1 · JD: Crocs HR Manager")
    lines.append(f"No training, no few-shot, no DSPy optimization. Pure prompt + rubric.")
    lines.append("")
    lines.append(f"- Total candidates: **{total}**")
    lines.append(f"- Errored calls: **{len(errors)}**")
    lines.append(f"- Valid predictions: **{len(valid)}**")
    lines.append(
        f"- Overall flag agreement: **{correct}/{len(valid)} "
        f"= {100*correct/max(len(valid),1):.1f}%**"
    )
    lines.append("")
    lines.append("## Confusion matrix (rows = human, cols = judge)")
    lines.append("")
    mat = confusion_matrix(valid)
    lines.append("| human \\ judge | green | yellow | red |")
    lines.append("|---|---:|---:|---:|")
    for h in ["green", "yellow", "red"]:
        r = mat[h]
        lines.append(f"| **{h}** | {r['green']} | {r['yellow']} | {r['red']} |")
    lines.append("")

    # green precision and recall — the primary metrics
    pred_green = sum(1 for p in valid if p["predicted_label"] == "green")
    true_green = sum(1 for p in valid if p["human_flag"] == "green")
    tp_green = sum(
        1 for p in valid if p["predicted_label"] == "green" and p["human_flag"] == "green"
    )
    gp = tp_green / pred_green if pred_green else 0.0
    gr = tp_green / true_green if true_green else 0.0
    f1 = 2 * gp * gr / (gp + gr) if (gp + gr) else 0.0
    lines.append("## Green metrics (primary — aim for green)")
    lines.append("")
    lines.append(f"- Green predictions: **{pred_green}**")
    lines.append(f"- True greens in data: **{true_green}**")
    lines.append(f"- True positives: **{tp_green}**")
    lines.append(f"- **Green precision:** {gp:.3f}  (of predicted-green, how many were really green)")
    lines.append(f"- **Green recall:** {gr:.3f}     (of real greens, how many did we find)")
    lines.append(f"- **Green F1:** {f1:.3f}")
    lines.append("")

    # Per-flag breakdown
    lines.append("## Per-flag agreement")
    lines.append("")
    lines.append("| human | n | correct | rate |")
    lines.append("|---|---:|---:|---:|")
    for f in ["green", "yellow", "red"]:
        sub = [p for p in valid if p["human_flag"] == f]
        c = sum(1 for p in sub if p["predicted_label"] == f)
        rate = f"{100*c/len(sub):.1f}%" if sub else "—"
        lines.append(f"| {f} | {len(sub)} | {c} | {rate} |")
    lines.append("")

    # Tag frequency (which tags is the judge picking most)
    lines.append("## Tag frequency across all 92 predictions")
    lines.append("")
    tag_counter: Counter = Counter()
    for p in valid:
        for t in p.get("reasoning_tags", []):
            tag_counter[t] += 1
    lines.append("| tag | count |")
    lines.append("|---|---:|")
    for t, c in tag_counter.most_common():
        lines.append(f"| `{t}` | {c} |")
    lines.append("")

    if errors:
        lines.append("## Errored calls")
        lines.append("")
        for e in errors[:10]:
            lines.append(f"- {e['name']}: `{e['error']}`")
        lines.append("")

    return "\n".join(lines)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    preds = run_all()
    with PRED_OUT.open("w") as f:
        for p in preds:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    report = metric_report(preds)
    METRICS_OUT.write_text(report)
    print(f"\nPredictions -> {PRED_OUT}")
    print(f"Metrics     -> {METRICS_OUT}")
    print()
    # Print just the headline numbers
    print(report.split("## Confusion matrix")[0])


if __name__ == "__main__":
    main()
