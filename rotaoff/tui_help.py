"""帮助：分组定义与帮助文本（正文在 data/i18n/*.json 的 help-* 键里）。"""

import os
import sys

from rotaoff import data, library, output, select, store, tasks, ui
from rotaoff.i18n import help_block, t
from rotaoff.store import RotaOffError

GROUPS = ("profile", "query", "task", "output", "library")
GROUP_ALIASES = {
    "rotaeno": "query", "rtr": "query", "r": "query",
    "db": "library",
}


def help_text(topic: str = "") -> str:
    """按当前配置的语言给出帮助；组名可用别名，未知主题回退总览。"""
    locale = store.profile_locale()
    name = (topic or "").strip().lower()
    name = GROUP_ALIASES.get(name, name)
    if name and name not in GROUPS:
        ui.warn(t("help-unknown-topic", locale, topic=topic))
        name = ""
    return help_block(name or "overview", locale)


def cmd_help(args) -> None:
    print(help_text(" ".join(args)))


def _want_help(args) -> bool:
    """组命令后面跟 help / ? / --help，或者干脆没参数时，只打印该组帮助。"""
    return not args or args[0].lower() in ("help", "?", "-h", "--help")
