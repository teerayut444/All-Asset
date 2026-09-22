@echo off
setlocal
chcp 65001 > nul
title Merge Monthly CSV & Generate Parquet

cd /d "%~dp0"

echo ======================================================================
echo   All Asset NPA: Merge Monthly CSV & Parquet Generator
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
    echo [ERROR] Python not found. Please install Python or set up .venv.
    echo.
    pause
    exit /b 1
)

echo [Environment] Using: %PYTHON_EXE%
echo [Executing]   Py Scraper\merge_csv_monthly.py
echo.

"%PYTHON_EXE%" "Py Scraper\merge_csv_monthly.py"

echo.
echo ======================================================================
echo กระบวนการทำงานเสร็จสิ้นแล้ว
echo ======================================================================
pause
