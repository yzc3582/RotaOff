# RotaOff

**Language**：[简体中文](README.zh_CN.md) · [English](README.md)

An offline stat viewer for Rotaeno built on [None1145/RotaBot](https://github.com/None1145/RotaBot) (made for showing your Rating on stream).

(Yes, another vibe-coded project...)

Compared with the original:

- **No Discord**: nothing does `import discord`; the old message handlers are now plain functions
- **No async**: a plain synchronous `while` loop — type a command, get a result
- **Tasks you can save**: describe "what to query and how to export it" in `data/tasks.json`, then let `run_tasks.py` run it on a schedule

All the math is reused from the bundled `rotaeno/` package (left untouched): per-chart Rating, B40 and status filters are its own functions — only the input changed from Discord interactions to local config.

## Install

```bat
install_env.bat
```

The script creates `.venv` and installs dependencies. Afterwards it **asks** whether to download the chromium engine (only needed for image output, about 150 MB, skipped by default).

On Linux / macOS use `./install_env.sh` with the same arguments. Manual install:

```bat
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
```

> `rotaeno/utils.py` runs `from playwright.sync_api import ...` at import time, so playwright and Pillow are hard dependencies. Without the chromium engine only image output is unavailable; text queries work fine.

## Quick start

```bat
.venv\Scripts\python tui.py          :: interactive shell (configure account, build tasks, ad-hoc queries)
.venv\Scripts\python bot.py          :: same as tui.py, kept for old habits
.venv\Scripts\python run_tasks.py    :: run every task in data/tasks.json
```

On first run, missing `data/users.json` / `data/tasks.json` are copied from the `*.example.json` files.

Three steps:

1. `login` — scan the TapTap QR code; `serverCode` / `objectID` / `sessionToken` are filled in for you
2. `task add` — guided task creation (B40, single song, status, level range, custom fields)
3. `run_tasks.py` — no interaction needed any more

## Commands (tui.py)

| Command | What it does |
| --- | --- |
| `profile` / `profile use <name>` / `profile new <name>` | list, switch, create player profiles |
| `profile set server cn\|global` | switch server |
| `login [cn\|global]` | scan-to-login for TapTap |
| `b40` | Best40 table |
| `song <title or alias>` | per-difficulty Rating of one song |
| `status [FC\|AP\|APP\|...]` | list charts by play status |
| `rtr <min> [max] [sort]` | level range, sort = rating/score/level |
| `custom [fields...]` | custom fields, e.g. `custom username rating level` |
| `tasks` / `task add` / `task rm <index>` / `task run [selection]` | task management |
| `output` / `output set <key> <value>` | output settings (dir, export formats, filename template, image toggle) |
| `interval <seconds>` | automation interval, 0 = run once |
| `save` | export the current result immediately |
| `help` / `quit` | — |

## Automation

```bat
python run_tasks.py --list                      :: list tasks
python run_tasks.py --dry-run                   :: show what would run, run nothing
python run_tasks.py --task 1,3                  :: only tasks 1 and 3
python run_tasks.py --task 1-5 --filter "i % 2 == 0"   :: only the even ones: 2 and 4
python run_tasks.py --interval 300              :: every 5 minutes, Ctrl+C to stop
python run_tasks.py --save txt,md --image       :: override export formats / enable image
```

Selection rules (`--task` starts a new segment, `--filter` narrows only the current one, all segments are unioned at the end) and the filter expression syntax are documented in [filter.en_US.md](filter.en_US.md) · [中文](filter.zh_CN.md).

## Configuration

Shape of `data/tasks.json`:

```json
{
    "profile": "default",
    "output": {
        "dir": "output",
        "image": false,
        "export": [],
        "template": "{type}-{stamp}",
        "latest": ""
    },
    "schedule": { "interval": 0 },
    "tasks": [
        { "name": "my B40", "type": "b40", "profile": "default" }
    ]
}
```

- `output.export` — empty means print only; any of `txt` / `md` / `csv` / `json`, multiple allowed
- `output.template` — filename template, placeholders: `{type}` `{name}` `{profile}` `{stamp}`
- `output.latest` — e.g. `"{type}-latest"` writes an extra copy under a fixed name so OBS can keep reading one file (writes go to `.tmp` then `os.replace`, so a half-written file is never visible)
- `tasks[].profile` — which player profile to use; omit to use the active one
- `tasks[].export` / `image` / `template` / `limit` / `strict` — per-task overrides of the global settings

Task types: `custom` (arbitrary fields), `b40`, `song_info` (one song), `song_status` (by status), `song_rtr` (level range).

> Omitting `level_max` in `song_rtr` means **no upper bound** (the internal default is 1145 — an easter egg for the original author, None1145). A future 14.9 chart needs no code change; write `"level_max": 15` only when you really want a ceiling.

## Localization and fallback

Strings live in `data/i18n/`; currently `zh-CN.json` and `en-US.json`. The active one comes from `locale` in the player profile (`profile set locale en-US`).

Lookup in `rotaoff/i18n.py` falls back step by step, so a missing line never crashes anything:

1. look up the key in the requested language (e.g. `en-US`)
2. if missing, look it up in `zh-CN`
3. if still missing, show the **key itself** (so a missing translation is obvious instead of blank)

Placeholders use the `{name}` form: `t("task-added", name="B40")`. If the passed arguments do not match, the unformatted text is returned instead of raising.

When adding strings you only have to edit `zh-CN.json`; keys missing from `en-US` fall back to Chinese. To translate one, add the same key to `en-US.json`.

## One instance at a time

`tui.py` and `run_tasks.py` both write `data/tasks.json`, so startup takes a mutex on `data/rotaoff.lock` via `filelock`:

- another instance is running → startup is refused and the holder (role / pid / start time) is printed
- the lock is managed by the OS, so it is **released automatically when the process exits** — including crashes and force-kills; no manual cleanup, and a long-running `--interval` is never mistaken for a stale lock
- to see who holds it, check `data/rotaoff.lock.info`; if you are sure the other instance is gone you can pass `--force` to skip the lock, but two instances writing the same output will overwrite each other

## About the data

- one request fetches `playerInfo` + `songDatas`, everything else is computed locally, which keeps rate-limiting unlikely
- missing title / artist / status shows `【无数据】`; no assets are downloaded
- **charts with a missing level (diff) are never silently counted as 0 rating**: they are skipped with a warning, or make the task fail when it sets `"strict": true`

## 📜 License

Released under the [MIT License](https://license/).

This project is a fork of [None1145/RotaBot](https://github.com/None1145/RotaBot). The original project shipped no standard LICENSE file, but its README explicitly allowed modification and redistribution, so this fork keeps the original attribution and is released under MIT.

