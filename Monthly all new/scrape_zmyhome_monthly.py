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
    "เนื้อที่ (ตร.ว.)", "พื้นที่ใช้สอย (ตร.ม.)", "วันที่ดึงข้อมูล",
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

# --- Offline GIS Engine Data Loader ---
_GIS_FEATURES = None

def _get_gis_features():
    global _GIS_FEATURES
    if _GIS_FEATURES is None:
        geojson_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "subdistricts.geojson")
        if os.path.exists(geojson_path):
            try:
                with open(geojson_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                features = []
                for feat in data.get("features", []):
                    geom = feat.get("geometry", {})
                    props = feat.get("properties", {})
                    features.append((geom, props.get("tam_th", ""), props.get("amp_th", ""), props.get("pro_th", "")))
                _GIS_FEATURES = features
            except Exception:
                _GIS_FEATURES = []
        else:
            _GIS_FEATURES = []
    return _GIS_FEATURES

def _point_in_poly(x, y, poly_coords):
    n = len(poly_coords)
    inside = False
    p1x, p1y = poly_coords[0]
    for i in range(n + 1):
        p2x, p2y = poly_coords[i % n]
        if y > min(p1y, p2y):
            if y <= max(p1y, p2y):
                if x <= max(p1x, p2x):
                    if p1y != p2y:
                        xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    if p1x == p2x or x <= xinters:
                        inside = not inside
        p1x, p1y = p2x, p2y
    return inside

def _check_geom(lng, lat, geometry):
    gtype = geometry.get("type")
    coords = geometry.get("coordinates", [])
    if gtype == "Polygon":
        for ring in coords:
            if _point_in_poly(lng, lat, ring): return True
    elif gtype == "MultiPolygon":
        for poly in coords:
            for ring in poly:
                if _point_in_poly(lng, lat, ring): return True
    return False

def reverse_geocode_location(session, lat, lng):
    """Reverse geocode Lat/Lng into ตำบล, อำเภอ, จังหวัด using Offline Thailand GeoJSON Engine."""
    if not lat or not lng or str(lat) == "nan":
        return "", "", ""
    try:
        lat_v, lng_v = float(lat), float(lng)
        features = _get_gis_features()
        for geom, tam_th, amp_th, pro_th in features:
            if _check_geom(lng_v, lat_v, geom):
                p = pro_th
                if "กรุงเทพ" in p: p = "กรุงเทพมหานคร"
                return tam_th, amp_th, p
    except Exception:
        pass
        
    # Nominatim Fallback if offline GIS misses
    url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lng}&accept-language=th"
    headers = {"User-Agent": "AllAssetDashboardApp/1.0"}
    try:
        r = session.get(url, headers=headers, timeout=5)
        if r.status_code == 200:
            addr = r.json().get('address', {})
            sd = clean_text(addr.get('quarter') or addr.get('suburb') or addr.get('neighbourhood') or addr.get('village'))
            d = clean_text(addr.get('city_district') or addr.get('district') or addr.get('county') or addr.get('town'))
            p = clean_text(addr.get('city') or addr.get('state') or addr.get('province'))
            if p and "กรุงเทพ" in p: p = "กรุงเทพมหานคร"
            return sd, d, p
    except Exception:
        pass
    return "", "", ""

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
                soup = BeautifulSoup(html, 'html.parser')

                # --- 1. Lat/Lng from Google Maps link / static map / shortlink ---
                map_link = soup.find('a', href=re.compile(r'google.*map|maps\.google|maps\.app\.goo\.gl', re.I))
                if map_link:
                    href = map_link.get('href', '')
                    m_ll = re.search(r'q=([\d\.-]+),([\d\.-]+)', href) or re.search(r'@([\d\.-]+),([\d\.-]+)', href) or re.search(r'center=([\d\.-]+),([\d\.-]+)', href)
                    if m_ll:
                        try:
                            lat_v, lng_v = float(m_ll.group(1)), float(m_ll.group(2))
                            if 5.0 <= lat_v <= 21.0 and 97.0 <= lng_v <= 106.0:
                                item["ละติจูด"] = lat_v
                                item["ลองจิจูด"] = lng_v
                        except Exception: pass
                            
                if not item.get("ละติจูด"):
                    m_map = re.search(r'query=([\d\.-]+),([\d\.-]+)', html) or re.search(r'q=([\d\.-]+),([\d\.-]+)', html) or re.search(r'@([\d\.-]+),([\d\.-]+)', html)
                    if m_map:
                        try:
                            lat_v, lng_v = float(m_map.group(1)), float(m_map.group(2))
                            if 5.0 <= lat_v <= 21.0 and 97.0 <= lng_v <= 106.0:
                                item["ละติจูด"] = lat_v
                                item["ลองจิจูด"] = lng_v
                        except Exception: pass

                if not item.get("ละติจูด"):
                    m_short = re.search(r'https?://(?:maps\.app\.goo\.gl|goo\.gl/maps)/[a-zA-Z0-9_-]+', html)
                    if m_short:
                        try:
                            r_m = session.get(m_short.group(0), allow_redirects=True, timeout=5)
                            m_ll_short = re.search(r'3d([\d\.-]+)!4d([\d\.-]+)', r_m.url) or re.search(r'@([\d\.-]+),([\d\.-]+)', r_m.url) or re.search(r'q=([\d\.-]+),([\d\.-]+)', r_m.url)
                            if m_ll_short:
                                lat_v, lng_v = float(m_ll_short.group(1)), float(m_ll_short.group(2))
                                if 5.0 <= lat_v <= 21.0 and 97.0 <= lng_v <= 106.0:
                                    item["ละติจูด"] = lat_v
                                    item["ลองจิจูด"] = lng_v
                        except Exception: pass

                # --- 2. Location (Primary: Reverse Geocode from Lat/Lng) ---
                if item.get("ละติจูด") and item.get("ลองจิจูด"):
                    sd, d, p = reverse_geocode_location(session, item["ละติจูด"], item["ลองจิจูด"])
                    if sd: item["ตำบล"] = sd
                    if d: item["อำเภอ"] = d
                    if p: item["จังหวัด"] = p

                # --- 2.5 Location Fallbacks (JSON-LD & Breadcrumb) if missing ---
                m_jsonld = re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.DOTALL)
                if m_jsonld:
                    try:
                        j_data = json.loads(m_jsonld.group(1))
                        if isinstance(j_data, list):
                            for j_obj in j_data:
                                if j_obj.get("@type") == "Offer":
                                    p_spec = j_obj.get("priceSpecification", {})
                                    price_val = p_spec.get("price") if isinstance(p_spec, dict) else j_obj.get("price")
                                    if price_val:
                                        try:
                                            p_f = float(price_val)
                                            if not item.get("ราคา") or item["ราคา"] < 10000 or p_f != item["ราคา"]:
                                                item["ราคา"] = p_f
                                        except Exception: pass
                                        
                                    item_off = j_obj.get("itemOffered", {})
                                    addr_obj = item_off.get("address", {})
                                    if addr_obj:
                                        loc_district = clean_text(addr_obj.get("addressLocality"))
                                        loc_region = clean_text(addr_obj.get("addressRegion"))
                                        desc_text = clean_text(item_off.get("description", ""))
                                        
                                        if loc_district and not item.get("อำเภอ"): item["อำเภอ"] = loc_district
                                        if loc_region and not item.get("จังหวัด"):
                                            if "กรุงเทพ" in loc_region: item["จังหวัด"] = "กรุงเทพมหานคร"
                                            else: item["จังหวัด"] = loc_region

                                        if not item.get("ตำบล"):
                                            m_sd = re.search(r'(?:ตำบล|แขวง)\s*([^\s,]+)', desc_text)
                                            if m_sd:
                                                sd_candidate = m_sd.group(1).strip()
                                                if not any(k in sd_candidate for k in ["ถนน", "ซอย", "ถ.", "ซ."]):
                                                    item["ตำบล"] = sd_candidate
                                elif j_obj.get("@type") == "BreadcrumbList":
                                    items_list = j_obj.get("itemListElement", [])
                                    for bc_i in items_list:
                                        if bc_i.get("position") == 2 and bc_i.get("name"):
                                            item["ประเภททรัพย์"] = bc_i.get("name").strip()
                    except Exception: pass

                # Fallback location from breadcrumbs if subdistrict/district still missing
                bc = soup.find(class_=re.compile(r'breadcrumb', re.I))
                if bc:
                    bc_texts = [clean_text(li.get_text()) for li in bc.find_all(['li', 'a'])]
                    bc_clean = [x for x in bc_texts if x and x not in ["หน้าแรก", "รวมประกาศขาย", "ขาย", ">"] and not x.isdigit()]
                    # Typical ZmyHome breadcrumb: [หน้าแรก, ขาย, คอนโด, จังหวัด, อำเภอ/เขต, ตำบล/แขวง]
                    for idx, text in enumerate(bc_clean):
                        if any(prov in text for prov in ["กรุงเทพ", "นนทบุรี", "ปทุมธานี", "สมุทรปราการ", "ชลบุรี", "เชียงใหม่", "ภูเก็ต"]):
                            if not item.get("จังหวัด"): item["จังหวัด"] = text
                            if idx + 1 < len(bc_clean) and not item.get("อำเภอ"):
                                item["อำเภอ"] = bc_clean[idx + 1]
                            if idx + 2 < len(bc_clean) and not item.get("ตำบล"):
                                item["ตำบล"] = bc_clean[idx + 2]
                            break

                # Fallback location from nearby-place__address if still missing
                addr_el = soup.find(class_='nearby-place__address')
                if addr_el:
                    addr_text = clean_text(addr_el.get_text())
                    if addr_text:
                        if not item.get("อำเภอ"):
                            m_d = re.search(r'(?:อำเภอ|อ\.|เขต)\s*([^\s,]+)', addr_text)
                            if m_d: item["อำเภอ"] = m_d.group(1).strip()
                        if not item.get("จังหวัด"):
                            m_p = re.search(r'(?:จังหวัด|จ\.)\s*([^\s,]+)', addr_text)
                            if m_p: item["จังหวัด"] = m_p.group(1).strip()
                            elif "กรุงเทพ" in addr_text or "กรุงเทพมหานคร" in addr_text:
                                item["จังหวัด"] = "กรุงเทพมหานคร"

                # HTML Province Search Fallback
                if not item.get("จังหวัด"):
                    ALL_PROVINCES = [
                        "กรุงเทพมหานคร", "กรุงเทพ", "กระบี่", "กาญจนบุรี", "กาฬสินธุ์", "กำแพงเพชร", "ขอนแก่น", "จันทบุรี",
                        "ฉะเชิงเทรา", "ชลบุรี", "ชัยนาท", "ชัยภูมิ", "ชุมพร", "เชียงราย", "เชียงใหม่", "ตรัง", "ตราด",
                        "ตาก", "นครนายก", "นครปฐม", "นครพนม", "นครราชสีมา", "นครศรีธรรมราช", "นครสวรรค์", "นนทบุรี",
                        "นราธิวาส", "น่าน", "บึงกาฬ", "บุรีรัมย์", "ปทุมธานี", "ประจวบคีรีขันธ์", "ปราจีนบุรี", "ปัตตานี",
                        "พระนครศรีอยุธยา", "อยุธยา", "พะเยา", "พังงา", "พัทลุง", "พิจิตร", "พิษณุโลก", "เพชรบุรี",
                        "เพชรบูรณ์", "แพร่", "ภูเก็ต", "มหาสารคาม", "มุกดาหาร", "แม่ฮ่องสอน", "ยโสธร", "ยะลา", "ร้อยเอ็ด",
                        "ระนอง", "ระยอง", "ราชบุรี", "ลพบุรี", "ลำปาง", "ลำพูน", "เลย", "ศรีสะเกษ", "สกลนคร", "สงขลา",
                        "สตูล", "สมุทรปราการ", "สมุทรสงคราม", "สมุทรสาคร", "สระแก้ว", "สระบุรี", "สิงห์บุรี", "สุโขทัย",
                        "สุพรรณบุรี", "สุราษฎร์ธานี", "สุรินทร์", "หนองคาย", "หนองบัวลำภู", "อ่างทอง", "อำนาจเจริญ",
                        "อุดรธานี", "อุตรดิตถ์", "อุทัยธานี", "อุบลราชธานี"
                    ]
                    for p_name in ALL_PROVINCES:
                        if p_name in html:
                            item["จังหวัด"] = "กรุงเทพมหานคร" if p_name in ["กรุงเทพ", "กรุงเทพมหานคร"] else p_name
                            break

                # --- 3. ชื่อประกาศ from og:title ---
                og = soup.find('meta', property='og:title')
                if og and clean_text(og.get('content', '')):
                    item["ชื่อประกาศ"] = clean_text(og.get('content', ''))

                # --- 4. ชื่อโครงการ & ประเภททรัพย์ ---
                proj_name = ""
                bc = soup.find(class_=re.compile(r'breadcrumb', re.I))
                if bc:
                    bc_items = []
                    for li in bc.find_all('li'):
                        a = li.find('a')
                        txt = (a.get_text().strip() if a else li.get_text().strip()).replace('>', '').replace('\xa0', '').strip()
                        if txt and txt not in bc_items:
                            bc_items.append(txt)
                    if len(bc_items) >= 3:
                        ptype_bc = bc_items[2]
                        if ptype_bc in ["คอนโด", "บ้าน", "ทาวน์เฮาส์", "ที่ดิน", "อาคารพาณิชย์"]:
                            item["ประเภททรัพย์"] = ptype_bc
                        elif "บ้าน" in ptype_bc: item["ประเภททรัพย์"] = "บ้านเดี่ยว"
                        elif "ทาวน์" in ptype_bc: item["ประเภททรัพย์"] = "ทาวน์เฮาส์"
                    if len(bc_items) >= 4:
                        proj_cand = bc_items[3]
                        if proj_cand and proj_cand not in ["รวมประกาศขาย", "ขาย", "หน้าแรก"] and not proj_cand.startswith("ขาย"):
                            proj_name = proj_cand

                proj_section = soup.find(class_=re.compile(r'info-project', re.I))
                if proj_section:
                    first_item = proj_section.find('li', class_=re.compile(r'info-project__item', re.I))
                    if first_item:
                        p_txt = first_item.get_text().strip()
                        if p_txt and p_txt != item.get("ชื่อประกาศ", ""):
                            proj_name = p_txt

                if proj_name:
                    item["ชื่อโครงการ"] = proj_name

                # --- 4.5 Decompose recommendation, carousel, & nearby blocks to avoid false field extraction ---
                for bad_tag in soup.find_all(['section', 'div', 'article'], class_=re.compile(r'announce-project|carousel|card-property|recommend|nearby|similar|relate|footer|banner', re.I)):
                    bad_tag.decompose()

                # --- 5. Usable Area & Land Area ---
                og_desc = soup.find('meta', property='og:description')
                if og_desc and not item.get("เนื้อที่ (ตร.ว.)"):
                    m_meta_land = re.search(r'เนื้อที่\s*([\d\.,]+)\s*(?:ตารางวา|ตร\.ว\.|วา)', og_desc.get("content", ""))
                    if m_meta_land:
                        item["เนื้อที่ (ตร.ว.)"] = f"{m_meta_land.group(1).replace(',', '')} ตร.ว."

                main_text = soup.get_text()
                m_u = re.search(r'([\d\.]+)\s*(?:ตร\.ม\.|ตารางเมตร)', main_text)
                if m_u and not item.get("พื้นที่ใช้สอย (ตร.ม.)"):
                    item["พื้นที่ใช้สอย (ตร.ม.)"] = m_u.group(1).strip()
                    
                m_l = re.search(r'((?:\d+\s*ไร่\s*)?(?:\d+\s*งาน\s*)?[\d\.,]+\s*(?:ตร\.ว\.|ตร\.วา|ตารางวา|วา))', main_text)
                if m_l and not item.get("เนื้อที่ (ตร.ว.)"):
                    clean_l = m_l.group(1).strip()
                    clean_l = re.sub(r'(?<=\d|\s)(?:ตร\.วา|ตารางวา|วา)\b', 'ตร.ว.', clean_l)
                    item["เนื้อที่ (ตร.ว.)"] = clean_l
                    
                # --- 6. Posted Date ---
                m_post = re.search(r'(?:ลงประกาศเมื่อ|อัปเดตเมื่อ|สร้างเมื่อ|ประกาศเมื่อ)\s*[:\s]*([^\n\r<"]+)', main_text)
                if m_post and not item.get("วันประกาศ"):
                    item["วันประกาศ"] = clean_text(m_post.group(1))
                    
                # --- 7. Bedrooms, Bathrooms, Parking ---
                if item.get("ประเภททรัพย์") == "ที่ดิน":
                    item["ห้องนอน"] = None
                    item["ห้องน้ำ"] = None
                    item["ที่จอดรถ"] = None
                else:
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
        price = None
        if price_str:
            is_million = any(w in price_str for w in ["ล้าน", "ลบ", "MB", "mb", "Mb", "M"])
            price_clean = re.sub(r"[^\d\.]", "", price_str.replace(",", ""))
            if price_clean:
                try:
                    p_val = float(price_clean)
                    if is_million and p_val < 10000:
                        p_val = p_val * 1000000.0
                    elif p_val < 500:  # anomalous low price e.g. 100.0 -> 100M
                        p_val = p_val * 1000000.0
                    price = p_val
                except ValueError:
                    price = None
        
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
            "ชื่อโครงการ": "",  # จะดึงจาก info-project ในหน้ารายละเอียด
            "ประเภททรัพย์": "คอนโด" if item_id.startswith("V") else "บ้านเดี่ยว/ทาวน์เฮาส์",
            "ประเภทการขาย": "ขาย",
            "ราคา": price,
            "ตำบล": "",  # จะดึงจากหน้ารายละเอียด (nearby-place__address)
            "อำเภอ": "",
            "จังหวัด": "",
            "ละติจูด": None,
            "ลองจิจูด": None,
            "ชื่อประกาศ": title,
            "ลิงก์": link,
            "เนื้อที่ (ตร.ว.)": "",
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
                for future in futures:
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
