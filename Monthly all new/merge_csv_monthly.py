import os
import glob
import sys
import time
import re
import pandas as pd
from datetime import datetime

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_DIR = os.path.join(BASE_DIR, "CSV_Output")
CURRENT_YM = datetime.now().strftime("%Y_%m")
CURRENT_YM_DISPLAY = datetime.now().strftime("%Y-%m")

MASTER_CSV = os.path.join(CSV_DIR, "all_assets_monthly.csv")
MASTER_CSV_TIMED = os.path.join(CSV_DIR, f"all_assets_monthly_{CURRENT_YM}.csv")

ROOT_DIR = os.path.dirname(BASE_DIR)
ROOT_PARQUET = os.path.join(ROOT_DIR, "all_assets.parquet")
ROOT_CSV = os.path.join(ROOT_DIR, "all_assets.csv")

COLUMNS = [
    "บริษัท", "ID", "รหัสทรัพย์", "ชื่อโครงการ", "ประเภททรัพย์", "ประเภทการขาย", "ราคา",
    "ตำบล", "อำเภอ", "จังหวัด", "ละติจูด", "ลองจิจูด", "ชื่อประกาศ", "ลิงก์",
    "เนื้อที่ (ตร.ว.)", "พื้นที่ใช้สอย (ตร.ม.)", "วันที่ดึงข้อมูล",
    "ห้องนอน", "ห้องน้ำ", "ที่จอดรถ", "วันประกาศ", "บริษัทเจ้าของทรัพย์", "เดือน-ปี"
]

def extract_month_year(filename, df):
    """Extract YYYY-MM from filename or fallback to วันที่ดึงข้อมูล / current date."""
    m = re.search(r'(\d{4})_(\d{2})', filename)
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    
    if "วันที่ดึงข้อมูล" in df.columns:
        valid_dates = df["วันที่ดึงข้อมูล"].dropna().astype(str)
        if not valid_dates.empty:
            m_date = re.search(r'(\d{4})[-\/](\d{2})', valid_dates.iloc[0])
            if m_date:
                return f"{m_date.group(1)}-{m_date.group(2)}"
                
    return CURRENT_YM_DISPLAY

def merge_monthly_csv():
    print("==========================================================================", flush=True)
    print("📊 เริ่มต้นการรวมไฟล์ CSV ทั้งหมดจาก Monthly all new/CSV_Output/", flush=True)
    print(f"📅 ประจำรอบเดือน-ปี: {CURRENT_YM_DISPLAY}", flush=True)
    print("==========================================================================", flush=True)
    
    csv_files = glob.glob(os.path.join(CSV_DIR, "*.csv"))
    csv_files = [
        f for f in csv_files 
        if not os.path.basename(f).startswith("all_assets_monthly")
        and not f.endswith("_BACKUP.csv")
        and "livinginsider" not in os.path.basename(f).lower()
    ]
    
    if not csv_files:
        print(f"⚠️ ไม่พบไฟล์ CSV ในโฟลเดอร์ {CSV_DIR}", flush=True)
        return False
        
    dfs = []
    for f in sorted(csv_files):
        try:
            df = pd.read_csv(f, encoding="utf-8-sig", dtype=str)
            month_year_val = extract_month_year(os.path.basename(f), df)
            
            if "เดือน-ปี" not in df.columns or df["เดือน-ปี"].isna().all():
                df["เดือน-ปี"] = month_year_val
                
            for col in COLUMNS:
                if col not in df.columns:
                    df[col] = ""
            df = df[COLUMNS]
            company_name = os.path.basename(f).split('_')[0]
            print(f"  [+] โหลด {company_name:<13s}: {len(df):,d} รายการ ({os.path.basename(f)} | รอบ {month_year_val})", flush=True)
            dfs.append(df)
        except Exception as e:
            print(f"  [-] อ่านไฟล์ {f} ล้มเหลว: {e}", flush=True)
            
    if not dfs:
        print("❌ ไม่พบข้อมูลสำหรับรวมไฟล์", flush=True)
        return False
        
    combined_df = pd.concat(dfs, ignore_index=True)
    
    def safe_write_csv(df_in, target_path, label):
        for attempt in range(3):
            try:
                df_in.to_csv(target_path, index=False, encoding="utf-8-sig")
                print(f"💾 [{label}] บันทึกสำเร็จ: {target_path}", flush=True)
                return True
            except PermissionError:
                if attempt < 2:
                    time.sleep(1)
                else:
                    alt_path = target_path.replace(".csv", "_BACKUP.csv")
                    df_in.to_csv(alt_path, index=False, encoding="utf-8-sig")
                    print(f"⚠️ [{label}] ไฟล์ถูกเปิดล็อกไว้ใน Excel -> บันทึกข้อมูลสำรองไว้ที่ {alt_path} แทน", flush=True)
                    return True
        return False

    # 1. Save standard all_assets_monthly.csv
    safe_write_csv(combined_df, MASTER_CSV, "MASTER CSV")
    
    # 2. Save timestamped all_assets_monthly_YYYY_MM.csv
    safe_write_csv(combined_df, MASTER_CSV_TIMED, "MONTHLY CSV")
    
    # 3. Save root files (CSV and Parquet for Dashboard)
    try:
        safe_write_csv(combined_df, ROOT_CSV, "ROOT CSV")
        
        df_p = combined_df.copy()
        df_p["ราคา"] = pd.to_numeric(df_p["ราคา"], errors="coerce")
        df_p["ละติจูด"] = pd.to_numeric(df_p["ละติจูด"], errors="coerce")
        df_p["ลองจิจูด"] = pd.to_numeric(df_p["ลองจิจูด"], errors="coerce")
        df_p["ห้องนอน"] = pd.to_numeric(df_p["ห้องนอน"], errors="coerce")
        df_p["ห้องน้ำ"] = pd.to_numeric(df_p["ห้องน้ำ"], errors="coerce")
        df_p.to_parquet(ROOT_PARQUET, index=False, compression="zstd")
        print(f"🚀 [PARQUET]    อัปเดตไฟล์ความเร็วสูง Dashboard: {ROOT_PARQUET}", flush=True)
    except Exception as e:
        print(f"⚠️ เตือน: ไม่สามารถบันทึก Parquet ได้: {e}", flush=True)
        
    print("==========================================================================", flush=True)
    print(f"🎉 รวมข้อมูลเสร็จสมบูรณ์! ข้อมูลสุทธิทั้งหมด {len(combined_df):,} รายการ (รอบ {CURRENT_YM_DISPLAY})", flush=True)
    print("==========================================================================", flush=True)
    return True

if __name__ == "__main__":
    merge_monthly_csv()
