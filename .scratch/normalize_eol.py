"""把 rotaoff/tui_*.py 的裸 LF 统一成 CRLF（仓库里其它文件都是 CRLF）。

用法：.venv\\Scripts\\python .scratch/normalize_eol.py [--check]
"""

import pathlib
import sys

TARGETS = sorted(pathlib.Path("rotaoff").glob("tui_*.py")) + [pathlib.Path("tui.py")]


def convert(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")


def main() -> int:
    check = "--check" in sys.argv
    changed = 0
    for path in TARGETS:
        raw = path.read_bytes()
        fixed = convert(raw)
        if fixed == raw:
            print(f"ok      {path}")
            continue
        changed += 1
        if check:
            print(f"杂行尾  {path}")
        else:
            path.write_bytes(fixed)
            print(f"已统一  {path}")
    print(f"共 {changed} 个文件{'待统一' if check else '已统一'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
