@echo off
chcp 65001 >nul
title LandsMaps Real Coordinates Enrichment Tool

echo ====================================================================
echo   LandsMaps Real GPS Coordinates Enrichment for LED Assets
echo ====================================================================
echo.
echo This tool searches real GPS coordinates from the Department of Lands
echo (https://landsmaps.dol.go.th/) using deed numbers for LED assets.
echo Progress is saved incrementally in data\led_coords_cache.parquet
echo.

set /p PROV="Enter Province to filter (e.g. ปทุมธานี or press Enter for ALL): "
set /p LIMIT="Enter Deed Limit (e.g. 50 or press Enter for ALL pending): "

set CMD_ARGS=

if not "%PROV%"=="" (
    set CMD_ARGS=%CMD_ARGS% --province %PROV%
)

if not "%LIMIT%"=="" (
    set CMD_ARGS=%CMD_ARGS% --limit %LIMIT%
)

echo.
echo Starting enrichment with args: %CMD_ARGS%
echo ====================================================================

python tools\enrich_led_landsmaps.py %CMD_ARGS%

echo.
echo ====================================================================
echo Finished processing.
echo ====================================================================
pause
