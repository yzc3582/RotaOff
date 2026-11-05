"""探测 LeanCloud call/ 云函数是否有曲库/谱面定数接口。"""

import hashlib
import json
import time

import requests
import urllib3

from rotaeno.api import taptap as tt
from rotaoff.store import require_ready_profile

urllib3.disable_warnings()

FUNCS = [
    "GetSongList", "GetSongData", "GetChartList", "GetMusicList", "GetSongInfo",
    "GetAllSongData", "GetSongDatas", "GetChartData", "SyncSongData",
    "GetGameConfig", "GetConfig", "GetVersion", "GetServerInfo",
]


def headers(secret, token):
    ts = str(int(time.time()))
    sign = hashlib.md5(f"{ts}{secret['key']}".encode()).hexdigest()
    return {
        "X-LC-Sign": f"{sign},{ts}",
        "X-LC-Session": token,
        "X-LC-Id": secret["id"],
        "Content-Type": "application/json",
    }


def main():
    profile = require_ready_profile()
    is_cn = profile.get("serverCode") == "cn"
    base = tt.ServerURL.CN if is_cn else tt.ServerURL.GLOBAL
    secret = tt.ServerSecret.CN if is_cn else tt.ServerSecret.GLOBAL
    token = profile.get("sessionToken", "")

    for name in FUNCS:
        url = f"{base}/1.1/call/{name}"
        try:
            r = requests.post(url, headers=headers(secret, token), json={}, timeout=12, verify=False)
            body = (r.text or "").strip().replace("\n", " ")[:160]
        except Exception as exc:
            print(f"{name:<18} EXC {type(exc).__name__}")
            continue
        print(f"{name:<18} HTTP {r.status_code}  {body}")


if __name__ == "__main__":
    main()
