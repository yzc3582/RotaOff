# AGENTS.md - 反正就是任务

把 RotaBot 魔改成可自动化，保存任务的TUI：

- **“剥离所有 Discord 依赖”**：让它删掉所有 `import discord`，把接收消息的回调函数直接重构成普通的 Python 函数。
- **“直接调用核心计算函数”**：RotaBot 里肯定有计算单谱 Rating 和 B40 的函数，让 AI 把输入源改成读取本地数据库或本地 json 文件，输出直接 `print()` 或者用 `rich` / `textual` 库渲染成漂亮的终端界面。
- **“干掉异步测试”**：TUI 不需要 `asyncio` 那套复杂的生命周期，让它改成纯同步的 `while` 循环，用户敲命令，程序给结果，简单粗暴。
- 另分别为配置任务和仅执行自动化提供独立的用户入口（如单独的py文件）
- 保持代码可读，追求高效复用，而非把大量可能已经存在的功能集成到程序里。
- 同步提供相应的 requirements.txt 及 install_env.bat/sh，省去用户装依赖的麻烦。

提示：`MEMORY.md` 存放记忆、经验等。你可以在需要的时候对其读写。

## 当前状态（2026-11-08）

- 入口：`tui.py`（配置 + 交互）、`run_tasks.py`（纯自动化）、`bot.py`（3 行启动器）。
- 交接文档：`MaterialsForAI/第三次暂歇文档.md`（下一阶段从这里读）。
- `rotaoff/anubis.py` 已抽取：通用「Session + PoW」抓取层，`library.fetch_remote()` 已改用它。
- 当前停在 **下架曲目 B40 排除之前**。**没有明确指令不要提前开工。**
- 离线验证：`.scratch/test_anubis.py`、`.scratch/test_snapshot_diff.py`。

## 硬约束

- `rotaeno/` 只读：只允许随游戏版本改公式（如 Rating 补丁），其它一律在 `rotaoff/` 运行期注入。
- 数据来源（`Songlist.json`、`data/song_data.db`、`wiki/`）版权归 Rotaeno 中文维基，**不入库**。
- 快照只用于对比，不当缓存；`update` 只是「下载 + 对比」，其它命令仍实时取数。
- 自动化 `stdout` 只放数据；摘要 / 轮次 / 失败 / 警告走 `stderr`。
- 用户可见文案改动要同步 `README.md`、`README.zh_CN.md`、`docs/py-all-in-one.en_US.md`。
- 中文回复、简短、一次一个原子改动；用户自己 commit/push。

## 常用命令

```bat
.venv\Scripts\python tui.py
.venv\Scripts\python run_tasks.py --list
.venv\Scripts\python run_tasks.py --dry-run
.venv\Scripts\python .scratch\test_snapshot_diff.py
.venv\Scripts\python .scratch\test_anubis.py
pyright rotaoff\data.py rotaoff\tasks.py rotaoff\patch.py tui.py run_tasks.py
```
