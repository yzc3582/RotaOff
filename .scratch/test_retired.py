import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import rotaeno

from rotaoff import retired

records = retired.load()
print(f"records={len(records)}")
for record in records:
    print(" ", record)

today = date(2026, 11, 8)
print(f"due={len(retired.due(records, today))}")

instance = rotaeno.database.song_data.song_data
songs = [(song_id, (instance.get_song(song_id) or {}).get("title", ""))
         for song_id in instance.getAllsong_ids()]
matched, missing = retired.match(records, songs)
print(f"matched={len(matched)} missing={missing}")
print("ids=", sorted(matched))

ids, missing, error = retired.status(today)
assert ids == matched and missing == [] and error == "", (ids, missing, error)

from rotaoff import data

fake = [{"id": "king", "ratingMix": 14.0}, {"id": "other", "ratingMix": 13.0}]
filtered, info = data.exclude_retired(fake)
assert [item["id"] for item in filtered] == ["other"], filtered
assert info["count"] == 5, info
assert [item["id"] for item in data.best40_from({"songDatas": fake})] == ["other"]

import contextlib
import io

from rotaoff import ui

buffer = io.StringIO()
with contextlib.redirect_stdout(buffer):
    ui.render_result({"name": "T", "summary": [], "warnings": ["测试警告"], "show_table": False})
assert "测试警告" in buffer.getvalue()

print("OK")