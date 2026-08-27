@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
title All Asset Dashboard - Setup & Launcher

cd /d "%~dp0"

echo ======================================================================
echo   All Asset NPA Intelligence Dashboard - One-Click Setup & Launcher
echo   รองรับการติดตั้งและรันเครื่องใหม่โดยอัตโนมัติ (New Machine Auto-Setup)
echo ======================================================================
echo.

:: ----------------------------------------------------------------------
:: 1. ตรวจสอบการติดตั้ง Python บนระบบ
:: ----------------------------------------------------------------------
set "PYTHON_CMD="

python --version >nul 2>&1
if %errorlevel% equ 0 (
    set "PYTHON_CMD=python"
    goto :python_found
)

py -3 --version >nul 2>&1
if %errorlevel% equ 0 (
    set "PYTHON_CMD=py -3"
    goto :python_found
)

py --version >nul 2>&1
if %errorlevel% equ 0 (
    set "PYTHON_CMD=py"
    goto :python_found
)

:: ไม่พบ Python
echo ======================================================================
echo  [ERROR] ไม่พบ Python บนเครื่องนี้ (Python is not installed or not in PATH)
echo ======================================================================
echo.
echo  วิธีแก้ไข:
echo  1. ดาวน์โหลดและติดตั้ง Python (แนะนำ 3.10 - 3.12) จาก:
echo     https://www.python.org/downloads/
echo  2. *** ข้อสำคัญ *** ระหว่างติดตั้งให้ติ๊กถูกที่:
echo     [✓] "Add Python to PATH" หรือ "Add python.exe to PATH"
echo  3. เมื่อติดตั้งเสร็จ ให้เปิดไฟล์นี้ (.bat) ใหม่อีกครั้ง
echo.
pause
exit /b 1

:python_found
echo [Info] ตรวจพบ Python บนเครื่อง: %PYTHON_CMD%
%PYTHON_CMD% --version
echo.

:: ----------------------------------------------------------------------
:: 2. ตรวจสอบและสร้าง Virtual Environment (.venv)
:: ----------------------------------------------------------------------
if exist ".venv\Scripts\python.exe" (
    echo [Info] พบ Virtual Environment (.venv) แล้ว
) else (
    echo ======================================================================
    echo  [Step 1/3] กำลังสร้าง Virtual Environment (.venv)...
    echo ======================================================================
    %PYTHON_CMD% -m venv .venv
    if errorlevel 1 (
        echo [ERROR] ไม่สามารถสร้าง .venv ได้ กรุณาตรวจสอบสิทธิ์ของโฟลเดอร์
        pause
        exit /b 1
    )
    echo [Success] สร้าง Virtual Environment (.venv) สำเร็จ!
    echo.
)

set "VENV_PYTHON=.venv\Scripts\python.exe"
set "VENV_PIP=.venv\Scripts\pip.exe"

:: ----------------------------------------------------------------------
:: 3. อัปเกรด pip
:: ----------------------------------------------------------------------
echo ======================================================================
echo  [Step 2/3] กำลังตรวจสอบและอัปเกรด pip...
echo ======================================================================
"%VENV_PYTHON%" -m pip install --upgrade pip --quiet

:: ----------------------------------------------------------------------
:: 4. ติดตั้ง Library ตาม requirements.txt
:: ----------------------------------------------------------------------
echo.
echo ======================================================================
echo  [Step 3/3] กำลังติดตั้ง Dependencies จาก requirements.txt...
echo ======================================================================
if exist "requirements.txt" (
    "%VENV_PIP%" install -r requirements.txt
) else (
    echo [Warning] ไม่พบไฟล์ requirements.txt กำลังติดตั้งชุดแพ็กเกจหลัก...
    "%VENV_PIP%" install streamlit pandas numpy plotly pyarrow openpyxl pydeck Pillow requests scipy beautifulsoup4 shapely curl_cffi
)

if errorlevel 1 (
    echo.
    echo [Warning] เกิดข้อผิดพลาดในการติดตั้งบางแพ็กเกจ กรุณาตรวจสอบการเชื่อมต่ออินเทอร์เน็ต
) else (
    echo.
    echo [Success] ติดตั้ง Dependencies ทั้งหมดเรียบร้อยแล้ว!
)

:: ----------------------------------------------------------------------
:: 5. เมนูเลือกการทำงาน (Dashboard หรือ Scrapers)
:: ----------------------------------------------------------------------
:menu
echo.
echo ======================================================================
echo   เลือกการทำงาน (All Asset NPA Intelligence)
echo ======================================================================
echo   [1] เปิด All Asset Dashboard (Streamlit Web App)
echo   [2] รัน Scraper ดึงข้อมูล NPA 12 แหล่ง (Parallel)
echo   [3] ตรวจสอบ/ติดตั้ง Dependencies ใหม่อีกครั้ง (Re-install requirements)
echo   [4] ออกจากโปรแกรม (Exit)
echo ======================================================================
set /p choice="กรุณาเลือกเมนู [1-4] (กด Enter เพื่อเลือก 1): "

if "%choice%"=="" set choice=1
if "%choice%"=="1" goto :launch_dashboard
if "%choice%"=="2" goto :launch_scrapers
if "%choice%"=="3" goto :reinstall
if "%choice%"=="4" exit /b 0

echo.
echo [!] ตัวเลือกไม่ถูกต้อง กรุณาเลือกหมายเลข 1, 2, 3 หรือ 4
goto :menu

:launch_dashboard
echo.
echo ======================================================================
echo  [Launch] กำลังเปิด Streamlit Dashboard...
echo  [URL]    http://localhost:8501
echo ======================================================================
echo.
"%VENV_PYTHON%" -m streamlit run app.py --server.maxUploadSize=500 --browser.gatherUsageStats=false
if errorlevel 1 (
    echo.
    echo [Warning] Streamlit ปิดการทำงานหรือเกิดข้อผิดพลาด
)
pause
goto :menu

:launch_scrapers
echo.
echo ======================================================================
echo  [Launch] กำลังเริ่มรัน Scrapers ทั้ง 12 แหล่งข้อมูล (Parallel Mode)...
echo ======================================================================
echo.
"%VENV_PYTHON%" run_all_scrapers.py --parallel
if errorlevel 1 (
    echo.
    echo [Error] Scraper ทำงานไม่สำเร็จ กรุณาตรวจสอบ Network หรือ log
)
pause
goto :menu

:reinstall
echo.
echo [Info] กำลังติดตั้ง Dependencies ใหม่...
"%VENV_PIP%" install -r requirements.txt --upgrade
echo.
pause
goto :menu
