"""实例互斥：防止 TUI 与自动化同时写同一份配置 / 输出。

用 filelock 这个成熟实现，而不是自己嗅探 pid：
- Windows 走 LockFileEx，Unix 走 fcntl.flock，都由系统在进程退出时释放
- 所以崩溃、强杀留下的锁不会挡路，不需要“陈旧锁”判断，也不用教用户删锁
- timeout=0 表示拿不到立刻失败，交互工具不该干等

另外写一份 data/rotaoff.lock.info 记录持有者（角色 / pid / 启动时间），
只用于报错时说明“是谁占着”，不参与加锁判断。
"""

import atexit
import json
import os
from datetime import datetime

from filelock import FileLock, Timeout

from .i18n import t
from .paths import DATA_DIR
from .store import RotaOffError

LOCK_FILE = os.path.join(DATA_DIR, "rotaoff.lock")
INFO_FILE = os.path.join(DATA_DIR, "rotaoff.lock.info")

_lock = None            # 当前进程持有的 FileLock


class LockedError(RotaOffError):
    """已有实例在运行。"""

    def __init__(self, info: dict):
        self.info = info
        holder = t(
            "lock-held",
            role=info.get("role") or "?",
            pid=info.get("pid") or "?",
            started=info.get("startedAt") or "?",
        )
        hint = t("lock-force-hint")
        super().__init__(f"{holder}\n{hint}")


def read_info() -> dict:
    if not os.path.exists(INFO_FILE):
        return {}
    try:
        with open(INFO_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def release() -> None:
    """释放锁并清掉持有者信息；没拿到锁时什么都不做。"""
    global _lock
    if _lock is not None:
        try:
            _lock.release()
        except Exception:                    # noqa: BLE001 - 退出阶段不抛异常
            pass
        _lock = None
    try:
        os.remove(INFO_FILE)
    except OSError:
        pass


def acquire(role: str, force: bool = False) -> dict:
    """尝试拿锁；被占用时抛 LockedError。

    force=True 表示跳过锁直接跑，留给“确认另一个实例已经不在了”的极端情况。
    """
    global _lock

    if force:
        return {}

    lock = FileLock(LOCK_FILE, timeout=0)
    try:
        lock.acquire(timeout=0)
    except Timeout:
        raise LockedError(read_info())

    _lock = lock
    info = {
        "pid": os.getpid(),
        "role": role,
        "startedAt": datetime.now().isoformat(timespec="seconds"),
    }
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(INFO_FILE, "w", encoding="utf-8") as file:
            json.dump(info, file, ensure_ascii=False, indent=4)
    except OSError:
        pass                                  # 只是给人看的信息，写不了也不影响互斥
    atexit.register(release)
    return info
