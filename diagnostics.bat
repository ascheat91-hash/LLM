@echo off
setlocal
cd /d "%~dp0"
title FOXSI Assistant - System Diagnostics

echo =======================================================
echo   FOXSI Voice Assistant - Hardware ^& Diagnostics Report
echo =======================================================
echo.

set "PY_CMD=python"
if exist "%~dp0venv\Scripts\python.exe" (
    set "PY_CMD=%~dp0venv\Scripts\python.exe"
)

set "PYTHONPATH=%~dp0;%PYTHONPATH%"

%PY_CMD% -m app.core.diagnostics

echo.
pause

