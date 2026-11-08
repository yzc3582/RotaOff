"""限时上架曲目列表的清洗：把 wiki 表格文本变成结构化记录。

数据源是 wiki 的「已下架曲目」表（`wiki/限时上架曲目列表.txt`，运行时抓取，
`wiki/` 不入库）。这里只做**解析与曲名匹配**，不碰 Rating / B40；
真正的「排除出 B40」等下一阶段再接。

表格里每条记录长这样（5 列，曲名在第 2 列，时间在第 5 列）：

    |-
    | [[file:Songs xxx.png|100px]]
    | -{[[六兆年と一夜物語]]}-
    | [[向未来之声]]
    | {{link|曲师|kemu}}
    | 2025/05/30 - 2026/06/30<ref name="delayed-date-1">…</ref>

只解析 `== 已下架曲目 ==` 这一节；「在售的限时上架曲目」即使写了未来下架日期也不能排除。
"""

import html
import os
import re
from datetime import date

_REF_RE = re.compile(r"<ref[^>]*/>|<ref[^>]*>.*?</ref>", re.S)
_LINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_TIME_RE = re.compile(
    r"(\d{4})/(\d{1,2})/(\d{1,2})\s*[-–—]\s*(\d{4})/(\d{1,2})/(\d{1,2})"
)
_SECTION_RE = re.compile(r"^==\s*已下架曲目\s*==\s*$", re.M)
_NEXT_SECTION_RE = re.compile(r"^==[^=].*==\s*$", re.M)
_ROW_SPLIT_RE = re.compile(r"^\s*\|-\s*$", re.M)


def clean_title(raw: str) -> str:
    """去掉 wiki 修饰：`-{…}-`、`[[…]]`、`<ref>`、HTML 标签与实体。"""
    text = _REF_RE.sub("", raw or "")
    text = text.replace("-{", "").replace("}-", "")
    text = _LINK_RE.sub(lambda match: match.group(2) or match.group(1), text)
    text = _HTML_TAG_RE.sub("", text)
    text = html.unescape(text)
    return " ".join(text.split()).strip()


def parse(text: str) -> list:
    """解析「已下架曲目」表；返回 [{title, start, end}]，日期是 ISO 字符串。"""
    match = _SECTION_RE.search(text or "")
    if not match:
        return []
    rest = text[match.end():]
    next_match = _NEXT_SECTION_RE.search(rest)
    if next_match:
        rest = rest[:next_match.start()]

    records = []
    for block in _ROW_SPLIT_RE.split(rest)[1:]:
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
        records.append({
            "title": title,
            "start": date(year1, month1, day1).isoformat(),
            "end": date(year2, month2, day2).isoformat(),
        })
    return records


def load(path: str | None = None) -> list:
    """读本地那份 wiki 文本；默认找仓库根目录的 `wiki/限时上架曲目列表.txt`。"""
    if path is None:
        from .paths import BASE_DIR

        path = os.path.join(BASE_DIR, "wiki", "限时上架曲目列表.txt")
    with open(path, encoding="utf-8") as handle:
        return parse(handle.read())


def due(records: list, today: date | None = None) -> list:
    """筛出「下架日期 <= 今天」的记录（含下架当天）。"""
    today = today or date.today()
    return [record for record in records if date.fromisoformat(record["end"]) <= today]


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