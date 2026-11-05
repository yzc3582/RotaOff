"""探测 LeanCloud 上是否有可读的曲库/谱面数据类。"""

import json

import requests

from rotaeno.api import taptap as tt
from rotaeno.api import taptap_processor as tp
from rotaoff.store import require_ready_profile

CANDIDATES = [
    "SongData", "Song", "Songs", "SongInfo", "SongList", "ChartData", "Chart",
    "MusicData", "Music", "LevelData", "SongLevel", "SongDifficulty",
]

REGION_HOSTS = {
    "cn": (tt.ServerURL.CN, tt.ServerSecret.CN),
    "global": (tt.ServerURL.GLOBAL, tt.ServerSecret.GLOBAL),
}


def main():
    profile = require_ready_profile()
    region_key = "cn" if profile.get("serverCode") == "cn" else "global"
    base, secret = REGION_HOSTS[region_key]

    import hashlib
    import time

    def headers():
        ts = str(int(time.time()))
        sign = hashlib.md5(f"{ts}{secret['key']}".encode()).hexdigest()
        return {
            "X-LC-Sign": f"{sign},{ts}",
            "X-LC-Session": profile.get("sessionToken", ""),
            "X-LC-Id": secret["id"],
            "Content-Type": "application/json",
        }

    for cls in CANDIDATES:
        url = f"{base}/1.1/classes/{cls}"
        try:
            r = requests.get(url, headers=headers(), params={"limit": 1}, timeout=10, verify=False)
        except Exception as exc:
            print(f"{cls:<16} EXC {exc}")
            continue
        body = (r.text or "")[:120].replace("\n", " ")
        print(f"{cls:<16} HTTP {r.status_code}  {body}")


if __name__ == "__main__":
    main()
