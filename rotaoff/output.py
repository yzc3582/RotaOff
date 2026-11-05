"""输出层：输出设置、文件名模板、原子写入、文本导出、可选图片渲染。

图片默认关闭；渲染失败只警告，不影响文本结果，因此不装 playwright 也能用。
"""

import json
import os
import shutil
from datetime import datetime

from . import ui
from .paths import BASE_DIR
from .store import RotaOffError, load_config, save_config, t

EXPORT_FORMATS = ("txt", "md", "csv", "json")

# 全部可在 TUI 里改并写回 data/tasks.json 的 output 段
DEFAULT_OUTPUT = {
    "dir": "output",
    "image": False,                  # 图片默认关闭，只出文本
    "export": [],                    # 例如 ["txt", "md"]，空表示只打印
    "template": "{type}-{stamp}",    # 可用 {type} {name} {profile} {stamp}
    "latest": "",                     # 比如 "{type}-latest"，留空则不生成固定名副本
}


def output_settings() -> dict:
    settings = dict(DEFAULT_OUTPUT)
    custom = load_config().get("output")
    if isinstance(custom, dict):
        settings.update(custom)
    formats = [str(item).lower() for item in settings.get("export") or []]
    settings["export"] = [item for item in formats if item in EXPORT_FORMATS]
    return settings


def set_output_field(key: str, value) -> dict:
    """改输出设置并立刻存盘。"""
    if key not in DEFAULT_OUTPUT:
        raise RotaOffError(t("output-field-invalid", field=key))
    settings = output_settings()
    settings[key] = value
    config = load_config()
    config["output"] = settings
    save_config(config)
    return settings


def resolve_output_dir(path: str = "") -> str:
    path = path or output_settings().get("dir") or "output"
    return path if os.path.isabs(path) else os.path.join(BASE_DIR, path)


def render_name(template: str, result: dict) -> str:
    """把 {type} {name} {profile} {stamp} 占位符换成实际名字。"""
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    values = {
        "type": result.get("type", "task"),
        "name": result.get("name", ""),
        "profile": result.get("profile", ""),
        "stamp": stamp,
    }
    text = template or "{type}-{stamp}"
    for key, value in values.items():
        text = text.replace("{" + key + "}", str(value))
    safe = "".join(ch for ch in text if ch not in '\\/:*?"<>|').strip()
    return safe or f"task-{stamp}"


def atomic_write(path: str, text: str, encoding: str = "utf-8") -> None:
    """先写临时文件再替换，避免 OBS 之类的程序读到写了一半的内容。"""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    temp = path + ".tmp"
    with open(temp, "w", encoding=encoding, newline="") as file:
        file.write(text)
    os.replace(temp, path)


def export_payload(result: dict) -> dict:
    return {
        "name": result.get("name", ""),
        "type": result.get("type", ""),
        "profile": result.get("profile", ""),
        "exportedAt": datetime.now().isoformat(timespec="seconds"),
        "elapsed": result.get("elapsed", 0),
        "summary": result.get("summary", []),
        "columns": result.get("columns", []),
        "rows": result.get("rows", []),
    }


def export_text(result: dict, fmt: str) -> str:
    columns = result.get("columns", [])
    rows = result.get("rows", [])
    if fmt == "md":
        return ui.to_markdown(columns, rows, title=result.get("name", ""))
    if fmt == "csv":
        return ui.to_csv(columns, rows)
    if fmt == "json":
        return json.dumps(export_payload(result), ensure_ascii=False, indent=4)

    lines = [f"# {result.get('name', '')}  ({result.get('type', '')})"]
    lines += [f"# {text}" for text in result.get("summary", [])]
    body = ui.table_lines(columns, rows, result.get("aligns"), footer=False)
    if not body:
        body = [result.get("empty_text", "（没有数据）")]
    return "\n".join(lines + [""] + body) + "\n"


def export_result(result: dict, formats=None, settings: dict = None) -> list:
    """把文本结果写成文件；返回生成的文件路径列表。"""
    settings = settings or output_settings()
    if formats is None:
        formats = settings.get("export") or []
    formats = [str(fmt).lower() for fmt in formats if str(fmt).lower() in EXPORT_FORMATS]
    if not formats:
        return []

    out_dir = resolve_output_dir(settings.get("dir"))
    os.makedirs(out_dir, exist_ok=True)
    stem = render_name(settings.get("template", "{type}-{stamp}"), result)
    latest = settings.get("latest") or ""
    files = []

    for fmt in dict.fromkeys(formats):
        text = export_text(result, fmt)
        encoding = "utf-8-sig" if fmt == "csv" else "utf-8"
        path = os.path.join(out_dir, f"{stem}.{fmt}")
        atomic_write(path, text, encoding)
        files.append(path)
        if latest:
            stable = os.path.join(out_dir, f"{render_name(latest, result)}.{fmt}")
            atomic_write(stable, text, encoding)
            files.append(stable)
    return files


def save_image(path: str, prefix: str, out_dir: str = "") -> str:
    """把渲染结果复制到输出目录，文件名用前缀 + 时间戳。"""
    if not path or not os.path.exists(path):
        return ""
    target_dir = resolve_output_dir(out_dir)
    os.makedirs(target_dir, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    suffix = os.path.splitext(path)[1] or ".png"
    target = os.path.join(target_dir, f"{prefix}-{stamp}{suffix}")
    index = 1
    while os.path.exists(target):
        target = os.path.join(target_dir, f"{prefix}-{stamp}-{index}{suffix}")
        index += 1
    shutil.copy2(path, target)
    return target


def try_render_image(render, prefix: str, *args, **kwargs) -> str:
    """调用可选的图片渲染函数；任何失败都只警告，不影响文本输出。"""
    try:
        return save_image(render(*args, **kwargs), prefix, kwargs.get("out_dir", ""))
    except Exception as exc:                      # noqa: BLE001 - 刻意兜底
        ui.warn(f"图片渲染已跳过（{type(exc).__name__}: {exc}）")
        return ""
