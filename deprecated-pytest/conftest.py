# conftest.py
import pytest
# 假设你把构建 bot 的逻辑抽成了 create_bot 函数，或者直接 import 那个全局的 bot 对象
from bot import bot  # 或者 from bot import bot

@pytest.fixture
def simcord_bot():
    """这个 fixture 会被 SimCord 自动发现并用于构建测试环境"""
    return bot  # 或者直接 return bot