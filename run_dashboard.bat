@echo off
chcp 65001 >nul
setlocal
title All Asset NPA Intelligence Dashboard (12 Sources)

cd /d "%~dp0"

echo ======================================================================
echo   All Asset NPA Intelligence Dashboard - 12 Sources
echo   SAM / BAM / KBANK / SCB / KTB / GHB / GSB / Chayo555 / NaYoo / Baania / ZmyHome / Taladnudbaan
echo ======================================================================
echo.

:: 1. ตรวจสอบว่ามี .venv หรือไม่
if exist ".venv\Scripts\python.exe" (
    echo [Info] พบ Virtual Environment ใน .venv
    set "PYTHON_EXE=.venv\Scripts\python.exe"
    goto :launch
)

if exist "..\.venv\Scripts\python.exe" (
    echo [Info] พบ Virtual Environment ใน parent folder
    set "PYTHON_EXE=..\.venv\Scripts\python.exe"
    goto :launch
)

:: 2. หากยังไม่มี .venv ให้สร้างและติดตั้ง dependencies ให้อัตโนมัติ
echo [Info] ไม่พบ .venv ในเครื่อง กำลังสร้างและติดตั้งสภาพแวดล้อมให้อัตโนมัติ...
set "SYS_PYTHON="
python --version >nul 2>&1 && set "SYS_PYTHON=python"
if not defined SYS_PYTHON (
    py -3 --version >nul 2>&1 && set "SYS_PYTHON=py -3"
)
if not defined SYS_PYTHON (
    py --version >nul 2>&1 && set "SYS_PYTHON=py"
)

if defined SYS_PYTHON (
    echo [Info] กำลังสร้าง .venv ด้วย %SYS_PYTHON%...
    %SYS_PYTHON% -m venv .venv
    if exist ".venv\Scripts\python.exe" (
        set "PYTHON_EXE=.venv\Scripts\python.exe"
        echo [Info] กำลังอัปเกรด pip และติดตั้ง Library จาก requirements.txt...
        ".venv\Scripts\python.exe" -m pip install --upgrade pip --quiet
        if exist "requirements.txt" (
            ".venv\Scripts\pip.exe" install -r requirements.txt
        )
        echo [Success] สร้างและติดตั้งสภาพแวดล้อมเรียบร้อยแล้ว!
        goto :launch
    )
)

set "PYTHON_EXE=python"
echo [Info] Using system python: %PYTHON_EXE%

:launch
echo.
echo [Launch] Starting Streamlit Dashboard for 12 NPA Sources...
echo [Path]   Using Python: %PYTHON_EXE%
echo [URL]    http://localhost:8501
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
