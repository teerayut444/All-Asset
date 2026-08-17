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

# Helper function to parse land area string ('ไร่-งาน-วา') to sq.wah
def parse_land_sqwah(val):
    if pd.isna(val) or not str(val).strip():
        return np.nan
    s = str(val).strip()
    # If already a numeric float/int
    try:
        return float(s)
    except ValueError:
        pass
    
    import re
    # Match patterns like: 2-1-50 or 2 ไร่ 1 งาน 50 วา
    m_dash = re.match(r'^(\d+(?:\.\d+)?)-(\d+(?:\.\d+)?)-(\d+(?:\.\d+)?)$', s)
    if m_dash:
        r, g, w = float(m_dash.group(1)), float(m_dash.group(2)), float(m_dash.group(3))
        return r * 400.0 + g * 100.0 + w
        
    m_thai = re.search(r'(?:(\d+(?:\.\d+)?)\s*ไร่)?\s*(?:(\d+(?:\.\d+)?)\s*งาน)?\s*(?:(\d+(?:\.\d+)?)\s*(?:วา|ตร\.?ว\.?|ตารางวา))?', s)
    if m_thai and (m_thai.group(1) or m_thai.group(2) or m_thai.group(3)):
        r = float(m_thai.group(1) or 0)
        g = float(m_thai.group(2) or 0)
        w = float(m_thai.group(3) or 0)
        return r * 400.0 + g * 100.0 + w
    return np.nan

def read_csv_safely(file_path):
    """Read CSV file trying common Thai encodings."""
    encodings = ['utf-8-sig', 'utf-8', 'cp874', 'tis-620', 'latin1']
    for enc in encodings:
        try:
            df = pd.read_csv(file_path, encoding=enc, low_memory=False, dtype=str)
            return df, enc
        except (UnicodeDecodeError, Exception):
            continue
    raise ValueError(f"ไม่สามารถอ่านไฟล์ {file_path} ด้วยการเข้ารหัสที่รองรับได้")

def optimize_and_clean_dataframe(df, exclude_livinginsider=True):
    """
    Cleans, parses, and downcasts DataFrame columns for maximum speed and minimal RAM/Disk size.
    """
    print("  ⚙️  กำลังทำความสะอาดและแปลงชนิดข้อมูล (Data Optimization)...", flush=True)
    
    # 1. Clean column names
    df.columns = [c.strip() for c in df.columns]
    
    # 2. Exclude Livinginsider if requested
    if exclude_livinginsider and 'บริษัท' in df.columns:
        before_len = len(df)
        df = df[df['บริษัท'].astype(str).str.strip().str.lower() != 'livinginsider'].copy()
        diff = before_len - len(df)
        if diff > 0:
            print(f"  ✂️  ตัดข้อมูล Livinginsider ออก: {diff:,} รายการ (คงเหลือ {len(df):,} รายการ)", flush=True)

    # 3. Clean and parse numeric price
    if 'ราคา' in df.columns:
        df['ราคา'] = pd.to_numeric(df['ราคา'].astype(str).str.replace(',', '').str.strip(), errors='coerce')
        # Filter out negative or zero prices
        df.loc[df['ราคา'] <= 0, 'ราคา'] = np.nan
        df['ราคา'] = df['ราคา'].astype('float32')

    # 4. Clean coordinates
    for coord_col in ['ละติจูด', 'ลองจิจูด']:
        if coord_col in df.columns:
            df[coord_col] = pd.to_numeric(df[coord_col].astype(str).str.replace(',', '').str.strip(), errors='coerce')
            df.loc[df[coord_col] == 0, coord_col] = np.nan
            df[coord_col] = df[coord_col].astype('float32')

    # Filter out coords outside Thailand boundary
    if 'ละติจูด' in df.columns and 'ลองจิจูด' in df.columns:
        invalid_coords = ~(df['ละติจูด'].between(5.0, 21.0) & df['ลองจิจูด'].between(97.0, 106.0))
        df.loc[invalid_coords, ['ละติจูด', 'ลองจิจูด']] = np.nan

    # 5. Clean usable area (ตร.ม.)
    area_col = None
    for c in ['พื้นที่ใช้สอย (ตร.ม.)', 'พื้นที่ใช้สอย', 'usable_area']:
        if c in df.columns:
            area_col = c
            break
    if area_col:
        df['พื้นที่ใช้สอย (ตร.ม.)'] = pd.to_numeric(df[area_col].astype(str).str.replace(',', '').str.strip(), errors='coerce')
        
        # Sanity check: Fix cases where price was mistakenly copied into usable area (e.g. 10,000,000 sqm for condo)
        if 'ราคา' in df.columns:
            corrupt_mask = (df['ราคา'] > 10000) & (df['พื้นที่ใช้สอย (ตร.ม.)'] == df['ราคา'])
            if 'ประเภททรัพย์' in df.columns:
                corrupt_mask |= (df['ประเภททรัพย์'].isin(['คอนโด', 'ห้องชุด', 'ทาวน์เฮ้าส์', 'ทาวน์โฮม']) & (df['พื้นที่ใช้สอย (ตร.ม.)'] > 5000))
            df.loc[corrupt_mask, 'พื้นที่ใช้สอย (ตร.ม.)'] = np.nan
            
        df['พื้นที่ใช้สอย (ตร.ม.)'] = df['พื้นที่ใช้สอย (ตร.ม.)'].astype('float32')

    # 6. Clean land area (ตารางวา)
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

    # 7. Integer counts (ห้องนอน, ห้องน้ำ, ที่จอดรถ)
    for c in ['ห้องนอน', 'ห้องน้ำ', 'ที่จอดรถ']:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors='coerce').astype('Int16')

    # 8. Convert repetitive text columns to category to save 80% RAM
    cat_cols = ['บริษัท', 'ประเภททรัพย์', 'ประเภทการขาย', 'จังหวัด', 'อำเภอ', 'ตำบล']
    for c in cat_cols:
        if c in df.columns:
            # Replace empty/nan strings
            df[c] = df[c].fillna('ไม่มีข้อมูล').astype(str).str.strip()
            df[c] = df[c].astype('category')

    # 9. Clean Title and Link
    if 'ชื่อประกาศ' not in df.columns and 'ชื่อโครงการ' in df.columns:
        df['ชื่อประกาศ'] = df['ชื่อโครงการ']
    if 'ชื่อประกาศ' in df.columns:
        df['ชื่อประกาศ'] = df['ชื่อประกาศ'].fillna('ไม่มีชื่อ').astype(str).str.strip()

    if 'ลิงก์' in df.columns:
        df['ลิงก์'] = df['ลิงก์'].fillna('').astype(str).str.strip()

    # 10. Drop complete duplicates
    initial_cnt = len(df)
    df = df.drop_duplicates(subset=['บริษัท', 'รหัสทรัพย์'] if ('บริษัท' in df.columns and 'รหัสทรัพย์' in df.columns) else None)
    dup_removed = initial_cnt - len(df)
    if dup_removed > 0:
        print(f"  🧹  ลบรายการซ้ำซ้อน (Duplicates): {dup_removed:,} รายการ", flush=True)

    return df

def convert_csv_to_parquet(input_path, output_path=None, exclude_livinginsider=True):
    """
    Main conversion function supporting single CSV file or wildcard / folder merge.
    """
    start_time = time.time()
    print("=" * 70)
    print("🚀 เริ่มต้นกระบวนการแปลงไฟล์ CSV เป็น Parquet (Optimized for Streamlit Cloud)")
    print("=" * 70)

    # 1. Determine input file (only convert the single target monthly file, not all files)
    target_file = None
    if os.path.isdir(input_path):
        # Look for the monthly merged CSV file with month-year specifically
        candidates = sorted(glob.glob(os.path.join(input_path, "all_assets_monthly_*.csv")), reverse=True)
        candidates = [c for c in candidates if not c.endswith("_BACKUP.csv")]
        if candidates:
            target_file = candidates[0]
        elif os.path.exists(os.path.join(input_path, "all_assets_monthly.csv")):
            target_file = os.path.join(input_path, "all_assets_monthly.csv")
        elif os.path.exists(os.path.join(input_path, "all_assets.csv")):
            target_file = os.path.join(input_path, "all_assets.csv")
    elif os.path.isfile(input_path):
        target_file = input_path
    elif "*" in input_path or "?" in input_path:
        matches = glob.glob(input_path)
        if matches:
            target_file = matches[0]

    if not target_file or not os.path.exists(target_file):
        print(f"❌ ไม่พบไฟล์ต้นทางที่ต้องการแปลง: {input_path}")
        return False

    sz = os.path.getsize(target_file)
    print(f"📂 ไฟล์ CSV ที่จะแปลง (แปลงเฉพาะไฟล์นี้): {target_file}")
    print(f"  [+] อ่าน {os.path.basename(target_file):<35s} | ขนาด: {sz/(1024*1024):.2f} MB")

    # 2. Read single CSV file
    try:
        combined_df, enc = read_csv_safely(target_file)
        print(f"  [+] โหลดข้อมูลสำเร็จ: {len(combined_df):,d} แถว (Enc: {enc})")
    except Exception as e:
        print(f"❌ ไม่สามารถอ่านไฟล์ {target_file}: {e}")
        return False

    total_csv_size = sz
    print(f"\n📊 ข้อมูลดิบที่นำมาแปลง: {len(combined_df):,} แถว ({total_csv_size/(1024*1024):.2f} MB)")

    # 3. Clean and optimize data
    clean_df = optimize_and_clean_dataframe(combined_df, exclude_livinginsider=exclude_livinginsider)

    # 4. Determine output path
    if output_path is None:
        if len(csv_files) == 1 and not os.path.isdir(input_path):
            output_path = os.path.splitext(csv_files[0])[0] + ".parquet"
        else:
            output_path = "all_assets.parquet"

    # 5. Save to Parquet with ZSTD compression
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
    parser.add_argument("-i", "--input", default="Monthly all new/CSV_Output", help="เส้นทางไฟล์ CSV หรือโฟลเดอร์ที่เก็บ CSV (ค่าเริ่มต้น: 'Monthly all new/CSV_Output')")
    parser.add_argument("-o", "--output", default="all_assets.parquet", help="ชื่อไฟล์ Parquet ผลลัพธ์ (ค่าเริ่มต้น: 'all_assets.parquet')")
    parser.add_argument("--keep-livinginsider", action="store_true", help="เก็บข้อมูล Livinginsider ไว้ (ค่าเริ่มต้น: ตัดออกตามนโยบายระบบ)")
    
    args = parser.parse_args()
    
    # Run conversion
    convert_csv_to_parquet(
        input_path=args.input,
        output_path=args.output,
        exclude_livinginsider=not args.keep_livinginsider
    )
