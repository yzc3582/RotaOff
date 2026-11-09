"""扫描聚合/口径变体，找出与游戏 43.638 相符的那一个。"""

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from rotaoff import completion, data

TARGET = 43.638
W = completion._LEVEL_WEIGHTS
IVA = completion._IV_ALPHA

snapshot = json.loads(sorted(pathlib.Path("data/saves").glob("*.json"))[-1].read_text(encoding="utf-8"))
charts, _ = data.exclude_retired(snapshot["songDatas"])

played = [c for c in charts if int(c.get("score") or 0) > 0]
songs_played = {c["id"] for c in played}
print(f"已游玩谱面 {len(played)} 张，涉及 {len(songs_played)} 首；目标 {TARGET}\n")


def base_only(chart):
    """只留 0.925·R/(D+3.6)，不要 B_score / B_flag。"""
    diff = float(chart.get("diff") or 0)
    if diff <= 0 or int(chart.get("score") or 0) == 0:
        return 0.0
    import rotaeno
    rating = rotaeno.api.taptap_processor.calculate_song_rating(
        int(chart.get("score") or 0), diff, bool(chart.get("isCleared")))[0]
    return min(1.0, 0.925 * rating / (diff + 3.6))


def sweep(name, chart_c, aggregate):
    per = {}
    for chart in charts:
        level = str(chart.get("level"))
        entry = per.setdefault(chart["id"], {"max": 0.0, "iva": 0.0, "iv": 0.0, "any": 0.0})
        c = chart_c(chart)
        if level == IVA:
            entry["iva"] = c
        elif level in W:
            entry["max"] = max(entry["max"], W[level] * c)
            if level == "IV":
                entry["iv"] = c
        entry["any"] = max(entry["any"], c)
    value = aggregate(per)
    print(f"{name:38s} = {value:7.3f}  差 {value - TARGET:+7.3f}")
    return value


sweep("当前实现 max(W·C) + C_IVα", completion.chart_completion,
      lambda p: sum(e["max"] + e["iva"] for e in p.values()))
sweep("同上但无 B_score/B_flag", base_only,
      lambda p: sum(e["max"] + e["iva"] for e in p.values()))
sweep("只算 IV 谱", completion.chart_completion, lambda p: sum(e["iv"] for e in p.values()))
sweep("只算 IV 谱（无加成）", base_only, lambda p: sum(e["iv"] for e in p.values()))
sweep("IV + IVα，都按 1.0", completion.chart_completion,
      lambda p: sum(e["iv"] + e["iva"] for e in p.values()))
sweep("IV + IVα（无加成）", base_only, lambda p: sum(e["iv"] + e["iva"] for e in p.values()))
sweep("max(所有难度 C)（不加权、不加 IVα）", completion.chart_completion,
      lambda p: sum(e["any"] for e in p.values()))

clear_only = [c for c in charts if c.get("isCleared")]
print(f"\nisCleared 的谱面 {len(clear_only)} 张")
sweep("仅 isCleared 的 IV 谱（无加成）",
      lambda c: base_only(c) if c.get("isCleared") else 0.0,
      lambda p: sum(e["iv"] for e in p.values()))

flag_only = [c for c in charts if str(c.get("status")) in ("FC", "AP", "APP")]
print(f"有 FC/AP/APP 的谱面 {len(flag_only)} 张")
sweep("仅 FC/AP/APP 的 IV 谱（无加成）",
      lambda c: base_only(c) if str(c.get("status")) in ("FC", "AP", "APP") else 0.0,
      lambda p: sum(e["iv"] for e in p.values()))
