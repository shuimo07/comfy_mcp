@echo off
chcp 936 >nul
title WorkBuddy data -^> E drive (FINISH)
color 0A

echo.
echo  =========================================================
echo    Move the rest of WorkBuddy off C: and keep it on E:
echo  =========================================================
echo.

tasklist /FI "IMAGENAME eq WorkBuddy.exe" 2>nul | find /I "WorkBuddy.exe" >nul
if not errorlevel 1 (
    echo  [ERROR] WorkBuddy is still running.
    echo  Quit WorkBuddy completely ^(tray icon too^), then run me again.
    echo  ^(Alternatively: just log off or reboot - the logon task does it too.^)
    echo.
    pause
    exit /b 1
)

echo  WorkBuddy is closed.
echo.
echo  What happens next:
echo    1. copy every remaining file to E:\WBData ^(copy only, never delete first^)
echo    2. verify the copy, then remove the C: original
echo    3. put a junction back at the C: path so the app sees no difference
echo.
echo  After this, anything the app writes under those paths
echo  lands on E: automatically.
echo.
pause

echo  [1/3] running logon guard ...
powershell -NoProfile -ExecutionPolicy Bypass -File "E:\WBData\_tools\guard.ps1"

echo.
echo  [2/3] second pass: recursive .workbuddy subdirectory migration ...
set PYEXE=
for /f "delims=" %%F in ('dir /b /o-n "C:\Users\legion\.workbuddy\binaries\python\versions" 2^>nul') do (
    if exist "C:\Users\legion\.workbuddy\binaries\python\versions\%%F\python.exe" set PYEXE=C:\Users\legion\.workbuddy\binaries\python\versions\%%F\python.exe
)
if "%PYEXE%"=="" (
    echo  [skip] bundled python not found
) else (
    "%PYEXE%" "E:\WBData\_tools\migrate_deep.py"
)

echo.
echo  =========================================================
echo   Result  ^(every line should say JUNCTION^)
echo  =========================================================
echo.
for %%P in ("C:\Users\legion\.workbuddy-key-fallback" "C:\Users\legion\.codebuddy" "C:\Users\legion\.cache" "C:\Users\legion\AppData\Roaming\WorkBuddy" "C:\Users\legion\WorkBuddy") do (
    fsutil reparsepoint query %%P >nul 2>&1
    if errorlevel 1 (
        echo   REAL DIR  %%P
    ) else (
        echo   JUNCTION  %%P
    )
)
echo.
echo   C:\Users\legion\.workbuddy  ^(per subdirectory^):
for /D %%P in ("C:\Users\legion\.workbuddy\*") do (
    echo   %%P | findstr /I "__old __probe __movetest" >nul
    if errorlevel 1 (
        fsutil reparsepoint query "%%P" >nul 2>&1
        if errorlevel 1 (
            echo     REAL DIR  %%~nxP
        ) else (
            echo     JUNCTION  %%~nxP
        )
    )
)
echo.
echo   Log: E:\WBData\_tools\guard.log
echo.
pause
