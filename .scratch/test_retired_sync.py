import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import rotaeno
import rotaeno.database.retired_songs as retired_module

from rotaoff import data, patch, retired

text = retired.read_local()
records = retired.parse_all(text)
assert len(records) == 11, len(records)
assert all(record["id"] for record in records)
expected = {"king", "lagtrain", "monitoring", "rokutyounen", "wildcard"}
assert expected <= {record["id"] for record in records}
print("parse_all_ok", len(records))

stats = retired.sync(text=text)
assert stats["count"] == 11, stats
assert not stats["warning"], stats
print("sync_ok", stats["path"], stats["source"])

patch.redirect_retired_songs()
ids = retired_module.retired_songs.get_retired_ids()
assert ids == expected, ids
print("inject_ok", sorted(ids))

ids2, missing, error = retired.status()
assert ids2 == expected and missing == [] and error == "", (ids2, missing, error)
print("status_ok")

filtered, info = data.exclude_retired([{"id": "king"}, {"id": "other"}])
assert [item["id"] for item in filtered] == ["other"], filtered
assert info["count"] == 5, info
print("exclude_ok", info)

print("OK")