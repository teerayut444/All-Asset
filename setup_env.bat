@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
title All Asset Dashboard - Environment Setup

cd /d "%~dp0"

echo ======================================================================
echo   All Asset NPA Intelligence - Environment Setup
echo   สร้าง .venv และติดตั้ง requirements.txt สำหรับเครื่องใหม่
echo ======================================================================
echo.

:: ตรวจสอบ Python
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

echo [ERROR] ไม่พบ Python บนเครื่องนี้ กรุณาติดตั้ง Python จาก https://www.python.org/
echo และอย่าลืมติ๊ก "Add Python to PATH"
echo.
pause
exit /b 1

:python_found
echo [Info] ตรวจพบ Python: %PYTHON_CMD%
%PYTHON_CMD% --version
echo.

:: ตรวจสอบหรือสร้าง .venv
if not exist ".venv\Scripts\python.exe" (
    echo [1/3] กำลังสร้าง Virtual Environment (.venv)...
    %PYTHON_CMD% -m venv .venv
    if errorlevel 1 (
        echo [ERROR] สร้าง .venv ล้มเหลว
        pause
        exit /b 1
    )
    echo [Success] สร้าง .venv สำเร็จ
) else (
    echo [1/3] มี .venv อยู่แล้ว ข้ามขั้นตอนการสร้าง
)

echo.
echo [2/3] กำลังอัปเกรด pip...
".venv\Scripts\python.exe" -m pip install --upgrade pip

echo.
echo [3/3] กำลังติดตั้ง Dependencies จาก requirements.txt...
".venv\Scripts\pip.exe" install -r requirements.txt

if errorlevel 1 (
    echo.
    echo [ERROR] ติดตั้ง dependencies ไม่สำเร็จ กรุณาตรวจสอบอินเทอร์เน็ต
) else (
    echo.
    echo ======================================================================
    echo   [SUCCESS] ติดตั้งสภาพแวดล้อม (.venv + requirements) เสร็จสมบูรณ์!
    echo   คุณสามารถดับเบิ้ลคลิก 'run_dashboard.bat' หรือ 'setup_and_run.bat' ได้ทันที
    echo ======================================================================
)

echo.
pause
