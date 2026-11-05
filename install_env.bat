@echo off
REM 一键建虚拟环境 + 装依赖。用法：
REM   install_env.bat            连 chromium 内核一起装（能出图片）
REM   install_env.bat nobrowser  只装 Python 依赖（只出文本）
setlocal
cd /d %~dp0

where uv >nul 2>nul
if %errorlevel%==0 (
    echo [RotaOff] 使用 uv 创建 .venv
    uv venv .venv
    uv pip install -r requirements.txt
) else (
    echo [RotaOff] 没找到 uv，改用 python -m venv
    python -m venv .venv || goto :fail
    .venv\Scripts\python -m pip install --upgrade pip
    .venv\Scripts\python -m pip install -r requirements.txt || goto :fail
)

if /i "%~1"=="nobrowser" goto :done
if /i "%~1"=="browser" goto :browser

set "ANSWER="
set /p ANSWER=要顺便安装 chromium 内核吗？只有生成图片才需要，约 150MB [y/N] 
if /i not "%ANSWER%"=="y" (
    echo [RotaOff] 已跳过 chromium，图片输出会提示不可用，文本功能正常。
    goto :done
)

:browser
echo [RotaOff] 安装 chromium 内核
.venv\Scripts\python -m playwright install chromium

:done
echo.
echo 装好了。启动交互界面： .venv\Scripts\python tui.py
echo 直接跑自动化：       .venv\Scripts\python run_tasks.py --dry-run
exit /b 0

:fail
echo.
echo 安装失败，检查上面的报错；也可以手动执行：
echo   python -m venv .venv
echo   .venv\Scripts\python -m pip install -r requirements.txt
exit /b 1
