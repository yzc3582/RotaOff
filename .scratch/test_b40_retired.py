import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import rotaeno

from rotaoff import data, retired, tasks

retired_ids, missing, error = retired.status()
assert len(retired_ids) == 5 and not missing and not error, (retired_ids, missing, error)

instance = rotaeno.database.song_data.song_data


def chart(song_id, title, diff, rating, score):
    return {
        "id": song_id, "title": title, "level": "IV", "diff": diff,
        "score": score, "ratingMix": rating, "rating": rating,
        "status": "AP", "isCleared": True,
    }


others = []
for song_id in instance.getAllsong_ids():
    if song_id in retired_ids:
        continue
    song = instance.get_song(song_id) or {}
    level = (song.get("levels") or {}).get("IV")
    if not level:
        continue
    others.append((song_id, song.get("title") or song_id, level.get("num", 10.0)))
    if len(others) == 40:
        break
assert len(others) == 40, len(others)

song_datas = [
    chart(song_id, title, diff, 14.0 - index * 0.01, 1000000 - index)
    for index, (song_id, title, diff) in enumerate(others)
]
for song_id in sorted(retired_ids):
    song = instance.get_song(song_id) or {}
    level = (song.get("levels") or {}).get("IV") or {}
    song_datas.append(
        chart(song_id, song.get("title") or song_id, level.get("num", 10.0), 15.0, 1000000)
    )

snapshot = {
    "playerInfo": {
        "displayName": "Tester", "rating": 14.7061, "level": 30.0, "exp": 123456,
        "totalPlayTime": "1 hour 0 minute 0 second",
        "playRecords": {"TotalApp": 1, "TotalAp": 2, "TotalFc": 3},
    },
    "songDatas": song_datas,
    "fetchedAt": "2026-11-08 16:00:00",
    "diff": {"rating": (14.7061, 14.7061), "songs": [], "first_time": False,
             "cloud_updated_at": "2026-11-08 15:00:00"},
}

ranked, warnings = tasks._ranked(snapshot, {"limit": 40}, "zh-CN")
assert warnings == [], warnings
assert len(ranked) == 40, len(ranked)
assert not any(item["id"] in retired_ids for item in ranked)
print("ranked_ok=40 retired_left=0")

assert not any(item["id"] in retired_ids for item in data.best40_from(snapshot))
assert len(data.best40_rows(ranked)) == 40

original_fetch = data.fetch_snapshot
original_profile = tasks._profile_name
original_locale = tasks.profile_locale
original_load = retired.load
try:
    data.fetch_snapshot = lambda *args, **kwargs: snapshot
    tasks._profile_name = lambda task: "default"
    tasks.profile_locale = lambda name: "zh-CN"

    b40 = tasks.run_task(
        {"name": "b40 test", "type": "b40", "profile": "default"}, render_image=False
    )
    assert len(b40["rows"]) == 40 and b40["warnings"] == []
    assert not any(row[0] in range(41) and row[1] in retired_ids for row in b40["rows"])

    custom = tasks.run_task(
        {"name": "custom test", "type": "custom", "profile": "default",
         "fields": ["rating", "b40"]},
        render_image=False,
    )
    assert len(custom["rows"]) == 40 and custom["warnings"] == []
    print("task_ok=b40+custom")

    retired.load = lambda *args, **kwargs: (_ for _ in ()).throw(OSError("no list"))
    filtered, info = data.exclude_retired(song_datas)
    assert info["error"], info
    assert len(filtered) == len(song_datas), len(filtered)
    ranked2, warnings2 = tasks._ranked(snapshot, {"limit": 40}, "zh-CN")
    assert warnings2 and "读不到" in warnings2[0], warnings2
    print("missing_list_ok=warned_and_not_silently_filtered")
finally:
    data.fetch_snapshot = original_fetch
    tasks._profile_name = original_profile
    tasks.profile_locale = original_locale
    retired.load = original_load

print("OK")