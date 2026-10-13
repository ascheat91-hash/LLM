@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"
title FOXSI Assistant - Automated Installer

echo =======================================================
echo   FOXSI Local AI Voice Assistant - Windows Installer
echo =======================================================
echo.

:: 1. Check Python installation
echo [1/7] Checking Python installation...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not found in PATH!
    echo Please install Python 3.10, 3.11, or 3.12 from https://www.python.org/
    echo Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)
for /f "tokens=*" %%i in ('python --version') do echo [OK] Found %%i

:: 2. Create required project directories
echo.
echo [2/7] Creating required directories...
if not exist "models" mkdir models
if not exist "voices" mkdir voices
if not exist "data" mkdir data
if not exist "logs" mkdir logs
echo [OK] Directories verified (models, voices, data, logs)

:: 3. Setup Virtual Environment (Optional or direct)
echo.
echo [3/7] Setting up Python environment...
if not exist "venv" (
    echo Creating virtual environment in venv\...
    python -m venv venv
    if %errorlevel% neq 0 (
        echo [WARNING] Failed to create venv, falling back to current Python interpreter.
        set "PY_CMD=python"
    ) else (
        set "PY_CMD=venv\Scripts\python.exe"
    )
) else (
    set "PY_CMD=venv\Scripts\python.exe"
)

:: 4. Install dependencies
echo.
echo [4/7] Installing / Verifying requirements...
%PY_CMD% -m pip install --upgrade pip
%PY_CMD% -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install required packages! Check error messages above.
    pause
    exit /b 1
)
echo [OK] Dependencies installed successfully.

:: 5. Validate Audio and Speech Dependencies
echo.
echo [5/7] Validating Speech Recognition, TTS, and Audio I/O...
%PY_CMD% -c "import sounddevice, soundfile, faster_whisper, piper, pyttsx3; print('[OK] Audio engines (Whisper, Piper, SoundDevice) verified!')"
if %errorlevel% neq 0 (
    echo [ERROR] Audio dependencies validation failed!
    pause
    exit /b 1
)

:: 6. Validate LLM Runtime
echo.
echo [6/7] Validating Local GGUF LLM Runtime...
%PY_CMD% -c "import llama_cpp; print('[OK] llama.cpp runtime (v' + llama_cpp.__version__ + ') verified!')"
if %errorlevel% neq 0 (
    echo [ERROR] llama-cpp-python runtime validation failed!
    pause
    exit /b 1
)

:: 7. Validate Web Server
echo.
echo [7/7] Validating FastAPI and Uvicorn Server...
%PY_CMD% -c "import fastapi, uvicorn; print('[OK] FastAPI and Uvicorn verified!')"
if %errorlevel% neq 0 (
    echo [ERROR] Web server validation failed!
    pause
    exit /b 1
)

echo.
echo =======================================================
echo   INSTALLATION COMPLETED SUCCESSFULLY!
echo   You can now run: start.bat
echo =======================================================
echo.
pause
