@echo off
setlocal
title Push All Asset Dashboard to GitHub
cd /d "%~dp0"

echo ======================================================================
echo   Push All Asset Dashboard to GitHub
echo ======================================================================
echo.

python github_push.py

if errorlevel 1 (
    echo.
    echo [ERROR] Git push encountered an issue.
    pause
    exit /b 1
)

echo.
pause
