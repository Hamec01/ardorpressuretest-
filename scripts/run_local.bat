@echo off
chcp 65001 >nul
echo ========================================================
echo   ARDOR Pressure Test — Local System Launcher
echo ========================================================
echo.

cd /d "%~dp0\.."

if not exist ".venv" (
    echo [ERROR] Python virtual environment (.venv) not found.
    echo Please create virtual environment and install dependencies first:
    echo   python -m venv .venv
    echo   .venv\Scripts\pip install -e .
    pause
    exit /b 1
)

echo [1/2] Starting FastAPI Backend on http://127.0.0.1:8000 ...
start "ARDOR Backend API" cmd /k ".venv\Scripts\python.exe -m uvicorn services.api.main:app --host 127.0.0.1 --port 8000 --reload"

echo [2/2] Starting React Web App on http://localhost:5173 ...
cd apps\web
start "ARDOR Web UI" cmd /k "npm run dev"

echo.
echo ========================================================
echo   ARDOR Pressure Test is running:
echo   - Web UI: http://localhost:5173
echo   - Backend API & Docs: http://127.0.0.1:8000/docs
echo ========================================================
echo.
pause
