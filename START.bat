@echo off
title WIKA CPG1500 Graph Processor

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo ============================================================
    echo   Virtual environment .venv was not found!
    echo   Starting automatic installation...
    echo ============================================================
    echo.
    call INSTALL.bat
    if %errorlevel% neq 0 (
        echo [ERROR] Automatic installation failed!
        pause
        exit /b 1
    )
)

echo ============================================================
echo   Running WIKA CPG1500 CSV Data Processing...
echo ============================================================
echo.

set PYTHONPATH=src
.venv\Scripts\python.exe -m wika_report %*

set APP_EXIT_CODE=%errorlevel%

echo.
if %APP_EXIT_CODE% equ 0 (
    echo [SUCCESS] Processing completed without critical errors.
) else (
    echo [WARNING] Finished with exit code %APP_EXIT_CODE%.
    echo Check logs in output\logs\app.log
)

echo.
pause
exit /b %APP_EXIT_CODE%
