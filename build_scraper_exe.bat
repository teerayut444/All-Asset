@echo off
setlocal
title Build Scraper_Monthly_Parallel.exe
cd /d "%~dp0"

echo ======================================================================
echo   [BUILD] Scraper_Monthly_Parallel.exe (Standalone Parallel Scraper)
echo   Compiling 14-Platform Parallel Scraper
echo ======================================================================
echo.

set "PYTHON_EXE="
if exist "%~dp0.venv\Scripts\python.exe" (
    set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"
) else if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=.venv\Scripts\python.exe"
) else (
    where python >nul 2>nul
    if %errorlevel% equ 0 (
        set "PYTHON_EXE=python"
    ) else (
        where py >nul 2>nul
        if %errorlevel% equ 0 (
            set "PYTHON_EXE=py"
        )
    )
)

if not defined PYTHON_EXE (
    echo [ERROR] Python not found. Please install Python or setup .venv.
    echo.
    pause
    exit /b 1
)

echo [Environment] Python: %PYTHON_EXE%
echo [Executing]   "Py Scraper\build_exe.py"
echo.

"%PYTHON_EXE%" "Py Scraper\build_exe.py"

echo.
echo ======================================================================
echo   Build process finished!
echo   Target: %~dp0Scraper_Monthly_Parallel.exe
echo ======================================================================
echo.
pause
