@echo off
setlocal
title All Asset NPA Intelligence Dashboard (12 Sources)

cd /d "%~dp0"

echo ======================================================================
echo   All Asset NPA Intelligence Dashboard - 12 Sources
echo   SAM / BAM / KBANK / SCB / KTB / GHB / GSB / Chayo555 / NaYoo / Baania / ZmyHome / Taladnudbaan
echo ======================================================================
echo.

if exist ".venv\Scripts\python.exe" (
    echo [Info] Found virtual environment in .venv
    set "PYTHON_EXE=.venv\Scripts\python.exe"
    goto :launch
)

if exist "..\.venv\Scripts\python.exe" (
    echo [Info] Found virtual environment in parent folder
    set "PYTHON_EXE=..\.venv\Scripts\python.exe"
    goto :launch
)

set "PYTHON_EXE=python"
echo [Info] Using system python: %PYTHON_EXE%

:launch
echo.
echo [Launch] Starting Streamlit Dashboard for 12 NPA Sources...
echo [Path] Using Python: %PYTHON_EXE%
echo [URL]  http://localhost:8501
echo.

"%PYTHON_EXE%" -m streamlit run app.py --server.maxUploadSize=500 --browser.gatherUsageStats=false

if errorlevel 1 (
    echo.
    echo [Warning] Streamlit exited or encountered an error.
    echo [Info] Checking and updating required dependencies...
    if exist "requirements.txt" (
        "%PYTHON_EXE%" -m pip install -r requirements.txt
    ) else (
        "%PYTHON_EXE%" -m pip install streamlit pandas openpyxl plotly pydeck pillow requests pyarrow
    )
    echo.
    echo [Launch] Retrying Streamlit Dashboard...
    "%PYTHON_EXE%" -m streamlit run app.py --server.maxUploadSize=500 --browser.gatherUsageStats=false
)

echo.
pause
