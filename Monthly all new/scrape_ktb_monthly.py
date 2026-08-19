import requests
import pandas as pd
import re
import os
import time
from datetime import datetime
import threading
import urllib3
import sys

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

COMPANY_NAME = "KTB"
MONTH_STR = datetime.now().strftime("%Y_%m")

_BASE_DIR = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(_BASE_DIR, "CSV_Output")
os.makedirs(OUTPUT_DIR, exist_ok=True)
OUTPUT_CSV = os.path.join(OUTPUT_DIR, f"KTB_NPA_New_{MONTH_STR}.csv")

PAGE_LIMIT = 50

COLUMNS = [
    "บริษัท", "ID", "รหัสทรัพย์", "ชื่อโครงการ", "ประเภททรัพย์", "ประเภทการขาย", "ราคา",
    "ตำบล", "อำเภอ", "จังหวัด", "ละติจูด", "ลองจิจูด", "ชื่อประกาศ", "ลิงก์",
    "เนื้อที่ (ตร.ว.)", "พื้นที่ใช้สอย (ตร.ม.)", "วันที่ดึงข้อมูล",
    "ห้องนอน", "ห้องน้ำ", "ที่จอดรถ", "วันประกาศ"
]

print_lock = threading.Lock()
progress_counter = 0
start_time_global = None

def print_alert(msg: str, level: str = "ERROR"):
    border = "=" * 75
    if level == "CRITICAL":
        icon = "🚨 [CRITICAL ALERT]"
    elif level == "WARNING":
        icon = "⚠️ [WARNING ALERT]"
    else:
        icon = "❌ [ERROR ALERT]"
    with print_lock:
        print(f"\n{border}\n{icon} ({COMPANY_NAME}): {msg}\n{border}\n", flush=True)

def make_progress_bar(pct, length=20):
    filled = int(length * pct / 100)
    bar = '█' * filled + '░' * (length - filled)
    return f"[{bar}] {pct:3d}%"

def format_eta(elapsed_sec, completed_units, total_units):
    if completed_units <= 0 or total_units <= 0 or elapsed_sec <= 0:
        return "กำลังคำนวณ..."
    rate = completed_units / elapsed_sec
    remaining_units = max(0, total_units - completed_units)
    if rate <= 0:
        return "กำลังคำนวณ..."
    eta_sec = remaining_units / rate
    finish_clock = datetime.fromtimestamp(datetime.now().timestamp() + eta_sec).strftime("%H:%M:%S")
    mins = int(eta_sec // 60)
    secs = int(eta_sec % 60)
    if mins > 60:
        hrs = mins // 60
        mins = mins % 60
        return f"เหลือ ~{hrs}ชม.{mins}น. ({finish_clock} น.)"
    elif mins > 0:
        return f"เหลือ ~{mins}น.{secs}ว. ({finish_clock} น.)"
    else:
        return f"เหลือ ~{secs}ว. ({finish_clock} น.)"

def clean_text(t):
    if t is None:
        return ""
    return re.sub(r'\s+', ' ', str(t)).strip()

def parse_rai_ngan_wah(area_str):
    if not area_str:
        return None
    try:
        # e.g. "0-1-57.8" -> 0 rai, 1 ngan, 57.8 wah
        m = re.match(r'(\d+)\s*-\s*(\d+)\s*-\s*([\d\.]+)', str(area_str).strip())
        if m:
            rai = float(m.group(1))
            ngan = float(m.group(2))
            wah = float(m.group(3))
            return rai * 400.0 + ngan * 100.0 + wah
        val = float(area_str)
        return val
    except Exception:
        return None

def load_existing_csv(filename):
    records = []
    seen_ids = set()
    if os.path.exists(filename):
        try:
            df = pd.read_csv(filename, encoding="utf-8-sig")
            for col in COLUMNS:
                if col not in df.columns:
                    df[col] = ""
            records = df[COLUMNS].to_dict(orient="records")
            for r in records:
                iid = str(r.get("ID") or "").strip()
                if iid:
                    seen_ids.add(iid)
            print(f"[{COMPANY_NAME}] 🔄 Smart Resume: โหลดข้อมูลเดิมจาก {filename} พบแล้ว {len(records):,} รายการ", flush=True)
        except Exception as e:
            print_alert(f"ไม่สามารถอ่านไฟล์สะสมเดิม {filename}: {e}", level="WARNING")
    return records, seen_ids

def check_link_health():
    url = "https://npa.krungthai.com/api/v1/product/searchAll"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Content-Type": "application/json",
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://npa.krungthai.com/searchResult"
    }
    payload = {
        "paging": {
            "currentPage": 1,
            "rowsPerPage": PAGE_LIMIT,
            "totalRows": 0
        }
    }
    for attempt in range(5):
        try:
            r = requests.post(url, headers=headers, json=payload, verify=False, timeout=15)
            if r.status_code == 200:
                data = r.json()
                paging = data.get("paging") or {}
                total_items = paging.get("totalRows") or len(data.get("dataResponse") or [])
                total_pages = (total_items + PAGE_LIMIT - 1) // PAGE_LIMIT if total_items > 0 else 1
                return True, r.status_code, total_items, total_pages
        except Exception:
            time.sleep(2)
    return False, 0, 0, 0

def fetch_page(page_no, session):
    url = "https://npa.krungthai.com/api/v1/product/searchAll"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Content-Type": "application/json",
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://npa.krungthai.com/searchResult"
    }
    payload = {
        "paging": {
            "currentPage": page_no,
            "rowsPerPage": PAGE_LIMIT,
            "totalRows": 0
        }
    }
    for attempt in range(3):
        try:
            r = session.post(url, headers=headers, json=payload, verify=False, timeout=15)
            if r.status_code == 200:
                data = r.json()
                return data.get("dataResponse") or []
        except Exception:
            time.sleep(1.5)
    return []

def main():
    global start_time_global, progress_counter
    print(f"[{COMPANY_NAME}] 🚀 เริ่มต้นการดึงข้อมูลประจำเดือน {MONTH_STR}", flush=True)
    
    healthy, code, total_items, total_pages = check_link_health()
    if not healthy:
        print_alert(f"ไม่สามารถเชื่อมต่อ KTB API ได้ (HTTP Status: {code})", level="CRITICAL")
        return

    print(f"[{COMPANY_NAME}] 🌐 ตรวจสอบสถานะลิงก์ปลายทาง: HTTP {code} OK! พบทั้งหมด ~{total_items:,} รายการ ({total_pages:,} หน้า)", flush=True)

    records, seen_ids = load_existing_csv(OUTPUT_CSV)
    
    start_time_global = time.time()
    progress_counter = 0
    today_str = datetime.now().strftime("%Y-%m-%d")

    session = requests.Session()
    adapter = requests.adapters.HTTPAdapter(pool_connections=15, pool_maxsize=15)
    session.mount('https://', adapter)
    session.mount('http://', adapter)

    for page_no in range(1, total_pages + 1):
        items = fetch_page(page_no, session)
        new_page_count = 0
        for item in items:
            p_id = str(item.get("collGrpId") or item.get("collCode") or "").strip()
            if not p_id or p_id in seen_ids:
                continue
            
            seen_ids.add(p_id)
            new_page_count += 1
            
            p_code = clean_text(item.get("collCode") or p_id)
            p_type = clean_text(item.get("collCateName") or item.get("assetTypeDetail") or item.get("collTypeName") or "")
            proj_name = clean_text(item.get("propertyName") or "")
            
            price_raw = str(item.get("price") or item.get("nmlPrice") or item.get("priceNumber") or "").replace(",", "").strip()
            try:
                price = float(price_raw) if price_raw else None
            except Exception:
                price = None
                
            sub_d = clean_text(item.get("shrTambonName") or "").replace("ตำบล", "").replace("แขวง", "").strip()
            dist = clean_text(item.get("shrAmphurName") or "").replace("อำเภอ", "").replace("เขต", "").strip()
            prov = clean_text(item.get("shrProvinceName") or "").replace("จังหวัด", "").strip()
            
            lat = None
            lng = None
            try:
                if item.get("lat"): lat = float(item["lat"])
                if item.get("lon"): lng = float(item["lon"])
            except Exception:
                pass
                
            link = clean_text(item.get("shareURL") or f"https://npa.krungthai.com/propertyDetail/{p_code or p_id}")
            
            # Title
            title = clean_text(item.get("collDesc") or "")
            if not title:
                title = f"{p_type} {proj_name} {dist} {prov}".strip()
                
            # Area
            area_str = item.get("area") or item.get("calSumAreaCollGrpId")
            land_area = parse_rai_ngan_wah(area_str)
            
            use_area = None
            try:
                if item.get("sumAreaNum"): use_area = float(item["sumAreaNum"])
            except Exception:
                pass
                
            bedroom = item.get("bedroomNum")
            bathroom = item.get("bathroomNum")
            publish_date = item.get("priceStrDt")

            record = {
                "บริษัท": COMPANY_NAME,
                "ID": p_id,
                "รหัสทรัพย์": p_code,
                "ชื่อโครงการ": proj_name,
                "ประเภททรัพย์": p_type,
                "ประเภทการขาย": "ทรัพย์ธนาคาร",
                "ราคา": price,
                "ตำบล": sub_d,
                "อำเภอ": dist,
                "จังหวัด": prov,
                "ละติจูด": lat,
                "ลองจิจูด": lng,
                "ชื่อประกาศ": title,
                "ลิงก์": link,
                "เนื้อที่ (ตร.ว.)": land_area,
                "พื้นที่ใช้สอย (ตร.ม.)": use_area,
                "วันที่ดึงข้อมูล": today_str,
                "ห้องนอน": bedroom if bedroom is not None and str(bedroom).isdigit() else None,
                "ห้องน้ำ": bathroom if bathroom is not None and str(bathroom).isdigit() else None,
                "ที่จอดรถ": None,
                "วันประกาศ": publish_date
            }
            records.append(record)

        progress_counter += 1
        pct = int(progress_counter * 100 / total_pages)
        elapsed = time.time() - start_time_global
        p_bar = make_progress_bar(pct, length=20)
        eta_str = format_eta(elapsed, progress_counter, total_pages)
        
        status_line = (
            f"[{COMPANY_NAME:<13s}] {p_bar} | "
            f"({progress_counter:4d}/{total_pages:4d} หน้า) | "
            f"สะสม: {len(records):7,d} รายการ | {eta_str}"
        )
        print(f"\r{status_line}", end="", flush=True)

        if page_no % 10 == 0 or page_no == total_pages:
            df = pd.DataFrame(records, columns=COLUMNS)
            df.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")

    print(f"\n[{COMPANY_NAME}] ✅ ดึงข้อมูลเสร็จสิ้น! บันทึกไฟล์ที่: {OUTPUT_CSV} รวม {len(records):,} รายการ", flush=True)

if __name__ == "__main__":
    main()
