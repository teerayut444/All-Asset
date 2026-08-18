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

# ตารางการจัดกลุ่มและแปลงประเภททรัพย์สินให้เป็นมาตรฐานเดียวกันทุกค่าย
PROPERTY_TYPE_MAPPING = {
    # 1. หมวดบ้านเดี่ยว
    "บ้าน": "บ้านเดี่ยว",
    
    # 2. หมวดคอนโดมิเนียม / ห้องชุด
    "คอนโด": "ห้องชุดพักอาศัย",
    "คอนโดมิเนียม": "ห้องชุดพักอาศัย",
    
    # 3. หมวดทาวน์เฮ้าส์ / ทาวน์โฮม
    "ทาวน์โฮม": "ทาวน์เฮ้าส์",
    "ทาวน์เฮาส์": "ทาวน์เฮ้าส์",
    
    # 4. หมวดที่ดิน
    "ที่ดินเปล่า": "ที่ดิน",
    "ที่ดินเกษตรกรรม": "ที่ดิน",
    
    # 5. หมวดโรงงาน / โกดัง
    "โรงงาน": "โรงงาน/โกดัง",
    "โกดัง/โรงงาน": "โรงงาน/โกดัง",
    "โกดัง / โรงงาน": "โรงงาน/โกดัง",
    "มินิแฟคตอรี่": "โรงงาน/โกดัง",
    
    # 6. หมวดอพาร์ทเมนท์ / หอพัก
    "อพาร์ทเม้นท์": "อพาร์ทเมนท์",
    "อพาร์ตเมนต์": "อพาร์ทเมนท์",
    "อพาตเมนต์": "อพาร์ทเมนท์",
    "อาคารพักอาศัย": "อพาร์ทเมนท์",
    
    # 7. หมวดโรงแรม / รีสอร์ท
    "Hotel Building": "โรงแรม/รีสอร์ท",
    "โรงแรม": "โรงแรม/รีสอร์ท",
    "รีสอร์ท": "โรงแรม/รีสอร์ท",
    
    # 8. หมวดสำนักงาน / เชิงพาณิชย์
    "สำนักงาน": "อาคารสำนักงาน",
    "ห้องชุดสำนักงาน": "ห้องชุดพาณิชยกรรม/สำนักงาน",
    "ห้องชุดพาณิชยกรรม": "ห้องชุดพาณิชยกรรม/สำนักงาน",
    
    # 9. หมวดสังหาริมทรัพย์ & อื่นๆ
    "เครื่องจักร": "สังหาริมทรัพย์",
    "บัตรสมาชิกสนามกอล์ฟ": "สังหาริมทรัพย์",
    "ส่วนโล่งหลังคาคลุม": "อื่นๆ",
}

def resolve_mixed_property_types(df):
    """Resolves fallback mixed property types (e.g. 'บ้านเดี่ยว/ทาวน์เฮาส์') based on listing title."""
    if 'ประเภททรัพย์' not in df.columns:
        return df
    
    mask = df['ประเภททรัพย์'].astype(str).str.contains('บ้านเดี่ยว/ทาวน์', na=False)
    if not mask.any():
        return df
        
    def resolve_row(row):
        title = str(row.get('ชื่อประกาศ', '')) + ' ' + str(row.get('ชื่อโครงการ', ''))
        t = title.lower()
        if any(k in t for k in ['ตึกแถว', 'อาคารพาณิชย์', 'shophouse', 'พาณิชย์']):
            return 'อาคารพาณิชย์'
        if any(k in t for k in ['โฮมออฟฟิศ', 'สำนักงาน', 'office', 'home office']):
            return 'อาคารสำนักงาน'
        if any(k in t for k in ['โกดัง', 'โรงงาน', 'warehouse', 'factory']):
            return 'โรงงาน/โกดัง'
        if any(k in t for k in ['ทาวน์โฮม', 'ทาวน์เฮ้าส์', 'ทาวน์เฮาส์', 'townhome', 'townhouse', 'ทาวน์']):
            return 'ทาวน์เฮ้าส์'
        if any(k in t for k in ['ที่ดิน', 'land']):
            return 'ที่ดิน'
        if any(k in t for k in ['คอนโด', 'ห้องชุด', 'condo']):
            return 'ห้องชุดพักอาศัย'
        return 'บ้านเดี่ยว'
        
    df.loc[mask, 'ประเภททรัพย์'] = df[mask].apply(resolve_row, axis=1)
    return df

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
            if company_name in ['Baania', 'BAM', 'SAM', 'DDproperty', 'Taladnudbaan', 'ZmyHome', 'Chayo555', 'NaYoo']:
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
    
    # ทำความสะอาดและจัดกลุ่มประเภททรัพย์สินให้เป็นมาตรฐานเดียวกัน
    if 'ประเภททรัพย์' in combined_df.columns:
        combined_df['ประเภททรัพย์'] = (
            combined_df['ประเภททรัพย์']
            .astype(str)
            .str.strip()
            .replace(PROPERTY_TYPE_MAPPING)
        )
        combined_df = resolve_mixed_property_types(combined_df)
        print("  ✨ จัดกลุ่มประเภททรัพย์สิน (Property Type Normalization) เรียบร้อยแล้ว", flush=True)
        
    # ทำความสะอาดและจัดกลุ่มประเภทการขาย
    if 'ประเภทการขาย' in combined_df.columns:
        combined_df['ประเภทการขาย'] = (
            combined_df['ประเภทการขาย']
            .astype(str)
            .str.strip()
            .replace({'ซื้อตรง': 'ขาย'})
        )
        print("  ✨ จัดกลุ่มประเภทการขาย (รวม 'ซื้อตรง' เข้า 'ขาย') เรียบร้อยแล้ว", flush=True)
    
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
