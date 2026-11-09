"""按 wiki 的 Completion 算法核对数字（离线，只用 data/saves 里的快照）。

锚点：
- 理论 Completion = IV 谱面数 + IV-α 谱面数（v2.99.0 = 463，已排除下架曲）
- 单谱面 C = min(1, 0.925 * R_chart / (D + 3.6) + B_score + B_flag)
"""

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from rotaeno.api.taptap_processor import calculate_song_rating

from rotaoff import data

WEIGHTS = {"I": 0.7, "II": 0.8, "III": 0.9, "IV": 1.0}
IVA = ("IV-α", "IV-alpha", "IVα", "IV_Alpha")


def b_score(score: int) -> float:
    if score < 1008000:
        return 0.0
    if score < 1009000:
        return (score - 1008000) * 0.00001
    if score < 1009250:
        return 0.01 + (score - 1009000) * 0.00002
    if score < 1009500:
        return 0.015 + (score - 1009250) * 0.00003
    if score < 1009750:
        return 0.0225 + (score - 1009500) * 0.00004
    if score < 1009900:
        return 0.0325 + (score - 1009750) * 0.00005
    return 0.04 + (score - 1009900) * 0.0001


B_FLAG = {"FC": 0.01, "AP": 0.02, "APP": 0.025}


def chart_c(chart: dict) -> float:
    diff = float(chart.get("diff") or 0)
    if diff <= 0:
        return 0.0
    score = int(chart.get("score") or 0)
    rating = calculate_song_rating(score, diff, bool(chart.get("isCleared")))[0]
    value = 0.925 * rating / (diff + 3.6) + b_score(score) + B_FLAG.get(chart.get("status"), 0.0)
    return min(1.0, value)


def main() -> None:
    path = sorted(pathlib.Path("data/saves").glob("*.json"))[-1]
    snapshot = json.loads(path.read_text(encoding="utf-8"))
    song_datas, excluded = data.exclude_retired(snapshot.get("songDatas") or [])
    print(f"快照 {path.name}: {len(song_datas)} 谱面（排除下架 {excluded['count']} 首）")

    levels = sorted({str(item.get("level")) for item in song_datas})
    statuses = {}
    for item in song_datas:
        statuses[item.get("status")] = statuses.get(item.get("status"), 0) + 1
    print("难度写法:", levels)
    print("状态分布:", statuses)

    iv = [item for item in song_datas if str(item.get("level")) == "IV"]
    iva = [item for item in song_datas if str(item.get("level")) in IVA]
    print(f"IV 谱面 {len(iv)} + IV-α 谱面 {len(iva)} = 理论 Completion {len(iv) + len(iva)}（wiki: 463）")

    per_song = {}
    for item in song_datas:
        level = str(item.get("level"))
        value = chart_c(item)
        if level in IVA:
            entry = per_song.setdefault(item["id"], {"max": 0.0, "iva": 0.0})
            entry["iva"] = value
        elif level in WEIGHTS:
            entry = per_song.setdefault(item["id"], {"max": 0.0, "iva": 0.0})
            entry["max"] = max(entry["max"], WEIGHTS[level] * value)
    total = sum(entry["max"] + entry["iva"] for entry in per_song.values())
    print(f"当前 Completion = {total:.3f} / {len(iv) + len(iva)}"
          f" = {total / (len(iv) + len(iva)) * 100:.3f}%")

    played = [item for item in song_datas if int(item.get("score") or 0) > 0]
    print(f"（旧口径）已玩谱面 {len(played)} / 总谱面 {len(song_datas)}"
          f" = {len(played) / len(song_datas) * 100:.1f}%")


if __name__ == "__main__":
    main()
