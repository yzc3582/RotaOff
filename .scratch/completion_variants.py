"""对照游戏 43.638，试不同的聚合口径，并打印 Cryogenic 的原始数据。"""

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from rotaeno.api.taptap_processor import calculate_song_rating

from rotaoff import completion, data

SNAP = sorted(pathlib.Path("data/saves").glob("*.json"))[-1]
snapshot = json.loads(SNAP.read_text(encoding="utf-8"))
charts, _ = data.exclude_retired(snapshot["songDatas"])
W = completion._LEVEL_WEIGHTS
IVA = completion._IV_ALPHA
TARGET = 43.638


def c_of(chart, use_rating_mix=False):
    if use_rating_mix:
        diff = float(chart.get("diff") or 0)
        if diff <= 0:
            return 0.0
        value = (0.925 * float(chart.get("ratingMix") or 0) / (diff + 3.6)
                 + completion.score_bonus(int(chart.get("score") or 0))
                 + completion._FLAG_BONUS.get(str(chart.get("status") or ""), 0.0))
        return min(1.0, value)
    return completion.chart_completion(chart)


def aggregate(mode: str) -> float:
    per_song = {}
    for chart in charts:
        level = str(chart.get("level"))
        c = c_of(chart, use_rating_mix=(mode == "ratingMix"))
        entry = per_song.setdefault(chart["id"], {"max": 0.0, "iva": 0.0, "iv": 0.0})
        if level == IVA:
            entry["iva"] = c
        elif level in W:
            entry["max"] = max(entry["max"], W[level] * c)
            if level == "IV":
                entry["iv"] = c
    if mode == "no_iva":
        return sum(e["max"] for e in per_song.values())
    if mode == "iv_only":
        return sum(e["iv"] for e in per_song.values())
    if mode == "iva_in_max":
        return sum(max(e["max"], e["iva"]) for e in per_song.values())
    return sum(e["max"] + e["iva"] for e in per_song.values())


print(f"目标（游戏）: {TARGET}\n")
for mode in ("ours", "no_iva", "iv_only", "iva_in_max", "ratingMix"):
    value = aggregate("ours" if mode == "ratingMix" else mode)
    if mode == "ratingMix":
        value = aggregate("ratingMix")
    print(f"{mode:12s} = {value:8.3f}   差 {value - TARGET:+.3f}")

print("\nCryogenic 的谱面：")
for chart in charts:
    if "cryogenic" in str(chart.get("id", "")).lower() or "cryogenic" in str(chart.get("title", "")).lower():
        print(f'  {chart["title"]} [{chart["level"]}] diff={chart.get("diff")} '
              f'score={chart.get("score")} status={chart.get("status")} '
              f'C={completion.chart_completion(chart):.4f}')

print("\n贡献最大的 8 首：")
rows = []
for chart in charts:
    pass
per_song = {}
for chart in charts:
    level = str(chart.get("level"))
    c = completion.chart_completion(chart)
    entry = per_song.setdefault(chart["id"], {"title": chart.get("title"), "max": 0.0, "iva": 0.0})
    if level == IVA:
        entry["iva"] = c
    elif level in W:
        entry["max"] = max(entry["max"], W[level] * c)
rows = sorted(per_song.values(), key=lambda e: e["max"] + e["iva"], reverse=True)[:8]
for row in rows:
    print(f'  {row["max"] + row["iva"]:.3f}  {row["title"]}  (常规 {row["max"]:.3f} + IVα {row["iva"]:.3f})')
