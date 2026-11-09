# Completion — bug and fix record

> A developer-facing post-mortem. `README` only links one line; the full story is here.
> Formula and tables come from the Rotaeno Chinese wiki page
> [「Completion」](https://wiki.rotaeno.cn/index.php?title=Completion) and are used under
> CC BY-NC-SA 3.0; attribution is in `NOTICE.md` section 3.

## 0. Status (wrapped up 2026-11-09)

- **Aligned with the original QQ-side RotaBot as measured at test time**: same cloud save,
  both produce `75.658/461 (16.412%)`.
- It still differs from the in-game value, and **the cloud save carries no unlock/purchase field**,
  so the gap cannot be closed (see §5). **The fix is abandoned.**
- Completion is therefore **hidden by default**: it is only printed after `output set completion on`,
  and every printout is preceded by a deviation warning (accounts that own the whole library
  usually match the game and can trust the number).

## 1. Symptom

The old code computed "completion" as `played charts / total charts in the library`, so every
account showed `100%`. With the real formula the same save produces `75.658/461 (16.412%)`,
while the game shows `43.638/463 (9.425%)` for that save. Both are wrong, in opposite directions:
the numerator is too large, the denominator too small.

## 2. Root cause

**Where 100% came from**: `songDatas` in the cloud save is not "the charts you played" but
**one record for every chart in the library** — unplayed ones sit there with `score = 0 / status = NONE`.
So `len(songDatas)` equals the total chart count (1770 at the time) and the division is always 1.0.

**Why we must compute it ourselves**: `playerInfo` has no official Completion field (the client
computes it and never uploads it), and upstream `rotaeno/` has no such logic at all. The only way
to get a number is to reimplement the wiki formula.

## 3. The formula (wiki)

Per chart:

```
C_chart = min(1, 0.925 × R_chart / (D + 3.6) + B_score + B_flag)
```

- `R_chart` — the single-chart rating of the current score (**recomputed**, see §4)
- `D` — the chart constant; `D + 3.6` is the theoretical maximum chart rating
- `B_score` — stepped bonus starting at 1,008,000, capped at `0.05` for 1,010,000
- `B_flag` — `FC = 0.01`, `AP = 0.02`, all-perfect (`理论值`) `= 0.025`; the best achieved counts

Per song (`W_d` = 0.7 / 0.8 / 0.9 / 1.0):

```
C_single = max(0.7·C_I, 0.8·C_II, 0.9·C_III, C_IV) + C_IVα
```

Total Completion = ΣC_single; the theoretical value = number of counted IV plus IV-α charts
(fixed per version, independent of what the player bought or unlocked). Nothing is rounded during
the calculation; only the display keeps three decimals, rounded **half to even**
(banker's rounding — exactly what Python `round()` does).

Self-check: an all-perfect chart must score `0.925 + 0.05 + 0.025 = 1.0`; verified with a chart
that has a theoretical-value score.


## 4. Implementation

`rotaoff/completion.py` — pure calculation, no network and no file access:

| Function | Purpose |
| --- | --- |
| `score_bonus(score)` | the stepped `B_score` table |
| `chart_completion(chart)` | per-chart Completion |
| `completion_from(song_datas)` | `(current, theoretical)` |
| `format_completion(song_datas)` | `75.658/461 (16.412%)` |

`data.metrics_from()` runs `exclude_retired()` and then calls `format_completion()`; the old
`total_chart_count()` and the copy that lived in `data.py` are gone.

**It never reads `ratingMix`**: upstream zeroes the IV rating whenever IV-α is higher than IV
(because of B40), which would underreport difficulty IV here. Every rating is recomputed through
`calculate_song_rating()`.

**Hidden by default**: `output.completion` defaults to `false`. When shown, the label itself reads
`完成度（可能有偏差）` and each printout is preceded by a warning (`completion-caveat` in
`data/i18n/*.json`). With the switch off, `custom completion` fails loudly (`completion-hidden`)
instead of silently degrading.

## 5. Known deviations (unresolved, missing data)

### 5.1 Numerator: 75.658 vs the game's 43.638

The wiki applies an unlocked-only rule: a chart that is not unlocked does not take part in the
current Completion. But the cloud save has **no unlock/purchase field**: `songDatas` only carries
`diff / id / isCleared / isFavorite / level / nextPointScore / rating / ratingMix / score / status /
title`, and `status = NONE` merely means "no score" — it cannot tell "bought but never played" from
"not bought, played during a limited event".

So the implementation approximates "unlocked" as `score > 0`, which makes the result an **upper bound**.
Typical counterexample: `Secret Illumination (seatrus's "The AURA" Remix)` sits in the test account's
B40 after an event play, yet that song was never unlocked. About 35 of that account's 97 played songs
must be of this kind to explain the 32.02 of excess.

Alternative readings were all tried and none matches 43.638: IV charts only (54.79), cleared IV charts
only (51.64), `(R-D)/3.6` (55.74), denominator taken from the song's highest constant (70.37),
an extra 0.925 factor (69.98). The error is not a single constant offset but the missing
"which charts take part" information.

### 5.2 Denominator: 461 vs 463

The library holds 429 songs (434 minus 5 retired) plus 32 IV-α charts = 461, while the wiki records
463 for v2.99.0. The 2-chart difference probably comes from the **scope of the retirement rule** —
whether `KING` / `ラグトレイン` also take their IV-α charts with them when retired — and from how the
wiki table's 465 → 463 step is counted. Unresolved.

### 5.3 A data source that could help (deferred)

The wiki "song list" page marks event songs, but event songs **can be unlocked too** (the test account
owns Flashdance, Love Splash and 伊天珀凌). Judging "not unlocked" reliably would need a hand-maintained
ownership list, which costs more than it is worth. We stop at "upper bound + documentation".


## 6. The calibration experiment we planned (abandoned)

Reason for abandoning: **the cloud save simply lacks an unlock/purchase field**, so the wiki's
"unlocked only" clause cannot be evaluated from data; the inflated numerator is structural and no
calibration will fix it. The denominator adds another 2-chart uncertainty (461 vs 463). The original
RotaBot prints the numerator alone (`75.658`), probably to dodge the denominator question; this
implementation still prints `numerator/denominator (percent)` but hides it by default.

Worth recording: `75.658` is the **numerator**, not a percentage — the percentage is `16.412%`.
Even that was misread at first.

The original plan (only ever meant to validate the per-chart formula, unrelated to the numerator gap):
`Cryogenic` has `score = 0` on all four difficulties (unlocked but never played), so its current
contribution to the numerator is exactly 0 while it already occupies one denominator slot. Playing its
**IV** once and comparing the in-game Completion before/after gives that chart's true `C_chart`, which
cleanly separates "the per-chart formula is wrong" from "the set of participating charts is wrong".

Prediction (`D = 13.0`, score 1,000,000): `R = 15.0` → `0.925 × 15 / 16.6 ≈ 0.836`, `B_score = 0`
(below 1,008,000), so Completion should move from `43.638` to about `44.474`.

It would also answer something the wiki leaves open: **an unlocked but never-cleared chart — does the
game award 0 or the base value?**
