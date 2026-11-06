# RotaOff

**语言 / Language**：[简体中文](README.zh_CN.md) · [English](README.md)

基于 [None1145/RotaBot](https://github.com/None1145/RotaBot) 的离线查数值工具（用于直播展示 Rating）。

（又是一个 Vibe Coding 项目……）

和原版相比，这一版：

- **没有 Discord**：不 `import discord`，原来的消息回调被拆成了普通函数
- **没有异步**：纯同步 `while` 循环，敲命令 → 出结果
- **能保存任务**：把「查什么、怎么导出」写成 `data/tasks.json`，交给 `run_tasks.py` 定时跑

计算部分直接复用仓库里的 `rotaeno/`（未做修改）：单谱 Rating、B40、状态筛选都是它的函数，只是输入从 Discord 交互换成了本地配置。

## 安装

```bat
install_env.bat
```

脚本会建 `.venv` 并装依赖；装完会**询问**要不要顺便下载 chromium 内核（只有“生成图片”才需要，约 150MB，默认不下）。

Linux / macOS 用 `./install_env.sh`，参数一样。手动安装：

```bat
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
```

> `rotaeno/utils.py` 在导入时就 `from playwright.sync_api import ...`，所以 playwright 和 Pillow 属于硬依赖；不装 chromium 内核只会让图片功能不可用，文本查询照常。

## 快速开始

```bat
.venv\Scripts\python tui.py          :: 交互界面（配置账号、建任务、随手查）
.venv\Scripts\python bot.py          :: 等同 tui.py，留着方便老用户
.venv\Scripts\python run_tasks.py    :: 把 data/tasks.json 里的任务跑一遍
```

第一次运行如果没有 `data/users.json` / `data/tasks.json`，会从 `*.example.json` 复制一份。

三步上手：

1. `login` —— 扫码登录 TapTap，自动填好 `serverCode` / `objectID` / `sessionToken`
2. `task add` —— 按提示建一个任务（B40、单曲、状态、定数区间、自定义字段）
3. `run_tasks.py` —— 不用再管交互，直接出结果

## 命令一览（tui.py）

| 命令 | 作用 |
| --- | --- |
| `profile` / `profile use <名>` / `profile new <名>` | 查看、切换、新建玩家配置 |
| `profile set server cn\|global` | 换服务器（只支持国服/国际服；上游的 `private` 是半成品，本项目不支持） |
| `login [cn\|global]` | 扫码登录 TapTap |
| `b40` | Best40 表格 |
| `song <曲名或别名>` | 单曲各难度 Rating |
| `status [FC\|AP\|APP\|...]` | 按成绩状态列曲目 |
| `rtr <下限> [上限] [排序]` | 指定定数区间，排序 = rating/score/level |
| `custom [字段...]` | 自定义字段，如 `custom username rating level` |
| `tasks` / `task add` / `task rm <序号>` / `task run [选择]` | 任务管理 |
| `output` / `output set <项> <值>` | 输出设置（目录、导出格式、文件名模板、图片开关） |
| `library` / `library update [--local]` / `library source <路径>` | 曲库：看用的哪份、联网或离线重建、换源 |
| `interval <秒>` | 自动化间隔，0 = 只跑一次 |
| `save` | 立刻导出当前结果 |
| `help` / `quit` | —— |

## 自动化

```bat
python run_tasks.py --list                      :: 看任务列表
python run_tasks.py --dry-run                   :: 只看会跑哪些，不真跑
python run_tasks.py --task 1,3                  :: 只跑 1、3
python run_tasks.py --task 1-5 --filter "i % 2 == 0"   :: 只留偶数号：2、4
python run_tasks.py --interval 300              :: 每 5 分钟一轮，Ctrl+C 停止
python run_tasks.py --save txt,md --image       :: 临时改导出格式 / 开图片
```

选择规则（`--task` 开新段、`--filter` 只筛当前段、最后求并集）和过滤表达式的写法见 [docs/filter.zh_CN.md](docs/filter.zh_CN.md) · [English](docs/filter.en_US.md)。

## 配置

`data/tasks.json` 结构：

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
        { "name": "我的 B40", "type": "b40", "profile": "default" }
    ]
}
```

- `output.export` —— 留空只打印；可选 `txt` / `md` / `csv` / `json`，可多选
- `output.template` —— 文件名模板，可用 `{type}` `{name}` `{profile}` `{stamp}`
- `output.latest` —— 比如 `"{type}-latest"`，额外写一份固定名字的副本，方便 OBS 一直读同一个文件（写入是先写 `.tmp` 再 `os.replace`，不会读到半截）
- `tasks[].profile` —— 用哪个玩家配置，省略则用当前的
- `tasks[].export` / `image` / `template` / `limit` / `strict` —— 按任务覆盖全局设置

任务类型：`custom`（自定义字段）、`b40`、`song_info`（单曲）、`song_status`（按状态）、`song_rtr`（定数区间）。

> `song_rtr` 不写 `level_max` 就是**没有上限**（内部默认值 1145，是原作者 None1145 的彩蛋）。以后出了 14.9 的谱也不用改代码；想限上界就显式写 `"level_max": 15`。

## 本地化与兜底

文案放在 `data/i18n/`，目前有 `zh-CN.json` 和 `en-US.json`；用哪个由玩家配置里的 `locale` 决定（`profile set locale en-US`）。

`rotaoff/i18n.py` 的查找顺序是**逐级回退**，所以少写几条不会让程序崩：

1. 请求的语言里找这个 key（例如 `en-US`
2. 找不到就查 `zh-CN`
3. 还找不到就把 **key 原样显示**（这样一眼能看出漏翻，而不是显示空白）

占位符用 `{name}` 这种写法，取值时用 `t("task-added", name="B40")`；万一传的参数对不上，会退回未格式化的原句，不会抛异常。

加新文案时只需要写 `zh-CN.json`，`en-US` 缺的键会自动回退成中文；想补英文照同样 key 加一条即可。

## 曲库（Rating 算得准不准全看这里）

`rotaeno/database/song_data.db` 是上游随仓库带的库。上游对项目本身的说法是「不会经常更新，仅在有重大更新或开发者有时间时维护」，所以这份库长期停在 2.9.0，共 307 首。比它新的曲目，每个谱面都没有定数（`num`），上游代码会按 0 分算进 Rating，于是总分被系统性压低。

给个具体量级：yzc3582（本分支的人类作者）在 2026 年 11 月实测时，游戏客户端是 2.99.0，存档 436 首，其中 129 首 / 538 个谱面没有定数，程序算出 Rating **14.5859**，游戏里显示 **14.6931**。这两个数字只是那一刻的快照——每出新曲差距都会变大，别当成固定值。

本项目**不改 `rotaeno/` 里那份 .db**，也不读它：启动时由 `rotaoff/library.py` 在**运行期**把 `song_data` 实例换成用新数据重建的库。也就是说 `rotaeno/database/song_data.db` 现在是**死文件**，留着只为兼容上游代码里的 `songData(path)` 签名；删掉也没关系，只要 `Songlist.json` 或 `data/song_data.db` 还在。

数据来源是 wiki 的 `Template:Songlist.json`（和 RotaBot 当初造 db 用的是同一份模板），包含曲目 id、曲名、曲师、时长、上架版本，以及全部难度的定数（含 IV-α，`ratingClass: 200`）。

> **版权**：定数数据**摘自 [Rotaeno 中文维基](https://wiki.rotaeno.cn/)**，依 [CC BY-NC-SA 3.0](https://creativecommons.org/licenses/by-nc-sa/3.0/) 使用。
> 本项目仅作非商业用途；若你对外分发由这些数据派生的成果，请沿用同一许可并保留出处。
> 抓取下来的 `Songlist.json` 与重建出的 `data/song_data.db` 都不进版本库。
> 完整的第三方声明与我们对上游代码的修改清单见 [`NOTICE.md`](NOTICE.md)。

> **与上游的关系**：`rotaeno/` 原本是 `None1145/RotaBot` 的代码，本项目**接管维护**。
> 改动范围只有一处：当游戏规则随版本变化时（例如 v2.23.0 取消理论值额外 0.1 补正），
> 在 `rotaeno/api/taptap_processor.py` 里跟进公式；数据来源、文件路径与 IO 一律在运行期注入，不改源码。

```bat
library                       :: 现在用的是哪份库、多少首、多少谱面
library update                :: 联网抓最新 Songlist.json 并重建 data/song_data.db
library update --local        :: 只用仓库根目录的 Songlist.json（不联网）
library source D:\some\Songlist.json  :: 指定本地文件位置
```

三层回退，任何一层挂了都还有下层：

1. `library update` 先试着从 `https://wiki.rotaeno.cn/index.php?title=Template:Songlist.json&action=raw` 自动抓。该站有 Anubis 反爬（工作量证明），程序会自己算 hash 过验证，一般几秒内完成。
2. 抓不到（网络不通、站点改版、难度调到算不出来）→ **回退到本地**：根目录的 `Songlist.json`，或 `library source` 指定的路径。所以你必须至少有一种拿到这个 json 的方式。
3. 连本地文件都没有 → **回退到上游旧库**，并在 `library` 里警告「缺定数的谱面算不出 Rating」。

想让第 2 步永远可用，手动拿一份就行：

1. 浏览器打开 <https://wiki.rotaeno.cn/index.php?title=Template:Songlist.json&action=raw>
2. 全选复制，粘到 `Songlist.json`（UTF-8，不要 BOM）
3. `library update --local`

> 曲绘、谱面物量都不需要 —— Rating / B40 只用到 id、定数与分数。所以这个 json 是「能算对 Rating」的**最小充分数据**。

重建出来的库落在 `data/song_data.db`（与上游同 schema：`songs` + `song_levels`），第一次之后每次启动直接读它，不再联网。`data/` 不可写时程序会自动退化为**内存曲库**（本次会话照常能算，重启要重来），并明确警告。

这份库**不进版本库**（见 `.gitignore`）：它是派生数据，内容版权归 wiki 的贡献者。要重建一条命令就够。

## 文档都在 `docs/`

- [`docs/filter.zh_CN.md`](docs/filter.zh_CN.md) / [`docs/filter.en_US.md`](docs/filter.en_US.md) —— 任务选择与过滤表达式
- [`docs/filter.yzc3582.fake.cpp`](docs/filter.yzc3582.fake.cpp) —— 选择规则最初的伪代码
- [`docs/py-all-in-one.en_US.md`](docs/py-all-in-one.en_US.md) —— 全部英文提示与选项的汇总

## 同时只能开一个

`tui.py` 和 `run_tasks.py` 会写同一份 `data/tasks.json`，所以启动时用 `filelock` 对 `data/rotaoff.lock` 加互斥锁：

- 已有实例在跑 → 拒绝启动，并打印占用者（角色 / pid / 启动时间）
- 锁由操作系统管理，**进程退出（包括崩溃、被强杀）时自动释放**，不用手动删锁，常驻的 `--interval` 也不会被误判
- 想确认是谁占着，可以看 `data/rotaoff.lock.info`；确认对方不在时也可以加 `--force` 跳过锁，但两个实例同时写输出会互相覆盖

## 关于数据

- 一次请求拿 `playerInfo` + `songDatas`，然后本地算，减少被限流的概率
- 缺标题 / 曲师 / 状态时显示 `【无数据】`，不会去下载素材
- **定数（diff）缺失的谱面不会被“当 0 分”混入 Rating**：默认跳过并警告，任务里写 `"strict": true` 则直接报错

## 📜 开源协议

本项目采用 [MIT License](LICENSE) 协议开源。

本项目是基于 [None1145/RotaBot](https://github.com/None1145/RotaBot) 的 Fork 版本。由于原项目未附带标准 LICENSE 文件，但原作者在 README 中明确声明允许自由修改与分发，因此本衍生项目在保留原作者署名的基础上，采用 MIT 协议进行开源。

