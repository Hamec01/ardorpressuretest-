@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul

echo ======================================================================
echo          ARDOR Pressure Test — Local System Launcher
echo ======================================================================
echo.

:: 1. Determine Root Directory
set "ROOT_DIR=%~dp0"
if "%ROOT_DIR:~-1%"=="\" set "ROOT_DIR=%ROOT_DIR:~0,-1%"
cd /d "%ROOT_DIR%"

:: 2. Detect Python Virtual Environment
set "PYTHON_EXE=%ROOT_DIR%\.venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" (
    echo [!] Virtual environment not found at: %PYTHON_EXE%
    echo [*] Checking system python...
    where python >nul 2>&1
    if %errorlevel% neq 0 (
        echo [ERROR] Python is not installed or not in PATH!
        echo Please install Python 3.11+ and create .venv.
        pause
        exit /b 1
    )
    set "PYTHON_EXE=python"
)

echo [✓] Using Python: %PYTHON_EXE%

:: 3. Detect Node / NPM
where npm >nul 2>&1
if %errorlevel% neq 0 (
    echo [WARNING] npm is not found in PATH.
    echo Make sure Node.js is installed to run the Web UI.
)

:: 4. Start FastAPI Backend in separate window
echo.
echo [1/2] Starting Backend API on http://127.0.0.1:8000 ...
start "ARDOR Backend API (Port 8000)" cmd /k "cd /d "%ROOT_DIR%" && "%PYTHON_EXE%" -m uvicorn services.api.main:app --host 127.0.0.1 --port 8000 --reload"

:: 5. Start React Web UI in separate window
echo [2/2] Starting Web UI on http://localhost:5173 ...
if exist "%ROOT_DIR%\apps\web\node_modules" (
    start "ARDOR Web UI (Port 5173)" cmd /k "cd /d "%ROOT_DIR%\apps\web" && npm run dev"
) else (
    echo [*] Installing frontend dependencies first...
    start "ARDOR Web UI (Port 5173)" cmd /k "cd /d "%ROOT_DIR%\apps\web" && npm install && npm run dev"
)

:: 6. Wait 3 seconds and open default browser
timeout /t 3 /nobreak >nul
start http://localhost:5173

echo.
echo ======================================================================
echo   ARDOR Pressure Test is running successfully!
echo   ------------------------------------------------------------------
echo   • Web Application UI:     http://localhost:5173
echo   • REST API Documentation: http://127.0.0.1:8000/docs
echo   ------------------------------------------------------------------
echo   Default Credentials:
echo   - Foreman:  foreman_matti  / foreman123
echo   - Operator: operator_pekka / operator123
echo   - Admin:    admin          / admin123
echo ======================================================================
echo.
echo Press any key to exit this launcher window (services keep running in background).
pause >nul
