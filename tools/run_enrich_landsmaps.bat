@echo off
chcp 65001 >nul
cd /d "%~dp0.."
title LandsMaps Real Coordinates Enrichment Tool

echo ====================================================================
echo   LandsMaps Real GPS Coordinates Enrichment for LED Assets
echo ====================================================================
echo ระบบดึงพิกัดจริงระดับแปลงจากโฉนดที่ดิน (https://landsmaps.dol.go.th/)
echo บันทึกแคชอัตโนมัติ: data\led_coords_cache.parquet
echo ====================================================================
echo.

set PY_EXE=python
if exist ".venv\Scripts\python.exe" set PY_EXE=.venv\Scripts\python.exe

if not "%1"=="" (
    echo รันด้วยคำสั่งพารามิเตอร์: %*
    %PY_EXE% tools\enrich_led_landsmaps.py %*
    goto end
)

echo เลือกรูปแบบการทำงาน:
echo  [1] รันเบื้องหลัง (Headless - ซ่อนหน้าต่างเบราว์เซอร์ ไม่กวนหน้าจอ) [แนะนำ]
echo  [2] รันแบบเปิดหน้าต่าง Chrome ให้เห็นการทำงาน
echo.
set /p MODE="เลือกโหมด [1/2] (กด Enter = [1] รันเบื้องหลัง): "

set CMD_ARGS=
if "%MODE%"=="2" (
    echo โหมด: เปิดหน้าต่างเบราว์เซอร์ Chrome
) else (
    echo โหมด: รันเบื้องหลัง (Headless)
    set CMD_ARGS=--headless
)
echo.

set /p PROV="ระบุจังหวัดที่ต้องการกรอง (เช่น ปทุมธานี หรือกด Enter เพื่อดึงทุกจังหวัด): "
set /p LIMIT="ระบุจำนวนโฉนดที่ต้องการดึง (เช่น 50, 100 หรือกด Enter เพื่อดึงทั้งหมด): "

if not "%PROV%"=="" (
    set CMD_ARGS=%CMD_ARGS% --province %PROV%
)

if not "%LIMIT%"=="" (
    set CMD_ARGS=%CMD_ARGS% --limit %LIMIT%
)

echo.
echo ====================================================================
echo กำลังเริ่มต้นค้นหาพิกัดจริง...
echo (สามารถกด Ctrl+C เพื่อหยุดเมื่อไหร่ก็ได้ ข้อมูลจะปลอดภัย 100%%)
echo ====================================================================
echo.

%PY_EXE% tools\enrich_led_landsmaps.py %CMD_ARGS%

:end
echo.
echo ====================================================================
echo Finished processing.
echo ====================================================================
pause
