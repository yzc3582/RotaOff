"""离线验证「存档快照对比」：不联网、不读真账号，只喂构造数据。

跑法：.venv\\Scripts\\python .scratch\\test_snapshot_diff.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rotaoff import data


def snapshot(rating, scores, updated_at="2026-11-06T08:46:52.000Z"):
    """scores: {(id, level): (score, chart_rating, status, is_cleared)}"""
    songs = []
    for (song_id, level), (score, chart_rating, status, cleared) in scores.items():
        songs.append({
            "id": song_id, "level": level, "title": f"Song-{song_id}",
            "score": score, "ratingMix": chart_rating, "status": status,
            "isCleared": cleared, "diff": 13.0,
        })
    return {"playerInfo": {"rating": rating, "updateAt": updated_at}, "songDatas": songs}


first = snapshot(14.6931, {
    ("1", "IV"): (1001551, 13.7551, "NONE", True),      # 通关但没标记
    ("2", "IV"): (0, 0.0, "", False),                   # 没打过
})

print("== 状态列格式 ==")
for song in first["songDatas"]:
    print(f'  {song["title"]}: {data.display_status(song)}')

print("\n== 首次（没有上一份）==")
diff = data.diff_snapshots(first, {})
print("first_time:", diff["first_time"])
print("rating_diff:", data._format_rating_diff(diff))
print("songs_diff :", data._format_songs_diff(diff))

data.store_previous("__probe__", first)
previous = data.load_previous("__probe__")
print("\n== 落盘往返 ==")
print("keys:", sorted(previous), "| 文件:",
      os.path.getsize(data.snapshot_path("__probe__")), "bytes")
print("playerInfo.rating:", previous["playerInfo"]["rating"])

# 第二轮：1 号涨分并打出 AP 但**没通关**，2 号从 0 打到 90 万
second = snapshot(14.7025, {
    ("1", "IV"): (1006012, 14.5020, "AP", False),
    ("2", "IV"): (900000, 11.8000, "NONE", True),
}, updated_at="2026-11-06T09:10:00.000Z")
second["fetchedAt"] = "2026-11-06 17:12:03"

print("\n== 第二次（有变化）==")
diff = data.diff_snapshots(second, previous)
print("rating_diff:", data._format_rating_diff(diff))
print("songs_diff :")
print(data._format_songs_diff(diff))

# 第三轮：分数、Flag 都没变，只有 1 号从「未通关」变成「已通关」
third = snapshot(14.7025, {
    ("1", "IV"): (1006012, 14.5020, "AP", True),
    ("2", "IV"): (900000, 11.8000, "NONE", True),
}, updated_at="2026-11-06T09:10:00.000Z")

print("\n== 第三次（只有通关状态变了）==")
diff = data.diff_snapshots(third, second)
print("rating_diff:", data._format_rating_diff(diff))
print("songs_diff :", data._format_songs_diff(diff))

# 第四轮：完全没变 -> 必须静默
fourth = snapshot(14.7025, {
    ("1", "IV"): (1006012, 14.5020, "AP", True),
    ("2", "IV"): (900000, 11.8000, "NONE", True),
}, updated_at="2026-11-06T09:10:00.000Z")
diff = data.diff_snapshots(fourth, third)
print("\n== 第四次（无变化）==")
print("rating_diff:", data._format_rating_diff(diff))
print("songs_diff :", data._format_songs_diff(diff))

os.remove(data.snapshot_path("__probe__"))
print("\nOK")
