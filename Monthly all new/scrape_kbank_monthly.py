from curl_cffi import requests
import pandas as pd
import re
import os
import json
import time
import random
from datetime import datetime
import threading
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

COMPANY_NAME = "KBANK"
MONTH_STR = datetime.now().strftime("%Y_%m")

_BASE_DIR = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(_BASE_DIR, "CSV_Output", MONTH_STR)
os.makedirs(OUTPUT_DIR, exist_ok=True)
OUTPUT_CSV = os.path.join(OUTPUT_DIR, f"KBANK_NPA_New_{MONTH_STR}.csv")

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

def parse_rai_ngan_wah_robust(s):
    if s is None or pd.isna(s):
        return None, None, None
    s = str(s).strip()
    if not s or s.lower() in ["nan", "none", "null", "$undefined", "-", "0", "0.0"]:
        return None, None, None
    m_dash = re.match(r'^(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)$', s)
    if m_dash:
        return float(m_dash.group(1)), float(m_dash.group(2)), float(m_dash.group(3))
    has_thai_units = any(u in s for u in ['ไร่', 'งาน', 'วา', 'ตร.ว', 'ตารางวา', 'ตร.ว.'])
    if has_thai_units:
        m_r = re.search(r'([\d\.,]+)\s*ไร่', s)
        m_g = re.search(r'([\d\.,]+)\s*งาน', s)
        m_w = re.search(r'([\d\.,]+)\s*(?:ตร\.?ว\.?|ตารางวา|วา)', s)
        r = float(m_r.group(1).replace(',', '')) if m_r else 0.0
        g = float(m_g.group(1).replace(',', '')) if m_g else 0.0
        w = float(m_w.group(1).replace(',', '')) if m_w else 0.0
        if r > 0 or g > 0 or w > 0:
            return r, g, w
    clean_num = re.sub(r'[^\d\.]', '', s)
    if clean_num:
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

def solve_akamai_challenge(session, resp):
    if "triggerInterstitialChallenge" in resp.text:
        m_i = re.search(r'var i = (\d+);', resp.text)
        m_num = re.search(r'Number\(["\'](\d+)["\'] \+ ["\'](\d+)["\']\)', resp.text)
        m_bm = re.search(r'["\']bm-verify["\']:\s*["\']([^"\']+)["\']', resp.text)
        if m_i and m_num and m_bm:
            i_val = int(m_i.group(1))
            num_val = int(m_num.group(1) + m_num.group(2))
            pow_val = i_val + num_val
            bm_verify = m_bm.group(1)
            session.post(
                "https://www.kasikornbank.com/_sec/verify?provider=interstitial", 
                json={"bm-verify": bm_verify, "pow": pow_val}, 
                headers={"Content-Type": "application/json", "Referer": resp.url}, 
                timeout=10
            )

def init_kbank_session():
    session = requests.Session(impersonate="chrome120")
    for attempt in range(3):
        try:
            r = session.get("https://www.kasikornbank.com/th/propertyforsale/search/pages/index.aspx", timeout=15)
            solve_akamai_challenge(session, r)
            r2 = session.get("https://www.kasikornbank.com/th/propertyforsale/search/pages/index.aspx", timeout=15)
            if r2.status_code == 200:
                return session
        except Exception:
            time.sleep(2)
    return session

def check_link_health(session):
    api_url = "https://www.kasikornbank.com/Custom/KWEB2020/NPA2023Backend13.aspx/GetProperties"
    payload = {
        "filter": {
            "AllCurrentPageIndex": 1,
            "CurrentPageIndex": 1,
            "PageSize": PAGE_LIMIT,
            "SearchPurposes": ["AllProperties"],
            "propertyList": "AllProperties"
        }
    }
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": "https://www.kasikornbank.com/th/propertyforsale/search/pages/index.aspx"
    }
    for attempt in range(5):
        try:
            r = session.post(api_url, json=payload, headers=headers, timeout=15)
            if "triggerInterstitialChallenge" in r.text:
                solve_akamai_challenge(session, r)
                r = session.post(api_url, json=payload, headers=headers, timeout=15)
            if r.status_code == 200:
                data = r.json()
                d_str = data.get("d")
                if isinstance(d_str, str):
                    parsed = json.loads(d_str)
                    data_block = parsed.get("Data", {})
                    total_items = data_block.get("TotalRows") or 0
                    total_pages = (total_items + PAGE_LIMIT - 1) // PAGE_LIMIT if total_items > 0 else 1
                    return True, r.status_code, total_items, total_pages
        except Exception:
            time.sleep(2)
    return False, 0, 0, 0

def fetch_page(page_no, session):
    api_url = "https://www.kasikornbank.com/Custom/KWEB2020/NPA2023Backend13.aspx/GetProperties"
    payload = {
        "filter": {
            "AllCurrentPageIndex": page_no,
            "CurrentPageIndex": page_no,
            "PageSize": PAGE_LIMIT,
            "SearchPurposes": ["AllProperties"],
            "propertyList": "AllProperties"
        }
    }
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": "https://www.kasikornbank.com/th/propertyforsale/search/pages/index.aspx"
    }
    for attempt in range(3):
        try:
            r = session.post(api_url, json=payload, headers=headers, timeout=15)
            if "triggerInterstitialChallenge" in r.text:
                solve_akamai_challenge(session, r)
                r = session.post(api_url, json=payload, headers=headers, timeout=15)
            if r.status_code == 200:
                data = r.json()
                d_str = data.get("d")
                if isinstance(d_str, str):
                    parsed = json.loads(d_str)
                    return parsed.get("Data", {}).get("Items", [])
        except Exception:
            time.sleep(1.5)
    return []

def main():
    global start_time_global, progress_counter
    print(f"[{COMPANY_NAME}] 🚀 เริ่มต้นการดึงข้อมูลประจำเดือน {MONTH_STR}", flush=True)
    
    session = init_kbank_session()
    healthy, code, total_items, total_pages = check_link_health(session)
    if not healthy:
        print_alert(f"ไม่สามารถเชื่อมต่อ KBANK API ได้ (HTTP Status: {code})", level="CRITICAL")
        return

    print(f"[{COMPANY_NAME}] 🌐 ตรวจสอบสถานะลิงก์ปลายทาง: HTTP {code} OK! พบทั้งหมด ~{total_items:,} รายการ ({total_pages:,} หน้า)", flush=True)

    records, seen_ids = load_existing_csv(OUTPUT_CSV)
    
    start_time_global = time.time()
    progress_counter = 0
    today_str = datetime.now().strftime("%Y-%m-%d")

    for page_no in range(1, total_pages + 1):
        items = fetch_page(page_no, session)
        new_page_count = 0
        for item in items:
            p_id = str(item.get("PropertyID") or "").strip()
            if not p_id or p_id in seen_ids:
                continue
            
            seen_ids.add(p_id)
            new_page_count += 1
            
            p_code = clean_text(item.get("PropertyIDFormat") or p_id)
            raw_type = clean_text(item.get("PropertyTypeName") or "")
            p_type = clean_text(re.sub(r'^\d+\s*', '', raw_type))
            
            proj_name = clean_text(item.get("VillageTH") or item.get("BuildingTH") or "").replace("-", "").strip()
            
            price = None
            try:
                if item.get("SellPrice") is not None:
                    price = float(item["SellPrice"])
            except Exception:
                pass
                
            sub_d = clean_text(item.get("TambonName") or "")
            dist = clean_text(item.get("AmphurName") or "")
            prov = clean_text(item.get("ProvinceName") or "")
            
            lat = None
            lng = None
            try:
                if item.get("Latitude"): lat = float(item["Latitude"])
                if item.get("Longtitude"): lng = float(item["Longtitude"])
            except Exception:
                pass
                
            link = f"https://www.kasikornbank.com/th/propertyforsale/detail/{p_id}.html"
            
            title = f"{p_type} {proj_name} {sub_d} {dist} {prov}".strip()
            
            land_area = None
            try:
                if item.get("AreaValue") is not None:
                    land_area = float(item["AreaValue"])
            except Exception:
                pass
                
            use_area = None
            try:
                if item.get("UseableArea") is not None:
                    use_area = float(item["UseableArea"])
            except Exception:
                pass
                
            bedroom = item.get("Bedroom")
            bathroom = item.get("Bathroom")
            
            sale_type = "ทรัพย์ธนาคาร"
            if str(item.get("SourceCode")) == "66":
                sale_type = "ทรัพย์ฝากขาย"

            record = {
                "บริษัท": COMPANY_NAME,
                "ID": p_id,
                "รหัสทรัพย์": p_code,
                "ชื่อโครงการ": proj_name,
                "ประเภททรัพย์": p_type,
                "ประเภทการขาย": sale_type,
                "ราคา": price,
                "ตำบล": sub_d,
                "อำเภอ": dist,
                "จังหวัด": prov,
                "ละติจูด": lat,
                "ลองจิจูด": lng,
                "ชื่อประกาศ": title,
                "ลิงก์": link,
                "เนื้อที่ (ตร.ว.)": convert_to_rai_ngan_wah(land_area),
                "พื้นที่ใช้สอย (ตร.ม.)": use_area,
                "วันที่ดึงข้อมูล": today_str,
                "ห้องนอน": bedroom if bedroom is not None and str(bedroom).isdigit() and int(bedroom) > 0 else None,
                "ห้องน้ำ": bathroom if bathroom is not None and str(bathroom).isdigit() and int(bathroom) > 0 else None,
                "ที่จอดรถ": None,
                "วันประกาศ": None
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

        time.sleep(random.uniform(1.2, 2.0))

    print(f"\n[{COMPANY_NAME}] ✅ ดึงข้อมูลเสร็จสิ้น! บันทึกไฟล์ที่: {OUTPUT_CSV} รวม {len(records):,} รายการ", flush=True)

if __name__ == "__main__":
    main()
