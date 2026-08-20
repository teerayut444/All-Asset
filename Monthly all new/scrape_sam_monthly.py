import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
import os
import time
import random
from datetime import datetime
import concurrent.futures
import threading
import urllib3
import sys

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

COMPANY_NAME = "SAM"
MONTH_STR = datetime.now().strftime("%Y_%m")

_BASE_DIR = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(_BASE_DIR, "CSV_Output", MONTH_STR)
os.makedirs(OUTPUT_DIR, exist_ok=True)
OUTPUT_CSV = os.path.join(OUTPUT_DIR, f"SAM_NPA_New_{MONTH_STR}.csv")

THREAD_POOL_SIZE = 4

COLUMNS = [
    "บริษัท", "ID", "รหัสทรัพย์", "ชื่อโครงการ", "ประเภททรัพย์", "ประเภทการขาย", "ราคา",
    "ตำบล", "อำเภอ", "จังหวัด", "ละติจูด", "ลองจิจูด", "ชื่อประกาศ", "ลิงก์",
    "เนื้อที่ (ตร.ว.)", "พื้นที่ใช้สอย (ตร.ม.)", "วันที่ดึงข้อมูล",
    "ห้องนอน", "ห้องน้ำ", "ที่จอดรถ", "วันประกาศ"
]

print_lock = threading.Lock()
progress_counter = 0
start_time_global = None
failed_items = []

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

def check_link_health():
    url = "https://sam.or.th/site/npa/page_list.php"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {"layout": "list", "limit": "10000", "sort": "", "order": "", "page": "1"}
    for attempt in range(5):
        try:
            r = requests.post(url, headers=headers, data=data, timeout=30, verify=False)
            status_code = r.status_code
            if status_code == 200:
                soup = BeautifulSoup(r.text, 'html.parser')
                blogs = soup.find_all(class_='full_blog')
                total_items = len(blogs)
                return True, status_code, total_items, 1, blogs
        except Exception as e:
            time.sleep(2)
    return False, 0, 0, 0, []

def parse_property_detail(prop_id, html):
    soup = BeautifulSoup(html, 'html.parser')
    container = soup.find(class_='detail_sec01_detail') or soup.find(class_='detail_sec01') or soup
    container_text = re.sub(r'\s+', ' ', container.text).strip()
    
    code = ""
    m_code = re.search(r'รหัสทรัพย์สิน\s*:\s*([A-Za-z0-9\-_]+)', container_text)
    if m_code: code = m_code.group(1).strip()
    
    prop_type = ""
    m_type = re.search(r'ประเภททรัพย์สิน\s*:\s*([^:]+?)(?=\s*(?:เอกสารสิทธิ์|หนังสือ|จำนวน|เนื้อที่|ที่ตั้ง|ราคา|$))', container_text)
    if m_type:
        raw_ptype = m_type.group(1).strip()
        prop_type = re.sub(r'\s*ประเภท(?:เอกสารสิทธิ์)?.*$', '', raw_ptype).strip()
        
    price = None
    m_price = re.search(r'ราคาประกาศขาย\s*:\s*([\d,]+)', container_text)
    if m_price:
        price = float(m_price.group(1).replace(",", ""))
    else:
        btn_price = soup.find(class_='btn-price')
        if btn_price:
            m = re.search(r'([\d,]+)', btn_price.text)
            if m: price = float(m.group(1).replace(",", ""))
            
    sub_district, district, province, project_name = "", "", "", ""
    m_loc = re.search(r'ที่ตั้ง\s*:\s*(.*?)(?=\s*(?:เขตพื้นที่|ราคา|รายละเอียด|$))', container_text)
    loc_str = m_loc.group(1).strip() if m_loc else container_text
    
    m_sd = re.search(r'(?:ตำบล|ต\.|แขวง)\s*([^\s,]+)', loc_str)
    if m_sd: sub_district = m_sd.group(1).strip()
    
    m_d = re.search(r'(?:อำเภอ|อ\.|เขต)\s*([^\s,]+)', loc_str)
    if m_d: district = m_d.group(1).strip()
    
    m_p = re.search(r'(?:จังหวัด|จ\.)\s*([^\s,]+)', loc_str)
    if m_p: province = m_p.group(1).strip()
    
    m_proj = re.search(r'(?:หมู่บ้าน/โครงการ|โครงการ|หมู่บ้าน|อาคารชุด|คอนโด)\s*[:\s]*([^\n\r,]+?)(?=\s*(?:เลขที่|ถนน|ตำบล|แขวง|อำเภอ|เขต|จังหวัด|โซน|รายละเอียด|$))', loc_str)
    if m_proj:
        p_raw = m_proj.group(1).strip()
        p_clean = re.sub(r'^[/\s]+', '', p_raw).strip()
        if p_clean and p_clean.lower() not in ["none", "null", "-", "/", "โครงการ", "หมู่บ้าน/โครงการ", "หมู่บ้าน"]:
            project_name = p_clean
        
    lat, lng = None, None
    m_map = (
        re.search(r'google\.com/maps/(?:dir//|dir/|search/|@)?([\d\.-]+),([\d\.-]+)', html, re.I) or
        re.search(r'maps\.google\.com/[^"\'<>\s]*[?&](?:q|ll|query)=([\d\.-]+),([\d\.-]+)', html, re.I) or
        re.search(r'([\d]{1,2}\.[\d]{4,15})\s*,\s*([\d]{2,3}\.[\d]{4,15})', html)
    )
    if m_map:
        try:
            lat = float(m_map.group(1))
            lng = float(m_map.group(2))
        except Exception:
            pass
            
    # Compose clean, rich title
    loc_parts = [x for x in [sub_district, district, province] if x]
    loc_str_title = " ".join(loc_parts)
    
    if project_name:
        clean_title = f"{prop_type} {project_name} {loc_str_title}".strip()
    elif loc_str_title:
        clean_title = f"{prop_type} {loc_str_title}".strip()
    else:
        clean_title = f"{prop_type} SAM ({code or prop_id})".strip()
        
    if code and f"({code})" not in clean_title:
        clean_title = f"{clean_title} ({code})".strip()
    
    land_area = ""
    usable_area = ""
    
    m_area = re.search(r'(?:เนื้อที่|พื้นที่|ขนาดพื้นที่)\s*:\s*([^:]+?)(?=\s*(?:ห้องนอน|ห้องน้ำ|ที่ตั้ง|เขตพื้นที่|หน้ากว้าง|ราคา|$))', container_text)
    area_str = m_area.group(1).strip() if m_area else ""
    
    if re.search(r'ตร\.ม\.|ตารางเมตร', area_str):
        m_num = re.search(r'([\d\.,]+)\s*(?:ตร\.ม\.|ตารางเมตร)', area_str)
        if m_num:
            usable_area = m_num.group(1).replace(',', '').strip()
        else:
            usable_area = area_str
    elif area_str:
        # เก็บตามที่เว็บระบุโดยตรง เช่น "96.8 ตร.ว.", "1 งาน 12.0 ตร.ว.", "3 ไร่ 2 งาน 68.9 ตร.ว."
        clean_a = area_str.strip()
        clean_a = re.sub(r'(?<=\d|\s)(?:ตร\.วา|ตารางวา|วา)\b', 'ตร.ว.', clean_a)
        land_area = clean_a
            
    if not usable_area:
        m_u = re.search(r'พื้นที่ใช้สอย\s*:\s*([\d\.,]+)\s*(?:ตร\.ม\.|ตารางเมตร)?', container_text) or re.search(r'([\d\.,]+)\s*(?:ตร\.ม\.|ตารางเมตร)', container_text)
        if m_u:
            usable_area = m_u.group(1).replace(',', '').strip()
    
    beds, baths, parking = None, None, None
    bed_match = re.search(r'(\d+)\s*ห้องนอน', container_text)
    if bed_match: beds = int(bed_match.group(1))
    bath_match = re.search(r'(\d+)\s*ห้องน้ำ', container_text)
    if bath_match: baths = int(bath_match.group(1))
    park_match = re.search(r'(\d+)\s*ที่จอดรถ', container_text)
    if park_match: parking = int(park_match.group(1))
    
    m_post = re.search(r'(?:วันที่ประกาศ|วันที่สร้าง|ปีที่สร้าง|วันที่ปรับปรุง)\s*[:\s]*([^\n\r<"]+)', container_text)
    post_date = clean_text(m_post.group(1)) if m_post else ""
    
    return {
        "บริษัท": COMPANY_NAME,
        "รหัสทรัพย์": code,
        "ชื่อโครงการ": project_name,
        "ประเภททรัพย์": prop_type,
        "ราคา": price,
        "ตำบล": sub_district,
        "อำเภอ": district,
        "จังหวัด": province,
        "ละติจูด": lat,
        "ลองจิจูด": lng,
        "ชื่อประกาศ": clean_title,
        "เนื้อที่ (ตร.ว.)": convert_to_rai_ngan_wah(land_area),
        "พื้นที่ใช้สอย (ตร.ม.)": usable_area,
        "วันประกาศ": post_date,
        "ห้องนอน": beds,
        "ห้องน้ำ": baths,
        "ที่จอดรถ": parking
    }

def fetch_detail_worker(prop_item, total_count, results_list, saved_milestones):
    global progress_counter, start_time_global, failed_items
    url = prop_item["ลิงก์"]
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    html = ""
    for attempt in range(3):
        try:
            time.sleep(random.uniform(0.25, 0.55))
            r = requests.get(url, headers=headers, timeout=15, verify=False)
            if r.status_code == 200:
                html = r.content.decode('utf-8', errors='replace')
                break
        except Exception:
            time.sleep(1)
            
    if html:
        try:
            details = parse_property_detail(prop_item["ID"], html)
            prop_item.update(details)
            # รอประกาศราคา = ยังไม่มีราคา → ล้างราคาที่ดึงมาจาก HTML (เป็นราคาเก่า/cached)
            sale_type = str(prop_item.get("ประเภทการขาย") or "").strip()
            if "รอประกาศราคา" in sale_type:
                prop_item["ราคา"] = None
            with print_lock:
                results_list.append(prop_item)
        except Exception as e:
            with print_lock:
                failed_items.append(prop_item["ID"])
    else:
        with print_lock:
            failed_items.append(prop_item["ID"])
            
    with print_lock:
        progress_counter += 1
        current = progress_counter
        pct = int((current / total_count) * 100)
        elapsed_sec = time.time() - start_time_global if start_time_global else 1.0
        eta_msg = format_eta(elapsed_sec, current, total_count)
        pbar = make_progress_bar(pct)
        
        print(f"\r[{COMPANY_NAME:<13s}] {pbar} | ({current:5,d}/{total_count:5,d} รายการ) | สะสม: {len(results_list):>7,d} รายการ | {eta_msg}", end="", flush=True)
            
        if len(results_list) >= 10 and "initial_10" not in saved_milestones:
            saved_milestones.add("initial_10")
            print(f"\n💾 [{COMPANY_NAME}] ครบ 10 รายการแรก -> บันทึกไฟล์เริ่มต้นลง {OUTPUT_CSV}...", flush=True)
            save_to_csv(results_list, OUTPUT_CSV)

        for target_pct in [25, 50, 75, 100]:
            if pct >= target_pct and target_pct not in saved_milestones:
                saved_milestones.add(target_pct)
                print(f"\n💾 [{COMPANY_NAME}] ครบ Milestone {target_pct}% ({current}/{total_count}) -> บันทึกสำรองลง {OUTPUT_CSV}...", flush=True)
                save_to_csv(results_list, OUTPUT_CSV)

def save_to_csv(records, filename):
    try:
        df = pd.DataFrame(records)
        for col in COLUMNS:
            if col not in df.columns:
                df[col] = ""
        df = df[COLUMNS]
        for attempt in range(3):
            try:
                df.to_csv(filename, index=False, encoding="utf-8-sig")
                return True
            except PermissionError:
                if attempt < 2:
                    time.sleep(1)
                else:
                    alt_file = filename.replace(".csv", "_BACKUP.csv")
                    df.to_csv(alt_file, index=False, encoding="utf-8-sig")
                    print(f"\n⚠️ [FILE LOCKED] ไฟล์ {os.path.basename(filename)} ถูกเปิดล็อกไว้ใน Excel -> บันทึกข้อมูลสำรองไว้ที่ {os.path.basename(alt_file)} แทน", flush=True)
                    return True
        return True
    except Exception as e:
        print_alert(f"เกิดข้อผิดพลาดในการเซฟไฟล์ CSV '{filename}': {e}", level="CRITICAL")
        return False

def main():
    global start_time_global
    print(f"==================================================", flush=True)
    print(f"🚀 เริ่มต้นการ Scrape [{COMPANY_NAME}] (Monthly Mode: ดึงข้อมูลแม่นยำ 100%)", flush=True)
    print(f"📁 บันทึกข้อมูลลงไฟล์: {OUTPUT_CSV}", flush=True)
    print(f"==================================================", flush=True)
    
    existing_records, seen_ids = load_existing_csv(OUTPUT_CSV)
    
    is_ok, code, total_items, pages_count, blogs = check_link_health()
    if is_ok:
        status_msg = f"🌐 สถานะลิงก์: ปกติ (HTTP {code}) | ทั้งหมด 1 API List | {total_items:,} รายการรวม"
        print(f"[{COMPANY_NAME}] {status_msg}", flush=True)
    else:
        print_alert("ไม่สามารถดึงรายการทรัพย์สิน SAM ได้", level="CRITICAL")
        return
        
    if total_items > 0 and len(existing_records) >= total_items:
        print(f"[{COMPANY_NAME}] 🎉 ข้อมูลใน CSV ครบถ้วน 100% แล้ว ({len(existing_records):,}/{total_items:,} รายการ) -> สแครปเสร็จสมบูรณ์ทันที!", flush=True)
        save_to_csv(existing_records, OUTPUT_CSV)
        return
        
    scrape_date = datetime.now().strftime('%Y-%m-%d')
    base_properties = []
    
    for blog in blogs:
        img_div = blog.find(class_='card-img')
        onclick = img_div.get('onclick') if img_div else ""
        id_match = re.search(r'gotoDetail\((\d+)\)', onclick)
        prop_id = id_match.group(1) if id_match else None
        if not prop_id: continue
        
        iid_str = str(prop_id).strip()
        if iid_str in seen_ids:
            continue
            
        status_span = blog.find(class_=re.compile("icon_status"))
        sale_type = status_span.text.strip() if status_span else "ขาย"
        detail_link = f"https://sam.or.th/site/npa/detail.php?id={prop_id}&keyref="
        
        base_properties.append({
            "บริษัท": COMPANY_NAME,
            "ID": prop_id,
            "รหัสทรัพย์": "",
            "ชื่อโครงการ": "",
            "ประเภททรัพย์": "",
            "ประเภทการขาย": sale_type,
            "ราคา": None,
            "ตำบล": "",
            "อำเภอ": "",
            "จังหวัด": "",
            "ละติจูด": None,
            "ลองจิจูด": None,
            "ชื่อประกาศ": "",
            "ลิงก์": detail_link,
            "เนื้อที่ (ตร.ว.)": convert_to_rai_ngan_wah(""),
            "พื้นที่ใช้สอย (ตร.ม.)": "",
            "วันที่ดึงข้อมูล": scrape_date,
            "ห้องนอน": None,
            "ห้องน้ำ": None,
            "ที่จอดรถ": None
        })
        
    base_properties.reverse()
    total_new_needed = len(base_properties)
    
    if total_new_needed == 0:
        print(f"[{COMPANY_NAME}] ✅ ข้อมูลทุกรายการถูกดึงครบถ้วนแล้วใน {OUTPUT_CSV} (ไม่มีรายการใหม่)", flush=True)
        return
        
    print(f"[{COMPANY_NAME}] กำลังสแครปรายละเอียดทรัพย์สินใหม่ {total_new_needed:,} รายการ (ข้ามรายการเดิม {len(existing_records):,} รายการ)...", flush=True)
    start_time_global = time.time()
    
    results_list = list(existing_records)
    saved_milestones = set()
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=THREAD_POOL_SIZE) as executor:
        futures = [
            executor.submit(fetch_detail_worker, prop, total_new_needed, results_list, saved_milestones)
            for prop in base_properties
        ]
        concurrent.futures.wait(futures)
        
    print("", flush=True)
    save_to_csv(results_list, OUTPUT_CSV)
    elapsed = time.time() - start_time_global
    print(f"\n==================================================", flush=True)
    print(f"✅ [{COMPANY_NAME}] สแครปเสร็จสมบูรณ์!", flush=True)
    print(f"📊 ได้ข้อมูลทั้งหมด: {len(results_list):,} รายการ (เพิ่มใหม่รอบนี้: {total_new_needed:,} รายการ)", flush=True)
    print(f"⏱️ ใช้เวลาทั้งหมด: {elapsed/60:.2f} นาที", flush=True)
    print(f"💾 ไฟล์ CSV: {OUTPUT_CSV}", flush=True)
    if failed_items:
        print(f"⚠️ รายการรายละเอียดที่ข้าม/ดึงไม่ได้ ({len(failed_items)} รายการ): {failed_items[:20]}...", flush=True)
    else:
        print(f"✅ ดึงข้อมูลได้ครบถ้วนสำเร็จทุกรายการ (ไม่มีรายการล้มเหลว)", flush=True)
    print(f"==================================================", flush=True)

if __name__ == "__main__":
    main()
