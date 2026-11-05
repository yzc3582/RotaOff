"""排查：本地曲库缺谱面导致 Rating 偏低。

结论只打印，不写任何文件。
"""

import json

import rotaeno
from rotaeno.database import song_data as sd
from rotaeno.api import taptap as tt
from rotaeno.api import taptap_processor as tp
from rotaoff.store import require_ready_profile

LEVELS = ("I", "II", "III", "IV", "IV_Alpha")


def raw_cloud_save():
    profile = require_ready_profile()
    region = tt.ServerRegion.CN if profile["serverCode"] == "cn" else tt.ServerRegion.GLOBAL
    api = tp.TapTapAPI(region=region, user_profile=profile)
    result = api.get_cloud_save()
    # 从上游的 UserAPI 拿原始存档
    base = tt.UserAPI.get_cloud_save(api)
    return base["results"][0]["cloudSave"]


def bonus(score, cleared):
    """calculate_song_rating 里与分数有关的那部分（不含定数）。"""
    r, _ = tp.calculate_song_rating(score, 0.0, cleared)
    return r


def main():
    cloud = raw_cloud_save()
    user = cloud["data"]["data"]
    records = user["songs"]["songs"]

    missing, present = [], []
    diffs_by_song = {}

    for song_id, levels in records.items():
        info = sd.song_data.get_song(song_id=song_id)
        has_song = bool(info) and info != {}
        for level, rec in (levels.get("levels") or {}).items():
            score = rec.get("Score", 0)
            cleared = rec.get("IsCleared", False)
            bonus_value = bonus(score, cleared)
            if has_song and level in info["levels"]:
                diff = info["levels"][level]["num"]
                rating = max(0.0, diff + bonus_value)
                if not cleared:
                    rating = min(6, rating)
                present.append((song_id, level, diff, score, rating, info["title"]))
            else:
                reason = "整首歌不在曲库" if not has_song else f"缺难度 {level}"
                missing.append((song_id, level, score, bonus_value, cleared, reason))

    print(f"曲库内可算谱面: {len(present)}")
    print(f"曲库缺失谱面: {len(missing)}")
    print()

    # 当前 Rating
    allr = sorted((x[4] for x in present), reverse=True)
    top = allr[:40]
    rating = (sum(top[:10]) * 0.6 / 10 + sum(top[10:20]) * 0.2 / 10
              + sum(top[20:40]) * 0.2 / 20)
    print(f"当前算出的 Rating = {rating:.4f}   目标 = 14.6931   差 = {14.6931 - rating:+.4f}")
    print(f"第 40 名 ratingMix = {top[-1]:.4f}")
    print()

    # 缺的谱面里，光靠分数就已经能进前 40 的（ratingMix >= 第40名 + 定数）
    print("=== 缺的谱面按“分数加成”排序（前 15）===")
    print(f"{'song_id':<28}{'lv':<10}{'score':>10}{'分数加成':>10}{'最小可能Mix':>12}  说明")
    for row in sorted(missing, key=lambda x: -x[3])[:15]:
        song_id, level, score, b, cleared, reason = row
        # 定数最低按 0 算，这里给个下界：只要 加成 + 最低定数 就超过第40名就必然影响
        print(f"{song_id:<28}{level:<10}{score:>10,}{b:>10.3f}{b:>12.3f}  {reason}")
    print()

    # 若这些谱面定数是“IV 类”的常见值，影响有多大
    print("=== 反推：要得到 14.6931，需要补多少 ===")
    delta = 14.6931 - rating
    print(f"需要净增 {delta:.4f}")
    for pos in (1, 10, 20, 40):
        weight = 0.06 if pos <= 10 else (0.02 if pos <= 20 else 0.01)
        print(f"  若新谱面排在第 {pos} 位，需要 ratingMix ≈ {delta / weight:.2f}（不含挤出效应）")

    return cloud, missing, present, top


if __name__ == "__main__":
    main()
