# MEMORY

给未来的自己（或下一个 AI）看的备忘。这里只记结论和坑，不放任何账号、token、objectID。

## 项目约定

- `rotaeno/` 是上游 `None1145/RotaBot` 的代码，**保持只读**，所有改动都在 `rotaoff/` 里。
- 设计目标：无 Discord、无 asyncio、任务可保存、可交给 `run_tasks.py` 自动跑。
- 入口：`tui.py`（交互）、`run_tasks.py`（自动化）、`bot.py`（3 行启动器，等同 `tui.py`）。
- 文档：`README.md`（英文）/ `README.zh_CN.md` 在根目录；`docs/` 下放 `filter.zh_CN.md` /
  `filter.en_US.md`、`filter.yzc3582.fake.cpp`（选择语义的原始伪代码）、`py-all-in-one.en_US.md`（英文提示汇总）。
  `AGENTS.md` 是工具固定读取的文件名，不套 `*.zh_CN.md` 规则。
- **文档面向所有人**：不写「我的账号」「你现在是 2.99」这种把某次测试当普适事实的说法，
  需要举例就写「yzc3582（人类方作者）当时测试的版本是 2.99」。任何人 clone 下来都应该能照着跑。
- **同步规则**：`docs/py-all-in-one.en_US.md` 是英文提示的唯一汇总。任何新增或修改的用户可见文案
  （`data/i18n/*.json` 的 `t()` 键、`tui.py` 的 `HELP`、`run_tasks.py` 的 help/epilog、任务向导的提问）
  都必须同步更新它，否则英文用户看到的清单就和程序不一致了。
- **`.gitignore` 覆盖派生数据**：`[sS]onglist.json`、`data/song_data.db(.tmp)`、`data/player_data.db`、
  `data/saves/`、`data/temp/` 都不入库 —— 内容源自 wiki / 游戏，版权不归本项目，避免「意外二次分发」。
  这些文件全都能用 `library update` 或首次运行自动重建，所以不入库不影响任何人使用。

## 上游修补：`rotaoff/patch.py`

`rotaeno/` 只读，所以运行时打补丁，`rotaoff/__init__.py` 导入时调用一次 `install()`。

- **P0 根因（已修）**：`BaseAPI` 里是 `f"{self.base_url}/{endpoint}"`，而 endpoint 自己以 `/` 开头，
  拼出 `https://host//1.1/classes/CloudSave`。网关把双斜杠当另一条路由 → 404 + 空响应体 →
  上层只剩一句 `JSONDecodeError: Expecting value: line 1 column 1`。
  以前 b40 / song / rtr / status 全挂同一个错，就是这个。
  `patch._request()` 改成 `f"{base_url}/{endpoint.lstrip('/')}"`，并接管 `get/post/put`。
- 顺带把「请求失败看不见原因」也修了：非 JSON 响应现在报 URL + 状态码 + 响应体字节数，
  超时报「请求超时（20 秒）」，不再是一句没信息量的异常。
- `patch.redirect_upstream_dirs()` 把上游写死的 `saves/`、`temp/` 重定向到 `data/` 下。

## `profile set` 的字段名（别再犯）

三处清单曾经各说各话：`help` 写短名（`server`/`objectid`/`session`）、`tui` 把输入 `.lower()`、
`store.PROFILE_FIELDS` 存 camelCase → 只有本来就小写的 `locale` 能保存成功。
现在 `store.PROFILE_ALIASES` + `store.normalize_profile_field()` 是唯一对照表，大小写不敏感，
认不出来时**原样返回**用户输入（报错能照抄那个词），合法性由 `field in PROFILE_FIELDS` 判断。
`set_profile_field()` 返回三元组 `(真实字段名, 是否可用, 消息键)`，改动时记得同步 `tui.py` 的 `login`。


## 曲库：原 `rotaeno/database/song_data.db` 怎么处理

**结论：不读、不改、当死文件。** 它随上游仓库带，最新一首是 2.9.0 的曲子，共 307 首，上游已不再维护。
举例说明量级（**只是那一刻的快照，别当普适事实写进文档**）：yzc3582（人类方作者）2026-11 实测时客户端是 2.99.0、存档 436 首，
缺的 129 首（538 个谱面）没有 `num` 定数，`taptap_processor` 会按 0 分算进 Rating → Rating 被压低（程序 14.5859，游戏 14.6931，差 0.1070）。
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
这就是 RotaBot 当初造 db 的同款模板，`ratingReal` 就是定数，含 `ratingClass: 200` 的 IV-α。
（2026-11-05 抓到的那份：434 首 / 34 首 IV-α / `release_version` 最高 2.99.0。数字会随版本变，别当常量写死。）
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
- 存档是**全量**的：没打过的谱也在里面（分数 0），所以下面这些警告跟「你查了哪一首」「有没有玩过」都无关。
- `Sp` 是**非常规谱面的总称**，不是「愚人节谱面」：旅程小游戏、愚人节、Stasis / Quadruplicity 的解禁谱都归这一类，
  一律**不计入 Rating**。`true` 的小游戏谱在存档里的难度键就是 `Sp`，游戏准备界面显示为 `- O v e r l o a d -`。
  `Songlist.json` 本来就没有 `Sp`，所以 `taptap_processor` 会 `print("Song level \`Sp\` not found ...")`。
  这类噪音连同 `doppelganger` / `terabyte-connection`（wiki 也还没收录）一起被 `fetch_snapshot` 的 stdout 缓冲吃掉，
  正常只出现 3 行，属于预期，不是 bug。`Sp` 分数为 0，不影响 Rating。
- 这 3 行噪音以前只有 `b40`（走 `data.fetch_snapshot()`）被 `redirect_stdout` 吃掉，
  `song`/`status`/`rtr` 直调 `rotaeno.processor` 时漏到主输出。现在统一走 `data.quiet_call()`：
  静音的同时把内容记进 `data._UPSTREAM_NOTES`，`data.missing_from_library()` 解析成
  `{songs, levels}`，由 `library` 命令底部展示。**注意**：记录是进程内的，
  所以要先查一次存档，`library` 才有内容可显示。

## 选择语义（最容易记错的地方）

以 `docs/filter.yzc3582.fake.cpp` 为准：初始集合是 `*`；每个 `--task` 开新段（先把「被动过的」当前段收进 `segments`），`--filter` 只筛当前段，最后取并集。

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

## 还没做的（下次从这里继续）

**1. 真实账号的端到端没跑过**（最重要）。patch 修掉双斜杠后只推断到「请求能发出去」，
还没有一次成功出数的记录。跑 `.venv\Scripts\python tui.py` → `b40`，核对三件事：
Rating 与游戏内是否一致；`song <新曲>` 在缺定数时给提示而不是 0 分；`rtr` 的区间语义。

**2. 锁：不是 bug（已排除）**。2026-11-06 那次 `已有 RotaOff 在运行: tui (pid 5860)` 是用户自己后台跑的实例忘了关，
`filelock` 报得对。**教训**：`--force` 不是「清理陈旧锁」的开关，而是「明知有实例在跑还要并行」——
两个实例同时写 `output/` 会互相覆盖。真要用，先确认那个 pid 已经退出。

**3. 小问题**
- `task add` 第一轮实测存进了 `b40,b40,b40`，字段没校验也没去重（这轮未复核是否已加）。
- argparse 的 `usage:` 行中英混排折行参差：它按字符数算宽度，不是显示宽度，纯外观问题。
- 图片渲染失败的提示只有一行 warn，应区分「playwright chromium 缺失」和「无子进程权限」。
- `output/` 里的历史文件没有清理策略。
- 曲名带空格时只走精确匹配 + 模糊回退，没有别名表。

**4. 文档同步**：新增 `library` 系列命令后，`HELP_ZH`/`HELP_EN`、`README(.zh_CN)`、
`docs/py-all-in-one.en_US.md` 是否都覆盖了 `library` / `library update` / `library source`；
以及 `profile set` 现在认短名和任意大小写这件事，也应写进英文汇总。
