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
| `profile set server cn\|global` | switch server (cn / global only; upstream's `private` was never implemented) |
| `login [cn\|global]` | scan-to-login for TapTap |
| `b40` | Best40 table (retired songs excluded automatically) |
| `song <title or alias>` | per-difficulty Rating of one song |
| `status [FC\|AP\|APP\|...]` | list charts by play status |
| `rtr <min> [max] [sort]` | level range, sort = rating/score/level |
| `custom [fields...]` | custom fields, e.g. `custom username rating level` |
| `update` / `refresh` | download the cloud save once and report Rating / per-chart changes since the previous snapshot |
| `tasks` / `task add` / `task rm <index>` / `task run [selection]` | task management |
| `output` / `output set <key> <value>` | output settings (dir, export formats, filename template, image toggle) |
| `library` / `library update [--local]` / `library source <path>` | song library: inspect, rebuild online or offline, repoint the source |
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

Selection rules (`--task` starts a new segment, `--filter` narrows only the current one, all segments are unioned at the end) and the filter expression syntax are documented in [docs/filter.en_US.md](docs/filter.en_US.md) · [中文](docs/filter.zh_CN.md).

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

## The song library (this is what makes Rating correct)

`rotaeno/database/song_data.db` ships with the upstream repo. Upstream describes the project itself as “not updated often — only for major releases or when the developer has time”, so this library has stayed at release 2.9.0 and holds 307 songs. Charts newer than that have no `num` (chart constant); upstream code rates them as 0, so the total is dragged down.

Concrete measurement, so the size of the problem is clear: when yzc3582 (the human author of this fork) ran it in November 2026, the game client was at 2.99.0 and the save held 436 songs. 129 songs / 538 charts had no constant, and the program reported Rating **14.5859** while the game showed **14.6931**. Both numbers are a snapshot of that moment — the gap grows with every release, so do not treat them as fixed values.

This project **never modifies or reads that .db**. On startup `rotaoff/library.py` swaps the `song_data` instance at runtime for a database rebuilt from fresh data. In other words `rotaeno/database/song_data.db` is now a **dead file**: it stays only because upstream code calls `songData(path)`; deleting it is fine as long as `Songlist.json` or `data/song_data.db` exists.

The data comes from the wiki's `Template:Songlist.json` — the very same template RotaBot originally built its db from. It carries song id, title, artist, duration, release version and the constant of every difficulty, IV-α included (`ratingClass: 200`).

> **Licensing**: chart constants are **taken from the [Rotaeno Chinese Wiki](https://wiki.rotaeno.cn/)**, used under
> [CC BY-NC-SA 3.0](https://creativecommons.org/licenses/by-nc-sa/3.0/). This project is non-commercial only;
> if you redistribute derived data, keep the same license and credit the wiki. Neither `Songlist.json`
> nor the rebuilt `data/song_data.db` is committed. Full third-party notices and the list of upstream
> changes live in [`NOTICE.md`](NOTICE.md).

> **Relationship to upstream**: `rotaeno/` started as `None1145/RotaBot` code and is now **maintained here**.
> The one allowed kind of change is following the game's rule updates (e.g. v2.23.0 dropped the extra 0.1
> theoretical-value bonus) inside `rotaeno/api/taptap_processor.py`. Data sources, paths and IO are injected
> at runtime instead of being patched into upstream source.

```bat
library                       :: which library is in use, how many songs / charts
library update                :: fetch the latest Songlist.json and rebuild data/song_data.db
library update --local        :: use only the local Songlist.json (offline)
library source                :: show manual download links for both sources (no download)
library source D:\some\Songlist.json  :: point at a local file
```

Three layers of fallback — if one fails, the next one still works:

1. `library update` first tries `https://wiki.rotaeno.cn/index.php?title=Template:Songlist.json&action=raw` automatically. That site is behind Anubis (a proof-of-work gate); the program solves the hash itself, usually in a few seconds.
2. If fetching fails (no network, site changed, difficulty cranked up) it **falls back to a local file**: `Songlist.json` in the repo root, or whatever `library source` points at. So you always want at least one way to obtain that json.
3. With no local file either, it **falls back to the upstream old db** and warns in `library` that charts without a constant cannot be rated.

To keep layer 2 permanently available, grab a copy by hand:

1. Open <https://wiki.rotaeno.cn/index.php?title=Template:Songlist.json&action=raw> in a browser
2. Select all, copy, paste into `Songlist.json` (UTF-8, no BOM)
3. `library update --local`

> Jackets and note counts are not needed — Rating / B40 only use id, constant and score. This json is therefore the **minimal sufficient dataset** for correct Rating.

The rebuilt library lands in `data/song_data.db` (same schema as upstream: `songs` + `song_levels`); after the first build every start reads it directly and never touches the network. If `data/` is not writable the program degrades to an **in-memory library** (works for this session, must be rebuilt next time) and says so loudly.

That file is **not committed** (see `.gitignore`): it is derived data, and its content belongs to the wiki contributors. Rebuilding it takes one command.

`library` lists both sources:

- **Song library source**: wiki “song constants list” (actual source `Template:Songlist.json`)
- **Song library json**: path to the local `Songlist.json`
- **Retired-song source**: wiki “limited-time song list” (actual source `限时上架曲目列表`)
- **Retired text / db / record count**: `wiki/限时上架曲目列表.txt`, `data/retired_songs.db`, `11 records / 5 retired`

Download links are **not printed by default**. `library update` prints the matching link only when a fetch fails; run `library source` (`db source` is the same command) to show both links without downloading:

```text
Songlist.json manual download: https://wiki.rotaeno.cn/index.php?title=Template:Songlist.json&action=raw
Retired-song list manual download: https://wiki.rotaeno.cn/index.php?title=限时上架曲目列表&action=raw
```

`library update` refreshes the retired-song db as well; `--local` uses the local text and stays offline.

## Retired songs

When a limited-time song is retired, all of its charts stop counting toward Rating / Completion. `b40` excludes them automatically:

- Source is the wiki “限时上架曲目列表”; `library update` fetches, cleans and writes it to `data/retired_songs.db` (`--local` uses the local text, no network)
- On first run the bundled `rotaeno/database/retired_songs.db` is copied as a seed; RotaOff maintains it from then on
- Only songs whose retirement date is **<= today** are excluded; the “on sale” table keeps playing even if it lists a future date
- Only Rating / B40 ranking is affected; `song` / `status` / `rtr` still show those charts
- The `b40` table and image both read the same `data/retired_songs.db`, so the image no longer includes retired songs
- If the list cannot be read or a title does not match the library, RotaOff warns instead of silently pretending the exclusion worked

## Save snapshots and changes

Every query still **downloads the cloud save in real time** and never reads a local cache. So that “what changed since last time?” can be answered, each successful download overwrites `data/saves/<profile>.json` with `playerInfo + songDatas + fetchedAt`, keeping only the latest copy; **a failed download never overwrites the previous snapshot**.

Run `update` (alias `refresh`) to ask for the comparison explicitly — it only does “download + diff”, with no caching semantics.

- `cloud_updated_at` — the CloudSave object's `updatedAt` (converted to your machine's local time), i.e. when the game synced the save to TapTap; this is the field that tells you whether there is new data
- `fetched_at` — when this machine downloaded it; changes on every run
- `rating_diff` — e.g. `14.7025+0.0094`; a zero delta is still printed as `+0.0000`, and the first record says “first snapshot, comparable from next time”
- `songs_diff` — e.g. `Title (IV): 1,001,551 → 1,006,012 (+4,461)｜13.7551 → 14.5020｜NONE(C) → AP(-)`; “no changes” when nothing moved

Status always carries a suffix: `(C)` = cleared, `(-)` = not cleared. The `Flag` and whether a chart is cleared are independent facts, so `AP(-)` (an AP flag on a chart the save reports as not cleared) can legitimately show up as historical dirty data; it is not a display bug. `NONE(-)` means never played or not cleared.

How changes are surfaced:

- **Interactive** (`tui.py`): after a download, `b40` / `custom` append a one-line summary when the save differs from the previous snapshot (e.g. `云存档有变化：Rating 14.7025+0.0094，2 个谱面有变化`); nothing is printed when nothing changed. `update` already reports the full detail, so it does not append the summary again.
- **Automation** (`run_tasks.py`): change summaries, round messages, failures and warnings **all go to stderr**; stdout keeps result data only (tables, `--quiet` lines, exported file paths), so pipes and OBS never get interleaved status noise.
- `song` / `status` / `rtr` still call upstream processors directly and do not run the snapshot diff, so they do not produce the automatic summary yet.

## Documentation

- [`docs/py-all-in-one.en_US.md`](docs/py-all-in-one.en_US.md) — every user-visible message and option in English
- [`docs/filter.en_US.md`](docs/filter.en_US.md) — task selection and filter expressions
- [`docs/filter.yzc3582.fake.cpp`](docs/filter.yzc3582.fake.cpp) — the original pseudocode the selection rules came from

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

Released under the [MIT License](LICENSE).

This project is a fork of [None1145/RotaBot](https://github.com/None1145/RotaBot). The original project shipped no standard LICENSE file, but its README explicitly allowed modification and redistribution, so this fork keeps the original attribution and is released under MIT.

