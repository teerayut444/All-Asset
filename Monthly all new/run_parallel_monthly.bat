@echo off
chcp 65001 > nul
title Monthly Parallel All Asset NPA Scrapers Launcher
echo ==========================================================================
echo Starting Monthly Parallel Scrapers (12 Sources)...
echo [ SAM / BAM / KBANK / SCB / KTB / GHB / GSB / Chayo555 / NaYoo / Baania / ZmyHome / Taladnudbaan ]
echo Folder: Monthly all new
echo ==========================================================================
echo.

python run_parallel_monthly.py

echo.
echo ==========================================================================
echo Scrape processes completed. Press any key to exit...
echo ==========================================================================
pause > nul
