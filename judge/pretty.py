"""
Pretty-print all .jsonl outputs under judge/IO/ so they're human-readable.

For each `<name>.jsonl`, writes:
  - `<name>.pretty.json` — indented JSON array, easy to read in an editor
  - `<name>.md`          — one readable block per row with tags, reasoning,
                           and a human-vs-judge comparison where applicable

Safe to re-run — overwrites the `.pretty.json` / `.md` companions each time.
Does not touch the original `.jsonl` files.
"""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).parent
IO_ROOT = HERE / "IO"


def load_jsonl(path: Path) -> list[dict]:
    out: list[dict] = []
    for line in path.open():
        line = line.strip()
        if not line:
            continue
        out.append(json.loads(line))
    return out


def write_pretty_json(rows: list[dict], out: Path) -> None:
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=2))


def flag_label(p: dict, key: str) -> str:
    v = p.get(key)
    if v is None:
        return "—"
    emoji = {"golden": "🟨", "blue": "🟦", "green": "🟢", "yellow": "🟡", "red": "🔴"}.get(v, "")
    return f"{emoji} {v}"


def row_md(r: dict, i: int) -> str:
    lines: list[str] = []
    name = r.get("name", "?")
    human = flag_label(r, "human_flag")
    pred = flag_label(r, "predicted_label") if "predicted_label" in r else None
    lines.append(f"### {i}. {name}")
    if pred is not None:
        match = "✅ match" if r.get("human_flag") == r.get("predicted_label") else "❌ mismatch"
        lines.append(f"- **Human:** {human}  ·  **Judge:** {pred}  ·  {match}")
    else:
        lines.append(f"- **Human:** {human}")
    if r.get("linkedin_url"):
        lines.append(f"- LinkedIn: {r['linkedin_url']}")
    if r.get("human_remark"):
        lines.append(f"- Human remark: *{r['human_remark']}*")
    tags = r.get("reasoning_tags") or []
    if tags:
        lines.append(f"- Judge tags: `{', '.join(tags)}`")
    if r.get("reasoning_text"):
        lines.append(f"- Judge reason: {r['reasoning_text']}")
    if r.get("red_bucket"):
        extra = ""
        if r.get("reapproach_after"):
            extra = f" · reapproach after **{r['reapproach_after']}**"
        lines.append(f"- Red routing: `{r['red_bucket']}`{extra}")
    if r.get("error"):
        lines.append(f"- ⚠️ error: {r['error']}")
    return "\n".join(lines)


def write_md(rows: list[dict], out: Path, src: Path) -> None:
    header = [f"# {src.name}", ""]
    # Summary counts where possible
    h_counts: dict[str, int] = {}
    p_counts: dict[str, int] = {}
    correct = 0
    valid = 0
    for r in rows:
        h = r.get("human_flag")
        if h:
            h_counts[h] = h_counts.get(h, 0) + 1
        p = r.get("predicted_label")
        if p:
            p_counts[p] = p_counts.get(p, 0) + 1
            valid += 1
            if h == p:
                correct += 1
    header.append(f"- Rows: **{len(rows)}**")
    if h_counts:
        header.append(f"- Human flags: {h_counts}")
    if p_counts:
        header.append(f"- Judge predictions: {p_counts}")
        header.append(f"- Agreement: **{correct}/{valid}** = {100*correct/max(valid,1):.1f}%")
    header.append("")
    body = [row_md(r, i) for i, r in enumerate(rows, 1)]
    out.write_text("\n\n".join(header + body))


def prettify_all() -> list[tuple[Path, Path, Path]]:
    produced: list[tuple[Path, Path, Path]] = []
    for src in sorted(IO_ROOT.rglob("*.jsonl")):
        rows = load_jsonl(src)
        pretty = src.with_suffix(".pretty.json")
        md = src.with_suffix(".md")
        # Don't clobber existing markdown reports (e.g., comparison.md),
        # only overwrite our own `<stem>.md` companions.
        write_pretty_json(rows, pretty)
        write_md(rows, md, src)
        produced.append((src, pretty, md))
    return produced


if __name__ == "__main__":
    for src, pretty, md in prettify_all():
        rel = src.relative_to(HERE)
        print(f"  {rel}  ({len(load_jsonl(src))} rows)")
        print(f"    -> {pretty.relative_to(HERE)}")
        print(f"    -> {md.relative_to(HERE)}")
