@echo off
title All Asset NPA Scrapers Runner (Monthly All New)
echo ======================================================================
echo   All Asset NPA Scrapers Runner
echo   [ Baania / BAM / SAM / ZmyHome / DDproperty / Taladnudbaan ]
echo   Source Folder: Monthly all new
echo ======================================================================
echo.

if exist ".venv\Scripts\activate.bat" (
    echo [Info] Found virtual environment in .venv folder. Activating...
    call ".venv\Scripts\activate.bat"
    goto run
)

if exist "..\.venv\Scripts\activate.bat" (
    echo [Info] Found virtual environment in parent folder. Activating...
    call "..\.venv\Scripts\activate.bat"
    goto run
)

echo [Info] Using global python environment.

:run
echo.
echo [Launch] Starting scrapers from 'Monthly all new' and generating all_assets.parquet...
echo.
python run_all_scrapers.py --parallel
if %errorlevel% neq 0 (
    echo.
    echo [Error] Failed to run scrapers. Please verify python dependencies.
)

pause
