@echo off
chcp 65001 >nul
title AutoGZH - 微信公众号 Markdown 自动排版与草稿同步工具
cd /d "%~dp0"

echo ======================================================================
echo    🚀 AutoGZH - 微信公众号 Markdown 自动排版与草稿箱一键同步工具
echo ======================================================================
echo.

:: 检查 Python 运行环境
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到 Python 环境！
    echo 请确认系统已安装 Python 3.8 及以上版本，并将 python 添加到了系统 PATH 环境变量中。
    echo.
    pause
    exit /b 1
)

echo 正在一键启动 Web 管理后台与排期系统...
echo 稍后将自动在您的默认浏览器中打开操作台 (http://127.0.0.1:5000)
echo.
echo [提示] 保持此窗口开启即可保持后台服务运行；若要关闭后台，关闭此窗口即可。
echo.

python main.py --ui

if errorlevel 1 (
    echo.
    echo [提示] 启动失败，尝试自动安装或更新依赖...
    pip install -r requirements.txt
    echo.
    echo 正在重新启动...
    python main.py --ui
    pause
)
