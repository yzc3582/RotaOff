"""集中管理路径，避免每个模块各自拼 BASE_DIR。"""

import os

PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(PACKAGE_DIR)

DATA_DIR = os.path.join(BASE_DIR, "data")
USERS_FILE = os.path.join(DATA_DIR, "users.json")
CONFIG_FILE = os.path.join(DATA_DIR, "tasks.json")
LOCALES_DIR = os.path.join(DATA_DIR, "i18n")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")

USERS_EXAMPLE = os.path.join(DATA_DIR, "users.example.json")
CONFIG_EXAMPLE = os.path.join(DATA_DIR, "tasks.example.json")
