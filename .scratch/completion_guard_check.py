"""验证「未游玩谱面是否虚增完成度」：score=0 时的单谱 Rating 是多少？"""

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from rotaeno.api.taptap_processor import calculate_song_rating

from rotaoff import completion, data

snapshot = json.loads(sorted(pathlib.Path("data/saves").glob("*.json"))[-1].read_text(encoding="utf-8"))
charts, _ = data.exclude_retired(snapshot["songDatas"])

unplayed = [c for c in charts if int(c.get("score") or 0) == 0]
played = [c for c in charts if int(c.get("score") or 0) > 0]
print(f"未游玩 {len(unplayed)} 张 / 已游玩 {len(played)} 张")
sample = unplayed[0]
print("样例未游玩谱面:", sample["title"], sample["level"], "diff =", sample["diff"],
      "score =", sample["score"])
print("  它的 rating =", calculate_song_rating(0, float(sample["diff"]), False)[0],
      "→ 单谱完成度 =", round(completion.chart_completion(sample), 6))

zero = sum(completion.chart_completion(c) for c in unplayed)


def total(rows, guard: bool) -> float:
    per_song = {}
    for chart in rows:
        if guard and int(chart.get("score") or 0) <= 0:
            continue
        level = str(chart.get("level"))
        entry = per_song.setdefault(chart["id"], [0.0, 0.0])
        value = completion.chart_completion(chart)
        if level == completion._IV_ALPHA:
            entry[1] = value
        elif level in completion._LEVEL_WEIGHTS:
            entry[0] = max(entry[0], completion._LEVEL_WEIGHTS[level] * value)
    return sum(best + alpha for best, alpha in per_song.values())


print(f"当前口径（含未游玩）= {total(charts, False):.3f}")
print(f"加 score>0 护栏后    = {total(charts, True):.3f}   （游戏: 43.638）")
print(f"未游玩谱面的单谱完成度之和 = {zero:.3f}")
