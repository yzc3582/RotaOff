"""结构变体扫描：改变分母/分子定义，看哪个正好等于游戏 43.638。"""

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from rotaeno.api.taptap_processor import calculate_song_rating

from rotaoff import completion, data

TARGET = 43.638
W = completion._LEVEL_WEIGHTS
IVA = completion._IV_ALPHA

snapshot = json.loads(sorted(pathlib.Path("data/saves").glob("*.json"))[-1].read_text(encoding="utf-8"))
charts, _ = data.exclude_retired(snapshot["songDatas"])
maxdiff = {}
for chart in charts:
    diff = float(chart.get("diff") or 0)
    maxdiff[chart["id"]] = max(maxdiff.get(chart["id"], 0.0), diff)


def score_and_rating(chart):
    diff = float(chart.get("diff") or 0)
    score = int(chart.get("score") or 0)
    if diff <= 0 or score == 0:
        return diff, score, 0.0
    rating = calculate_song_rating(score, diff, bool(chart.get("isCleared")))[0]
    return diff, score, rating


def bonus(chart):
    return (completion.score_bonus(int(chart.get("score") or 0))
            + completion._FLAG_BONUS.get(str(chart.get("status") or ""), 0.0))


VARIANTS = {
    "A 现行 R/(D+3.6)": lambda c: completion.chart_completion(c),
    "B 只取高于定数的部分 (R-D)/3.6": lambda c: max(0.0, min(1.0, 0.925 * (score_and_rating(c)[2] - score_and_rating(c)[0]) / 3.6 + bonus(c))),
    "C 分母用全曲最高定数": lambda c: max(0.0, min(1.0, 0.925 * score_and_rating(c)[2] / (maxdiff[c["id"]] + 3.6) + bonus(c))),
    "D (R-D)/(D+3.6)": lambda c: max(0.0, min(1.0, 0.925 * (score_and_rating(c)[2] - score_and_rating(c)[0]) / (score_and_rating(c)[0] + 3.6) + bonus(c))),
    "E 现行但衰减 0.925 再乘一次": lambda c: 0.925 * completion.chart_completion(c),
}


for name, func in VARIANTS.items():
    per = {}
    for chart in charts:
        level = str(chart.get("level"))
        if level not in W and level != IVA:
            continue
        value = func(chart)
        entry = per.setdefault(chart["id"], 0.0)
        if level == IVA:
            per[chart["id"]] = entry + value
        else:
            per[chart["id"]] = entry + 0.0
            per[chart["id"]] = per[chart["id"]]
    # 上面写法绕，重算一遍：max(常规) + IVα
    per = {}
    for chart in charts:
        level = str(chart.get("level"))
        if level not in W and level != IVA:
            continue
        value = func(chart)
        slot = per.setdefault(chart["id"], {"max": 0.0, "iva": 0.0})
        if level == IVA:
            slot["iva"] = value
        else:
            slot["max"] = max(slot["max"], W[level] * value)
    total = sum(s["max"] + s["iva"] for s in per.values())
    print(f"{name:34s} = {total:7.3f}  差 {total - TARGET:+7.3f}")
