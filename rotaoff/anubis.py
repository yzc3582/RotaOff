"""wiki 的 Anubis 反爬验证：通用「会话 + 工作量证明」抓取层。

wiki.rotaeno.cn 在请求 raw 页面时会返回挑战页。流程固定为三步：

1. GET 目标页面，从 `<script id="anubis_challenge">` 里取挑战；
2. 暴力找 nonce，使 `sha256(randomData + nonce)` 有 `difficulty` 个前导 0；
3. 用**同一个 Session** 提交 `pass-challenge`（必须带 `id`），再 GET 一次。

这里只负责「拿到文本」。Songlist.json 的字段校验留在 `library.py`，
下架曲目页面以后也复用 `fetch_text()`。`rotaeno/` 仍然只读。
"""

import hashlib
import json
import re
import warnings
from urllib.parse import urlencode

import requests

from .store import RotaOffError

WIKI_BASE = "https://wiki.rotaeno.cn"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0 Safari/537.36")
MAX_POW_ITERATIONS = 5_000_000

_CHALLENGE_RE = re.compile(
    r'<script id="anubis_challenge" type="application/json">(.*?)</script>',
    re.S,
)


def new_session() -> requests.Session:
    """建一个已设置 UA / 忽略证书警告的 Session，供多次请求复用 cookie。"""
    session = requests.Session()
    session.headers["User-Agent"] = UA
    session.verify = False
    warnings.filterwarnings("ignore", message="Unverified HTTPS request")
    return session


def fetch(path: str, params: dict | None = None, timeout: int = 30,
          session: requests.Session | None = None) -> requests.Response:
    """GET 一个 wiki 页面，必要时自动通过 Anubis 挑战，返回原始响应。

    `path` 可以是相对路径（`/index.php`）或完整 URL。失败抛 `RotaOffError`。
    """
    session = session or new_session()
    target = path if path.startswith("http") else WIKI_BASE + path
    try:
        response = session.get(target, params=params, timeout=timeout)
    except requests.RequestException as exc:
        raise RotaOffError(f"连不上 wiki.rotaeno.cn: {type(exc).__name__}: {exc}") from exc

    challenge = _parse_challenge(response.text)
    if challenge is not None:
        _solve_challenge(session, challenge, redir=_redir(path, params), timeout=timeout)
        try:
            response = session.get(target, params=params, timeout=timeout)
        except requests.RequestException as exc:
            raise RotaOffError(f"通过验证后重新拉取失败: {exc}") from exc

    return response


def fetch_text(path: str, params: dict | None = None, timeout: int = 30,
               session: requests.Session | None = None) -> str:
    """同 `fetch()`，但只返回正文文本。"""
    return fetch(path, params=params, timeout=timeout, session=session).text or ""


def _redir(path: str, params: dict | None) -> str:
    """给 pass-challenge 的 `redir` 参数：验证通过后让服务器跳回原页面。"""
    if not params:
        return path
    separator = "&" if "?" in path else "?"
    return f"{path}{separator}{urlencode(params)}"


def _parse_challenge(html: str) -> dict | None:
    """从被拦截的页面里取出 Anubis 挑战；没有挑战返回 None。"""
    match = _CHALLENGE_RE.search(html or "")
    if not match:
        return None
    raw = match.group(1).strip()
    try:
        if raw.startswith('"'):
            raw = json.loads(raw)        # 内容是双引号包起来的字符串，要解两次
        return json.loads(raw)
    except ValueError:
        return None


def _solve_challenge(session: requests.Session, challenge: dict, redir: str,
                     timeout: int) -> None:
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