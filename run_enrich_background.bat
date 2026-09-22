@echo off
chcp 65001 >nul
title Launch LandsMaps Enrichment in Background

echo ====================================================================
echo   LandsMaps Enrichment: โหมดรันเบื้องหลังอัตโนมัติ (Background Mode)
echo ====================================================================
echo  - ซ่อนหน้าต่างเบราว์เซอร์ Chrome 100%% (Headless)
echo  - ย่อหน้าต่างการทำงานลง Taskbar อัตโนมัติ (Minimized)
echo  - บันทึกความคืบหน้าลง logs\enrich_landsmaps.log
echo ====================================================================
echo.

if not exist "logs" mkdir "logs"

echo กำลังเริ่มรันตัวดึงพิกัดในเบื้องหลัง...
start "LandsMaps Background Enrichment" /min python tools\enrich_led_landsmaps.py --headless

echo.
echo ✅ เริ่มต้นการทำงานเบื้องหลังเรียบร้อยแล้ว!
echo 💡 หน้าต่างจะย่ออยู่บน Taskbar คุณสามารถทำงานอื่นบนคอมพิวเตอร์ได้ตามปกติ
echo.
timeout /t 5
