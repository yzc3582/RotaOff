"""试试能不能纯 Python 自动拿到 Template:Songlist.json（省掉手动复制）。"""
import hashlib
import json
import re
import sys

import requests
import urllib3

sys.stdout.reconfigure(encoding="utf-8")
urllib3.disable_warnings()

BASE = "https://wiki.rotaeno.cn"
RAW = BASE + "/index.php"  # ?title=Template:Songlist.json&action=raw
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"

s = requests.Session()
s.headers["User-Agent"] = UA
s.verify = False


def challenge_of(html):
    m = re.search(r'<script id="anubis_challenge" type="application/json">(.*?)</script>', html, re.S)
    if not m:
        return None
    raw = m.group(1).strip()
    if raw.startswith('"'):
        raw = json.loads(raw)
    return json.loads(raw)


def solve(ch, redir):
    difficulty = ch["rules"]["difficulty"]
    c = ch["challenge"]
    data = c["randomData"]
    nonce = resp = None
    for i in range(0, 5_000_000):
        h = hashlib.sha256(f"{data}{i}".encode()).hexdigest()
        if h.startswith("0" * difficulty):
            nonce, resp = i, h
            break
    url = f"{BASE}/.within.website/x/cmd/anubis/api/pass-challenge"
    pr = s.get(url, params={"id": c["id"], "response": resp, "nonce": nonce,
                            "redir": redir, "elapsedTime": 1500}, timeout=30)
    return pr


target = RAW
params = {"title": "Template:Songlist.json", "action": "raw"}
r = s.get(target, params=params, timeout=30)
print("first:", r.status_code, len(r.text), r.headers.get("content-type"))

ch = challenge_of(r.text)
if ch is None:
    print("no challenge on raw endpoint; body head:", r.text[:200])
else:
    print("challenge difficulty:", ch["rules"]["difficulty"])
    pr = solve(ch, "/index.php?title=Template:Songlist.json&action=raw")
    print("pass-challenge:", pr.status_code, len(pr.text))
    r2 = s.get(target, params=params, timeout=30)
    print("second:", r2.status_code, len(r2.text), r2.headers.get("content-type"))
    body = r2.text.strip()
    print("head:", body[:200])
    if body.startswith("{"):
        d = json.loads(body)
        print("JSON OK songs:", len(d.get("songs", [])), "packs:", len(d.get("packs", [])))
        open(".scratch/songlist_fetched.json", "w", encoding="utf-8").write(body)
        print("saved .scratch/songlist_fetched.json")
