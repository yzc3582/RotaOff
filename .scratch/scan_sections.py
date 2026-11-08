"""找出搬代码后剩下的空段头（后面紧跟空行/另一个段头/文件尾）。"""
import glob

for path in ["tui.py"] + sorted(glob.glob("rotaoff/tui_*.py")):
    lines = open(path, encoding="utf-8").read().splitlines()
    dead = []
    for i, line in enumerate(lines):
        if not line.startswith("# ---"):
            continue
        rest = [x for x in lines[i + 1:] if x.strip()]
        nxt = rest[0] if rest else ""
        if nxt.startswith("# ---") or not nxt.startswith(("def ", "class ", "#")):
            dead.append(i + 1)
    print(f"{path}: {len(lines)} 行, 空段头行号 {dead}")
