"""按「有没有打 IV」把已游玩曲目拆开，看 43.638 更接近哪一块。"""

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from rotaoff import completion, data

W = completion._LEVEL_WEIGHTS
IVA = completion._IV_ALPHA

snapshot = json.loads(sorted(pathlib.Path("data/saves").glob("*.json"))[-1].read_text(encoding="utf-8"))
charts, _ = data.exclude_retired(snapshot["songDatas"])

per = {}
for chart in charts:
    level = str(chart.get("level"))
    if level not in W and level != IVA:
        continue
    c = completion.chart_completion(chart)
    entry = per.setdefault(chart["id"], {"title": chart.get("title"), "max": 0.0,
                                        "iv": None, "iva": 0.0, "levels": []})
    if int(chart.get("score") or 0) > 0:
        entry["levels"].append(level)
    if level == IVA:
        entry["iva"] = c
    else:
        entry["max"] = max(entry["max"], W[level] * c)
        if level == "IV":
            entry["iv"] = c

with_iv = [e for e in per.values() if e["iv"]]
no_iv = [e for e in per.values() if not e["iv"]]
with_iva = [e for e in per.values() if e["iva"]]

def total(rows):
    return sum(e["max"] + e["iva"] for e in rows)

print(f"计入曲目 {len(per)} 首")
print(f"  打过 IV 的 {len(with_iv)} 首 → 合计 {total(with_iv):.3f}")
print(f"  没打过 IV 的 {len(no_iv)} 首（还在玩的低难度）→ 合计 {total(no_iv):.3f}"
      f"   其中真的有成绩的 {sum(1 for e in no_iv if e['levels'])} 首")
print(f"  IV-α 曲目 {len(with_iva)} 首，IVα 部分合计 {sum(e['iva'] for e in with_iva):.3f}")
print(f"总计 {total(per.values()):.3f}   （游戏 43.638）\n")

print("没打过 IV 的曲目明细（前 15 条）：")
for e in sorted(no_iv, key=lambda x: x["max"], reverse=True)[:15]:
    print(f'  {e["max"]:.3f}  {e["title"]}  打过: {e["levels"] or "无"}')

print("\n打过 IV 的曲目里，IV 谱 C 值分布：")
vals = sorted((e["iv"] for e in with_iv), reverse=True)
print("  前 10:", [round(v, 3) for v in vals[:10]])
print("  后 10:", [round(v, 3) for v in vals[-10:]])
print("  平均:", round(sum(vals) / len(vals), 4))
