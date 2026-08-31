@echo off
setlocal
title All Asset Dashboard Launcher

cd /d "%~dp0"

echo ======================================================================
echo   All Asset NPA Intelligence Dashboard - 14 Sources
echo   LED / SAM / BAM / Chayo555 / GHB / KBANK / KTB / SCB / GSB /
echo   DDproperty / Livinginsider / NaYoo / ZmyHome / Baania
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
    echo [ERROR] Python not found on this machine!
    echo Please install Python 3.10+ and make sure to check "Add Python to PATH".
    pause
    exit /b 1
)

echo [Launch] Starting Streamlit Dashboard...
echo [Path]   Using Python: %PYTHON_EXE%
echo [URL]    http://localhost:8501
echo.

"%PYTHON_EXE%" -m streamlit run app.py --server.maxUploadSize=500 --browser.gatherUsageStats=false

if %errorlevel% neq 0 (
    echo.
    echo [Warning] Streamlit exited or encountered an error.
    echo [Info] Checking dependencies...
    "%PYTHON_EXE%" -m pip install -r requirements.txt
    echo.
    echo [Launch] Retrying Streamlit Dashboard...
    "%PYTHON_EXE%" -m streamlit run app.py --server.maxUploadSize=500 --browser.gatherUsageStats=false
)

echo.
pause
