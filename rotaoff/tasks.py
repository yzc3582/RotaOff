"""任务层：构造、校验、执行任务。

一条任务就是 data/tasks.json 里的一小段 dict，例如：

    {"name": "OBS Rating", "type": "custom", "profile": "default",
     "fields": ["rating", "level", "completion"], "layout": "{value}",
     "export": ["txt"], "template": "rating"}

公共可选字段：limit / image / export / template / strict / record_history
"""

import time
from typing import cast

import rotaeno

from . import data, output, ui
from .store import (
    RotaOffError,
    active_profile_name,
    load_users,
    profile_locale,
    require_ready_profile,
    t,
)

SONG_STATUSES = ("NONE", "FC", "AP", "APP", "CLEAR", "NOTCLEAR", "FAVORITE", "NOTFAVORITE")
SORT_TYPES = ("rating", "score", "level")

# 定数上界的默认值 = “不设上限”。
# 1145 是沿用上游 rotaeno.processor.get_song_rtr 的默认参数，
# 也是原作者 None1145 的彩蛋；rotaeno/ 目录保持只读，所以这个数只在 rotaoff/ 里出现。
LEVEL_MAX_UNBOUNDED = 1145


def _check_diff(song_datas: list, task: dict, locale: str) -> list:
    """定数缺失的谱面不能用来算 Rating：默认跳过并警告，strict 时直接报错。"""
    missing = data.charts_without_diff(song_datas)
    if not missing:
        return song_datas
    names = ", ".join(str(item.get("title") or data.NO_DATA) for item in missing[:5])
    if task.get("strict"):
        raise RotaOffError(t("chart-diff-missing", locale, count=len(missing), songs=names))
    ui.warn(t("chart-diff-missing-warning", locale, count=len(missing), songs=names))
    return [item for item in song_datas if item.get("diff")]


def _profile_name(task: dict) -> str:
    """任务里存的配置名；如果那个配置已经被删/改名，回退到当前配置并提示一句。

    任务是在建任务那一刻把 profile 名字写死的，所以 `profile new/use` 换档之后，
    老任务会指向一个不存在的名字。这里不静默失败，也不让整条任务挂掉。
    """
    name = task.get("profile") or active_profile_name()
    if name in load_users():
        return name
    fallback = active_profile_name()
    if fallback in load_users():
        ui.warn(f"任务里的配置 `{name}` 已不存在，改用当前配置 `{fallback}`")
        return fallback
    raise RotaOffError(t("profile-not-found", profile=name))


def _ranked(snapshot: dict, task: dict, locale: str) -> list:
    song_datas = _check_diff(snapshot.get("songDatas") or [], task, locale)
    limit = int(task.get("limit", 40))
    return sorted(song_datas, key=lambda item: item.get("ratingMix", 0), reverse=True)[:limit]


def _task_custom(task: dict, render_image: bool) -> dict:
    """自定义字段：username / rating / level / completion / b40 ..."""
    profile_name = _profile_name(task)
    locale = profile_locale(profile_name)
    snapshot = data.fetch_snapshot(
        profile_name, record_history=bool(task.get("record_history", False))
    )
    metrics = data.metrics_from(snapshot)

    fields = list(dict.fromkeys(str(field).lower() for field in task.get("fields") or ["rating"]))
    unknown = [field for field in fields if field not in metrics and field != "b40"]
    if unknown:
        raise RotaOffError(t("custom-field-unknown", locale, field=", ".join(unknown)))

    layout = task.get("layout") or "{label}: {value}"
    summary = [
        layout.replace("{label}", data.CUSTOM_LABELS.get(field, field)).replace(
            "{value}", metrics[field]
        )
        for field in fields
        if field in metrics
    ]

    if "b40" in fields:
        columns = list(data.B40_COLUMNS)
        aligns = list(data.B40_ALIGNS)
        rows = data.best40_rows(_ranked(snapshot, task, locale))
    else:
        columns = ["字段", "值"]
        aligns = ["left", "left"]
        rows = [
            [data.CUSTOM_LABELS.get(field, field), metrics[field]]
            for field in fields
            if field in metrics
        ]

    image = ""
    if render_image:
        image = output.try_render_image(
            lambda: rotaeno.processor.get_best40(require_ready_profile(profile_name)),
            f"custom-{profile_name}",
        )
    return {
        "title": "自定义内容",
        "columns": columns,
        "rows": rows,
        "aligns": aligns,
        "summary": summary,
        "profile": profile_name,
        "raw": metrics,
        "image": image,
        "change_summary": data.change_summary(snapshot),
    }


def _task_b40(task: dict, render_image: bool) -> dict:
    profile_name = _profile_name(task)
    locale = profile_locale(profile_name)
    snapshot = data.fetch_snapshot(
        profile_name, record_history=bool(task.get("record_history", False))
    )

    image = ""
    if render_image:
        image = output.try_render_image(
            lambda: rotaeno.processor.get_best40(require_ready_profile(profile_name)),
            f"b40-{profile_name}",
        )
    return {
        "title": "Best40",
        "columns": list(data.B40_COLUMNS),
        "rows": data.best40_rows(_ranked(snapshot, task, locale)),
        "aligns": list(data.B40_ALIGNS),
        "summary": data.profile_summary(snapshot),
        "profile": profile_name,
        "raw": snapshot,
        "image": image,
        "change_summary": data.change_summary(snapshot),
    }


def _task_song_info(task: dict, render_image: bool) -> dict:
    profile_name = _profile_name(task)
    locale = profile_locale(profile_name)
    alias = str(task.get("song_alias") or "").strip()
    if not alias:
        raise RotaOffError(t("task-song-alias-required", locale))
    song_id = data.find_song_id(alias)
    if not song_id:
        raise RotaOffError(t("song-alias-not-found", locale, song_alias=alias))

    profile = require_ready_profile(profile_name)
    song_data = data.quiet_call(rotaeno.processor.get_song, profile, song_id=song_id, just_data=True)
    if not song_data:
        raise RotaOffError(t("task-no-song-data", locale, song_alias=alias))

    samples = sorted(song_data.items(), key=lambda pair: pair[1].get("diff", 0), reverse=True)
    rows = [
        [
            level,
            f'{item.get("diff", 0):.1f}',
            f'{item.get("score", 0):,}',
            f'{item.get("rating", 0):.2f}',
            f'{item.get("nextPointScore", 0):.0f}',
            data.display_status(item),
        ]
        for level, item in samples
    ]
    first = samples[0][1]
    summary = [f'{first.get("title") or alias}  |  {first.get("artist") or data.NO_DATA}']

    image = ""
    if render_image:
        image = output.try_render_image(
            lambda: rotaeno.processor.get_song(profile, song_id=song_id),
            f"song-{profile_name}",
        )
    return {
        "title": "单曲信息",
        "columns": ["难度", "定数", "分数", "Rating", "到下一分", "状态"],
        "rows": rows,
        "aligns": ["center", "right", "right", "right", "right", "center"],
        "summary": summary,
        "profile": profile_name,
        "raw": song_data,
        "image": image,
    }


def _task_song_status(task: dict, render_image: bool) -> dict:
    profile_name = _profile_name(task)
    locale = profile_locale(profile_name)
    status = str(task.get("status") or "FC").upper()
    if status not in SONG_STATUSES:
        raise RotaOffError(t("unavailable-song-status", locale, song_status=status))

    profile = require_ready_profile(profile_name)
    song_datas = cast(
        list,
        data.quiet_call(
            rotaeno.processor.get_song_status, profile, song_status=status, just_data=True
        ),
    )
    song_datas = _check_diff(song_datas, task, locale)
    rows = [
        [
            str(item.get("title") or data.NO_DATA),
            str(item.get("level") or data.NO_DATA),
            f'{item.get("diff", 0):.1f}',
            f'{item.get("score", 0):,}',
            f'{item.get("ratingMix", 0):.2f}',
            data.display_status(item),
        ]
        for item in song_datas
    ]

    image = ""
    if render_image:
        image = output.try_render_image(
            lambda: rotaeno.processor.get_song_status(profile, song_status=status),
            f"status-{profile_name}",
        )
    return {
        "title": f"歌曲状态 {status}",
        "columns": ["曲目", "难度", "定数", "分数", "Rating", "状态"],
        "rows": rows,
        "aligns": ["left", "center", "right", "right", "right", "center"],
        "summary": [t("task-summary-count", locale, count=len(song_datas))],
        "profile": profile_name,
        "raw": song_datas,
        "image": image,
    }


def _task_song_rtr(task: dict, render_image: bool) -> dict:
    profile_name = _profile_name(task)
    locale = profile_locale(profile_name)
    try:
        low = float(task.get("level_min", 12.5))
        high = float(task.get("level_max", LEVEL_MAX_UNBOUNDED))
    except (TypeError, ValueError):
        raise RotaOffError(t("invalid-song-level-num-range", locale, song_level_num_range=task))
    low, high = min(low, high), max(low, high)

    sort = str(task.get("sort") or "rating").lower()
    if sort not in SORT_TYPES:
        raise RotaOffError(t("unavailable-song-sort-type", locale, song_sort_type=sort))
    span = f"≥{low:g}" if high >= LEVEL_MAX_UNBOUNDED else f"{low:g} ~ {high:g}"

    profile = require_ready_profile(profile_name)
    song_datas = cast(
        list,
        data.quiet_call(
            rotaeno.processor.get_song_rtr,
            profile,
            song_level_num_range=(low, high),
            song_sort_type=sort,
            just_data=True,
        ),
    )
    song_datas = _check_diff(song_datas, task, locale)
    rows = [
        [
            str(item.get("title") or data.NO_DATA),
            str(item.get("level") or data.NO_DATA),
            f'{item.get("diff", 0):.1f}',
            f'{item.get("ratingMix", 0):.2f}',
            f'{item.get("score", 0):,}',
        ]
        for item in song_datas
    ]

    image = ""
    if render_image:
        image = output.try_render_image(
            lambda: rotaeno.processor.get_song_rtr(
                profile, song_level_num_range=(low, high), song_sort_type=sort
            ),
            f"rtr-{profile_name}",
        )
    return {
        "title": f"等级 {span} · 按 {sort}",
        "columns": ["曲目", "难度", "定数", "Rating", "分数"],
        "rows": rows,
        "aligns": ["left", "center", "right", "right", "right"],
        "summary": [t("task-summary-count", locale, count=len(song_datas))],
        "limit": int(task.get("limit", 30)),
        "profile": profile_name,
        "raw": song_datas,
        "image": image,
    }


# ---------------------------------------------------------------- 任务注册与校验
TASK_BUILDERS = {
    "custom": _task_custom,
    "b40": _task_b40,
    "song_info": _task_song_info,
    "song_status": _task_song_status,
    "song_rtr": _task_song_rtr,
}

TASK_TYPES = tuple(TASK_BUILDERS)


def build_task(kind: str, name: str = "", profile: str = "", **fields) -> dict:
    """校验参数并生成一条任务描述（就是写进 data/tasks.json 的那种）。"""
    kind = (kind or "").strip().lower()
    if kind not in TASK_BUILDERS:
        raise RotaOffError(t("task-type-unknown", task_type=kind))

    profile = profile or active_profile_name()
    if profile not in load_users():
        raise RotaOffError(t("profile-not-found", profile=profile))

    task = {"name": name or kind, "type": kind, "profile": profile}
    if fields.get("export") is not None:
        chosen = [str(item).lower() for item in fields["export"]]
        task["export"] = [item for item in chosen if item in output.EXPORT_FORMATS]
    if fields.get("image") is not None:
        task["image"] = bool(fields["image"])
    if fields.get("strict") is not None:
        task["strict"] = bool(fields["strict"])
    if fields.get("template"):
        task["template"] = str(fields["template"])
    if fields.get("limit"):
        task["limit"] = max(int(fields["limit"]), 1)

    if kind == "custom":
        picked = [str(item).lower() for item in fields.get("fields") or ["rating"]]
        unknown = [item for item in picked if item not in data.CUSTOM_LABELS]
        if unknown:
            raise RotaOffError(t("custom-field-unknown", field=", ".join(unknown)))
        task["fields"] = list(dict.fromkeys(picked))   # 去重但保留顺序
        if fields.get("layout"):
            task["layout"] = str(fields["layout"])
    elif kind == "song_info":
        alias = str(fields.get("song_alias") or "").strip()
        if not alias:
            raise RotaOffError(t("task-song-alias-required"))
        if not data.find_song_id(alias):
            raise RotaOffError(t("song-alias-not-found", song_alias=alias))
        task["song_alias"] = alias
    elif kind == "song_status":
        status = str(fields.get("status") or "FC").upper()
        if status not in SONG_STATUSES:
            raise RotaOffError(t("unavailable-song-status", song_status=status))
        task["status"] = status
    elif kind == "song_rtr":
        try:
            low = float(fields.get("level_min", 12.5))
            high = float(fields.get("level_max", LEVEL_MAX_UNBOUNDED))
        except (TypeError, ValueError):
            raise RotaOffError(t("invalid-song-level-num-range", song_level_num_range=fields))
        task["level_min"], task["level_max"] = min(low, high), max(low, high)
        sort = str(fields.get("sort") or "rating").lower()
        if sort not in SORT_TYPES:
            raise RotaOffError(t("unavailable-song-sort-type", song_sort_type=sort))
        task["sort"] = sort
    return task


def describe_task(task: dict, index: int = 0) -> str:
    """一行摘要，给 TUI 列表和 --list 用。"""
    kind = str(task.get("type") or "?")
    if kind == "custom":
        detail = ",".join(task.get("fields") or ["rating"])
    elif kind == "song_info":
        detail = str(task.get("song_alias") or "")
    elif kind == "song_status":
        detail = str(task.get("status") or "")
    elif kind == "song_rtr":
        low = task.get("level_min", 12.5)
        high = task.get("level_max", LEVEL_MAX_UNBOUNDED)
        try:
            if float(high) >= LEVEL_MAX_UNBOUNDED:
                span = f"{float(low):g}+"
            else:
                span = f"{float(low):g}~{float(high):g}"
        except (TypeError, ValueError):
            span = f"{low}~{high}"
        detail = f'{span}/{task.get("sort", "rating")}'
    else:
        detail = ""
    export = ",".join(task.get("export") or [])
    head = f"{index:>2}. " if index else "    "
    tail = f"  [{export}]" if export else ""
    return f'{head}[{kind}] {task.get("name") or "(未命名)"}  {detail}{tail}'.rstrip()


def run_task(task: dict, render_image: bool | None = None, formats=None,
             report_changes: bool = True) -> dict:
    """执行一条任务：取数据 -> 组结果 -> 可选导出文本 / 图片。

    `report_changes=False` 用于 `update`：它自己会完整报告变化，避免摘要重复。
    """
    kind = str(task.get("type") or "").strip().lower()
    builder = TASK_BUILDERS.get(kind)
    if builder is None:
        raise RotaOffError(t("task-type-unknown", task_type=kind))

    settings = output.output_settings()
    if render_image is None:
        render_image = bool(task.get("image", settings.get("image")))

    started = time.time()
    result = builder(task, render_image)
    result["type"] = kind
    result["name"] = task.get("name") or result.get("title") or kind
    result["elapsed"] = round(time.time() - started, 2)
    if not report_changes:
        result["change_summary"] = ""

    task_settings = dict(settings)
    if task.get("export") is not None:
        task_settings["export"] = task["export"]
    if task.get("template"):
        task_settings["template"] = task["template"]
    try:
        result["files"] = output.export_result(result, formats, task_settings)
    except OSError as exc:
        # 导出失败不该毁掉结果本身：表格照常打印，只提示写不进去
        result["files"] = []
        result["export_error"] = str(exc)
        ui.warn(f"导出失败，结果只在终端显示: {exc}")
    return result


def run_tasks(tasks: list | None = None, render_image: bool | None = None, formats=None, on_result=None) -> list:
    """依次执行任务；单条失败只记录错误，不影响后面的任务（错误隔离）。"""
    tasks = tasks if tasks is not None else store_tasks()
    results = []
    for index, task in enumerate(tasks, 1):
        try:
            result = run_task(task, render_image, formats)
            result["ok"] = True
        except Exception as exc:                      # noqa: BLE001 - 刻意兜底
            result = {
                "ok": False,
                "name": task.get("name") or f"task-{index}",
                "type": task.get("type", ""),
                "error": str(exc),
                "elapsed": 0.0,
                "summary": [],
                "columns": [],
                "rows": [],
                "files": [],
                "image": "",
            }
        results.append(result)
        if on_result is not None:
            on_result(result)
    return results


def store_tasks() -> list:
    """小包装，方便测试时替换数据源。"""
    from .store import load_tasks

    return load_tasks()