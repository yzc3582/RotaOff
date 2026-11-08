import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import rotaoff.library as lib
from rotaoff.store import RotaOffError

lib.build_database = lambda payload, target: {
    "songs": 1, "charts": 1, "iv_alpha": 0, "latest_release": "x", "path": target,
}
lib.activate = lambda instance: None
lib.open_database = lambda target: object()

retired_ok = {
    "count": 11, "path": "x", "text": "t", "db": "d", "url": "u",
    "source": "fetched from wiki", "warning": "", "missing": [],
}

lib.retired.sync = lambda *args, **kwargs: retired_ok
lib.fetch_remote = lambda timeout=30: {"songs": {}}
notes = lib.update(locale="en-US")["notes"]
assert not any("manual download" in item.lower() for item in notes), notes
print("success_no_links", notes)

lib.fetch_remote = lambda timeout=30: (_ for _ in ()).throw(RotaOffError("no net"))
lib.load_local = lambda path: {"songs": {}}
notes = lib.update(locale="en-US")["notes"]
assert any("Songlist.json manual download" in item for item in notes), notes
assert not any("Retired-song list manual download" in item for item in notes), notes
print("songlist_failure_has_link")

lib.retired.sync = lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("boom"))
notes = lib.update(locale="en-US")["notes"]
assert any("Failed to refresh" in item for item in notes), notes
assert any("Retired-song list manual download" in item for item in notes), notes
print("retired_failure_has_link")

print("OK")