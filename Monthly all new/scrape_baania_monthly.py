import requests
import json
import re
import os
import sys
import time
import random
from datetime import datetime
import pandas as pd

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

COMPANY_NAME = "Baania"
MONTH_STR = datetime.now().strftime("%Y_%m")

_BASE_DIR = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(_BASE_DIR, "CSV_Output")
os.makedirs(OUTPUT_DIR, exist_ok=True)
OUTPUT_CSV = os.path.join(OUTPUT_DIR, f"Baania_NPA_New_{MONTH_STR}.csv")

BASE_URL = "https://www.baania.com/s/%E0%B8%97%E0%B8%B1%E0%B9%89%E0%B8%87%E0%B8%AB%E0%B8%A1%E0%B8%94/listing?sellState=on-sale,sale-rent&sort.created=asc"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
    'Accept-Language': 'th-TH,th;q=0.9,en-US;q=0.8,en;q=0.7',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Connection': 'keep-alive'
}

COLUMNS = [
    "บริษัท", "ID", "รหัสทรัพย์", "ชื่อโครงการ", "ประเภททรัพย์", "ประเภทการขาย", "ราคา",
    "ตำบล", "อำเภอ", "จังหวัด", "ละติจูด", "ลองจิจูด", "ชื่อประกาศ", "ลิงก์",
    "เนื้อที่ (ตร.ว.)", "พื้นที่ใช้สอย (ตร.ม.)", "วันที่ดึงข้อมูล",
    "ห้องนอน", "ห้องน้ำ", "ที่จอดรถ", "วันประกาศ"
]

ITEMS_PER_PAGE = 48

def print_alert(msg: str, level: str = "ERROR"):
    border = "=" * 75
    if level == "CRITICAL":
        icon = "🚨 [CRITICAL ALERT]"
    elif level == "WARNING":
        icon = "⚠️ [WARNING ALERT]"
    else:
        icon = "❌ [ERROR ALERT]"
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

def clean_text(val):
    if val is None:
        return ""
    s = str(val)
    return re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F-\x9F]', '', s).strip()

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

def parse_land_area(area_total):
    if not isinstance(area_total, dict):
        return ""
    rai = area_total.get("rai")
    ngan = area_total.get("ngan")
    wa = area_total.get("wa")
    parts = []
    if rai: parts.append(f"{rai} ไร่")
    if ngan: parts.append(f"{ngan} งาน")
    if wa: parts.append(f"{wa} ตร.ว.")
    return " ".join(parts)

def parse_sell_state(vd):
    st = str(vd.get("sell_state", "")).lower()
    lt = str(vd.get("listing_type", "")).lower()
    if "sale-rent" in st or "sale-rent" in lt: return "ขาย/เช่า"
    if "rent" in lt or "rent" in st: return "เช่า"
    if "on-sale" in st or "for-sale" in lt or "sale" in st: return "ขาย"
    return vd.get("sell_state") or vd.get("listing_type") or ""

def parse_property_type(vd):
    pt_list = vd.get("property_type", [])
    if isinstance(pt_list, list):
        names = []
        for pt in pt_list:
            if isinstance(pt, dict) and pt.get("th"): names.append(pt.get("th"))
            elif isinstance(pt, str): names.append(pt)
        return ", ".join(names)
    return ""

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

def check_link_health(session):
    url = f"{BASE_URL}&page=1"
    for attempt in range(5):
        try:
            res = session.get(url, timeout=25)
            status_code = res.status_code
            if status_code == 200:
                match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', res.text)
                if match:
                    data = json.loads(match.group(1))
                    hits = (((data.get("props") or {}).get("pageProps") or {}).get("defaultData") or {}).get("hits") or {}
                    tot = hits.get("total")
                    total_val = 0
                    if isinstance(tot, dict):
                        total_val = tot.get("value", 0)
                    elif isinstance(tot, (int, float)):
                        total_val = int(tot)
                    pages = total_val // ITEMS_PER_PAGE if total_val > 0 else 1
                    total_val = pages * ITEMS_PER_PAGE
                    return True, status_code, total_val, pages
        except Exception as e:
            time.sleep(2 + attempt)
    return False, 0, 0, 0

def fetch_page_items(session, page_num):
    url = f"{BASE_URL}&page={page_num}"
    max_retries = 5
    for attempt in range(max_retries):
        try:
            res = session.get(url, timeout=25)
            if res.status_code == 404:
                return None
            if res.status_code == 429 or res.status_code == 503:
                sleep_time = (2 ** attempt) + random.uniform(1.0, 3.0)
                print_alert(f"HTTP Status {res.status_code} (Rate Limit/Busy) ในหน้า {page_num} -> พักรอ {sleep_time:.1f} วินาที", level="WARNING")
                time.sleep(sleep_time)
                continue
            if res.status_code != 200:
                print_alert(f"HTTP Status {res.status_code} ในหน้า {page_num} (พยายามที่ {attempt+1}/{max_retries})", level="WARNING")
                time.sleep(2 + attempt)
                continue
            
            match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', res.text)
            if not match:
                return []
            
            data = json.loads(match.group(1))
            hits = ((((data.get("props") or {}).get("pageProps") or {}).get("defaultData") or {}).get("hits") or {}).get("hits") or []
            records = []
            scrape_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            for item in hits:
                src = item.get("_source", {})
                vd = src.get("view_data", {})
                addr = src.get("address", {})
                loc = src.get("location", {})
                
                item_id = clean_text(item.get("_id") or vd.get("pkid") or vd.get("keyId") or "")
                code = clean_text(vd.get("code") or "")
                if code in ["None", "null"]: code = ""
                
                proj_title = vd.get("project_title")
                proj_name = clean_text(proj_title.get("th") if isinstance(proj_title, dict) else str(proj_title or ""))
                
                title_obj = vd.get("title")
                title_th = clean_text(title_obj.get("th") if isinstance(title_obj, dict) else str(title_obj or ""))
                
                price = vd.get("price_start") or vd.get("price_rent")
                
                subdist = clean_text(((addr.get("subdistrict") or {}).get("title") or {}).get("th") or "" if isinstance(addr.get("subdistrict"), dict) else "")
                dist = clean_text(((addr.get("district") or {}).get("title") or {}).get("th") or "" if isinstance(addr.get("district"), dict) else "")
                prov = clean_text(((addr.get("province") or {}).get("title") or {}).get("th") or "" if isinstance(addr.get("province"), dict) else "")
                
                link = f"https://www.baania.com/th/listing/{item_id}" if item_id else ""
                
                record = {
                    "บริษัท": COMPANY_NAME,
                    "ID": item_id,
                    "รหัสทรัพย์": code,
                    "ชื่อโครงการ": proj_name,
                    "ประเภททรัพย์": clean_text(parse_property_type(vd)),
                    "ประเภทการขาย": clean_text(parse_sell_state(vd)),
                    "ราคา": price,
                    "ตำบล": subdist,
                    "อำเภอ": dist,
                    "จังหวัด": prov,
                    "ละติจูด": loc.get("lat") if isinstance(loc, dict) else None,
                    "ลองจิจูด": loc.get("lon") if isinstance(loc, dict) else None,
                    "ชื่อประกาศ": title_th,
                    "ลิงก์": link,
                    "เนื้อที่ (ตร.ว.)": convert_to_rai_ngan_wah(clean_text(parse_land_area(vd.get("area_total")))),
                    "พื้นที่ใช้สอย (ตร.ม.)": vd.get("area_usable"),
                    "วันที่ดึงข้อมูล": scrape_time,
                    "วันประกาศ": clean_text(vd.get("created_at") or vd.get("published_at") or vd.get("updated_at") or ""),
                    "ห้องนอน": vd.get("bedroom"),
                    "ห้องน้ำ": vd.get("bathroom"),
                    "ที่จอดรถ": vd.get("parking")
                }
                records.append(record)
            return records
        except Exception as e:
            sleep_time = (2 ** attempt) + random.uniform(0.5, 2.0)
            print_alert(f"เกิดข้อผิดพลาดในการดึงข้อมูลหน้า {page_num} (พยายามที่ {attempt+1}/{max_retries}): {e} -> พัก {sleep_time:.1f} วินาที", level="WARNING")
            time.sleep(sleep_time)
    return None

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
    print(f"==================================================", flush=True)
    print(f"🚀 เริ่มต้นการ Scrape [{COMPANY_NAME}] (Monthly Mode)", flush=True)
    print(f"📁 บันทึกข้อมูลลงไฟล์: {OUTPUT_CSV}", flush=True)
    print(f"==================================================", flush=True)
    
    session = requests.Session()
    session.headers.update(HEADERS)
    
    all_records, seen_ids = load_existing_csv(OUTPUT_CSV)
    
    is_ok, code, total_items, total_pages = check_link_health(session)
    if is_ok:
        calc_total = total_pages * ITEMS_PER_PAGE
        status_msg = f"🌐 สถานะลิงก์: ปกติ (HTTP {code}) | ทั้งหมด {total_pages:,} หน้า | {ITEMS_PER_PAGE} รายการ/หน้า ({calc_total:,} รายการ)"
        print(f"[{COMPANY_NAME}] {status_msg}", flush=True)
    else:
        print_alert("ไม่สามารถเชื่อมต่อเว็บ Baania ได้", level="CRITICAL")
        return
        
    if calc_total > 0 and len(all_records) >= (calc_total - 100):
        print(f"[{COMPANY_NAME}] 🎉 ข้อมูลใน CSV ครบถ้วน 100% แล้ว ({len(all_records):,}/{calc_total:,} รายการ) -> สแครปเสร็จสมบูรณ์ทันที!", flush=True)
        save_to_csv(all_records, OUTPUT_CSV)
        return
    
    saved_milestones = set()
    failed_pages = []
    
    start_time = time.time()
    new_added = 0
    
    completed_pages = min(total_pages - 1, len(all_records) // ITEMS_PER_PAGE)
    start_page = completed_pages + 1
    if completed_pages > 0:
        print(f"[{COMPANY_NAME}] ⏩ Fast-Forward Resume: ข้าม {completed_pages:,} หน้าแรกที่เคยดึงแล้ว -> เริ่มสแครปหน้า {start_page:,} ต่อทันที", flush=True)
    
    for page in range(start_page, total_pages + 1):
        if total_items > 0 and len(all_records) >= total_items:
            print(f"\n[{COMPANY_NAME}] 🎉 สะสมข้อมูลครบถ้วนทั้งหมดแล้ว ({len(all_records):,}/{total_items:,} รายการ) -> สิ้นสุดการสแครป!", flush=True)
            break
        items = fetch_page_items(session, page)
        if items is None:
            failed_pages.append(page)
            print(f"\n[{COMPANY_NAME}] ⚠️ ข้ามหน้า {page} เนื่องจากดึงข้อมูลไม่สำเร็จหลังจากลองหลายครั้ง", flush=True)
            continue
            
        if not items and page > 20 and len(all_records) > 0:
            print(f"\n[{COMPANY_NAME}] ไม่พบข้อมูลในหน้า {page} จบการดึงข้อมูล", flush=True)
            break
            
        page_added = 0
        for item in items:
            iid = str(item["ID"]).strip()
            if iid and iid in seen_ids:
                continue
            if iid:
                seen_ids.add(iid)
            all_records.append(item)
            page_added += 1
            new_added += 1
            
        pct = int((page / total_pages) * 100)
        elapsed_sec = time.time() - start_time
        eta_msg = format_eta(elapsed_sec, page, total_pages)
        pbar = make_progress_bar(pct)
        
        print(f"\r[{COMPANY_NAME:<13s}] {pbar} | ({page:5,d}/{total_pages:5,d} หน้า) | สะสม: {len(all_records):>7,d} รายการ | {eta_msg}", end="", flush=True)
        
        if len(all_records) >= 10 and "initial_10" not in saved_milestones:
            saved_milestones.add("initial_10")
            print(f"\n💾 [{COMPANY_NAME}] ครบ 10 รายการแรก -> บันทึกไฟล์เริ่มต้นลง {OUTPUT_CSV}...", flush=True)
            save_to_csv(all_records, OUTPUT_CSV)

        for target_pct in [25, 50, 75, 100]:
            if pct >= target_pct and target_pct not in saved_milestones:
                saved_milestones.add(target_pct)
                print(f"\n💾 [{COMPANY_NAME}] ครบ Milestone {target_pct}% ({page}/{total_pages} หน้า) -> บันทึกสำรองลง {OUTPUT_CSV}...", flush=True)
                save_to_csv(all_records, OUTPUT_CSV)
                
        time.sleep(0.7 + random.uniform(0.1, 0.4))
        
    print("", flush=True)
    save_to_csv(all_records, OUTPUT_CSV)
    elapsed = time.time() - start_time
    print(f"\n==================================================", flush=True)
    print(f"✅ [{COMPANY_NAME}] สแครปเสร็จสมบูรณ์!", flush=True)
    print(f"📊 ได้ข้อมูลทั้งหมด: {len(all_records):,} รายการ (เพิ่มใหม่ในรอบนี้: {new_added:,} รายการ)", flush=True)
    print(f"⏱️ ใช้เวลาทั้งหมด: {elapsed/60:.2f} นาที", flush=True)
    print(f"💾 ไฟล์ CSV: {OUTPUT_CSV}", flush=True)
    if failed_pages:
        print(f"⚠️ รายการหน้าที่ข้าม/ดึงไม่ได้ ({len(failed_pages)} หน้า): {failed_pages}", flush=True)
    else:
        print(f"✅ ดึงข้อมูลได้ครบถ้วนสำเร็จทุกหน้า (ไม่มีหน้าล้มเหลว)", flush=True)
    print(f"==================================================", flush=True)

if __name__ == "__main__":
    main()
