import glob
from pathlib import Path
import pandas as pd
import openpyxl
import csv

print("=" * 80)
print("📌 1. ตรวจสอบคอลัมน์ในไฟล์ EXCEL (.xlsx)")
print("=" * 80)

excel_files = glob.glob("*.xlsx") + glob.glob("Monthly all new/**/*.xlsx", recursive=True)
for ef in sorted(excel_files):
    p = Path(ef)
    size_mb = p.stat().st_size / (1024 * 1024)
    print(f"\n📂 ไฟล์: {p} (ขนาด: {size_mb:.2f} MB)")
    try:
        wb = openpyxl.load_workbook(p, read_only=True)
        sheet = wb.active
        headers = [cell for cell in next(sheet.iter_rows(values_only=True)) if cell is not None]
        wb.close()
        print(f"   จำนวนคอลัมน์: {len(headers)}")
        print("   รายชื่อคอลัมน์:")
        for idx, col in enumerate(headers, 1):
            print(f"     {idx:2d}. {col}")
    except Exception as e:
        print(f"   ❌ ไม่สามารถอ่านได้: {e}")

print("\n" + "=" * 80)
print("📌 2. ตรวจสอบคอลัมน์ในไฟล์ CSV (.csv)")
print("=" * 80)

csv_files = glob.glob("*.csv") + glob.glob("Monthly all new/**/*.csv", recursive=True)
for cf in sorted(csv_files):
    p = Path(cf)
    size_mb = p.stat().st_size / (1024 * 1024)
    print(f"\n📄 ไฟล์: {p} (ขนาด: {size_mb:.2f} MB)")
    try:
        headers = None
        for enc in ['utf-8-sig', 'utf-8', 'cp874', 'tis-620', 'latin-1']:
            try:
                with open(p, 'r', encoding=enc) as f:
                    reader = csv.reader(f)
                    headers = next(reader)
                    break
            except Exception:
                continue
        if headers:
            print(f"   จำนวนคอลัมน์: {len(headers)}")
            print("   รายชื่อคอลัมน์:")
            for idx, col in enumerate(headers, 1):
                print(f"     {idx:2d}. {col.strip()}")
        else:
            print("   ❌ ไม่สามารถอ่าน Header ได้")
    except Exception as e:
        print(f"   ❌ ไม่สามารถอ่านได้: {e}")

print("\n" + "=" * 80)
print("📌 3. ตรวจสอบคอลัมน์ในไฟล์ PARQUET (.parquet)")
print("=" * 80)

parquet_files = glob.glob("*.parquet") + glob.glob("Monthly all new/**/*.parquet", recursive=True)
for pf in sorted(parquet_files):
    p = Path(pf)
    size_mb = p.stat().st_size / (1024 * 1024)
    print(f"\n⚡ ไฟล์: {p} (ขนาด: {size_mb:.2f} MB)")
    try:
        import pyarrow.parquet as pq
        table = pq.read_schema(p)
        cols = table.names
        print(f"   จำนวนคอลัมน์: {len(cols)}")
        print("   รายชื่อคอลัมน์:")
        for idx, col in enumerate(cols, 1):
            print(f"     {idx:2d}. {col}")
    except Exception as e:
        print(f"   ❌ ไม่สามารถอ่านได้: {e}")
