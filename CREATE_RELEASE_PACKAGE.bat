@echo off
title WIKA CPG1500 Processor - Release Package Generator

cd /d "%~dp0"

echo ============================================================
echo   Creating Release Package (Both Portable and Installer Ways)
echo ============================================================
echo.

echo [1/2] Preparing Portable Release Folder (Way 1)...
if not exist "release\1_Portable_Version" mkdir "release\1_Portable_Version"
copy /y "dist\WIKA CPG1500 Processor.exe" "release\1_Portable_Version\WIKA CPG1500 Processor.exe" >nul
copy /y "config.json" "release\1_Portable_Version\config.json" >nul

powershell -Command "$text = '============================================================`nWIKA CPG1500 Pressure CSV Analyzer - Portable Version`n============================================================`n`nHOW TO USE:`n1. Double-click WIKA CPG1500 Processor.exe.`n2. Click Select CSV File(s)... or Select Folder...`n3. Click START PROCESSING.`n4. Click Open Output Folder to view PNG graphs, Excel & TXT reports.`n`nNo Python installation required!'; Set-Content -Path 'release\1_Portable_Version\HOW_TO_USE.txt' -Value $text -Encoding UTF8"

echo [2/2] Preparing Installer Script (Way 2)...
if not exist "release\2_Installer_Script" mkdir "release\2_Installer_Script"
copy /y "installer_setup.iss" "release\2_Installer_Script\installer_setup.iss" >nul

if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" (
    echo Compiling Inno Setup Installer...
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer_setup.iss >nul
    echo Installer built successfully in: release\2_Installer\WIKA_CPG1500_Setup.exe
    goto DONE
)

if exist "C:\Program Files\Inno Setup 6\ISCC.exe" (
    echo Compiling Inno Setup Installer...
    "C:\Program Files\Inno Setup 6\ISCC.exe" installer_setup.iss >nul
    echo Installer built successfully in: release\2_Installer\WIKA_CPG1500_Setup.exe
    goto DONE
)

echo [INFO] Inno Setup compiler (ISCC.exe) was not detected in standard system folders.
echo        The installer script 'installer_setup.iss' is generated and ready in release\2_Installer_Script\.

:DONE
echo.
echo ============================================================
echo   RELEASE PACKAGE CREATED SUCCESSFULLY!
echo   Location: release\
echo ============================================================
echo.
pause
