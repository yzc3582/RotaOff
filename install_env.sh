#!/usr/bin/env bash
# 一键建虚拟环境 + 装依赖。用法：
#   ./install_env.sh              装完会问要不要下 chromium 内核（默认不下）
#   ./install_env.sh nobrowser    只装 Python 依赖（只出文本）
#   ./install_env.sh browser      直接连同 chromium 一起装（能出图片）
set -u
cd "$(dirname "$0")" || exit 1

PY="${PYTHON:-python3}"

if command -v uv >/dev/null 2>&1; then
    echo "[RotaOff] 使用 uv 创建 .venv"
    uv venv .venv || exit 1
    uv pip install -r requirements.txt || exit 1
else
    echo "[RotaOff] 没找到 uv，改用 $PY -m venv"
    "$PY" -m venv .venv || exit 1
    .venv/bin/python -m pip install --upgrade pip || exit 1
    .venv/bin/python -m pip install -r requirements.txt || exit 1
fi

MODE="${1:-ask}"
if [ "$MODE" = "ask" ]; then
    printf '要顺便安装 chromium 内核吗？只有生成图片才需要，约 150MB [y/N] '
    read -r answer || answer=""
    case "$answer" in
        y|Y|yes|YES) MODE="browser" ;;
        *) MODE="nobrowser" ;;
    esac
fi

if [ "$MODE" = "browser" ]; then
    echo "[RotaOff] 安装 chromium 内核"
    .venv/bin/python -m playwright install chromium || echo "[RotaOff] chromium 安装失败，图片功能不可用，文本功能不受影响。"
else
    echo "[RotaOff] 已跳过 chromium，图片输出会提示不可用，文本功能正常。"
fi

echo
echo "装好了。启动交互界面： .venv/bin/python tui.py"
echo "直接跑自动化：       .venv/bin/python run_tasks.py --dry-run"
