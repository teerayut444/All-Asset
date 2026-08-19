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
NaYoo (น่าอยู่) Monthly Scraper
Scrapes all Secondhand properties (~10,711) and Project listings (~3,528) from https://api.nayoo.co
Adheres strictly to the 21 standard dashboard columns, GIS STRtree reverse geocoding, coordinates extraction, and monthly export structure.
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

# Standard 21 Columns
COLUMNS = [
    "บริษัท", "ID", "รหัสทรัพย์", "ชื่อโครงการ", "ประเภททรัพย์",
    "ประเภทการขาย", "ราคา", "ตำบล", "อำเภอ", "จังหวัด",
    "ละติจูด", "ลองจิจูด", "ชื่อประกาศ", "ลิงก์",
    "เนื้อที่ (ตร.ว.)", "พื้นที่ใช้สอย (ตร.ม.)", "วันที่ดึงข้อมูล",
    "ห้องนอน", "ห้องน้ำ", "ที่จอดรถ", "วันประกาศ"
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
            logger.info(f"Loaded {len(_GIS_PROPS):,} GIS subdistrict boundaries & built STRtree.")
    except Exception as e:
        logger.warning(f"Failed to load subdistricts.geojson: {e}")

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

def fetch_and_process_item(session, item):
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

    # Price & Sale Type
    pricing = item.get("pricing", {}) or {}
    price = None
    sale_type = "ขาย"

    if isinstance(pricing, dict):
        p_val = pricing.get("sale_price") or pricing.get("start_price") or pricing.get("starting_price") or pricing.get("promotion_price")
        if p_val and str(p_val).replace('.', '').isdigit():
            try:
                p_num = float(p_val)
                if p_num > 0: price = p_num
            except Exception: pass
        if not price and pricing.get("rent_price"):
            try:
                r_num = float(pricing.get("rent_price"))
                if r_num > 0:
                    price = r_num
                    sale_type = "ให้เช่า"
            except Exception: pass

    if not price and item.get("price"):
        try:
            p_num = float(item.get("price"))
            if p_num > 0: price = p_num
        except Exception: pass

    # Functions (Bed, Bath, Area)
    funcs = item.get("functions", {}) or {}
    bed = funcs.get("bedrooms") if isinstance(funcs, dict) else None
    bath = funcs.get("bathrooms") if isinstance(funcs, dict) else None
    parking = funcs.get("parking") if isinstance(funcs, dict) else None
    raw_land = funcs.get("land_area") if isinstance(funcs, dict) else ""
    raw_usable = funcs.get("usable_area") if isinstance(funcs, dict) else ""

    # Fetch Detailed endpoint for Coordinates and Precise Location
    detail_data = None
    lat, lng = None, None
    subdist, dist, prov = "", "", ""
    post_date = ""

    try:
        r_det = session.get(f"{API_BASE}/api/listing/post/{pid}", headers=HEADERS, timeout=10)
        if r_det.status_code == 200:
            detail_data = r_det.json().get("data", {})
    except Exception:
        pass

    if detail_data:
        loc = detail_data.get("location", {})
        coords = loc.get("coordinates")
        if isinstance(coords, (list, tuple)) and len(coords) >= 2:
            try:
                c0 = float(coords[0])
                c1 = float(coords[1])
                if c0 != 0 or c1 != 0:
                    lat, lng = c0, c1
            except Exception:
                pass

        if lat and lng:
            sd_geo, d_geo, p_geo = reverse_geocode_location(lat, lng)
            if sd_geo: subdist = sd_geo
            if d_geo: dist = d_geo
            if p_geo: prov = p_geo

        if not prov or not dist:
            p_dict = loc.get("province", {})
            if isinstance(p_dict, dict): prov = p_dict.get("name", {}).get("th", "")
            d_dict = loc.get("district", {})
            if isinstance(d_dict, dict): dist = d_dict.get("name", {}).get("th", "")
            sd_dict = loc.get("sub_district", {})
            if isinstance(sd_dict, dict): subdist = sd_dict.get("name", {}).get("th", "")

        spec = detail_data.get("spec", {})
        if isinstance(spec, dict):
            if spec.get("parking") is not None:
                parking = spec.get("parking")
            if spec.get("bedroom") is not None:
                bed = spec.get("bedroom")
            if spec.get("bathroom") is not None:
                bath = spec.get("bathroom")
            if spec.get("usable_area") and float(spec.get("usable_area") or 0) > 1.0:
                raw_usable = spec.get("usable_area")

        # Price fallback from detail_data
        det_pricing = detail_data.get("pricing", {}) or {}
        if isinstance(det_pricing, dict):
            det_val = det_pricing.get("sale_price") or det_pricing.get("start_price") or det_pricing.get("starting_price") or det_pricing.get("promotion_price")
            if det_val and str(det_val).replace('.', '').isdigit():
                try:
                    d_num = float(det_val)
                    if d_num > 0 and (not price or price == 0):
                        price = d_num
                except Exception: pass
            if (not price or price == 0) and det_pricing.get("rent_price"):
                try:
                    r_num = float(det_pricing.get("rent_price"))
                    if r_num > 0:
                        price = r_num
                        sale_type = "ให้เช่า"
                except Exception: pass

        if (not price or price == 0) and detail_data.get("price"):
            try:
                d_num = float(detail_data.get("price"))
                if d_num > 0: price = d_num
            except Exception: pass

        det_types = detail_data.get("listing_types") or item.get("listing_types") or []
        if isinstance(det_types, list) and "rent" in det_types and "sale" not in det_types:
            sale_type = "ให้เช่า"

        pub_dt = detail_data.get("published_at") or detail_data.get("created_at") or detail_data.get("updated_at")
        if pub_dt:
            post_date = str(pub_dt)[:10]

    # Smart price sanity check (filter out seller input typos like phone numbers or billion errors)
    desc_obj = (detail_data.get("description") if detail_data else None) or item.get("description") or {}
    desc_text = desc_obj.get("th", "") if isinstance(desc_obj, dict) else str(desc_obj or "")
    combined_text = f"{title} {desc_text}"
    if price and price > 1_000_000_000:
        m_lakh = re.findall(r'(?:ราคา|ขาย|เพียง)?\s*[:\s]*(\d+(?:\.\d+)?)\s*(?:ล้านบาท|ล้าน|ลบ\b)', combined_text)
        if m_lakh:
            try:
                candidate = float(m_lakh[0]) * 1_000_000
                if 100_000 <= candidate <= 500_000_000:
                    price = candidate
            except Exception:
                pass

    # Fallback for location if detail was not reachable
    if not prov:
        p_obj = item.get("province", {})
        p_slug = p_obj.get("slug", "") if isinstance(p_obj, dict) else str(p_obj)
        prov = PROVINCE_SLUG_MAP.get(str(p_slug).lower(), "")

    if not post_date:
        dt_str = item.get("created_at") or item.get("updated_at") or ""
        if dt_str:
            post_date = str(dt_str)[:10]

    # Clean location strings
    if dist:
        dist = dist.replace("อำเภอ", "").replace("เขต", "").strip()
    if subdist:
        subdist = subdist.replace("ตำบล", "").replace("แขวง", "").strip()
    if prov == "กรุงเทพ":
        prov = "กรุงเทพมหานคร"

    land_area, usable_area = parse_nayoo_areas(raw_land, raw_usable, title=title, prop_type=prop_type)

    p_obj = item.get("province", {})
    p_slug = p_obj.get("slug", "") if isinstance(p_obj, dict) else str(p_obj)
    item_slug = item.get("slug", "")
    if item_slug:
        link = f"https://nayoo.co/property-for-sale/properties/{p_slug or 'thailand'}/{item_slug}"
    else:
        link = f"https://nayoo.co/posts/{pid}"

    pull_date = datetime.datetime.now().strftime("%Y-%m-%d")

    return {
        "บริษัท": COMPANY_NAME,
        "ID": pid,
        "รหัสทรัพย์": pid,
        "ชื่อโครงการ": title,
        "ประเภททรัพย์": prop_type,
        "ประเภทการขาย": sale_type,
        "ราคา": price,
        "ตำบล": subdist,
        "อำเภอ": dist,
        "จังหวัด": prov,
        "ละติจูด": lat,
        "ลองจิจูด": lng,
        "ชื่อประกาศ": title,
        "ลิงก์": link,
        "เนื้อที่ (ตร.ว.)": convert_to_rai_ngan_wah(land_area),
        "พื้นที่ใช้สอย (ตร.ม.)": usable_area,
        "วันที่ดึงข้อมูล": pull_date,
        "ห้องนอน": bed,
        "ห้องน้ำ": bath,
        "ที่จอดรถ": parking,
        "วันประกาศ": post_date
    }

def scrape_nayoo(progress_callback=None):
    logger.info("=" * 65)
    logger.info("🚀 Starting NaYoo (น่าอยู่) Monthly Scraper")
    logger.info("=" * 65)

    _init_gis()

    session = requests.Session()
    adapter = requests.adapters.HTTPAdapter(pool_connections=50, pool_maxsize=50)
    session.mount('https://', adapter)
    session.mount('http://', adapter)

    endpoints = [
        ("/api/listing/search/secondhands", "Secondhands"),
        ("/api/listing/search/projects", "Projects")
    ]

    discovered_items = {}

    # 1. Fetch pages and collect items
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
            pid = p.get("id") or p.get("uuid")
            if pid and pid not in discovered_items:
                discovered_items[pid] = p

        # Concurrently fetch remaining pages for this endpoint
        logger.info(f"⚡ Fetching remaining {total_pages - 1} pages for {ep_label}...")
        with ThreadPoolExecutor(max_workers=20) as page_exec:
            futures = {page_exec.submit(fetch_nayoo_page, session, ep, p_num, 36): p_num for p_num in range(2, total_pages + 1)}
            for fut in as_completed(futures):
                try:
                    p_res = fut.result()
                    if p_res and p_res.get("success"):
                        p_posts = p_res.get("data", {}).get("posts", []) or p_res.get("data", {}).get("projects", []) or []
                        for item in p_posts:
                            pid = item.get("id") or item.get("uuid")
                            if pid and pid not in discovered_items:
                                discovered_items[pid] = item
                except Exception as e:
                    logger.warning(f"Error on {ep_label} page: {e}")

    total_discovered = len(discovered_items)
    logger.info(f"🎯 Total unique NaYoo listings discovered: {total_discovered:,}")
    if progress_callback:
        progress_callback(30, f"Discovered {total_discovered:,} listings")

    # 2. Concurrently fetch details and extract coordinates for all items
    logger.info(f"⚡ Concurrently fetching details and coordinates for {total_discovered:,} listings...")
    all_records = []
    
    with ThreadPoolExecutor(max_workers=35) as detail_exec:
        futures = {detail_exec.submit(fetch_and_process_item, session, item): pid for pid, item in discovered_items.items()}
        completed = 0
        for fut in as_completed(futures):
            try:
                rec = fut.result()
                if rec:
                    all_records.append(rec)
            except Exception as e:
                logger.warning(f"Error processing detail: {e}")
            completed += 1
            if completed % 500 == 0 or completed == total_discovered:
                pct = 30 + int((completed / max(1, total_discovered)) * 70)
                logger.info(f"  Processed {completed:,}/{total_discovered:,} items ({completed/total_discovered*100:.1f}%)")
                if progress_callback:
                    progress_callback(pct, f"Scraped {completed:,}/{total_discovered:,} items")

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
