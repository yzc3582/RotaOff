"""探测 wiki.rotaeno.cn 的 Anubis PoW 是否可以用纯 Python 解开。"""
import hashlib
import json
import re
import sys

import requests
import urllib3

urllib3.disable_warnings()

BASE = "https://wiki.rotaeno.cn"
URL = BASE + "/%E5%AE%9A%E6%95%B0%E8%AF%A6%E8%A1%A8"  # 定数详表
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
        raw = json.loads(raw)  # 双引号包裹的字符串
    return json.loads(raw)


r = s.get(URL, timeout=30)
print("page:", r.status_code, len(r.text))
ch = challenge_of(r.text)
if ch is None:
    print("NO CHALLENGE -> already passed?")
    sys.exit(0)
print("challenge:", json.dumps(ch, ensure_ascii=False)[:300])

difficulty = ch["rules"]["difficulty"]
c = ch["challenge"]
data = c["randomData"]
print("difficulty:", difficulty, "method:", c["method"])

nonce = None
resp = None
for i in range(0, 5_000_000):
    h = hashlib.sha256(f"{data}{i}".encode()).hexdigest()
    if h.startswith("0" * difficulty):
        nonce, resp = i, h
        break
print("solved nonce:", nonce, "hash:", resp)

pass_url = f"{BASE}/.within.website/x/cmd/anubis/api/pass-challenge"
pr = s.get(
    pass_url,
    params={
        "id": c["id"],
        "response": resp,
        "nonce": nonce,
        "redir": "/定数详表",
        "elapsedTime": 1500,
    },
    timeout=30,
    allow_redirects=True,
)
print("pass:", pr.status_code, len(pr.text), dict(s.cookies))
print("still challenge?", challenge_of(pr.text) is not None)

r2 = s.get(URL, timeout=30)
print("retry:", r2.status_code, len(r2.text), "challenge?", challenge_of(r2.text) is not None)
open(".scratch/wiki_page.html", "w", encoding="utf-8").write(r2.text)
print("saved .scratch/wiki_page.html")
