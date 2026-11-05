# Task selection and filtering

**Language**：[简体中文](filter.zh_CN.md) · [English](filter.en_US.md) · [back to README](../README.md)

`run_tasks.py` and `tui.py`'s `task run` share the same rules. They are short but **order-sensitive**, so here is the summary first:

```text
segments = []          # finished segments (the task_sets in filter.yzc3582.fake.cpp)
current  = "*"         # current segment, starts as every task (the task_set there)
while (more arguments) {
    if (--task) {                 // start a new segment
        if (current was touched) segments.append(current);
        current = (given);
    } else if (--filter) {
        current = filtered(current);   // narrows the current segment only
    }
}
if (current was touched) segments.append(current);
if (segments is empty) segments = ["*"];
// result = union of all segments
```

In one line: **`--task` starts a new segment, `--filter` only changes the current one, everything is unioned at the end.**

> Note: the initial `"*"` only becomes a segment when something changed it (i.e. a `--filter` already applied to it);
> otherwise it is dropped, because then the union would always be every task. So `--filter F --task 2` yields
> "everything matching F" **plus** "task 2", while `--task 2` alone yields just task 2.
> Naming: `segments` is the accumulated `task_sets` in `filter.yzc3582.fake.cpp`, `current` is `task_set`; they differ by a single `s`, which is easy to misread, so this document uses clearer names.

## Worked examples

Assume the config holds 5 tasks.

| Command | Result |
| --- | --- |
| `--task 1,3` | tasks 1 and 3 |
| `--filter "i % 2 == 0"` | tasks 2 and 4 (filtered over all tasks) |
| `--task 1-3 --filter "i % 2 == 1"` | tasks 1 and 3 (the filter keeps odd indices) |
| `--task 1,3 --task 5` | tasks 1, 3 and 5 (union of two segments) |
| `--task 1-3 --filter "i % 2 == 1" --task 5` | tasks 1, 3 and 5 |
| `--filter "type == 'custom'" --task 2` | every custom task **plus** task 2 |
| `--task all --task 1` | everything (`"*"` unioned with 1) |

## What `--task` accepts

- `1`, `1,3,4` — indices, starting at 1
- `4-6`, `7~9` — closed interval (both ends included, so `4-6` means 4, 5, 6)
- `all` or `*` — everything
- `rating` — tasks whose **name contains** `rating` (case-insensitive)

An out-of-range index raises an error instead of being skipped silently.

## What `--filter` accepts

Expressions are evaluated in a restricted environment. Available names:

- `i` — the task's **original index** in the config file (filtering never renumbers it)
- `x` — the whole task dict, e.g. `x['type']`
- task fields are also unpacked directly: `type`, `name`, `profile`, `fields`, `status`, `song_alias`, `level_min`, `level_max`, `sort`, …

Allowed operators: `and or not`, `== != < <= > >=`, `in / not in`, `+ - * / % //`, subscripts and slices, tuples/lists.
The only callable functions are: `len str int float bool any all`.

Typical usage:

```bat
python run_tasks.py --filter "type == 'custom' and 'rating' in fields" --dry-run
python run_tasks.py --task 1-3 --filter "i % 2 == 1"
python run_tasks.py --filter "len(fields) > 2 or type == 'b40'"
```

Attribute access (such as `x.items`) is rejected, and escape tricks like `().__class__` do not work.

## Using `--dry-run`

When unsure what will be selected, look first:

```bat
python run_tasks.py --task 1-3 --filter "i % 2 == 0" --dry-run
```

It prints the tasks that would run, using their original indices. If nothing is selected it exits with a non-zero status code, which is handy inside a `.bat` file.

## One more note

A `song_rtr` task without `level_max` means **no upper bound** (the upstream default 1145 is kept as an easter egg for the original author, None1145). A future 14.9 chart is still found without touching the code; to see 13+ up to 15 only, write `"level_min": 13, "level_max": 15` explicitly.
