# MEMORY

给未来的自己（或下一个 AI）看的备忘。这里只记结论和坑，不放任何账号、token、objectID。

## 项目约定

- `rotaeno/` 是上游 `None1145/RotaBot` 的代码，**我们接管维护，但改动范围有硬边界**：
  - **只**在「上游规则随游戏版本变化」时才改（公式、机制、判定阈值），改完在本文件记下依据的 wiki 条目与版本号；
  - **不改**数据来源、文件路径、目录布局、IO 方式——这类一律走**运行期注入**。正例：
    `rotaoff/library.py` 在 import 之后替换 `song_data` 实例，而不是去改源码里写死的 db 路径；
  - 理由：保住「非官方客户端」的可替换性。上游哪天更新，我们这些补丁可以直接对照或丢弃。
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

## 维基内容使用与版权（先读这一节）

本项目用到的曲库数据与规则说明都来自 **Rotaeno 中文维基**，授权为 **CC BY-NC-SA 3.0**；
该站另有明确要求：**任何引用都必须标注“摘自 Rotaeno 中文维基”**，未标注视为侵权。

| 用到的内容 | 来源条目 | 我们的处理 |
| --- | --- | --- |
| 曲目定数与谱面信息（`Songlist.json`） | 模板 `Template:Songlist.json` | 不随仓库分发：`.gitignore` 忽略 `[sS]onglist.json`、`data/song_data.db` |
| Rating 规则（单谱补正系数、b40 权重与取舍） | 条目「Rating」 | 只复述算法与常数，不整段搬运原文 |
| 限时上架 / 下架曲目名单 | 条目「限时上架曲目列表」 | 同上，不入库 |
| 原始抓取件（`wiki/*.txt`） | 上述条目 | `.gitignore` 忽略整个 `wiki/`，仅供本地阅读 |

- 面向用户的文档（`README*` 等）只要提到这些数据来源，就必须同时写出“摘自 Rotaeno 中文维基”和条目链接。
- **NC**：本项目不得用于商业用途；**SA**：若对外分发由维基内容改写的成果，需沿用同一许可。
- 拿不准就按“只在本地用、不写进仓库”处理；`Songlist.json` 和重建出的 `song_data.db` 都属这一类。



依据 `wiki/rating-source.txt`（wiki「Rating」条目存档，**版权原因不入库**，见 `.gitignore` 的 `wiki/`）：
摘自 Rotaeno 中文维基（CC BY-NC-SA 3.0），<https://wiki.rotaeno.cn/index.php?title=Rating>。

- **v2.23.0**：取消「理论值的额外 0.1 补正系数」→ 满分段补正 `+3.7` 改 `+3.6`；
  1008000~1009999 段分母 `10000` 改 `9995`（段末 3.5999 → 3.6，与满分段连续）。
  已改 `taptap_processor.calculate_song_rating`，用 wiki 关键节点验证通过：
  1010000→+3.6、1008000→+3.4、1004000→+2.4、1000000→+2、980000→+1、
  950000→0、900000→−1、800000→−2、700000→−3、500000→−5。
- 原本就正确，别动：单谱 Rating 下限 0；未通关且算出 >6 时封顶 6；IV/IV-α 只保留高者。
- **未跟进的规则**：
  - b40 递补：**实测等价，不用改**。`taptap_processor` 是「先置 0（:178-182）再排序（:188）」，
    低者被置 0 后沉到队尾，`[:40]` 自然由第 41 名补上，与 wiki 的「保留高者 + 依次递补」结果相同
    （构造 50 张谱含 3 组冲突的对照：两种算法都得 15.8337）。别被"少算一个名额"的说法带偏。
  - **已下架曲目不计入 b40**（例：六兆年と一夜物語 IV-α 定数 14.3，2026-06-30 后下架）。
    数据源：`wiki/限时上架曲目列表.txt`（同样版权原因不入库）。`Songlist.json` 没有下架字段，
    需要自己维护这份名单。



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

**结论：不读、不改、当死文件。** 它随上游仓库带，最新一首是 2.9.0 的曲子，共 307 首。
注意措辞：上游**没有**弃坑，只是"不会经常更新，仅在有重大更新或开发者有时间时维护"，
所以这份 db 长期停在 2.9.0。写文档时别把"更新慢"说成"不再维护"。
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
- Rating 显示口径：我们（沿用上游 RotaBot）**显示 4 位小数**；官方游戏只显示 3 位且**直接截断**。
  所以拿界面数字对照时，游戏那边天生比我们少一位，别把「位数不同」当成计算偏差。
  单曲 Rating 在表格里显示 2 位，同样只是展示，排序/求和一律用 `ratingMix` 全精度。
- 评分公式（`taptap_processor.py:190`）：`sum(top10)*0.6/10 + sum(top[10:20])*0.2/10 + sum(top[20:40])*0.2/20`；
  `:178-182` 有 IV 与 IV_Alpha 二选一（取高者，另一个置 0）。
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
- **`WinError 5` 替换 `data/song_data.db` 失败**：不是「忘了 `conn.close()`」。上游 `database/song_data.py:25`
  用 SQLAlchemy `create_engine`，engine 是进程级连接池，**只建好、还没查询**就已经抓着文件句柄，
  同进程里 `os.replace` 必然被 Windows 拒绝。实测对照（`.scratch/winerror_probe.py`）：
  无实例 → OK；`create_engine` 后 → `PermissionError winerror=5`；`engine.dispose()` 后 → OK。
  现由 `library._replace_database()` 先 `dispose_active()` 再替换，并重试 3 次兜住杀毒软件。
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

## 暂停后的待办队列（按用户定的顺序）

**0. private 服务器：已定案「不支持」**（2026-11-06）。已写进 `tui.py` 帮助（中/英）与两版 README 的
`profile set server` 行。事实依据：`rotaeno/api/taptap.py:7-38` 的 `ServerRegion` 只有 `CN`/`GLOBAL`，
`else: raise ValueError("Invalid region")`——上游 Discord 版的「私有服务器」选项本身就是半成品，
我们没有支持它，不是砍功能。

**1. `/r update` 等价物（QQ 端 RotaBot 有，Discord 上游没有）**
- QQ 端那个 `/r update` 拉的是**云存档**，不是曲库；QQ 端会缓存用户数据，所以才需要手动刷新。
- 本项目每条命令都实时拉云存档，缺的不是「拉数据」，而是**显式刷新/缓存语义 + 让用户看见新鲜度**。
- 同一批要做：**结果里显示 `TIME`（云存档同步时间）**。数据已经存在：
  `taptap_processor.py:272` 产出 `updateAt = user_data["updatedAt"]`，全仓库无人消费
  （`findstr updateAt` 只有这一处），所以这一步基本是展示层改动。
- 排在 Anubis 之前。

**2. Anubis PoW 拆成独立模块**：目前内嵌在 `library.py`，下架曲目功能要复用同一套
「会话 + 挑战流程」，所以先拆再复用。

**3. 下架曲目排除出 b40**：数据源 `wiki/限时上架曲目列表.txt`，仍然只在运行时获取、不进仓库。

**上游回推状态**：我们改的两处常数已于 2026-11-06 提交给 `None1145/RotaBot` 的 PR #1
（标题「借助 wiki.rotaeno.cn，修复上游的 Rating 计算公式」；单补丁分支 `fix/for-upstream`），**未合并**。
patch 统计 `12 insertions(+), 3 deletions(-)` 与本地 `git diff --stat rotaeno` 完全一致，两边没有分叉。

**合并后要做什么（别误会成 revert）**：本仓库的 `rotaeno/` 是上游副本，合并后上游那份文件
与我们逐字相同，**不存在要回退的差异，也不要 `git revert`**（那会把 `+3.6` / `/9995` 退回旧值，
Rating 又会偏）。真正要做的只是两件记账的事：
① `NOTICE.md` 第 2 节那几行从「我们的修改」改述为「已随上游版本生效」；
② 将来整体同步 `rotaeno/` 覆盖目录时，**不用再记得重打这几处补丁**，也不会因此退回旧常数。

**别再记错**：`login` **是有扫码的**（`tui.py:193-204` 用 `taptap_auth.TapTapLogin` 出二维码并回填三项），
不要再说「qrcode 没搬」。上游顶层命令只有 `login` / `b40` / `song` / `rtr` 四组，**没有 update**；
文件里出现的 `update` 都是内部函数 `update_user_datas()`（`upstream_bot.py:65`，写 `users.json`）。
