@echo off
chcp 65001 >nul
title ComfyUI-MCP  bootstrap
setlocal enabledelayedexpansion

set "BASE=%~dp0"
if "%BASE:~-1%"=="\" set "BASE=%BASE:~0,-1%"

echo ================================================================
echo   ComfyUI x WorkBuddy MCP - bootstrap
echo   BASE = %BASE%
echo ================================================================
echo.

rem ---------- 1) 上游服务端（git submodule）----------
echo [1/4] 拉取上游 comfyui-mcp-server ...
if exist "%BASE%\comfyui-mcp-server\server.py" (
    echo       已存在，跳过。
) else (
    git -C "%BASE%" submodule update --init --recursive
    if errorlevel 1 (
        echo       [失败] 请确认已安装 git 且能访问 github.com
        pause & exit /b 1
    )
)

rem ---------- 2) 找 Python ----------
echo.
echo [2/4] 查找 Python 解释器 ...
set "PY="
for %%P in ("C:\Users\legion\.workbuddy\binaries\python\versions\3.13.12\python.exe") do (
    if exist %%P set "PY=%%~P"
)
if not defined PY (
    where py >nul 2>&1 && set "PY=py -3"
)
if not defined PY (
    where python >nul 2>&1 && set "PY=python"
)
if not defined PY (
    echo       [失败] 没找到 Python，请先安装 Python 3.10+
    pause & exit /b 1
)
echo       PY = %PY%

rem ---------- 3) venv ----------
echo.
echo [3/4] 创建独立 venv（%BASE%\.venv）...
if exist "%BASE%\.venv\Scripts\python.exe" (
    echo       已存在，跳过。
) else (
    %PY% -m venv "%BASE%\.venv"
    if errorlevel 1 ( echo       [失败] venv 创建失败 & pause & exit /b 1 )
)
set "VPY=%BASE%\.venv\Scripts\python.exe"

rem ---------- 4) 依赖 ----------
echo.
echo [4/4] 安装依赖 ...
"%VPY%" -m pip install --disable-pip-version-check --no-warn-script-location -r "%BASE%\comfyui-mcp-server\requirements.txt"
if errorlevel 1 ( echo       [失败] 依赖安装失败 & pause & exit /b 1 )

rem 关键修正：上游只写 mcp>=0.9.0，pip 会装 mcp 2.x，代码用的是 v1 的 FastMCP -> 必须钉回 1.x
echo.
echo       钉住 mcp 1.x ...
"%VPY%" -m pip install --disable-pip-version-check --no-warn-script-location "mcp<2"
if errorlevel 1 ( echo       [失败] mcp 降级失败 & pause & exit /b 1 )

echo.
echo       自检 ...
"%VPY%" -c "from mcp.server.fastmcp import FastMCP; import requests, PIL; print('      OK: mcp / requests / Pillow 均可导入')"
if errorlevel 1 ( echo       [失败] 自检不通过 & pause & exit /b 1 )

echo.
echo ================================================================
echo   完成。
echo   1) 把 config\workbuddy-mcp.example.json 里的 comfyui 段
echo      合并进 C:\Users\legion\.workbuddy\mcp.json
echo   2) WorkBuddy 连接器管理 - 自定义连接器 - 对 comfyui 点「信任」- 重启应用
echo   3) 双击 start-comfyui.bat 预热后端
echo ================================================================
pause >nul
