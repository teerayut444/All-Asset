@echo off
setlocal
title All Asset NPA Scrapers Runner (12 Sources)
cd /d "%~dp0"

echo ======================================================================
echo   All Asset NPA Scrapers Runner (12 Sources)
echo   SAM / BAM / KBANK / SCB / KTB / GHB / GSB / Chayo555 / NaYoo / Baania / ZmyHome / Taladnudbaan
echo   Source Folder: Monthly all new
echo ======================================================================
echo.

if exist ".venv\Scripts\python.exe" (
    echo [Info] Found virtual environment in .venv
    set "PYTHON_EXE=.venv\Scripts\python.exe"
    goto :run
)

if exist "..\.venv\Scripts\python.exe" (
    echo [Info] Found virtual environment in parent folder
    set "PYTHON_EXE=..\.venv\Scripts\python.exe"
    goto :run
)

set "PYTHON_EXE=python"
echo [Info] Using system python: %PYTHON_EXE%

:run
echo.
echo [Launch] Starting scrapers for 12 NPA sources and generating all_assets.parquet...
echo.
"%PYTHON_EXE%" run_all_scrapers.py --parallel
if errorlevel 1 (
    echo.
    echo [Error] Scraper execution encountered an error. Please check dependencies or network.
)

echo.
pause
