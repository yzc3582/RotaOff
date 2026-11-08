# RotaOff — all-in-one English reference

**Language**：[简体中文](../README.zh_CN.md) · [English](../README.md) · this page

The Python entry points print Chinese by default, because the project (and its upstream `rotaeno/` package) is Chinese-first. Everything a user sees is listed here in English. Program messages can also be switched at runtime:

```bat
.venv\Scripts\python tui.py
rotaoff> profile set locale en-US
```

That makes `rotaoff/i18n.py` read `data/i18n/en-US.json`; any key missing there falls back to `zh-CN`, then to the raw key.

## `run_tasks.py` options

```
usage: run_tasks.py [-h] [--list] [--task SPEC] [--filter EXPR] [--dry-run]
                    [--interval SECONDS] [--save FORMATS] [--image]
                    [--no-image] [--quiet] [--force]
```

| Option | Meaning |
| --- | --- |
| `--list` | print the saved tasks and exit |
| `--task SPEC` | select tasks: `1,3` (indices), `4-6` / `7~9` (closed interval, both ends included), `all` / `*`, or a name substring. Repeatable |
| `--filter EXPR` | narrow the current selection, repeatable, e.g. `"i % 2 == 0"` |
| `--dry-run` | print which tasks would run, execute nothing |
| `--interval SECONDS` | loop interval; omitted = `schedule.interval` from the config, `0` = run once |
| `--save FORMATS` | override export formats, e.g. `txt,md,csv,json` |
| `--image` | force image rendering on |
| `--no-image` | force image rendering off |
| `--quiet` | report results only, no tables |
| `--force` | ignore `data/rotaoff.lock` (only when you are sure the other instance is gone) |

Selection rules: the initial set is every task; each `--task` starts a new segment, `--filter` narrows only the current segment, and all segments are unioned at the end. See [filter.en_US.md](filter.en_US.md) in this folder.

## `tui.py` commands

Account:

| Command | Meaning |
| --- | --- |
| `profile` | show every profile and which one is active |
| `profile use <name>` | switch the active profile |
| `profile new <name>` | create a profile |
| `profile set server cn\|global` | set the server |
| `profile set objectid <ID>` | set `objectID` |
| `profile set session <TOKEN>` | set `sessionToken` |
| `login [cn\|global]` | scan the TapTap QR code and fill in the three settings above |

Queries (results are printed unless `output` export is enabled):

| Command | Meaning |
| --- | --- |
| `b40` | Best40 table (retired songs excluded automatically; backed by `data/retired_songs.db`, refreshed by `library update`) |
| `song <title or alias>` | per-difficulty rating of one song |
| `status [FC\|AP\|APP\|CLEAR\|...]` | list charts by play status |
| `rtr <min> <max> [sort]` | level range; sort = `rating` / `score` / `level` |
| `custom [fields...]` | custom fields, e.g. `custom username rating level completion` |
| `update` / `refresh` | download the cloud save once and report Rating / per-chart changes since the previous snapshot |

Snapshot and change fields (usable through `custom`, `task add`, and `update`):

| Field | Meaning |
| --- | --- |
| `cloud_updated_at` | the CloudSave object's `updatedAt` — when the game synced the save to TapTap (converted to local time); the field that says whether data is fresh |
| `fetched_at` | when this machine downloaded the save; changes on every run |
| `rating_diff` | e.g. `14.7025+0.0094`; zero delta still prints `+0.0000`; the first record prints `首次记录，下次起可对比` |
| `songs_diff` | e.g. `Title (IV): 1,001,551 → 1,006,012 (+4,461)｜13.7551 → 14.5020｜NONE(C) → AP(-)`; `无变化` when nothing moved |

Every query still downloads the save in real time. A successful download overwrites `data/saves/<profile>.json` (`playerInfo + songDatas + fetchedAt`, latest copy only); a failed download never overwrites it. Status suffixes: `(C)` = cleared, `(-)` = not cleared, so `NONE(-)` means never played / not cleared and `AP(-)` is possible historical dirty data.

Change reporting: `tui.py` appends one summary line after `b40` / `custom` when the save changed (e.g. `云存档有变化：Rating 14.7025+0.0094，2 个谱面有变化`); `update` reports the full detail itself and skips that line. `run_tasks.py` sends change summaries, round messages, failures and warnings to **stderr**, keeping stdout for result data only. `song` / `status` / `rtr` do not run the snapshot diff yet.

Tasks (stored in `data/tasks.json`, can be run by `run_tasks.py`):

| Command | Meaning |
| --- | --- |
| `tasks` | list tasks |
| `task add` | guided task creation |
| `task rm <index>` | delete a task |
| `task run [index\|all]` | run tasks |

Output:

| Command | Meaning |
| --- | --- |
| `output` | show output settings |
| `output set export txt,md` | default export formats (empty = print only) |
| `output set template <tmpl>` | filename template; `{type}` `{name}` `{profile}` `{stamp}` |
| `output set latest <tmpl>` | extra copy under a fixed name, handy for OBS |
| `output set dir <dir>` | output directory |
| `output set image on\|off` | render images (default `off`) |

Other:

| Command | Meaning |
| --- | --- |
| `library` | which song library is in use, songs / charts / IV-α / latest version; also the retired-song source, text and db paths |
| `library update` | fetch `Template:Songlist.json` from the wiki (solves the Anubis proof-of-work) and rebuild `data/song_data.db` |
| `library update --local` | rebuild from the local `Songlist.json` only (offline) |
| `library source <path>` | point at another `Songlist.json` |
| `interval <seconds>` | save the automation loop interval, `0` = run once |
| `help` / `quit` | — |

> `library update` falls back in three steps: online fetch → local `Songlist.json` → the stale upstream db (with a warning that charts without a chart constant cannot be rated). Grab the json by hand from
> <https://wiki.rotaeno.cn/index.php?title=Template:Songlist.json&action=raw> if fetching fails.
>
> `library` also shows the retired-song text (`wiki/限时上架曲目列表.txt`), db (`data/retired_songs.db`),
> record count and due count, and prints the manual download link:
> <https://wiki.rotaeno.cn/index.php?title=限时上架曲目列表&action=raw>. `library update` refreshes it
> (`--local` uses the local text).

## Task wizard prompts (`task add`)

| Prompt | Notes |
| --- | --- |
| Task type (`custom` / `b40` / `song_info` / `song_status` / `song_rtr`) | default `custom` |
| Fields (comma separated, one of `username`, `rating`, `level`, `exp`, `completion`, `app`, `ap`, `fc`, `charts`, `playtime`, `b40`, `cloud_updated_at`, `fetched_at`, `rating_diff`, `songs_diff`) | `custom` only, default `rating` |
| Line template (`{label}` / `{value}`, empty = `{label}: {value}`) | `custom` only |
| Song title or alias | `song_info` only |
| Status (`NONE` / `FC` / `AP` / `APP` / `CLEAR` / `NOTCLEAR` / `FAVORITE` / `NOTFAVORITE`) | `song_status` only, default `FC` |
| Level min / max / sort | `song_rtr` only, defaults `14.0` / `15.0` / `rating` |
| Task name | default = song alias or type |
| Export formats (`txt` / `md` / `csv` / `json`, comma separated, empty = print only) | |
| Filename template | `{type}` `{name}` `{profile}` `{stamp}` |
| Render an image as well? (y/N) | default no |
| Fail when a level (diff) is missing? (y/N) | default no; `strict` per task |

## Runtime messages

| Situation | English meaning |
| --- | --- |
| `已有 RotaOff 在运行: …` | another RotaOff instance holds `data/rotaoff.lock`; the holder role / pid / start time follows. The OS releases the lock when that process exits; `--force` skips the lock |
| `没有任务被选中，检查 --task / --filter 的写法。` | nothing matched the selection; check `--task` / `--filter` (exit code 1) |
| `任务序号越界: 9（共 3 个）` | task index out of range |
| `data/tasks.json 里没有任务，先运行 python tui.py 配置。` | no tasks configured yet |
| `已选中 N 个任务：` | `--dry-run` selected N tasks, listed below |
| `已跳过 N 张缺少定数的谱面: …（不会用 0 代替）` | N charts had no level (diff) and were excluded from rating, never counted as 0 |
| `有 N 张谱面缺少定数: …` | same case, but the task had `"strict": true`, so it aborts |
| `图片渲染已跳过（…）` | image rendering failed or chromium is missing; text output is unaffected |
| `未知字段: …` / `未知任务类型: …` / `未知输出设置: …` | unknown custom field / task type / output setting |
| `首次记录，下次起可对比` | first snapshot for this profile; run `update` again later to get a diff |
| `无变化` | the save was downloaded successfully but nothing changed since the previous snapshot |
| `找不到歌曲: …` / `没有这首歌的成绩: …` | song alias not found / no score data for this song |
| `已有 RotaOff 在运行` | (see the first row) |
| `再见，记得休息一下眼睛。` | goodbye |

Exit codes: `0` success, `1` error or nothing selected, `130` interrupted with Ctrl+C.
