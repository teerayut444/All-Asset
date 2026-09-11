@echo off
setlocal
title Build All_Asset_Dashboard.exe

cd /d "%~dp0"

echo ======================================================================
echo   Build All_Asset_Dashboard.exe (PyInstaller)
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
    echo [ERROR] Python not found. Please ensure Python is installed and in PATH.
    pause
    exit /b 1
)

echo [Python] Using: %PYTHON_EXE%

:: 2. Check PyInstaller
"%PYTHON_EXE%" -m PyInstaller --version >nul 2>nul
if errorlevel 1 (
    echo [Info] PyInstaller not found. Installing PyInstaller...
    "%PYTHON_EXE%" -m pip install pyinstaller
)
"%PYTHON_EXE%" -m PyInstaller --version >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Failed to find or install PyInstaller.
    pause
    exit /b 1
)

echo [Build] Compiling All_Asset_Dashboard.exe from packaging/All_Asset_Dashboard.spec...
echo.

:: 3. Run PyInstaller
"%PYTHON_EXE%" -m PyInstaller --clean --noconfirm packaging/All_Asset_Dashboard.spec
if errorlevel 1 goto build_failed

:: 4. Copy to Root Directory
if not exist "dist\All_Asset_Dashboard.exe" goto missing_dist

echo.
echo [Deploy] Copying dist\All_Asset_Dashboard.exe to root folder...
copy /y "dist\All_Asset_Dashboard.exe" "All_Asset_Dashboard.exe" >nul
if errorlevel 1 goto copy_failed

echo.
echo ======================================================================
echo   [SUCCESS] All_Asset_Dashboard.exe built and updated successfully!
echo   File location: All_Asset_Dashboard.exe
echo ======================================================================
goto cleanup

:copy_failed
echo.
echo [WARNING] Could not overwrite root All_Asset_Dashboard.exe (is it running?)
echo The new build is available at: dist\All_Asset_Dashboard.exe
goto cleanup

:missing_dist
echo.
echo [ERROR] dist\All_Asset_Dashboard.exe was not created.
goto cleanup

:build_failed
echo.
echo ======================================================================
echo   [ERROR] Build Failed! Check the error messages above.
echo ======================================================================

:cleanup
if exist "build" rmdir /s /q "build" 2>nul
echo.
pause
