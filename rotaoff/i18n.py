"""极简本地化：复用 data/i18n/*.json 里的文案。"""

import json
import os

from .paths import LOCALES_DIR

DEFAULT_LOCALE = "zh-CN"
LOCALES = {}


def _load() -> None:
    if LOCALES or not os.path.isdir(LOCALES_DIR):
        return
    for name in os.listdir(LOCALES_DIR):
        if not name.endswith(".json"):
            continue
        try:
            with open(os.path.join(LOCALES_DIR, name), "r", encoding="utf-8") as file:
                LOCALES[name[:-5]] = json.load(file)
        except (OSError, json.JSONDecodeError):
            continue


def t(key: str, locale: str = DEFAULT_LOCALE, **kwargs) -> str:
    """取一条文案；找不到时原样返回 key，方便发现漏翻的键。"""
    _load()
    table = LOCALES.get(str(locale)) or LOCALES.get(DEFAULT_LOCALE, {})
    text = table.get(key) or LOCALES.get(DEFAULT_LOCALE, {}).get(key, key)
    try:
        return text.format(**kwargs)
    except (KeyError, IndexError):
        return text
