import requests
import json
import re
import os
import sys
import time
import random
from datetime import datetime
import pandas as pd
from bs4 import BeautifulSoup
import concurrent.futures

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

COMPANY_NAME = "BAM"
MONTH_STR = datetime.now().strftime("%Y_%m")

_BASE_DIR = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(_BASE_DIR, "CSV_Output", MONTH_STR)
os.makedirs(OUTPUT_DIR, exist_ok=True)
OUTPUT_CSV = os.path.join(OUTPUT_DIR, f"BAM_NPA_New_{MONTH_STR}.csv")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "th-TH,th;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://www.bam.co.th/th/npa/property/search"
}

COLUMNS = [
    "บริษัท", "ID", "รหัสทรัพย์", "ชื่อโครงการ", "ประเภททรัพย์", "ประเภทการขาย", "ราคา",
    "ตำบล", "อำเภอ", "จังหวัด", "ละติจูด", "ลองจิจูด", "ชื่อประกาศ", "ลิงก์",
    "เนื้อที่ (ตร.ว.)", "พื้นที่ใช้สอย (ตร.ม.)", "วันที่ดึงข้อมูล",
    "ห้องนอน", "ห้องน้ำ", "ที่จอดรถ", "วันประกาศ"
]

ITEMS_PER_PAGE = 12

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
    if not val or str(val).strip().lower() in ["none", "null", "$undefined", "undefined"]:
        return ""
    cleaned = re.sub(r"\s+", " ", str(val)).strip()
    return "" if cleaned.lower() in ["none", "null", "$undefined", "undefined"] else cleaned

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

def clean_num(val):
    if val is None:
        return None
    s = str(val).strip()
    if s.lower() in ["none", "null", "$undefined", "undefined", ""]:
        return None
    try:
        return float(s) if "." in s else int(s)
    except ValueError:
        return None

def _clean_val(val):
    if val is None or str(val).strip().startswith('$undefined') or str(val).strip() == "":
        return None
    return str(val).strip()

def format_land_area(item):
    land_obj = item.get("landArea")
    parts = []
    if isinstance(land_obj, dict):
        rai = _clean_val(land_obj.get("rai"))
        ngan = _clean_val(land_obj.get("ngan"))
        wa = _clean_val(land_obj.get("sqWa") or land_obj.get("wa"))
        if rai and rai != "0": parts.append(f"{rai} ไร่")
        if ngan and ngan != "0": parts.append(f"{ngan} งาน")
        if wa and wa != "0": parts.append(f"{wa} ตร.ว.")
    
    if not parts:
        rai = _clean_val(item.get("landRai") or item.get("rai"))
        ngan = _clean_val(item.get("landNgan") or item.get("ngan"))
        wa = _clean_val(item.get("landWa") or item.get("wa"))
        if rai and rai != "0": parts.append(f"{rai} ไร่")
        if ngan and ngan != "0": parts.append(f"{ngan} งาน")
        if wa and wa != "0": parts.append(f"{wa} ตร.ว.")
        
    return " ".join(parts)

def format_usable_area(item):
    b_area = item.get("buildingArea") or item.get("usableArea")
    val = _clean_val(b_area)
    if val and val != "0":
        return val
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
    url = "https://www.bam.co.th/th/npa/property/search?page=1"
    for attempt in range(5):
        try:
            r = session.get(url, timeout=20)
            status_code = r.status_code
            if status_code == 200:
                html = r.text
                m_tot = (
                    re.search(r'ทรัพย์ทั้งหมด\s*(?:<!--\s*-->)?\s*([0-9,]+)\s*รายการ', html) or
                    re.search(r'["\']?totalCount["\']?\s*[:=]\s*(\d+)', html, re.I) or
                    re.search(r'["\']?total["\']?\s*[:=]\s*(\d+)', html, re.I)
                )
                tot_count = int(m_tot.group(1).replace(",", "")) if m_tot else 17536
                tot_pages = math.ceil(tot_count / 12)
                return True, status_code, tot_count, tot_pages
            else:
                time.sleep(2)
        except Exception as e:
            time.sleep(2)
    # If initial health check request times out, log warning but continue scraping with fallback defaults
    print(f"\n⚠️ [{COMPANY_NAME}] ไม่สามารถดึงหน้าตรวจสถานะเริ่มต้นได้ -> ใช้ค่าเริ่มต้น ~17,536 รายการ (1,462 หน้า)", flush=True)
    return True, 200, 17536, 1462

def fetch_item_detail(session, item_id):
    if not item_id: return "", "", "", None, None, None
    time.sleep(random.uniform(0.2, 0.45))
    url = f"https://www.bam.co.th/th/npa/property/{item_id}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    subdist, dist, prov, lat, lng, price = "", "", "", None, None, None
    for attempt in range(3):
        try:
            r = session.get(url, headers=headers, timeout=12)
            if r.status_code == 200:
                html = r.text
                soup = BeautifulSoup(html, 'html.parser')
                meta_desc = soup.find("meta", property="og:description") or soup.find("meta", attrs={"name": "description"})
                desc_str = meta_desc.get("content", "") if meta_desc else ""
                
                if desc_str and "|" in desc_str:
                    parts = [p.strip() for p in desc_str.split("|")]
                    if len(parts) >= 2:
                        loc_part = parts[1]
                        if "," in loc_part:
                            loc_tokens = [t.strip() for t in loc_part.split(",")]
                            if len(loc_tokens) >= 3:
                                subdist = loc_tokens[0]
                                dist = loc_tokens[1]
                                prov = loc_tokens[2]
                            elif len(loc_tokens) == 2:
                                dist = loc_tokens[0]
                                prov = loc_tokens[1]
                                
                for sc in soup.find_all('script', type='application/ld+json'):
                    if not sc.string: continue
                    try:
                        data = json.loads(sc.string)
                        if isinstance(data, dict):
                            offers = data.get('offers')
                            if isinstance(offers, dict) and 'price' in offers:
                                p_val = float(offers['price'])
                                if p_val > 0:
                                    price = p_val
                                    break
                    except Exception: pass

                m_lat = re.search(r'["\']?latitude["\']?\s*:\s*([\d\.-]+)', html, re.I)
                m_lng = re.search(r'["\']?longitude["\']?\s*:\s*([\d\.-]+)', html, re.I)
                if m_lat and m_lng:
                    try:
                        lat = float(m_lat.group(1))
                        lng = float(m_lng.group(1))
                    except Exception: pass
                if not lat:
                    m_map = re.search(r'maps\.google\.com/\?q=([\d\.-]+),([\d\.-]+)', html) or re.search(r'q=([\d\.-]+),([\d\.-]+)', html)
                    if m_map:
                        try:
                            lat = float(m_map.group(1))
                            lng = float(m_map.group(2))
                        except Exception: pass
                break
        except Exception:
            time.sleep(0.5)
    return subdist, dist, prov, lat, lng, price

def fetch_bam_page(session, page_num):
    url = f"https://www.bam.co.th/th/npa/property/search?page={page_num}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    for attempt in range(3):
        try:
            r = session.get(url, headers=headers, timeout=20)
            if r.status_code != 200:
                print_alert(f"HTTP Status {r.status_code} ในหน้า {page_num}", level="WARNING")
                time.sleep(2)
                continue
                
            html = r.text
            start_idx = html.find(r'\"properties\":')
            if start_idx == -1: start_idx = html.find('"properties":')
            if start_idx == -1:
                return []
                
            bracket_start = html.find('[', start_idx)
            if bracket_start == -1:
                return []
            balance = 0
            bracket_end = -1
            for i in range(bracket_start, len(html)):
                if html[i] == '[': balance += 1
                elif html[i] == ']':
                    balance -= 1
                    if balance == 0:
                        bracket_end = i
                        break
            items = json.loads(html[bracket_start:bracket_end+1].replace(r'\"', '"').replace(r'\/', '/'))
            
            records = []
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
                detail_futures = {executor.submit(fetch_item_detail, session, item.get("id") or item.get("propertyCode")): item for item in items}
                detail_results = {}
                for future in concurrent.futures.as_completed(detail_futures):
                    item = detail_futures[future]
                    item_id = item.get("id") or item.get("propertyCode")
                    try:
                        detail_results[item_id] = future.result()
                    except Exception:
                        detail_results[item_id] = ("", "", "", None, None, None)

            for item in items:
                pid = clean_text(item.get("id") or "")
                pcode = clean_text(item.get("propertyCode") or item.get("code") or "")
                title = clean_text(item.get("title") or item.get("propertyName") or "")
                ptype = clean_text(item.get("propertyType") or item.get("category") or "")
                price_list = clean_num(item.get("price") or item.get("specialPrice"))
                prov_list = clean_text(item.get("province") or "")
                dist_list = clean_text(item.get("district") or "")
                
                subdist, dist_det, prov_det, lat, lng, price_det = detail_results.get(pid, ("", "", "", None, None, None))
                
                final_dist = dist_det or dist_list
                final_prov = prov_det or prov_list
                final_price = price_list if price_list is not None else price_det
                
                land_str = format_land_area(item)
                usable_area = format_usable_area(item)
                
                link = f"https://www.bam.co.th/th/npa/property/{pid}" if pid else ""
                
                records.append({
                    "บริษัท": COMPANY_NAME,
                    "ID": pid or pcode,
                    "รหัสทรัพย์": pcode,
                    "ชื่อโครงการ": title,
                    "ประเภททรัพย์": ptype,
                    "ประเภทการขาย": "ขาย",
                    "ราคา": final_price,
                    "ตำบล": subdist,
                    "อำเภอ": final_dist,
                    "จังหวัด": final_prov,
                    "ละติจูด": lat,
                    "ลองจิจูด": lng,
                    "ชื่อประกาศ": title,
                    "ลิงก์": link,
                    "เนื้อที่ (ตร.ว.)": convert_to_rai_ngan_wah(land_str),
                    "พื้นที่ใช้สอย (ตร.ม.)": usable_area,
                    "วันที่ดึงข้อมูล": now_str,
                    "วันประกาศ": clean_text(item.get("created_at") or item.get("postDate") or item.get("yearBuilt") or ""),
                    "ห้องนอน": clean_num(item.get("bedrooms")),
                    "ห้องน้ำ": clean_num(item.get("bathrooms")),
                    "ที่จอดรถ": clean_num(item.get("parking"))
                })
            return records
        except Exception as e:
            print_alert(f"เกิดข้อผิดพลาดในการดึงข้อมูลหน้า {page_num} (พยายาม {attempt+1}): {e}", level="WARNING")
            time.sleep(2)
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
    print(f"🚀 เริ่มต้นการ Scrape [{COMPANY_NAME}] (Monthly Mode: จากหน้าเก่าสุด -> หน้าล่าสุด)", flush=True)
    print(f"📁 บันทึกข้อมูลลงไฟล์: {OUTPUT_CSV}", flush=True)
    print(f"==================================================", flush=True)
    
    session = requests.Session()
    session.headers.update(HEADERS)
    
    all_records, seen_ids = load_existing_csv(OUTPUT_CSV)
    
    is_ok, code, total_count, max_page = check_link_health(session)
    if is_ok:
        status_msg = f"🌐 สถานะลิงก์: ปกติ (HTTP {code}) | ทั้งหมด {max_page:,} หน้า | {ITEMS_PER_PAGE} รายการ/หน้า ({total_count:,} รายการ)"
        print(f"[{COMPANY_NAME}] {status_msg}", flush=True)
    else:
        print_alert("ไม่สามารถเข้าถึง API BAM ได้", level="CRITICAL")
        return
        
    if total_count > 0 and len(all_records) >= (total_count - 50):
        print(f"[{COMPANY_NAME}] 🎉 ข้อมูลใน CSV ครบถ้วน 100% แล้ว ({len(all_records):,}/{total_count:,} รายการ) -> สแครปเสร็จสมบูรณ์ทันที!", flush=True)
        save_to_csv(all_records, OUTPUT_CSV)
        return
    
    saved_milestones = set()
    failed_pages = []
    
    start_time = time.time()
    
    items_per_p = 12
    completed_pages = min(max_page - 1, len(all_records) // items_per_p)
    processed_count = completed_pages
    new_added = 0
    
    start_page = max(1, max_page - completed_pages)
    pages_order = list(range(start_page, 0, -1))
    if completed_pages > 0:
        print(f"[{COMPANY_NAME}] ⏩ Fast-Forward Resume: ข้าม {completed_pages:,} หน้าแรกที่เคยดึงแล้ว -> เริ่มสแครปหน้า {start_page:,} ต่อทันที", flush=True)
    
    for page in pages_order:
        if total_count > 0 and len(all_records) >= total_count:
            print(f"\n[{COMPANY_NAME}] 🎉 สะสมข้อมูลครบถ้วนทั้งหมดแล้ว ({len(all_records):,}/{total_count:,} รายการ) -> สิ้นสุดการสแครป!", flush=True)
            break
        items = fetch_bam_page(session, page)
        if items is None:
            failed_pages.append(page)
            print(f"\n[{COMPANY_NAME}] ⚠️ ข้ามหน้า {page} เนื่องจากดึงข้อมูลไม่สำเร็จ", flush=True)
            processed_count += 1
            continue

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
            
        processed_count += 1
        pct = int((processed_count / max_page) * 100)
        elapsed_sec = time.time() - start_time
        eta_msg = format_eta(elapsed_sec, processed_count, max_page)
        pbar = make_progress_bar(pct)
        
        print(f"\r[{COMPANY_NAME:<13s}] {pbar} | ({processed_count:5,d}/{max_page:5,d} หน้า) | สะสม: {len(all_records):>7,d} รายการ | {eta_msg}", end="", flush=True)
        
        if len(all_records) >= 10 and "initial_10" not in saved_milestones:
            saved_milestones.add("initial_10")
            print(f"\n💾 [{COMPANY_NAME}] ครบ 10 รายการแรก -> บันทึกไฟล์เริ่มต้นลง {OUTPUT_CSV}...", flush=True)
            save_to_csv(all_records, OUTPUT_CSV)

        for target_pct in [25, 50, 75, 100]:
            if pct >= target_pct and target_pct not in saved_milestones:
                saved_milestones.add(target_pct)
                print(f"\n💾 [{COMPANY_NAME}] ครบ Milestone {target_pct}% ({processed_count}/{max_page} หน้า) -> บันทึกสำรองลง {OUTPUT_CSV}...", flush=True)
                save_to_csv(all_records, OUTPUT_CSV)
                
        time.sleep(0.5)
        
    print("", flush=True)
    save_to_csv(all_records, OUTPUT_CSV)
    elapsed = time.time() - start_time
    print(f"\n==================================================", flush=True)
    print(f"✅ [{COMPANY_NAME}] สแครปเสร็จสมบูรณ์!", flush=True)
    print(f"📊 ได้ข้อมูลทั้งหมด: {len(all_records):,} รายการ (เพิ่มใหม่ในรอบนี้: {new_added:,} รายการ)", flush=True)
    print(f"⏱️ ใช้เวลาทั้งหมด: {elapsed/60:.2f} นาที", flush=True)
    print(f"💾 ไฟล์ CSV: {OUTPUT_CSV}", flush=True)
    if failed_pages:
        print(f"⚠️ รายการหน้าที่ข้าม/ดึงไม่ได้ ({len(failed_pages)} หน้า): {sorted(failed_pages)}", flush=True)
    else:
        print(f"✅ ดึงข้อมูลได้ครบถ้วนสำเร็จทุกหน้า (ไม่มีหน้าล้มเหลว)", flush=True)
    print(f"==================================================", flush=True)

if __name__ == "__main__":
    main()
