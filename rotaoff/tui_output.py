"""output 组：导出格式、文件名模板、输出目录、图片开关。"""

import os
import sys

from rotaoff import data, library, output, select, store, tasks, ui
from rotaoff.i18n import help_block, t
from rotaoff.store import RotaOffError

from rotaoff.tui_help import _want_help, help_text


def _parse_setting(key: str, value: str):
    """`off` / `null` / `none` / `-` 都表示「关掉 / 清空」，不用靠输入一对空引号。"""
    text = value.strip()
    lowered = text.lower()
    off = not text or lowered in ("off", "null", "none", "-", "no", "false")

    if key in ("image", "completion"):
        if lowered in ("on", "yes", "y", "true", "1"):
            return True
        if off:
            return False
        raise RotaOffError(f"{key} 只接受 on / off，收到: {text}")
    if key == "export":
        if off:
            return []
        return [item for item in text.replace(" ", ",").split(",") if item]
    if key == "latest" and off:
        return ""
    return text


def _format_setting(value) -> str:
    if isinstance(value, bool):
        return "on" if value else "off"
    if isinstance(value, list):
        return ",".join(value) or "(只打印)"
    return str(value) or "(空)"


def _show_output_settings() -> None:
    settings = output.output_settings()
    ui.table(["设置", "值"], [[key, _format_setting(value)] for key, value in settings.items()])
    ui.info(f"输出目录: {output.resolve_output_dir(settings.get('dir'))}")


def cmd_output(args) -> None:
    if _want_help(args):
        print(help_text("output"))
        return

    action = args[0].lower()
    if action in ("ls", "list", "show"):
        _show_output_settings()
        return

    if action == "set":
        if len(args) < 3:                    # `output set` 与 `output ls` 等价
            _show_output_settings()
            return
        key, value = args[1].lower(), " ".join(args[2:])
        if key not in output.DEFAULT_OUTPUT:
            raise RotaOffError(t("output-field-invalid", field=key))
        settings = output.set_output_field(key, _parse_setting(key, value))
        ui.ok(f"已保存: {key} = {_format_setting(settings[key])}")
        return

    if args[0] == "reset" and len(args) >= 2:
        key = args[1].lower()
        if key not in output.DEFAULT_OUTPUT:
            raise RotaOffError(t("output-field-invalid", field=key))
        settings = output.set_output_field(key, output.DEFAULT_OUTPUT[key])
        ui.ok(f"已恢复默认: {key} = {_format_setting(settings[key])}")
        return

    ui.warn("用法: output ls | output set <键> <值> | output reset <键>"
            "（<值> 填 off 表示关闭 / 清空）")
