import os
import glob
import sys
import time
import pandas as pd
from datetime import datetime

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_DIR = os.path.join(BASE_DIR, "CSV_Output")
MASTER_CSV = os.path.join(CSV_DIR, "all_assets_monthly.csv")

ROOT_DIR = os.path.dirname(BASE_DIR)
ROOT_PARQUET = os.path.join(ROOT_DIR, "all_assets.parquet")
ROOT_CSV = os.path.join(ROOT_DIR, "all_assets.csv")

COLUMNS = [
    "บริษัท", "ID", "รหัสทรัพย์", "ชื่อโครงการ", "ประเภททรัพย์", "ประเภทการขาย", "ราคา",
    "ตำบล", "อำเภอ", "จังหวัด", "ละติจูด", "ลองจิจูด", "ชื่อประกาศ", "ลิงก์",
    "พื้นที่ (ไร่-งาน-วา)", "พื้นที่ใช้สอย (ตร.ม.)", "วันที่ดึงข้อมูล",
    "ห้องนอน", "ห้องน้ำ", "ที่จอดรถ", "วันประกาศ", "บริษัทเจ้าของทรัพย์"
]

def merge_monthly_csv():
    print("==========================================================================", flush=True)
    print("📊 เริ่มต้นการรวมไฟล์ CSV ทั้งหมดจาก Monthly all new/CSV_Output/", flush=True)
    print("==========================================================================", flush=True)
    
    csv_files = glob.glob(os.path.join(CSV_DIR, "*.csv"))
    csv_files = [f for f in csv_files if not f.endswith("all_assets_monthly.csv") and not f.endswith("_BACKUP.csv")]
    
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

    safe_write_csv(combined_df, MASTER_CSV, "MASTER CSV")
    
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
    print(f"🎉 รวมข้อมูลเสร็จสมบูรณ์! ข้อมูลสุทธิทั้งหมด {len(combined_df):,} รายการ", flush=True)
    print("==========================================================================", flush=True)
    return True

if __name__ == "__main__":
    merge_monthly_csv()
