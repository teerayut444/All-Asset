import os
import glob
import sys
import time
import re
import pandas as pd
import numpy as np
from datetime import datetime

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

_BASE_DIR = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))
BASE_DIR = _BASE_DIR
CURRENT_YM = datetime.now().strftime("%Y_%m")
MONTHLY_DIR = os.path.join(BASE_DIR, "CSV_Output", CURRENT_YM)
CSV_DIR = MONTHLY_DIR if os.path.exists(MONTHLY_DIR) else os.path.join(BASE_DIR, "CSV_Output")
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
    "บ้านครึ่งตึกครึ่งไม้": "บ้านเดี่ยว",
    "บ้านพร้อมกิจการ": "บ้านเดี่ยว",
    
    # 2. หมวดคอนโดมิเนียม / ห้องชุด
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
    "ที่ดินเปล่า": "ที่ดินเปล่า",
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
    "โรงภาพยนต์": "อื่นๆ",
    "สวนน้ำ": "อื่นๆ",
    "โรงพยาบาล": "อื่นๆ",
    "อาคารจอดรถ": "อื่นๆ",
    "บ้านพักคนงาน": "อื่นๆ",
    "อาคาร": "อื่นๆ",
    "Public Service": "อื่นๆ",
    "โครงการที่พักอาศัย/พาณิชยกรรม": "อื่นๆ",
    "อสังหาริมทรัพย์อื่นๆ": "อื่นๆ",
}

def parse_rai_ngan_wah_robust(s):
    if s is None or pd.isna(s):
        return None, None, None
    s = str(s).strip()
    if not s or s.lower() in ["nan", "none", "null", "$undefined", "-", "0", "0.0", "."]:
        return None, None, None
    
    # 1. Dash pattern: R-N-W
    m_dash = re.match(r'^(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)$', s)
    if m_dash:
        try:
            return float(m_dash.group(1)), float(m_dash.group(2)), float(m_dash.group(3))
        except ValueError:
            pass
        
    # 2. Thai explicit units: ไร่, งาน, วา / ตร.ว. / ตารางวา
    has_thai_units = any(u in s for u in ['ไร่', 'งาน', 'วา', 'ตร.ว', 'ตารางวา', 'ตร.ว.'])
    if has_thai_units:
        m_r = re.search(r'([\d\.,]+)\s*ไร่', s)
        m_g = re.search(r'([\d\.,]+)\s*งาน', s)
        m_w = re.search(r'([\d\.,]+)\s*(?:ตร\.?ว\.?|ตารางวา|วา)', s)
        
        r, g, w = 0.0, 0.0, 0.0
        try:
            if m_r: r = float(m_r.group(1).replace(',', ''))
        except ValueError: pass
        try:
            if m_g: g = float(m_g.group(1).replace(',', ''))
        except ValueError: pass
        try:
            if m_w: w = float(m_w.group(1).replace(',', ''))
        except ValueError: pass
        
        if r > 0 or g > 0 or w > 0:
            return r, g, w

    # 3. Clean numeric with optional unit suffix
    clean_num = re.sub(r'[^\d\.]', '', s)
    if clean_num and clean_num != '.' and clean_num != '..':
        try:
            total_wah = float(clean_num)
            if total_wah > 0:
                r = int(total_wah // 400)
                rem = total_wah - (r * 400)
                g = int(rem // 100)
                w = rem - (g * 100)
                return r, g, round(w, 4)
        except ValueError:
            pass
            
    return None, None, None

def format_wah_val(w):
    if isinstance(w, float) and w.is_integer():
        return str(int(w))
    elif isinstance(w, int):
        return str(int(w))
    elif isinstance(w, float):
        return f"{w:g}"
    return str(w)

def convert_to_rai_ngan_wah(val):
    r, g, w = parse_rai_ngan_wah_robust(val)
    if r is None:
        return ""
    if w >= 100:
        g += int(w // 100)
        w = w % 100
    if g >= 4:
        r += int(g // 4)
        g = g % 4
    if r == 0 and g == 0 and w == 0:
        return ""
    return f"{int(r)}-{int(g)}-{format_wah_val(w)}"

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
            return 'ที่ดินเปล่า'
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
        and "ddproperty" not in os.path.basename(f).lower()
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
            
            # แปลงคอลัมน์ เนื้อที่ (ตร.ว.) ให้เป็นรูปแบบ ไร่-งาน-ตร.ว. (เช่น 1-1-1, 0-1-1, 0-0-1)
            if 'เนื้อที่ (ตร.ว.)' in df.columns:
                df['เนื้อที่ (ตร.ว.)'] = df['เนื้อที่ (ตร.ว.)'].apply(convert_to_rai_ngan_wah)
                df.to_csv(f, index=False, encoding="utf-8-sig")

            company_name = os.path.basename(f).split('_')[0]
            # Ensure primary company name is set correctly for dashboard filters
            if company_name in ['Baania', 'BAM', 'SAM', 'Taladnudbaan', 'ZmyHome', 'Chayo555', 'NaYoo', 'GHB', 'KBANK', 'KTB', 'SCB', 'GSB']:
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
        combined_df = combined_df[combined_df['ประเภทการขาย'].astype(str).str.strip() != 'ให้เช่า']
        sale_map = {
            'ซื้อตรง': 'ขาย',
            'ทรัพย์ธนาคาร': 'ขาย',
            'ทรัพย์โปรโมชั่นราคาพิเศษ': 'ขาย',
            'ทรัพย์โปรโมชันราคาพิเศษ': 'ขาย',
            'โปรโมชั่น': 'ขาย',
            'โปรโมชัน': 'ขาย',
            'ทรัพย์ฝากขาย': 'ขาย',
            'ฝากขาย': 'ขาย',
            'ขายดาวน์': 'ขาย',
            'ขาย/เช่า': 'ขาย',
        }
        combined_df['ประเภทการขาย'] = (
            combined_df['ประเภทการขาย']
            .astype(str)
            .str.strip()
            .replace(sale_map)
        )
        print("  ✨ จัดกลุ่มประเภทการขาย (รวมทรัพย์ธนาคาร/โปรโมชั่น/ฝากขาย/ขายดาวน์ เข้า 'ขาย' และตัด 'ให้เช่า') เรียบร้อยแล้ว", flush=True)
    
    # แปลงคอลัมน์ เนื้อที่ (ตร.ว.) ให้เป็นรูปแบบ ไร่-งาน-ตร.ว. (เช่น 1-1-1, 0-1-1, 0-0-1)
    if 'เนื้อที่ (ตร.ว.)' in combined_df.columns:
        combined_df['เนื้อที่ (ตร.ว.)'] = combined_df['เนื้อที่ (ตร.ว.)'].apply(convert_to_rai_ngan_wah)
        print("  ✨ แปลงคอลัมน์ 'เนื้อที่ (ตร.ว.)' เป็นรูปแบบ ไร่-งาน-ตร.ว. (เช่น 1-1-1, 0-1-1, 0-0-1) เรียบร้อยแล้ว", flush=True)

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
        
        # คืนค่าพื้นที่_ตารางวา (float) ให้ Dashboard สำหรับการกรองและคำนวณกราฟ
        def calc_sqwah_num(val):
            r, g, w = parse_rai_ngan_wah_robust(val)
            if r is None:
                return np.nan
            return r * 400.0 + g * 100.0 + w
            
        df_p["พื้นที่_ตารางวา"] = df_p["เนื้อที่ (ตร.ว.)"].apply(calc_sqwah_num)
        
        df_p.to_parquet(ROOT_PARQUET, index=False, compression="zstd")
        print(f"🚀 [PARQUET]    อัปเดตไฟล์ความเร็วสูง Dashboard: {ROOT_PARQUET}", flush=True)
    except Exception as e:
        print(f"⚠️ เตือน: ไม่สามารถบันทึก Parquet ได้: {e}", flush=True)
        
    # Append merge summary to scraping.log
    try:
        log_paths = [
            os.path.join(ROOT_DIR, "scraping.log"),
            os.path.join(MONTHLY_DIR, "scraping.log")
        ]
        time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        merge_msg = f"[{time_str}] [MERGE] Auto-merged {len(combined_df):,} records into {os.path.basename(MASTER_CSV_TIMED)} and {os.path.basename(ROOT_PARQUET)}\n"
        for lp in log_paths:
            with open(lp, "a", encoding="utf-8") as f:
                f.write(merge_msg)
    except Exception:
        pass

    print("==========================================================================", flush=True)
    print(f"🎉 รวมข้อมูลเสร็จสมบูรณ์! ข้อมูลสุทธิทั้งหมด {len(combined_df):,} รายการ (บันทึกเฉพาะไฟล์: {os.path.basename(MASTER_CSV_TIMED)})", flush=True)
    print("==========================================================================", flush=True)
    return True

if __name__ == "__main__":
    merge_monthly_csv()
