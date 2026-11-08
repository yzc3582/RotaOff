"""task 组：任务列表、向导、删除、执行，以及自动化间隔。"""

import os
import sys

from rotaoff import data, library, output, select, store, tasks, ui
from rotaoff.i18n import help_block, t
from rotaoff.store import RotaOffError

from rotaoff.tui_common import _ask, _run
from rotaoff.tui_help import _want_help, help_text


def _list_tasks() -> None:
    items = store.load_tasks()
    if not items:
        ui.info("还没有任务，输入 task add 创建一个。")
        return
    for index, task in enumerate(items, 1):
        print(tasks.describe_task(task, index))


def _run_selected(items: list, selected: str) -> None:
    """执行选中的任务：序号 / all / 1,3 / 4-6 / 名字，与 run_tasks.py 同一套选择规则。"""
    if selected != "all":
        items = [item for _, item in select.parse_spec(selected, items)]
    for result in tasks.run_tasks(items):
        if result.get("ok"):
            ui.render_result(result)
            for path in result.get("files", []):
                ui.ok(f"已写入: {path}")
        else:
            ui.error(f'{result["name"]}: {result["error"]}')


def cmd_task(args) -> None:
    if _want_help(args):
        print(help_text("task"))
        return
    action = args[0].lower()
    if action in ("list", "ls"):
        _list_tasks()
        return

    if action == "add":
        wizard_add_task()
        return

    if action in ("rm", "del", "delete"):
        if len(args) < 2:
            raise RotaOffError("用法: task rm <序号>")
        removed = store.remove_task(int(args[1]))
        ui.ok(t("task-removed", name=removed.get("name")))
        return

    if action == "run":
        selected = args[1] if len(args) > 1 else "all"
        _run_selected(store.load_tasks(), selected)
        return

    if action == "interval":
        cmd_interval(args[1:])
        return

    raise RotaOffError("未知 task 子命令（task help 看看）")


def wizard_add_task() -> None:
    kind = _ask(f"任务类型 ({'/'.join(tasks.TASK_TYPES)})", "custom").lower()
    fields = {}

    if kind == "custom":
        picked = _ask(f"字段（逗号分隔，可选 {'/'.join(data.CUSTOM_LABELS)}）", "rating")
        fields["fields"] = [item for item in picked.replace(" ", ",").split(",") if item]
        layout = _ask("每行模板（{label} / {value}，留空 = {label}: {value}）")
        if layout:
            fields["layout"] = layout
    elif kind == "song_info":
        fields["song_alias"] = _ask("曲名或别名", "")
    elif kind == "song_status":
        fields["status"] = _ask(f"状态 ({'/'.join(tasks.SONG_STATUSES)})", "FC")
    elif kind == "song_rtr":
        fields["level_min"] = _ask("定数下限", "14.0")
        fields["level_max"] = _ask("定数上限", "15.0")
        fields["sort"] = _ask("排序 (rating/score/level)", "rating")

    name = _ask("任务名", fields.get("song_alias") or kind)
    export = _ask("导出格式 (txt/md/csv/json，逗号分隔，留空 = 这条任务不导出)", "")
    template = _ask("文件名模板（可用 {type} {name} {profile} {stamp}，留空 = 用 output 设置）", "")
    image = _ask("同时生成图片? (y/N)", "n").lower().startswith("y")
    strict = _ask("定数缺失时直接报错? (y/N)", "n").lower().startswith("y")

    task = tasks.build_task(
        kind,
        name=name,
        export=[item for item in export.replace(" ", ",").split(",") if item],
        template=template,
        image=image,
        strict=strict,
        **fields,
    )
    store.add_task(task)
    ui.ok(t("task-added", name=task["name"]))
    print(tasks.describe_task(task))


def cmd_interval(args) -> None:
    if not args:
        seconds = store.load_config().get("schedule", {}).get("interval", 0)
        ui.info(f"自动化间隔: {seconds} 秒（0 = 只跑一次）")
        return
    schedule = store.set_schedule_interval(int(args[0]))
    ui.ok(f"自动化间隔已保存: {schedule['interval']} 秒")
