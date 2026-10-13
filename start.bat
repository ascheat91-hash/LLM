@echo off
setlocal
cd /d "%~dp0"
title FOXSI Local AI Voice Assistant

echo =======================================================
echo   Launching FOXSI Local AI Voice Assistant...
echo =======================================================
echo.

set "PY_CMD=python"
if exist "%~dp0venv\Scripts\python.exe" (
    set "PY_CMD=%~dp0venv\Scripts\python.exe"
)

set "PYTHONPATH=%~dp0;%PYTHONPATH%"

:: Launch web dashboard in default browser after short delay
start "" cmd /c "timeout /t 2 /nobreak >nul && start http://127.0.0.1:8000"

:: Start the FastAPI / Uvicorn application
%PY_CMD% -m app.main

pause
