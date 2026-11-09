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
from datetime import datetime

import requests

import rotaeno

from . import completion, patch, retired
from .paths import LIBRARY_GAPS_FILE, SAVES_DIR
from .store import RotaOffError, active_profile_name, require_ready_profile

NO_DATA = "【无数据】"          # 只兜底展示性字段；定数缺失的谱面不会进结果

CUSTOM_LABELS = {
    "username": "用户名",
    "rating": "Rating",
    "level": "等级",
    "exp": "EXP",
    "completion": "完成度（可能有偏差）",
    "app": "APP",
    "ap": "AP",
    "fc": "FC",
    "charts": "谱面记录",
    "playtime": "游玩时长",
    "b40": "B40",
    "cloud_updated_at": "云存档更新时间",
    "fetched_at": "拉取时间",
    "rating_diff": "Rating 变化",
    "songs_diff": "成绩变化",
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


# ------------------------------------------------------------ 存档快照与变化
# 上游历史库（`rotaeno/database/player_data.py`）只存玩家级字段，单谱分数**不入库**，
# 所以「哪首歌的分数变了」只能自己留一份上一轮的成绩。这份快照只用于对比，
# 不参与计算、也不当作读缓存：每条命令仍然实时拉取云存档。


def snapshot_path(profile_name: str) -> str:
    """按配置分开存。配置名可能带斜杠/空格，先滤掉路径分隔符再当文件名。"""
    safe = re.sub(r"[^0-9A-Za-z_.-]+", "_", profile_name or "").strip(" .") or "default"
    return os.path.join(SAVES_DIR, f"{safe}.json")


def _chart_key(song: dict) -> str:
    """谱面唯一键：曲目 id + 难度。两者都不随曲名改动。"""
    return f'{song.get("id")}|{song.get("level")}'


def _song_rating(song: dict) -> float:
    return float(song.get("ratingMix", song.get("rating", 0)) or 0)


def display_status(song: dict) -> str:
    """状态列：`Flag` + 是否通关，例如 `NONE(C)` / `AP(-)`。

    `Flag` 只说明有没有 FC/AP 标记，**不保证通关**：All Perfect+ 挑战、以及历史上
    「AP 了但没 Clear」的 bug，都会留下 `FC`/`AP` 却没通关的记录。所以统一带后缀，
    已通关 `(C)`、未通关 `(-)`，不要只给 NONE 加标记。
    """
    flag = str(song.get("status") or "").upper() or "NONE"
    return f"{flag}({'C' if song.get('isCleared') else '-'})"


def _charts_from(song_datas: list) -> dict:
    """把一轮谱面压成 `{键: (分数, 单谱 Rating, 状态)}`，只在内存里比对用。"""
    charts = {}
    for song in song_datas or []:
        charts[_chart_key(song)] = (
            int(song.get("score") or 0),
            round(_song_rating(song), 4),
            display_status(song),
        )
    return charts


def load_previous(profile_name: str) -> dict:
    """上一轮的快照；文件不存在或损坏都当作「第一次记录」。"""
    try:
        with open(snapshot_path(profile_name), "r", encoding="utf-8") as file:
            payload = json.load(file)
    except (OSError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def store_previous(profile_name: str, snapshot: dict) -> bool:
    """把本轮存成下一轮的对照（全量：`playerInfo` + 全部 `songDatas`）。

    只保留最近一份、每次覆盖；写不进去（只读目录）不该影响本次结果。
    """
    payload = {
        "fetchedAt": str(snapshot.get("fetchedAt") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        "playerInfo": snapshot.get("playerInfo") or {},
        "songDatas": snapshot.get("songDatas") or [],
    }
    try:
        os.makedirs(SAVES_DIR, exist_ok=True)
        with open(snapshot_path(profile_name), "w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False)
    except OSError:
        return False
    return True


def cloud_updated_at(snapshot: dict) -> str:
    """云存档更新时间（CloudSave 对象的 `updatedAt`）：游戏把存档同步到 TapTap 的时刻。

    服务器返回的是 UTC（`...Z`），这里转成运行机器的本地时区再展示；
    与本地时钟无关，也**不是**我们这次拉取的时间（那个是 `fetchedAt`，每次都变）。
    判断「有没有新数据」只看这个。
    """
    raw = str((snapshot.get("playerInfo") or {}).get("updateAt") or "")
    if not raw:
        return ""
    try:
        moment = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return raw.replace("T", " ")[:19]
    if moment.tzinfo is not None:
        moment = moment.astimezone()
    return moment.strftime("%Y-%m-%d %H:%M:%S")


def diff_snapshots(snapshot: dict, previous: dict) -> dict:
    """本轮与上一轮比：Rating 变化 + 单谱变化。`previous` 为空表示第一次记录。"""
    info = snapshot.get("playerInfo") or {}
    rating_now = float(info.get("rating", 0) or 0)
    first_time = not previous
    rating_before = (
        None if first_time else float((previous.get("playerInfo") or {}).get("rating", 0) or 0)
    )

    before_charts = _charts_from(previous.get("songDatas") or [])
    songs = []
    for song in snapshot.get("songDatas") or []:
        score = int(song.get("score") or 0)
        rating = round(_song_rating(song), 4)
        status = display_status(song)
        before = before_charts.get(_chart_key(song))
        if before is None:
            if not score:                    # 以前没打、现在也没打：无关
                continue
            old_score, old_rating, old_status = 0, 0.0, "NONE(-)"
        else:
            old_score = int(before[0] or 0)
            old_rating = float(before[1] or 0)
            old_status = str(before[2] or "") or "NONE(-)"
        if score == old_score and status == old_status:
            continue
        songs.append({
            "title": str(song.get("title") or NO_DATA),
            "level": str(song.get("level") or ""),
            "score": (old_score, score),
            "rating": (old_rating, rating),
            "status": (old_status, status),
        })

    return {
        "first_time": first_time,
        "cloud_updated_at": cloud_updated_at(snapshot),
        "previous_time": cloud_updated_at(previous),
        "rating": (rating_before, rating_now),
        "songs": songs,
    }


def _format_rating_diff(diff: dict) -> str:
    """与 RotaBot 输出兼容：`14.7025+0.0000`，即使增量为 0 也照样打。"""
    if not diff:
        return NO_DATA
    if diff.get("first_time"):
        return "首次记录，下次起可对比"
    before, now = diff.get("rating") or (None, None)
    if before is None:
        return f"{now:.4f}"
    return f"{now:.4f}{now - before:+.4f}"


def _format_songs_diff(diff: dict, limit: int = 0) -> str:
    if not diff:
        return NO_DATA
    if diff.get("first_time"):
        return "首次记录，下次起可对比"
    songs = diff.get("songs") or []
    if not songs:
        return "无变化"
    lines = []
    for song in songs[:limit] if limit else songs:
        old_score, new_score = song["score"]
        old_rating, new_rating = song["rating"]
        line = (
            f'{song["title"]} ({song["level"]}): '
            f'{old_score:,} → {new_score:,} ({new_score - old_score:+,})｜'
            f'{old_rating:.4f} → {new_rating:.4f}'
        )
        old_status, new_status = (str(value or "NONE(-)") for value in song["status"])
        if old_status != new_status:
            line += f"｜{old_status} → {new_status}"
        lines.append(line)
    if limit and len(songs) > limit:
        lines.append(f"…还有 {len(songs) - limit} 首")
    return "\n".join(lines)


def change_summary(snapshot: dict) -> str:
    """一行变化摘要，供查询命令顺手提示；没变化或首次记录返回空串。

    真正的明细仍由 `rating_diff` / `songs_diff` 提供，这里只负责「有没有变、变了多少」。
    """
    diff = (snapshot or {}).get("diff") or {}
    if not diff or diff.get("first_time"):
        return ""
    songs = diff.get("songs") or []
    before, now = diff.get("rating") or (None, None)
    if not songs and before == now:
        return ""
    parts = [f"Rating {float(now or 0):.4f}{float(now or 0) - float(before or 0):+.4f}"]
    if songs:
        parts.append(f"{len(songs)} 个谱面有变化")
    return "云存档有变化：" + "，".join(parts)


def fetch_snapshot(profile_name: str | None = None, record_history: bool = True) -> dict:
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
    name = profile_name or active_profile_name()
    previous = load_previous(name)
    try:
        with contextlib.redirect_stdout(buffer):
            snapshot = api.get_cloud_save(add_to_database=record_history)
    except ValueError as exc:                       # 含 requests 的 JSONDecodeError
        raise RotaOffError(
            f"服务器返回的不是 JSON（{type(exc).__name__}: {exc}）\n"
            f"诊断:\n{_probe_response(api, profile)}"
        )
    finally:
        setattr(fetch_snapshot, "last_noise", buffer.getvalue().strip())
        _remember_upstream(buffer.getvalue())

    # 顺序要紧：先跟上一份比，再覆盖写。反了就会永远对比到「无变化」。
    info = snapshot.get("playerInfo")
    if isinstance(info, dict):
        # 上游 `get_cloud_save` 不返回 CloudSave 的 updatedAt，由 patch 在出口截获
        info["updateAt"] = patch.last_cloud_save_updated_at()
    snapshot["fetchedAt"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    snapshot["diff"] = diff_snapshots(snapshot, previous)
    store_previous(name, snapshot)
    return snapshot


def exclude_retired(song_datas: list) -> tuple:
    """去掉已下架曲目的谱面，返回 `(过滤后的列表, 诊断信息)`。

    只用于 Rating / B40；单曲、状态、区间查询仍保留这些谱面。
    """
    retired_ids, missing, error = retired.status()
    if retired_ids:
        song_datas = [
            item for item in song_datas if str(item.get("id")) not in retired_ids
        ]
    return song_datas, {"count": len(retired_ids), "missing": missing, "error": error}


def best40_from(snapshot: dict, limit: int = 40) -> list:
    """按 ratingMix 排序取前 N —— 与 rotaeno.processor.get_best40 的取法一致。"""
    song_datas, _ = exclude_retired(snapshot.get("songDatas") or [])
    return sorted(song_datas, key=lambda item: item.get("ratingMix", 0), reverse=True)[:limit]


def charts_without_diff(song_datas: list) -> list:
    """定数缺失（diff 为 0）的谱面。

    Rating 是用 score + 定数算的，没定数就等于算不准；
    这类谱面在 taptap_processor 那边会被当成 0 定数照算，所以这里要单独拦一下。
    """
    return [item for item in song_datas if not item.get("diff")]


def metrics_from(snapshot: dict) -> dict:
    """把 playerInfo 里能单独拿出来用的数值整理成扁平字典。"""
    info = snapshot.get("playerInfo") or {}
    records = info.get("playRecords") or {}
    diff = snapshot.get("diff") or {}
    raw = snapshot.get("songDatas") or []
    played = len(raw)
    counted, _ = exclude_retired(raw)            # 下架曲不参与 Completion
    return {
        "username": str(info.get("displayName") or NO_DATA),
        "rating": f'{info.get("rating", 0):.4f}',
        "level": f'{info.get("level", 0):.2f}',
        "exp": f'{info.get("exp", 0):,}',
        "completion": completion.format_completion(counted),
        "app": str(records.get("TotalApp", 0)),
        "ap": str(records.get("TotalAp", 0)),
        "fc": str(records.get("TotalFc", 0)),
        "charts": str(played),
        "playtime": str(info.get("totalPlayTime") or NO_DATA),
        "cloud_updated_at": diff.get("cloud_updated_at") or NO_DATA,
        "fetched_at": str(snapshot.get("fetchedAt") or NO_DATA),
        "rating_diff": _format_rating_diff(diff),
        "songs_diff": _format_songs_diff(diff),
    }


def profile_summary(snapshot: dict, show_completion: bool = False) -> list:
    """b40 图片最上面那两行：Rating / 等级。

    完成度默认不显示：数值有已知偏差，只有 `output set completion on` 时才带上
    （见 docs/completion.zh_CN.md 或 docs/completion.en_US.md）。
    """
    info = snapshot.get("playerInfo") or {}
    values = metrics_from(snapshot)
    second = f'APP {values["app"]}  AP {values["ap"]}  FC {values["fc"]}'
    if show_completion:
        second += f'  |  完成度（可能有偏差） {values["completion"]}'
    second += f'  |  时长 {values["playtime"]}'
    return [
        f'{values["username"]}  |  Rating {values["rating"]}  |  Lv.{values["level"]}',
        second,
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
            display_status(song),
        ])
    return rows
