@echo off
title WIKA CPG1500 Processor - App Builder

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo ============================================================
    echo   Virtual environment .venv was not found!
    echo   Installing environment first...
    echo ============================================================
    call INSTALL.bat
    if %errorlevel% neq 0 (
        echo [ERROR] Environment installation failed.
        pause
        exit /b 1
    )
)

echo ============================================================
echo   Building Single-File Windows Executable with PyInstaller...
echo ============================================================
echo.

.venv\Scripts\pip.exe install pyinstaller >nul 2>&1

.venv\Scripts\pyinstaller.exe --clean wika_app.spec

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] PyInstaller build failed!
    pause
    exit /b 1
)

echo.
echo [1/2] Copying configuration file to dist...
copy /y config.json "dist\config.json" >nul

echo.
echo ============================================================
echo   BUILD COMPLETED SUCCESSFULLY!
echo   Single File Executable: dist\WIKA CPG1500 Processor.exe
echo ============================================================
echo.
pause
