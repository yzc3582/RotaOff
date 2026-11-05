"""用 wiki 定数重算 Rating，验证能否复现用户真实值 14.6931。"""
import json
import sys

sys.stdout.reconfigure(encoding="utf-8")

from rotaeno.api import taptap_processor as tp
from rotaoff import data as od
from rotaoff import store

LEVEL_TO_DIFF = {"I": 0, "II": 1, "III": 2, "IV": 3, "IVa": 4}

consts = {r["id"]: r["levels"] for r in json.load(open(".scratch/wiki_constants.json", encoding="utf-8"))}

profile = store.require_ready_profile()
from rotaeno.api.taptap import ServerRegion

region = ServerRegion.CN if profile["serverCode"] == "cn" else ServerRegion.GLOBAL
api = tp.TapTapAPI(region=region, user_profile=profile)
raw = tp.UserAPI.get_cloud_save(api)["results"][0]["cloudSave"]
songs = raw["data"]["data"]["songs"]["songs"]

rows = []
missing = []
for sid, rec in songs.items():
    lv = consts.get(sid)
    for level, cell in (rec.get("levels") or {}).items():
        score = cell.get("Score", 0) or 0
        cleared = bool(cell.get("IsCleared"))
        if level not in LEVEL_TO_DIFF:
            continue
        if not lv or level not in lv:
            missing.append((sid, level, score))
            continue
        num = lv[level]
        mix, _ = tp.calculate_song_rating(score, 0.0, cleared)
        rating = max(0.0, num + mix)
        if not cleared:
            rating = min(6.0, rating)
        rows.append((rating, sid, level, score, num))

# IV 与 IV_Alpha 二选一：官方只取高的那个，另一个置 0（见 taptap_processor.py:170-176）
by_song = {}
for r in rows:
    by_song.setdefault(r[1], {})[r[2]] = r
for sid, lvmap in by_song.items():
    if "IV" in lvmap and "IVa" in lvmap:
        loser = "IV" if lvmap["IVa"][0] >= lvmap["IV"][0] else "IVa"
        r = lvmap[loser]
        rows[rows.index(r)] = (0.0, r[1], r[2], r[3], r[4])


def total(values):
    values = sorted(values, reverse=True)[:40]
    while len(values) < 40:
        values.append(0.0)
    return sum(values[:10]) * 0.6 / 10 + sum(values[10:20]) * 0.2 / 10 + sum(values[20:40]) * 0.2 / 20


rows.sort(reverse=True)
rating = total([r[0] for r in rows])
print(f"可算谱面 {len(rows)} | 仍缺定数 {len(missing)}")
print(f"Rating = {rating:.4f}   (目标 14.6931, 差 {rating - 14.6931:+.4f})")
print(f"第40名 ratingMix = {rows[39][0]:.4f}" if len(rows) > 39 else "不足40条")
print("\nB40 (rating / 曲名 / 难度 / 分数 / 定数):")
titles = {r["id"]: r["title"] for r in json.load(open(".scratch/wiki_constants.json", encoding="utf-8"))}
for i, (rt, sid, level, score, num) in enumerate(rows[:40], 1):
    print(f"{i:2d}. {rt:7.4f}  {titles.get(sid, sid)[:28]:28s} {level:3s} {score:>8}  {num}")
if missing:
    print("\n仍缺定数的谱面:", missing[:20], "共", len(missing))
