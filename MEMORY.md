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

## 曲库：原 `rotaeno/database/song_data.db` 怎么处理

**结论：不读、不改、当死文件。** 它随上游仓库带，停在 **2.9.0 / 307 首**；客户端 2.99.0，存档 436 首。
缺的 129 首（538 个谱面）没有 `num` 定数，`taptap_processor` 会按 0 分算进 Rating → Rating 被压低（实测 14.5859，真实 14.6931，差 0.1070）。
**这不是 ID 漂移**：129 个缺失 id 里 101 个是曲库完全没有的真新歌，其余是模糊匹配误配。换 ID 映射没用，必须换数据。

新机制（`rotaoff/library.py`，不动 `rotaeno/` 源码）：

- 启动时 `library.ensure()` → 有 `data/song_data.db` 就读它；没有就用 `Songlist.json` 重建；再不行退**内存曲库**；都没有则回上游旧库并在 `library` 里警告。
- `activate(instance)` 会**同时替换两个模块对象**的 `song_data` 属性 ——
  `sys.modules["rotaeno.database.song_data"].song_data` 和 `sys.modules["database.song_data"].song_data`。
  原因是 `rotaeno/api/taptap_processor.py:5-8` 用 `sys.path.insert(ROTAENO_ROOT)` + `from database import song_data`，
  加载出了**第二个模块实例**，两者 `is not`。只换一个，`taptap_processor.py:142` 那条路径仍用旧库 → 静默算错。
- `MemorySongData` 只实现上游真正会调的三个方法：`getAllsong_ids()` / `get_song(id)` / `get_songs_rating_real_range(lo,hi)`。

## 曲库怎么更新（三层回退，用户要能自己拿到数据）

数据源：`https://wiki.rotaeno.cn/index.php?title=Template:Songlist.json&action=raw`
这就是 RotaBot 当初造 db 的同款模板：434 首、含 `ratingClass: 200` 的 IV-α（34 首）、`ratingReal` 就是定数，`release_version` 到 2.99.0。
**曲绘 / 物量都不需要**，Rating/B40 只要 id + 定数 + 分数，所以这是最小充分数据。

1. **自动抓**：`library update`。该站在 Anubis 反爬后面（PoW），三步：
   GET 页面 → 正则取 `<script id="anubis_challenge" type="application/json">`（内容是**双引号包裹的 JSON 字符串，要 `json.loads` 两次**）
   → 暴力 `sha256(randomData + i)` 找以 `"0"*difficulty` 开头的 i → GET
   `/.within.website/x/cmd/anubis/api/pass-challenge?id=<id>&response=<hash>&nonce=<i>&redir=<url>&elapsedTime=1500`
   → 成功种 `techaro.lol-anubis-auth` cookie，同 Session 再 GET raw 即得 JSON。
   **必须带 `id` 参数**，漏了就 HTTP 500 + `techaro.lol-anubis-cookie-verification`。
2. **手动兜底**：浏览器打开上面那个 raw 链接，全选复制存成 `Songlist.json`（UTF-8 无 BOM），`library update --local`。
   沙箱/无网环境一定要走这条。
3. **旧库兜底**：前两层都废就用上游 2.9.0 的库，`library` 里明确警告「缺定数的谱面算不出 Rating」。

重建出的库是 `data/song_data.db`，schema 与上游一致（`songs(id,title,artist,duration,release)` + `song_levels(id, levels_data JSON)`）。
**已验证 `level == num` 在旧库 1242 条里 0 例外**，所以两者写同一个值。落盘失败（`data/` 不可写）自动退内存曲库，会话内照常可用。

## 已确认的事实（别再猜）

- `rotaeno.database.song_data` 的难度键只有 `I` / `II` / `III` / `IV` / `IV_Alpha`，没有 `IN`。
- `rotaeno/__init__.py` → `processor` → `utils`，而 `rotaeno/utils.py` 在**导入期**就 `from playwright.sync_api import ...` 且 `from PIL import Image`。
  ⇒ playwright、Pillow 是硬依赖；chromium 内核只在出图片时需要。
- `rotaeno.processor.get_song_rtr` 的默认定数区间是 `(12.5, 1145)`，`1145` = 不设上限，也是原作者 None1145 的彩蛋。
- `taptap_processor` 遇到缺 diff 的谱面会 `continue`，等于按 0 算进 Rating —— 所以 `rotaoff/tasks.py` 里多了 `_check_diff()`：默认跳过并警告，`strict: true` 才报错。
- `calculate_song_rating` 需要 `levels[...]["num"]`，缺了就没法定数。
- **上游 db 只有 307 首 / 2.9.0**，`github.com/None1145/RotaBot` 上的那份 md5 与本地相同（`eb8ab512550d89ba57ad68f967c0bad8`），拉仓库更新不了曲库。
- LeanCloud 侧没有曲库接口：`classes SongData/Song/...` 全是 `404 code:101`，`/1.1/call/` 的云函数一律 200 但返回 `{}`。
- 云存档里只有分数（`{"levels":{"IV":{"Score","Flag","IsCleared"}}}`），**没有定数**，定数只能来自外部数据。
- 评分公式（`taptap_processor.py:184`）：`sum(top10)*0.6/10 + sum(top[10:20])*0.2/10 + sum(top[20:40])*0.2/20`；
  `:170-176` 有 IV 与 IV_Alpha 二选一（取高者，另一个置 0）。
- 存档里存在 `Sp` 难度（愚人节谱面，目前只有 `true` 这一首），**不计入 Rating**。
  `Songlist.json` 本来就没有 `Sp`，所以 `taptap_processor` 会 `print("Song level \`Sp\` not found ...")`。
  这类噪音连同 `doppelganger` / `terabyte-connection`（wiki 也还没收录）一起被 `fetch_snapshot` 的 stdout 缓冲吃掉，
  正常只出现 3 行，属于预期，不是 bug。`Sp` 分数为 0，不影响 Rating。

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

- 在**正常权限**的机器上复验落盘：本会话 `data/`、`output/` 全程 `PermissionError`，
  所以 `data/song_data.db`、`data/saves/*.msgpack`、`output/*.txt` 都只在内存里通过，
  图片（playwright chromium）也因为起不了子进程而没跑通 —— 这三项需要用户侧确认。
- 图片渲染失败时的提示文案还可以更友好（现在只有一行 warn）。
- `output/` 目录里的历史文件没有清理策略。
- `song -1` 这种「纯编号」输入已经能精确命中 id，但用户输入带空格的曲名时仍只走
  精确匹配 + 模糊回退，没有做别名表。
