"""终端渲染小工具：ANSI 颜色 + 中英混排表格（只用标准库）。

表格列宽按“显示宽度”计算（中日韩字符算 2 列），
所以中文曲名不会把边框撑歪。
"""

import csv
import io
import os
import sys
import unicodedata

BOLD = "\033[1m"
DIM = "\033[2m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
RESET = "\033[0m"


def _enable_ansi() -> bool:
    """判断终端是否支持 ANSI 颜色；Windows 下顺手打开 VT 模式。"""
    if os.environ.get("NO_COLOR"):
        return False
    try:
        if not sys.stdout.isatty():
            return False
    except Exception:
        return False
    if os.name == "nt":
        try:
            import ctypes

            kernel32 = ctypes.windll.kernel32
            handle = kernel32.GetStdHandle(-11)
            mode = ctypes.c_uint32()
            if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
                kernel32.SetConsoleMode(handle, mode.value | 0x0004)
        except Exception:
            return False
    return True


COLOR = _enable_ansi()


def paint(text: str, *codes: str) -> str:
    if not COLOR or not codes:
        return str(text)
    return "".join(codes) + str(text) + RESET


def display_width(text: str) -> int:
    return sum(2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1 for ch in text)


def _emit(message: str, *codes: str, stream=None) -> None:
    """按目标流决定是否上色：重定向到文件 / 管道的 stderr 不该混入 ANSI 码。"""
    target = stream or sys.stdout
    try:
        colored = COLOR and target.isatty()
    except Exception:
        colored = False
    text = "".join(codes) + str(message) + RESET if colored and codes else str(message)
    print(text, file=target)


def info(message: str, stream=None) -> None:
    _emit(message, DIM, stream=stream)


def ok(message: str, stream=None) -> None:
    _emit("✔ " + message, GREEN, stream=stream)


def warn(message: str, stream=None) -> None:
    _emit("! " + message, YELLOW, stream=stream)


def error(message: str, stream=None) -> None:
    _emit("✘ " + message, RED, stream=stream)


def banner(title: str, subtitle: str = "") -> None:
    width = max(display_width(title), display_width(subtitle)) + 8
    print(paint("─" * width, CYAN))
    print(paint("  " + title, BOLD, CYAN))
    if subtitle:
        print(paint("  " + subtitle, DIM))
    print(paint("─" * width, CYAN))


def prompt(text: str) -> str:
    return paint(text, CYAN, BOLD)


def _fit(text: str, width: int) -> str:
    if width <= 0 or display_width(text) <= width:
        return text
    kept = ""
    used = 0
    for ch in text:
        step = 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
        if used + step > width - 1:
            break
        kept += ch
        used += step
    return kept + "…"


def _align(text: str, width: int, align: str) -> str:
    gap = max(width - display_width(text), 0)
    if align == "right":
        return " " * gap + text
    if align == "center":
        left = gap // 2
        return " " * left + text + " " * (gap - left)
    return text + " " * gap


def table_lines(
    columns,
    rows,
    aligns=None,
    limit: int | None = None,
    max_width: int = 46,
    footer: bool = True,
    footer_text: str = "  共 {total} 条，这里只显示前 {limit} 条",
) -> list:
    """生成表格的各行文本（不带颜色），既能打印也能落盘。"""
    columns = [str(column) for column in columns]
    aligns = (list(aligns or []) + ["left"] * len(columns))[: len(columns)]

    if not rows:
        return []

    total = len(rows)
    shown = rows[:limit] if limit else rows
    cells = [[_fit(str(cell), max_width) for cell in row] for row in shown]

    widths = [display_width(column) for column in columns]
    for row in cells:
        for index, cell in enumerate(row):
            if index < len(widths):
                widths[index] = max(widths[index], display_width(cell))

    def rule(left: str, joint: str, right: str) -> str:
        return left + joint.join("─" * (width + 2) for width in widths) + right

    def line(row) -> str:
        body = "│".join(
            " " + _align(str(cell), width, align) + " "
            for cell, width, align in zip(row, widths, aligns)
        )
        return "│" + body + "│"

    lines = [rule("┌", "┬", "┐"), line(columns), rule("├", "┼", "┤")]
    lines += [line(row) for row in cells]
    lines.append(rule("└", "┴", "┘"))
    if footer and limit and total > limit:
        lines.append(footer_text.format(total=total, limit=limit))
    return lines


def table(columns, rows, aligns=None, limit: int | None = None, max_width: int = 46,
          empty_text: str = "（没有数据）", footer: bool = True) -> None:
    """打印一张等宽表格；limit 只影响显示，不裁剪数据本身。"""
    if not rows:
        print(paint("  " + empty_text, DIM))
        return
    for index, line in enumerate(table_lines(columns, rows, aligns, limit, max_width, footer)):
        if index < 3 or line.startswith(("└", "  共")):
            print(paint(line, DIM) if index != 1 else paint(line, BOLD))
        else:
            print(line)


def to_markdown(columns, rows, title: str = "") -> str:
    """导出为 Markdown 表格，方便贴进笔记 / issue。"""
    def cell(value) -> str:
        return str(value).replace("|", "\\|").replace("\n", " ")

    lines = [f"# {title}", ""] if title else []
    lines.append("| " + " | ".join(cell(column) for column in columns) + " |")
    lines.append("| " + " | ".join("---" for _ in columns) + " |")
    for row in rows:
        lines.append("| " + " | ".join(cell(value) for value in row) + " |")
    return "\n".join(lines) + "\n"


def to_csv(columns, rows) -> str:
    """导出为 CSV（utf-8-sig 写盘时 Excel 直接不乱码）。"""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow([str(column) for column in columns])
    for row in rows:
        writer.writerow(["" if value is None else value for value in row])
    return buffer.getvalue()


def render_result(result: dict) -> None:
    """把 bot.run_task() 的结果打印成人能读的样子。"""
    print()
    headline = f"▶ {result.get('name', result.get('type', ''))}"
    print(paint(headline, BOLD, CYAN) + paint(f"  ({result.get('elapsed', 0)}s)", DIM))
    for text in result.get("summary", []):
        print("  " + str(text))
    for warning in result.get("warnings", []):
        warn(str(warning))
    if result.get("show_table", True):
        table(
            result.get("columns", []),
            result.get("rows", []),
            aligns=result.get("aligns"),
            limit=result.get("limit"),
            empty_text=result.get("empty_text", "（没有数据）"),
        )
    image = result.get("image")
    if image:
        ok(f"图片已保存: {image}")
