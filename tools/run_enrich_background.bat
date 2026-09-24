@echo off
chcp 65001 >nul
cd /d "%~dp0.."
title Launch LandsMaps Enrichment in Background

echo ====================================================================
echo   LandsMaps Enrichment: โหมดรันเบื้องหลังอัตโนมัติ (Background Mode)
echo ====================================================================
echo  - ซ่อนหน้าต่างเบราว์เซอร์ Chrome 100%% (Headless)
echo  - ย่อหน้าต่างการทำงานลง Taskbar อัตโนมัติ (Minimized)
echo  - ซิงค์พิกัดลง CSV และ Parquet Cache อัตโนมัติ
echo ====================================================================
echo.

if not exist "logs" mkdir "logs"

set PY_EXE=python
if exist ".venv\Scripts\python.exe" set PY_EXE=.venv\Scripts\python.exe

echo กำลังเริ่มรันตัวดึงพิกัดในเบื้องหลัง...
start "LandsMaps Background Enrichment" /min %PY_EXE% tools\enrich_led_landsmaps.py --headless

echo.
echo ✅ เริ่มต้นการทำงานเบื้องหลังเรียบร้อยแล้ว!
echo 💡 หน้าต่างจะย่ออยู่บน Taskbar คุณสามารถทำงานอื่นบนคอมพิวเตอร์ได้ตามปกติ
echo.
timeout /t 5
