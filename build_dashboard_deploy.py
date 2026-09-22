# -*- coding: utf-8 -*-
"""
build_dashboard_deploy.py
สร้างโฟลเดอร์ All_Asset_Dashboard_Deploy ที่พร้อมนำไปรันบนเครื่องอื่นได้ทันที
รันสคริปต์นี้ครั้งเดียว -> ได้โฟลเดอร์พร้อม Deploy เลย
"""

import os, sys, shutil, subprocess
from pathlib import Path
from datetime import datetime

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

ROOT        = Path(__file__).parent.resolve()
DEPLOY_NAME = "All_Asset_Dashboard_Deploy"
DEPLOY_DIR  = ROOT / DEPLOY_NAME
W           = 76

# =========================================================================
# UI HELPERS
# =========================================================================
def line():    print("-" * W)
def box(text):
    pad = max(0, W - 4 - len(text))
    print(f"| {text}{' ' * pad} |")
def header():
    print()
    print("+" + "=" * (W - 2) + "+")
    box("[BUILD] ALL ASSET DASHBOARD - DEPLOY PACKAGE")
    box("คัดลอกไฟล์จำเป็นสำหรับนำไปรันบนเครื่องอื่น")
    print("+" + "=" * (W - 2) + "+")
    print()
def step(n, text): print(f"  [STEP {n}] {text}")
def ok(text):   print(f"  [ OK  ] {text}")
def skip(text): print(f"  [SKIP ] {text}")
def warn(text): print(f"  [WARN ] {text}")
def fail(text): print(f"  [FAIL ] {text}")

# =========================================================================
# COPY HELPERS
# =========================================================================
def copy_file(src_rel, dst_rel):
    src = ROOT / src_rel
    dst = DEPLOY_DIR / dst_rel
    if src.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        size_mb = round(src.stat().st_size / 1_048_576, 1)
        ok(f"{src_rel}  ({size_mb} MB)")
    else:
        skip(f"{src_rel}  (ไม่พบไฟล์ ข้ามไป)")

def copy_folder(src_rel, dst_rel):
    src = ROOT / src_rel
    dst = DEPLOY_DIR / dst_rel
    if src.exists():
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
        count = sum(1 for _ in src.rglob("*") if _.is_file())
        ok(f"{src_rel}/  ({count} files)")
    else:
        skip(f"{src_rel}/  (ไม่พบโฟลเดอร์ ข้ามไป)")

# =========================================================================
# FIND LATEST DATA FILE
# =========================================================================
def find_data_file():
    priority = ["all_assets.parquet", "all_assets_no_centroid.parquet"]
    for f in priority:
        if (ROOT / f).exists():
            return f
    # fallback: any parquet
    parquets = sorted(ROOT.glob("*.parquet"), key=lambda p: p.stat().st_mtime, reverse=True)
    if parquets:
        return parquets[0].name
    # fallback: any csv
    csvs = sorted(ROOT.glob("all_assets*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
    if csvs:
        return csvs[0].name
    return None

# =========================================================================
# MAIN
# =========================================================================
def main():
    header()

    # STEP 1 - Verify critical source files
    step(1, "ตรวจสอบไฟล์ต้นทางที่จำเป็น...")
    line()
    critical_missing = False
    for f in ["All_Asset_Dashboard.exe", "app.py"]:
        if not (ROOT / f).exists():
            fail(f"{f} - ไม่พบไฟล์นี้! กรุณา Build EXE ก่อน")
            critical_missing = True
        else:
            size_mb = round((ROOT / f).stat().st_size / 1_048_576, 1)
            ok(f"{f}  ({size_mb} MB) - พร้อม")
    if critical_missing:
        print()
        warn("พบไฟล์จำเป็นขาดหายไป กรุณา Build EXE ก่อนแล้วรันสคริปต์นี้ใหม่")
        input("\nกด Enter เพื่อปิด...")
        sys.exit(1)
    print()

    # STEP 2 - Prepare output folder
    step(2, f"เตรียมโฟลเดอร์ปลายทาง: {DEPLOY_NAME}")
    line()
    if DEPLOY_DIR.exists():
        warn("พบโฟลเดอร์เดิมอยู่แล้ว -> กำลังลบเพื่อเริ่มใหม่ทั้งหมด")
        shutil.rmtree(DEPLOY_DIR)
    DEPLOY_DIR.mkdir(parents=True)
    ok(f"สร้างโฟลเดอร์: {DEPLOY_DIR}")
    print()

    # STEP 3 - Copy EXE Launcher
    step(3, "คัดลอก EXE Launcher")
    line()
    copy_file("All_Asset_Dashboard.exe", "All_Asset_Dashboard.exe")
    print()

    # STEP 4 - Copy core app files
    step(4, "คัดลอกไฟล์แอปพลิเคชันหลัก")
    line()
    for f in [
        "app.py",
        "sam_analytics.py",
        "monthly_comparison.py",
        "bubble_chart.py",
        "dashboard_metrics.py",
        "requirements.txt",
    ]:
        copy_file(f, f)
    print()

    # STEP 5 - Copy resource folders
    step(5, "คัดลอกโฟลเดอร์ทรัพยากร (logo, static, .streamlit)")
    line()
    if (ROOT / "logo").exists():
        copy_folder("logo",       "logo")
    if (ROOT / "assets").exists():
        copy_folder("assets",     "assets")
    copy_folder("static",     "static")
    copy_folder(".streamlit", ".streamlit")
    print()

    # STEP 6 - Copy latest data file
    step(6, "คัดลอกไฟล์ข้อมูลทรัพย์สินล่าสุด")
    line()
    data_file = find_data_file()
    if data_file:
        copy_file(data_file, data_file)
    else:
        warn("ไม่พบไฟล์ข้อมูล (.parquet/.csv) - นำไฟล์มาวางในโฟลเดอร์ก่อนรัน")
    print()

    # STEP 7 - Copy .venv
    step(7, "คัดลอก Python Virtual Environment (.venv)")
    line()
    venv_path = ROOT / ".venv"
    if venv_path.exists():
        print("  [INFO ] พบ .venv -> กำลังคัดลอก (อาจใช้เวลา 1-3 นาที)...")
        shutil.copytree(venv_path, DEPLOY_DIR / ".venv")
        venv_files = sum(1 for _ in venv_path.rglob("*") if _.is_file())
        venv_mb = round(sum(p.stat().st_size for p in venv_path.rglob("*") if p.is_file()) / 1_048_576)
        ok(f".venv/  ({venv_files} files, {venv_mb} MB) - เครื่องปลายทางไม่ต้องติดตั้ง Python!")
    else:
        warn(".venv ไม่พบ - เครื่องปลายทางต้องมี Python + pip install requirements.txt เอง")
    print()

    # STEP 8 - Create README
    step(8, "สร้าง DEPLOY_README.txt คำแนะนำการใช้งาน")
    line()
    readme = DEPLOY_DIR / "DEPLOY_README.txt"
    readme.write_text(f"""=========================================================================
  All Asset NPA Intelligence Dashboard - Deploy Package
  วิธีการติดตั้งและรันบนเครื่องใหม่
=========================================================================

[ วิธีรันทันที - กรณีโฟลเดอร์นี้มี .venv อยู่ ]
  1. ก็อปปี้โฟลเดอร์ "{DEPLOY_NAME}" ทั้งโฟลเดอร์ไปวางบนเครื่องปลายทาง
  2. ดับเบิลคลิก All_Asset_Dashboard.exe
  3. รอสักครู่ ระบบจะเปิดเบราว์เซอร์ไปที่ http://localhost:8501 อัตโนมัติ

[ วิธีรัน - กรณีไม่มี .venv (ต้องมี Python บนเครื่องปลายทาง) ]
  1. เปิด Command Prompt ในโฟลเดอร์นี้
  2. รันคำสั่ง: pip install -r requirements.txt
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
  - ไม่ต้องการ Internet เพื่อรัน Dashboard
  - อัปเดตข้อมูลใหม่ด้วย Scraper_Monthly_Parallel.exe แล้วก็อปปี้ไฟล์ .parquet มาแทน
=========================================================================
Build Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
=========================================================================
""", encoding="utf-8")
    ok("DEPLOY_README.txt")
    print()

    # FINAL SUMMARY
    total_files = sum(1 for _ in DEPLOY_DIR.rglob("*") if _.is_file())
    total_mb    = round(sum(p.stat().st_size for p in DEPLOY_DIR.rglob("*") if p.is_file()) / 1_048_576)
    print("+" + "=" * (W - 2) + "+")
    box("[SUCCESS] สร้าง Deploy Package สำเร็จเรียบร้อย!")
    print("+" + "=" * (W - 2) + "+")
    print()
    print(f"  โฟลเดอร์ผลลัพธ์ : {DEPLOY_DIR}")
    print(f"  จำนวนไฟล์รวม  : {total_files:,} files")
    print(f"  ขนาดรวม       : {total_mb:,} MB")
    print()
    print("  วิธีใช้งาน:")
    print(f"   1. ก็อปปี้โฟลเดอร์ [{DEPLOY_NAME}] ทั้งโฟลเดอร์ไปบนเครื่องปลายทาง")
    print("   2. ดับเบิลคลิก All_Asset_Dashboard.exe")
    print("   3. เบราว์เซอร์จะเปิดขึ้นมาอัตโนมัติ")
    print()

    # Open folder in Explorer
    try:
        subprocess.Popen(["explorer", str(DEPLOY_DIR)])
    except Exception:
        pass

    input("กด Enter เพื่อปิดหน้าต่าง...")


if __name__ == "__main__":
    main()
