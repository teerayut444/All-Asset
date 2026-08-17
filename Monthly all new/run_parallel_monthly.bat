@echo off
chcp 65001 > nul
title Monthly Parallel All Asset NPA Scrapers Launcher
echo ==========================================================================
echo Starting Monthly Parallel Scrapers (6 Companies)...
echo Folder: Monthly all new
echo ==========================================================================
echo.

python run_parallel_monthly.py

echo.
echo ==========================================================================
echo Scrape processes completed. Press any key to exit...
echo ==========================================================================
pause > nul
