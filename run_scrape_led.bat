@echo off
chcp 65001 >nul
title Scrape LED Assets & Auto Fetch Real LandsMaps Coordinates

echo ====================================================================
echo   LED NPA Intelligence: ระบบดึงข้อมูลและพิกัดจริงแบบอัตโนมัติ 100%%
echo ====================================================================
echo  - Phase 1: สแครปข้อมูลประกาศขายทอดตลาดจากกรมบังคับคดี (LED)
echo  - Phase 2: ค้นหาพิกัดจริงระดับแปลงจาก LandsMaps (Single-Tab Loop)
echo  - Sync: อัปเดตพิกัดจริงลงไฟล์ CSV และ all_assets.parquet สำหรับ Dashboard
echo ====================================================================
echo.

python "Py Scraper\scrape_led_monthly.py" %*

echo.
echo ====================================================================
echo 🎉 เสร็จสิ้นกระบวนการ LED ทั้งหมด 100%% เรียบร้อยแล้ว!
echo 📊 ข้อมูลพร้อมใช้งานบน All Asset Dashboard ทันที
echo ====================================================================
pause
