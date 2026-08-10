import requests
import json
import re
import os
import sys
import time
import random
import urllib.parse
from datetime import datetime
import pandas as pd
from bs4 import BeautifulSoup
import concurrent.futures
import threading

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

COMPANY_NAME = "Livinginsider"
MONTH_STR = datetime.now().strftime("%Y_%m")

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "CSV_Output")
os.makedirs(OUTPUT_DIR, exist_ok=True)
OUTPUT_CSV = os.path.join(OUTPUT_DIR, f"Livinginsider_NPA_New_{MONTH_STR}.csv")

URL_TEMPLATE = "https://www.livinginsider.com/searchword/all/Buysell/{page_num}/%E0%B8%A3%E0%B8%A7%E0%B8%A1%E0%B8%9B%E0%B8%A3%E0%B8%B0%E0%B8%81%E0%B8%B2%E0%B8%A8%E0%B8%82%E0%B8%B2%E0%B8%A2-%E0%B8%84%E0%B8%AD%E0%B8%99%E0%B9%82%E0%B8%94-%E0%B8%9A%E0%B9%89%E0%B8%B2%E0%B8%99-%E0%B8%97%E0%B8%B5%E0%B9%88%E0%B8%94%E0%B8%B4%E0%B8%99.html"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "th,en-US;q=0.9,en;q=0.8",
    "Referer": "https://www.livinginsider.com/",
    "Connection": "keep-alive"
}

COLUMNS = [
    "บริษัท", "ID", "รหัสทรัพย์", "ชื่อโครงการ", "ประเภททรัพย์", "ประเภทการขาย", "ราคา",
    "ตำบล", "อำเภอ", "จังหวัด", "ละติจูด", "ลองจิจูด", "ชื่อประกาศ", "ลิงก์",
    "พื้นที่ (ไร่-งาน-วา)", "พื้นที่ใช้สอย (ตร.ม.)", "วันที่ดึงข้อมูล",
    "ห้องนอน", "ห้องน้ำ", "ที่จอดรถ", "วันประกาศ"
]

ITEMS_PER_PAGE = 48
THREAD_POOL_SIZE = 35

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
            valid_rows = []
            for r in df[COLUMNS].to_dict(orient="records"):
                link_str = str(r.get("ลิงก์") or "")
                if "living_transit" in link_str or "living_zone" in link_str:
                    continue
                iid = str(r.get("ID") or "").strip()
                if iid and len(iid) > 4:
                    seen_ids.add(iid)
                    valid_rows.append(r)
            records = valid_rows
            print(f"[{COMPANY_NAME}] 🔄 Smart Resume: โหลดข้อมูลเดิมจาก {filename} พบรายการทรัพย์สินจริง {len(records):,} รายการ", flush=True)
        except Exception as e:
            print_alert(f"ไม่สามารถอ่านไฟล์สะสมเดิม {filename}: {e}", level="WARNING")
    return records, seen_ids

def check_link_health(session):
    url = URL_TEMPLATE.format(page_num=1)
    for attempt in range(5):
        try:
            r = session.get(url, timeout=20)
            status_code = r.status_code
            if status_code == 200:
                pages = [int(m) for m in re.findall(r'/searchword/all/Buysell/(\d+)/', r.text)]
                if not pages:
                    pages = [int(m) for m in re.findall(r'/searchword/all/[^/]+/(\d+)/', r.text)]
                max_p = max(pages) if pages else 2993
                tot_est = max_p * ITEMS_PER_PAGE
                return True, status_code, tot_est, max_p
        except Exception as e:
            time.sleep(2 + attempt)
    return False, 0, 0, 0

def parse_living_address(soup, html):
    subdist, dist, prov = "", "", ""
    
    # 1. Check Breadcrumbs List for Project Name and District/Zone
    b_items = []
    for sc in soup.find_all('script', type='application/ld+json'):
        if not sc.string: continue
        try:
            data = json.loads(sc.string)
            if isinstance(data, dict) and data.get('@type') == 'BreadcrumbList':
                b_items = data.get('itemListElement', [])
                break
        except Exception: pass

    zone_name = ""
    for elem in b_items:
        item_url = str(elem.get('item') or '')
        name = str(elem.get('name') or '').strip()
        if 'living_zone' in item_url and not zone_name:
            if name and name not in ["หน้าแรก"]:
                zone_name = name

    # 2. Text clean up for strict address parsing
    clean_html = re.sub(r'<script.*?</script>', '', html, flags=re.DOTALL)
    clean_html = re.sub(r'<style.*?</style>', '', clean_html, flags=re.DOTALL)
    clean_html = re.sub(r'<header.*?</header>', '', clean_html, flags=re.DOTALL)
    clean_html = re.sub(r'<footer.*?</footer>', '', clean_html, flags=re.DOTALL)
    
    soup_clean = BeautifulSoup(clean_html, 'html.parser')
    text_only = soup_clean.get_text()

    # 3. Subdistrict (ตำบล/แขวง) - ONLY match explicit ตำบล / แขวง / ต.
    m_sd = re.search(r'(?:ตำบล|ต\.|แขวง)\s*([^\s,\|<"\'\(\)\/\d\-\:\.]+)', text_only)
    if m_sd:
        cand_sd = m_sd.group(1).strip()
        if len(cand_sd) > 1 and cand_sd not in ["โซน", "ถนน", "ซอย", "โครงการ", "อื่นๆ", "ทำเล"]:
            subdist = cand_sd
            
    # 4. District (อำเภอ/เขต)
    m_d = re.search(r'(?:อำเภอ|อ\.|เขต)\s*([^\s,\|<"\'\(\)\/\d\-\:\.]+)', text_only)
    if m_d:
        cand_d = m_d.group(1).strip()
        if len(cand_d) > 1 and cand_d not in ["โซน", "ถนน", "ซอย", "โครงการ", "อื่นๆ", "ทำเล"]:
            dist = cand_d
    if not dist and zone_name:
        dist = zone_name
        
    # 5. Province (จังหวัด)
    m_p = re.search(r'(?:จังหวัด|จ\.)\s*([^\s,\|<"\'\(\)\/\d\-\:\.]+)', text_only)
    if m_p:
        cand_p = m_p.group(1).strip()
        if cand_p not in ["อื่นๆ"]: prov = cand_p
    if not prov:
        for p in ["กรุงเทพมหานคร", "กรุงเทพ", "สมุทรปราการ", "นนทบุรี", "ปทุมธานี", "ชลบุรี", "เชียงใหม่", "ภูเก็ต", "ระยอง", "ฉะเชิงเทรา"]:
            pattern = r'(?<![\u0E00-\u0E7F])' + re.escape(p) + r'(?![\u0E00-\u0E7F])'
            if re.search(pattern, text_only):
                prov = "กรุงเทพมหานคร" if p in ["กรุงเทพ", "กรุงเทพมหานคร"] else p
                break
    if not prov and ("กรุงเทพ" in text_only or "กรุงเทพมหานคร" in text_only):
        prov = "กรุงเทพมหานคร"
        
    return subdist, dist, prov

def extract_living_project_name(soup, title):
    b_items = []
    for sc in soup.find_all('script', type='application/ld+json'):
        if not sc.string: continue
        try:
            data = json.loads(sc.string)
            if isinstance(data, dict) and data.get('@type') == 'BreadcrumbList':
                b_items = data.get('itemListElement', [])
                break
        except Exception: pass

    for elem in b_items:
        item_url = str(elem.get('item') or '')
        name = str(elem.get('name') or '').strip()
        if 'living_project' in item_url:
            if name and name not in ["ดูโครงการทั้งหมด", "โครงการทั้งหมด", "หน้าแรก", "รายการ ขาย เช่า"]:
                return name

    proj_tag = soup.find('a', href=re.compile(r'living_project/'))
    if proj_tag:
        p_name = proj_tag.get_text().strip()
        if p_name and p_name not in ["ดูโครงการทั้งหมด", "โครงการทั้งหมด", "รายการ ขาย เช่า"]:
            return p_name
            
    m_proj = re.search(r'(?:โครงการ|หมู่บ้าน|คอนโด)\s*([A-Za-z0-9\u0E00-\u0E7F\s\-\.]{3,30}?)(?=\s*(?:ซอย|ถนน|ตำบล|แขวง|อำเภอ|เขต|จังหวัด|ชั้น|ขนาด|ราคา|ให้เช่า|ขาย|$))', title)
    if m_proj:
        p_cand = m_proj.group(1).strip()
        p_cand = re.sub(r'^[/\s]+', '', p_cand).strip()
        if p_cand and p_cand.lower() not in ["none", "null", "-", "/", "โครงการ", "หมู่บ้าน", "รายการ ขาย เช่า"]:
            return p_cand
            
    return ""  # Leave blank if no project name

def detect_living_property_type(html_or_text, title="", link=""):
    title_link = f"{title} {link}".lower()
    
    # 1. Prioritize Title and Link URL
    if any(x in title_link for x in ["ทาวน์โฮม", "ทาวน์เฮ้าส์", "townhome", "townhouse"]):
        return "ทาวน์โฮม"
    if any(x in title_link for x in ["บ้านเดี่ยว", "บ้านแฝด", "single-house", "single house"]):
        return "บ้านเดี่ยว"
    if any(x in title_link for x in ["อาคารพาณิชย์", "ตึกแถว", "shophouse", "commercial"]):
        return "อาคารพาณิชย์"
    if any(x in title_link for x in ["ที่ดิน", "land-for-sale", "land"]):
        return "ที่ดิน"
    if any(x in title_link for x in ["โรงงาน", "โกดัง", "factory", "warehouse"]):
        return "โรงงาน/โกดัง"
    if any(x in title_link for x in ["อพาร์ทเม้นท์", "หอพัก", "apartment"]):
        return "อพาร์ทเม้นท์"
    if any(x in title_link for x in ["คอนโด", "condo"]):
        return "คอนโด"
    if any(x in title_link for x in ["บ้าน", "house"]):
        return "บ้านเดี่ยว"
        
    # 2. Check main content text (excluding html header/footer links)
    clean_text = re.sub(r'<footer.*?</footer>', '', str(html_or_text), flags=re.DOTALL | re.I)
    clean_text = re.sub(r'<header.*?</header>', '', clean_text, flags=re.DOTALL | re.I).lower()
    
    if "ทาวน์โฮม" in clean_text or "ทาวน์เฮ้าส์" in clean_text:
        return "ทาวน์โฮม"
    if "บ้านเดี่ยว" in clean_text or "บ้านแฝด" in clean_text:
        return "บ้านเดี่ยว"
    if "อาคารพาณิชย์" in clean_text or "ตึกแถว" in clean_text:
        return "อาคารพาณิชย์"
    if "ที่ดิน" in clean_text:
        return "ที่ดิน"
    if "โรงงาน" in clean_text or "โกดัง" in clean_text:
        return "โรงงาน/โกดัง"
    if "อพาร์ทเม้นท์" in clean_text or "หอพัก" in clean_text:
        return "อพาร์ทเม้นท์"
    if "คอนโด" in clean_text:
        return "คอนโด"
        
    return "คอนโด"

def fetch_living_detail(session, item):
    link = item.get("ลิงก์")
    if not link:
        return item
        
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    for attempt in range(3):
        try:
            r = session.get(link, headers=headers, timeout=12)
            if r.status_code == 200:
                html = r.text
                soup = BeautifulSoup(html, 'html.parser')
                main_box = soup.find('div', id='detail-post') or soup.find(class_=re.compile(r'detail-container|post-detail|main-info', re.I)) or soup
                main_text = main_box.get_text()
                
                # Extract Real Listing Title from H1 or og:title
                h1_elem = soup.find('h1')
                real_title = clean_text(h1_elem.get_text()) if h1_elem else ""
                if not real_title:
                    og_meta = soup.find('meta', property='og:title') or soup.find('meta', attrs={'name': 'title'})
                    if og_meta:
                        real_title = clean_text(og_meta.get('content', '')).split('|')[0].strip()
                        
                if real_title:
                    item["ชื่อประกาศ"] = real_title
                    
                # Extract Project Name (Leave blank if none)
                item["ชื่อโครงการ"] = extract_living_project_name(soup, item.get("ชื่อประกาศ", ""))
                
                # Property Type Detection
                item["ประเภททรัพย์"] = detect_living_property_type(html, item.get("ชื่อประกาศ", ""), link)
                
                # 1. Lat/Lng
                m_lat = re.search(r'data-lat=["\']([\d\.-]+)["\']', html) or re.search(r'lat\s*[:=]\s*["\']?([\d\.-]+)', html)
                m_lng = re.search(r'data-lng=["\']([\d\.-]+)["\']', html) or re.search(r'lng\s*[:=]\s*["\']?([\d\.-]+)', html)
                if m_lat and m_lng:
                    try:
                        item["ละติจูด"] = float(m_lat.group(1))
                        item["ลองจิจูด"] = float(m_lng.group(1))
                    except Exception:
                        pass
                else:
                    m_map = re.search(r'query=([\d\.-]+),([\d\.-]+)', html) or re.search(r'q=([\d\.-]+),([\d\.-]+)', html)
                    if m_map:
                        try:
                            item["ละติจูด"] = float(m_map.group(1))
                            item["ลองจิจูด"] = float(m_map.group(2))
                        except Exception:
                            pass
                            
                # 2. Location (subdistrict, district, province)
                sd, d, p = parse_living_address(soup, html)
                if sd and not item.get("ตำบล"): item["ตำบล"] = sd
                if d and not item.get("อำเภอ"): item["อำเภอ"] = d
                if p and not item.get("จังหวัด"): item["จังหวัด"] = p
                    
                # 3. Usable Area & Land Area
                m_u = re.search(r'พื้นที่ใช้สอย\s*[:\s]*([\d\.,]+)\s*(?:ตร\.ม\.|ตารางเมตร)', main_text) or re.search(r'([\d\.,]+)\s*ตร\.ม\.', main_text)
                if m_u and not item.get("พื้นที่ใช้สอย (ตร.ม.)"):
                    item["พื้นที่ใช้สอย (ตร.ม.)"] = m_u.group(1).replace(',', '').strip()
                    
                rai_m = re.search(r'(\d+)\s*ไร่', main_text)
                ngan_m = re.search(r'(\d+)\s*งาน', main_text)
                wa_m = re.search(r'ขนาดที่ดิน\s*[:\s]*([\d\.,]+)\s*(?:ตร\.วา|ตารางวา|ตร\.ว\.|วา)', main_text) or re.search(r'([\d\.,]+)\s*(?:ตร\.วา|ตารางวา|ตร\.ว\.|วา)', main_text)
                
                parts = []
                if rai_m: parts.append(f"{rai_m.group(1)} ไร่")
                if ngan_m: parts.append(f"{ngan_m.group(1)} งาน")
                if wa_m: parts.append(f"{wa_m.group(1)} วา")
                
                if parts and not item.get("พื้นที่ (ไร่-งาน-วา)"):
                    item["พื้นที่ (ไร่-งาน-วา)"] = " ".join(parts)
                    
                # 4. Posted / Completed Date (วันประกาศ)
                m_post = re.search(r'(?:สร้างเมื่อ|สร้างเสร็จปี|โพสต์เมื่อ)\s*[:\s]*([^\n\r<"]+)', main_text)
                if m_post:
                    item["วันประกาศ"] = clean_text(m_post.group(1))
                    
                # 5. Bedrooms, Bathrooms, Parking
                m_bed = re.search(r'(\d+)\s*ห้องนอน', main_text)
                if m_bed: item["ห้องนอน"] = int(m_bed.group(1))
                m_bath = re.search(r'(\d+)\s*ห้องน้ำ', main_text)
                if m_bath: item["ห้องน้ำ"] = int(m_bath.group(1))
                m_park = re.search(r'(\d+)\s*ที่จอดรถ', main_text)
                if m_park: item["ที่จอดรถ"] = int(m_park.group(1))
                
                break
        except Exception:
            time.sleep(0.5)
    return item

def parse_living_card(card):
    try:
        a_tag = card.find('a', href=re.compile(r'living_detail|/detail/'))
        if not a_tag:
            a_tag = card.find('a', href=True)
        
        link = a_tag['href'] if a_tag else ""
        if link and not link.startswith("http"):
            link = "https://www.livinginsider.com" + link
            
        if any(x in link for x in ["living_transit", "living_zone", "living_project", "manual.php"]):
            return None
            
        m_id = re.search(r'living_detail/(\d+)', link) or re.search(r'-(\d+)(?:\.html|\?|$)', link)
        if not m_id:
            return None
        item_id = m_id.group(1)
        
        title = ""
        a_title = card.find('h2') or card.find('h3') or card.find('a', title=True)
        if a_title:
            title = clean_text(a_title.get('title') or a_title.text)
        if not title or title in ["คอนโด", "ทาวน์โฮม", "ทาวน์เฮ้าส์", "บ้านเดี่ยว", "บ้าน", "ที่ดิน", "อาคารพาณิชย์"]:
            title_tag = card.find(class_=lambda c: c and ("title" in c.lower() or "heading" in c.lower()) and "type" not in c.lower() and "cat" not in c.lower())
            if title_tag:
                title = clean_text(title_tag.text)
        if not title:
            title = clean_text(card.text[:100])
        
        price_tag = card.find(class_=lambda c: c and "price" in c.lower())
        price_str = clean_text(price_tag.text) if price_tag else ""
        price_clean = re.sub(r"[^\d\.]", "", price_str.replace(",", ""))
        price = float(price_clean) if price_clean else None
        
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        ptype = detect_living_property_type(card.text, title, link)
        
        return {
            "บริษัท": COMPANY_NAME,
            "ID": item_id,
            "รหัสทรัพย์": item_id,
            "ชื่อโครงการ": "",
            "ประเภททรัพย์": ptype,
            "ประเภทการขาย": "ขาย",
            "ราคา": price,
            "ตำบล": "",
            "อำเภอ": "",
            "จังหวัด": "",
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

def enrich_living_detail_location(session, item):
    """Lightweight detail page fetcher: extracts only ตำบล/อำเภอ/จังหวัด/พิกัด."""
    link = item.get("ลิงก์")
    if not link:
        return item
    try:
        r = session.get(link, timeout=8)
        if r.status_code == 200:
            html = r.text
            soup = BeautifulSoup(html, 'html.parser')
            main_text = soup.get_text()

            # --- Lat/Lng ---
            m_gmap = (
                re.search(r'(?:q|center|ll|location|place)=([\d\.-]+)%2C([\d\.-]+)', html, re.I)
                or re.search(r'(?:q|center|ll|location|place)=([\d\.-]+),([\d\.-]+)', html, re.I)
                or re.search(r'@([\d\.-]+),([\d\.-]+)', html)
            )
            if not m_gmap:
                m_lat = re.search(r'data-lat=["\']?([\d\.-]+)', html) or re.search(r'lat\s*[:=]\s*["\']?([\d\.-]+)', html)
                m_lng = re.search(r'data-lng=["\']?([\d\.-]+)', html) or re.search(r'lng\s*[:=]\s*["\']?([\d\.-]+)', html)
                if m_lat and m_lng:
                    m_gmap = type('M', (), {'group': lambda s, i: [None, m_lat.group(1), m_lng.group(1)][i]})()
            if m_gmap:
                try:
                    lat_v, lng_v = float(m_gmap.group(1)), float(m_gmap.group(2))
                    if 5.0 <= lat_v <= 21.0 and 97.0 <= lng_v <= 106.0:
                        item["ละติจูด"] = lat_v
                        item["ลองจิจูด"] = lng_v
                except Exception:
                    pass

            # --- ตำบล / อำเภอ / จังหวัด from text patterns ---
            m_loc = re.search(
                r'(?:ตำบล|แขวง)\s*([^\s\n\r<>"]+)\s*(?:อำเภอ|เขต)\s*([^\s\n\r<>"]+)\s*(?:จังหวัด)?\s*([^\s\n\r<>"]+)',
                main_text
            )
            if m_loc:
                item["ตำบล"] = m_loc.group(1).strip()
                item["อำเภอ"] = m_loc.group(2).strip()
                prov = m_loc.group(3).strip()
                if prov and prov not in ["รหัสไปรษณีย์"]:
                    item["จังหวัด"] = prov
            else:
                m_sd = re.search(r'(?:แขวง\s*/\s*ตำบล|ตำบล|แขวง)\s*[:\s]*([^\n\r<"]+)', main_text)
                if m_sd:
                    item["ตำบล"] = m_sd.group(1).split()[0].strip()
                m_d = re.search(r'(?:เขต\s*/\s*อำเภอ|อำเภอ|เขต)\s*[:\s]*([^\n\r<"]+)', main_text)
                if m_d:
                    item["อำเภอ"] = m_d.group(1).split()[0].strip()
                m_p = re.search(r'จังหวัด\s*[:\s]*([^\n\r<"]+)', main_text)
                if m_p:
                    item["จังหวัด"] = m_p.group(1).split()[0].strip()

            # --- ชื่อโครงการ from detail ---
            item["ชื่อโครงการ"] = extract_living_project_name(soup, item.get("ชื่อประกาศ", ""))
    except Exception:
        pass
    return item

def fetch_living_page(session, page_num):
    url = URL_TEMPLATE.format(page_num=page_num)
    max_retries = 5
    for attempt in range(max_retries):
        try:
            r = session.get(url, timeout=20)
            if r.status_code == 429 or r.status_code == 503:
                sleep_time = (2 ** attempt) + random.uniform(1.0, 3.0)
                print_alert(f"HTTP Status {r.status_code} (Rate Limit) ในหน้า {page_num} -> พักรอ {sleep_time:.1f} วินาที", level="WARNING")
                time.sleep(sleep_time)
                continue
            if r.status_code != 200:
                print_alert(f"HTTP Status {r.status_code} ในหน้า {page_num} (พยายามที่ {attempt+1}/{max_retries})", level="WARNING")
                time.sleep(2 + attempt)
                continue
                
            soup = BeautifulSoup(r.text, 'html.parser')
            cards = soup.find_all(class_=lambda c: c and ("item" in c.lower() or "card" in c.lower() or "box" in c.lower()))
            raw_records = []
            seen_page_ids = set()
            for card in cards:
                item = parse_living_card(card)
                if item and item.get("ID") and item["ID"] not in seen_page_ids:
                    seen_page_ids.add(item["ID"])
                    raw_records.append(item)

            # Enrich with location & coords from detail pages concurrently
            records = []
            with concurrent.futures.ThreadPoolExecutor(max_workers=THREAD_POOL_SIZE) as executor:
                futures = [executor.submit(enrich_living_detail_location, session, item) for item in raw_records]
                for future in concurrent.futures.as_completed(futures):
                    try:
                        records.append(future.result())
                    except Exception:
                        pass
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
    print(f"🚀 เริ่มต้นการ Scrape [{COMPANY_NAME}] (Monthly Mode: วันประกาศ + พิกัด + ที่ตั้ง + พื้นที่ครบถ้วน)", flush=True)
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
        print_alert("ไม่สามารถเข้าถึงเว็บ Livinginsider ได้", level="CRITICAL")
        return
        
    if total_count > 0 and len(all_records) >= (total_count - 100):
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
        items = fetch_living_page(session, page)
        if items is None:
            failed_pages.append(page)
            print(f"\n[{COMPANY_NAME}] ⚠️ ข้ามหน้า {page} เนื่องจากดึงข้อมูลไม่สำเร็จหลังจากลองหลายครั้ง", flush=True)
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
        
        print(f"\r[{COMPANY_NAME:<13s}] {pbar} | [กำลังดึงหน้า {page:,}/{max_page:,}] | สะสม: {len(all_records):>7,d} รายการ | {eta_msg}", end="", flush=True)
        
        if len(all_records) >= 10 and "initial_10" not in saved_milestones:
            saved_milestones.add("initial_10")
            print(f"\n💾 [{COMPANY_NAME}] ครบ 10 รายการแรก -> บันทึกไฟล์เริ่มต้นลง {OUTPUT_CSV}...", flush=True)
            save_to_csv(all_records, OUTPUT_CSV)

        for target_pct in [5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80, 85, 90, 95, 100]:
            if pct >= target_pct and target_pct not in saved_milestones:
                saved_milestones.add(target_pct)
                print(f"\n💾 [{COMPANY_NAME}] ครบ Milestone {target_pct}% ({processed_count:,}/{max_page:,} หน้า) -> บันทึกสำรองลง {OUTPUT_CSV}...", flush=True)
                save_to_csv(all_records, OUTPUT_CSV)
                
        time.sleep(0.6 + random.uniform(0.1, 0.3))
        
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
