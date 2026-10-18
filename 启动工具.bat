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

echo 请选择运行模式：
echo ----------------------------------------------------------------------
echo  [1] 启动原生桌面应用 (GUI 窗口模式 - 推荐，直接双击使用)
echo  [2] 启动浏览器控制台 (Web UI 模式，在默认浏览器中打开操作台)
echo  [3] 快速排版离线预览 (无需 API 凭证，测试渲染并在浏览器查看效果)
echo  [4] 安装 / 更新运行依赖 (pip install -r requirements.txt)
echo ----------------------------------------------------------------------
echo.

set "choice="
set /p choice="请输入数字选项 [直接按回车默认启动 1]: "

if "%choice%"=="" set choice=1

if "%choice%"=="1" (
    echo.
    echo 正在拉起原生 GUI 桌面应用客户端...
    python main.py --gui
) else if "%choice%"=="2" (
    echo.
    echo 正在启动 Web 服务，稍后将自动在默认浏览器中为您打开操作台...
    python main.py --ui
) else if "%choice%"=="3" (
    echo.
    echo 正在执行本地排版编译测试 (采用新版硬核实战橙主题)...
    python scripts/test_render.py articles/drafts/test.md story
) else if "%choice%"=="4" (
    echo.
    echo 正在安装/更新项目依赖库，请稍候...
    pip install -r requirements.txt
    echo.
    echo 依赖安装完成！
    pause
) else (
    echo.
    echo 正在启动桌面客户端...
    python main.py --gui
)

if errorlevel 1 (
    echo.
    echo [提示] 程序异常退出或发生错误。
    echo 如果缺少第三方依赖库，可重新运行此批处理文件并选择 [4] 安装依赖。
    echo.
    pause
)
