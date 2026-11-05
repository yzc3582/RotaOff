# MEMORY

给未来的自己（或下一个 AI）看的备忘。这里只记结论和坑，不放任何账号、token、objectID。

## 项目约定

- `rotaeno/` 是上游 `None1145/RotaBot` 的代码，**保持只读**，所有改动都在 `rotaoff/` 里。
- 设计目标：无 Discord、无 asyncio、任务可保存、可交给 `run_tasks.py` 自动跑。
- 入口：`tui.py`（交互）、`run_tasks.py`（自动化）、`bot.py`（3 行启动器，等同 `tui.py`）。
- 文档：`README.md`（英文）/ `README.zh_CN.md`、`filter.zh_CN.md` / `filter.en_US.md`、`py-all-in-one.en_US.md`（英文提示汇总）。
  `AGENTS.md` 是工具固定读取的文件名，不套 `*.zh_CN.md` 规则。
- **同步规则**：`py-all-in-one.en_US.md` 是英文提示的唯一汇总。任何新增或修改的用户可见文案
  （`data/i18n/*.json` 的 `t()` 键、`tui.py` 的 `HELP`、`run_tasks.py` 的 help/epilog、任务向导的提问）
  都必须同步更新它，否则英文用户看到的清单就和程序不一致了。

## 已确认的事实（别再猜）

- `rotaeno.database.song_data` 的难度键只有 `I` / `II` / `III` / `IV` / `IV_Alpha`，没有 `IN`。
- `rotaeno/__init__.py` → `processor` → `utils`，而 `rotaeno/utils.py` 在**导入期**就 `from playwright.sync_api import ...` 且 `from PIL import Image`。
  ⇒ playwright、Pillow 是硬依赖；chromium 内核只在出图片时需要。
- `rotaeno.processor.get_song_rtr` 的默认定数区间是 `(12.5, 1145)`，`1145` = 不设上限，也是原作者 None1145 的彩蛋。
- `taptap_processor` 遇到缺 diff 的谱面会 `continue`，等于按 0 算进 Rating —— 所以 `rotaoff/tasks.py` 里多了 `_check_diff()`：默认跳过并警告，`strict: true` 才报错。
- `calculate_song_rating` 需要 `levels[...]["num"]`，缺了就没法定数。

## 选择语义（最容易记错的地方）

以根目录 `filter.yzc3582.fake.cpp` 为准：初始集合是 `*`；每个 `--task` 开新段（先把「被动过的」当前段收进 `segments`），`--filter` 只筛当前段，最后取并集。

注意两个反直觉点：

1. 初始的 `"*"` 只有被改动过才会单独成段，否则会被丢掉——不然并集永远是全部任务。
2. `--task 1,3 --filter "i % 2 == 1"` 这种例子**看不出 filter 的作用**（1、3 本来都是奇数）；文档里统一改用 `--task 1-3 --filter "i % 2 == 1"`。

## 踩过的坑

- 手写 pid 锁（`OpenProcess` 探活）是重复造轮子，而且「锁龄 > 12h 算陈旧」会把常驻的 `--interval` 误判成可以抢占。现在用 `filelock`，由操作系统保证进程退出即释放。
- 测试里用 `json.dump(..., open(path,'w'))` 不 close，缓冲没落盘；子进程读到空文件 → 被判成「没有锁」。写测试要用 `pathlib.write_text`。
- 一次调用里同时跑「写锁」和「删锁」的两条命令会并行执行，测试结果会互相破坏；涉及副作用的验证要串行。
- `%errorlevel%` 在同一条 `&` 命令里会被提前展开，判断退出码要写成 `命令 & if errorlevel 1 (...)`。

## 验证过的命令

```bat
.venv\Scripts\python run_tasks.py --list
.venv\Scripts\python run_tasks.py --dry-run
.venv\Scripts\python run_tasks.py --task 1,3 --filter "i % 2 == 1" --dry-run
.venv\Scripts\python run_tasks.py --task 9 --dry-run      :: 退出码 1，提示序号越界
.venv\Scripts\python run_tasks.py --force --dry-run       :: 已有实例持锁时也能跑
```

- i18n：`zh-CN.json` 与 `en-US.json` 键集合一致（39 条），缺键会依次回退到 `zh-CN` → 原始 key。
- 导出：`txt` / `md` / `csv` / `json` 与 `latest` 固定名副本都测过，CJK 表格宽度对齐正常。

## 还没做的

- 真实账号下的端到端跑一遍（`login` + `b40` + 图片渲染），需要有效 sessionToken。
- 图片渲染失败时的提示文案还可以更友好（现在只有一行 warn）。
- `output/` 目录里的历史文件没有清理策略。
