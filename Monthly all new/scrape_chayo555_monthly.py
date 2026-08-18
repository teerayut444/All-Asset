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

# Standard 16 Columns
COLUMNS = [
    "บริษัท", "ID", "รหัสทรัพย์", "ชื่อโครงการ", "ประเภททรัพย์",
    "ประเภทการขาย", "ราคา", "ตำบล", "อำเภอ", "จังหวัด",
    "ละติจูด", "ลองจิจูด", "ชื่อประกาศ", "เนื้อที่ (ตร.ว.)",
    "พื้นที่ใช้สอย (ตร.ม.)", "ห้องนอน", "ห้องน้ำ", "วันที่ลงประกาศ", "ลิงก์"
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
        if not code:
            m_code = re.search(r'รหัสทรัพย์(?:สิน)?\s*[:\s]*([A-Za-z0-9\-\/_]+)', full_text)
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
        m_coord = re.search(r'(?:lat|latitude)[=:\s]+([\d\.-]+).*?(?:lng|longitude|lon)[=:\s]+([\d\.-]+)', r.text, re.I)
        if m_coord:
            try:
                lat = float(m_coord.group(1))
                lng = float(m_coord.group(2))
            except Exception:
                pass

        if not lat:
            m_map = re.search(r'maps\.google\.com.*?q=([\d\.-]+),([\d\.-]+)', r.text)
            if m_map:
                try:
                    lat = float(m_map.group(1))
                    lng = float(m_map.group(2))
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
            "เนื้อที่ (ตร.ว.)": land_area,
            "พื้นที่ใช้สอย (ตร.ม.)": usable_area,
            "ห้องนอน": bed,
            "ห้องน้ำ": bath,
            "วันที่ลงประกาศ": "",
            "ลิงก์": item_url
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
