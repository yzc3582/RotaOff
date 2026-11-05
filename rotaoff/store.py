"""本地存储层：data/users.json（账号）与 data/tasks.json（配置 + 任务）。

配置文件不进版本库（见 .gitignore）；缺失时优先从 *.example.json 复制一份，
这样仓库 clone 下来就能直接运行，也不会把 sessionToken 提交上去。
"""

import json
import os
import shutil

from .i18n import DEFAULT_LOCALE, t
from .paths import CONFIG_EXAMPLE, CONFIG_FILE, DATA_DIR, USERS_EXAMPLE, USERS_FILE

DEFAULT_PROFILE = "default"
REQUIRED_KEYS = ("serverCode", "objectID", "sessionToken")
SERVER_CODES = ("cn", "global")          # rotaeno.api 只实现了国服 / 国际服端点
PROFILE_FIELDS = ("serverCode", "objectID", "sessionToken", "locale")

DEFAULT_CONFIG = {
    "profile": DEFAULT_PROFILE,
    "output": {},
    "schedule": {"interval": 0},         # 0 表示只跑一次
    "tasks": [],
}


class RotaOffError(Exception):
    """可以直接展示给用户看的错误。"""


def ensure_workspace() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(USERS_FILE):
        if os.path.exists(USERS_EXAMPLE):
            shutil.copyfile(USERS_EXAMPLE, USERS_FILE)
        else:
            save_users({})
    if not os.path.exists(CONFIG_FILE):
        if os.path.exists(CONFIG_EXAMPLE):
            shutil.copyfile(CONFIG_EXAMPLE, CONFIG_FILE)
        else:
            save_config(DEFAULT_CONFIG)


def _read_json(path: str, fallback):
    if not os.path.exists(path):
        return fallback
    try:
        with open(path, "r", encoding="utf-8") as file:
            return json.load(file)
    except (OSError, json.JSONDecodeError) as exc:
        raise RotaOffError(f"读取 {path} 失败: {exc}")


def _write_json(path: str, data) -> None:
    os.makedirs(os.path.dirname(path) or DATA_DIR, exist_ok=True)
    with open(path, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=4)


# ---------------------------------------------------------------- 账号资料

def load_users() -> dict:
    users = _read_json(USERS_FILE, {})
    return users if isinstance(users, dict) else {}


def save_users(users: dict) -> None:
    _write_json(USERS_FILE, users)


# ---------------------------------------------------------------- 配置文件

def load_config(path: str = None) -> dict:
    config = dict(DEFAULT_CONFIG)
    data = _read_json(path or CONFIG_FILE, {})
    if isinstance(data, dict):
        config.update(data)
    config["profile"] = str(config.get("profile") or DEFAULT_PROFILE)
    config["tasks"] = [task for task in config.get("tasks") or [] if isinstance(task, dict)]
    if not isinstance(config.get("output"), dict):
        config["output"] = {}
    if not isinstance(config.get("schedule"), dict):
        config["schedule"] = {"interval": 0}
    return config


def save_config(config: dict, path: str = None) -> None:
    _write_json(path or CONFIG_FILE, config)


def set_schedule_interval(seconds: int) -> dict:
    config = load_config()
    config["schedule"] = {"interval": max(int(seconds), 0)}
    save_config(config)
    return config["schedule"]


def active_profile_name() -> str:
    return load_config().get("profile") or DEFAULT_PROFILE


def set_active_profile(name: str) -> str:
    if name not in load_users():
        raise RotaOffError(t("profile-not-found", profile=name))
    config = load_config()
    config["profile"] = name
    save_config(config)
    return name


def create_profile(name: str) -> dict:
    name = (name or "").strip()
    if not name:
        raise RotaOffError(t("profile-name-required"))
    users = load_users()
    if name in users:
        raise RotaOffError(t("profile-exists", profile=name))
    users[name] = {"locale": DEFAULT_LOCALE}
    save_users(users)
    return users[name]


def get_profile(name: str = None) -> dict:
    name = name or active_profile_name()
    profile = load_users().get(name)
    if not isinstance(profile, dict):
        raise RotaOffError(t("profile-not-found", profile=name))
    return profile


def profile_locale(name: str = None) -> str:
    try:
        return get_profile(name).get("locale", DEFAULT_LOCALE)
    except RotaOffError:
        return DEFAULT_LOCALE


def verify_profile(profile: dict) -> tuple:
    """返回 (是否可用, 缺失项 / 成功标记)，消息键沿用原有 i18n。"""
    if not isinstance(profile, dict):
        return False, "missing-required-parameter-serverCode"
    for key in REQUIRED_KEYS:
        if profile.get(key) in (None, ""):
            return False, f"missing-required-parameter-{key}"
    if profile.get("serverCode") not in SERVER_CODES:
        return False, "server-code-unsupported-for-query"
    return True, "binding-successful"


def set_profile_field(key: str, value: str, name: str = None) -> tuple:
    if key not in PROFILE_FIELDS:
        raise RotaOffError(t("profile-field-invalid", field=key))
    if key == "serverCode" and value not in SERVER_CODES:
        raise RotaOffError(t("unavailable-server-code", server_code=value))
    users = load_users()
    name = name or active_profile_name()
    if name not in users:
        raise RotaOffError(t("profile-not-found", profile=name))
    users[name][key] = value
    save_users(users)
    return verify_profile(users[name])


def require_ready_profile(name: str = None) -> dict:
    """取一个已经绑定完毕、可以发请求的配置。"""
    profile = get_profile(name)
    verified, key = verify_profile(profile)
    if not verified:
        locale = profile.get("locale", DEFAULT_LOCALE)
        raise RotaOffError(
            t("rotaeno-account-binding-not-yet-completed", locale, message=t(key, locale))
        )
    return profile


# ---------------------------------------------------------------- 任务清单

def load_tasks(path: str = None) -> list:
    return load_config(path).get("tasks") or []


def save_tasks(tasks: list, path: str = None) -> list:
    config = load_config(path)
    config["tasks"] = list(tasks)
    save_config(config, path)
    return config["tasks"]


def add_task(task: dict, path: str = None) -> int:
    tasks = load_tasks(path)
    tasks.append(task)
    save_tasks(tasks, path)
    return len(tasks)


def remove_task(index: int, path: str = None) -> dict:
    tasks = load_tasks(path)
    if not 1 <= int(index) <= len(tasks):
        raise RotaOffError(t("task-not-found", task=index))
    task = tasks.pop(int(index) - 1)
    save_tasks(tasks, path)
    return task
