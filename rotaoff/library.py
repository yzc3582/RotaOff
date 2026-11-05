"""曲库同步：把 wiki 的 Songlist.json 变成 rotaoff 能直接用的定数库。

## 为什么需要这一层

上游 `rotaeno/database/song_data.db` 停更在 2.9.0（307 首），而客户端已经到 2.99.0。
Rating 完全依赖定数（`num`），缺一首歌的定数就等于这首算不出来，B40 就整体偏低。
所以这里不碰 `rotaeno/` 里的 .db，只在运行期把 `song_data` 实例换成我们自己建的库。

## 数据从哪来

`https://wiki.rotaeno.cn/index.php?title=Template:Songlist.json&action=raw`，
这正是 RotaBot 原本构建 song_data.db 的同款结构（songs + packs，含 ratingReal 定数、
ratingClass 200 = IV-α）。

## 三层取数，后面的兜前面

1. `--auto` / 自动：纯 Python 解 Anubis 的工作量证明后直接拉 raw。
2. 本地 `Songlist.json`（仓库根目录，gitignore 里）：手动 Ctrl+A Ctrl+C 存下来的也行。
3. 都没有就沿用 `rotaeno/database/song_data.db`（旧库），并明确提示多少谱面算不出来。

## 输出

`data/song_data.db`，表结构与上游完全一致（`songs` + `song_levels`），
上游 `songData` 类可以直接读，所以不用改 `rotaeno/` 一行代码。
"""

import hashlib
import json
import os
import re
import sqlite3
import time

import requests

from . import ui
from .store import RotaOffError

WIKI_BASE = "https://wiki.rotaeno.cn"
WIKI_RAW = WIKI_BASE + "/index.php"
WIKI_PAGE = "Template:Songlist.json"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0 Safari/537.36")

# ratingClass → 库里的难度名。200 是官方给 IV-α 用的特殊值
LEVEL_NAMES = {0: "I", 1: "II", 2: "III", 3: "IV", 200: "IV_Alpha"}
MAX_POW_ITERATIONS = 5_000_000


# ---------------------------------------------------------------- 取原始 json

def fetch_remote(timeout: int = 30) -> dict:
    """自动去 wiki 拉 Songlist.json（含 Anubis PoW）。失败抛 RotaOffError。"""
    session = requests.Session()
    session.headers["User-Agent"] = UA
    session.verify = False
    try:
        import urllib3

        urllib3.disable_warnings()
    except Exception:                    # noqa: BLE001 - 只是少一行警告
        pass

    params = {"title": WIKI_PAGE, "action": "raw"}
    try:
        response = session.get(WIKI_RAW, params=params, timeout=timeout)
    except requests.RequestException as exc:
        raise RotaOffError(f"连不上 wiki.rotaeno.cn: {type(exc).__name__}: {exc}") from exc

    challenge = _parse_challenge(response.text)
    if challenge is not None:
        _solve_challenge(session, challenge, redir=f"/index.php?title={WIKI_PAGE}&action=raw",
                         timeout=timeout)
        try:
            response = session.get(WIKI_RAW, params=params, timeout=timeout)
        except requests.RequestException as exc:
            raise RotaOffError(f"通过验证后重新拉取失败: {exc}") from exc

    body = (response.text or "").strip()
    if not body.startswith("{"):
        head = body[:120].replace("\n", " ")
        raise RotaOffError(
            f"没拿到 Songlist.json（HTTP {response.status_code}，{len(body)} 字节）。\n"
            f"内容开头：{head}\n"
            "多半是 wiki 的反爬验证没通过，或页面改了名字。\n"
            "可以改用本地文件：把页面内容存成仓库根目录的 Songlist.json，"
            "然后执行 `library update --local`。"
        )
    try:
        payload = json.loads(body)
    except ValueError as exc:
        raise RotaOffError(f"Songlist.json 不是合法 JSON: {exc}") from exc
    if not isinstance(payload, dict) or not payload.get("songs"):
        raise RotaOffError("Songlist.json 里没有 songs 字段，格式可能变了。")
    return payload


def _parse_challenge(html: str) -> dict:
    """从被拦截的页面里取出 Anubis 挑战；没有挑战返回 None。"""
    match = re.search(
        r'<script id="anubis_challenge" type="application/json">(.*?)</script>',
        html or "", re.S,
    )
    if not match:
        return None
    raw = match.group(1).strip()
    try:
        if raw.startswith('"'):
            raw = json.loads(raw)        # 内容是双引号包起来的字符串，要解两次
        return json.loads(raw)
    except ValueError:
        return None


def _solve_challenge(session: requests.Session, challenge: dict, redir: str, timeout: int) -> None:
    """暴力找一个 nonce，让 sha256(randomData + nonce) 以 difficulty 个 0 开头。"""
    rules = challenge.get("rules") or {}
    parts = challenge.get("challenge") or {}
    difficulty = int(rules.get("difficulty") or 0)
    data = str(parts.get("randomData") or "")
    if not data:
        raise RotaOffError("wiki 的反爬挑战里没有 randomData，无法自动通过。")

    prefix = "0" * difficulty
    nonce = digest = None
    for index in range(MAX_POW_ITERATIONS):
        candidate = hashlib.sha256(f"{data}{index}".encode()).hexdigest()
        if candidate.startswith(prefix):
            nonce, digest = index, candidate
            break
    if nonce is None:
        raise RotaOffError(
            f"算了 {MAX_POW_ITERATIONS:,} 次也没通过 wiki 的反爬验证（难度 {difficulty}）。\n"
            "请改用本地 Songlist.json：`library update --local`。"
        )

    try:
        passed = session.get(
            f"{WIKI_BASE}/.within.website/x/cmd/anubis/api/pass-challenge",
            params={"id": parts.get("id"), "response": digest, "nonce": nonce,
                    "redir": redir, "elapsedTime": 1500},
            timeout=timeout,
        )
    except requests.RequestException as exc:
        raise RotaOffError(f"提交反爬验证时出错: {exc}") from exc
    if passed.status_code >= 400:
        raise RotaOffError(
            f"wiki 拒绝了反爬验证（HTTP {passed.status_code}）。\n"
            "请改用本地 Songlist.json：`library update --local`。"
        )


# ---------------------------------------------------------------- json → 库

def load_local(path: str) -> dict:
    """读本地 Songlist.json（手动复制的那份也行）。"""
    if not os.path.isfile(path):
        raise RotaOffError(
            f"找不到本地曲库文件: {path}\n"
            "请在 https://wiki.rotaeno.cn/ 打开 Template:Songlist.json 的“查看源代码”，"
            "全选复制，存成这个路径；或者不加 --local 让程序自动抓取。"
        )
    try:
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except ValueError as exc:
        raise RotaOffError(f"{path} 不是合法 JSON: {exc}") from exc
    if not isinstance(payload, dict) or not payload.get("songs"):
        raise RotaOffError(f"{path} 里没有 songs 字段，格式不对。")
    return payload


def levels_of(song: dict) -> dict:
    """把 difficulties 数组转成库里要的 `{"I":{"level","chart","jacket","num"}}`。

    上游 `level` 与 `num` 恒等（已核对旧库 1242 条无例外），这里写同一个值。
    """
    levels = {}
    for difficulty in song.get("difficulties") or []:
        name = LEVEL_NAMES.get(difficulty.get("ratingClass"))
        if name is None:
            continue
        value = difficulty.get("ratingReal")
        if value in (None, 0, "-", ""):
            continue
        value = float(value)
        levels[name] = {
            "level": value,
            "chart": difficulty.get("chartDesigner") or "",
            "jacket": difficulty.get("jacketDesigner") or "",
            "num": value,
        }
    return levels


def normalize(payload: dict) -> list:
    """整理成 [(id, title, artist, duration, release, levels)]，跳过没有谱面的歌。"""
    rows = []
    for song in payload.get("songs") or []:
        song_id = str(song.get("id") or "").strip()
        if not song_id:
            continue
        levels = levels_of(song)
        if not levels:
            continue
        titles = song.get("title_localized") or {}
        title = str(titles.get("default") or song.get("title") or song_id)
        rows.append((
            song_id,
            title,
            str(song.get("artist") or ""),
            int(song.get("duration") or 0),
            str(song.get("release_version") or ""),
            levels,
        ))
    rows.sort(key=lambda item: item[0])
    return rows


def build_database(payload: dict, target: str) -> dict:
    """写出与上游表结构一致的 sqlite 库，返回统计信息。"""
    rows = normalize(payload)
    if not rows:
        raise RotaOffError("Songlist.json 解析后没有任何可用谱面，放弃建库。")

    directory = os.path.dirname(os.path.abspath(target))
    try:
        os.makedirs(directory, exist_ok=True)
    except OSError as exc:
        raise RotaOffError(
            f"建不了目录 {directory}: {exc}\n"
            "如果这是权限问题，请把仓库放在你自己能写的盘里再试。"
        ) from exc

    temporary = target + ".tmp"
    if os.path.exists(temporary):
        try:
            os.remove(temporary)
        except OSError:
            temporary = target + f".{os.getpid()}.tmp"

    try:
        connection = sqlite3.connect(temporary)
    except sqlite3.Error as exc:
        raise RotaOffError(
            f"打不开曲库文件 {temporary}: {exc}\n"
            "多半是 data/ 目录没有写权限；程序会自动退回到内存曲库，不影响本次计算。"
        ) from exc

    try:
        connection.execute(
            "CREATE TABLE songs (id VARCHAR PRIMARY KEY, title VARCHAR NOT NULL, "
            "artist VARCHAR NOT NULL, duration INTEGER NOT NULL, release VARCHAR NOT NULL)"
        )
        connection.execute(
            "CREATE TABLE song_levels (id VARCHAR PRIMARY KEY, levels_data JSON NOT NULL)"
        )
        connection.executemany(
            "INSERT INTO songs (id, title, artist, duration, release) VALUES (?, ?, ?, ?, ?)",
            [(sid, title, artist, duration, release) for sid, title, artist, duration, release, _ in rows],
        )
        connection.executemany(
            "INSERT INTO song_levels (id, levels_data) VALUES (?, ?)",
            [(sid, json.dumps(levels, ensure_ascii=False)) for sid, _, _, _, _, levels in rows],
        )
        connection.commit()
    except sqlite3.Error as exc:
        connection.close()
        raise RotaOffError(f"写曲库时出错: {exc}") from exc
    finally:
        try:
            connection.close()
        except Exception:            # noqa: BLE001
            pass

    try:
        os.replace(temporary, target)
    except OSError as exc:
        raise RotaOffError(f"替换 {target} 失败: {exc}") from exc

    charts = sum(len(levels) for *_, levels in rows)
    return {
        "songs": len(rows),
        "charts": charts,
        "iv_alpha": sum(1 for *_, levels in rows if "IV_Alpha" in levels),
        "latest_release": max((release for _, _, _, _, release, _ in rows), default=""),
        "path": target,
    }


# ---------------------------------------------------------------- 供运行期使用

class MemorySongData:
    """和上游 `songData` 同接口的内存实现，只在磁盘写不进去时兜底。

    只实现上游真正会调用的三个方法，故意保持很小。
    """

    LEVEL_NAMES = ("I", "II", "III", "IV", "IV_Alpha")

    def __init__(self, rows: list):
        self._songs = {}
        self._levels = {}
        for song_id, title, artist, duration, release, levels in rows:
            self._songs[song_id] = {
                "id": song_id, "title": title, "artist": artist,
                "duration": duration, "release": release,
            }
            self._levels[song_id] = levels

    def getAllsong_ids(self) -> list:
        return list(self._songs)

    def get_song(self, song_id: str) -> dict:
        song = self._songs.get(song_id)
        if song is None:
            return {}
        return {**song, "levels": self._levels[song_id]}

    def get_songs_rating_real_range(self, low: float, high: float) -> list:
        results = []
        for song_id, levels in self._levels.items():
            names = [
                name for name in self.LEVEL_NAMES
                if levels.get(name, {}).get("num") and low <= levels[name]["num"] <= high
            ]
            if names:
                results.append({"id": song_id, "levels": names})
        return results


def memory_database(payload: dict) -> MemorySongData:
    """不落盘的曲库，供 data/ 不可写的场景兜底。"""
    rows = normalize(payload)
    if not rows:
        raise RotaOffError("Songlist.json 解析后没有任何可用谱面。")
    return MemorySongData(rows)


def activate(instance) -> list:
    """把新的 songData 实例挂到上游两个模块上。

    上游有两条 import 路径（`rotaeno.database.song_data` 和 `database.song_data`），
    是两个不同的模块对象、两个不同的实例，必须都换掉，否则算 B40 的那条路还是旧库。
    """
    import sys

    target = sys.modules.get("rotaeno.database.song_data")
    if target is None:                       # 还没加载过就先触发加载
        import rotaeno.database.song_data    # noqa: F401
        target = sys.modules["rotaeno.database.song_data"]
    target.song_data = instance
    swapped = ["rotaeno.database.song_data"]

    alias = sys.modules.get("database.song_data")
    if alias is not None and alias is not target:
        alias.song_data = instance
        swapped.append("database.song_data")
    return swapped


def open_database(path: str):
    """把磁盘上的库包成 `songData` 实例（表结构相同，直接读）。"""
    import rotaeno.database.song_data as module

    if not os.path.isfile(path):
        raise RotaOffError(f"曲库文件不存在: {path}")
    return module.songData(path)


# ---------------------------------------------------------------- 对外一条龙

def source_path() -> str:
    """Songlist.json 的位置：先看配置里指定过没有，否则用仓库根目录那份。"""
    from .paths import BASE_DIR
    from .store import library_path

    configured = ""
    try:
        configured = library_path()
    except Exception:                     # noqa: BLE001 - 配置坏了就用默认位置
        configured = ""
    return configured or os.path.join(BASE_DIR, "Songlist.json")


def database_path() -> str:
    from .paths import DATA_DIR

    return os.path.join(DATA_DIR, "song_data.db")


def status() -> dict:
    """当前进程用的是哪份曲库（不联网、不写盘）。"""
    import sys

    module = sys.modules.get("rotaeno.database.song_data")
    instance = getattr(module, "song_data", None) if module else None
    info = {
        "source": "rotaeno/database/song_data.db（上游旧库）",
        "built": False,
        "path": "",
        "source_json": source_path(),
    }
    if instance is None:
        return info

    info.update(_stats_of(instance))
    if isinstance(instance, MemorySongData):
        info["source"] = "内存曲库（未落盘）"
        info["built"] = True
    elif os.path.isfile(database_path()) and os.path.getsize(database_path()) > 0:
        info["source"] = "data/song_data.db"
        info["path"] = database_path()
        info["built"] = True
    elif info.get("songs", 0) > 307:
        info["source"] = "运行期替换的曲库"
        info["built"] = True
    return info


def _version_key(text: str) -> list:
    """把 `2.99.0` / `2.12.1-rc` 这类版本号拆成可比较的整数列表。"""
    parts = []
    for chunk in str(text).replace("-", ".").split("."):
        parts.append(int(chunk) if chunk.isdigit() else 0)
    return parts


def update(local: bool = False, path: str = None) -> dict:
    """更新 data/song_data.db。

    local=True 时只读本地文件（不联网）；否则先自动抓，失败再回退本地文件。
    落盘失败时退回内存曲库并说明原因，不中断当前会话。
    """
    target = database_path()
    path = path or source_path()
    notes = []

    payload = None
    if not local:
        ui.info("正在从 wiki.rotaeno.cn 拉取 Songlist.json（需要先过 Anubis 反爬验证）…")
        try:
            payload = fetch_remote()
            stamp = time.strftime("%Y-%m-%d %H:%M:%S")
            notes.append(f"来源：wiki 在线抓取（{stamp}）")
        except RotaOffError as exc:
            ui.warn(str(exc))
            notes.append("在线抓取失败，回退到本地文件")

    if payload is None:
        payload = load_local(path)
        notes.append(f"来源：本地 {os.path.basename(path)}")

    try:
        stats = build_database(payload, target)
        activate(open_database(target))
    except RotaOffError as exc:
        instance = memory_database(payload)
        activate(instance)
        notes.append(str(exc))
        notes.append("已改用内存曲库，本次会话照常可用，但下次启动要重来。")
        stats = _stats_of(instance)
        stats["path"] = "(内存，未落盘)"

    stats["notes"] = notes
    return stats


def _stats_of(instance) -> dict:
    """从任意 songData 实例统计曲目/谱面/IV-α/最新版本。"""
    ids = instance.getAllsong_ids()
    ranged = instance.get_songs_rating_real_range(0, 9999)
    iv_alpha = 0
    releases = []
    for song_id in ids:
        song = instance.get_song(song_id) or {}
        levels = song.get("levels") or {}
        if "IV_Alpha" in levels:
            iv_alpha += 1
        release = song.get("release") or ""
        if release:
            releases.append(release)
    return {
        "songs": len(ids),
        "charts": sum(len(item["levels"]) for item in ranged),
        "iv_alpha": iv_alpha,
        "latest_release": max(releases, key=_version_key) if releases else "",
        "path": "",
    }


def ensure() -> dict:
    """确保当前进程用的是新曲库，返回一份说明。

    - 有 data/song_data.db 就直接用；
    - 没有则尝试用本地 Songlist.json 建一个；
    - 建不出来（目录不可写等）就用内存曲库；
    - 连 Songlist.json 都没有，就仍用上游旧库，并说明有多少谱面算不出来。
    """
    target = database_path()
    if os.path.isfile(target):
        activate(open_database(target))
        return {"path": target, "source": "data/song_data.db", "built": False}

    local = source_path()
    if not os.path.isfile(local):
        return {
            "source": "rotaeno/database/song_data.db（上游旧库，未更新）",
            "built": False,
            "hint": f"没有 {local}；执行 `library update` 或把 Songlist.json 放到仓库根目录。",
        }

    payload = load_local(local)
    try:
        build_database(payload, target)
        instance = open_database(target)
        activate(instance)
        stats = _stats_of(instance)
        stats.update({"source": os.path.basename(local), "built": True, "path": target})
        return stats
    except RotaOffError as exc:
        instance = memory_database(payload)
        activate(instance)
        stats = _stats_of(instance)
        stats.update({
            "source": f"{os.path.basename(local)}（内存曲库，未落盘）",
            "built": True,
            "warning": str(exc),
        })
        return stats
