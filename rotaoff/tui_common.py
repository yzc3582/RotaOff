"""TUI 公用小工具：交互提问、执行一条任务、打开路径。"""

import os
import sys

from rotaoff import data, library, output, select, store, tasks, ui
from rotaoff.i18n import help_block, t
from rotaoff.store import RotaOffError


def _ask(label: str, default: str = "") -> str:
    hint = f" [{default}]" if default else ""
    text = input(ui.prompt(f"{label}{hint}: ")).strip()
    return text or default


def _run(task: dict, report_changes: bool = True, show_table: bool = True) -> dict:
    result = tasks.run_task(task, report_changes=report_changes, show_table=show_table)
    ui.render_result(result)
    if result.get("change_summary"):
        ui.info(result["change_summary"])
    for path in result.get("files", []):
        ui.ok(f"已写入: {path}")
    return result


def _open_path(path: str) -> None:
    try:
        if os.name == "nt":
            os.startfile(path)                      # noqa: S606 - 本地文件预览
        elif sys.platform == "darwin":
            os.system(f'open "{path}"')
        else:
            os.system(f'xdg-open "{path}"')
    except Exception:
        pass
