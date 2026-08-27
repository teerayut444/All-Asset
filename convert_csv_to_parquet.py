# -*- coding: utf-8 -*-
"""
convert_csv_to_parquet.py
สคริปต์ความเร็วสูงสำหรับแปลงและบีบอัดไฟล์ CSV รายเดือนเป็น Parquet (ZSTD Compression)
ออกแบบสำหรับ All Asset NPA Dashboard
"""

import os
import sys
import glob
import time
import argparse
import pandas as pd
import numpy as np

# Force UTF-8 stdout for Thai characters on Windows console
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# ตารางการจัดกลุ่มและแปลงประเภททรัพย์สินให้เป็นมาตรฐานเดียวกันทุกค่าย
PROPERTY_TYPE_MAPPING = {
    # 1. หมวดบ้านเดี่ยว
    "บ้าน": "บ้านเดี่ยว",
    "บ้านครึ่งตึกครึ่งไม้": "บ้านเดี่ยว",
    "บ้านพร้อมกิจการ": "บ้านเดี่ยว",
    
    # 2. หมวดคอนโดมิเนียม / ห้องชุด
    "ห้องชุด": "ห้องชุดพักอาศัย",
    "คอนโด": "ห้องชุดพักอาศัย",
    "คอนโดมิเนียม": "ห้องชุดพักอาศัย",
    "ห้องชุด/คอนโดมิเนียม": "ห้องชุดพักอาศัย",
    "ห้องชุด/ตอนโดมิเนียม": "ห้องชุดพักอาศัย",
    "คอนโดมิเนียม/อาคารชุด": "ห้องชุดพักอาศัย",
    "คอนโด/อาคารชุด/ห้องชุด": "ห้องชุดพักอาศัย",
    
    # 3. หมวดทาวน์เฮ้าส์ / ทาวน์โฮม
    "ทาวน์โฮม": "ทาวน์เฮ้าส์",
    "ทาวน์เฮาส์": "ทาวน์เฮ้าส์",
    
    # 4. หมวดที่ดิน
    "ที่ดิน": "ที่ดินเปล่า",
    "ที่ดินเกษตรกรรม": "ที่ดินเปล่า",
    "ที่ดินว่างเปล่า": "ที่ดินเปล่า",
    "สวนเกษตร": "ที่ดินเปล่า",
    
    # 5. หมวดโรงงาน / โกดัง
    "โรงงาน": "โรงงาน/โกดัง",
    "โกดัง": "โรงงาน/โกดัง",
    "อาคารโรงงาน": "โรงงาน/โกดัง",
    "โกดัง/โรงงาน": "โรงงาน/โกดัง",
    "โกดัง / โรงงาน": "โรงงาน/โกดัง",
    "มินิแฟคตอรี่": "โรงงาน/โกดัง",
    "โรงสี": "โรงงาน/โกดัง",
    
    # 6. หมวดอพาร์ทเมนท์ / หอพัก
    "อพาร์ทเม้นท์": "อพาร์ทเมนท์",
    "อพาร์ตเมนต์": "อพาร์ทเมนท์",
    "อพาตเมนต์": "อพาร์ทเมนท์",
    "หอพัก": "อพาร์ทเมนท์",
    "หอพัก/อพาร์ทเมนท์": "อพาร์ทเมนท์",
    "อพาร์ทเม้นท์/หอพัก": "อพาร์ทเมนท์",
    "แฟลต": "อพาร์ทเมนท์",
    "อาคารพักอาศัย": "อพาร์ทเมนท์",
    
    # 7. หมวดอาคารพาณิชย์ / ตึกแถว / ร้านค้า
    "ตึกแถว": "อาคารพาณิชย์",
    "ห้องแถว": "อาคารพาณิชย์",
    "ร้านค้า": "อาคารพาณิชย์",
    "ร้านอาหาร": "อาคารพาณิชย์",
    "ตลาดสด": "อาคารพาณิชย์",
    "ศูนย์จำหน่ายสินค้า": "อาคารพาณิชย์",
    "ห้างสรรพสินค้า": "อาคารพาณิชย์",
    "โชว์รูม": "อาคารพาณิชย์",
    
    # 8. หมวดสำนักงาน
    "สำนักงาน": "อาคารสำนักงาน",
    "โฮมออฟฟิศ": "อาคารสำนักงาน",
    "อาคารที่ทำการสาขา": "อาคารสำนักงาน",
    "ห้องชุดสำนักงาน": "ห้องชุดพาณิชยกรรม/สำนักงาน",
    "ห้องชุดพาณิชยกรรม": "ห้องชุดพาณิชยกรรม/สำนักงาน",
    
    # 9. หมวดโรงแรม / รีสอร์ท
    "Hotel Building": "โรงแรม/รีสอร์ท",
    "โรงแรม": "โรงแรม/รีสอร์ท",
    "รีสอร์ท": "โรงแรม/รีสอร์ท",
    
    # 10. หมวดสังหาริมทรัพย์ & อื่นๆ
    "เครื่องจักร": "สังหาริมทรัพย์",
    "บัตรสมาชิกสนามกอล์ฟ": "สังหาริมทรัพย์",
    "ส่วนโล่งหลังคาคลุม": "อื่นๆ",
    "ฟาร์มเลี้ยงสัตว์": "ฟาร์ม",
    "สถานีบริการน้ำมัน": "ปั๊มน้ำมัน",
    "ศูนย์บริการ/โชว์รูม/ปั้มน้ำมัน": "ปั๊มน้ำมัน",
}

# รายชื่อบริษัทที่คัดออกจากการประมวลผลหลัก
EXCLUDED_COMPANIES = ['taladnudbaan', 'ตลาดนัด']

# ตารางการจัดกลุ่มและแปลงประเภทการขายให้เป็นมาตรฐานเดียวกัน
SALE_TYPE_MAPPING = {
    # 1. ขายทอดตลาด (ปลอดจำนอง)
    "ปลอดการจำนอง": "ขายทอดตลาด (ปลอดจำนอง)",
    "ไม่มีภาระจำนอง": "ขายทอดตลาด (ปลอดจำนอง)",
    "ปลอดภาระผูกพัน": "ขายทอดตลาด (ปลอดจำนอง)",
    "ไม่มีภาระจำนำ": "ขายทอดตลาด (ปลอดจำนอง)",
    "ประมูล": "ขายทอดตลาด (ปลอดจำนอง)",
    
    # 2. ขายทอดตลาด (จำนองติดไป)
    "การจำนองติดไป": "ขายทอดตลาด (จำนองติดไป)",
    "การจำนำติดไป": "ขายทอดตลาด (จำนองติดไป)",
    
    # 3. ขายตรง NPA
    "ซื้อตรง": "ขาย",
    "ทรัพย์ธนาคาร": "ขาย",
    "ทรัพย์โปรโมชั่นราคาพิเศษ": "ขาย",
    "ทรัพย์โปรโมชันราคาพิเศษ": "ขาย",
    "โปรโมชั่น": "ขาย",
    "โปรโมชัน": "ขาย",
    "ทรัพย์ฝากขาย": "ขาย",
    "ฝากขาย": "ขาย",
    "ขายดาวน์": "ขาย",
    "ขาย/เช่า": "ขาย",
}

def parse_land_sqwah(val):
    """แปลงข้อความขนาดที่ดิน (เช่น '2-1-50' หรือ '2 ไร่ 1 งาน 50 ตร.ว.') เป็นตารางวา (float)"""
    if pd.isna(val) or not str(val).strip():
        return np.nan
    s = str(val).strip()
    try:
        return float(s)
    except ValueError:
        pass
    
    import re
    # Match pattern: R-G-W (e.g. 2-1-50)
    m_dash = re.match(r'^(\d+(?:\.\d+)?)-(\d+(?:\.\d+)?)-(\d+(?:\.\d+)?)$', s)
    if m_dash:
        r, g, w = float(m_dash.group(1)), float(m_dash.group(2)), float(m_dash.group(3))
        return r * 400.0 + g * 100.0 + w
        
    # Match Thai words (เช่น 2 ไร่ 1 งาน 50 วา)
    m_thai = re.search(r'(?:(\d+(?:\.\d+)?)\s*ไร่)?\s*(?:(\d+(?:\.\d+)?)\s*งาน)?\s*(?:(\d+(?:\.\d+)?)\s*(?:วา|ตร\.?ว\.?|ตารางวา))?', s)
    if m_thai and (m_thai.group(1) or m_thai.group(2) or m_thai.group(3)):
        r = float(m_thai.group(1) or 0)
        g = float(m_thai.group(2) or 0)
        w = float(m_thai.group(3) or 0)
        return r * 400.0 + g * 100.0 + w
    return np.nan

def read_csv_safely(file_path):
    """อ่านไฟล์ CSV โดยลองตรวจหา Encoding อัตโนมัติ"""
    encodings = ['utf-8-sig', 'utf-8', 'cp874', 'tis-620', 'latin1']
    for enc in encodings:
        try:
            df = pd.read_csv(file_path, encoding=enc, low_memory=False, dtype=str)
            return df, enc
        except (UnicodeDecodeError, Exception):
            continue
    raise ValueError(f"ไม่สามารถอ่านไฟล์ {file_path} ด้วยการเข้ารหัสที่รองรับได้")

def optimize_and_clean_dataframe(df, exclude_unwanted=True):
    """
    ทำความสะอาด ปรับชนิดข้อมูล (Downcasting) และจัดกลุ่มประเภททรัพย์สินเพื่อประสิทธิภาพสูงสุด
    """
    print("  ⚙️  กำลังทำความสะอาดและแปลงชนิดข้อมูล (Data Optimization)...", flush=True)
    
    # 1. ลบช่องว่างในชื่อคอลัมน์
    df.columns = [c.strip() for c in df.columns]
    
    # 2. กรองบริษัทที่ไม่ได้ใช้ออก (Taladnudbaan)
    if exclude_unwanted and 'บริษัท' in df.columns:
        before_len = len(df)
        df = df[~df['บริษัท'].astype(str).str.strip().str.lower().isin(EXCLUDED_COMPANIES)].copy()
        diff = before_len - len(df)
        if diff > 0:
            print(f"  ✂️  ตัดข้อมูลที่ไม่ได้ใช้ออก (Taladnudbaan): {diff:,} รายการ (คงเหลือ {len(df):,} รายการ)", flush=True)

    # 3. กรองประเภทการขาย 'ทรัพย์ NPL' และ 'ให้เช่า' ออกทั้งหมดตามคำสั่ง
    if 'ประเภทการขาย' in df.columns:
        df = df[df['ประเภทการขาย'].astype(str).str.strip() != 'ให้เช่า'].copy()
        if exclude_unwanted:
            before_len = len(df)
            df = df[~df['ประเภทการขาย'].astype(str).str.contains('NPL', case=False, na=False)].copy()
            diff = before_len - len(df)
            if diff > 0:
                print(f"  ✂️  ตัดข้อมูล 'ทรัพย์ NPL' ออก: {diff:,} รายการ (คงเหลือ {len(df):,} รายการ)", flush=True)

        # จัดกลุ่มประเภทการขายให้เป็นมาตรฐาน (Sale Type Normalization)
        df['ประเภทการขาย'] = df['ประเภทการขาย'].astype(str).str.strip().replace(SALE_TYPE_MAPPING)

    # 4. จัดกลุ่มประเภททรัพย์สินให้เป็นมาตรฐาน (Property Type Normalization)
    if 'ประเภททรัพย์' in df.columns:
        df['ประเภททรัพย์'] = df['ประเภททรัพย์'].astype(str).str.strip().replace(PROPERTY_TYPE_MAPPING)

    # 5. แปลงราคาเป็นตัวเลข float32
    if 'ราคา' in df.columns:
        df['ราคา'] = pd.to_numeric(df['ราคา'].astype(str).str.replace(',', '').str.strip(), errors='coerce')
        df.loc[df['ราคา'] <= 0, 'ราคา'] = np.nan
        df['ราคา'] = df['ราคา'].astype('float32')

    # 5. พิกัดละติจูด/ลองจิจูด
    for coord_col in ['ละติจูด', 'ลองจิจูด']:
        if coord_col in df.columns:
            df[coord_col] = pd.to_numeric(df[coord_col].astype(str).str.replace(',', '').str.strip(), errors='coerce')
            df.loc[df[coord_col] == 0, coord_col] = np.nan
            df[coord_col] = df[coord_col].astype('float32')

    # กรองพิกัดที่อยู่นอกประเทศไทย
    if 'ละติจูด' in df.columns and 'ลองจิจูด' in df.columns:
        invalid_coords = ~(df['ละติจูด'].between(5.0, 21.0) & df['ลองจิจูด'].between(97.0, 106.0))
        df.loc[invalid_coords, ['ละติจูด', 'ลองจิจูด']] = np.nan

    # 6. พื้นที่ใช้สอย (ตร.ม.)
    area_col = None
    for c in ['พื้นที่ใช้สอย (ตร.ม.)', 'พื้นที่ใช้สอย', 'usable_area']:
        if c in df.columns:
            area_col = c
            break
    if area_col:
        df['พื้นที่ใช้สอย (ตร.ม.)'] = pd.to_numeric(df[area_col].astype(str).str.replace(',', '').str.strip(), errors='coerce')
        # แก้ไขกรณีราคาหลุดเข้าไปในช่องพื้นที่ใช้สอย
        if 'ราคา' in df.columns:
            corrupt_mask = (df['ราคา'] > 10000) & (df['พื้นที่ใช้สอย (ตร.ม.)'] == df['ราคา'])
            if 'ประเภททรัพย์' in df.columns:
                corrupt_mask |= (df['ประเภททรัพย์'].isin(['คอนโด', 'ห้องชุดพักอาศัย', 'ทาวน์เฮ้าส์', 'ทาวน์โฮม']) & (df['พื้นที่ใช้สอย (ตร.ม.)'] > 5000))
            df.loc[corrupt_mask, 'พื้นที่ใช้สอย (ตร.ม.)'] = np.nan
            
        df['พื้นที่ใช้สอย (ตร.ม.)'] = df['พื้นที่ใช้สอย (ตร.ม.)'].astype('float32')

    # 7. เนื้อที่ดิน (ตารางวา)
    if 'พื้นที่_ตารางวา' not in df.columns:
        land_str_col = None
        for c in ['พื้นที่ (ไร่-งาน-วา)', 'เนื้อที่ (ตร.ว.)', 'เนื้อที่', 'พื้นที่ดิน']:
            if c in df.columns:
                land_str_col = c
                break
        if land_str_col:
            df['พื้นที่_ตารางวา'] = df[land_str_col].apply(parse_land_sqwah).astype('float32')
    else:
        df['พื้นที่_ตารางวา'] = pd.to_numeric(df['พื้นที่_ตารางวา'], errors='coerce').astype('float32')

    # 8. จำนวนห้อง (ห้องนอน, ห้องน้ำ, ที่จอดรถ)
    for c in ['ห้องนอน', 'ห้องน้ำ', 'ที่จอดรถ']:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors='coerce').astype('Int16')

    # 9. คำนวณราคาต่อหน่วย (ราคา/ตร.ว. และ ราคา/ตร.ม.)
    if 'ราคาต่อตารางวา' not in df.columns:
        df['ราคาต่อตารางวา'] = np.where((df['พื้นที่_ตารางวา'] > 0) & (df['ราคา'] > 0), df['ราคา'] / df['พื้นที่_ตารางวา'], np.nan).astype('float32')
    else:
        df['ราคาต่อตารางวา'] = pd.to_numeric(df['ราคาต่อตารางวา'], errors='coerce').astype('float32')
        
    if 'ราคาต่อตารางเมตร' not in df.columns:
        df['ราคาต่อตารางเมตร'] = np.where((df['พื้นที่ใช้สอย (ตร.ม.)'] > 0) & (df['ราคา'] > 0), df['ราคา'] / df['พื้นที่ใช้สอย (ตร.ม.)'], np.nan).astype('float32')
    else:
        df['ราคาต่อตารางเมตร'] = pd.to_numeric(df['ราคาต่อตารางเมตร'], errors='coerce').astype('float32')

    # ตัดราคาต่อหน่วยที่ผิดปกติเกินจริง
    df.loc[df['ราคาต่อตารางวา'] > 50_000_000, 'ราคาต่อตารางวา'] = np.nan
    df.loc[df['ราคาต่อตารางเมตร'] > 20_000_000, 'ราคาต่อตารางเมตร'] = np.nan

    # 10. แปลงคอลัมน์ข้อความที่มีค่าซ้ำกันเป็น Category เพื่อประหยัด RAM 80%
    cat_cols = ['บริษัท', 'ประเภททรัพย์', 'ประเภทการขาย', 'จังหวัด', 'อำเภอ', 'ตำบล']
    for c in cat_cols:
        if c in df.columns:
            df[c] = df[c].fillna('ไม่มีข้อมูล').astype(str).str.strip()
            df[c] = df[c].astype('category')

    # 11. ตรวจสอบชื่อประกาศและลิงก์
    if 'ชื่อประกาศ' not in df.columns and 'ชื่อโครงการ' in df.columns:
        df['ชื่อประกาศ'] = df['ชื่อโครงการ']
    if 'ชื่อประกาศ' in df.columns:
        df['ชื่อประกาศ'] = df['ชื่อประกาศ'].fillna('ไม่มีชื่อ').astype(str).str.strip()

    if 'ลิงก์' in df.columns:
        df['ลิงก์'] = df['ลิงก์'].fillna('').astype(str).str.strip()

    # 12. ลบรายการซ้ำซ้อน (Deduplication)
    initial_cnt = len(df)
    df = df.drop_duplicates(subset=['บริษัท', 'รหัสทรัพย์'] if ('บริษัท' in df.columns and 'รหัสทรัพย์' in df.columns) else None)
    dup_removed = initial_cnt - len(df)
    if dup_removed > 0:
        print(f"  🧹  ลบรายการซ้ำซ้อน (Duplicates): {dup_removed:,} รายการ", flush=True)

    return df

def find_best_input_csv(input_path=None):
    """ค้นหาไฟล์ CSV รวมรายเดือนที่ดีที่สุดอัตโนมัติ"""
    if input_path and os.path.isfile(input_path):
        return input_path

    # Search candidates in prioritized locations
    search_paths = []
    if input_path:
        search_paths.append(input_path)
    search_paths.extend([
        "CSV_Output",
        "Monthly all new/CSV_Output",
        "."
    ])

    candidates = []
    for sp in search_paths:
        if not os.path.exists(sp):
            continue
        if os.path.isfile(sp):
            candidates.append(sp)
            continue
            
        # Look for all_assets_monthly_*.csv recursively
        pattern1 = os.path.join(sp, "**", "all_assets_monthly_*.csv")
        pattern2 = os.path.join(sp, "all_assets_monthly_*.csv")
        pattern3 = os.path.join(sp, "**", "all_assets*.csv")
        
        found = glob.glob(pattern1, recursive=True) + glob.glob(pattern2) + glob.glob(pattern3, recursive=True)
        for f in found:
            f_norm = os.path.normpath(f)
            if "_BACKUP.csv" not in f_norm and f_norm not in candidates:
                candidates.append(f_norm)

    if candidates:
        # Sort by modification time descending
        candidates.sort(key=lambda p: os.path.getmtime(p), reverse=True)
        return candidates[0]

    return None

def convert_csv_to_parquet(input_path=None, output_path="all_assets.parquet", exclude_unwanted=True):
    """
    ฟังก์ชันหลักในการแปลงไฟล์ CSV เป็น Parquet
    """
    start_time = time.time()
    print("=" * 70)
    print("🚀 เริ่มต้นกระบวนการแปลงไฟล์ CSV เป็น Parquet (Optimized for Streamlit Cloud)")
    print("=" * 70)

    # 1. ค้นหาไฟล์ CSV เป้าหมาย
    target_file = find_best_input_csv(input_path)

    if not target_file or not os.path.exists(target_file):
        print("=" * 70)
        print(f"❌ ไม่พบไฟล์ CSV รวมสำหรับแปลงข้อมูล")
        print("=" * 70)
        print("🔍 คำแนะนำ:")
        print("   กรุณารันคำสั่งรวมไฟล์ CSV ก่อน โดยพิมพ์:")
        print("   👉 python \"Monthly all new/merge_csv_monthly.py\"")
        print("   จากนั้นค่อยรัน convert_csv_to_parquet.py อีกครั้ง")
        print("=" * 70)
        return False

    sz = os.path.getsize(target_file)
    print(f"📂 ไฟล์ CSV ที่พบ: {target_file}")
    print(f"  [+] อ่าน {os.path.basename(target_file):<35s} | ขนาด: {sz/(1024*1024):.2f} MB")

    # 2. อ่านไฟล์ CSV
    try:
        combined_df, enc = read_csv_safely(target_file)
        print(f"  [+] โหลดข้อมูลสำเร็จ: {len(combined_df):,d} แถว (Enc: {enc})")
    except Exception as e:
        print(f"❌ ไม่สามารถอ่านไฟล์ {target_file}: {e}")
        return False

    total_csv_size = sz
    print(f"\n📊 ข้อมูลดิบที่นำมาแปลง: {len(combined_df):,} แถว ({total_csv_size/(1024*1024):.2f} MB)")

    # 3. ทำความสะอาดและ Optimize ข้อมูล
    clean_df = optimize_and_clean_dataframe(combined_df, exclude_unwanted=exclude_unwanted)

    # 4. บันทึกเป็น Parquet ด้วยการบีบอัด ZSTD
    if not output_path:
        output_path = "all_assets.parquet"

    print(f"\n💾 กำลังบันทึกไฟล์ Parquet ความเร็วสูง (ZSTD Compression)...", flush=True)
    clean_df.to_parquet(output_path, compression='zstd', index=False)

    parquet_size = os.path.getsize(output_path)
    ram_usage = clean_df.memory_usage(deep=True).sum()
    elapsed = time.time() - start_time

    print("=" * 70)
    print("🎉 แปลงไฟล์สำเร็จเรียบร้อย! (Conversion Completed)")
    print("=" * 70)
    print(f"📁 ไฟล์ผลลัพธ์ (Output):       {os.path.abspath(output_path)}")
    print(f"📊 จำนวนรายการทั้งหมด:        {len(clean_df):,} รายการ")
    print(f"📦 ขนาดไฟล์ Parquet:         {parquet_size / (1024*1024):.2f} MB (ลดลง {(1 - parquet_size/total_csv_size)*100:.1f}%)")
    print(f"⚡ การใช้ Memory ใน RAM:     {ram_usage / (1024*1024):.2f} MB (เบามาก เหมาะกับ Streamlit Cloud)")
    print(f"⏱️  เวลาที่ใช้ทั้งหมด:          {elapsed:.2f} วินาที")
    print("=" * 70)
    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="สคริปต์แปลงและบีบอัดไฟล์ CSV เป็น Parquet สำหรับ All Asset Dashboard")
    parser.add_argument("-i", "--input", default=None, help="เส้นทางไฟล์ CSV หรือโฟลเดอร์ที่เก็บ CSV (ค่าเริ่มต้น: ค้นหาอัตโนมัติใน CSV_Output)")
    parser.add_argument("-o", "--output", default="all_assets.parquet", help="ชื่อไฟล์ Parquet ผลลัพธ์ (ค่าเริ่มต้น: 'all_assets.parquet')")
    parser.add_argument("--keep-all", action="store_true", help="เก็บข้อมูลทุกบริษัทไว้ทั้งหมดโดยไม่ตัด Taladnudbaan")
    
    args = parser.parse_args()
    
    # Run conversion
    convert_csv_to_parquet(
        input_path=args.input,
        output_path=args.output,
        exclude_unwanted=not args.keep_all
    )
