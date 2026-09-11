@echo off
setlocal
title Build All_Asset_Dashboard_Portable

cd /d "%~dp0"

echo ======================================================================
echo   Build Standalone Portable All_Asset_Dashboard
echo   (สามารถนำโฟลเดอร์ผลลัพธ์ไปรันบนทุกเครื่อง Windows ได้ทันที)
echo ======================================================================
echo.

:: 1. Detect Python
set "PYTHON_EXE="
if exist "%~dp0.venv\Scripts\python.exe" set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"
if not defined PYTHON_EXE if exist ".venv\Scripts\python.exe" set "PYTHON_EXE=.venv\Scripts\python.exe"
if not defined PYTHON_EXE (
    where python >nul 2>nul
    if %errorlevel% equ 0 set "PYTHON_EXE=python"
)
if not defined PYTHON_EXE (
    where py >nul 2>nul
    if %errorlevel% equ 0 set "PYTHON_EXE=py"
)

if not defined PYTHON_EXE (
    echo [ERROR] ไม่พบ Python ในระบบ กรุณาติดตั้ง Python ก่อนดำเนินการ
    pause
    exit /b 1
)

echo [Python] ใช้: %PYTHON_EXE%

:: 2. Check PyInstaller
"%PYTHON_EXE%" -m PyInstaller --version >nul 2>nul
if errorlevel 1 (
    echo [Info] กำลังติดตั้ง PyInstaller...
    "%PYTHON_EXE%" -m pip install pyinstaller
)
"%PYTHON_EXE%" -m PyInstaller --version >nul 2>nul
if errorlevel 1 (
    echo [ERROR] ไม่สามารถติดตั้งหรือเรียกใช้ PyInstaller ได้
    pause
    exit /b 1
)

echo [Build] กำลังคอมไพล์แพ็กเกจ Standalone Portable...
echo         (ขั้นตอนนี้อาจใช้เวลาประมาณ 1-3 นาทีในการรวบรวมไฟล์ทั้งหมด)
echo.

:: 3. Run PyInstaller
"%PYTHON_EXE%" -m PyInstaller --clean --noconfirm packaging/build_portable.spec
if errorlevel 1 goto build_failed

:: 4. Verify Output and Sync Files
if not exist "dist\All_Asset_Dashboard_Portable\All_Asset_Dashboard.exe" goto missing_dist

echo.
echo [Deploy] ซิงค์ไฟล์ข้อมูลและสคริปต์หลักไปยัง dist\All_Asset_Dashboard_Portable...
for %%F in (app.py all_assets.parquet sam_analytics.py monthly_comparison.py bubble_chart.py dashboard_metrics.py convert_csv_to_parquet.py) do (
    if exist "%%F" copy /y "%%F" "dist\All_Asset_Dashboard_Portable\" >nul
)
if exist "assets" xcopy /e /i /y "assets" "dist\All_Asset_Dashboard_Portable\assets" >nul
if exist "static" xcopy /e /i /y "static" "dist\All_Asset_Dashboard_Portable\static" >nul

echo.
echo ======================================================================
echo   [SUCCESS] คอมไพล์ Standalone Portable สำเร็จเรียบร้อย!
echo ======================================================================
echo.
echo โฟลเดอร์แพ็กเกจพร้อมใช้งาน:
echo   - ที่อยู่: "%~dp0dist\All_Asset_Dashboard_Portable"
echo.
echo วิธีนำไปใช้งานบนเครื่องอื่น:
echo   1. ก๊อปปี้โฟลเดอร์ "All_Asset_Dashboard_Portable" ไปทั้งโฟลเดอร์
echo   2. ดับเบิลคลิก "All_Asset_Dashboard.exe" ในโฟลเดอร์นั้น
echo   3. รันได้ทันทีบน Windows ทุกเครื่องโดยไม่ต้องลง Python!
echo.
pause
exit /b 0

:build_failed
echo.
echo [ERROR] การบิลด์ด้วย PyInstaller ล้มเหลว กรุณาตรวจสอบข้อความ Error ด้านบน
pause
exit /b 1

:missing_dist
echo.
echo [ERROR] ไม่พบไฟล์ dist\All_Asset_Dashboard_Portable\All_Asset_Dashboard.exe
pause
exit /b 1
