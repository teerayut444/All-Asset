import os
import glob
import sys
import time
import re
import pandas as pd
from datetime import datetime

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

_BASE_DIR = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))
BASE_DIR = _BASE_DIR
CSV_DIR = os.path.join(BASE_DIR, "CSV_Output")
CURRENT_YM = datetime.now().strftime("%Y_%m")
CURRENT_YM_DISPLAY = datetime.now().strftime("%Y-%m")

# บันทึกแค่ไฟล์เดียวที่มีปี_เดือน
MASTER_CSV_TIMED = os.path.join(CSV_DIR, f"all_assets_monthly_{CURRENT_YM}.csv")

ROOT_DIR = os.path.dirname(BASE_DIR)
ROOT_PARQUET = os.path.join(ROOT_DIR, "all_assets.parquet")

COLUMNS = [
    "บริษัท", "ID", "รหัสทรัพย์", "ชื่อโครงการ", "ประเภททรัพย์", "ประเภทการขาย", "ราคา",
    "ตำบล", "อำเภอ", "จังหวัด", "ละติจูด", "ลองจิจูด", "ชื่อประกาศ", "ลิงก์",
    "เนื้อที่ (ตร.ว.)", "พื้นที่ใช้สอย (ตร.ม.)", "วันที่ดึงข้อมูล",
    "ห้องนอน", "ห้องน้ำ", "ที่จอดรถ", "วันประกาศ"
]

def merge_monthly_csv():
    print("==========================================================================", flush=True)
    print("📊 เริ่มต้นการรวมไฟล์ CSV ทั้งหมดจาก Monthly all new/CSV_Output/", flush=True)
    print(f"📅 ประจำรอบเดือน-ปี: {CURRENT_YM_DISPLAY}", flush=True)
    print("==========================================================================", flush=True)
    
    csv_files = glob.glob(os.path.join(CSV_DIR, "*.csv"))
    csv_files = [
        f for f in csv_files 
        if not os.path.basename(f).startswith("all_assets_monthly")
        and not os.path.basename(f).startswith("all_assets_")
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
            for col in COLUMNS:
                if col not in df.columns:
                    df[col] = ""
            df = df[COLUMNS]
            company_name = os.path.basename(f).split('_')[0]
            # Ensure primary company name is set correctly for dashboard filters
            if company_name in ['Baania', 'BAM', 'SAM', 'DDproperty', 'Taladnudbaan', 'ZmyHome']:
                if 'บริษัทเจ้าของทรัพย์' in df.columns:
                    df['บริษัทเจ้าของทรัพย์'] = df['บริษัท']
                df['บริษัท'] = company_name
            print(f"  [+] โหลด {company_name:<13s}: {len(df):,d} รายการ ({os.path.basename(f)})", flush=True)
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

    # บันทึกไฟล์เดียวที่มี ปี_เดือน
    safe_write_csv(combined_df, MASTER_CSV_TIMED, f"MASTER CSV ({CURRENT_YM})")
    
    # ลบไฟล์ซ้ำซ้อนที่ไม่จำเป็นออก
    redundant_files = [
        os.path.join(CSV_DIR, "all_assets_monthly.csv"),
        os.path.join(ROOT_DIR, "all_assets.csv"),
        os.path.join(ROOT_DIR, f"all_assets_{CURRENT_YM}.csv")
    ]
    for rf in redundant_files:
        if os.path.exists(rf):
            try:
                os.remove(rf)
            except Exception:
                pass
                
    # แปลงและอัปเดต Parquet ความเร็วสูงสำหรับ Dashboard
    try:
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
    print(f"🎉 รวมข้อมูลเสร็จสมบูรณ์! ข้อมูลสุทธิทั้งหมด {len(combined_df):,} รายการ (บันทึกเฉพาะไฟล์: {os.path.basename(MASTER_CSV_TIMED)})", flush=True)
    print("==========================================================================", flush=True)
    return True

if __name__ == "__main__":
    merge_monthly_csv()
