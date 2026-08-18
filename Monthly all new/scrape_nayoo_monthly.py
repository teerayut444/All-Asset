# -*- coding: utf-8 -*-
"""
NaYoo (น่าอยู่) Monthly Scraper
Scrapes all Secondhand properties (~10,711) and Project listings (~3,528) from https://api.nayoo.co
Adheres strictly to the 16 standard dashboard columns, GIS reverse geocoding, gazetteer lookup, and monthly export structure.
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
COMPANY_NAME = "NaYoo"
API_BASE = "https://api.nayoo.co"
API_KEY = "bf78c26f3bde3729d957df5e00682b4f67e15dcb1ef0a62127403669b0d01ee3"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://nayoo.co",
    "Referer": "https://nayoo.co/",
    "apikey": API_KEY,
}

# Output directories
_BASE_DIR = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(_BASE_DIR, "CSV_Output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

MONTH_STR = datetime.datetime.now().strftime("%Y_%m")
OUTPUT_CSV = os.path.join(OUTPUT_DIR, f"{COMPANY_NAME}_NPA_New_{MONTH_STR}.csv")

# Standard 16 Columns
COLUMNS = [
    "บริษัท", "ID", "รหัสทรัพย์", "ชื่อโครงการ", "ประเภททรัพย์",
    "ประเภทการขาย", "ราคา", "ตำบล", "อำเภอ", "จังหวัด",
    "ละติจูด", "ลองจิจูด", "ชื่อประกาศ", "เนื้อที่ (ตร.ว.)",
    "พื้นที่ใช้สอย (ตร.ม.)", "ห้องนอน", "ห้องน้ำ", "วันที่ลงประกาศ", "ลิงก์"
]

# Thailand Province Slug Mapping
PROVINCE_SLUG_MAP = {
    'rayong': 'ระยอง',
    'chonburi': 'ชลบุรี',
    'khonkaen': 'ขอนแก่น',
    'udon': 'อุดรธานี',
    'huahin': 'ประจวบคีรีขันธ์',
    'buriram': 'บุรีรัมย์',
    'phitsanulok': 'พิษณุโลก',
    'ubon': 'อุบลราชธานี',
    'chiangrai': 'เชียงราย',
    'surin': 'สุรินทร์',
    'bangkok': 'กรุงเทพมหานคร'
}

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

# GIS Boundary & Gazetteer Cache
_GIS_SUBDISTRICTS = None
_DISTRICTS_BY_PROV = None
_SUBDIST_TO_DIST = None

def _load_gis():
    global _GIS_SUBDISTRICTS, _DISTRICTS_BY_PROV, _SUBDIST_TO_DIST
    if _GIS_SUBDISTRICTS is not None:
        return _GIS_SUBDISTRICTS, _DISTRICTS_BY_PROV, _SUBDIST_TO_DIST

    geojson_path = os.path.join(_BASE_DIR, "subdistricts.geojson")
    if not os.path.exists(geojson_path):
        geojson_path = os.path.join(os.path.dirname(_BASE_DIR), "Monthly all new", "subdistricts.geojson")

    _GIS_SUBDISTRICTS = []
    _DISTRICTS_BY_PROV = {}
    _SUBDIST_TO_DIST = {}

    if os.path.exists(geojson_path):
        try:
            with open(geojson_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                _GIS_SUBDISTRICTS = data.get("features", [])
                for feat in _GIS_SUBDISTRICTS:
                    props = feat.get("properties", {})
                    p = props.get("pro_th") or props.get("province_th") or props.get("province") or ""
                    d = props.get("amp_th") or props.get("district_th") or props.get("district") or ""
                    sd = props.get("tam_th") or props.get("subdistrict_th") or props.get("subdistrict") or ""
                    if p not in _DISTRICTS_BY_PROV: _DISTRICTS_BY_PROV[p] = set()
                    if d: _DISTRICTS_BY_PROV[p].add(d.replace("อำเภอ", "").replace("เขต", "").strip())
                    if sd and d: _SUBDIST_TO_DIST[(p, sd.replace("ตำบล", "").replace("แขวง", "").strip())] = d.replace("อำเภอ", "").replace("เขต", "").strip()
                logger.info(f"Loaded {len(_GIS_SUBDISTRICTS):,} GIS subdistrict boundaries & gazetteer.")
        except Exception as e:
            logger.warning(f"Failed to load subdistricts.geojson: {e}")

    return _GIS_SUBDISTRICTS, _DISTRICTS_BY_PROV, _SUBDIST_TO_DIST

def _point_in_poly(x, y, poly):
    n = len(poly)
    inside = False
    p1x, p1y = poly[0]
    for i in range(n + 1):
        p2x, p2y = poly[i % n]
        if y > min(p1y, p2y):
            if y <= max(p1y, p2y):
                if x <= max(p1x, p2x):
                    if p1y != p2y:
                        xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    if p1x == p2x or x <= xinters:
                        inside = not inside
        p1x, p1y = p2x, p2y
    return inside

def _check_geom(lng, lat, geom):
    gtype = geom.get("type")
    coords = geom.get("coordinates", [])
    if gtype == "Polygon":
        if coords and _point_in_poly(lng, lat, coords[0]):
            return True
    elif gtype == "MultiPolygon":
        for poly in coords:
            if poly and _point_in_poly(lng, lat, poly[0]):
                return True
    return False

def reverse_geocode_location(session, lat, lng):
    if not lat or not lng:
        return "", "", ""
    try:
        lat_f = float(lat)
        lng_f = float(lng)
    except Exception:
        return "", "", ""

    features, _, _ = _load_gis()
    for feat in features:
        props = feat.get("properties", {})
        geom = feat.get("geometry", {})
        if _check_geom(lng_f, lat_f, geom):
            sd = props.get("tam_th") or props.get("subdistrict_th") or props.get("subdistrict") or ""
            d = props.get("amp_th") or props.get("district_th") or props.get("district") or ""
            p = props.get("pro_th") or props.get("province_th") or props.get("province") or ""
            if p == "กรุงเทพมหานคร":
                sd = sd.replace("ตำบล", "แขวง")
                d = d.replace("อำเภอ", "เขต")
            return sd, d, p

    return "", "", ""

def resolve_nayoo_location(title, zone, p_slug):
    _, districts_by_prov, subdist_to_dist = _load_gis()
    prov = PROVINCE_SLUG_MAP.get(str(p_slug).lower(), "")
    subdist = str(zone).strip() if zone and zone != "None" else ""
    dist = ""

    if str(p_slug).lower() == "huahin":
        prov = "ประจวบคีรีขันธ์"
        dist = "หัวหิน"

    combined = f"{title} {subdist}".replace("อำเภอ", " ").replace("เขต", " ")

    # 1. Check direct regex in title
    m_d = re.search(r'(?:ใน)?(?:อำเภอ|เขต)\s*([^\s,]+)', f"{title} {zone}")
    if m_d:
        d_cand = m_d.group(1).strip()
        if prov and prov in districts_by_prov:
            for real_d in districts_by_prov[prov]:
                if real_d in d_cand or d_cand in real_d:
                    dist = real_d
                    break
        if not dist:
            dist = d_cand

    m_sd = re.search(r'(?:ใน)?(?:ตำบล|แขวง)\s*([^\s,]+)', f"{title} {zone}")
    if m_sd:
        sd_cand = m_sd.group(1).strip()
        subdist = sd_cand

    # 2. Check if zone or title matches a known district in province
    if prov and prov in districts_by_prov:
        if not dist:
            for real_d in sorted(districts_by_prov[prov], key=len, reverse=True):
                if real_d in f"{title} {zone}":
                    dist = real_d
                    break

        # 3. Check if zone or title matches a known subdistrict in province
        for (p_k, sd_k), d_v in subdist_to_dist.items():
            if p_k == prov and sd_k in f"{title} {zone}":
                if not subdist or subdist == zone:
                    subdist = sd_k
                if not dist:
                    dist = d_v
                break

    # 4. Fallback for "ในเมือง" or "ตัวเมือง"
    if not dist and ("ในเมือง" in subdist or "ตัวเมือง" in subdist or "เซ็นทรัล" in subdist):
        if prov:
            dist = f"เมือง{prov}"

    # Normalize Province
    if not prov:
        for p in PROVINCES:
            if p in combined:
                prov = "กรุงเทพมหานคร" if p == "กรุงเทพ" else p
                break

    if prov == "กรุงเทพ":
        prov = "กรุงเทพมหานคร"

    return subdist, dist, prov

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
        return "ที่ดิน"
    if any(w in combined for w in ["โรงแรม", "รีสอร์ท", "อพาร์ทเม้นท์", "อพาร์ตเมนต์", "หอพัก"]):
        return "โรงแรม/รีสอร์ท"
    return "บ้านเดี่ยว" if raw_type else "อื่นๆ"

def parse_nayoo_areas(raw_land, raw_usable, title="", prop_type=""):
    combined = f"{raw_land} {raw_usable} {title}"
    land_area = ""
    usable_area = ""

    # 1. Parse Land Area
    if raw_land and str(raw_land).strip() not in ["", "nan", "None", "0"]:
        clean_l = str(raw_land).strip()
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

    if not land_area and title:
        m_dash = re.search(r'(?:ขนาดที่ดิน|เนื้อที่)?\s*([0-9]{1,3})\s*-\s*([0-3])\s*-\s*([0-9]{1,2}(?:\.[0-9]+)?)\s*(?:ไร่)?', title)
        m_txt_land = re.search(r'((?:\d+\s*ไร่\s*)?(?:\d+\s*งาน\s*)?[\d\.,]+\s*(?:ตร\.วา|ตารางวา|ตร\.ว\.|วา))', title)
        if m_dash and any(w in title for w in ["ไร่", "เนื้อที่", "ที่ดิน"]):
            land_area = f"{m_dash.group(1)} ไร่ {m_dash.group(2)} งาน {m_dash.group(3)} ตร.ว."
        elif m_txt_land:
            land_area = m_txt_land.group(1).strip()
            land_area = re.sub(r'(?<=\d|\s)(?:ตร\.วา|ตารางวา|วา)\b', 'ตร.ว.', land_area)

    # 2. Parse Usable Area (Filter out dummy 1.0 placeholder)
    if raw_usable and str(raw_usable).strip() not in ["", "nan", "None", "0"]:
        try:
            u_val = float(str(raw_usable).replace(',', '').strip())
            if u_val > 1.0:
                usable_area = f"{u_val:g}"
        except Exception:
            pass

    if not usable_area and title:
        m_txt_usable = re.search(r'([\d\.,]+)\s*(?:ตร\.ม\.|ตารางเมตร|sqm)\b', title, re.I)
        if m_txt_usable:
            try:
                u_val = float(m_txt_usable.group(1).replace(',', '').strip())
                if u_val > 1.0:
                    usable_area = f"{u_val:g}"
            except Exception:
                pass

    # Apply property type constraints
    if prop_type == "คอนโด":
        land_area = ""
    if prop_type == "ที่ดิน":
        if not any(w in combined for w in ["ตึก", "อาคาร", "โรงงาน", "โกดัง", "บ้าน", "รีสอร์ท"]):
            usable_area = ""

    if land_area:
        land_area = re.sub(r'\s*วา$', ' ตร.ว.', land_area)
        land_area = re.sub(r'\s*ตารางวา$', ' ตร.ว.', land_area)
        land_area = re.sub(r'\s*ตร\.วา$', ' ตร.ว.', land_area)
        if re.match(r'^\d+(?:\.\d+)?$', land_area):
            land_area = f"{land_area} ตร.ว."

    return land_area, usable_area

def fetch_nayoo_page(session, endpoint, page, per_page=36):
    url = f"{API_BASE}{endpoint}"
    params = {"page": page, "per_page": per_page}
    try:
        r = session.get(url, headers=HEADERS, params=params, timeout=25)
        if r.status_code == 200:
            return r.json()
        elif r.status_code == 401:
            logger.error("NaYoo API 401 Unauthorized - Check API Key!")
    except Exception as e:
        logger.warning(f"Error fetching NaYoo {endpoint} p{page}: {e}")
    return None

def process_nayoo_item(session, item):
    pid = str(item.get("id") or item.get("uuid") or "").strip()
    if not pid or pid == "None":
        return None

    # Title
    p_name = item.get("project_name", {})
    title = p_name.get("th") if isinstance(p_name, dict) else (item.get("title") or "")
    if isinstance(title, dict):
        title = title.get("th") or title.get("en") or ""
    if not title:
        title = item.get("slug", "").replace("-", " ")
    if not title:
        return None

    # Property Type
    raw_type = ""
    p_info = item.get("project_info", {})
    if isinstance(p_info, dict):
        p_types = p_info.get("property_type", [])
        if isinstance(p_types, list) and p_types:
            first_pt = p_types[0]
            if isinstance(first_pt, dict):
                raw_type = first_pt.get("name", {}).get("th", "") or first_pt.get("slug", "")
    if not raw_type and item.get("property_type"):
        pt_val = item.get("property_type")
        if isinstance(pt_val, dict):
            raw_type = pt_val.get("name", {}).get("th") or pt_val.get("slug", "")
        elif isinstance(pt_val, str):
            raw_type = pt_val
    prop_type = normalize_prop_type(raw_type, title)

    # Price
    pricing = item.get("pricing", {}) or {}
    price = None
    if isinstance(pricing, dict):
        p_val = pricing.get("sale_price") or pricing.get("starting_price") or pricing.get("promotion_price")
        if p_val and str(p_val).replace('.', '').isdigit():
            try: price = float(p_val)
            except Exception: pass
    if not price and item.get("price"):
        try: price = float(item.get("price"))
        except Exception: pass

    # Functions (Bed, Bath, Area)
    funcs = item.get("functions", {}) or {}
    bed = funcs.get("bedrooms") if isinstance(funcs, dict) else None
    bath = funcs.get("bathrooms") if isinstance(funcs, dict) else None
    raw_land = funcs.get("land_area") if isinstance(funcs, dict) else ""
    raw_usable = funcs.get("usable_area") if isinstance(funcs, dict) else ""

    land_area, usable_area = parse_nayoo_areas(raw_land, raw_usable, title=title, prop_type=prop_type)

    # Location & Coordinates
    p_obj = item.get("province", {})
    p_slug = p_obj.get("slug", "") if isinstance(p_obj, dict) else str(p_obj)
    zone = item.get("zone", "") or ""

    subdist, dist, prov = resolve_nayoo_location(title, zone, p_slug)

    coords = item.get("coordinates")
    lat, lng = None, None
    if isinstance(coords, list) and len(coords) >= 2:
        try:
            lat = float(coords[0])
            lng = float(coords[1])
        except Exception:
            pass

    # Reverse Geocode with GIS if coordinates present
    if lat and lng:
        sd_geo, d_geo, p_geo = reverse_geocode_location(session, lat, lng)
        if sd_geo: subdist = sd_geo
        if d_geo: dist = d_geo
        if p_geo: prov = p_geo

    # Dates
    post_date = ""
    dt_str = item.get("created_at") or item.get("updated_at") or ""
    if dt_str:
        try:
            post_date = str(dt_str)[:10]
        except Exception:
            pass

    # URL Link
    item_slug = item.get("slug", "")
    if item_slug:
        link = f"https://nayoo.co/property-for-sale/properties/{p_slug or 'khonkaen'}/{item_slug}"
    else:
        link = f"https://nayoo.co/posts/{pid}"

    return {
        "บริษัท": COMPANY_NAME,
        "ID": pid,
        "รหัสทรัพย์": pid,
        "ชื่อโครงการ": title,
        "ประเภททรัพย์": prop_type,
        "ประเภทการขาย": "ขาย",
        "ราคา": price,
        "ตำบล": subdist,
        "อำเภอ": dist,
        "จังหวัด": prov,
        "ละติจูด": lat,
        "ลองจิจูด": lng,
        "ชื่อประกาศ": title,
        "เนื้อที่ (ตร.ว.)": land_area,
        "พื้นที่ใช้สอย (ตร.ม.)": usable_area,
        "ห้องนอน": bed,
        "ห้องน้ำ": bath,
        "วันที่ลงประกาศ": post_date,
        "ลิงก์": link
    }

def scrape_nayoo(progress_callback=None):
    logger.info("=" * 65)
    logger.info("🚀 Starting NaYoo (น่าอยู่) Monthly Scraper")
    logger.info("=" * 65)

    session = requests.Session()
    # Ensure GIS is pre-loaded
    _load_gis()

    all_records = []
    endpoints = [
        ("/api/listing/search/secondhands", "Secondhands"),
        ("/api/listing/search/projects", "Projects")
    ]

    total_tasks = 0
    ep_configs = []

    # Determine pagination for both endpoints
    for ep, ep_label in endpoints:
        res1 = fetch_nayoo_page(session, ep, page=1, per_page=36)
        if not res1 or not res1.get("success"):
            logger.warning(f"Failed to fetch initial page for {ep_label}")
            continue

        pag = res1.get("data", {}).get("pagination", {})
        total_items = pag.get("total_items") or pag.get("total") or 0
        items_per_page = pag.get("items_per_page") or 36
        total_pages = (total_items + items_per_page - 1) // items_per_page
        
        logger.info(f"📊 [{ep_label}] Total items: {total_items:,} -> {total_pages:,} pages")
        
        posts1 = res1.get("data", {}).get("posts", []) or res1.get("data", {}).get("projects", []) or []
        for p in posts1:
            rec = process_nayoo_item(session, p)
            if rec: all_records.append(rec)

        ep_configs.append((ep, ep_label, total_pages))
        total_tasks += total_pages

    completed_pages = len(ep_configs)
    logger.info(f"⚡ Concurrently fetching {total_tasks:,} pages across all endpoints...")

    with ThreadPoolExecutor(max_workers=15) as executor:
        future_to_page = {}
        for ep, ep_label, total_pages in ep_configs:
            for p_num in range(2, total_pages + 1):
                f = executor.submit(fetch_nayoo_page, session, ep, page=p_num, per_page=36)
                future_to_page[f] = (ep_label, p_num)

        for fut in as_completed(future_to_page):
            ep_label, p_num = future_to_page[fut]
            try:
                p_res = fut.result()
                if p_res and p_res.get("success"):
                    p_posts = p_res.get("data", {}).get("posts", []) or p_res.get("data", {}).get("projects", []) or []
                    for item in p_posts:
                        rec = process_nayoo_item(session, item)
                        if rec:
                            all_records.append(rec)
            except Exception as e:
                logger.warning(f"Error on {ep_label} p{p_num}: {e}")

            completed_pages += 1
            if completed_pages % 25 == 0 or completed_pages == total_tasks:
                pct = int((completed_pages / max(1, total_tasks)) * 100)
                logger.info(f"  Processed {completed_pages}/{total_tasks} pages ({pct}%) - Records: {len(all_records):,}")
                if progress_callback:
                    progress_callback(pct, f"Scraped {len(all_records):,} items")

    # Convert to DataFrame
    df = pd.DataFrame(all_records)
    for col in COLUMNS:
        if col not in df.columns:
            df[col] = ""
    df = df[COLUMNS]

    # Clean & Deduplicate
    df.dropna(subset=["ID", "ชื่อโครงการ"], inplace=True)
    df.drop_duplicates(subset=["ID"], inplace=True)
    df.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")

    logger.info("=" * 65)
    logger.info(f"🎉 NaYoo scraping complete! Saved {len(df):,} records to:")
    logger.info(f"📁 {OUTPUT_CSV}")
    logger.info("=" * 65)

    return df

main = scrape_nayoo

if __name__ == "__main__":
    main()
