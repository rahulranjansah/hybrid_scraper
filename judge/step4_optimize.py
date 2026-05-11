"""
Step 4: DSPy optimizer (BootstrapFewShotWithRandomSearch).

Trains few-shot demonstrations on a stratified 70/22 train/val split
of the 92 colored Crocs rows. Uses `gemini-2.5-flash` (same model as
baseline) so the lift we measure is purely from prompt demonstrations,
not from a bigger model.

Metric: exact-match on derived label. We track green-F1 alongside as
the primary human-facing metric ("aim for green").

Before running this, Step 3b's baseline exists at:
  judge/IO/step3_dspy/baseline_metrics.md  — 43.5% overall / 0.364 green-F1

Output:
  judge/IO/step4_optimize/optimized_program.json   — DSPy compiled program
  judge/IO/step4_optimize/train.jsonl               — 70 train examples
  judge/IO/step4_optimize/val.jsonl                 — 22 val examples
  judge/IO/step4_optimize/val_predictions.jsonl     — predictions on val
  judge/IO/step4_optimize/val_metrics.md            — before/after comparison
"""

from __future__ import annotations

import json
import random
from pathlib import Path

import dspy
from dspy.teleprompt import BootstrapFewShotWithRandomSearch

from step3_dspy_judge import (
    ExplainThenLabel, configure_lm, load_brief, load_colored,
    format_candidate, derive_label,
)
from step3b_baseline import confusion_matrix

HERE = Path(__file__).parent
OUT_DIR = HERE / "IO" / "step4_optimize"
TRAIN_OUT = OUT_DIR / "train.jsonl"
VAL_OUT = OUT_DIR / "val.jsonl"
PROGRAM_OUT = OUT_DIR / "optimized_program.json"
PRED_OUT = OUT_DIR / "val_predictions.jsonl"
METRICS_OUT = OUT_DIR / "val_metrics.md"

RNG_SEED = 7
VAL_SIZE_PER_FLAG = {"green": 7, "yellow": 6, "red": 9}  # 7+6+9 = 22


def stratified_split(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    rng = random.Random(RNG_SEED)
    by_flag: dict[str, list[dict]] = {"green": [], "yellow": [], "red": []}
    for r in rows:
        by_flag[r["human_flag"]].append(r)
    for f in by_flag:
        rng.shuffle(by_flag[f])

    train, val = [], []
    for flag, n_val in VAL_SIZE_PER_FLAG.items():
        val += by_flag[flag][:n_val]
        train += by_flag[flag][n_val:]
    rng.shuffle(train)
    rng.shuffle(val)
    return train, val


def to_example(row: dict, brief: str) -> dspy.Example:
    return dspy.Example(
        brief=brief,
        candidate=format_candidate(row),
        flag=row["human_flag"],
        name=row["name"],
    ).with_inputs("brief", "candidate")


def metric(example: dspy.Example, pred, trace=None) -> float:
    tags = set(pred.reasoning_tags or [])
    return float(derive_label(tags) == example.flag)


def eval_program(program, val_examples: list[dspy.Example]) -> list[dict]:
    preds = []
    for ex in val_examples:
        try:
            p = program(brief=ex.brief, candidate=ex.candidate)
            tags = set(p.reasoning_tags or [])
            predicted = derive_label(tags)
            preds.append({
                "name": ex.name,
                "human_flag": ex.flag,
                "predicted_label": predicted,
                "reasoning_tags": sorted(tags),
                "reasoning_text": p.reasoning_text,
            })
        except Exception as e:
            preds.append({"name": ex.name, "human_flag": ex.flag, "error": str(e)[:200]})
    return preds


def compute_metrics(preds: list[dict]) -> dict:
    valid = [p for p in preds if "error" not in p]
    correct = sum(1 for p in valid if p["predicted_label"] == p["human_flag"])
    pred_green = sum(1 for p in valid if p["predicted_label"] == "green")
    true_green = sum(1 for p in valid if p["human_flag"] == "green")
    tp_green = sum(
        1 for p in valid
        if p["predicted_label"] == "green" and p["human_flag"] == "green"
    )
    gp = tp_green / pred_green if pred_green else 0.0
    gr = tp_green / true_green if true_green else 0.0
    return {
        "n": len(valid),
        "correct": correct,
        "accuracy": correct / len(valid) if valid else 0.0,
        "green_precision": gp,
        "green_recall": gr,
        "green_f1": 2 * gp * gr / (gp + gr) if (gp + gr) else 0.0,
        "confusion": confusion_matrix(valid),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    configure_lm()
    brief = load_brief()
    rows = load_colored()
    train_rows, val_rows = stratified_split(rows)
    print(f"train={len(train_rows)}  val={len(val_rows)}")
    assert len(train_rows) == 70 and len(val_rows) == 22

    with TRAIN_OUT.open("w") as f:
        for r in train_rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    with VAL_OUT.open("w") as f:
        for r in val_rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    train = [to_example(r, brief) for r in train_rows]
    val = [to_example(r, brief) for r in val_rows]

    base_program = dspy.Predict(ExplainThenLabel)

    # Evaluate baseline on the val split (comparable number)
    print("\n=== Baseline (zero-shot) on val set ===")
    base_preds = eval_program(base_program, val)
    base_metrics = compute_metrics(base_preds)
    print(
        f"  acc={base_metrics['accuracy']:.3f}  "
        f"green_f1={base_metrics['green_f1']:.3f}  "
        f"green_recall={base_metrics['green_recall']:.3f}"
    )

    # Optimize
    print("\n=== Running BootstrapFewShotWithRandomSearch ===")
    optimizer = BootstrapFewShotWithRandomSearch(
        metric=metric,
        max_bootstrapped_demos=4,
        max_labeled_demos=4,
        num_candidate_programs=8,
        num_threads=1,
    )
    compiled = optimizer.compile(
        student=base_program,
        trainset=train,
        valset=val,
    )
    print("Optimization complete.")
    compiled.save(str(PROGRAM_OUT))

    # Evaluate optimized
    print("\n=== Optimized on val set ===")
    opt_preds = eval_program(compiled, val)
    opt_metrics = compute_metrics(opt_preds)
    print(
        f"  acc={opt_metrics['accuracy']:.3f}  "
        f"green_f1={opt_metrics['green_f1']:.3f}  "
        f"green_recall={opt_metrics['green_recall']:.3f}"
    )

    with PRED_OUT.open("w") as f:
        for p in opt_preds:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")

    # Write side-by-side metrics
    lines = [
        "# Step 4 — Optimized vs. baseline on 22-row val set",
        "",
        f"Train: 70 rows (stratified) · Val: 22 rows (7g/6y/9r) · seed={RNG_SEED}",
        f"Model: `gemini/gemini-2.5-flash`  ·  Optimizer: `BootstrapFewShotWithRandomSearch`",
        "",
        "## Headline",
        "",
        "| metric | baseline | optimized | delta |",
        "|---|---:|---:|---:|",
        f"| accuracy | {base_metrics['accuracy']:.3f} | {opt_metrics['accuracy']:.3f} | {opt_metrics['accuracy']-base_metrics['accuracy']:+.3f} |",
        f"| green precision | {base_metrics['green_precision']:.3f} | {opt_metrics['green_precision']:.3f} | {opt_metrics['green_precision']-base_metrics['green_precision']:+.3f} |",
        f"| green recall | {base_metrics['green_recall']:.3f} | {opt_metrics['green_recall']:.3f} | {opt_metrics['green_recall']-base_metrics['green_recall']:+.3f} |",
        f"| green F1 | {base_metrics['green_f1']:.3f} | {opt_metrics['green_f1']:.3f} | {opt_metrics['green_f1']-base_metrics['green_f1']:+.3f} |",
        "",
        "## Confusion matrix — optimized (rows=human, cols=judge)",
        "",
        "| human \\ judge | green | yellow | red |",
        "|---|---:|---:|---:|",
    ]
    for h in ["green", "yellow", "red"]:
        r = opt_metrics["confusion"][h]
        lines.append(f"| **{h}** | {r['green']} | {r['yellow']} | {r['red']} |")
    lines += [
        "",
        "## Confusion matrix — baseline on same val set",
        "",
        "| human \\ judge | green | yellow | red |",
        "|---|---:|---:|---:|",
    ]
    for h in ["green", "yellow", "red"]:
        r = base_metrics["confusion"][h]
        lines.append(f"| **{h}** | {r['green']} | {r['yellow']} | {r['red']} |")

    METRICS_OUT.write_text("\n".join(lines))
    print(f"\nReport -> {METRICS_OUT}")
    print(f"Program -> {PROGRAM_OUT}")


if __name__ == "__main__":
    main()
