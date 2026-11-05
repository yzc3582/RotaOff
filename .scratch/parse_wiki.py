"""从 .scratch/wiki_page.html 解析定数详表，输出 .scratch/wiki_constants.json（仅用标准库）。"""
import json
import re
import sys
from html.parser import HTMLParser

sys.stdout.reconfigure(encoding="utf-8")

LEVELS = ["I", "II", "III", "IV", "IVa"]


class RowParser(HTMLParser):
    """收集每个 <tr> 内的 td 文本与首格 File:Songs_xxx.png 的 href。"""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows = []
        self._row = None
        self._td = None
        self._href = None
        self._depth = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "tr":
            self._row = {"cells": [], "songs_href": None}
            self._depth = 0
        elif tag == "td" and self._row is not None:
            self._td = []
        elif tag == "a" and self._row is not None:
            href = a.get("href") or ""
            if href.startswith("/File:Songs_") and href.endswith(".png"):
                self._row["songs_href"] = href

    def handle_endtag(self, tag):
        if tag == "td" and self._td is not None:
            self._row["cells"].append("".join(self._td).strip())
            self._td = None
        elif tag == "tr" and self._row is not None:
            self.rows.append(self._row)
            self._row = None

    def handle_data(self, data):
        if self._td is not None:
            self._td.append(data)


p = RowParser()
p.feed(open(".scratch/wiki_page.html", encoding="utf-8").read())

songs = []
for row in p.rows:
    href = row["songs_href"]
    cells = row["cells"]
    if not href or len(cells) < 6:
        continue
    sid = href[len("/File:Songs_"):-len(".png")]
    title = cells[1]
    entry = {"id": sid, "title": title, "levels": {}}
    for name, val in zip(LEVELS, cells[2:7]):
        val = val.strip()
        if val in ("", "-", "—", "N/A"):
            continue
        try:
            entry["levels"][name] = float(val)
        except ValueError:
            pass
    if entry["levels"]:
        songs.append(entry)

print("解析到曲目:", len(songs))
print("其中带 IV-α:", sum(1 for r in songs if "IVa" in r["levels"]))
print("举例:", json.dumps(songs[:2], ensure_ascii=False))

json.dump(songs, open(".scratch/wiki_constants.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("已写 .scratch/wiki_constants.json")

# 与本地曲库比对
from rotaeno.database import song_data as sd

local_ids = set(sd.song_data.getAllsong_ids())
wiki_ids = {r["id"] for r in songs}
print("本地曲库:", len(local_ids), "| wiki:", len(wiki_ids))
print("wiki 有本地没有:", len(wiki_ids - local_ids))
print("本地有 wiki 没有:", len(local_ids - wiki_ids), sorted(local_ids - wiki_ids)[:10])
