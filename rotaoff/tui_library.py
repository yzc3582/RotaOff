"""library 组（db）：曲库来源、更新、换源，以及存档对不上曲库的提示。"""

import os
import sys

from rotaoff import data, library, output, select, store, tasks, ui
from rotaoff.i18n import help_block, t
from rotaoff.store import RotaOffError

from rotaoff.tui_help import _want_help, help_text


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

    if _want_help(args):
        print(help_text("library"))
        return

    if args[0].lower() in ("show", "list", "ls", "status"):
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
