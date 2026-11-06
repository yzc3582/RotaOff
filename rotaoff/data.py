"""数据层：一次请求拿到成绩快照，再提取 rating / 等级 / 完成度 / B40。

真正的计算全部复用 rotaeno/ 下已有模块：
- rotaeno.api.taptap_processor.TapTapAPI.get_cloud_save  单谱 Rating、playStats
- rotaeno.database.song_alias                           曲目别名模糊匹配
- rotaeno.database.song_data                            定数与谱面总数

`rotaeno/` 保持只读，网络与目录层面的修补集中在 `rotaoff/patch.py`
（双斜杠 URL、非 JSON 响应、写死的 saves/temp 目录、历史库写入失败）。
"""

import contextlib
import io
import json
import os
import re

import requests

import rotaeno

from .paths import LIBRARY_GAPS_FILE
from .store import RotaOffError, require_ready_profile

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


def _song_library():
    """当前生效的曲库实例（可能是重建库或内存库）。"""
    return rotaeno.database.song_data.song_data


def find_song_id(song_alias: str) -> str:
    """把用户输入解析成 song_id；找不到返回空字符串。

    顺序很重要：先认 **id 完全相同**，再认 **曲名完全相同**，最后才用上游的
    别名模糊匹配。以前只走模糊匹配，输入 `-1` 会被匹配成 `BATTLE NO.1`
    （都是 `-1` 的子串），查出来的是另一首歌。
    """
    alias = (song_alias or "").strip()
    if not alias:
        return ""

    library = _song_library()
    lowered = alias.lower()
    ids = library.getAllsong_ids()

    for song_id in ids:
        if str(song_id).lower() == lowered:
            return song_id

    for song_id in ids:
        song = library.get_song(song_id) or {}
        title = str(song.get("title") or "")
        if title and title.strip().lower() == lowered:
            return song_id

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


def _probe_response(api, profile: dict) -> str:
    """出错时补发几条原始请求做对照，只报告状态码和结构，不打印存档内容。

    rotaeno 里的 BaseAPI 直接 `.json()`，服务器返回空串时只剩一句
    JSONDecodeError；这里把「双斜杠 / 单斜杠 / 有没有 where」几种可能一起试掉。
    """
    object_id = (profile or {}).get("objectID", "")
    where = json.dumps({
        "user": {"__type": "Pointer", "className": "_User", "objectId": object_id}
    })
    cases = (
        ("双斜杠+where", f"{api.base_url}//1.1/classes/CloudSave", {"where": where}),
        ("单斜杠+where", f"{api.base_url}/1.1/classes/CloudSave", {"where": where}),
        ("单斜杠+limit", f"{api.base_url}/1.1/classes/CloudSave", {"limit": 1}),
        ("users/me 对照", f"{api.base_url}/1.1/users/me", None),
    )
    lines = []
    for label, url, params in cases:
        try:
            response = requests.get(
                url, headers=api._build_headers(), params=params,
                allow_redirects=True, proxies=api.proxies, timeout=10, verify=False,
            )
        except Exception as exc:                   # 网络层错误也要看得见
            lines.append(f"  {label}: {type(exc).__name__}: {exc}")
            continue
        text = (response.text or "").strip()
        try:
            body = json.loads(text)
        except ValueError:
            head = " ".join(text.split())[:60] or "(空响应体)"
            lines.append(f"  {label}: HTTP {response.status_code} 非 JSON | {head}")
            continue
        results = body.get("results")
        shape = f"results={len(results)}" if isinstance(results, list) else "无 results"
        lines.append(f"  {label}: HTTP {response.status_code} | {shape} | keys={list(body)}")
    return "\n".join(lines)


_GAPS = {"songs": [], "levels": []}     # 存档里对不上本地曲库的记录
_GAPS_LOADED = False


def _load_gaps() -> None:
    """把上次落盘的记录读回来，跨会话也能看到。读不出来就当没有。"""
    global _GAPS_LOADED
    if _GAPS_LOADED:
        return
    _GAPS_LOADED = True
    try:
        with open(LIBRARY_GAPS_FILE, "r", encoding="utf-8") as file:
            saved = json.load(file)
    except (OSError, json.JSONDecodeError):
        return
    if not isinstance(saved, dict):
        return
    for song_id in saved.get("songs") or []:
        text = str(song_id)
        if text not in _GAPS["songs"]:
            _GAPS["songs"].append(text)
    for pair in saved.get("levels") or []:
        pair = tuple(str(item) for item in pair)
        if len(pair) == 2 and pair not in _GAPS["levels"]:
            _GAPS["levels"].append(pair)


def _save_gaps() -> None:
    """落盘；写失败只忽略——查询结果比这份缓存重要。"""
    payload = {
        "songs": list(_GAPS["songs"]),
        "levels": [list(pair) for pair in _GAPS["levels"]],
    }
    try:
        os.makedirs(os.path.dirname(LIBRARY_GAPS_FILE), exist_ok=True)
        with open(LIBRARY_GAPS_FILE, "w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False, indent=4)
    except OSError:
        pass


def _remember_upstream(text: str) -> None:
    """解析上游那两类提示，记进 `_GAPS` 并落盘（有变化才写）。"""
    _load_gaps()
    changed = False
    for line in (text or "").splitlines():
        found = re.match(r"Song ID `(.+?)` not found", line)
        if found:
            song_id = found.group(1)
            if song_id not in _GAPS["songs"]:
                _GAPS["songs"].append(song_id)
                changed = True
            continue
        found = re.match(r"Song level `(.+?)` not found .*song ID `(.+?)`", line)
        if found:
            pair = (found.group(2), found.group(1))
            if pair not in _GAPS["levels"]:
                _GAPS["levels"].append(pair)
                changed = True
    if changed:
        _save_gaps()


def quiet_call(fn, *args, **kwargs):
    """跑上游函数，吃掉它的 `print` 噪音，但把内容记下来给 `library` 命令看。

    `taptap_processor:141` 会遍历**整份存档**——存档是全量的，没打过的谱也在
    里面（分数 0）——对本地曲库对不上的曲目逐条 `print`。所以这些警告跟
    「你查的是哪一首」无关，查任何一首都会出现同一批。

    两类对不上：
    - `Song ID ... not found`：存档里有这首，`Songlist.json` 还没收录，
      定数无从查起（目前是 doppelganger / terabyte-connection）。
    - `Song level ... not found`：曲目在库里，但存档里的难度键不在库里。
      典型是 `Sp`——**非常规谱面**的总称（旅程小游戏、愚人节、Stasis 与
      Quadruplicity 解禁谱等），一律不计入 Rating。
    """
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        try:
            return fn(*args, **kwargs)
        finally:
            _remember_upstream(buffer.getvalue())


def missing_from_library() -> dict:
    """曲库对不上的清单（含上次落盘的记录）：整首缺失的曲目 + 缺失的难度键。"""
    _load_gaps()
    return {"songs": list(_GAPS["songs"]), "levels": list(_GAPS["levels"])}


def fetch_snapshot(profile_name: str = None, record_history: bool = True) -> dict:
    """一次请求拿到 playerInfo + songDatas。

    `taptap_processor` 在解析时会对本地曲库没收录的曲目 `print(...)` 一行，
    一屏几十上百行噪音会盖住真正的结果，所以这里把这段 stdout 暂时收进缓冲区。
    真出异常时再把缓冲内容一并抛出去，方便排查。

    当前正常会剩 3 行：`doppelganger` 与 `terabyte-connection`（wiki 还没收录），
    以及 `true` 的 `Sp` 难度（愚人节谱面，不计入 Rating）。这三行是预期内的。
    """
    profile = require_ready_profile(profile_name)
    region = (
        rotaeno.api.taptap.ServerRegion.CN
        if profile["serverCode"] == "cn"
        else rotaeno.api.taptap.ServerRegion.GLOBAL
    )
    api = rotaeno.api.taptap_processor.TapTapAPI(region=region, user_profile=profile)
    buffer = io.StringIO()
    try:
        with contextlib.redirect_stdout(buffer):
            return api.get_cloud_save(add_to_database=record_history)
    except ValueError as exc:                       # 含 requests 的 JSONDecodeError
        raise RotaOffError(
            f"服务器返回的不是 JSON（{type(exc).__name__}: {exc}）\n"
            f"诊断:\n{_probe_response(api, profile)}"
        )
    finally:
        fetch_snapshot.last_noise = buffer.getvalue().strip()
        _remember_upstream(buffer.getvalue())


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
