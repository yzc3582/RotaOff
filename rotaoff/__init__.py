"""RotaOff 包：无 Discord、纯同步的 Rotaeno 数值终端。"""

from . import data, i18n, library, output, paths, store, tasks, ui
from .store import RotaOffError
from .tasks import TASK_TYPES, build_task, describe_task, run_task, run_tasks

__all__ = [
    "data",
    "i18n",
    "library",
    "output",
    "paths",
    "store",
    "tasks",
    "ui",
    "RotaOffError",
    "TASK_TYPES",
    "build_task",
    "describe_task",
    "run_task",
    "run_tasks",
]

from . import patch

patch.install()          # 修补上游 URL 拼接；必须在其它模块发请求之前执行

# 把上游那个停更在 2.9.0 的 song_data.db 换成用 Songlist.json 建的库。
# 换失败不算致命：继续用旧库，只是缺定数的谱面算不出来。
try:
    LIBRARY = library.ensure()
except Exception as exc:                      # noqa: BLE001 - 曲库问题不该拦住启动
    LIBRARY = {"source": "rotaeno/database/song_data.db（旧库，未更新）",
               "built": False, "error": str(exc)}
