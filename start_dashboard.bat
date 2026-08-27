@echo off
chcp 65001 >nul
setlocal
title All Asset Dashboard

cd /d "%~dp0"

echo ======================================================================
echo   All Asset NPA Intelligence Dashboard (Streamlit)
echo ======================================================================
echo.

:: ----------------------------------------------------------------------
:: 1. ตรวจสอบหรือสร้าง Virtual Environment (.venv)
:: ----------------------------------------------------------------------
if not exist ".venv\Scripts\python.exe" (
    echo [Info] ไม่พบ .venv กำลังตรวจสอบ Python บนเครื่อง...
    
    set "PYTHON_CMD="
    python --version >nul 2>&1 && set "PYTHON_CMD=python"
    if not defined PYTHON_CMD (
        py -3 --version >nul 2>&1 && set "PYTHON_CMD=py -3"
    )
    if not defined PYTHON_CMD (
        py --version >nul 2>&1 && set "PYTHON_CMD=py"
    )
    
    if not defined PYTHON_CMD (
        echo [ERROR] ไม่พบ Python บนเครื่องนี้!
        echo กรุณาติดตั้ง Python 3.10+ จาก https://www.python.org/
        echo และอย่าลืมติ๊กถูกที่ "Add Python to PATH"
        echo.
        pause
        exit /b 1
    )
    
    echo [Info] กำลังสร้าง Virtual Environment (.venv)...
    %PYTHON_CMD% -m venv .venv
    if errorlevel 1 (
        echo [ERROR] ไม่สามารถสร้าง .venv ได้
        pause
        exit /b 1
    )
    
    echo [Info] กำลังติดตั้ง Library จาก requirements.txt...
    ".venv\Scripts\python.exe" -m pip install --upgrade pip --quiet
    ".venv\Scripts\pip.exe" install -r requirements.txt
    if errorlevel 1 (
        echo [Warning] ติดตั้ง Library บางตัวไม่สำเร็จ กรุณาตรวจสอบอินเทอร์เน็ต
    )
    echo [Success] ติดตั้ง Dependencies เรียบร้อยแล้ว!
    echo.
)

:: ----------------------------------------------------------------------
:: 2. รัน Streamlit Dashboard ทันที
:: ----------------------------------------------------------------------
set "VENV_PYTHON=.venv\Scripts\python.exe"

echo [Launch] กำลังเปิด Streamlit Dashboard...
echo [URL]    http://localhost:8501
echo.

"%VENV_PYTHON%" -m streamlit run app.py --server.maxUploadSize=500 --browser.gatherUsageStats=false

if errorlevel 1 (
    echo.
    echo [Warning] เกิดข้อผิดพลาดหรือ Dashboard ถูกปิด
    echo [Info] กำลังลองติดตั้ง requirements.txt ซ้ำอีกครั้ง...
    "%VENV_PYTHON%" -m pip install -r requirements.txt
    echo.
    echo [Launch] ลองเปิด Dashboard ใหม่อีกครั้ง...
    "%VENV_PYTHON%" -m streamlit run app.py --server.maxUploadSize=500 --browser.gatherUsageStats=false
)

echo.
pause
