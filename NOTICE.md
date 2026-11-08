# NOTICE — 第三方内容、数据来源与修改声明

本文件说明本仓库各部分内容的权利归属，以及我们对上游代码做过哪些改动。
代码许可见 `LICENSE`（MIT，Copyright © 2026 yzc3582；上游部分 © 2025 None1145）。

## 1. 本项目自身

- 本项目**不发布 Release**，也**不把 wiki 内容放进仓库或任何发布物**。
- `wiki/`、`[sS]onglist.json`、`data/song_data.db` 均在 `.gitignore` 中；
  需要这些数据时由使用者在**本机**自行获取或生成，仓库本身不携带。
- 因此本仓库的分发物只包含代码，采用 MIT 许可；上述数据不受本项目的 MIT 许可覆盖。

## 2. 上游代码：`rotaeno/`

- 来源：**None1145 / RotaBot**（MIT），版权归原作者。
- 我们对它的改动只有一类：**跟随游戏规则版本变更**修改计算规则。
  数据来源、文件路径、目录布局、IO 方式一律**不改源码**，改在运行期注入
  （例：`rotaoff/library.py` 在导入后替换 `song_data` 实例，而不是修改源码里的数据库路径）。

### 修改清单（截至 2026-11-06，仅涉及一个文件）

`rotaeno/api/taptap_processor.py` → `calculate_song_rating()`

| 项 | 原值 | 现值 | 理由 |
| --- | --- | --- | --- |
| 满分（1010000+）补正系数 | `+3.7` | `+3.6` | v2.23.0 取消了理论值的额外 0.1 补正 |
| 1008000 ~ 1009999 段分母 | `10000` | `9995` | 使该段在段末恰好到 3.6，与满分段连续 |
| `next_point_score` 同段换算 | `* 10000` | `* 9995` | 与上一行保持一致 |
| 函数 docstring | 无 | 补说明与出处 | 便于日后核对依据 |

依据：Rotaeno 中文维基「Rating」条目（许可见第 3 节）。这里只是**按算法重写常数**，
不包含原文搬运。除上述文件外，`rotaeno/` 与上游一致。

上述改动已于 2026-11-06 回推上游（`None1145/RotaBot` PR #1，标题「借助 wiki.rotaeno.cn，
修复上游的 Rating 计算公式」），**目前未合并**。若上游合并并发布，本节改动即随上游版本生效，
届时只需保留数据来源说明，不必再维护本地补丁。

## 3. 数据来源：Rotaeno 中文维基

- 曲目定数（`Template:Songlist.json`）、限时上架 / 下架曲目名单、Rating 规则说明均来自
  <https://wiki.rotaeno.cn/>，**摘自 Rotaeno 中文维基**。
- 许可：**CC BY-NC-SA 3.0**。按该站要求，任何引用都须标注出处，未标注视为侵权。
- 我们不分发这些内容：程序在运行时向该站请求，或由用户自行保存到本地。
- 若你**另行分发**由这些数据派生的成果（例如自己重建的 `song_data.db`），
  那份成果需沿用 CC BY-NC-SA 3.0 并保留出处；此项要求**不适用于本项目代码**。
- **两份 `retired_songs.db` 不要混淆**：`rotaeno/database/retired_songs.db` 是**种子**，
  由本项目把 wiki「限时上架曲目列表」清洗成表后生成，内容按 CC BY-NC-SA 3.0 提供，
  出处标注在 `rotaeno/database/retired_songs.py` 顶部；`data/retired_songs.db` 是本机
  运行时生成并刷新的副本，已在 `.gitignore` 中，**不随仓库分发**。种子入库沿用上游的目录惯例
  （每个 Python 查询器配一个基本不更新的同名 db，如 `song_data.py` + `song_data.db`），
  与「是否方便离线使用」无关；所以曲库类数据（`Songlist.json`、`data/song_data.db`）仍然一律不入库。

## 4. 游戏内容与图像素材

Rotaeno 及其曲绘、音源、徽章、界面素材等版权归 Dream Engine Games 及相关权利人所有。

| 文件 | 来源 | 说明 |
| --- | --- | --- |
| `data/logo.png`、`data/logo.RotaBot.png` | 上游 None1145 / RotaBot 仓库，随 fork 继承 | 两者内容相同。若其中包含游戏或第三方素材，权利仍归原权利人；本仓库的 MIT 许可**不会**改变这一点 |
| `data/logo.RotaOff.png` | 本项目作者对上游 logo 的**改编（derivative work）** | 做法：复制原版 logo → 用 Windows 11 画图的「魔术擦除」抹掉 `BOT` → 手绘加上 `Off`。因此它**不是独立创作，也不是戏仿意义上的新作品**，权利状态跟随原图：原图若由 MIT 覆盖，则允许改编与再分发（须保留 `LICENSE` 中的版权声明）；若原图本身含游戏或第三方素材，改编不消除这些权利 |

本项目主体是命令行工具，图像仅用于界面展示，不包含曲绘、音源等游戏资源。

## 5. 免责

本项目是非官方工具，与 Dream Engine Games、Rotaeno 中文维基均无隶属或授权关系。
使用风险自负，请遵守游戏服务条款。
