"""RotaOff 自动化入口：无交互地把 data/tasks.json 里的任务跑一遍。

用法：
    python run_tasks.py                     跑一次全部任务
    python run_tasks.py --list              只看任务列表
    python run_tasks.py --task 1 --task 3   多段选择，结果取并集
    python run_tasks.py --task 1-3 --filter "i % 2 == 1"
    python run_tasks.py --interval 300      启动后每 300 秒跑一轮
    python run_tasks.py --save txt,md       强制导出格式
    python run_tasks.py --image             强制生成图片（默认关）
    python run_tasks.py --dry-run           只打印选中的任务
    python run_tasks.py --force             忽略 data/rotaoff.lock 强行启动

选择规则与 tui.py 里 task run 一致，见 docs/filter.zh_CN.md / docs/filter.en_US.md。
"""

import argparse
import sys
import time

from rotaoff import lock, select, store, tasks, ui
from rotaoff.store import RotaOffError


class _SelectAction(argparse.Action):
    """把 --task / --filter 按命令行出现顺序记进 namespace.selection_ops。

    argparse 本身会丢顺序，而选择规则依赖顺序（见 docs/filter.yzc3582.fake.cpp），
    所以这里自己记一笔。
    """

    def __call__(self, parser, namespace, values, option_string=None):
        ops = getattr(namespace, "selection_ops", None)
        if ops is None:
            ops = []
            setattr(namespace, "selection_ops", ops)
        ops.append((self.dest, values))

        given = list(getattr(namespace, self.dest, None) or [])
        given.append(values)
        setattr(namespace, self.dest, given)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="RotaOff 自动化任务执行器（无交互）",
        # 默认的 HelpFormatter 会把 epilog 折成一段，换行全被吃掉；这里保留原样
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="选择规则：初始集合是全部任务；每遇到一个 --task 就开新段，"
               "--filter 只作用于当前段，最后取各段并集。详见 docs/filter.zh_CN.md\n"
               "English users: see docs/py-all-in-one.en_US.md.",
    )
    parser.add_argument("--list", action="store_true", help="只列出任务")
    parser.add_argument("--task", action=_SelectAction, metavar="序号|区间|名字",
                        help="选择任务，支持 1,3 / 4-6 / 7~9 / all / * / 名字；可重复")
    parser.add_argument("--filter", action=_SelectAction, metavar="表达式",
                        help="在当前集合上筛选，可重复，如 \"i %% 2 == 0\"")
    parser.add_argument("--dry-run", action="store_true",
                        help="只打印会被执行的任务，不真正执行")
    parser.add_argument("--interval", type=int, metavar="秒",
                        help="循环间隔；不填则用配置里的 schedule.interval，0 = 只跑一次")
    parser.add_argument("--save", metavar="格式",
                        help="覆盖导出格式，例如 txt,md,csv,json")
    parser.add_argument("--image", dest="image", action="store_true", default=None,
                        help="强制生成图片")
    parser.add_argument("--no-image", dest="image", action="store_false",
                        help="强制不生成图片")
    parser.add_argument("--quiet", action="store_true", help="只报告结果，不打印表格")
    parser.add_argument("--force", action="store_true",
                        help="忽略 data/rotaoff.lock（确认另一个实例已退出时用）")
    return parser


def run_once(selected: list, args) -> int:
    """执行一轮，返回失败条数（错误隔离在 tasks.run_tasks 里做）。"""
    failures = 0
    for result in tasks.run_tasks(selected, render_image=args.image, formats=args.save):
        if not result.get("ok"):
            ui.error(f'{result["name"]}: {result["error"]}', stream=sys.stderr)
            failures += 1
            continue
        if args.quiet:
            ui.ok(f'{result["name"]}  {result["elapsed"]}s')
        else:
            ui.render_result(result)
        for warning in result.get("warnings", []):
            ui.warn(str(warning), stream=sys.stderr)
        if result.get("change_summary"):
            ui.info(result["change_summary"], stream=sys.stderr)
        for path in result.get("files", []):
            ui.ok(f"已写入: {path}")
    return failures


def show_selection(all_tasks: list, selected: list) -> None:
    """--dry-run 用：按原序号打印会被执行的任务。"""
    chosen = {id(task) for task in selected}
    ui.info(f"已选中 {len(selected)} 个任务：")
    for index, task in enumerate(all_tasks, 1):
        if id(task) in chosen:
            print(tasks.describe_task(task, index))


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    args = build_parser().parse_args(argv)
    store.ensure_workspace()

    all_tasks = store.load_tasks()
    if args.list:
        if not all_tasks:
            ui.info("还没有任务，先运行 python tui.py，用 task add 创建。", stream=sys.stderr)
            return 0
        for index, task in enumerate(all_tasks, 1):
            print(tasks.describe_task(task, index))
        return 0

    if not all_tasks:
        ui.warn("data/tasks.json 里没有任务，先运行 python tui.py 配置。", stream=sys.stderr)
        return 1

    lock.acquire("automation", force=args.force)

    if args.save is not None:
        args.save = [item for item in args.save.replace(" ", ",").split(",") if item]

    ops = getattr(args, "selection_ops", None) or []
    selected = select.apply_selection(all_tasks, ops)

    if not selected:
        ui.warn("没有任务被选中，检查 --task / --filter 的写法。", stream=sys.stderr)
        return 1

    if args.dry_run:
        show_selection(all_tasks, selected)
        return 0

    interval = args.interval
    if interval is None:
        interval = int(store.load_config().get("schedule", {}).get("interval", 0) or 0)

    if interval <= 0:
        return 1 if run_once(selected, args) else 0

    ui.info(f"自动化启动：每 {interval} 秒执行 {len(selected)} 个任务，Ctrl+C 停止", stream=sys.stderr)

    round_index = 0
    while True:
        round_index += 1
        ui.info(f"[{time.strftime('%H:%M:%S')}] 第 {round_index} 轮开始", stream=sys.stderr)
        failures = run_once(selected, args)
        ui.info(
            f"[{time.strftime('%H:%M:%S')}] 第 {round_index} 轮结束，"
            f"失败 {failures} 个，等待 {interval} 秒",
            stream=sys.stderr,
        )
        try:
            time.sleep(interval)
        except KeyboardInterrupt:
            ui.info("已停止自动化。", stream=sys.stderr)
            return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print()
        sys.exit(130)
    except RotaOffError as error:
        ui.error(str(error), stream=sys.stderr)
        sys.exit(1)
