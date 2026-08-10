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
import threading

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

COMPANY_NAME = "ZmyHome"
MONTH_STR = datetime.now().strftime("%Y_%m")

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "CSV_Output")
os.makedirs(OUTPUT_DIR, exist_ok=True)
OUTPUT_CSV = os.path.join(OUTPUT_DIR, f"ZmyHome_NPA_New_{MONTH_STR}.csv")

BASE_URL = "https://zmyhome.com/buy"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "th,en-US;q=0.9,en;q=0.8",
    "Referer": "https://zmyhome.com/"
}

COLUMNS = [
    "บริษัท", "ID", "รหัสทรัพย์", "ชื่อโครงการ", "ประเภททรัพย์", "ประเภทการขาย", "ราคา",
    "ตำบล", "อำเภอ", "จังหวัด", "ละติจูด", "ลองจิจูด", "ชื่อประกาศ", "ลิงก์",
    "พื้นที่ (ไร่-งาน-วา)", "พื้นที่ใช้สอย (ตร.ม.)", "วันที่ดึงข้อมูล",
    "ห้องนอน", "ห้องน้ำ", "ที่จอดรถ", "วันประกาศ"
]

ITEMS_PER_PAGE = 35
THREAD_POOL_SIZE = 10

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
    if not val or str(val).strip().lower() in ["none", "null", "undefined"]:
        return ""
    return re.sub(r"\s+", " ", str(val)).strip()

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
    for attempt in range(5):
        try:
            r = session.get(BASE_URL, timeout=20)
            status_code = r.status_code
            if status_code == 200:
                soup = BeautifulSoup(r.text, 'html.parser')
                pag_ul = soup.find(class_=lambda c: c and "pagination" in c.lower())
                pages = []
                if pag_ul:
                    for a in pag_ul.find_all('a', href=True):
                        m = re.search(r'page=(\d+)', a['href'])
                        if m:
                            pages.append(int(m.group(1)))
                max_p = max(pages) if pages else 800
                tot_est = max_p * ITEMS_PER_PAGE
                return True, status_code, tot_est, max_p
        except Exception as e:
            time.sleep(2)
    return False, 0, 0, 0

def fetch_zmyhome_detail(session, item):
    link = item.get("ลิงก์")
    if not link:
        return item
        
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    for attempt in range(3):
        try:
            r = session.get(link, headers=headers, timeout=12)
            if r.status_code == 200:
                html = r.text
                
                # 1. Lat/Lng
                m_map = re.search(r'query=([\d\.-]+),([\d\.-]+)', html) or re.search(r'q=([\d\.-]+),([\d\.-]+)', html) or re.search(r'maps\.google\.com[^\'"]*?@([\d\.-]+),([\d\.-]+)', html)
                if m_map:
                    try:
                        item["ละติจูด"] = float(m_map.group(1))
                        item["ลองจิจูด"] = float(m_map.group(2))
                    except Exception:
                        pass
                        
                # 2. Location (subdistrict, district, province)
                m_sd = re.search(r'(?:ตำบล|ต\.|แขวง)\s*([^\s,\|<"\']+)', html)
                if m_sd and not item.get("ตำบล"):
                    item["ตำบล"] = m_sd.group(1).strip()
                    
                m_d = re.search(r'(?:อำเภอ|อ\.|เขต)\s*([^\s,\|<"\']+)', html)
                if m_d and not item.get("อำเภอ"):
                    item["อำเภอ"] = m_d.group(1).strip()
                    
                m_p = re.search(r'(?:จังหวัด|จ\.)\s*([^\s,\|<"\']+)', html)
                if m_p and not item.get("จังหวัด"):
                    item["จังหวัด"] = m_p.group(1).strip()
                elif "กรุงเทพ" in html and not item.get("จังหวัด"):
                    item["จังหวัด"] = "กรุงเทพมหานคร"
                    
                # 3. Usable Area & Land Area
                m_u = re.search(r'([\d\.]+)\s*(?:ตร\.ม\.|ตารางเมตร)', html)
                if m_u and not item.get("พื้นที่ใช้สอย (ตร.ม.)"):
                    item["พื้นที่ใช้สอย (ตร.ม.)"] = m_u.group(1).strip()
                    
                m_l = re.search(r'([\d\.]+)\s*(?:ตร\.วา|ตารางวา|วา)', html)
                if m_l and not item.get("พื้นที่ (ไร่-งาน-วา)"):
                    item["พื้นที่ (ไร่-งาน-วา)"] = f"{m_l.group(1)} วา"
                    
                # 4. Posted Date
                m_post = re.search(r'(?:ลงประกาศเมื่อ|อัปเดตเมื่อ|สร้างเมื่อ|ประกาศเมื่อ)\s*[:\s]*([^\n\r<"]+)', html)
                if m_post and not item.get("วันประกาศ"):
                    item["วันประกาศ"] = clean_text(m_post.group(1))
                    
                # 5. Bedrooms, Bathrooms, Parking
                m_bed = re.search(r'(\d+)\s*ห้องนอน', html)
                if m_bed: item["ห้องนอน"] = int(m_bed.group(1))
                m_bath = re.search(r'(\d+)\s*ห้องน้ำ', html)
                if m_bath: item["ห้องน้ำ"] = int(m_bath.group(1))
                m_park = re.search(r'(\d+)\s*ที่จอดรถ', html)
                if m_park: item["ที่จอดรถ"] = int(m_park.group(1))
                
                break
        except Exception:
            time.sleep(0.5)
    return item

def parse_zmyhome_card(card):
    try:
        fig_a = card.find("figure").find("a") if card.find("figure") else card.find('a', href=True)
        link = fig_a['href'].strip() if fig_a and fig_a.has_attr('href') else ""
        if link and not link.startswith("http"):
            link = "https://zmyhome.com" + link
            
        m_id = re.search(r'/([A-Za-z0-9]+)(?:\?|$)', link)
        item_id = m_id.group(1) if m_id else ""
        if not item_id or item_id.lower() in ["buy", "property"]:
            item_id = link.split("/")[-1].split("?")[0].strip()
            
        if not item_id:
            return None
            
        title_tag = card.find("div", class_="card-property__ad-text-small-highlight")
        title = ""
        if title_tag:
            h3 = title_tag.find("h3")
            title = clean_text(h3.text) if h3 else ""
        if not title:
            title_tag = card.find(class_=lambda c: c and ("title" in c.lower() or "heading" in c.lower()))
            title = clean_text(title_tag.text) if title_tag else clean_text(card.text[:50])
            
        title = re.sub(r'^(?:ขาย\s*)+', 'ขาย ', title).strip()
        title = re.sub(r'^(?:เช่า\s*)+', 'เช่า ', title).strip()
        
        price_tag = card.find("span", class_="currency th")
        if not price_tag:
            price_tag = card.find(class_=lambda c: c and "price" in c.lower())
        price_str = clean_text(price_tag.text) if price_tag else ""
        price_clean = re.sub(r"[^\d\.]", "", price_str.replace(",", ""))
        price = float(price_clean) if price_clean else None
        
        loc_li = card.find("li", class_="location")
        loc_text = clean_text(loc_li.text) if loc_li else ""
        
        prov, dist, subdist = "", "", ""
        if loc_text:
            m_sd = re.search(r'(?:ตำบล|ต\.|แขวง)\s*([^\s,]+)', loc_text)
            if m_sd: subdist = m_sd.group(1).strip()
            
            m_d = re.search(r'(?:อำเภอ|อ\.|เขต)\s*([^\s,]+)', loc_text)
            if m_d: dist = m_d.group(1).strip()
            
            m_p = re.search(r'(?:จังหวัด|จ\.)\s*([^\s,]+)', loc_text)
            if m_p: prov = m_p.group(1).strip()
            elif "กรุงเทพ" in loc_text:
                prov = "กรุงเทพมหานคร"
                
            if not prov and not dist:
                parts = [p.strip() for p in loc_text.split() if p.strip() and not p.isdigit()]
                if len(parts) >= 2:
                    prov = parts[-1]
                    dist = parts[-2]
                elif len(parts) == 1:
                    prov = parts[0]
                    
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        return {
            "บริษัท": COMPANY_NAME,
            "ID": item_id,
            "รหัสทรัพย์": item_id,
            "ชื่อโครงการ": title,
            "ประเภททรัพย์": "คอนโด" if item_id.startswith("V") else "บ้านเดี่ยว/ทาวน์เฮาส์",
            "ประเภทการขาย": "ขาย",
            "ราคา": price,
            "ตำบล": subdist,
            "อำเภอ": dist,
            "จังหวัด": prov,
            "ละติจูด": None,
            "ลองจิจูด": None,
            "ชื่อประกาศ": title,
            "ลิงก์": link,
            "พื้นที่ (ไร่-งาน-วา)": "",
            "พื้นที่ใช้สอย (ตร.ม.)": "",
            "วันที่ดึงข้อมูล": now_str,
            "วันประกาศ": "",
            "ห้องนอน": None,
            "ห้องน้ำ": None,
            "ที่จอดรถ": None
        }
    except Exception:
        return None

def fetch_zmyhome_page(session, page_num):
    url = f"{BASE_URL}?page={page_num}&sortFilter=ads&per-page=35"
    for attempt in range(3):
        try:
            r = session.get(url, timeout=20)
            if r.status_code != 200:
                print_alert(f"HTTP Status {r.status_code} ในหน้า {page_num}", level="WARNING")
                time.sleep(2)
                continue
                
            soup = BeautifulSoup(r.text, 'html.parser')
            cards = soup.find_all("article", class_="card-property__item--article")
            if not cards:
                cards = soup.find_all("article")
                
            raw_records = []
            for card in cards:
                item = parse_zmyhome_card(card)
                if item and item.get("ID"):
                    raw_records.append(item)
                    
            # Fetch detail pages concurrently for coordinates & full details
            records = []
            with concurrent.futures.ThreadPoolExecutor(max_workers=THREAD_POOL_SIZE) as executor:
                futures = [executor.submit(fetch_zmyhome_detail, session, item) for item in raw_records]
                for future in concurrent.futures.as_completed(futures):
                    try:
                        records.append(future.result())
                    except Exception:
                        pass
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
    print(f"🚀 เริ่มต้นการ Scrape [{COMPANY_NAME}] (Monthly Mode: ดึงพิกัด Lat/Lng 100%)", flush=True)
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
        print_alert("ไม่สามารถเข้าถึงเว็บ ZmyHome ได้", level="CRITICAL")
        return
        
    if total_count > 0 and len(all_records) >= (total_count - 50):
        print(f"[{COMPANY_NAME}] 🎉 ข้อมูลใน CSV ครบถ้วน 100% แล้ว ({len(all_records):,}/{total_count:,} รายการ) -> สแครปเสร็จสมบูรณ์ทันที!", flush=True)
        save_to_csv(all_records, OUTPUT_CSV)
        return
    
    saved_milestones = set()
    failed_pages = []
    
    start_time = time.time()
    
    items_per_p = ITEMS_PER_PAGE
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
        items = fetch_zmyhome_page(session, page)
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
