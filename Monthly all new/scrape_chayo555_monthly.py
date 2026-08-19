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

# -*- coding: utf-8 -*-
"""
Chayo555 NPA Monthly Scraper
Scrapes all NPA properties from https://asset.chayo555.com
Adheres strictly to the 16 standard dashboard columns, GIS reverse geocoding, and monthly export structure.
"""

import os
import re
import sys
import time
import json
import logging
import datetime
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
import urllib3
import pandas as pd
from bs4 import BeautifulSoup

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Set stdout encoding to UTF-8
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Constants
COMPANY_NAME = "Chayo555"
BASE_URL = "https://asset.chayo555.com"
SEARCH_URL = f"{BASE_URL}/search"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "th,en-US;q=0.9,en;q=0.8",
    "Referer": "https://asset.chayo555.com/",
}

# Output directories
_BASE_DIR = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(_BASE_DIR, "CSV_Output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

MONTH_STR = datetime.datetime.now().strftime("%Y_%m")
OUTPUT_CSV = os.path.join(OUTPUT_DIR, f"{COMPANY_NAME}_NPA_New_{MONTH_STR}.csv")

# Standard 21 Columns
COLUMNS = [
    "บริษัท", "ID", "รหัสทรัพย์", "ชื่อโครงการ", "ประเภททรัพย์", "ประเภทการขาย", "ราคา",
    "ตำบล", "อำเภอ", "จังหวัด", "ละติจูด", "ลองจิจูด", "ชื่อประกาศ", "ลิงก์",
    "เนื้อที่ (ตร.ว.)", "พื้นที่ใช้สอย (ตร.ม.)", "วันที่ดึงข้อมูล",
    "ห้องนอน", "ห้องน้ำ", "ที่จอดรถ", "วันประกาศ"
]

# Thailand Provinces for fallback normalization
PROVINCES = [
    "กรุงเทพมหานคร", "กรุงเทพ", "กระบี่", "กาญจนบุรี", "กาฬสินธุ์", "กำแพงเพชร", "ขอนแก่น",
    "จันทบุรี", "ฉะเชิงเทรา", "ชลบุรี", "ชัยนาท", "ชัยภูมิ", "ชุมพร", "เชียงราย", "เชียงใหม่",
    "ตรัง", "ตราด", "ตาก", "นครนายก", "นครปฐม", "นครพนม", "นครราชสีมา", "นครศรีธรรมราช",
    "นครสวรรค์", "นนทบุรี", "นราธิวาส", "น่าน", "บึงกาฬ", "บุรีรัมย์", "ปทุมธานี", "ประจวบคีรีขันธ์",
    "ปราจีนบุรี", "ปัตตานี", "พระนครศรีอยุธยา", "พะเยา", "พังงา", "พัทลุง", "พิจิตร", "พิษณุโลก",
    "เพชรบุรี", "เพชรบูรณ์", "แพร่", "ภูเก็ต", "มหาสารคาม", "มุกดาหาร", "แม่ฮ่องสอน", "ยโสธร",
    "ยะลา", "ร้อยเอ็ด", "ระนอง", "ระยอง", "ราชบุรี", "ลพบุรี", "ลำปาง", "ลำพูน", "เลย", "ศรีสะเกษ",
    "สกลนคร", "สงขลา", "สตูล", "สมุทรปราการ", "สมุทรสงคราม", "สมุทรสาคร", "สระแก้ว", "สระบุรี",
    "สิงห์บุรี", "สุโขทัย", "สุพรรณบุรี", "สุราษฎร์ธานี", "สุรินทร์", "หนองคาย", "หนองบัวลำภู",
    "อ่างทอง", "อำนาจเจริญ", "อุดรธานี", "อุตรดิตถ์", "อุทัยธานี", "อุบลราชธานี"
]

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
        from shapely.geometry import shape, Point
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
            logger.info(f"Loaded {len(_GIS_PROPS):,} GIS subdistrict boundaries & built STRtree.")
    except Exception as e:
        logger.warning(f"Failed to load subdistricts.geojson: {e}")

def reverse_geocode_location(session, lat, lng):
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

def normalize_prop_type(raw_type, title=""):
    combined = f"{raw_type} {title}".lower()
    if any(w in combined for w in ["คอนโด", "ห้องชุด", "อาคารชุด"]):
        return "คอนโด"
    if any(w in combined for w in ["ทาวน์เฮ้าส์", "ทาวน์โฮม", "ทาวน์เฮาส์", "ทฮ"]):
        return "ทาวน์เฮ้าส์"
    if any(w in combined for w in ["บ้านแฝด", "บ้านเดี่ยว/แฝด"]):
        return "บ้านแฝด"
    if any(w in combined for w in ["บ้านเดี่ยว", "บ้านพร้อมที่ดิน", "บ้านพักอาศัย", "บ้าน"]):
        return "บ้านเดี่ยว"
    if any(w in combined for w in ["อาคารพาณิชย์", "ตึกแถว", "โฮมออฟฟิศ", "อาคาร"]):
        return "อาคารพาณิชย์"
    if any(w in combined for w in ["โรงงาน", "โกดัง", "คลังสินค้า"]):
        return "โรงงาน/โกดัง"
    if any(w in combined for w in ["ที่ดิน", "สวน", "ไร่", "นา", "เกษตรกรรม"]):
        return "ที่ดินเปล่า"
    if any(w in combined for w in ["โรงแรม", "รีสอร์ท", "อพาร์ทเม้นท์", "อพาร์ตเมนต์"]):
        return "โรงแรม/รีสอร์ท"
    return "บ้านเดี่ยว" if raw_type else "อื่นๆ"

def parse_chayo_areas(full_text, spec_land="", spec_usable="", prop_type=""):
    land_area = ""
    usable_area = ""

    # 1. Prefer spec_land / spec_usable directly from sidebar if present
    if spec_land and str(spec_land).strip() not in ["", "nan", "None"]:
        clean_l = str(spec_land).strip()
        m_dash = re.search(r'(?<!\d)([0-9]{1,3})\s*-\s*([0-3])\s*-\s*([0-9]{1,2}(?:\.[0-9]+)?)\s*(?:ไร่)?', clean_l)
        m_sqw = re.search(r'([\d\.,]+)\s*(?:ตร\.วา|ตารางวา|ตร\.ว\.|วา)', clean_l)
        if m_dash:
            land_area = f"{m_dash.group(1)} ไร่ {m_dash.group(2)} งาน {m_dash.group(3)} ตร.ว."
        elif m_sqw:
            land_area = f"{m_sqw.group(1).replace(',', '')} ตร.ว."
        elif re.match(r'^\d+(?:\.\d+)?$', clean_l):
            land_area = f"{clean_l} ตร.ว."
        else:
            land_area = clean_l

    if not land_area:
        m_dash = re.search(r'(?:ขนาดที่ดิน|เนื้อที่)\s*[:\s]*([0-9]{1,3})\s*-\s*([0-3])\s*-\s*([0-9]{1,2}(?:\.[0-9]+)?)\s*(?:ไร่)?', full_text)
        m_txt_land = re.search(r'(?:ขนาดที่ดิน|เนื้อที่)\s*[:\s]*((?:\d+\s*ไร่\s*)?(?:\d+\s*งาน\s*)?[\d\.,]+\s*(?:ตร\.วา|ตารางวา|ตร\.ว\.|วา))', full_text)
        if m_dash:
            land_area = f"{m_dash.group(1)} ไร่ {m_dash.group(2)} งาน {m_dash.group(3)} ตร.ว."
        elif m_txt_land:
            land_area = m_txt_land.group(1).strip()
            land_area = re.sub(r'(?<=\d|\s)(?:ตร\.วา|ตารางวา|วา)\b', 'ตร.ว.', land_area)

    # 2. Usable Area
    if spec_usable and str(spec_usable).strip() not in ["", "nan", "None"]:
        m_u = re.search(r'([\d\.,]+)', str(spec_usable))
        if m_u:
            usable_area = m_u.group(1).replace(',', '').strip()

    if not usable_area:
        m_txt_usable = re.search(r'พื้นที่ใช้สอย\s*[:\s]*([\d\.,]+)\s*(?:ตร\.ม\.|ตารางเมตร|sqm)?', full_text)
        if m_txt_usable:
            usable_area = m_txt_usable.group(1).replace(',', '').strip()

    # Apply property type constraints
    if prop_type == "คอนโด":
        land_area = ""
    if prop_type == "ที่ดิน":
        if not any(w in full_text for w in ["ตึก", "อาคาร", "โรงงาน", "โกดัง", "บ้าน", "รีสอร์ท"]):
            usable_area = ""

    if land_area:
        land_area = re.sub(r'\s*วา$', ' ตร.ว.', land_area)
        land_area = re.sub(r'\s*ตารางวา$', ' ตร.ว.', land_area)
        land_area = re.sub(r'\s*ตร\.วา$', ' ตร.ว.', land_area)
        if re.match(r'^\d+(?:\.\d+)?$', land_area):
            land_area = f"{land_area} ตร.ว."

    return land_area, usable_area

def fetch_chayo_detail(session, item_url, preview_data):
    try:
        r = session.get(item_url, headers=HEADERS, verify=False, timeout=20)
        if r.status_code != 200:
            return preview_data

        soup = BeautifulSoup(r.text, 'html.parser')
        full_text = soup.get_text()

        title = ""
        h_title = soup.find(['h1', 'h2', 'h3', 'h4'], class_=re.compile(r'title|name', re.I))
        if h_title:
            title = h_title.get_text().strip()
        if not title:
            t_tag = soup.find('title')
            if t_tag:
                title = t_tag.get_text().split('-')[0].strip()
        if not title:
            title = preview_data.get("ชื่อโครงการ", "")

        code = preview_data.get("รหัสทรัพย์", "")
        if not code or any(ord(c) >= 0x0E00 and ord(c) <= 0x0E7F for c in code):
            # 1. Search for inner_label span with รหัสทรัพย์
            for span in soup.find_all('span', class_=re.compile(r'inner_label', re.I)):
                if 'รหัสทรัพย์' in span.get_text():
                    parent = span.parent
                    if parent:
                        raw = parent.get_text().replace(span.get_text(), '').strip()
                        clean = re.sub(r'[\u0E00-\u0E7F\s]', '', raw).strip()
                        if clean:
                            code = clean
                            break
            # 2. Regex fallback in HTML / full_text
            if not code or any(ord(c) >= 0x0E00 and ord(c) <= 0x0E7F for c in code):
                m_code = re.search(r'รหัสทรัพย์(?:สิน)?\s*(?:</span>)?\s*[\u0E00-\u0E7F\s]*([A-Za-z0-9\-\/_]+)', r.text) or re.search(r'รหัสทรัพย์(?:สิน)?\s*[:\s]*[\u0E00-\u0E7F\s]*([A-Za-z0-9\-\/_]+)', full_text)
                if m_code:
                    code = m_code.group(1).strip()

        price = preview_data.get("ราคา", None)
        m_price = re.search(r'ราคา(?:ขาย)?\s*[:\s]*฿?([\d,]+)', full_text)
        if m_price:
            p_val = m_price.group(1).replace(',', '').strip()
            if p_val.isdigit() and int(p_val) > 0:
                price = float(p_val)

        spec_land = ""
        spec_subdist = ""
        spec_dist = ""
        spec_prov = ""

        for span in soup.find_all('span'):
            txt = span.get_text().strip()
            parent_txt = span.parent.get_text().strip() if span.parent else ""
            if 'เนื้อที่' in txt:
                spec_land = parent_txt.replace(txt, '').strip()
            elif 'แขวง/ตำบล' in txt or 'ตำบล' in txt:
                spec_subdist = parent_txt.replace(txt, '').strip()
            elif 'เขต/อำเภอ' in txt or 'อำเภอ' in txt:
                spec_dist = parent_txt.replace(txt, '').strip()
            elif 'จังหวัด' in txt:
                spec_prov = parent_txt.replace(txt, '').strip()

        if not spec_prov or not spec_dist:
            m_addr = re.search(r'ที่ตั้งทรัพย์\s*[:\s]*(.*?)(?=✨|ขนาด|พื้นที่|$)', full_text, re.DOTALL)
            if m_addr:
                addr_text = m_addr.group(1).strip().replace('\n', ' ')
                m_sd = re.search(r'(?:ตำบล|แขวง)\s*([^\s,]+)', addr_text)
                if m_sd: spec_subdist = m_sd.group(1).strip()
                m_d = re.search(r'(?:อำเภอ|เขต)\s*([^\s,]+)', addr_text)
                if m_d: spec_dist = m_d.group(1).strip()
                m_p = re.search(r'(?:จังหวัด|จ\.)\s*([^\s,]+)', addr_text)
                if m_p: spec_prov = m_p.group(1).strip()

        if not spec_prov:
            for p in PROVINCES:
                if p in title or p in item_url:
                    spec_prov = "กรุงเทพมหานคร" if p == "กรุงเทพ" else p
                    break

        if spec_prov == "กรุงเทพ":
            spec_prov = "กรุงเทพมหานคร"

        lat, lng = None, None
        m_map = re.search(r'(?:query|daddr|q|center|loc|ll)=([0-9\.]+),([0-9\.]+)', r.text)
        if m_map:
            try:
                lat = float(m_map.group(1))
                lng = float(m_map.group(2))
            except Exception:
                pass

        if not lat:
            m_coord = re.search(r'(?:lat|latitude)[=:\s]+([\d\.-]+).*?(?:lng|longitude|lon)[=:\s]+([\d\.-]+)', r.text, re.I)
            if m_coord:
                try:
                    lat = float(m_coord.group(1))
                    lng = float(m_coord.group(2))
                except Exception:
                    pass

        if lat and lng:
            sd_geo, d_geo, p_geo = reverse_geocode_location(session, lat, lng)
            if sd_geo: spec_subdist = sd_geo
            if d_geo: spec_dist = d_geo
            if p_geo: spec_prov = p_geo

        bed = None
        m_bed = re.search(r'(\d+)\s*ห้องนอน', full_text)
        if m_bed:
            try: bed = int(m_bed.group(1))
            except Exception: pass

        bath = None
        m_bath = re.search(r'(\d+)\s*ห้องน้ำ', full_text)
        if m_bath:
            try: bath = int(m_bath.group(1))
            except Exception: pass

        parking = None
        m_park = re.search(r'(\d+)\s*(?:ที่)?จอดรถ', full_text)
        if m_park:
            try: parking = int(m_park.group(1))
            except Exception: pass

        pull_date = datetime.datetime.now().strftime("%Y-%m-%d")
        post_date = ""
        m_date = re.search(r'(?:ประกาศเมื่อ|วันที่ลงประกาศ|สร้างเมื่อ)\s*[:\s]*(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})', full_text)
        if m_date:
            post_date = m_date.group(1).strip()

        prop_type = normalize_prop_type(preview_data.get("ประเภททรัพย์", ""), title)
        land_area, usable_area = parse_chayo_areas(full_text, spec_land=spec_land, prop_type=prop_type)

        return {
            "บริษัท": COMPANY_NAME,
            "ID": code or item_url.split('/')[-1],
            "รหัสทรัพย์": code or item_url.split('/')[-1],
            "ชื่อโครงการ": title,
            "ประเภททรัพย์": prop_type,
            "ประเภทการขาย": "ขาย",
            "ราคา": price,
            "ตำบล": spec_subdist,
            "อำเภอ": spec_dist,
            "จังหวัด": spec_prov,
            "ละติจูด": lat,
            "ลองจิจูด": lng,
            "ชื่อประกาศ": title,
            "ลิงก์": item_url,
            "เนื้อที่ (ตร.ว.)": convert_to_rai_ngan_wah(land_area),
            "พื้นที่ใช้สอย (ตร.ม.)": usable_area,
            "วันที่ดึงข้อมูล": pull_date,
            "ห้องนอน": bed,
            "ห้องน้ำ": bath,
            "ที่จอดรถ": parking,
            "วันประกาศ": post_date
        }
    except Exception as e:
        logger.warning(f"Error fetching detail {item_url}: {e}")
        return preview_data

def scrape_chayo555(progress_callback=None):
    logger.info("=" * 65)
    logger.info("🚀 Starting Chayo555 NPA Monthly Scraper")
    logger.info("=" * 65)

    session = requests.Session()
    discovered_items = {}

    categories = ['', '1', '2', '3', '4', '5', '6', '18', '33', '34']
    widgets = ['2', '3', '4', '5', '6', '11', '12']

    total_tasks = len(categories) + len(widgets)
    completed_tasks = 0

    logger.info("📡 Scanning Chayo555 category & widget listings...")
    for cat_id in categories:
        url = f"{SEARCH_URL}?term_condition=1&q=&category={cat_id}&start_price=0&end_price=760&geography=&province=&district=&sys_lang_id=1"
        try:
            r = session.get(url, headers=HEADERS, verify=False, timeout=20)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, 'html.parser')
                for a in soup.find_all('a', href=True):
                    href = a['href']
                    txt = a.get_text().strip()
                    if 'รหัสทรัพย์สิน' in txt and href.startswith('http'):
                        if href not in discovered_items:
                            m_code = re.search(r'รหัสทรัพย์สิน\s*([A-Za-z0-9\-\/_]+)', txt)
                            m_price = re.search(r'ราคาขาย\s*฿?([\d,]+)', txt)
                            price_val = None
                            if m_price:
                                try: price_val = float(m_price.group(1).replace(',', ''))
                                except Exception: pass
                            discovered_items[href] = {
                                "url": href,
                                "รหัสทรัพย์": m_code.group(1) if m_code else "",
                                "ราคา": price_val,
                                "ประเภททรัพย์": "",
                                "ชื่อโครงการ": href.split('/')[-1].replace('-', ' ')
                            }
        except Exception as e:
            logger.warning(f"Error checking category {cat_id}: {e}")
        completed_tasks += 1
        if progress_callback:
            progress_callback(int((completed_tasks / total_tasks) * 30), f"Scanning listings ({len(discovered_items)} found)")

    for w_id in widgets:
        url = f"{SEARCH_URL}?term_condition=1&q=&category=&start_price=0&end_price=760&geography=&province=&district=&widgets={w_id}&sys_lang_id=1"
        try:
            r = session.get(url, headers=HEADERS, verify=False, timeout=20)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, 'html.parser')
                for a in soup.find_all('a', href=True):
                    href = a['href']
                    txt = a.get_text().strip()
                    if 'รหัสทรัพย์สิน' in txt and href.startswith('http'):
                        if href not in discovered_items:
                            m_code = re.search(r'รหัสทรัพย์สิน\s*([A-Za-z0-9\-\/_]+)', txt)
                            m_price = re.search(r'ราคาขาย\s*฿?([\d,]+)', txt)
                            price_val = None
                            if m_price:
                                try: price_val = float(m_price.group(1).replace(',', ''))
                                except Exception: pass
                            discovered_items[href] = {
                                "url": href,
                                "รหัสทรัพย์": m_code.group(1) if m_code else "",
                                "ราคา": price_val,
                                "ประเภททรัพย์": "",
                                "ชื่อโครงการ": href.split('/')[-1].replace('-', ' ')
                            }
        except Exception as e:
            logger.warning(f"Error checking widget {w_id}: {e}")
        completed_tasks += 1
        if progress_callback:
            progress_callback(int((completed_tasks / total_tasks) * 30), f"Scanning listings ({len(discovered_items)} found)")

    total_discovered = len(discovered_items)
    logger.info(f"🎯 Total unique Chayo555 listings discovered: {total_discovered:,}")

    records = []
    logger.info(f"⚡ Fetching {total_discovered} property detail pages with ThreadPoolExecutor...")
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {
            executor.submit(fetch_chayo_detail, session, url, data): url
            for url, data in discovered_items.items()
        }
        done_count = 0
        for fut in as_completed(futures):
            try:
                res = fut.result()
                if res:
                    records.append(res)
            except Exception as e:
                logger.warning(f"Thread error: {e}")
            done_count += 1
            if done_count % 25 == 0 or done_count == total_discovered:
                logger.info(f"  Processed {done_count}/{total_discovered} detail pages ({done_count/total_discovered*100:.1f}%)")
            if progress_callback:
                pct = 30 + int((done_count / max(1, total_discovered)) * 70)
                progress_callback(pct, f"Scraped {done_count}/{total_discovered} items")

    df = pd.DataFrame(records)
    for col in COLUMNS:
        if col not in df.columns:
            df[col] = ""
    df = df[COLUMNS]

    df.drop_duplicates(subset=["รหัสทรัพย์", "ชื่อโครงการ"], inplace=True)
    df.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")
    logger.info("=" * 65)
    logger.info(f"🎉 Chayo555 scraping complete! Saved {len(df):,} records to:")
    logger.info(f"📁 {OUTPUT_CSV}")
    logger.info("=" * 65)

    return df

main = scrape_chayo555

if __name__ == "__main__":
    main()
