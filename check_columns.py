import os
import glob
from pathlib import Path
import pandas as pd

print("=" * 70)
print("📌 ตรวจสอบคอลัมน์ในไฟล์ EXCEL (.xlsx)")
print("=" * 70)

excel_files = glob.glob("*.xlsx") + glob.glob("Monthly all new/**/*.xlsx", recursive=True)
for ef in excel_files:
    p = Path(ef)
    size_mb = p.stat().st_size / (1024 * 1024)
    print(f"\n📂 ไฟล์: {p} (ขนาด: {size_mb:.2f} MB)")
    try:
        df_ex = pd.read_excel(p, nrows=5)
        print(f"   จำนวนคอลัมน์: {len(df_ex.columns)}")
        print("   รายชื่อคอลัมน์:")
        for idx, col in enumerate(df_ex.columns, 1):
            print(f"     {idx:2d}. {col}")
    except Exception as e:
        print(f"   ❌ ไม่สามารถอ่านไฟล์ได้: {e}")

print("\n" + "=" * 70)
print("📌 ตรวจสอบคอลัมน์ในไฟล์ CSV (.csv)")
print("=" * 70)

csv_files = glob.glob("*.csv") + glob.glob("Monthly all new/**/*.csv", recursive=True)
for cf in sorted(csv_files):
    p = Path(cf)
    size_mb = p.stat().st_size / (1024 * 1024)
    print(f"\n📄 ไฟล์: {p} (ขนาด: {size_mb:.2f} MB)")
    try:
        # Try utf-8-sig first, then utf-8, then cp874
        df_csv = None
        for enc in ['utf-8-sig', 'utf-8', 'cp874', 'tis-620']:
            try:
                df_csv = pd.read_csv(p, nrows=5, encoding=enc)
                break
            except Exception:
                continue
        if df_csv is not None:
            print(f"   จำนวนคอลัมน์: {len(df_csv.columns)}")
            print("   รายชื่อคอลัมน์:")
            for idx, col in enumerate(df_csv.columns, 1):
                print(f"     {idx:2d}. {col}")
        else:
            print("   ❌ ไม่สามารถ decode ไฟล์ด้วย encoding ทั่วไปได้")
    except Exception as e:
        print(f"   ❌ ไม่สามารถอ่านไฟล์ได้: {e}")

print("\n" + "=" * 70)
print("📌 ตรวจสอบคอลัมน์ในไฟล์ PARQUET (.parquet)")
print("=" * 70)
parquet_files = glob.glob("*.parquet") + glob.glob("Monthly all new/**/*.parquet", recursive=True)
for pf in parquet_files:
    p = Path(pf)
    size_mb = p.stat().st_size / (1024 * 1024)
    print(f"\n⚡ ไฟล์: {p} (ขนาด: {size_mb:.2f} MB)")
    try:
        df_pq = pd.read_parquet(p)
        print(f"   จำนวนแถว: {len(df_pq):,} แถว | จำนวนคอลัมน์: {len(df_pq.columns)}")
        print("   รายชื่อคอลัมน์:")
        for idx, col in enumerate(df_pq.columns, 1):
            print(f"     {idx:2d}. {col}")
    except Exception as e:
        print(f"   ❌ ไม่สามารถอ่านไฟล์ได้: {e}")
