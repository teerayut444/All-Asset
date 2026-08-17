@echo off
setlocal enabledelayedexpansion
title NPA Data Quality and Visual QA Dashboard

echo ==============================================================================
echo   NPA Data Quality and Visual QA Dashboard
echo   Data Completeness Audit and Live Webpage Screenshot QA
echo ==============================================================================
echo.

cd /d "%~dp0"

set "PYTHON_EXE="

if exist "..\.venv\Scripts\python.exe" (
    set "PYTHON_EXE=..\.venv\Scripts\python.exe"
    goto found_python
)

if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=.venv\Scripts\python.exe"
    goto found_python
)

if exist "..\Livinginsider NPA\.venv\Scripts\python.exe" (
    set "PYTHON_EXE=..\Livinginsider NPA\.venv\Scripts\python.exe"
    goto found_python
)

if exist "..\BAM NPA\.venv\Scripts\python.exe" (
    set "PYTHON_EXE=..\BAM NPA\.venv\Scripts\python.exe"
    goto found_python
)

where python >nul 2>nul
if %errorlevel% equ 0 (
    set "PYTHON_EXE=python"
    goto found_python
)

echo [ERROR] Python not found in virtual environments or system PATH.
pause
exit /b 1

:found_python
echo [*] Using Python: %PYTHON_EXE%
echo [*] Starting Streamlit QA Application on Port 8502...
echo.

"%PYTHON_EXE%" -m streamlit run app.py --server.port 8502 --server.headless false

pause
