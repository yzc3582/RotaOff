"""一次性重构：把 tui.py 按分组切成 rotaoff/tui_*.py。

用 ast 定位函数块，原样搬运（不改函数体），最后重写 tui.py 的头部与导入。
跑完即可删除本脚本。
"""

import ast

SRC = "tui.py"
src = open(SRC, encoding="utf-8").read()
tree = ast.parse(src)
lines = src.splitlines(keepends=True)
NL = "\r\n" if "\r\n" in src else "\n"


def _node(name):
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise SystemExit(f"missing: {name}")


def block(name):
    node = _node(name)
    start = (node.decorator_list[0].lineno - 1) if node.decorator_list else node.lineno - 1
    return "".join(lines[start:node.end_lineno])


IMPORTS = (
    "import os" + NL
    + "import sys" + NL
    + NL
    + "from rotaoff import data, library, output, select, store, tasks, ui" + NL
    + "from rotaoff.i18n import help_block, t" + NL
    + "from rotaoff.store import RotaOffError" + NL
)

MODULES = {
    "rotaoff/tui_common.py": (
        "TUI 公用小工具：交互提问、执行一条任务、打开路径。",
        ["_ask", "_run", "_open_path"],
        "",
    ),
    "rotaoff/tui_help.py": (
        "帮助：分组定义与帮助文本（正文在 data/i18n/*.json 的 help-* 键里）。",
        ["help_text", "cmd_help", "_want_help"],
        "GROUPS = (\"profile\", \"rotaeno\", \"task\", \"output\", \"library\")" + NL
        + "GROUP_ALIASES = {" + NL
        + "    \"rtr\": \"rotaeno\", \"r\": \"rotaeno\", \"query\": \"rotaeno\"," + NL
        + "    \"db\": \"library\"," + NL
        + "}" + NL,
    ),
    "rotaoff/tui_profile.py": (
        "profile 组：配置、字段、扫码登录。",
        ["_mask", "show_profiles", "cmd_profile", "cmd_login"],
        "",
    ),
    "rotaoff/tui_query.py": (
        "rotaeno 组（rtr / r / query）：b40 / song / status / search / custom / update。",
        ["cmd_b40", "cmd_song", "cmd_status", "cmd_search", "cmd_update", "cmd_custom"],
        "from rotaoff.tui_common import _run" + NL
        + "from rotaoff.tui_help import _want_help, help_text" + NL
        + NL + NL
        + "QUERY_COMMANDS = {" + NL
        + "    \"b40\": cmd_b40," + NL
        + "    \"song\": cmd_song," + NL
        + "    \"status\": cmd_status," + NL
        + "    \"search\": cmd_search," + NL
        + "    \"custom\": cmd_custom," + NL
        + "    \"update\": cmd_update," + NL
        + "    \"refresh\": cmd_update," + NL
        + "}" + NL,
    ),
    "rotaoff/tui_task.py": (
        "task 组：任务列表、向导、删除、执行，以及自动化间隔。",
        ["cmd_tasks", "_run_selected", "cmd_task", "wizard_add_task", "cmd_interval"],
        "from rotaoff.tui_common import _ask, _run" + NL
        + "from rotaoff.tui_help import _want_help, help_text" + NL,
    ),
    "rotaoff/tui_output.py": (
        "output 组：导出格式、文件名模板、输出目录、图片开关。",
        ["_parse_setting", "_format_setting", "_show_output_settings", "cmd_output"],
        "from rotaoff.tui_help import _want_help, help_text" + NL,
    ),
    "rotaoff/tui_library.py": (
        "library 组（db）：曲库来源、更新、换源，以及存档对不上曲库的提示。",
        ["_show_library_gaps", "_display_path", "cmd_library"],
        "from rotaoff.tui_help import _want_help, help_text" + NL,
    ),
}

moved = {}
for path, (doc, names, extra) in MODULES.items():
    body = (NL + NL).join(block(n) for n in names)
    text = f'"""{doc}"""' + NL + NL + IMPORTS + NL
    if extra:
        text += extra + NL
    text += NL + body.rstrip() + NL
    open(path, "w", encoding="utf-8", newline="").write(text)
    for name in names:
        node = _node(name)
        start = (node.decorator_list[0].lineno - 1) if node.decorator_list else node.lineno - 1
        moved[name] = (start, node.end_lineno)

# 从 tui.py 里删掉已搬走的函数（自下而上删，避免行号漂移）
for name in sorted(moved, key=lambda n: moved[n][0], reverse=True):
    start, end = moved[name]
    del lines[start:end]

text = "".join(lines)
head_start = text.index("import os")
head_end = text.index("# ---------------------------------------------------------------- 小工具")
new_head = (
    "import os" + NL
    + "import shlex" + NL
    + "import sys" + NL
    + NL
    + "from rotaoff import lock, output, store, ui" + NL
    + "from rotaoff.i18n import help_block, t" + NL
    + "from rotaoff.store import RotaOffError" + NL
    + "from rotaoff.tui_common import _run" + NL
    + "from rotaoff.tui_help import cmd_help, help_text" + NL
    + "from rotaoff.tui_library import cmd_library" + NL
    + "from rotaoff.tui_output import cmd_output" + NL
    + "from rotaoff.tui_profile import cmd_profile" + NL
    + "from rotaoff.tui_query import cmd_query" + NL
    + "from rotaoff.tui_task import cmd_task" + NL
    + NL + NL
)
text = text[:head_start] + new_head + text[head_end:]
open(SRC, "w", encoding="utf-8", newline="").write(text)
print("moved:", ", ".join(sorted(moved)))
