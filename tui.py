"""RotaOff 交互入口：配置账号 / 任务，也可以立刻查一次。

纯同步 while 循环：敲一行命令 -> 调 rotaoff.tasks -> 打印结果。
没有 asyncio，也没有任何 Discord 依赖。
"""

import shlex
import sys

from rotaoff import lock, output, store, ui
from rotaoff.store import RotaOffError
from rotaoff.tui_help import cmd_help, help_text
from rotaoff.tui_library import cmd_library
from rotaoff.tui_output import _format_setting, cmd_output
from rotaoff.tui_profile import cmd_profile
from rotaoff.tui_query import cmd_query
from rotaoff.tui_task import cmd_task

# ---------------------------------------------------------------- 主循环

COMMANDS = {
    "help": cmd_help,
    "?": cmd_help,
    "profile": cmd_profile,
    "query": cmd_query,
    "rotaeno": cmd_query,
    "rtr": cmd_query,
    "r": cmd_query,
    "task": cmd_task,
    "tasks": cmd_task,
    "output": cmd_output,
    "library": cmd_library,
    "db": cmd_library,
}

# 命令洗牌后消失的裸命令：给出新位置，而不是只说"未知命令"
MOVED_COMMANDS = {
    "b40": "r b40",
    "song": "r song <曲名>",
    "status": "r status [值]",
    "custom": "r custom [字段...]",
    "update": "r update",
    "refresh": "r update",
    "search": "r search <下限> <上限>",
    "login": "profile login",
    "interval": "task interval",
    "save": "output set export",
}

def dispatch(parts: list) -> bool:
    command, args = parts[0].lower(), parts[1:]
    if command in ("quit", "exit", "q"):
        ui.info("再见，记得休息一下眼睛。")
        return False

    handler = COMMANDS.get(command)
    if handler is None:
        moved = MOVED_COMMANDS.get(command)
        if moved:
            ui.error(f"命令已移到子命令: {moved}")
        else:
            ui.error(f"未知命令: {' '.join(parts)}（输入 help 看看）")
        return True

    try:
        handler(args)
    except RotaOffError as exc:
        ui.error(str(exc))
    except KeyboardInterrupt:
        ui.warn("已取消。")
    except Exception as exc:                      # noqa: BLE001 - 不让 TUI 整个挂掉
        ui.error(f"{type(exc).__name__}: {exc}")
    return True

def main(argv=None) -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    argv = list(sys.argv[1:] if argv is None else argv)
    lock.acquire("tui", force="--force" in argv)
    store.ensure_workspace()
    ui.banner("RotaOff", "Rotaeno 数值终端 · 无 Discord · 无异步")
    settings = output.output_settings()
    ui.info(
        f"当前配置: {store.active_profile_name()} | "
        f"图片: {'on' if settings['image'] else 'off'} | "
        f"导出: {_format_setting(settings['export'])}"
    )
    print(help_text())

    while True:
        try:
            line = input(ui.prompt("rotaoff> ")).strip()
        except (EOFError, KeyboardInterrupt):
            print()
            ui.info("再见，记得休息一下眼睛。")
            break
        if not line or line.startswith("#"):
            continue
        try:
            parts = shlex.split(line)
        except ValueError:
            ui.error("引号没闭合，再试一次。")
            continue
        if not dispatch(parts):
            break

if __name__ == "__main__":
    try:
        main()
    except RotaOffError as error:
        ui.error(str(error))
        sys.exit(1)
    except KeyboardInterrupt:
        print()
        sys.exit(130)
