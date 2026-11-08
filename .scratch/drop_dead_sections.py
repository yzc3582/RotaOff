"""删掉搬代码后留下的空段头，并把连续空行压到最多两行。"""
import re

path = "tui.py"
lines = open(path, encoding="utf-8").read().splitlines()

dead = []
for i, line in enumerate(lines):
    if not line.startswith("# ---"):
        continue
    rest = [x for x in lines[i + 1:] if x.strip()]
    if not rest or rest[0].startswith("#"):
        dead.append(i)

keep = [line for i, line in enumerate(lines) if i not in dead]
text = "\n".join(keep) + "\n"
text = re.sub(r"\n{3,}", "\n\n", text)
open(path, "w", encoding="utf-8", newline="").write(text)
print(f"删除空段头 {len(dead)} 个 -> {path}")
