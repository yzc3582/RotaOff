"""区分“新歌”与“ID 漂移”：把缺失的 song_id 拿去本地曲库里比对标题。"""

import re

from rotaeno.database import song_data as sd
from rotaeno.api import taptap as tt
from rotaeno.api import taptap_processor as tp
from rotaoff.store import require_ready_profile


def norm(text) -> str:
    return re.sub(r"[^a-z0-9]", "", str(text).lower())


def main():
    profile = require_ready_profile()
    region = tt.ServerRegion.CN if profile["serverCode"] == "cn" else tt.ServerRegion.GLOBAL
    api = tp.TapTapAPI(region=region, user_profile=profile)
    cloud = tt.UserAPI.get_cloud_save(api)["results"][0]["cloudSave"]
    records = cloud["data"]["data"]["songs"]["songs"]

    ids = sd.song_data.getAllsong_ids()
    print(f"本地曲库曲目数: {len(ids)}")
    by_norm = {}
    for sid in ids:
        info = sd.song_data.get_song(song_id=sid)
        title = info.get("title", sid)
        by_norm.setdefault(norm(title), []).append((sid, title))

    missing = [sid for sid in records if not sd.song_data.get_song(song_id=sid)]
    print(f"玩家存档里有、曲库没有的 song_id: {len(missing)}")
    print()

    drift, new = [], []
    for sid in missing:
        key = norm(sid)
        hit = by_norm.get(key) if key else None
        if not hit:
            near = [(i, t) for k, v in by_norm.items() for (i, t) in v
                    if key and k and (key in k or k in key)]
            hit = near
        (drift if hit else new).append((sid, hit[0] if hit else None))

    print(f"=== 疑似 ID 漂移（曲库有同名曲）: {len(drift)} ===")
    for sid, hit in drift[:30]:
        print(f"  {sid:<34} -> {hit[0]:<30} ({hit[1]})")
    print()
    print(f"=== 曲库完全没有（真·新歌）: {len(new)} ===")
    for sid, _ in new[:40]:
        print(f"  {sid}")


if __name__ == "__main__":
    main()
