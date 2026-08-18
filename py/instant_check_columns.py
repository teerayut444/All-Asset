import glob
import csv
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
import pyarrow.parquet as pq

print("=" * 80)
print("📌 1. คอลัมน์ในไฟล์ CSV (.csv)")
print("=" * 80)

csv_files = glob.glob("*.csv") + glob.glob("Monthly all new/**/*.csv", recursive=True)
for cf in sorted(csv_files):
    p = Path(cf)
    size_mb = p.stat().st_size / (1024 * 1024)
    print(f"\n📄 ไฟล์: {p} (ขนาด: {size_mb:.2f} MB)")
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

print("\n" + "=" * 80)
print("📌 2. คอลัมน์ในไฟล์ EXCEL (.xlsx)")
print("=" * 80)

def get_xlsx_headers(filepath):
    try:
        with zipfile.ZipFile(filepath, 'r') as z:
            # 1. Read shared strings
            shared_strings = []
            if 'xl/sharedStrings.xml' in z.namelist():
                tree = ET.fromstring(z.read('xl/sharedStrings.xml'))
                for si in tree.findall('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}si'):
                    t = si.find('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t')
                    if t is not None and t.text:
                        shared_strings.append(t.text)
                    else:
                        text_parts = [elem.text for elem in si.findall('.//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t') if elem.text]
                        shared_strings.append(''.join(text_parts))
            
            # 2. Read first row of sheet1.xml
            sheet1 = z.read('xl/worksheets/sheet1.xml')
            tree = ET.fromstring(sheet1)
            row1 = tree.find('.//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}row')
            headers = []
            if row1 is not None:
                for c in row1.findall('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}c'):
                    t_attr = c.get('t')
                    v = c.find('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}v')
                    if v is not None and v.text:
                        if t_attr == 's' and int(v.text) < len(shared_strings):
                            headers.append(shared_strings[int(v.text)])
                        else:
                            headers.append(v.text)
            return headers
    except Exception as e:
        return [f"Error: {e}"]

excel_files = glob.glob("*.xlsx") + glob.glob("Monthly all new/**/*.xlsx", recursive=True)
for ef in sorted(excel_files):
    p = Path(ef)
    size_mb = p.stat().st_size / (1024 * 1024)
    print(f"\n📂 ไฟล์: {p} (ขนาด: {size_mb:.2f} MB)")
    headers = get_xlsx_headers(p)
    print(f"   จำนวนคอลัมน์: {len(headers)}")
    print("   รายชื่อคอลัมน์:")
    for idx, col in enumerate(headers, 1):
        print(f"     {idx:2d}. {col}")

print("\n" + "=" * 80)
print("📌 3. คอลัมน์ในไฟล์ PARQUET (.parquet)")
print("=" * 80)

parquet_files = glob.glob("*.parquet") + glob.glob("Monthly all new/**/*.parquet", recursive=True)
for pf in sorted(parquet_files):
    p = Path(pf)
    size_mb = p.stat().st_size / (1024 * 1024)
    print(f"\n⚡ ไฟล์: {p} (ขนาด: {size_mb:.2f} MB)")
    try:
        schema = pq.read_schema(p)
        cols = schema.names
        print(f"   จำนวนคอลัมน์: {len(cols)}")
        print("   รายชื่อคอลัมน์:")
        for idx, col in enumerate(cols, 1):
            print(f"     {idx:2d}. {col}")
    except Exception as e:
        print(f"   ❌ ไม่สามารถอ่านได้: {e}")
