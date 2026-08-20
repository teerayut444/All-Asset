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

COMPANY_NAME = "Taladnudbaan"
MONTH_STR = datetime.now().strftime("%Y_%m")

_BASE_DIR = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(_BASE_DIR, "CSV_Output")
os.makedirs(OUTPUT_DIR, exist_ok=True)
OUTPUT_CSV = os.path.join(OUTPUT_DIR, f"Taladnudbaan_NPA_New_{MONTH_STR}.csv")

BASE_URL = "https://www.taladnudbaan.com/properties?page={page_num}"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "th,en-US;q=0.9,en;q=0.8",
    "Referer": "https://www.taladnudbaan.com/"
}

COLUMNS = [
    "บริษัท", "ID", "รหัสทรัพย์", "ชื่อโครงการ", "ประเภททรัพย์", "ประเภทการขาย", "ราคา",
    "ตำบล", "อำเภอ", "จังหวัด", "ละติจูด", "ลองจิจูด", "ชื่อประกาศ", "ลิงก์",
    "เนื้อที่ (ตร.ว.)", "พื้นที่ใช้สอย (ตร.ม.)", "วันที่ดึงข้อมูล",
    "ห้องนอน", "ห้องน้ำ", "ที่จอดรถ", "วันประกาศ"
]

ITEMS_PER_PAGE = 20
THREAD_POOL_SIZE = 3

# GIS Boundary Engine Cache
_GIS_TREE = None
_GIS_PROPS = None

SPECIAL_TAM_CLEAN = {
    'เทศบาลนครสมุทรปร': 'ปากน้ำ',
    'เทศบาลบางปู': 'บางปูใหม่',
    'เทศบาลบางเมือง': 'บางเมือง',
    'เทศบาลเมืองพระปร': 'ตลาด',
    'เทศบาลสำโรงใต้': 'สำโรงใต้',
    'เขตการปกคองพิเศษ': 'เมืองพัทยา',
    'ท่าเรือ (เทศบาลเมื': 'ท่าเรือ',
    'เทศบาลเมืองทุ่งส': 'ปากแพรก'
}

def _init_gis():
    global _GIS_TREE, _GIS_PROPS
    if _GIS_TREE is not None:
        return
    try:
        from shapely.geometry import shape
        from shapely.strtree import STRtree
        
        geojson_path = os.path.join(_BASE_DIR, "subdistricts.geojson")
        if not os.path.exists(geojson_path):
            geojson_path = os.path.join(os.path.dirname(_BASE_DIR), "subdistricts.geojson")
        
        if os.path.exists(geojson_path):
            with open(geojson_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            geoms = []
            props = []
            for feat in data.get("features", []):
                geom = shape(feat["geometry"])
                geoms.append(geom)
                p = feat.get("properties", {})
                tam = p.get("tam_th", "").strip()
                amp = p.get("amp_th", "").strip()
                pro = p.get("pro_th", "").strip()
                if tam in SPECIAL_TAM_CLEAN:
                    tam = SPECIAL_TAM_CLEAN[tam]
                if "กรุงเทพ" in pro:
                    pro = "กรุงเทพมหานคร"
                props.append((tam, amp, pro))
            _GIS_PROPS = props
            _GIS_TREE = STRtree(geoms)
            print(f"[{COMPANY_NAME}] 🗺️ Loaded {len(_GIS_PROPS):,} GIS subdistrict boundaries & built STRtree.", flush=True)
    except Exception as e:
        print_alert(f"Failed to load subdistricts.geojson: {e}", level="WARNING")

def reverse_geocode_location(lat, lng):
    if not lat or not lng:
        return "", "", ""
    try:
        lat_f = float(lat)
        lng_f = float(lng)
        if not (5.0 < lat_f < 21.0 and 97.0 < lng_f < 106.0):
            return "", "", ""
        _init_gis()
        if _GIS_TREE is not None and _GIS_PROPS is not None:
            from shapely.geometry import Point
            pt = Point(lng_f, lat_f)
            res = _GIS_TREE.query(pt, predicate='intersects')
            if len(res) > 0:
                g_idx = res[0]
                return _GIS_PROPS[g_idx]
            else:
                nearest = _GIS_TREE.query_nearest(pt)
                if len(nearest) > 0:
                    import numpy as np
                    g_idx = nearest[0] if not isinstance(nearest[0], (list, tuple, np.ndarray)) else nearest[1][0]
                    return _GIS_PROPS[g_idx]
    except Exception:
        pass
    return "", "", ""

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

def format_eta(elapsed_sec, pages_done_session, total_pages_left):
    if pages_done_session <= 0 or total_pages_left <= 0 or elapsed_sec <= 0:
        return "กำลังคำนวณ..."
    rate = pages_done_session / elapsed_sec
    if rate <= 0:
        return "กำลังคำนวณ..."
    eta_sec = total_pages_left / rate
    finish_clock = datetime.fromtimestamp(datetime.now().timestamp() + eta_sec).strftime("%H:%M:%S")
    mins = int(eta_sec // 60)
    secs = int(eta_sec % 60)
    if mins >= 60:
        hrs = mins // 60
        mins = mins % 60
        return f"เหลือเวลาอีก ~{hrs} ชม. {mins} นาที (เสร็จประมาณ {finish_clock} น.)"
    elif mins > 0:
        return f"เหลือเวลาอีก ~{mins} นาที {secs} วินาที (เสร็จประมาณ {finish_clock} น.)"
    else:
        return f"เหลือเวลาอีก ~{secs} วินาที (เสร็จประมาณ {finish_clock} น.)"

def clean_text(val):
    if not val or str(val).strip().lower() in ["none", "null", "undefined"]:
        return ""
    return re.sub(r"\s+", " ", str(val)).strip()

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
            print(f"[{COMPANY_NAME}] 🔄 Smart Resume: โหลดข้อมูลเดิมจาก {filename} พบ {len(records):,} รายการ", flush=True)
        except Exception as e:
            print_alert(f"ไม่สามารถอ่านไฟล์สะสมเดิม {filename}: {e}", level="WARNING")
    return records, seen_ids

def check_link_health(session):
    url = BASE_URL.format(page_num=1)
    for attempt in range(5):
        try:
            r = session.get(url, timeout=20)
            status_code = r.status_code
            if status_code == 200:
                soup = BeautifulSoup(r.text, 'html.parser')
                page_links = soup.find_all('a', href=re.compile(r'page=\d+'))
                pages = []
                for a in page_links:
                    m = re.search(r'page=(\d+)', a['href'])
                    if m:
                        val = int(m.group(1))
                        if val <= 20000:
                            pages.append(val)
                max_p = max(pages) if pages else 8631
                tot_est = max_p * ITEMS_PER_PAGE
                return True, status_code, tot_est, max_p
        except Exception as e:
            time.sleep(2 + attempt)
    return False, 0, 0, 0

def fetch_talad_detail(session, item):
    link = item.get("ลิงก์")
    if not link:
        return item
        
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"}
    max_retries = 5
    for attempt in range(max_retries):
        try:
            time.sleep(random.uniform(0.3, 0.6))
            r = session.get(link, headers=headers, timeout=30)
            if r.status_code == 429 or r.status_code == 503:
                sleep_time = (2 ** attempt) + random.uniform(2.0, 5.0)
                time.sleep(sleep_time)
                continue
            if r.status_code != 200:
                time.sleep(1 + attempt)
                continue
                
            html = r.text
            soup = BeautifulSoup(html, 'html.parser')
            main_box = soup.find(class_=re.compile(r'card-body|content|detail', re.I)) or soup
            main_text = main_box.get_text()
                
            # 1. Lat/Lng (JS properties object, data-lat/lng, gmap iframe or html regex)
            lat_v, lng_v = None, None
            m_lat = re.search(r'Lat\s*:\s*\[\s*["\']([\d\.-]+)["\']\s*\]', html, re.I) or re.search(r'lat[a-z_]*["\']?\s*[:=]\s*["\']?([\d\.-]+)', html, re.I) or re.search(r'data-lat=["\']([\d\.-]+)["\']', html, re.I)
            m_lng = re.search(r'Lng\s*:\s*\[\s*["\']([\d\.-]+)["\']\s*\]', html, re.I) or re.search(r'lng[a-z_]*["\']?\s*[:=]\s*["\']?([\d\.-]+)', html, re.I) or re.search(r'data-lng=["\']([\d\.-]+)["\']', html, re.I)
                
            if m_lat and m_lng:
                try:
                    lat_cand = float(m_lat.group(1))
                    lng_cand = float(m_lng.group(1))
                    if 5.0 <= lat_cand <= 21.0 and 97.0 <= lng_cand <= 106.0:
                        lat_v, lng_v = lat_cand, lng_cand
                except Exception: pass
                    
            if not lat_v:
                m_gmap = re.search(r'(?:q|center|ll|location|place)=([\d\.-]+)%2C([\d\.-]+)', html, re.I) or re.search(r'(?:q|center|ll|location|place)=([\d\.-]+),([\d\.-]+)', html, re.I) or re.search(r'@([\d\.-]+),([\d\.-]+)', html)
                if m_gmap:
                    try:
                        lat_cand = float(m_gmap.group(1))
                        lng_cand = float(m_gmap.group(2))
                        if 5.0 <= lat_cand <= 21.0 and 97.0 <= lng_cand <= 106.0:
                            lat_v, lng_v = lat_cand, lng_cand
                    except Exception: pass
                        
            if lat_v and lng_v:
                item["ละติจูด"] = lat_v
                item["ลองจิจูด"] = lng_v
                # 1.1 Primary Location: Reverse Geocode via GIS Polygon STRtree from Coordinates
                tam_gis, amp_gis, pro_gis = reverse_geocode_location(lat_v, lng_v)
                if pro_gis:
                    item["ตำบล"] = tam_gis
                    item["อำเภอ"] = amp_gis
                    item["จังหวัด"] = pro_gis
                        
            # 2. Location Fallback (from Breadcrumbs & Regex) if coordinates are missing or GIS unmapped
            if not item.get("จังหวัด") or not item.get("อำเภอ"):
                bc_items = []
                bc_ol = soup.find('ol', class_=re.compile(r'breadcrumb', re.I)) or soup.find(class_=re.compile(r'breadcrumb', re.I))
                if bc_ol:
                    for li in bc_ol.find_all(['li', 'a']):
                        t = clean_text(li.get_text())
                        if t and t not in bc_items and not t.isdigit() and len(t) < 35:
                            bc_items.append(t)
                                
                # Filter out breadcrumb navigation keywords AND the item ID itself
                item_id_str = str(item.get("ID") or "").strip()
                filtered_bc = [x for x in bc_items if x not in ["หน้าหลัก", "รายการทรัพย์", "Home", item_id_str] and not x.isdigit()]
                    
                # Breadcrumbs structure: [ประเภททรัพย์, จังหวัด, อำเภอ, ตำบล]
                if len(filtered_bc) >= 4:
                    if not item.get("จังหวัด"): item["จังหวัด"] = filtered_bc[1]
                    if not item.get("อำเภอ"): item["อำเภอ"] = filtered_bc[2]
                    if not item.get("ตำบล"): item["ตำบล"] = filtered_bc[3]
                elif len(filtered_bc) == 3:
                    if not item.get("จังหวัด"): item["จังหวัด"] = filtered_bc[1]
                    if not item.get("อำเภอ"): item["อำเภอ"] = filtered_bc[2]
                elif len(filtered_bc) == 2:
                    if not item.get("จังหวัด"): item["จังหวัด"] = filtered_bc[1]
                        
                # Multiline Regex Fallback for Location if missing
                if not item.get("ตำบล") or item.get("ตำบล") == item_id_str:
                    m_sd = re.search(r'(?:แขวง\s*/\s*ตำบล|ตำบล|แขวง)\s*[:\s]*[\n\r]*([^\n\r<"\|]{2,30})', main_text)
                    if m_sd and clean_text(m_sd.group(1)):
                        item["ตำบล"] = clean_text(m_sd.group(1))
                    else:
                        item["ตำบล"] = ""
                        
                if not item.get("อำเภอ") or item.get("อำเภอ") == item_id_str:
                    m_d = re.search(r'(?:เขต\s*/\s*อำเภอ|อำเภอ|เขต)\s*[:\s]*[\n\r]*([^\n\r<"\|]{2,30})', main_text)
                    if m_d and clean_text(m_d.group(1)):
                        item["อำเภอ"] = clean_text(m_d.group(1))
                        
                if not item.get("จังหวัด") or item.get("จังหวัด") == item_id_str:
                    m_p = re.search(r'จังหวัด\s*[:\s]*[\n\r]*([^\n\r<"\|]{2,30})', main_text)
                    if m_p and clean_text(m_p.group(1)):
                        item["จังหวัด"] = clean_text(m_p.group(1))

            # --- 2.5 Mapping ID & รหัสทรัพย์ ---
            # ในเว็บ: "รหัสทรัพย์" คือ ID จริงของเว็บ (เช่น ALPHA211228378981) -> ใส่ช่อง ID
            # ในเว็บ: "รหัสหน่วยงาน" คือ รหัสอ้างอิงทรัพย์ (เช่น L4_6_0520_G01) -> ใส่ช่อง รหัสทรัพย์
            m_code_prop = re.search(r'รหัสทรัพย์\s*[:\s]*([^\n\r<"\|]+)', html)
            if m_code_prop:
                real_id = clean_text(m_code_prop.group(1))
                if real_id:
                    item["ID"] = real_id

            m_code_agency = re.search(r'รหัสหน่วยงาน\s*[:\s]*([^\n\r<"\|]+)', html)
            if m_code_agency:
                agency_code = clean_text(m_code_agency.group(1))
                if agency_code:
                    item["รหัสทรัพย์"] = agency_code
                
            # 3. Land Area (ไร่-งาน-วา / ตร.ว.)
            m_land = re.search(r'(?:ขนาดที่ดิน|เนื้อที่)\s*:\s*([^\n\r<"]+)', main_text)
            if m_land:
                land_str = m_land.group(1).strip()
                if any(w in land_str for w in ["ไร่", "งาน", "วา", "ตร.ว.", "ตารางวา"]):
                    clean_l = re.sub(r'(?<=\d|\s)(?:ตร\.วา|ตารางวา|วา)\b', 'ตร.ว.', land_str)
                    item["เนื้อที่ (ตร.ว.)"] = clean_l
                    
            # 4. Usable Area (ตร.ม.)
            m_u = re.search(r'ขนาดพื้นที่ใช้สอย\s*:\s*([^\n\r<"]+)', main_text) or re.search(r'พื้นที่ใช้สอย\s*:\s*([^\n\r<"]+)', main_text)
            if m_u:
                u_clean = re.sub(r'[^\d\.]', '', m_u.group(1)).strip('.')
                if u_clean: item["พื้นที่ใช้สอย (ตร.ม.)"] = u_clean
                    
            # 5. Posted / Completed Date (วันประกาศ)
            m_post = re.search(r'(?:โพสวันที่|สร้างเมื่อ|วันที่ประกาศ|สร้างเสร็จปี|ปรับปรุงวันที่)\s*[:\s]*([^\n\r<"]+)', main_text)
            if m_post:
                item["วันประกาศ"] = clean_text(m_post.group(1))
                    
            # 7. Refine Property Type, Project Name and Compose Full Listing Title
            h1_elem = soup.find('h1')
            h1_text = clean_text(h1_elem.get_text()) if h1_elem else ""
                
            ptype = detect_talad_property_type(link, h1_text, main_text)
            item["ประเภททรัพย์"] = ptype
                
            m_proj = re.search(r'(?:ชื่อโครงการ|โครงการ)\s*:\s*([^\n\r<"]+)', main_text)
            if m_proj:
                p_cand = clean_text(m_proj.group(1))
                if p_cand and p_cand.lower() not in ["none", "null", "-", "/", "โครงการ", "หมู่บ้าน"]:
                    item["ชื่อโครงการ"] = p_cand
            else:
                item["ชื่อโครงการ"] = ""  # Leave blank if no project name exists
                    
            # Compose informative title from Type + Location
            loc_parts = [x for x in [item.get("ตำบล"), item.get("อำเภอ"), item.get("จังหวัด")] if x]
            if loc_parts:
                item["ชื่อประกาศ"] = f"{ptype} {' '.join(loc_parts)}".strip()
            else:
                item["ชื่อประกาศ"] = f"{ptype} ({item.get('ID', '')})".strip()
                
            break
        except Exception as e:
            sleep_time = (2 ** attempt) + random.uniform(1.0, 3.0)
            time.sleep(sleep_time)
    return item

def detect_talad_property_type(link, title="", text=""):
    link_l = str(link or "").lower()
    
    # 1. Strict URL Path Matching
    if "commercial-building" in link_l or "shophouse" in link_l:
        return "อาคารพาณิชย์"
    if "condominium" in link_l or "condo" in link_l:
        return "คอนโด"
    if "plant-storage" in link_l or "factory" in link_l or "warehouse" in link_l:
        return "โรงงาน/โกดัง"
    if "single-house" in link_l or "detached-house" in link_l:
        return "บ้านเดี่ยว"
    if "town-home" in link_l or "townhome" in link_l or "townhouse" in link_l:
        return "ทาวน์โฮม"
    if "land" in link_l:
        return "ที่ดินเปล่า"
    if "apartment" in link_l:
        return "อพาร์ทเม้นท์"
        
    # 2. Text / Title Fallback Matching
    text_l = f"{title} {text}".lower()
    if "อาคารพาณิชย์" in text_l or "ตึกแถว" in text_l:
        return "อาคารพาณิชย์"
    if "คอนโด" in text_l:
        return "คอนโด"
    if "โรงงาน" in text_l or "โกดัง" in text_l:
        return "โรงงาน/โกดัง"
    if "บ้านเดี่ยว" in text_l or "บ้านแฝด" in text_l:
        return "บ้านเดี่ยว"
    if "ทาวน์โฮม" in text_l or "ทาวน์เฮ้าส์" in text_l:
        return "ทาวน์โฮม"
    if "ที่ดิน" in text_l:
        return "ที่ดินเปล่า"
    if "อพาร์ทเม้นท์" in text_l or "หอพัก" in text_l:
        return "อพาร์ทเม้นท์"
        
    return "บ้านเดี่ยว"

COMPANY_MAP = {
    "BAM": "BAM",
    "SAM": "SAM",
    "GHB": "ธอส.",
    "KBANK": "กสิกรไทย",
    "LED": "กรมบังคับคดี",
    "SCB": "ไทยพาณิชย์",
    "BAY": "กรุงศรีอยุธยา",
    "KTB": "กรุงไทย",
    "TTB": "ทหารไทยธนชาต",
    "GSB": "ออมสิน"
}

def extract_talad_source_company(link):
    m = re.search(r'/property/[^/]+/([^/]+)/', str(link or ""))
    if m:
        code = m.group(1).upper()
        name = COMPANY_MAP.get(code, code)
        return code, name
    return "", ""

def parse_talad_card(card):
    try:
        a_tag = card.find('a', href=re.compile(r'/property/'))
        if not a_tag:
            return None
        link = a_tag['href']
        if not link.startswith('http'):
            link = 'https://www.taladnudbaan.com' + link
            
        m_id = re.search(r'/property/[^/]+/[^/]+/([^\s\?/]+)', link)
        item_id = m_id.group(1) if m_id else link.split('/')[-1]
        
        code, source_company = extract_talad_source_company(link)
        company_val = source_company if source_company else COMPANY_NAME
        
        title_tag = card.find(class_=lambda c: c and ("title" in c.lower() or "name" in c.lower() or "card-title" in c.lower()))
        title = clean_text(title_tag.text) if title_tag else ""
        
        price_tag = card.find(class_=lambda c: c and ("price" in c.lower() or "card-price" in c.lower()))
        price_str = clean_text(price_tag.text) if price_tag else ""
        price_clean = re.sub(r"[^\d\.]", "", price_str.replace(",", ""))
        price = float(price_clean) if price_clean else None
        
        prop_type = detect_talad_property_type(link, title)
            
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        return {
            "บริษัท": company_val,
            "ID": item_id,
            "รหัสทรัพย์": item_id,
            "ชื่อโครงการ": "",  # Leave blank if no project name
            "ประเภททรัพย์": prop_type,
            "ประเภทการขาย": "ขาย",
            "ราคา": price,
            "ตำบล": "",
            "อำเภอ": "",
            "จังหวัด": "",
            "ละติจูด": None,
            "ลองจิจูด": None,
            "ชื่อประกาศ": title,
            "ลิงก์": link,
            "เนื้อที่ (ตร.ว.)": convert_to_rai_ngan_wah(""),
            "พื้นที่ใช้สอย (ตร.ม.)": "",
            "วันที่ดึงข้อมูล": now_str,
            "วันประกาศ": "",
            "ห้องนอน": None,
            "ห้องน้ำ": None,
            "ที่จอดรถ": None
        }
    except Exception:
        return None

STATE_FILE = os.path.join(OUTPUT_DIR, f".taladnudbaan_state_{MONTH_STR}.json")

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("last_processed_page", 0), data.get("skipped_bamsam", 0)
        except Exception:
            pass
    return 0, 0

def save_state(last_page, skipped_bamsam=0):
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump({"last_processed_page": last_page, "skipped_bamsam": skipped_bamsam}, f)
    except Exception:
        pass

def fetch_talad_page(session, page_num):
    url = BASE_URL.format(page_num=page_num)
    max_retries = 8
    for attempt in range(max_retries):
        try:
            r = session.get(url, timeout=30)
            if r.status_code == 429 or r.status_code == 503:
                sleep_time = (2 ** min(attempt, 5)) + random.uniform(3.0, 8.0)
                ts = datetime.now().strftime("%H:%M:%S")
                print(f"\n[{ts}] [{COMPANY_NAME}] ⚠️ HTTP {r.status_code} (Rate Limit) หน้า {page_num} (ครั้งที่ {attempt+1}/{max_retries}) -> พักรอ {sleep_time:.1f} วินาที", flush=True)
                time.sleep(sleep_time)
                continue
            if r.status_code != 200:
                sleep_time = 3 + attempt * 2 + random.uniform(1.0, 3.0)
                ts = datetime.now().strftime("%H:%M:%S")
                print(f"\n[{ts}] [{COMPANY_NAME}] ⚠️ HTTP {r.status_code} หน้า {page_num} (ครั้งที่ {attempt+1}/{max_retries}) -> พัก {sleep_time:.1f} วินาที", flush=True)
                time.sleep(sleep_time)
                continue
                
            soup = BeautifulSoup(r.text, 'html.parser')
            cards = soup.find_all(class_=lambda c: c and ("card" in c.lower() or "property" in c.lower() or "item" in c.lower()))
            raw_records = []
            seen_page_ids = set()
            skipped_bamsam = 0
            for card in cards:
                item = parse_talad_card(card)
                if item and item.get("ID") and item["ID"] not in seen_page_ids:
                    code, _ = extract_talad_source_company(item.get("ลิงก์"))
                    if code in ["BAM", "SAM"]:
                        skipped_bamsam += 1
                        continue  # Skip BAM & SAM to prevent duplication with official BAM & SAM scrapers
                    seen_page_ids.add(item["ID"])
                    raw_records.append(item)
                    
            # Fetch detail pages sequentially with small delay to avoid overwhelming server
            records = []
            with concurrent.futures.ThreadPoolExecutor(max_workers=THREAD_POOL_SIZE) as executor:
                futures = [executor.submit(fetch_talad_detail, session, item) for item in raw_records]
                for future in futures:
                    try:
                        records.append(future.result())
                    except Exception:
                        pass
            return records, skipped_bamsam
        except Exception as e:
            sleep_time = (2 ** min(attempt, 5)) + random.uniform(3.0, 8.0)
            ts = datetime.now().strftime("%H:%M:%S")
            print(f"\n[{ts}] [{COMPANY_NAME}] ⚠️ เกิดข้อผิดพลาดหน้า {page_num} (ครั้งที่ {attempt+1}/{max_retries}): {e} -> พัก {sleep_time:.1f} วินาที", flush=True)
            time.sleep(sleep_time)
    return None, 0

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
        net_est = max(0, total_count - 22575)
        status_msg = f"🌐 สถานะลิงก์: ปกติ (HTTP {code}) | ทั้งหมด {max_page:,} หน้า ({total_count:,} รายการ) | สแครปจริง ~{net_est:,} รายการ (ยกเว้น BAM ~17,907 & SAM ~4,668 รายการ)"
        print(f"[{COMPANY_NAME}] {status_msg}", flush=True)
    else:
        print_alert("ไม่สามารถเข้าถึงเว็บ Taladnudbaan ได้", level="CRITICAL")
        return
        
    if total_count > 0 and len(all_records) >= (total_count - 50):
        print(f"[{COMPANY_NAME}] 🎉 ข้อมูลใน CSV ครบถ้วน 100% แล้ว ({len(all_records):,}/{total_count:,} รายการ) -> สแครปเสร็จสมบูรณ์ทันที!", flush=True)
        save_to_csv(all_records, OUTPUT_CSV)
        return
    
    saved_milestones = set()
    failed_pages = []
    
    start_time = time.time()
    
    items_per_p = ITEMS_PER_PAGE
    last_page_saved, total_skipped = load_state()
    completed_pages = max(last_page_saved, min(max_page - 1, len(all_records) // items_per_p))
    processed_count = completed_pages
    new_added = 0
    
    start_page = completed_pages + 1
    pages_order = list(range(start_page, max_page + 1))
    if completed_pages > 0:
        print(f"[{COMPANY_NAME}] ⏩ Fast-Forward Resume: ข้าม {completed_pages:,} หน้าแรกที่เคยดึงแล้ว -> เริ่มสแครปหน้า {start_page:,} ต่อทันที", flush=True)
    
    def process_page(page):
        nonlocal total_skipped, processed_count, new_added
        if total_count > 0 and len(all_records) >= total_count:
            return False  # signal to stop
        items, skipped_bamsam = fetch_talad_page(session, page)
        total_skipped += skipped_bamsam
        if items is None:
            failed_pages.append(page)
            ts = datetime.now().strftime("%H:%M:%S")
            print(f"\n[{ts}] [{COMPANY_NAME}] ⚠️ ข้ามหน้า {page} ชั่วคราว (จะกลับมาดึงใหม่ภายหลัง)", flush=True)
            processed_count += 1
            save_state(page, total_skipped)
            return True

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
        pages_done_session = processed_count - completed_pages
        remaining_pages = max(0, max_page - processed_count)
        pct = int((processed_count / max_page) * 100)
        elapsed_sec = time.time() - start_time
        eta_msg = format_eta(elapsed_sec, pages_done_session, remaining_pages)
        pbar = make_progress_bar(pct)
        
        print(f"\r[{COMPANY_NAME:<13s}] {pbar} | ({processed_count:5,d}/{max_page:5,d} หน้า) | สะสม: {len(all_records):>6,d} รายการ (คัด BAM/SAM ออกแล้ว {total_skipped:,} รายการ) | ⏱️ {eta_msg}", end="", flush=True)
        
        if len(all_records) >= 10 and "initial_10" not in saved_milestones:
            saved_milestones.add("initial_10")
            print(f"\n💾 [{COMPANY_NAME}] ครบ 10 รายการแรก -> บันทึกไฟล์เริ่มต้นลง {OUTPUT_CSV}...", flush=True)
            save_to_csv(all_records, OUTPUT_CSV)
            save_state(page, total_skipped)

        for target_pct in [5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80, 85, 90, 95, 100]:
            if pct >= target_pct and target_pct not in saved_milestones:
                saved_milestones.add(target_pct)
                print(f"\n💾 [{COMPANY_NAME}] ครบ Milestone {target_pct}% ({processed_count:,}/{max_page:,} หน้า) -> บันทึกสำรองลง {OUTPUT_CSV} (สะสมใน CSV: {len(all_records):,} รายการ | คัด BAM/SAM ออกแล้ว: {total_skipped:,} รายการ)...", flush=True)
                save_to_csv(all_records, OUTPUT_CSV)
                save_state(page, total_skipped)
                
        time.sleep(1.0 + random.uniform(0.3, 1.0))
        return True

    # --- Main page loop ---
    for page in pages_order:
        if not process_page(page):
            print(f"\n[{COMPANY_NAME}] 🎉 สะสมข้อมูลครบถ้วนทั้งหมดแล้ว ({len(all_records):,}/{total_count:,} รายการ) -> สิ้นสุดการสแครป!", flush=True)
            break

    # --- Retry failed pages (up to 3 rounds) ---
    for retry_round in range(1, 4):
        if not failed_pages:
            break
        retry_list = list(failed_pages)
        failed_pages.clear()
        print(f"\n🔄 [{COMPANY_NAME}] Retry รอบที่ {retry_round}: กลับมาดึง {len(retry_list)} หน้าที่ล้มเหลว... (พักรอ 15 วินาทีก่อนเริ่ม)", flush=True)
        time.sleep(15)  # Rest before retrying to let server cool down
        for page in retry_list:
            process_page(page)
            time.sleep(2.0 + random.uniform(0.5, 1.5))  # Extra delay for retries
        
    print("", flush=True)
    save_to_csv(all_records, OUTPUT_CSV)
    save_state(max_page, total_skipped)
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
