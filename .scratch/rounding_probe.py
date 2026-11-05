"""试各种取整/精度变体，看哪个能精确复现 14.6931。"""
import json
import sys

sys.stdout.reconfigure(encoding="utf-8")

from rotaeno.api import taptap_processor as tp
from rotaeno.api.taptap import ServerRegion
from rotaoff import store

TARGET = 14.6931
consts = {r["id"]: r["levels"] for r in json.load(open(".scratch/wiki_constants.json", encoding="utf-8"))}

p = store.require_ready_profile()
api = tp.TapTapAPI(region=ServerRegion.CN if p["serverCode"] == "cn" else ServerRegion.GLOBAL, user_profile=p)
raw = tp.UserAPI.get_cloud_save(api)["results"][0]["cloudSave"]
songs = raw["data"]["data"]["songs"]["songs"]

raw_rows = []
for sid, rec in songs.items():
    lv = consts.get(sid) or {}
    for level, cell in (rec.get("levels") or {}).items():
        if level not in lv:
            continue
        num = lv[level]
        mix, _ = tp.calculate_song_rating(cell.get("Score", 0) or 0, 0.0, bool(cell.get("IsCleared")))
        r = max(0.0, num + mix)
        if not cell.get("IsCleared"):
            r = min(6.0, r)
        raw_rows.append((r, sid, level))
        if level == "IV" and "IVa" in lv:
            mix2, _ = tp.calculate_song_rating((rec["levels"].get("IV_Alpha") or {}).get("Score", 0) or 0, 0.0, bool((rec["levels"].get("IV_Alpha") or {}).get("IsCleared")))
            raw_rows.append((max(0.0, lv["IVa"] + mix2), sid, "IVa"))


def total(vals):
    v = sorted(vals, reverse=True)[:40]
    v += [0.0] * (40 - len(v))
    return sum(v[:10]) * 0.6 / 10 + sum(v[10:20]) * 0.2 / 10 + sum(v[20:40]) * 0.2 / 20


base = [r[0] for r in raw_rows]
variants = {
    "原样": base,
    "每位round3": [round(x, 3) for x in base],
    "每位floor3": [int(x * 1000) / 1000 for x in base],
    "每位round4": [round(x, 4) for x in base],
    "总和round4": [round(x, 4) for x in base],
}
for name, vals in variants.items():
    t = total(vals)
    print(f"{name:12s} = {t:.6f}   差 {t - TARGET:+.6f}")

print()
print("最接近精确值的方案是哪个 → 需要额外 -0.0010")
# 检查 top40 边界附近有没有并列/极端值
srt = sorted(base, reverse=True)
print("top10-11 边界:", srt[9], srt[10])
print("top20-21 边界:", srt[19], srt[20])
print("top40-41 边界:", srt[39], srt[40])
