"""任务选择与过滤：给 run_tasks.py 和 tui.py 共用。

选择表达式（--task）：
    1,3          单个序号
    4-6 / 7~9    闭区间（包括两端：4-6 就是 4、5、6）
    all / *      全部
    rating       —— 名字里包含 "rating" 的任务

过滤表达式（--filter）：只作用于“当前这一段”任务集合，可写多个：
    "i % 2 == 0"                          按序号筛
    "type == 'custom'"                     按字段筛（任务字段会直接展开成变量）
    "x['type'] == 'b40' and 'txt' in export"
    "len(fields) > 2"                      len 之类常用函数会单独放行

多段合并的规则见 apply_selection()，或根目录 filter.md。
"""

import ast

from .store import RotaOffError

_SAFE_FUNCTIONS = {"len": len, "str": str, "int": int, "float": float, "bool": bool, "any": any, "all": all}

_ALLOWED_NODES = (
    ast.Expression,
    ast.BoolOp, ast.And, ast.Or, ast.Not,
    ast.Compare, ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.In, ast.NotIn,
    ast.BinOp, ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Mod, ast.FloorDiv,
    ast.UnaryOp, ast.USub, ast.UAdd,
    ast.Name, ast.Load, ast.Constant,
    ast.Subscript, ast.Slice,
    ast.Tuple, ast.List,
    ast.Call,            # 只允许 _SAFE_FUNCTIONS 里那几个，见 _SafeChecker
)


class _SafeChecker(ast.NodeVisitor):
    """只放行白名单节点；函数调用必须是白名单里的名字，属性访问一律拒绝。"""

    def generic_visit(self, node) -> None:
        if not isinstance(node, _ALLOWED_NODES):
            raise RotaOffError(f"过滤器里不允许使用 {type(node).__name__}")
        super().generic_visit(node)

    def visit_Call(self, node) -> None:            # noqa: N802 - ast 接口
        if not isinstance(node.func, ast.Name) or node.func.id not in _SAFE_FUNCTIONS:
            raise RotaOffError("过滤器里只能调用 len/str/int/float/bool/any/all")
        for argument in node.args:
            self.visit(argument)


def compile_filter(expression: str):
    """把过滤表达式编译成 predicate(index, task) -> bool。"""
    expression = (expression or "").strip()
    if not expression:
        raise RotaOffError("过滤器不能为空")
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise RotaOffError(f"过滤器语法错误: {expression}（{exc.msg}）")
    _SafeChecker().visit(tree)
    code = compile(tree, "<filter>", "eval")

    def predicate(index: int, task: dict) -> bool:
        context = {"__builtins__": {}, "i": index, "x": task}
        context.update({key: value for key, value in task.items() if isinstance(key, str)})
        try:
            return bool(eval(code, {"__builtins__": _SAFE_FUNCTIONS}, context))  # noqa: S307
        except Exception as exc:                   # noqa: BLE001 - 统一转成可读错误
            raise RotaOffError(f"过滤器执行失败: {expression}（{type(exc).__name__}: {exc}）")

    return predicate


def parse_spec(spec: str, all_tasks: list) -> list:
    """把 "1,3,4-6,all,名字" 解析成 [(序号, 任务)]，保持顺序并去重。"""
    import re

    chosen = []
    for raw in str(spec).split(","):
        token = raw.strip()
        if not token:
            continue

        if token.lower() in ("all", "*"):
            chosen.extend(enumerate(all_tasks, 1))
            continue

        if re.fullmatch(r"\d+", token):
            index = int(token)
            if not 1 <= index <= len(all_tasks):
                raise RotaOffError(f"任务序号越界: {token}（共 {len(all_tasks)} 个）")
            chosen.append((index, all_tasks[index - 1]))
            continue

        span = re.fullmatch(r"(\d+)\s*[-~]\s*(\d+)", token)
        if span:
            low, high = sorted((int(span.group(1)), int(span.group(2))))
            if not 1 <= low <= len(all_tasks):
                raise RotaOffError(f"任务序号越界: {token}（共 {len(all_tasks)} 个）")
            for index in range(low, min(high, len(all_tasks)) + 1):
                chosen.append((index, all_tasks[index - 1]))
            continue

        matched = [
            (index, task)
            for index, task in enumerate(all_tasks, 1)
            if token.lower() in str(task.get("name", "")).lower()
        ]
        if not matched:
            raise RotaOffError(f"找不到任务: {token}")
        chosen.extend(matched)

    seen, unique = set(), []
    for index, task in chosen:
        if index in seen:
            continue
        seen.add(index)
        unique.append((index, task))
    return unique


def apply_selection(all_tasks: list, ops: list) -> list:
    """按命令行顺序执行选择，语义同 filter.yzc3582.fake.cpp：

        current = "*"          # 初始集合
        segments = []
        for op in ops:
            if op 是 --task X:  if current 被动过: segments.push(current); current = parse(X)
            if op 是 --filter F: current = {t ∈ current | F(t)}   # 只动当前段
        if current 被动过: segments.push(current)
        if segments 为空: segments = ["*"]

    结果就是所有段的并集；序号 i 始终是任务在配置里的原始序号。
    """
    everything = list(enumerate(all_tasks, 1))
    current = everything
    touched = False          # 当前段是否被 --task / --filter 改过
    segments = []

    for kind, value in ops or []:
        if kind == "task":
            if touched:
                segments.append(current)
            current = parse_spec(value, all_tasks)
            touched = True
        elif kind == "filter":
            predicate = compile_filter(value)
            current = [(index, task) for index, task in current if predicate(index, task)]
            touched = True
        else:
            raise RotaOffError(f"未知的选择操作: {kind}")

    if touched:
        segments.append(current)
    if not segments:
        segments = [everything]

    merged, seen = [], set()
    for segment in segments:
        for index, task in segment:
            if index in seen:
                continue
            seen.add(index)
            merged.append(task)
    return merged


