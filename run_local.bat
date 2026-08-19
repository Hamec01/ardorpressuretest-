@echo off
REM =====================================================================
REM   ARDOR Pressure Test - Local System Launcher
REM =====================================================================

cd /d "%~dp0"
set "PROJECT_DIR=%CD%"

set "PYTHON_PATH=%PROJECT_DIR%\.venv\Scripts\python.exe"

if not exist "%PYTHON_PATH%" (
    set "PYTHON_PATH=python"
)

echo Starting ARDOR Backend API on http://127.0.0.1:8000 ...
start "ARDOR Backend API" cmd /k "cd /d "%PROJECT_DIR%" && "%PYTHON_PATH%" -m uvicorn services.api.main:app --host 127.0.0.1 --port 8000 --reload"

echo Starting ARDOR Web UI on http://localhost:5173 ...
start "ARDOR Web UI" cmd /k "cd /d "%PROJECT_DIR%\apps\web" && npm run dev"

timeout /t 3 /nobreak >nul
start http://localhost:5173

echo.
echo =====================================================================
echo   ARDOR Pressure Test is running!
echo   Web UI:      http://localhost:5173
echo   API Docs:    http://127.0.0.1:8000/docs
echo =====================================================================
echo.
pause
