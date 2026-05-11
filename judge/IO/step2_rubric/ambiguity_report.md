# Ambiguity Report — 92 colored Crocs-HR-Manager rows

Label semantics: **red=MISMATCH, yellow=OK, green=RELEVANT**.
Target = green. Red and yellow are both penalized.

## The big one: JD is 'HR Manager', not CHRO

`combined_scraper/ai_scorer.py` is tuned for CHRO/Director+ and
penalizes below-Director. The Crocs brief is an *HR Manager*.
That's why several perfect-scored CHROs were flagged RED:

- 10.0  **Tatsuo Kinoshita**  ·  weakness: _While experience is broad_
- 10.0  **Shinichiroh Yamamoto**  ·  weakness: _Current role duration is short (5 months at Google)._
- 9.8  **Akiko Shirasawa** — *Too senior*  ·  weakness: _JD emphasizes hands-on execution; her profile leans heavily towards strategic leadership._
- 9.5  **Mitsuhiro Kageyama**  ·  weakness: _While scope is large_
- 9.5  **Hiroe Onishi**  ·  weakness: _Current role duration is short (5 mos)_
- 9.5  **Kazuo Koiso**  ·  weakness: _Most recent roles are interim or consulting-based_
- 9.3  **Sachi Morishita** — *too senior*  ·  weakness: _Recent tenure at Richemont (3y 5m) is good_
- 9.2  **Yusuke Yamada**  ·  weakness: _Recent roles have been shorter in duration (AvePoint: ~1.5 years_

**Q for user:** is the rubric JD-conditional (`{brief}`
as an input to the judge), or do we treat every JD as a fresh
rubric training run? Haiku on 92 examples is cheap enough for
per-JD retraining, but the rubric tags themselves should be
brief-agnostic (e.g. `level_matches_brief`, not `is_chro`).

## Same remark, different flag

- `'just changed jobs'` → {'yellow': 1, 'red': 7}

**Q for user:** for `'just changed jobs'` the overwhelming label is red
(7×) with one outlier yellow. Does yellow mean "just changed jobs BUT
still approachable / worth keeping warm" or is that one-off a mistake?

## Score × flag matrix (what scores does each color cover?)

| score bucket | green | yellow | red |
|---|---:|---:|---:|
| 9.5-10 | 1 | 6 | 6 |
| 9.0-9.4 | 6 | 3 | 10 |
| 8.0-8.9 | 16 | 10 | 14 |
| 7.0-7.9 | 5 | 3 | 2 |
| <7.0 | 1 | 4 | 5 |

Observation: every score bucket has greens AND reds. **Score does
not predict flag** — the flag is a fit-to-brief verdict, not a
quality rating. The judge must learn tags, not thresholds.

## Low-score GREENs (what makes them relevant despite low score?)

- 6.5  **Fumiko Ogame**  ·  strength: _Current and previous roles at Loro Piana (luxury brand)_
- 7.0  **Hisako O.**  ·  strength: _Progressive HR experience at Tatcha_
- 7.5  **Mitsuki Iida**  ·  strength: _Good tenure in HR roles within luxury retail (Chanel_
- 7.5  **Ryosuke Murata**  ·  strength: _Over 15 years of corporate HR experience with a strong blend of HR_
- 7.5  **Emi Kono**  ·  strength: _Current role as HR Manager_

**Q for user:** what's the minimum criterion for GREEN?
From the data it looks like: HR Manager-level, clean tenure,
relevant industry/multinational context, no red flags.

## Short-tenure / interim / consulting pattern

Several high-score REDs have no remark but share a weakness:
- 10.0  **Shinichiroh Yamamoto**  ·  _Current role duration is short (5 months at Google)._
- 9.5  **Hiroe Onishi**  ·  _Current role duration is short (5 mos)_
- 9.5  **Kazuo Koiso**  ·  _Most recent roles are interim or consulting-based_
- 9.3  **Sachi Morishita**  ·  _Recent tenure at Richemont (3y 5m) is good_
- 9.2  **Yusuke Yamada**  ·  _Recent roles have been shorter in duration (AvePoint: ~1.5 years_
- 9.0  **Seitaro Kano**  ·  _Recent role at LVMH Watches & Jewelry (current_

**Q for user:** is "short tenure in current role" a hard red,
or yellow with a 'recently-joined' caveat? The current data
suggests hard red when tenure is under ~6 months.
