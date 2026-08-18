import os
import sys
import subprocess

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

print("=" * 75)
print("🚀 เริ่มต้นกระบวนการ Compile Scraper_Monthly_Parallel.exe")
print("=" * 75)

# 1. Install PyInstaller if missing
try:
    import PyInstaller
except ImportError:
    print("\n[1/3] กำลังติดตั้ง PyInstaller...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "pyinstaller"])
    import PyInstaller

import PyInstaller.__main__

base_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(base_dir)

print("\n[2/3] กำลัง Build ไฟล์ .exe ด้วย PyInstaller (กรุณารอสักครู่)...")

args = [
    "run_parallel_monthly.py",
    "--noconfirm",
    "--onefile",
    "--console",
    "--name", "Scraper_Monthly_Parallel",
    "--hidden-import=pandas",
    "--hidden-import=requests",
    "--hidden-import=bs4",
    "--hidden-import=openpyxl",
    "--hidden-import=pyarrow",
    "--hidden-import=scrape_baania_monthly",
    "--hidden-import=scrape_bam_monthly",
    "--hidden-import=scrape_ddproperty_monthly",
    "--hidden-import=scrape_sam_monthly",
    "--hidden-import=scrape_taladnudbaan_monthly",
    "--hidden-import=scrape_zmyhome_monthly",
    "--hidden-import=merge_csv_monthly"
]

try:
    PyInstaller.__main__.run(args)
    print("\n" + "=" * 75)
    print("🎉 สร้างไฟล์ EXE สำเร็จเรียบร้อยแล้ว!")
    dist_exe = os.path.join(base_dir, "dist", "Scraper_Monthly_Parallel.exe")
    print(f"📁 ไฟล์ EXE อยู่ที่: {dist_exe}")
    print("=" * 75)
except Exception as e:
    print(f"\n❌ เกิดข้อผิดพลาดในการสร้าง EXE: {e}")

input("\nกด Enter เพื่อปิดหน้าต่างนี้...")
