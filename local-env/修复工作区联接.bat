@echo off
chcp 65001 >nul
setlocal

set "SRC=C:\Users\legion\WorkBuddy"
set "DST=E:\WorkBuddy"

echo ============================================================
echo  修复 WorkBuddy 工作区目录联接
echo ============================================================
echo   联接位置: %SRC%
echo   真实数据: %DST%
echo.

rem ---------- 1. E 盘目标自检 ----------
if not exist "%DST%" (
    echo [中止] %DST% 不存在，E 盘数据可能有异常，请人工确认后再处理。
    echo.
    pause
    exit /b 1
)

rem ---------- 2. SRC 不存在 -> 直接建 ----------
if not exist "%SRC%" goto MAKELINK

rem ---------- 3. SRC 已是联接 -> 结束 ----------
fsutil reparsepoint query "%SRC%" >nul 2>&1
if not errorlevel 1 (
    echo [跳过] 已经是目录联接，无需修复。
    echo.
    fsutil reparsepoint query "%SRC%" | findstr /i "替代目标\|Substitute"
    echo.
    pause
    exit /b 0
)

rem ---------- 4. SRC 是真实目录 -> 列出内容并要求确认 ----------
echo [注意] %SRC% 当前是【真实目录】，需要删除后重建为联接。
echo.
echo   将要删除的 C 盘内容：
echo   ------------------------------------------------------------
dir /s /b "%SRC%" 2>nul
echo   ------------------------------------------------------------
echo.
echo   * 只删上面列出的 C 盘内容；E:\WorkBuddy 的数据不受影响。
echo   * 请先【完全退出 WorkBuddy】（含右下角托盘图标），
echo     否则目录被占用会删除失败。
echo.
echo   按任意键继续，或直接关闭本窗口取消...
pause >nul

cd /d E:\
rmdir /s /q "%SRC%"

if exist "%SRC%" (
    echo.
    echo [失败] 目录仍被占用，无法删除。
    echo        请在任务管理器里确认没有 WorkBuddy 相关进程后重试。
    echo.
    pause
    exit /b 1
)
echo [OK] 已删除 C 盘真实目录（E 盘数据未受影响）
echo.

:MAKELINK
mklink /J "%SRC%" "%DST%"
if errorlevel 1 (
    echo [失败] 创建目录联接失败。
    echo.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo  完成。
echo ------------------------------------------------------------
echo  [联接验证]
dir /AL "C:\Users\legion" | findstr /i WorkBuddy
echo.
echo  [会话目录数]
dir /b "%SRC%" | find /c /v ""
echo ============================================================
echo.
pause
