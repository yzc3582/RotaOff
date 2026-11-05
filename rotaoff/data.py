"""数据层：一次请求拿到成绩快照，再提取 rating / 等级 / 完成度 / B40。

真正的计算全部复用 rotaeno/ 下已有模块：
- rotaeno.api.taptap_processor.TapTapAPI.get_cloud_save  单谱 Rating、playStats
- rotaeno.database.song_alias                           曲目别名模糊匹配
- rotaeno.database.song_data                            定数与谱面总数
"""

import rotaeno

from .store import require_ready_profile

NO_DATA = "【无数据】"          # 只兜底展示性字段；定数缺失的谱面不会进结果

CUSTOM_LABELS = {
    "username": "用户名",
    "rating": "Rating",
    "level": "等级",
    "exp": "EXP",
    "completion": "完成度",
    "app": "APP",
    "ap": "AP",
    "fc": "FC",
    "charts": "谱面记录",
    "playtime": "游玩时长",
    "b40": "B40",
}

B40_COLUMNS = ("#", "曲目", "难度", "定数", "Rating", "分数", "状态")
B40_ALIGNS = ("right", "left", "center", "right", "right", "right", "center")


def find_song_id(song_alias: str) -> str:
    """模糊匹配曲目别名，返回 song_id；找不到返回空字符串。"""
    alias = (song_alias or "").strip()
    if not alias:
        return ""
    fit = 80
    while fit > 0:
        results = rotaeno.database.song_alias.song_alias.get_song_id(song_alias=alias, fit=fit)
        if results:
            return next(iter(results.values()))
        fit -= 5
    return ""


def suggest_song_aliases(song_alias: str, limit: int = 10) -> list:
    fit = 80
    while fit > 0:
        results = rotaeno.database.song_alias.song_alias.get_song_id(song_alias=song_alias, fit=fit)
        if results:
            return list(results.keys())[:limit]
        fit -= 5
    return []


def fetch_snapshot(profile_name: str = None, record_history: bool = True) -> dict:
    """一次请求拿到 playerInfo + songDatas。"""
    profile = require_ready_profile(profile_name)
    region = (
        rotaeno.api.taptap.ServerRegion.CN
        if profile["serverCode"] == "cn"
        else rotaeno.api.taptap.ServerRegion.GLOBAL
    )
    api = rotaeno.api.taptap_processor.TapTapAPI(region=region, user_profile=profile)
    return api.get_cloud_save(add_to_database=record_history)


def best40_from(snapshot: dict, limit: int = 40) -> list:
    """按 ratingMix 排序取前 N —— 与 rotaeno.processor.get_best40 的取法一致。"""
    song_datas = snapshot.get("songDatas") or []
    return sorted(song_datas, key=lambda item: item.get("ratingMix", 0), reverse=True)[:limit]


def charts_without_diff(song_datas: list) -> list:
    """定数缺失（diff 为 0）的谱面。

    Rating 是用 score + 定数算的，没定数就等于算不准；
    这类谱面在 taptap_processor 那边会被当成 0 定数照算，所以这里要单独拦一下。
    """
    return [item for item in song_datas if not item.get("diff")]


def total_chart_count() -> int:
    """本地曲库里的谱面总数，用来算完成度（只查一次，进程内缓存）。"""
    cached = getattr(total_chart_count, "cached", None)
    if cached is None:
        songs = rotaeno.database.song_data.song_data.get_songs_rating_real_range(0, 9999)
        cached = sum(len(song["levels"]) for song in songs)
        total_chart_count.cached = cached
    return cached


def metrics_from(snapshot: dict) -> dict:
    """把 playerInfo 里能单独拿出来用的数值整理成扁平字典。"""
    info = snapshot.get("playerInfo") or {}
    records = info.get("playRecords") or {}
    played = len(snapshot.get("songDatas") or [])
    total = total_chart_count()
    percent = played / total * 100 if total else 0.0
    return {
        "username": str(info.get("displayName") or NO_DATA),
        "rating": f'{info.get("rating", 0):.4f}',
        "level": f'{info.get("level", 0):.2f}',
        "exp": f'{info.get("exp", 0):,}',
        "completion": f"{played}/{total} ({percent:.1f}%)",
        "app": str(records.get("TotalApp", 0)),
        "ap": str(records.get("TotalAp", 0)),
        "fc": str(records.get("TotalFc", 0)),
        "charts": str(played),
        "playtime": str(info.get("totalPlayTime") or NO_DATA),
    }


def profile_summary(snapshot: dict) -> list:
    """b40 图片最上面那两行：Rating / 等级 / 完成度。"""
    info = snapshot.get("playerInfo") or {}
    values = metrics_from(snapshot)
    return [
        f'{values["username"]}  |  Rating {values["rating"]}  |  Lv.{values["level"]}',
        f'APP {values["app"]}  AP {values["ap"]}  FC {values["fc"]}  |  '
        f'完成度 {values["completion"]}  |  时长 {values["playtime"]}',
    ]


def best40_rows(song_datas: list) -> list:
    """B40 表格行；缺曲名时用【无数据】占位，不去下载任何素材。"""
    rows = []
    for index, song in enumerate(song_datas, 1):
        rows.append([
            index,
            str(song.get("title") or NO_DATA),
            str(song.get("level") or NO_DATA),
            f'{song.get("diff", 0):.1f}',
            f'{song.get("ratingMix", song.get("rating", 0)):.2f}',
            f'{song.get("score", 0):,}',
            str(song.get("status") or NO_DATA),
        ])
    return rows
