"""上游 `rotaeno/` 的运行时修补：集中一处，所有入口自动生效。

上游 `BaseAPI` 有两个问题，而 `rotaeno/` 目录要求保持只读，所以在这里打补丁：

1. `f"{self.base_url}/{endpoint}"` 而 endpoint 自己以 `/` 开头，
   拼出来是 `https://host//1.1/classes/CloudSave`。这个双斜杠会被网关
   当成另一条路由，直接 404 + 空响应体，于是只剩一句 JSONDecodeError。
2. 请求失败时直接 `.json()`，用户看不到 URL 和状态码。

启动时调用一次 `install()` 即可（`rotaoff/__init__.py` 已经做了）。
"""

import os
import sys

import requests

import rotaeno

from .store import RotaOffError


def _fixed_url(base_url: str, endpoint: str) -> str:
    return f"{base_url}/{str(endpoint).lstrip('/')}"


def _request(self, method: str, endpoint: str, **kwargs) -> dict:
    url = _fixed_url(self.base_url, endpoint)
    try:
        response = requests.request(
            method, url, headers=self._build_headers(),
            allow_redirects=True, proxies=self.proxies, timeout=20, verify=False,
            **kwargs,
        )
    except requests.Timeout:
        raise RotaOffError(f"请求超时（20 秒）: {url}\n网络或代理比较慢，稍后再试一次。")
    except requests.RequestException as exc:
        raise RotaOffError(f"请求失败: {url}\n{type(exc).__name__}: {exc}")
    try:
        return response.json()
    except ValueError:
        raise RotaOffError(
            f"服务器返回的不是 JSON: {url}\n"
            f"HTTP {response.status_code}，响应体 {len(response.text or '')} 字节"
        )


def _get(self, endpoint: str, params: dict | None = None) -> dict:
    return _request(self, "GET", endpoint, params=params)


def _post(self, endpoint: str, data: dict | None = None) -> dict:
    return _request(self, "POST", endpoint, json=data)


def _put(self, endpoint: str, data: dict | None = None) -> dict:
    return _request(self, "PUT", endpoint, json=data)


_installed = False
_LAST_CLOUD_SAVE_UPDATED_AT = ""


def last_cloud_save_updated_at() -> str:
    """最近一次 CloudSave 请求里 `results[0].updatedAt`（LeanCloud 对象修改时间）。"""
    return _LAST_CLOUD_SAVE_UPDATED_AT


def _capture_cloud_save_time(original):
    """记下 CloudSave 对象的 `updatedAt`，供快照展示云端同步时间。

    上游子类 `TapTapAPI.get_cloud_save` 只返回 `playerInfo` / `songDatas`，
    把 `results[0]` 元数据里的 `updatedAt` 丢掉了；`get_user_data` 里的
    `updateAt` 是用户资料的时间，**不是**云存档。所以在父类出口截一下。
    """

    def get_cloud_save(self, *args, **kwargs):
        global _LAST_CLOUD_SAVE_UPDATED_AT
        response = original(self, *args, **kwargs)
        try:
            _LAST_CLOUD_SAVE_UPDATED_AT = str(response["results"][0].get("updatedAt") or "")
        except (KeyError, IndexError, TypeError):
            _LAST_CLOUD_SAVE_UPDATED_AT = ""
        return response

    setattr(get_cloud_save, "_captures_updated_at", True)
    return get_cloud_save


# 上游把临时文件 / 存档写死在 `rotaeno/` 里面，而仓库里并没有 `saves/`、`temp/`：
# `tempfile.NamedTemporaryFile(dir=TEMP_DIR)` 与 `save_data_to_file(...)` 会直接
# FileNotFoundError，于是 song / status / rtr / 出图全都跑不起来。
# `rotaeno/` 要保持只读，所以不改它的源码，只把这些模块级常量指到我们自己的数据目录。
UPSTREAM_DIRS = {
    "rotaeno.processor": {
        "SAVES_DIR": "saves",
        "CLOUD_SAVES_DIR": "saves/cloud_saves",
        "USER_DATAS_DIR": "saves/user_datas",
        "FOLLOW_DATAS_DIR": "saves/follow_datas",
    },
    "rotaeno.utils": {"TEMP_DIR": "temp"},
}


def _candidate_roots(root: str | None = None) -> list:
    """按优先级列出可以放上游临时文件的位置。

    `data/` 是首选（和其余数据放一起）；它不可写时（只读安装目录、企业环境、
    沙箱）退到系统临时目录下的 RotaOff/，这样 song / status / rtr 不会因为
    单纯「写不进去」就整个跑不起来。
    """
    import tempfile

    from .paths import DATA_DIR

    roots = []
    for item in (root, DATA_DIR, os.path.join(tempfile.gettempdir(), "RotaOff")):
        if item and item not in roots:
            roots.append(item)
    return roots


def redirect_upstream_dirs(root: str | None = None) -> list:
    """把上游写死的输出目录改到可写位置，返回仍然失败的目录（不抛异常）。

    这些常量是在函数里按模块全局名查找的，所以运行时改掉就生效，
    不需要动 `rotaeno/` 的任何一行源码。
    """
    import rotaeno.processor
    import rotaeno.utils

    modules = {"rotaeno.processor": rotaeno.processor, "rotaeno.utils": rotaeno.utils}
    roots = _candidate_roots(root)
    failed = []
    for module_name, attributes in UPSTREAM_DIRS.items():
        module = modules[module_name]
        for attribute, relative in attributes.items():
            for base in roots:
                target = os.path.join(base, relative)
                try:
                    os.makedirs(target, exist_ok=True)
                except OSError:
                    continue
                setattr(module, attribute, target)
                break
            else:
                failed.append(relative)
    return failed


def _tolerant_add_player(original):
    """让 `player_data.add_player` 的写库失败不再毁掉整次查询。

    上游的 `get_song` / `get_song_status` / `get_song_rtr` 都把
    `add_to_database=True` 写死了，只要 `player_data.db` 不可写（只读安装目录、
    企业策略、沙箱），连「查一首歌」都会整条失败。历史记录本来就是附带功能，
    写不进去最多警告一句，结果照常返回。
    """

    def add_player(self, player, timestamp=None):
        try:
            return original(self, player, timestamp=timestamp)
        except Exception as exc:              # noqa: BLE001 - 刻意兜底
            from . import ui

            ui.warn(f"这次没记进历史库（{type(exc).__name__}），不影响本次结果。")
            return None

    add_player._tolerant = True
    return add_player


def redirect_player_history(root: str | None = None) -> dict:
    """把 `player_data` 指到可写目录，并让写失败变成警告。

    与 `song_data` 一样，这里也有**两个模块对象**：
    `rotaeno.database.player_data` 和 `sys.path` 版本 `database.player_data`
    （`rotaeno/api/taptap_processor.py:9` 用的是后者），两个都要换。
    """
    import rotaeno.database.player_data as main_module

    if not getattr(main_module.PlayerData.add_player, "_tolerant", False):
        main_module.PlayerData.add_player = _tolerant_add_player(
            main_module.PlayerData.add_player
        )

    instance = main_module.player_data
    for base in _candidate_roots(root):
        try:
            instance = main_module.PlayerData(os.path.join(base, "player_data.db"))
            break
        except Exception:                     # noqa: BLE001 - 换个位置再试
            continue

    replaced = []
    for name in ("rotaeno.database.player_data", "database.player_data"):
        module = sys.modules.get(name)
        if module is not None:
            module.player_data = instance
            replaced.append(name)
    return {"path": str(getattr(instance, "engine").url) if instance.engine else "", "modules": replaced}


def redirect_retired_songs(root: str | None = None) -> dict:
    """把上游 `retired_songs` 指到 `data/retired_songs.db`（可写、可刷新）。

    首次没有这份 db 时，从仓库自带的 `rotaeno/database/retired_songs.db`
    复制一份作为种子；之后由 `rotaoff.retired.sync()` 现场更新。
    """
    import shutil

    import rotaeno.database.retired_songs as main_module

    from .paths import DATA_DIR

    target = os.path.join(DATA_DIR, "retired_songs.db")
    seed = os.path.join(os.path.dirname(os.path.abspath(main_module.__file__)), "retired_songs.db")
    if (not os.path.isfile(target) or os.path.getsize(target) == 0) and os.path.isfile(seed):
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
            shutil.copyfile(seed, target)
        except OSError:
            pass

    try:
        instance = main_module.RetiredSongs(target)
    except Exception:                     # noqa: BLE001 - data/ 不可写时保留上游种子
        return {"path": "", "modules": []}

    replaced = []
    for name in ("rotaeno.database.retired_songs", "database.retired_songs"):
        module = sys.modules.get(name)
        if module is not None:
            setattr(module, "retired_songs", instance)
            replaced.append(name)
    return {"path": target, "modules": replaced}


def install() -> None:
    """给上游 `BaseAPI` 换上修好的 URL 拼接与错误提示（幂等）。"""
    global _installed
    if _installed:
        return
    api = rotaeno.api.taptap.BaseAPI
    api.get, api.post, api.put = _get, _post, _put
    user_api = rotaeno.api.taptap.UserAPI
    if not getattr(user_api.get_cloud_save, "_captures_updated_at", False):
        user_api.get_cloud_save = _capture_cloud_save_time(user_api.get_cloud_save)
    try:
        redirect_upstream_dirs()
    except Exception:                 # noqa: BLE001 - 目录不可写不该拦住启动
        pass
    try:
        redirect_player_history()
    except Exception:                 # noqa: BLE001
        pass
    try:
        redirect_retired_songs()
    except Exception:                 # noqa: BLE001 - 下架曲 db 不该拦住启动
        pass
    _installed = True
