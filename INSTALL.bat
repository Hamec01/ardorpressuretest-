@echo off
title WIKA CPG1500 Graph Processor - Installation

cd /d "%~dp0"

echo ============================================================
echo   Installing environment for WIKA CPG1500 Graph Processor
echo ============================================================
echo.

:: 1. Check Python installation
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python was not found on your system!
    echo Please install Python 3.11+ from https://www.python.org/
    echo Make sure to check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)

echo [1/4] Checking Python version...
for /f "tokens=2 delims= " %%v in ('python --version') do set PY_VER=%%v
echo Found Python version: %PY_VER%

echo [2/4] Creating virtual environment (.venv)...
if not exist ".venv" (
    python -m venv .venv
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to create virtual environment .venv!
        pause
        exit /b 1
    )
    echo Virtual environment created successfully.
) else (
    echo Virtual environment .venv already exists.
)

echo [3/4] Upgrading pip...
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip >nul 2>&1

echo [4/4] Installing dependencies from requirements.txt...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install dependencies!
    pause
    exit /b 1
)

echo [5/5] Installing wika-cpg1500-graph in editable mode...
pip install -e . >nul 2>&1

echo.
echo ============================================================
echo   Installation completed successfully!
echo   You can now run START.bat to process your CSV files.
echo ============================================================
echo.
pause
