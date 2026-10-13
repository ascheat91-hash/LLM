@echo off
setlocal
cd /d "%~dp0"
title FOXSI Assistant - Stop Server

echo =======================================================
echo   Stopping FOXSI Local AI Voice Assistant...
echo =======================================================
echo.

set "STOPPED=0"

:: Find process listening on port 8000
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8000 ^| findstr LISTENING') do (
    echo Terminating PID %%a on port 8000...
    taskkill /f /pid %%a >nul 2>&1
    set "STOPPED=1"
)

if "%STOPPED%"=="1" (
    echo [OK] FOXSI Assistant server stopped successfully.
) else (
    echo [INFO] No server process detected running on port 8000.
)

echo.
pause
