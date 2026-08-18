# -*- coding: utf-8 -*-
"""
NaYoo (น่าอยู่) Monthly Scraper
Scrapes both Secondhand properties and Project listings from https://api.nayoo.co
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

# Thailand Provinces
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
_GIS_SUBDISTRICTS = None

def _get_gis_features():
    global _GIS_SUBDISTRICTS
    if _GIS_SUBDISTRICTS is not None:
        return _GIS_SUBDISTRICTS
    
    geojson_path = os.path.join(CURRENT_DIR, "subdistricts.geojson")
    if not os.path.exists(geojson_path):
        geojson_path = os.path.join(os.path.dirname(CURRENT_DIR), "Monthly all new", "subdistricts.geojson")
    
    if os.path.exists(geojson_path):
        try:
            with open(geojson_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                _GIS_SUBDISTRICTS = data.get("features", [])
                logger.info(f"Loaded {len(_GIS_SUBDISTRICTS):,} GIS subdistrict boundaries.")
                return _GIS_SUBDISTRICTS
        except Exception as e:
            logger.warning(f"Failed to load subdistricts.geojson: {e}")
    _GIS_SUBDISTRICTS = []
    return _GIS_SUBDISTRICTS

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

    features = _get_gis_features()
    for feat in features:
        props = feat.get("properties", {})
        geom = feat.get("geometry", {})
        if _check_geom(lng_f, lat_f, geom):
            sd = props.get("subdistrict_th") or props.get("name_th") or props.get("subdistrict") or ""
            d = props.get("district_th") or props.get("district") or ""
            p = props.get("province_th") or props.get("province") or ""
            if p == "กรุงเทพมหานคร":
                sd = sd.replace("ตำบล", "แขวง")
                d = d.replace("อำเภอ", "เขต")
            return sd, d, p

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
        return "ที่ดิน"
    if any(w in combined for w in ["โรงแรม", "รีสอร์ท", "อพาร์ทเม้นท์", "อพาร์ตเมนต์", "หอพัก"]):
        return "โรงแรม/รีสอร์ท"
    return "บ้านเดี่ยว" if raw_type else "อื่นๆ"

def parse_nayoo_areas(raw_land, raw_usable, title="", prop_type=""):
    combined = f"{raw_land} {raw_usable} {title}"
    land_area = ""
    usable_area = ""

    # 1. Parse Land Area
    m_dash = re.search(r'(\d+)\s*-\s*(\d+)\s*-\s*([\d\.]+)\s*(?:ไร่)?', combined)
    m_full_land = re.search(r'((?:\d+\s*ไร่\s*)?(?:\d+\s*งาน\s*)?[\d\.,]+\s*(?:ตร\.วา|ตารางวา|ตร\.ว\.|วา))\b', combined)
    m_rai = re.search(r'(\d+(?:\.\d+)?)\s*ไร่\b', combined)
    m_sqw = re.search(r'([\d\.,]+)\s*(?:ตร\.วา|ตารางวา|ตร\.ว\.|วา)\b', combined)

    if m_dash and any(w in combined for w in ["ไร่", "ขนาด", "เนื้อที่", "ที่ดิน"]):
        r_r, r_n, r_w = m_dash.group(1), m_dash.group(2), m_dash.group(3)
        land_area = f"{r_r} ไร่ {r_n} งาน {r_w} ตร.ว."
    elif m_full_land:
        l_val = m_full_land.group(1).strip()
        land_area = re.sub(r'(?<=\d|\s)(?:ตร\.วา|ตารางวา|วา)\b', 'ตร.ว.', l_val)
        land_area = re.sub(r'\s+', ' ', land_area).strip()
    elif m_rai and any(w in combined for w in ["ที่ดิน", "เนื้อที่", "ขนาด", "ไร่"]):
        r_num = m_rai.group(1).strip()
        land_area = f"{r_num} ไร่"
    elif m_sqw:
        w_num = m_sqw.group(1).replace(',', '').strip()
        land_area = f"{w_num} ตร.ว."
    elif raw_land:
        l_c = re.sub(r'(?<=\d|\s)(?:ตร\.วา|ตารางวา|วา)\b', 'ตร.ว.', str(raw_land).strip())
        if re.match(r'^\d+(?:\.\d+)?$', l_c):
            l_c = f"{l_c} ตร.ว."
        land_area = l_c

    # 2. Parse Usable Area
    m_sqm = re.search(r'([\d\.,]+)\s*(?:ตร\.ม\.|ตารางเมตร|sq\.?m|sqm)\b', combined, re.I)
    if m_sqm:
        usable_area = m_sqm.group(1).replace(',', '').strip()
    elif raw_usable and str(raw_usable).replace('.', '').isdigit():
        usable_area = str(raw_usable).strip()

    # 3. Apply Property Type Rules
    if prop_type == "คอนโด":
        land_area = ""

    if prop_type == "ที่ดิน":
        if not land_area and usable_area:
            try:
                sqm_val = float(usable_area)
                sqw_val = sqm_val / 4.0
                if sqw_val >= 400:
                    rai = int(sqw_val // 400)
                    rem = sqw_val % 400
                    ngan = int(rem // 100)
                    wah = rem % 100
                    if wah == 0 and ngan == 0:
                        land_area = f"{rai} ไร่"
                    elif wah == 0:
                        land_area = f"{rai} ไร่ {ngan} งาน"
                    else:
                        land_area = f"{rai} ไร่ {ngan} งาน {wah:.1f} ตร.ว.".replace('.0 ตร.ว.', ' ตร.ว.')
                else:
                    land_area = f"{sqw_val:.1f} ตร.ว.".replace('.0 ตร.ว.', ' ตร.ว.')
            except Exception:
                pass
        if not any(w in combined for w in ["ตึก", "อาคาร", "โรงงาน", "โกดัง", "บ้าน", "รีสอร์ท"]):
            usable_area = ""

    if land_area:
        land_area = re.sub(r'\s*วา$', ' ตร.ว.', land_area)
        land_area = re.sub(r'\s*ตารางวา$', ' ตร.ว.', land_area)
        land_area = re.sub(r'\s*ตร\.วา$', ' ตร.ว.', land_area)
        if re.match(r'^\d+(?:\.\d+)?$', land_area):
            land_area = f"{land_area} ตร.ว."

    return land_area, usable_area

def fetch_nayoo_page(session, endpoint, page, per_page=50, province=""):
    params = {"page": page, "per_page": per_page}
    if province:
        params["province"] = province

    url = f"{API_BASE}{endpoint}"
    try:
        r = session.get(url, headers=HEADERS, params=params, timeout=25)
        if r.status_code == 200:
            return r.json()
        elif r.status_code == 401:
            logger.error("NaYoo API 401 Unauthorized - Check API Key!")
    except Exception as e:
        logger.warning(f"Error fetching NaYoo {endpoint} p{page} ({province}): {e}")
    return None

def process_nayoo_item(session, item, province_name=""):
    pid = item.get("id") or item.get("uuid")
    uuid = item.get("uuid") or pid
    
    # Title
    p_name = item.get("project_name", {})
    title = p_name.get("th") if isinstance(p_name, dict) else (item.get("title") or "")
    if not title:
        title = item.get("slug", "").replace("-", " ")

    # Property Type
    raw_type = ""
    p_info = item.get("project_info", {})
    if isinstance(p_info, dict):
        p_types = p_info.get("property_type", [])
        if isinstance(p_types, list) and p_types:
            first_pt = p_types[0]
            if isinstance(first_pt, dict):
                raw_type = first_pt.get("name", {}).get("th", "") or first_pt.get("slug", "")
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
    prov = province_name or item.get("province", {}).get("slug", "") or ""
    zone = item.get("zone", "") or ""
    subdist = zone if zone else ""
    dist = ""

    coords = item.get("coordinates")
    lat, lng = None, None
    if isinstance(coords, list) and len(coords) >= 2:
        try:
            lat = float(coords[0])
            lng = float(coords[1])
        except Exception:
            pass

    # Reverse Geocode with GIS
    if lat and lng:
        sd_geo, d_geo, p_geo = reverse_geocode_location(session, lat, lng)
        if sd_geo: subdist = sd_geo
        if d_geo: dist = d_geo
        if p_geo: prov = p_geo

    # Province Normalization
    if not prov:
        for p in PROVINCES:
            if p in title or p in str(zone):
                prov = "กรุงเทพมหานคร" if p == "กรุงเทพ" else p
                break

    if prov == "กรุงเทพ":
        prov = "กรุงเทพมหานคร"

    # Dates
    post_date = ""
    dt_str = item.get("created_at") or item.get("updated_at") or ""
    if dt_str:
        try:
            post_date = dt_str[:10]
        except Exception:
            pass

    # URL Link
    p_slug = item.get("province", {}).get("slug", "") or "khonkaen"
    item_slug = item.get("slug", "")
    if item_slug:
        link = f"https://nayoo.co/property-for-sale/properties/{p_slug}/{item_slug}"
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

    # 1. Fetch Supported Provinces
    provinces = []
    try:
        r_prov = session.get(f"{API_BASE}/api/support-provinces", headers=HEADERS, timeout=15)
        if r_prov.status_code == 200:
            prov_items = r_prov.json().get("data", {}).get("items", [])
            for pi in prov_items:
                slug = pi.get("slug")
                name_th = pi.get("province", {}).get("name", {}).get("th", "")
                if slug:
                    provinces.append((slug, name_th))
    except Exception as e:
        logger.warning(f"Failed to fetch support-provinces: {e}")

    if not provinces:
        provinces = [
            ("khonkaen", "ขอนแก่น"), ("rayong", "ระยอง"), ("udon", "อุดรธานี"),
            ("ubon", "อุบลราชธานี"), ("chonburi", "ชลบุรี"), ("chiangrai", "เชียงราย"),
            ("phitsanulok", "พิษณุโลก"), ("surin", "สุรินทร์"), ("buriram", "บุรีรัมย์"),
            ("huahin", "ประจวบคีรีขันธ์")
        ]

    logger.info(f"📍 Supported provincial hubs: {len(provinces)} ({[p[0] for p in provinces]})")

    all_records = []
    endpoints = [
        ("/api/listing/search/secondhands", "Secondhands"),
        ("/api/listing/search/projects", "Projects")
    ]

    total_provinces = len(provinces)
    for prov_idx, (prov_slug, prov_name) in enumerate(provinces):
        logger.info(f"\n--- Scraping Hub: {prov_name} ({prov_slug}) [{prov_idx+1}/{total_provinces}] ---")
        
        for ep, ep_label in endpoints:
            # First page to determine total items
            res = fetch_nayoo_page(session, ep, page=1, per_page=50, province=prov_slug)
            if not res or not res.get("success"):
                continue

            pag = res.get("data", {}).get("pagination", {})
            total_items = pag.get("total_items", 0)
            total_pages = pag.get("total_pages", 1)
            
            logger.info(f"  [{ep_label}] Found {total_items:,} items across {total_pages} pages.")
            
            posts = res.get("data", {}).get("posts", []) or res.get("data", {}).get("projects", []) or []
            for p in posts:
                rec = process_nayoo_item(session, p, province_name=prov_name)
                if rec:
                    all_records.append(rec)

            # Concurrent fetch for remaining pages
            if total_pages > 1:
                with ThreadPoolExecutor(max_workers=8) as executor:
                    futures = {
                        executor.submit(fetch_nayoo_page, session, ep, page=p_num, per_page=50, province=prov_slug): p_num
                        for p_num in range(2, total_pages + 1)
                    }
                    for fut in as_completed(futures):
                        try:
                            p_res = fut.result()
                            if p_res and p_res.get("success"):
                                p_posts = p_res.get("data", {}).get("posts", []) or p_res.get("data", {}).get("projects", []) or []
                                for item in p_posts:
                                    rec = process_nayoo_item(session, item, province_name=prov_name)
                                    if rec:
                                        all_records.append(rec)
                        except Exception as e:
                            logger.warning(f"Error fetching page: {e}")

        logger.info(f"  Cumulative items collected: {len(all_records):,}")
        if progress_callback:
            pct = int(((prov_idx + 1) / total_provinces) * 100)
            progress_callback(pct, f"Scraped {prov_name} ({len(all_records):,} items)")

    # Convert to DataFrame
    df = pd.DataFrame(all_records)
    for col in COLUMNS:
        if col not in df.columns:
            df[col] = ""
    df = df[COLUMNS]

    df.drop_duplicates(subset=["รหัสทรัพย์", "ชื่อโครงการ"], inplace=True)
    df.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")
    
    logger.info("=" * 65)
    logger.info(f"🎉 NaYoo scraping complete! Saved {len(df):,} records to:")
    logger.info(f"📁 {OUTPUT_CSV}")
    logger.info("=" * 65)

    return df

if __name__ == "__main__":
    scrape_nayoo()
