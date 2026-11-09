"""抓 wiki 的 Completion 页原文，存成 wiki/Completion.txt（数据不入库）。

用法：.venv\\Scripts\\python .scratch\\fetch_completion.py
"""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from rotaoff import anubis

TARGET = pathlib.Path("wiki/Completion.txt")


def main() -> int:
    text = anubis.fetch_text("/index.php", {"title": "Completion", "action": "raw"})
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(text, encoding="utf-8", newline="")
    print(f"{len(text)} chars -> {TARGET}")
    print("-" * 50)
    print(text[:1200])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
