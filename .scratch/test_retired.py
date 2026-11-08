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

print("OK")