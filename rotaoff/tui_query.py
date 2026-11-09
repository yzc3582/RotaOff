"""rotaeno 组（rtr / r / query）：b40 / song / status / search / custom / update。"""

import os
import sys

from rotaoff import data, library, output, select, store, tasks, ui
from rotaoff.i18n import help_block, t
from rotaoff.store import RotaOffError

from rotaoff.tui_common import _run
from rotaoff.tui_help import _want_help, help_text


def cmd_b40(args) -> None:
    # 不要在这里传 template：文件名模板统一由 `output set template` 决定，
    # 传了会覆盖全局设置，导致 txt/md 永远叫 b40.txt。
    _run(tasks.build_task("b40", name="Best40"))


def cmd_song(args) -> None:
    alias = " ".join(args).strip()
    if not alias:
        raise RotaOffError("用法: song <曲名或别名>")
    _run(tasks.build_task("song_info", name=alias, song_alias=alias))


def cmd_status(args) -> None:
    status = (args[0] if args else "FC").upper()
    _run(tasks.build_task("song_status", name=f"状态 {status}", status=status))


def cmd_search(args) -> None:
    if len(args) < 2:
        raise RotaOffError("用法: r search <下限> <上限> [rating|score|level]")
    sort = (args[2] if len(args) > 2 else "rating").lower()
    _run(tasks.build_task(
        "song_rtr",
        name=f"等级 {args[0]}~{args[1]}",
        level_min=args[0],
        level_max=args[1],
        sort=sort,
    ))


def cmd_update(args) -> None:
    """单独下载一次云存档并报告与上次的差异。

    QQ 端 `/r update` 的轻量等价物：只跑「下载 + 对比」，不引入读缓存，
    其它命令照旧每次实时取数。数据没变时不会报出变化的条目。
    """
    _run(tasks.build_task(
        "custom",
        name="Update",
        fields=["cloud_updated_at", "fetched_at", "rating_diff", "songs_diff"],
        layout="{label}: {value}",
    ), report_changes=False, show_table=False)


def cmd_custom(args) -> None:
    fields = [item.lower() for item in args] or ["rating"]
    _run(tasks.build_task("custom", name="自定义", fields=fields))


QUERY_COMMANDS = {
    "b40": cmd_b40,
    "song": cmd_song,
    "status": cmd_status,
    "search": cmd_search,
    "custom": cmd_custom,
    "update": cmd_update,
    "refresh": cmd_update,
}


def cmd_query(args) -> None:
    """query 组（别名 rotaeno / rtr / r）：查询。不带子命令或带 help 只出帮助。"""
    if _want_help(args):
        print(help_text("query"))
        return
    action, rest = args[0].lower(), args[1:]
    handler = QUERY_COMMANDS.get(action)
    if handler is None:
        raise RotaOffError(f"未知查询: {action}（help query 看看）")
    handler(rest)
