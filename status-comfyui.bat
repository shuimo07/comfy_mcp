@echo off
chcp 65001 >nul
title ComfyUI Status
"E:\ComfyUI-MCP\.venv\Scripts\python.exe" "E:\ComfyUI-MCP\comfy_launcher.py" status
echo.
pause >nul
