from curl_cffi import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
import os
import time
from datetime import datetime
import concurrent.futures
import threading
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

COMPANY_NAME = "GHB"
MONTH_STR = datetime.now().strftime("%Y_%m")

_BASE_DIR = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(_BASE_DIR, "CSV_Output")
os.makedirs(OUTPUT_DIR, exist_ok=True)
OUTPUT_CSV = os.path.join(OUTPUT_DIR, f"GHB_NPA_New_{MONTH_STR}.csv")

THREAD_POOL_SIZE = 8

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
    session = requests.Session(impersonate="chrome120")
    url = "https://www.ghbhomecenter.com/property-for-sale"
    for attempt in range(5):
        try:
            r = session.get(url, timeout=15)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, 'html.parser')
                page_links = [a.get_text().strip() for a in soup.find_all('a', class_='page-link')]
                p_nums = [int(p) for p in page_links if p.isdigit()]
                total_pages = max(p_nums) if p_nums else 1511
                
                total_items = total_pages * 20
                m_items = re.search(r'ค้นพบทรัพย์\s*([\d,]+)\s*รายการ', r.text)
                if m_items:
                    total_items = int(m_items.group(1).replace(",", ""))
                    total_pages = (total_items + 19) // 20
                return True, r.status_code, total_items, total_pages
        except Exception:
            time.sleep(2)
    return False, 0, 0, 0

def fetch_page_records(page_no, today_str):
    url = f"https://www.ghbhomecenter.com/property-for-sale?pg={page_no}"
    session = requests.Session(impersonate="chrome120")
    for attempt in range(3):
        try:
            r = session.get(url, timeout=15)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, 'html.parser')
                cards = soup.find_all('div', class_='card d-block')
                page_records = []
                for c in cards:
                    a_link = c.find('a', href=re.compile(r'/property-\d+'))
                    link = a_link.get('href') if a_link else ""
                    if link and not link.startswith('http'):
                        link = f"https://www.ghbhomecenter.com{link}"
                    m_id = re.search(r'/property-(\d+)', link)
                    p_id = m_id.group(1) if m_id else ""
                    if not p_id:
                        continue
                    
                    price = None
                    price_div = c.find(class_='text-propertyprice')
                    if price_div:
                        m_p = re.search(r'([\d,]+)', price_div.text)
                        if m_p:
                            try: price = float(m_p.group(1).replace(",", ""))
                            except Exception: pass
                            
                    header_div = c.find(class_='text-header-titletype')
                    title_raw = clean_text(header_div.get_text()) if header_div else ""
                    
                    p_type = ""
                    proj_name = ""
                    m_pt = re.search(r'ขาย\s*([^\(\s]+)', title_raw)
                    if m_pt: p_type = clean_text(m_pt.group(1))
                    m_proj = re.search(r'\((.*?)\)', title_raw)
                    if m_proj: proj_name = clean_text(m_proj.group(1))
                    
                    sub_d, dist, prov = "", "", ""
                    loc_div = c.find(class_='text-location')
                    if loc_div:
                        loc_text = clean_text(loc_div.get_text())
                        parts = [p.strip() for p in loc_text.split(',') if p.strip()]
                        if len(parts) == 3:
                            sub_d, dist, prov = parts[0], parts[1], parts[2]
                        elif len(parts) == 2:
                            dist, prov = parts[0], parts[1]
                        elif len(parts) == 1:
                            prov = parts[0]
                            
                    land_area, use_area = None, None
                    area_div = c.find(class_='text-area')
                    if area_div:
                        area_text = area_div.get_text()
                        m_sqm = re.search(r'([\d\.]+)\s*(?:ตร\.ม\.|ตารางเมตร)', area_text)
                        if m_sqm:
                            try: use_area = float(m_sqm.group(1))
                            except Exception: pass
                        m_sqw = re.search(r'([\d\.]+)\s*(?:ตร\.ว\.|ตารางวา)', area_text)
                        if m_sqw:
                            try: land_area = float(m_sqw.group(1))
                            except Exception: pass
                            
                    code = p_id
                    card_text = c.get_text()
                    m_code = re.search(r'รหัสทรัพย์\s*[:\s]*(\d+)', card_text)
                    if m_code: code = m_code.group(1).strip()
                    
                    tag_div = c.find(class_='card-tag')
                    sale_type = clean_text(tag_div.get_text()) if tag_div else "ทรัพย์ธนาคาร"
                    if not sale_type:
                        sale_type = "ทรัพย์ธนาคาร"

                    record = {
                        "บริษัท": COMPANY_NAME,
                        "ID": p_id,
                        "รหัสทรัพย์": code,
                        "ชื่อโครงการ": proj_name,
                        "ประเภททรัพย์": p_type,
                        "ประเภทการขาย": sale_type,
                        "ราคา": price,
                        "ตำบล": sub_d,
                        "อำเภอ": dist,
                        "จังหวัด": prov,
                        "ละติจูด": None,
                        "ลองจิจูด": None,
                        "ชื่อประกาศ": title_raw,
                        "ลิงก์": link,
                        "เนื้อที่ (ตร.ว.)": land_area,
                        "พื้นที่ใช้สอย (ตร.ม.)": use_area,
                        "วันที่ดึงข้อมูล": today_str,
                        "ห้องนอน": None,
                        "ห้องน้ำ": None,
                        "ที่จอดรถ": None,
                        "วันประกาศ": None
                    }
                    page_records.append(record)
                return page_records
        except Exception:
            time.sleep(1.5)
    return []

def main():
    global start_time_global, progress_counter
    print(f"[{COMPANY_NAME}] 🚀 เริ่มต้นการดึงข้อมูลประจำเดือน {MONTH_STR}", flush=True)
    
    healthy, code, total_items, total_pages = check_link_health()
    if not healthy:
        print_alert(f"ไม่สามารถเชื่อมต่อ GHB Web ได้ (HTTP Status: {code})", level="CRITICAL")
        return

    print(f"[{COMPANY_NAME}] 🌐 ตรวจสอบสถานะลิงก์ปลายทาง: HTTP {code} OK! พบทั้งหมด ~{total_items:,} รายการ ({total_pages:,} หน้า)", flush=True)

    records, seen_ids = load_existing_csv(OUTPUT_CSV)
    
    start_time_global = time.time()
    progress_counter = 0
    today_str = datetime.now().strftime("%Y-%m-%d")

    with concurrent.futures.ThreadPoolExecutor(max_workers=THREAD_POOL_SIZE) as executor:
        futures = {executor.submit(fetch_page_records, p, today_str): p for p in range(1, total_pages + 1)}
        for future in concurrent.futures.as_completed(futures):
            p_no = futures[future]
            try:
                res_list = future.result()
                if res_list:
                    with print_lock:
                        for item in res_list:
                            iid = item.get("ID")
                            if iid and iid not in seen_ids:
                                seen_ids.add(iid)
                                records.append(item)
            except Exception:
                pass
                
            with print_lock:
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

                if progress_counter % 25 == 0 or progress_counter == total_pages:
                    df = pd.DataFrame(records, columns=COLUMNS)
                    df.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")

    df = pd.DataFrame(records, columns=COLUMNS)
    df.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")
    print(f"\n[{COMPANY_NAME}] ✅ ดึงข้อมูลเสร็จสิ้น! บันทึกไฟล์ที่: {OUTPUT_CSV} รวม {len(records):,} รายการ", flush=True)

if __name__ == "__main__":
    main()
