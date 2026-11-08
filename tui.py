"""RotaOff 交互入口：配置账号 / 任务，也可以立刻查一次。

纯同步 while 循环：敲一行命令 -> 调 rotaoff.tasks -> 打印结果。
没有 asyncio，也没有任何 Discord 依赖。
"""

import os
import shlex
import sys

from rotaoff import data, library, lock, output, select, store, tasks, ui
from rotaoff.i18n import t
from rotaoff.store import RotaOffError

HELP_ZH = """
账号
  profile                     查看所有配置与当前配置
  profile use <名称>          切换当前配置
  profile new <名称>          新建一个配置
  profile set server cn|global      设置服务器
  profile set objectid <ID>        设置 objectID
  profile set session <TOKEN>      设置 sessionToken
  login [cn|global]           扫码登录 TapTap 并自动填好上面三项
                              只支持 cn / global；上游的 private 服务器是半成品，本项目不支持

查询（结果只在终端显示，除非开了 output 导出）
  b40                         Best40 表格
  song <曲名或别名>            单曲所有难度的 Rating
  status [FC|AP|APP|CLEAR|...] 按状态列曲目
  rtr <下限> <上限> [排序]      指定定数区间，排序 = rating/score/level
  custom [字段...]             自定义字段，如 custom username rating level completion
  update                      下载一次云存档并报告与上次相比的变化（别名 refresh）

任务（保存在 data/tasks.json，可交给 run_tasks.py 自动跑）
  tasks                       列出任务
  task add                    引导式新建任务
  task rm <序号>              删除任务
  task run [序号|all]         执行任务

输出
  output                      查看输出设置
  output set export txt,md    默认导出格式（留空则只打印）
  output set template <模板>   文件名模板，可用 {type} {name} {profile} {stamp}
  output set latest <模板>     额外写一份固定名副本，方便 OBS 读取
  output set dir <目录>        输出目录
  output set image on|off     是否生成图片（默认 off）

其它
  library                     查看当前用的是哪份曲库
  library update              从 wiki 抓最新 Songlist.json 并重建 data/song_data.db
  library update --local      只用本地的 Songlist.json（不联网）
  library source [路径]       指定 Songlist.json 的位置
  interval <秒>               保存自动化循环间隔，0 = 只跑一次
  help / quit
""".strip()

HELP_EN = """
Account
  profile                     show every profile and the active one
  profile use <name>          switch the active profile
  profile new <name>          create a profile
  profile set server cn|global      set the server
  profile set objectid <ID>         set objectID
  profile set session <TOKEN>       set sessionToken
  login [cn|global]           scan the TapTap QR code and fill the three fields above
                              cn / global only; upstream's "private" server is a stub and is not supported

Queries (printed in the terminal unless output export is enabled)
  b40                         Best40 table
  song <title or alias>       rating of every difficulty of one song
  status [FC|AP|APP|CLEAR|...] list charts by play status
  rtr <min> <max> [sort]      level range; sort = rating/score/level
  custom [fields...]          custom fields, e.g. custom username rating level completion
  update                      download the cloud save once and report changes since last time (alias: refresh)

Tasks (stored in data/tasks.json, can also run by run_tasks.py)
  tasks                       list tasks
  task add                    guided task creation
  task rm <index>             delete a task
  task run [index|all]        run tasks
  tasks run [index|all]       same as above

Output
  output                      show output settings
  output set export txt,md    default export formats (empty = print only)
  output set template <tmpl>  filename template; {type} {name} {profile} {stamp}
  output set latest <tmpl>    extra fixed-name copy, handy for OBS
  output set dir <dir>        output directory
  output set image on|off     render images (default off)

Other
  library                     show which song library is in use
  library update              fetch the latest Songlist.json from the wiki and rebuild data/song_data.db
  library update --local      use only the local Songlist.json (no network)
  library source [path]       point at a different Songlist.json
  interval <seconds>          save the automation loop interval, 0 = run once
  help / quit
""".strip()

HELP_BY_LOCALE = {"zh-CN": HELP_ZH, "en-US": HELP_EN}


def help_text() -> str:
    """按当前配置的语言给出帮助；没有对应语言就回退中文。"""
    return HELP_BY_LOCALE.get(store.profile_locale(), HELP_ZH)



# ---------------------------------------------------------------- 小工具

def _mask(token) -> str:
    text = str(token or "")
    return f"{text[:6]}…" if len(text) > 6 else text


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


# ---------------------------------------------------------------- 账号

def show_profiles() -> None:
    users = store.load_users()
    active = store.active_profile_name()
    if not users:
        ui.info("还没有任何配置，用 profile new <名称> 建一个，或直接 login 扫码。")
        return
    rows = []
    for name, profile in users.items():
        verified, key = store.verify_profile(profile)
        rows.append([
            ("* " if name == active else "  ") + name,
            str(profile.get("serverCode") or "-"),
            _mask(profile.get("objectID")),
            _mask(profile.get("sessionToken")),
            t(key, profile.get("locale", "zh-CN")),
        ])
    ui.table(["配置", "服务器", "objectID", "sessionToken", "状态"], rows,
             aligns=["left", "center", "left", "left", "left"])


def cmd_profile(args) -> None:
    if not args or args[0] in ("show", "list", "ls"):
        show_profiles()
        return

    action = args[0]
    if action == "use" and len(args) >= 2:
        store.set_active_profile(args[1])
        ui.ok(f"当前配置: {args[1]}")
        return
    if action == "new" and len(args) >= 2:
        store.create_profile(args[1])
        store.set_active_profile(args[1])
        ui.ok(f"已新建并切换到配置: {args[1]}")
        return
    if action == "set" and len(args) >= 3:
        key, value = args[1], " ".join(args[2:])
        field, verified, message_key = store.set_profile_field(key, value)
        if verified:
            ui.ok(f"已保存: {field} = {value}")
        else:
            ui.warn(f"已保存: {field} = {value}（还缺: {t(message_key, store.profile_locale())}）")
        return
    ui.warn("用法: profile | profile use <名> | profile new <名> | profile set <字段> <值>")


def cmd_login(args) -> None:
    from rotaeno.api import taptap_auth

    server = (args[0] if args else "cn").lower()
    if server not in store.SERVER_CODES:
        raise RotaOffError(t("unavailable-server-code", server_code=server))

    login = taptap_auth.TapTapLogin(server=server, device_id=store.active_profile_name())
    qrcode = login.get_qrcode(needImage=True)
    ui.info(f"二维码已保存: {qrcode['image']}")
    _open_path(qrcode["image"])
    ui.info("请用 TapTap 在 60 秒内扫码登录…（Ctrl+C 可放弃）")

    try:
        info = login.get_objectid_and_sessiontoken(qrcode_data=qrcode, show_qrcode=False)
    except TimeoutError:
        raise RotaOffError(
            t("login-timed-out-please-retrieve-taptap-login-qrcode-again")
        )

    store.set_profile_field("serverCode", server)
    store.set_profile_field("objectID", info["objectID"])
    _, verified, message_key = store.set_profile_field("sessionToken", info["sessionToken"])
    message = t(message_key, store.profile_locale())
    ui.ok(message) if verified else ui.warn(message)


# ---------------------------------------------------------------- 即时查询

def cmd_b40(args) -> None:
    _run(tasks.build_task("b40", name="Best40", template="b40"))


def cmd_song(args) -> None:
    alias = " ".join(args).strip()
    if not alias:
        raise RotaOffError("用法: song <曲名或别名>")
    _run(tasks.build_task("song_info", name=alias, song_alias=alias, template="song"))


def cmd_status(args) -> None:
    status = (args[0] if args else "FC").upper()
    _run(tasks.build_task("song_status", name=f"状态 {status}", status=status,
                          template="status"))


def cmd_rtr(args) -> None:
    if len(args) < 2:
        raise RotaOffError("用法: rtr <下限> <上限> [rating|score|level]")
    sort = (args[2] if len(args) > 2 else "rating").lower()
    _run(tasks.build_task(
        "song_rtr",
        name=f"等级 {args[0]}~{args[1]}",
        level_min=args[0],
        level_max=args[1],
        sort=sort,
        template="rtr",
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
    _run(tasks.build_task("custom", name="自定义", fields=fields, template="custom"))


# ---------------------------------------------------------------- 任务

def cmd_tasks(args) -> None:
    """`tasks` 列表；`tasks run ...` 是 `task run ...` 的别名（很多人会顺手写复数）。"""
    if args and args[0].lower() in ("run", "rm", "del", "delete", "add"):
        cmd_task(args)
        return
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
    action = (args[0] if args else "list").lower()
    if action in ("list", "ls"):
        cmd_tasks([])
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

    cmd_tasks([])


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
    export = _ask("导出格式 (txt/md/csv/json，逗号分隔，留空 = 只打印)", "")
    template = _ask("文件名模板（可用 {type} {name} {profile} {stamp}）", "")
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


# ---------------------------------------------------------------- 输出设置

def _parse_setting(key: str, value: str):
    if key == "image":
        return value.lower() in ("1", "true", "on", "yes", "y")
    if key == "export":
        return [item for item in value.replace(" ", ",").split(",") if item]
    return value


def _format_setting(value) -> str:
    if isinstance(value, bool):
        return "on" if value else "off"
    if isinstance(value, list):
        return ",".join(value) or "(只打印)"
    return str(value) or "(空)"


def cmd_output(args) -> None:
    if not args or args[0] in ("show", "list"):
        settings = output.output_settings()
        ui.table(["设置", "值"], [[key, _format_setting(value)] for key, value in settings.items()])
        ui.info(f"输出目录: {output.resolve_output_dir(settings.get('dir'))}")
        return

    if args[0] == "set" and len(args) >= 3:
        key, value = args[1].lower(), " ".join(args[2:])
        if key not in output.DEFAULT_OUTPUT:
            raise RotaOffError(t("output-field-invalid", field=key))
        settings = output.set_output_field(key, _parse_setting(key, value))
        ui.ok(f"已保存: {key} = {_format_setting(settings[key])}")
        return

    if args[0] in ("export", "save"):
        formats = [item for item in ",".join(args[1:]).replace(" ", ",").split(",") if item]
        settings = output.set_output_field("export", formats)
        ui.ok(f"默认导出: {_format_setting(settings['export'])}")
        return

    ui.warn("用法: output | output set <键> <值> | output export txt,md")


def _show_library_gaps(locale: str = "zh-CN") -> None:
    """本次运行里上游扫描存档时发现的「曲库对不上」，平时被 `data.quiet_call` 吃掉。"""
    gaps = data.missing_from_library()
    if not gaps["songs"] and not gaps["levels"]:
        return
    rows = [
        [song_id, t("library-gaps-whole-song", locale),
         t("library-gaps-song-missing", locale)]
        for song_id in gaps["songs"]
    ]
    rows += [
        [song_id, level, t("library-gaps-level-special", locale)]
        for song_id, level in gaps["levels"]
    ]
    print()
    ui.info(t("library-gaps-title", locale))
    ui.table(
        [t("library-gaps-column-song", locale), t("library-gaps-column-level", locale),
         t("library-gaps-column-note", locale)],
        rows, aligns=["left", "center", "left"],
    )


def _display_path(path: str) -> str:
    """仓库内的绝对路径按相对路径显示；仓库外保持原样。"""
    if not path or not os.path.isabs(path):
        return path or ""
    from rotaoff.paths import BASE_DIR

    try:
        relative = os.path.relpath(path, BASE_DIR)
    except ValueError:
        return path
    if relative.startswith(".."):
        return path
    return relative.replace(os.sep, "/")


def cmd_library(args) -> None:
    """曲库：看现在用的哪份、更新、换源。"""
    locale = store.profile_locale(store.active_profile_name())

    if not args or args[0] in ("show", "list", "status"):
        status = library.status(locale)
        retired_info = status.get("retired") or {}
        ui.table(
            [t("library-column-item", locale), t("library-column-value", locale)],
            [
                [t("library-current-source", locale), status["source"]],
                [t("library-songs", locale), status.get("songs", "-")],
                [t("library-charts", locale), status.get("charts", "-")],
                [t("library-iv-alpha", locale), status.get("iv_alpha", "-")],
                [t("library-latest-version", locale), status.get("latest_release") or "-"],
                [t("library-library-file", locale),
                 _display_path(status.get("path", "")) or t("library-none", locale)],
                [t("library-songlist-origin", locale),
                 t("library-origin-songlist", locale)],
                [t("library-songlist-json", locale),
                 _display_path(status.get("source_json", "")) or t("library-none", locale)],
                [t("library-retired-origin", locale),
                 t("library-origin-retired", locale)],
                [t("library-retired-text", locale),
                 retired_info.get("text") or t("library-none", locale)],
                [t("library-retired-db", locale),
                 retired_info.get("db") or t("library-none", locale)],
                [t("library-retired-records", locale), t(
                    "library-retired-records-value", locale,
                    count=retired_info.get("count", "-"),
                    due=retired_info.get("due", "-"),
                )],
            ],
            max_width=60,
        )
        if status.get("warning"):
            ui.warn(status["warning"])
        if not status.get("built"):
            ui.warn(t("library-old-warning", locale))
        _show_library_gaps(locale)
        return

    if args[0] == "update":
        local = "--local" in args or "-l" in args
        stats = library.update(local=local, locale=locale)
        ui.ok(t(
            "library-updated", locale,
            songs=stats["songs"],
            charts=stats["charts"],
            iv_alpha=stats["iv_alpha"],
            version=stats["latest_release"] or t("library-unknown", locale),
        ))
        for note in stats.get("notes") or []:
            ui.info(note)
        if stats.get("path"):
            ui.info(t("library-write", locale, path=_display_path(stats["path"])))
            ui.info(t("library-effective", locale))
        else:
            ui.warn(t("library-not-persisted", locale))
        return

    if args[0] in ("source", "path"):
        if len(args) < 2:
            retired_info = library.status().get("retired") or {}
            ui.info(t("library-songlist-json-location", locale,
                      path=_display_path(library.source_path())))
            ui.info(t("library-manual-songlist", locale, url=library.SONGLIST_URL))
            ui.info(t("library-retired-text-location", locale,
                      path=retired_info.get("text") or t("library-none", locale)))
            ui.info(t("library-manual-retired", locale,
                      url=retired_info.get("url") or ""))
            return
        store.set_library_path(" ".join(args[1:]))
        ui.ok(t("library-source-saved", locale,
                path=_display_path(library.source_path())))
        return

    ui.warn(t("library-usage", locale))


def cmd_interval(args) -> None:
    if not args:
        seconds = store.load_config().get("schedule", {}).get("interval", 0)
        ui.info(f"自动化间隔: {seconds} 秒（0 = 只跑一次）")
        return
    schedule = store.set_schedule_interval(int(args[0]))
    ui.ok(f"自动化间隔已保存: {schedule['interval']} 秒")


# ---------------------------------------------------------------- 主循环

COMMANDS = {
    "help": lambda args: print(help_text()),
    "?": lambda args: print(help_text()),
    "profile": cmd_profile,
    "login": cmd_login,
    "b40": cmd_b40,
    "song": cmd_song,
    "status": cmd_status,
    "rtr": cmd_rtr,
    "custom": cmd_custom,
    "update": cmd_update,
    "refresh": cmd_update,
    "tasks": cmd_tasks,
    "task": cmd_task,
    "output": cmd_output,
    "save": lambda args: cmd_output(["export"] + args),
    "library": cmd_library,
    "db": cmd_library,
    "interval": cmd_interval,
}


def dispatch(parts: list) -> bool:
    command, args = parts[0].lower(), parts[1:]
    if command in ("quit", "exit", "q"):
        ui.info("再见，记得休息一下眼睛。")
        return False

    handler = COMMANDS.get(command)
    if handler is None:
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
