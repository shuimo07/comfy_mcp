@echo off
chcp 65001 >nul
title Install ComfyUI-MiniMax-H3-API custom node
setlocal

set "REPO=%~dp0"
set "NAME=ComfyUI-MiniMax-H3-API"
set "SRC=%REPO%custom_nodes\%NAME%"
set "DST=%COMFY_CUSTOM_NODES%"
if "%DST%"=="" set "DST=E:\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\custom_nodes"

echo ================================================================
echo   Install  %NAME%   (MiniMax H3 video via official API)
echo   src : %SRC%
echo   dst : %DST%\%NAME%
echo ================================================================
echo.

if not exist "%SRC%\nodes.py" (
    echo [FAIL] repo copy not found: %SRC%\nodes.py
    echo        run this bat from the comfy_mcp repo root.
    pause >nul & exit /b 1
)
if not exist "%DST%" (
    echo [FAIL] custom_nodes dir not found: %DST%
    echo        set COMFY_CUSTOM_NODES to override the target.
    pause >nul & exit /b 1
)

echo [1/2] mirror repo copy into custom_nodes ...
robocopy "%SRC%" "%DST%\%NAME%" /MIR /NJH /NJS /NDL /NP /R:2 /W:1
if errorlevel 8 (
    echo [FAIL] robocopy returned an error
    pause >nul & exit /b 1
)

echo [2/2] verify ...
if exist "%DST%\%NAME%\nodes.py" (
    echo       OK   %DST%\%NAME%\nodes.py
) else (
    echo       [FAIL] nodes.py missing after copy
    pause >nul & exit /b 1
)

echo.
echo ================================================================
echo   Done.  Restart ComfyUI to load the node:
echo       E:\ComfyUI-MCP\stop-comfyui.bat
echo       E:\ComfyUI-MCP\start-comfyui.bat
echo.
echo   Then put your MiniMax API key (one line, plain text) into:
echo       E:\Comfy-Desktop\ComfyUI-Cache\minimax_key.txt
echo   The node reads it at run time - no restart needed after that.
echo ================================================================
pause >nul
