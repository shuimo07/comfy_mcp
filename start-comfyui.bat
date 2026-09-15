@echo off
chcp 65001 >nul
title ComfyUI Backend  (headless :8188)
echo ================================================================
echo   ComfyUI headless backend for WorkBuddy MCP
echo   API : http://127.0.0.1:8188
echo   Log : E:\ComfyUI-MCP\logs\comfyui-headless.log
echo ================================================================
echo.
"E:\ComfyUI-MCP\.venv\Scripts\python.exe" "E:\ComfyUI-MCP\comfy_launcher.py" start
echo.
echo --- status ---
"E:\ComfyUI-MCP\.venv\Scripts\python.exe" "E:\ComfyUI-MCP\comfy_launcher.py" status
echo.
echo Close this window when done. The backend keeps running.
pause >nul
