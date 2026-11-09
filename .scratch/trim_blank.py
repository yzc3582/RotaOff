"""把 docs/py-all-in-one.en_US.md 里连续 3 个以上换行压成 2 个（一次最多空一行）。

用法：.venv\\Scripts\\python .scratch/trim_blank.py <文件> [更多文件]
"""

import pathlib
import sys

B3, B2 = b"\r\n\r\n\r\n", b"\r\n\r\n"


def main() -> int:
    for name in sys.argv[1:]:
        path = pathlib.Path(name)
        raw = path.read_bytes()
        fixed = raw
        while B3 in fixed:
            fixed = fixed.replace(B3, B2)
        if fixed == raw:
            print(f"ok    {path}")
        else:
            path.write_bytes(fixed)
            print(f"已压缩 {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
