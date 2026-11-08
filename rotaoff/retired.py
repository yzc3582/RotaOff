"""限时上架曲目列表：现场获取 → 清洗 → 存储，并供上游 Best40 使用。

数据来源是 wiki 的「限时上架曲目列表」页（`wiki/` 不入库）：

    https://wiki.rotaeno.cn/index.php?title=限时上架曲目列表&action=raw

页面里有两张表：「已下架曲目」和「在售的限时上架曲目」。每条记录 5 列，
曲名在第 2 列、时间在第 5 列，曲绘文件名里带曲目 ID：

    | [[file:Songs rokutyounen.png|100px]]
    | -{[[六兆年と一夜物語]]}-
    | 2025/05/30 - 2026/06/30<ref name="delayed-date-1">…</ref>

`sync()` 把两张表都写进 `data/retired_songs.db`（与上游 `RetiredSongs` 同 schema），
由 `rotaoff.patch.redirect_retired_songs()` 注入上游实例；`get_best40` 再按
`end_date <= 今天` 把已下架曲目排除。上游仓库自带的
`rotaeno/database/retired_songs.db` 只作为首次启动的种子。
"""

import html
import os
import re
import sqlite3
from datetime import date

from .i18n import DEFAULT_LOCALE, t
from .store import RotaOffError

PAGE = "限时上架曲目列表"

_REF_RE = re.compile(r"<ref[^>]*/>|<ref[^>]*>.*?</ref>", re.S)
_LINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_IMAGE_RE = re.compile(r"file:Songs\s+([^.|]+)\.png", re.I)
_TIME_RE = re.compile(
    r"(\d{4})/(\d{1,2})/(\d{1,2})\s*[-–—]\s*(\d{4})/(\d{1,2})/(\d{1,2})"
)
_SECTION_END_RE = re.compile(r"^==[^=].*==\s*$", re.M)
_ROW_SPLIT_RE = re.compile(r"^\s*\|-\s*$", re.M)


def clean_title(raw: str) -> str:
    """去掉 wiki 修饰：`-{…}-`、`[[…]]`、`<ref>`、HTML 标签与实体。"""
    text = _REF_RE.sub("", raw or "")
    text = text.replace("-{", "").replace("}-", "")
    text = _LINK_RE.sub(lambda match: match.group(2) or match.group(1), text)
    text = _HTML_TAG_RE.sub("", text)
    text = html.unescape(text)
    return " ".join(text.split()).strip()


def _section_body(text: str, heading: str) -> str:
    pattern = re.compile(r"^==\s*" + re.escape(heading) + r"\s*==\s*$", re.M)
    match = pattern.search(text or "")
    if not match:
        return ""
    rest = text[match.end():]
    end = _SECTION_END_RE.search(rest)
    return rest[:end.start()] if end else rest


def _records_from_body(body: str, with_id: bool) -> list:
    records = []
    for block in _ROW_SPLIT_RE.split(body)[1:]:
        cells = [
            line[1:].strip()
            for line in block.splitlines()
            if line.startswith("|") and not line.startswith("|}")
        ]
        if len(cells) < 5:
            continue
        title = clean_title(cells[1])
        time_match = _TIME_RE.search(_REF_RE.sub("", cells[4]))
        if not title or not time_match:
            continue
        year1, month1, day1, year2, month2, day2 = (int(part) for part in time_match.groups())
        record = {
            "title": title,
            "start": date(year1, month1, day1).isoformat(),
            "end": date(year2, month2, day2).isoformat(),
        }
        if with_id:
            image = _IMAGE_RE.search(cells[0])
            record["id"] = image.group(1).strip() if image else ""
        records.append(record)
    return records


def parse(text: str) -> list:
    """只解析「已下架曲目」表；返回 [{title, start, end}]。"""
    return _records_from_body(_section_body(text, "已下架曲目"), with_id=False)


def parse_all(text: str) -> list:
    """解析「已下架」+「在售」两张表；返回 [{id, title, start, end}]。"""
    records = _records_from_body(_section_body(text, "已下架曲目"), with_id=True)
    records += _records_from_body(_section_body(text, "在售的限时上架曲目"), with_id=True)
    return records


def local_path() -> str:
    from .paths import BASE_DIR

    return os.path.join(BASE_DIR, "wiki", "限时上架曲目列表.txt")


def read_local(path: str | None = None) -> str:
    with open(path or local_path(), encoding="utf-8") as handle:
        return handle.read()


def load(path: str | None = None) -> list:
    """读本地那份 wiki 文本并解析「已下架曲目」表。"""
    return parse(read_local(path))


def due(records: list, today: date | None = None) -> list:
    """筛出「下架日期 <= 今天」的记录（含下架当天）。"""
    today = today or date.today()
    return [record for record in records if date.fromisoformat(record["end"]) <= today]


def database_path() -> str:
    from .paths import DATA_DIR

    return os.path.join(DATA_DIR, "retired_songs.db")


def _relative(path: str) -> str:
    from .paths import BASE_DIR

    try:
        relative = os.path.relpath(path, BASE_DIR)
    except ValueError:
        return path
    return path if relative.startswith("..") else relative.replace(os.sep, "/")


def db_count() -> int:
    path = database_path()
    if not os.path.isfile(path):
        return 0
    connection = sqlite3.connect(path)
    try:
        return int(connection.execute("SELECT COUNT(*) FROM retired_songs").fetchone()[0])
    except sqlite3.Error:
        return 0
    finally:
        connection.close()


def summary(today: date | None = None) -> dict:
    """下架曲列表的来源、路径与条数（不联网，供 `library` 展示）。"""
    text = local_path()
    count = db_count()
    if count == 0:
        try:
            count = len(parse_all(read_local(text)))
        except OSError:
            count = 0
    ids, _, _ = status(today)
    return {
        "url": f"https://wiki.rotaeno.cn/index.php?title={PAGE}&action=raw",
        "text": _relative(text),
        "db": _relative(database_path()),
        "count": count,
        "due": len(ids),
    }


def _write_db(records: list, path: str, locale: str = DEFAULT_LOCALE) -> int:
    rows = [
        (record["id"], record["title"], record["start"], record["end"])
        for record in records
        if record.get("id")
    ]
    if not rows:
        raise RotaOffError(t("retired-no-ids", locale))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    connection = sqlite3.connect(path)
    try:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS retired_songs ("
            "id VARCHAR PRIMARY KEY, title VARCHAR NOT NULL, "
            "start_date VARCHAR NOT NULL, end_date VARCHAR NOT NULL)"
        )
        connection.execute("DELETE FROM retired_songs")
        connection.executemany(
            "INSERT INTO retired_songs (id, title, start_date, end_date) VALUES (?, ?, ?, ?)",
            rows,
        )
        connection.commit()
    finally:
        connection.close()
    return len(rows)


def sync(text: str | None = None, path: str | None = None, timeout: int = 30,
         locale: str = DEFAULT_LOCALE) -> dict:
    """现场抓 wiki → 清洗两张表 → 覆盖写 `data/retired_songs.db`。

    远程失败时回退本地 `wiki/限时上架曲目列表.txt`；两边都失败才抛错。
    """
    warning = ""
    source = t("retired-source-text", locale)
    if text is None:
        from . import anubis

        try:
            text = anubis.fetch_text(
                "/index.php", {"title": PAGE, "action": "raw"}, timeout=timeout
            )
            source = t("retired-source-online", locale)
        except Exception as exc:             # noqa: BLE001 - 在线失败要能回退
            warning = t("retired-fetch-failed", locale, error=exc)

    if text is None:
        try:
            text = read_local()
            source = t("retired-source-local", locale, name=os.path.basename(local_path()))
        except OSError as exc:
            raise RotaOffError(t("retired-no-list", locale, error=exc)) from exc

    records = parse_all(text)
    if not records:
        raise RotaOffError(t("retired-empty", locale))

    target = path or database_path()
    written = _write_db(records, target, locale)
    missing = [record["title"] for record in records if not record.get("id")]
    return {
        "count": written,
        "path": target,
        "text": _relative(local_path()),
        "db": _relative(target),
        "url": f"https://wiki.rotaeno.cn/index.php?title={PAGE}&action=raw",
        "source": source,
        "warning": warning,
        "missing": missing,
    }


def _normalize(title: str) -> str:
    return "".join(ch for ch in str(title).casefold() if not ch.isspace())


def match(records: list, songs) -> tuple:
    """按曲名把记录对到曲库；`songs` 是 (song_id, title) 的可迭代对象。

    返回 `(matched_ids, missing_titles)`。匹配不上不静默丢弃，交给调用方提示。
    """
    by_title = {}
    for song_id, title in songs:
        by_title.setdefault(_normalize(title), set()).add(song_id)
    matched, missing = set(), []
    for record in records:
        ids = by_title.get(_normalize(record["title"]))
        if ids:
            matched.update(ids)
        else:
            missing.append(record["title"])
    return matched, missing


def status(today: date | None = None) -> tuple:
    """返回 `(已下架曲目 ID 集合, 未匹配曲名, 错误信息)`。

    优先读注入后的上游 `retired_songs` 实例（`data/retired_songs.db`）；
    db 里没有已下架曲目时，回退本地 wiki 文本 + 曲名匹配。
    """
    try:
        import rotaeno

        instance = rotaeno.database.retired_songs.retired_songs
        ids = set(instance.get_retired_ids(today))
        if ids:
            return ids, [], ""
    except Exception:                    # noqa: BLE001 - db 未注入时走回退
        pass

    try:
        records = due(load(), today)
    except OSError as exc:
        return set(), [], f"读不到限时上架曲目列表: {exc}"

    try:
        import rotaeno

        instance = rotaeno.database.song_data.song_data
        songs = [
            (song_id, (instance.get_song(song_id) or {}).get("title", ""))
            for song_id in instance.getAllsong_ids()
        ]
    except Exception as exc:             # noqa: BLE001 - 曲库没准备好时不能拦死查询
        return set(), [], f"曲库不可用，无法匹配下架曲目: {exc}"

    matched, missing = match(records, songs)
    return matched, missing, ""