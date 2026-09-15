@echo off
chcp 65001 >nul
title Stop ComfyUI Backend
echo Stopping the process listening on :8188 ...
"E:\ComfyUI-MCP\.venv\Scripts\python.exe" "E:\ComfyUI-MCP\comfy_launcher.py" stop
echo.
pause >nul
