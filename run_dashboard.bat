@echo off
setlocal enabledelayedexpansion
title All Asset NPA Dashboard Launcher (6 Companies)

:: Change directory to the folder where this batch file is located
cd /d "%~dp0"

echo ======================================================================
echo   All Asset NPA Dashboard Launcher - 6 Companies
echo   [ Baania / BAM / SAM / ZmyHome / DDproperty / Taladnudbaan ]
echo ======================================================================
echo.

:: Check local virtual environment executable directly
if exist ".venv\Scripts\python.exe" (
    echo [Info] Found local virtual environment in .venv folder.
    set "PYTHON_EXE=.venv\Scripts\python.exe"
    goto launch
)

:: Check parent virtual environment
if exist "..\.venv\Scripts\python.exe" (
    echo [Info] Found parent virtual environment.
    set "PYTHON_EXE=..\.venv\Scripts\python.exe"
    goto launch
)

:: Fallback to system python
set "PYTHON_EXE=python"
echo [Info] Using system python: %PYTHON_EXE%

:launch
echo.
echo [Launch] Starting Streamlit Dashboard for 6 Companies...
echo [Path] Using Python: %PYTHON_EXE%
echo.

"%PYTHON_EXE%" -m streamlit run app.py

if %errorlevel% neq 0 (
    echo.
    echo [Warning] Streamlit exited or encountered an error.
    echo [Info] Attempting to install / verify required dependencies...
    "%PYTHON_EXE%" -m pip install streamlit pandas openpyxl plotly bs4 requests pyarrow
    echo.
    echo [Launch] Retrying Streamlit Dashboard...
    "%PYTHON_EXE%" -m streamlit run app.py
)

pause
