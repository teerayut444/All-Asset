# -*- coding: utf-8 -*-
# =========================================================================
# Build Dashboard Deploy Package
# สร้างโฟลเดอร์ที่นำไปรัน All Asset Dashboard บนเครื่องอื่นได้ทันที
# รันสคริปต์นี้ครั้งเดียว -> ได้โฟลเดอร์พร้อม Deploy เลย
# =========================================================================

$Host.UI.RawUI.WindowTitle = "Build Dashboard Deploy Package"
$ErrorActionPreference = "Continue"

# =========================================================================
# CONFIGURATION
# =========================================================================
$ROOT = $PSScriptRoot                                        # โฟลเดอร์ที่ไฟล์ .ps1 อยู่
$DEPLOY_NAME = "All_Asset_Dashboard_Deploy"                 # ชื่อโฟลเดอร์ผลลัพธ์
$DEPLOY_DIR  = Join-Path $ROOT $DEPLOY_NAME

$W = 76   # ความกว้างกรอบข้อความ

# =========================================================================
# HELPERS
# =========================================================================
function Write-Line  { Write-Host ("-" * $W) }
function Write-Box($text) {
    $pad = $W - 4 - $text.Length
    if ($pad -lt 0) { $pad = 0 }
    Write-Host ("| " + $text + (" " * $pad) + " |")
}
function Write-Header {
    Write-Host ""
    Write-Host ("+" + ("=" * ($W - 2)) + "+")
    Write-Box "[BUILD] ALL ASSET DASHBOARD - DEPLOY PACKAGE"
    Write-Box "คัดลอกไฟล์จำเป็นทั้งหมดสำหรับนำไปรันบนเครื่องอื่น"
    Write-Host ("+" + ("=" * ($W - 2)) + "+")
    Write-Host ""
}
function Write-Step($num, $text) { Write-Host ("  [STEP $num] " + $text) }
function Write-Ok($text)   { Write-Host ("  [ OK  ] " + $text) -ForegroundColor Green }
function Write-Skip($text) { Write-Host ("  [SKIP ] " + $text) -ForegroundColor DarkGray }
function Write-Warn($text) { Write-Host ("  [WARN ] " + $text) -ForegroundColor Yellow }
function Write-Fail($text) { Write-Host ("  [FAIL ] " + $text) -ForegroundColor Red }

# =========================================================================
# COPY HELPERS
# =========================================================================
function Copy-SingleFile($src, $dst) {
    $srcFull = Join-Path $ROOT $src
    if (Test-Path $srcFull) {
        $dstFull = Join-Path $DEPLOY_DIR $dst
        $dstDir  = Split-Path $dstFull -Parent
        if (!(Test-Path $dstDir)) { New-Item -ItemType Directory -Force $dstDir | Out-Null }
        Copy-Item -Force $srcFull $dstFull
        $size = (Get-Item $srcFull).Length
        $sizeMB = [math]::Round($size / 1MB, 1)
        Write-Ok "${src}  (${sizeMB} MB)"
    } else {
        Write-Skip "${src}  (ไม่พบไฟล์ ข้ามไป)"
    }
}

function Copy-Folder($src, $dstSubPath) {
    $srcFull = Join-Path $ROOT $src
    if (Test-Path $srcFull) {
        $dstFull = Join-Path $DEPLOY_DIR $dstSubPath
        if (!(Test-Path $dstFull)) { New-Item -ItemType Directory -Force $dstFull | Out-Null }
        Copy-Item -Recurse -Force "$srcFull\*" $dstFull
        $count = (Get-ChildItem $srcFull -Recurse -File).Count
        Write-Ok "${src}/  ($count files)"
    } else {
        Write-Skip "${src}/  (ไม่พบโฟลเดอร์ ข้ามไป)"
    }
}

# =========================================================================
# FIND LATEST PARQUET DATA FILE
# =========================================================================
function Get-LatestDataFile {
    $candidates = @(
        "all_assets.parquet",
        "all_assets_no_centroid.parquet"
    )
    foreach ($f in $candidates) {
        if (Test-Path (Join-Path $ROOT $f)) { return $f }
    }
    $any = Get-ChildItem $ROOT -Filter "*.parquet" -File | Select-Object -First 1
    if ($any) { return $any.Name }
    $anycsv = Get-ChildItem $ROOT -Filter "all_assets*.csv" -File | Select-Object -First 1
    if ($anycsv) { return $anycsv.Name }
    return $null
}

# =========================================================================
# MAIN
# =========================================================================
Write-Header

# ------------------------------------------------------------------
# STEP 1: Verify source files exist
# ------------------------------------------------------------------
Write-Step 1 "ตรวจสอบไฟล์ต้นทางที่จำเป็น..."
Write-Line

$missingCritical = $false
foreach ($f in @("All_Asset_Dashboard.exe", "app.py")) {
    if (!(Test-Path (Join-Path $ROOT $f))) {
        Write-Fail "$f - ไม่พบไฟล์นี้! กรุณา Build ก่อน"
        $missingCritical = $true
    } else {
        Write-Ok "$f พร้อม"
    }
}
if ($missingCritical) {
    Write-Host ""
    Write-Warn "พบไฟล์ที่จำเป็นขาดหายไป กรุณา Build EXE ก่อนแล้วรันสคริปต์นี้ใหม่"
    Read-Host "`nกด Enter เพื่อปิด..."
    exit 1
}
Write-Host ""

# ------------------------------------------------------------------
# STEP 2: Create / Clear output folder
# ------------------------------------------------------------------
Write-Step 2 "เตรียมโฟลเดอร์ปลายทาง: $DEPLOY_NAME"
Write-Line
if (Test-Path $DEPLOY_DIR) {
    Write-Warn "พบโฟลเดอร์เดิมอยู่แล้ว -> กำลังลบเพื่อเริ่มใหม่ทั้งหมด"
    Remove-Item -Recurse -Force $DEPLOY_DIR
}
New-Item -ItemType Directory -Force $DEPLOY_DIR | Out-Null
Write-Ok "สร้างโฟลเดอร์: $DEPLOY_DIR"
Write-Host ""

# ------------------------------------------------------------------
# STEP 3: Copy EXE launcher
# ------------------------------------------------------------------
Write-Step 3 "คัดลอก EXE Launcher"
Write-Line
Copy-SingleFile "All_Asset_Dashboard.exe" "All_Asset_Dashboard.exe"
Write-Host ""

# ------------------------------------------------------------------
# STEP 4: Copy core app files
# ------------------------------------------------------------------
Write-Step 4 "คัดลอกไฟล์แอปพลิเคชันหลัก"
Write-Line
Copy-SingleFile "app.py"                "app.py"
Copy-SingleFile "sam_analytics.py"      "sam_analytics.py"
Copy-SingleFile "monthly_comparison.py" "monthly_comparison.py"
Copy-SingleFile "bubble_chart.py"       "bubble_chart.py"
Copy-SingleFile "dashboard_metrics.py"  "dashboard_metrics.py"
Copy-SingleFile "requirements.txt"      "requirements.txt"
Write-Host ""

# ------------------------------------------------------------------
# STEP 5: Copy resource folders
# ------------------------------------------------------------------
Write-Step 5 "คัดลอกโฟลเดอร์ทรัพยากร (logo, static, .streamlit)"
Write-Line
if (Test-Path "$ROOT\logo")   { Copy-Folder "logo"   "logo" }
if (Test-Path "$ROOT\assets") { Copy-Folder "assets" "assets" }
Copy-Folder "static"     "static"
Copy-Folder ".streamlit" ".streamlit"
Write-Host ""

# ------------------------------------------------------------------
# STEP 6: Copy latest data file
# ------------------------------------------------------------------
Write-Step 6 "คัดลอกไฟล์ข้อมูลทรัพย์สินล่าสุด"
Write-Line
$dataFile = Get-LatestDataFile
if ($dataFile) {
    Copy-SingleFile $dataFile $dataFile
} else {
    Write-Warn "ไม่พบไฟล์ข้อมูล (.parquet / .csv) - ผู้ใช้ต้องนำไฟล์ข้อมูลมาวางเองในโฟลเดอร์นี้ก่อนรัน"
}
Write-Host ""

# ------------------------------------------------------------------
# STEP 7: Copy .venv (optional - for machines without Python)
# ------------------------------------------------------------------
Write-Step 7 "คัดลอก Python Virtual Environment (.venv)"
Write-Line
$venvPath = Join-Path $ROOT ".venv"
if (Test-Path $venvPath) {
    Write-Host "  [INFO ] พบ .venv ขนาดใหญ่ -> กำลังคัดลอก (อาจใช้เวลา 1-3 นาที)..." -ForegroundColor Cyan
    $dstVenv = Join-Path $DEPLOY_DIR ".venv"
    Copy-Item -Recurse -Force $venvPath $dstVenv
    $venvFiles = (Get-ChildItem $venvPath -Recurse -File).Count
    $venvSizeMB = [math]::Round((Get-ChildItem $venvPath -Recurse -File | Measure-Object -Property Length -Sum).Sum / 1MB, 0)
    Write-Ok ".venv/  ($venvFiles files, ${venvSizeMB} MB) - เครื่องปลายทางไม่ต้องติดตั้ง Python!"
} else {
    Write-Warn ".venv ไม่พบ - เครื่องปลายทางต้องมี Python + pip install requirements.txt เอง"
}
Write-Host ""

# ------------------------------------------------------------------
# STEP 8: Create README for target machine
# ------------------------------------------------------------------
Write-Step 8 "สร้าง README คำแนะนำการใช้งาน"
Write-Line
$readmePath = Join-Path $DEPLOY_DIR "DEPLOY_README.txt"
$readmeContent = @"
=========================================================================
  All Asset NPA Intelligence Dashboard - Deploy Package
  วิธีการติดตั้งและรันบนเครื่องใหม่
=========================================================================

[ วิธีรันทันที - กรณีโฟลเดอร์นี้มี .venv อยู่ ]
  1. ก็อปปี้โฟลเดอร์ "$DEPLOY_NAME" ทั้งโฟลเดอร์ไปวางบนเครื่องปลายทาง
  2. ดับเบิลคลิก All_Asset_Dashboard.exe
  3. รอสักครู่ ระบบจะเปิดเบราว์เซอร์ไปที่ http://localhost:8501 อัตโนมัติ

[ วิธีรัน - กรณีไม่มี .venv (ต้องมี Python บนเครื่องปลายทาง) ]
  1. เปิด Command Prompt ใน โฟลเดอร์นี้
  2. รันคำสั่ง:  pip install -r requirements.txt
  3. ดับเบิลคลิก All_Asset_Dashboard.exe

[ โครงสร้างไฟล์ที่สำคัญ ]
  All_Asset_Dashboard.exe    -> ตัวเปิดแอป (ดับเบิลคลิกได้เลย)
  app.py                     -> โค้ดระบบ Dashboard หลัก
  all_assets.parquet         -> ฐานข้อมูลทรัพย์สิน NPA ล่าสุด
  logo/                      -> โลโก้และไอคอนสถาบันการเงิน
  static/                    -> เทมเพลตแผนที่ Leaflet
  .streamlit/                -> การตั้งค่า Streamlit
  .venv/                     -> Python Environment (ถ้ามี)

[ หมายเหตุ ]
  - รองรับ Windows 10 / 11 (64-bit) เท่านั้น
  - ไม่ต้องการ Internet Connection เพื่อรัน Dashboard
  - ไฟล์ข้อมูลฐานข้อมูล (.parquet) อัปเดตจาก Scraper_Monthly_Parallel.exe
=========================================================================
Build Date: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")
=========================================================================
"@
Set-Content -Path $readmePath -Value $readmeContent -Encoding UTF8
Write-Ok "DEPLOY_README.txt"
Write-Host ""

# ------------------------------------------------------------------
# FINAL SUMMARY
# ------------------------------------------------------------------
$totalFiles = (Get-ChildItem $DEPLOY_DIR -Recurse -File).Count
$totalSizeMB = [math]::Round((Get-ChildItem $DEPLOY_DIR -Recurse -File | Measure-Object -Property Length -Sum).Sum / 1MB, 0)

Write-Host ("+" + ("=" * ($W - 2)) + "+")
Write-Box "[SUCCESS] สร้าง Deploy Package สำเร็จเรียบร้อย!"
Write-Host ("+" + ("=" * ($W - 2)) + "+")
Write-Host ""
Write-Host "  โฟลเดอร์ผลลัพธ์ : $DEPLOY_DIR" -ForegroundColor Cyan
Write-Host "  จำนวนไฟล์รวม  : $totalFiles files"
Write-Host "  ขนาดรวม       : $totalSizeMB MB"
Write-Host ""
Write-Host "  วิธีใช้งาน:"
Write-Host "   1. ก็อปปี้โฟลเดอร์ [$DEPLOY_NAME] ทั้งโฟลเดอร์ไปบนเครื่องปลายทาง"
Write-Host "   2. ดับเบิลคลิก All_Asset_Dashboard.exe ในโฟลเดอร์นั้น"
Write-Host "   3. เบราว์เซอร์จะเปิดขึ้นมาอัตโนมัติ"
Write-Host ""

# Open deploy folder in Explorer
Start-Process explorer.exe $DEPLOY_DIR

Read-Host "กด Enter เพื่อปิดหน้าต่าง..."
