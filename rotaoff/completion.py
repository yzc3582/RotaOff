"""Completion（完成度）：纯计算，不碰网络与文件。

算法、难度权重与加成表出自 Rotaeno 中文维基「Completion」条目
<https://wiki.rotaeno.cn/index.php?title=Completion>，按 CC BY-NC-SA 3.0 使用；
改这里的公式前先回去对照原条目。

调用方负责先排除已下架曲目（`data.exclude_retired`），本模块只看传入的谱面。
"""

from rotaeno.api.taptap_processor import calculate_song_rating

_LEVEL_WEIGHTS = {"I": 0.7, "II": 0.8, "III": 0.9, "IV": 1.0}
_IV_ALPHA = "IV_Alpha"                     # 存档里的写法，不是 "IV-α"
_FLAG_BONUS = {"FC": 0.01, "AP": 0.02, "APP": 0.025}   # APP = 理论值


def score_bonus(score: int) -> float:
    """高分段分数加成 B_score：1,008,000 以下为 0，往上分档递增。"""
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


def chart_completion(chart: dict) -> float:
    """单谱面 Completion：min(1, 0.925 * R/(D+3.6) + B_score + B_flag)。

    Rating 现算而不是读 `ratingMix`：上游为了 B40 会把 IV-α 高于 IV 时的 IV 置 0。
    """
    diff = float(chart.get("diff") or 0)
    if diff <= 0:                        # 没定数就算不出 Rating，自然算不出完成度
        return 0.0
    score = int(chart.get("score") or 0)
    rating = calculate_song_rating(score, diff, bool(chart.get("isCleared")))[0]
    value = (0.925 * rating / (diff + 3.6)
             + score_bonus(score)
             + _FLAG_BONUS.get(str(chart.get("status") or ""), 0.0))
    return min(1.0, value)


def completion_from(song_datas: list) -> tuple:
    """(当前 Completion, 理论 Completion)。

    单曲取四个常规难度里「权重 × 单谱完成度」的最大值，IV-α 额外相加；
    理论 Completion 就是计入的 IV 与 IV-α 谱面数。
    """
    per_song: dict = {}
    theory = 0
    for chart in song_datas:
        level = str(chart.get("level") or "")
        song_id = str(chart.get("id") or "")
        entry = per_song.setdefault(song_id, [0.0, 0.0])
        if level == _IV_ALPHA:
            entry[1] = chart_completion(chart)
            theory += 1
        elif level in _LEVEL_WEIGHTS:
            entry[0] = max(entry[0], _LEVEL_WEIGHTS[level] * chart_completion(chart))
            if level == "IV":
                theory += 1
    return sum(best + alpha for best, alpha in per_song.values()), theory


def format_completion(song_datas: list) -> str:
    """`75.658/461 (16.412%)`，与游戏里显示的两个数字对齐。"""
    current, theory = completion_from(song_datas)
    if not theory:
        return "【无数据】"
    return f"{current:.3f}/{theory} ({current / theory * 100:.3f}%)"
