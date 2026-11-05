# 任务选择与过滤

**语言 / Language**：[简体中文](filter.zh_CN.md) · [English](filter.en_US.md) · [返回 README](../README.zh_CN.md)

`run_tasks.py` 和 `tui.py` 的 `task run` 用同一套规则。规则很短，但**依赖参数顺序**，所以先说结论：

```text
segments = []          # 已经收起来的各段（对应 filter.yzc3582.fake.cpp 的 task_sets）
current  = "*"         # 当前段，初始是全部任务（对应同文件的 task_set）
while (还有参数) {
    if (--task) {                 // 开新段
        if (current 被动过) segments.append(current);
        current = (given);
    } else if (--filter) {
        current = filtered(current);   // 只筛当前段
    }
}
if (current 被动过) segments.append(current);
if (segments 为空) segments = ["*"];
// 结果 = 所有段的并集
```

一句话：**`--task` 开新段，`--filter` 只改当前段，最后求并集。**

> 说明：初始的 `"*"` 只有在被改动过（已经过 `--filter`）时才会单独成为一段；
> 没被改动就直接丢掉，否则并集永远是全部任务。所以 `--filter F --task 2` 的结果是
> “F 筛过的全部” 并上 “第 2 个”，而 `--task 2` 单独用就只有第 2 个。
> 名字对照：`segments` 对应 `filter.yzc3582.fake.cpp` 里累计的 `task_sets`，`current` 对应 `task_set`；两者只差一个 `s`，容易看错，因此这里改成更明确的名字。

## 推演几个例子

假设配置里有 5 个任务。

| 命令 | 结果 |
| --- | --- |
| `--task 1,3` | 第 1、3 个 |
| `--filter "i % 2 == 0"` | 第 2、4 个（在全部任务上筛） |
| `--task 1-3 --filter "i % 2 == 1"` | 第 1、3 个（filter 只留奇数号） |
| `--task 1,3 --task 5` | 第 1、3、5 个（两段并集） |
| `--task 1-3 --filter "i % 2 == 1" --task 5` | 第 1、3、5 个 |
| `--filter "type == 'custom'" --task 2` | 所有 custom 任务 **加上** 第 2 个 |
| `--task all --task 1` | 全部（`"*"` 并上 1） |

## `--task` 支持什么

- `1`、`1,3,4` —— 序号，从 1 开始
- `4-6`、`7~9` —— 闭区间（即包括两端的这段数字，`4-6` 就是 4、5、6）
- `all` 或 `*` —— 全部
- `rating` —— 名字里**包含** `rating` 的任务（不区分大小写）

序号越界会直接报错，不会静默跳过。

## `--filter` 能写什么

表达式在受控环境里求值，可用的名字有：

- `i` —— 任务在配置文件里的**原始序号**（不会因为过滤而重新编号）
- `x` —— 整个任务 dict，例如 `x['type']`
- 任务字段本身直接展开：`type`、`name`、`profile`、`fields`、`status`、`song_alias`、`level_min`、`level_max`、`sort`…

允许的运算符：`and or not`、`== != < <= > >=`、`in / not in`、`+ - * / % //`、下标和切片、元组/列表。
允许的函数只有：`len str int float bool any all`。

常见写法：

```bat
python run_tasks.py --filter "type == 'custom' and 'rating' in fields" --dry-run
python run_tasks.py --task 1-3 --filter "i % 2 == 1"
python run_tasks.py --filter "len(fields) > 2 or type == 'b40'"
```

属性访问（`x.items` 之类）会被拒绝，`().__class__` 这类逃逸写法跑不通。

## 配套的 `--dry-run`

拿不准结果就先看：

```bat
python run_tasks.py --task 1-3 --filter "i % 2 == 0" --dry-run
```

它会按原始序号打印将被执行的任务；如果一个都没选中，会返回非零退出码，方便 `bat` 里判断。

## 顺手记一句

`song_rtr` 任务不写 `level_max` 就是**没有上限**（内部沿用上游默认值 1145，彩蛋来自原作者 None1145）。以后出了 14.9 的谱，不写它照样能查到；只想看 13 以上、15 以下，就显式写 `"level_min": 13, "level_max": 15`。
