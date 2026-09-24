@echo off
chcp 65001 >nul
cd /d "%~dp0"
title LandsMaps Chrome GUI Mode (แบบเปิดหน้าต่าง)

echo ====================================================================
echo   LandsMaps Real GPS Coordinates - โหมดเปิดหน้าต่างเบราว์เซอร์ Chrome
echo ====================================================================
echo  - เปิดหน้าต่าง Chrome ให้เห็นกระบวนการค้นหาและแปลงที่ดินบนแผนที่สดๆ
echo  - บันทึกพิกัดลง CSV และแคชอัตโนมัติเหมือนเดิม 100%%
echo  - สามารถย่อหน้าต่าง หรือลากไปไว้จออื่นขณะทำงานได้
echo ====================================================================
echo.

set PY_EXE=python
if exist ".venv\Scripts\python.exe" set PY_EXE=.venv\Scripts\python.exe

%PY_EXE% tools\enrich_led_landsmaps.py %*

pause
