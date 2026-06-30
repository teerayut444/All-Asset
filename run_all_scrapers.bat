@echo off
title All Asset NPA Scrapers Runner
echo ===================================================
echo   All Asset NPA Scrapers Runner
echo ===================================================
echo.
echo Checking virtual environments or global python...
echo.

set VENV_PATH=..\BAM NPA\.venv
if exist "%VENV_PATH%\Scripts\activate.bat" (
    echo [Info] Found virtual environment in BAM NPA folder. Activating...
    call "%VENV_PATH%\Scripts\activate.bat"
    goto run
)

set VENV_PATH_ZMY=..\ZmyHome NPA\.venv
if exist "%VENV_PATH_ZMY%\Scripts\activate.bat" (
    echo [Info] Found virtual environment in ZmyHome NPA folder. Activating...
    call "%VENV_PATH_ZMY%\Scripts\activate.bat"
    goto run
)

echo [Info] No local virtual environment found. Using global python environment.

:run
echo.
echo [Launch] Starting all scrapers and merging data...
python run_all_scrapers.py
if %errorlevel% neq 0 (
    echo.
    echo [Error] Failed to run scrapers. Please verify python dependencies.
)

pause
