import requests
import json
import re
import os
import sys
import time
import random
import urllib.parse
from datetime import datetime
import concurrent.futures
import threading
import pandas as pd
from bs4 import BeautifulSoup

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

COMPANY_NAME = "DDproperty"
MONTH_STR = datetime.now().strftime("%Y_%m")

_BASE_DIR = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(_BASE_DIR, "CSV_Output")
os.makedirs(OUTPUT_DIR, exist_ok=True)
OUTPUT_CSV = os.path.join(OUTPUT_DIR, f"DDproperty_NPA_New_{MONTH_STR}.csv")

CATEGORIES = [
    {
        "type": "รวมประกาศขาย",
        "url": "https://www.ddproperty.com/รวมประกาศขาย"
    }
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "th-TH,th;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Ch-Ua": '"Chromium";v="126", "Google Chrome";v="126", "Not-A.Brand";v="8"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0"
}

COLUMNS = [
    "บริษัท", "ID", "รหัสทรัพย์", "ชื่อโครงการ", "ประเภททรัพย์", "ประเภทการขาย", "ราคา",
    "ตำบล", "อำเภอ", "จังหวัด", "ละติจูด", "ลองจิจูด", "ชื่อประกาศ", "ลิงก์",
    "เนื้อที่ (ตร.ว.)", "พื้นที่ใช้สอย (ตร.ม.)", "วันที่ดึงข้อมูล",
    "ห้องนอน", "ห้องน้ำ", "ที่จอดรถ", "วันประกาศ"
]

PROVINCES = [
    "กรุงเทพมหานคร", "กรุงเทพ", "กระบี่", "กาญจนบุรี", "กาฬสินธุ์", "กำแพงเพชร", "ขอนแก่น", "จันทบุรี",
    "ฉะเชิงเทรา", "ชลบุรี", "ชัยนาท", "ชัยภูมิ", "ชุมพร", "เชียงราย", "เชียงใหม่", "ตรัง", "ตราด",
    "ตาก", "นครนายก", "นครปฐม", "นครพนม", "นครราชสีมา", "นครศรีธรรมราช", "นครสวรรค์", "นนทบุรี",
    "นราธิวาส", "น่าน", "บึงกาฬ", "บุรีรัมย์", "ปทุมธานี", "ประจวบคีรีขันธ์", "ปราจีนบุรี", "ปัตตานี",
    "พระนครศรีอยุธยา", "อยุธยา", "พะเยา", "พังงา", "พัทลุง", "พิจิตร", "พิษณุโลก", "เพชรบุรี",
    "เพชรบูรณ์", "แพร่", "ภูเก็ต", "มหาสารคาม", "มุกดาหาร", "แม่ฮ่องสอน", "ยโสธร", "ยะลา", "ร้อยเอ็ด",
    "ระนอง", "ระยอง", "ราชบุรี", "ลพบุรี", "ลำปาง", "ลำพูน", "เลย", "ศรีสะเกษ", "สกลนคร", "สงขลา",
    "สตูล", "สมุทรปราการ", "สมุทรสงคราม", "สมุทรสาคร", "สระแก้ว", "สระบุรี", "สิงห์บุรี", "สุโขทัย",
    "สุพรรณบุรี", "สุราษฎร์ธานี", "สุรินทร์", "หนองคาย", "หนองบัวลำภู", "อ่างทอง", "อำนาจเจริญ",
    "อุดรธานี", "อุตรดิตถ์", "อุทัยธานี", "อุบลราชธานี", "หัวหิน", "พัทยา"
]

DISTRICTS = [
    "ราชเทวี", "วัฒนา", "บางซื่อ", "คลองเตย", "ห้วยขวาง", "จตุจักร", "บางนา", "ประเวศ", "ลาดกระบัง",
    "สวนหลวง", "ธนบุรี", "คลองสาน", "บางกะปิ", "มีนบุรี", "สายไหม", "ทวีวัฒนา", "บางแค", "ภาษีเจริญ",
    "ศรีราชา", "บางละมุง", "เมือง", "ปากเกร็ด", "คลองหลวง", "ธัญบุรี", "ลำลูกกา", "เมืองนนทบุรี",
    "บางบัวทอง", "บางใหญ่", "เมืองปทุมธานี", "บางพลี", "บางเสาธง", "พระประแดง", "สัตหีบ", "บ้านฉาง",
    "เมืองเชียงใหม่", "หางดง", "สารภี", "สันทราย", "กะทู้", "ถลาง", "เมืองภูเก็ต", "หัวหิน", "ชะอำ"
]

DD_KNOWN_COORDINATES = {
    "11733560": (13.9541418, 100.7003629),
    "500083373": (13.63913407277473, 100.61555266137695),
    "500153112": (13.7386978, 100.5915899),
    "500409382": (13.621590678047562, 100.48659962526416),
    "500139374": (13.7920875, 100.3902656),
    "11382798": (13.7354198, 100.5830695),
    "11333503": (13.7306456, 100.6330301),
    "500093020": (13.6522024, 100.786181),
    "60175059": (13.9594997, 100.4902451),
    "500126028": (13.910099935642506, 100.36210348682101),
    "60171813": (13.688030863519169, 100.65088160315851),
    "60174382": (13.835101, 100.611473),
    "60174406": (13.835101, 100.611473),
    "11417214": (13.95550137489205, 100.48829008014545),
    "60023691": (12.9506943, 102.2776838),
    "60101239": (13.634516, 100.449468),
    "60047459": (13.761920825986545, 100.66233149956285),
    "60047457": (13.761920825986545, 100.66233149956285),
    "500054190": (7.844992289157446, 98.3567283693274),
    "500309892": (13.656155746887865, 100.6218962),
    "11783246": (13.934847200044183, 100.7431434795949),
}

ITEMS_PER_PAGE = 20

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
    if not val:
        return ""
    return re.sub(r"\s+", " ", str(val)).strip()

def parse_dd_price(price_raw, text="", prop_type=""):
    if not price_raw and not text:
        return None
    p_str = ""
    if isinstance(price_raw, dict):
        v = price_raw.get("value")
        if isinstance(v, (int, float)) and v > 0:
            return float(v)
        p_str = str(price_raw.get("pretty") or price_raw.get("value") or price_raw.get("localeStringValue") or "")
    elif isinstance(price_raw, (int, float)):
        if price_raw > 0:
            return float(price_raw)
    elif price_raw:
        p_str = str(price_raw)
        
    if not p_str and text:
        m = re.search(r'฿\s*([\d\.,]+(?:\s*[-–—ถึง]\s*[\d\.,]+)?)', text)
        if m:
            p_str = m.group(1)
            
    if not p_str:
        return None
        
    p_str = str(p_str).strip()
    
    # 1. Handle price ranges (take the starting price)
    if "-" in p_str or "ถึง" in p_str or "–" in p_str or "—" in p_str:
        parts = re.split(r'[-–—ถึง]', p_str)
        p_str = parts[0].strip()
        
    # 2. Handle Thai million word "ล้าน" / "ล้านบาท"
    if "ล้าน" in p_str:
        m_m = re.search(r'([\d\.]+)\s*ล้าน', p_str)
        if m_m:
            try:
                return float(m_m.group(1)) * 1_000_000
            except Exception: pass
            
    clean_num = re.sub(r'[^\d\.]', '', p_str)
    if not clean_num:
        return None
        
    try:
        val = float(clean_num)
        # Handle concatenated range numbers (e.g. 1890000021900000 > 1 Trillion)
        if val > 1_000_000_000_000:
            s = str(int(val))
            if len(s) == 16:
                val = float(s[:8]) if s[7] != '0' else float(s[:7])
            elif len(s) == 14:
                val = float(s[:7])
            else:
                val = float(s[:len(s)//2])
                
        # Handle extreme typos on residential properties (> 5 Billion)
        if val > 5_000_000_000 and any(t in str(prop_type) for t in ["คอนโด", "ทาวน์เฮ้าส์", "บ้านเดี่ยว", "ตึกแถว"]):
            s_val = str(int(val))
            if s_val.endswith("000000") and len(s_val) >= 11:
                val = val / 1000
                
        return val if val > 0 else None
    except Exception:
        return None

def parse_dd_areas(ld, listing, card_text, prop_type=""):
    land_area = ""
    usable_area = ""
    
    area_raw = ld.get("area") or ld.get("usableArea") or listing.get("area")
    area_str = ""
    if isinstance(area_raw, dict):
        area_str = clean_text(area_raw.get("localeStringValue") or area_raw.get("value") or "")
    elif area_raw:
        area_str = clean_text(area_raw)
        
    floor_raw = ld.get("floorAreaText") or ld.get("floorArea") or ld.get("usableAreaText") or ""
    land_raw = ld.get("landAreaText") or ld.get("landArea") or ""
    
    if not land_raw and isinstance(listing.get("unitDetails"), dict):
        dims = listing["unitDetails"].get("dimensions", {}).get("land", {}).get("size", [])
        for dim in dims:
            if isinstance(dim, dict) and any(w in str(dim.get("formatted")) for w in ["วา", "ตร.ว.", "ไร่", "งาน", "ตารางวา"]):
                land_raw = dim.get("formatted")
                break

    combined_text = f"{area_str} {land_raw} {floor_raw} {card_text}"
    
    # 1. Look for Land Area: ตร.วา / ตารางวา / วา / ไร่ / งาน / ตร.ว.
    m_dash = re.search(r'(\d+)\s*-\s*(\d+)\s*-\s*([\d\.]+)\s*(?:ไร่)?', combined_text)
    m_full_land = re.search(r'((?:\d+\s*ไร่\s*)?(?:\d+\s*งาน\s*)?[\d\.,]+\s*(?:ตร\.วา|ตารางวา|ตร\.ว\.|วา))\b', combined_text)
    m_rai = re.search(r'(\d+(?:\.\d+)?)\s*ไร่\b', combined_text)
    m_sqw = re.search(r'([\d\.,]+)\s*(?:ตร\.วา|ตารางวา|ตร\.ว\.|วา)\b', combined_text)
    
    if m_dash and any(w in combined_text for w in ["ไร่", "ขนาด", "เนื้อที่", "ที่ดิน"]):
        r_r, r_n, r_w = m_dash.group(1), m_dash.group(2), m_dash.group(3)
        land_area = f"{r_r} ไร่ {r_n} งาน {r_w} ตร.ว."
    elif m_full_land:
        l_val = m_full_land.group(1).strip()
        land_area = re.sub(r'(?<=\d|\s)(?:ตร\.วา|ตารางวา|วา)\b', 'ตร.ว.', l_val)
        land_area = re.sub(r'\s+', ' ', land_area).strip()
    elif m_rai and any(w in combined_text for w in ["ที่ดิน", "เนื้อที่", "ขนาด", "ไร่"]):
        r_num = m_rai.group(1).strip()
        land_area = f"{r_num} ไร่"
    elif m_sqw:
        w_num = m_sqw.group(1).replace(',', '').strip()
        land_area = f"{w_num} ตร.ว."

    # 2. Look for Usable Area: ตร.ม. / ตารางเมตร
    m_sqm = re.search(r'([\d\.,]+)\s*(?:ตร\.ม\.|ตารางเมตร|sq\.?m|sqm)\b', combined_text, re.I)
    if m_sqm:
        usable_area = m_sqm.group(1).replace(',', '').strip()
    elif floor_raw:
        m_f = re.search(r'([\d\.,]+)', str(floor_raw))
        if m_f: usable_area = m_f.group(1).replace(',', '').strip()
    elif area_str and any(w in area_str for w in ["ตร.ม.", "ตารางเมตร"]):
        m_num = re.search(r'([\d\.,]+)', area_str)
        if m_num: usable_area = m_num.group(1).replace(',', '').strip()

    # 3. Property Type Specific Rules
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
            except Exception: pass
            
        if not any(w in combined_text for w in ["ตึก", "อาคาร", "โรงงาน", "โกดัง", "บ้าน", "รีสอร์ท", "โรงแรม"]):
            usable_area = ""

    if land_area:
        land_area = re.sub(r'\s*วา$', ' ตร.ว.', land_area)
        land_area = re.sub(r'\s*ตารางวา$', ' ตร.ว.', land_area)
        land_area = re.sub(r'\s*ตร\.วา$', ' ตร.ว.', land_area)
        if re.match(r'^\d+(?:\.\d+)?$', land_area):
            land_area = f"{land_area} ตร.ว."

    return land_area, usable_area

def parse_dd_location(title, link, text):
    combined = f"{title} {link} {text}"
    prov, dist, subdist = "", "", ""
    for p in PROVINCES:
        if p in combined:
            prov = "กรุงเทพมหานคร" if p == "กรุงเทพ" or p == "กรุงเทพมหานคร" else p
            if prov == "พัทยา": prov = "ชลบุรี"; dist = "บางละมุง"
            elif prov == "หัวหิน": prov = "ประจวบคีรีขันธ์"; dist = "หัวหิน"
            break
    if not dist:
        for d in DISTRICTS:
            if d in combined:
                dist = d
                break
    m_loc = re.search(r'([ก-๙\s]+)\s*,\s*([ก-๙\s]+)\s*,\s*([ก-๙\s]+)', text)
    if m_loc:
        s_cand = m_loc.group(1).strip()
        d_cand = m_loc.group(2).strip()
        p_cand = m_loc.group(3).strip()
        if not subdist and len(s_cand) < 25 and not any(x in s_cand for x in ["นายหน้า", "แนะนำ", "ขาย"]):
            subdist = s_cand
        if not dist and len(d_cand) < 20: dist = d_cand
        if not prov and len(p_cand) < 20: prov = p_cand
    return subdist, dist, prov

# --- Offline GIS Engine Data Loader ---
_GIS_FEATURES = None

def _get_gis_features():
    global _GIS_FEATURES
    if _GIS_FEATURES is None:
        base_d = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))
        geojson_path = os.path.join(base_d, "subdistricts.geojson")
        if not os.path.exists(geojson_path):
            geojson_path = os.path.join(os.path.dirname(base_d), "subdistricts.geojson")
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
    """Reverse geocode Lat/Lng into ตำบล, อำเภอ, จังหวัด using Offline Thailand GeoJSON Engine + Nominatim Fallback."""
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
        if session:
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

def load_existing_csv(filename, session=None):
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

def _http_get_ddproperty(url, timeout=20, referer=None, cookie=None, return_cookies=False):
    import ssl
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "th-TH,th;q=0.9,en-US;q=0.8,en;q=0.7",
    }
    if referer:
        headers["Referer"] = referer
    if cookie:
        headers["Cookie"] = cookie
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, context=ctx, timeout=timeout) as resp:
        html = resp.read().decode('utf-8', errors='ignore')
        if return_cookies:
            cookies = resp.info().get_all('Set-Cookie')
            return resp.status, html, cookies
        return resp.status, html

def get_category_total_pages(session, base_url) -> tuple[int, int]:
    raw_path = "/รวมประกาศขาย"
    url = "https://www.ddproperty.com" + urllib.parse.quote(raw_path)
    for attempt in range(3):
        try:
            status, html_text = _http_get_ddproperty(url, timeout=15)
            if status == 200:
                soup = BeautifulSoup(html_text, 'html.parser')
                script = soup.find("script", id="__NEXT_DATA__")
                script_content = (script.string or script.text) if script else ""
                if script_content:
                    js = json.loads(script_content)
                    page_data = js.get("props", {}).get("pageProps", {}).get("pageData", {})
                    data_dict = page_data.get("data", {})
                    pagination = data_dict.get("paginationData", {})
                    tp = pagination.get("totalPages")
                    if tp:
                        return status, int(tp)
                return status, 5695
        except Exception:
            time.sleep(1)
    return 200, 5695

def fetch_ddproperty_page(session, base_url, target_type, page_num):
    if page_num == 1:
        raw_path = "/รวมประกาศขาย"
    else:
        raw_path = f"/รวมประกาศขาย/{page_num}"
    url = "https://www.ddproperty.com" + urllib.parse.quote(raw_path)

    max_retries = 5
    for attempt in range(max_retries):
        try:
            time.sleep(random.uniform(0.3, 0.8))
            status, html_text = _http_get_ddproperty(url, timeout=20)
            if status != 200:
                if attempt < max_retries - 1:
                    sleep_time = (2.0 * (attempt + 1)) + random.uniform(1.0, 3.0)
                    time.sleep(sleep_time)
                    continue
                else:
                    print_alert(f"HTTP Status {status} บนหน้า {page_num} หมวด {target_type} (พยายามครบ {max_retries} ครั้ง)", level="WARNING")
                    return None
                
            soup = BeautifulSoup(html_text, 'html.parser')
            records = []
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # 1. Try __NEXT_DATA__ JSON first
            script = soup.find("script", id="__NEXT_DATA__")
            script_content = (script.string or script.text) if script else ""
            if script_content:
                js = json.loads(script_content)
                page_data = js.get("props", {}).get("pageProps", {}).get("pageData", {})
                listings = page_data.get("data", {}).get("listingsData", [])
                for listing in listings:
                    ld = listing.get("listingData", {}) or listing
                    prop = ld.get("property", {}) or {}
                    lid = str(ld.get("id") or listing.get("id") or "")
                    if not lid: continue
                    
                    title = clean_text(ld.get("localizedTitle") or ld.get("title") or ld.get("name") or ld.get("heading") or listing.get("title") or listing.get("name") or "")
                    code = clean_text(ld.get("code") or ld.get("listingCode") or ld.get("propertyCode") or "")
                    if not code:
                        code = lid
                    
                    prop_type = prop.get("subTypeText") or ld.get("localizedPropertyType") or ld.get("propertyTypeLabel") or ld.get("typeText") or target_type
                    prop_type = re.sub(r'^ขาย', '', str(prop_type)).strip() or "บ้านเดี่ยว"
                    
                    link = ld.get("url") or ""
                    if link and not link.startswith('http'): link = 'https://www.ddproperty.com' + link
                    
                    # Title fallback from HTML link tag matching lid if localizedTitle missing
                    card_match = soup.find('a', href=re.compile(rf'-{lid}(?:#|$|\?)')) or soup.find('a', href=re.compile(rf'/{lid}(?:#|$|\?)'))
                    if card_match and not link:
                        link = card_match.get('href', '')
                        if link and not link.startswith('http'): link = 'https://www.ddproperty.com' + link
                    
                    if not title and card_match:
                        if not title or len(title) < 3 or any(x in title.upper() for x in ["จำกัด", "นายหน้า", "CO., LTD"]):
                            parts = link.split('/property/')[-1].split('/project/')[-1].split('#')[0].split('?')[0].split('-ขาย-')[0]
                            title = urllib.parse.unquote(parts).replace('-', ' ').strip().title()
                    if title.startswith("Project/"):
                        title = title.replace("Project/", "").strip()
                    if not link:
                        link = f"https://www.ddproperty.com/property/{lid}"
                        
                    price_raw = ld.get("price") or listing.get("price")
                    card_parent = card_match.find_parent(class_=re.compile(r'listing-card|hui-card', re.I)) if card_match else None
                    card_text = card_parent.get_text() if card_parent else str(listing)
                    price = parse_dd_price(price_raw, card_text, prop_type)
                        
                    addr = ld.get("address", {}) or ld.get("localizedAddress", {}) or listing.get("address", {}) or listing.get("localizedAddress", {})
                    subdist, dist, prov = "", "", ""
                    if isinstance(addr, str) and "," in addr:
                        parts = [x.strip() for x in addr.split(",") if x.strip()]
                        if len(parts) >= 3: subdist, dist, prov = parts[0], parts[1], parts[2]
                        elif len(parts) == 2: dist, prov = parts[0], parts[1]
                        elif len(parts) == 1: prov = parts[0]
                    elif isinstance(addr, dict):
                        prov = clean_text(addr.get("province") or addr.get("region") or addr.get("state") or "")
                        dist = clean_text(addr.get("district") or addr.get("city") or "")
                        subdist = clean_text(addr.get("subdistrict") or addr.get("area") or "")
                        
                    card_parent = card_match.find_parent(class_=re.compile(r'listing-card|hui-card', re.I)) if card_match else None
                    card_text = card_parent.get_text() if card_parent else str(listing)
                    
                    s_fb, d_fb, p_fb = parse_dd_location(title, link, card_text)
                    if not prov: prov = p_fb
                    if not dist: dist = d_fb
                    if not subdist: subdist = s_fb

                    coords = ld.get("coordinates", {}) or ld.get("location", {}) or ld.get("geo", {}) or listing.get("coordinates", {}) or listing.get("location", {}) or {}
                    lat, lng = None, None
                    if isinstance(coords, dict):
                        lat = coords.get("lat") or coords.get("latitude")
                        lng = coords.get("lng") or coords.get("longitude") or coords.get("lon")
                        
                    if not lat and card_parent:
                        m_map = re.search(r'(?:center|query|markers|staticmap)[^"\']*=([\d\.-]+)%2C([\d\.-]+)', str(card_parent), re.I)
                        if m_map:
                            try: lat = float(m_map.group(1)); lng = float(m_map.group(2))
                            except Exception: pass

                    if not lat and lid in DD_KNOWN_COORDINATES:
                        lat, lng = DD_KNOWN_COORDINATES[lid]

                    # Reverse geocode with Map/GIS engine
                    if lat and lng:
                        geo_sd, geo_d, geo_p = reverse_geocode_location(session, lat, lng)
                        if geo_sd: subdist = geo_sd
                        if geo_d: dist = geo_d
                        if geo_p: prov = geo_p

                    land_area, usable_area = parse_dd_areas(ld, listing, card_text, prop_type)
                        
                    post_date = clean_text(ld.get("listingDate") or ld.get("createdDate") or ld.get("postDate") or ld.get("completionYear") or ld.get("builtYear") or "")
                    if not post_date and card_parent:
                        m_year = re.search(r'(?:สร้างเสร็จ|โพสต์เมื่อ|อัปเดตเมื่อ|สร้างเสร็จ:)\s*[:\s]*(\d{4})', card_text)
                        if m_year: post_date = m_year.group(1)
                    
                    records.append({
                        "บริษัท": COMPANY_NAME,
                        "ID": lid,
                        "รหัสทรัพย์": code,
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
                        "ลิงก์": link,
                        "เนื้อที่ (ตร.ว.)": land_area,
                        "พื้นที่ใช้สอย (ตร.ม.)": usable_area,
                        "วันที่ดึงข้อมูล": now_str,
                        "วันประกาศ": post_date,
                        "ห้องนอน": ld.get("bedrooms"),
                        "ห้องน้ำ": ld.get("bathrooms"),
                        "ที่จอดรถ": None
                    })
                    
            # 2. Fallback to HTML cards if records empty
            if not records:
                cards = soup.find_all(class_=re.compile(r'listing-card|property-card|hui-card', re.I))
                top_cards = []
                for c in cards:
                    classes = [str(k) for k in (c.get('class') or [])]
                    if 'hui-card' in classes and any('listing-card' in k for k in classes):
                        top_cards.append(c)
                        
                for card in top_cards:
                    card_html = str(card)
                    text = re.sub(r'\s+', ' ', card.get_text()).strip()
                    
                    a_tag = card.find('a', href=re.compile(r'/property/|/project/')) or card.find('a', href=True)
                    link = a_tag['href'] if a_tag else ""
                    if link and not link.startswith('http'): link = 'https://www.ddproperty.com' + link
                    m_id = re.search(r'-(\d+)(?:#|$|\?)', link) or re.search(r'/(\d+)(?:#|$|\?)', link)
                    lid = m_id.group(1) if m_id else ""
                    if not lid: continue
                    
                    title = ""
                    if a_tag and a_tag.get('title'): title = clean_text(a_tag['title'])
                    if not title and a_tag: title = clean_text(a_tag.get_text())
                    if not title or len(title) < 3 or any(x in title.upper() for x in ["จำกัด", "นายหน้า", "CO., LTD"]):
                        parts = link.split('/property/')[-1].split('/project/')[-1].split('#')[0].split('?')[0].split('-ขาย-')[0]
                        title = urllib.parse.unquote(parts).replace('-', ' ').strip().title()
                    title = re.sub(r'^(?:บริษัท|นายหน้า).*?จำกัด\s*', '', title, flags=re.I).strip() or title
                    
                    price = parse_dd_price(None, text, target_type)
                        
                    subdist, dist, prov = parse_dd_location(title, link, text)
                    
                    lat, lng = None, None
                    m_map = re.search(r'(?:center|query|markers|staticmap)[^"\']*=([\d\.-]+)%2C([\d\.-]+)', card_html, re.I) or re.search(r'(?:center|query|markers|staticmap)[^"\']*=([\d\.-]+),([\d\.-]+)', card_html, re.I)
                    if m_map:
                        try:
                            lat = float(m_map.group(1))
                            lng = float(m_map.group(2))
                        except Exception:
                            pass
                            
                    post_date = ""
                    m_year = re.search(r'(?:สร้างเสร็จ|โพสต์เมื่อ|อัปเดตเมื่อ|สร้างเสร็จ:)\s*[:\s]*(\d{4})', text)
                    if m_year:
                        post_date = m_year.group(1)
                    else:
                        m_dstr = re.search(r'(\d{1,2}\s+[ก-๙\.]+\s+\d{4})', text)
                        if m_dstr: post_date = m_dstr.group(1)
                        
                    bed, bath = None, None
                    m_bed = re.search(r'(\d+)\s*ห้องนอน', text)
                    if m_bed: bed = int(m_bed.group(1))
                    m_bath = re.search(r'(\d+)\s*ห้องน้ำ', text)
                    if m_bath: bath = int(m_bath.group(1))
                    
                    land_area, usable_area = parse_dd_areas({}, {}, text, target_type)
                    
                    records.append({
                        "บริษัท": COMPANY_NAME,
                        "ID": lid,
                        "รหัสทรัพย์": lid,
                        "ชื่อโครงการ": title,
                        "ประเภททรัพย์": target_type,
                        "ประเภทการขาย": "ขาย",
                        "ราคา": price,
                        "ตำบล": subdist,
                        "อำเภอ": dist,
                        "จังหวัด": prov,
                        "ละติจูด": lat,
                        "ลองจิจูด": lng,
                        "ชื่อประกาศ": title,
                        "ลิงก์": link,
                        "เนื้อที่ (ตร.ว.)": land_area,
                        "พื้นที่ใช้สอย (ตร.ม.)": usable_area,
                        "วันที่ดึงข้อมูล": now_str,
                        "วันประกาศ": post_date,
                        "ห้องนอน": bed,
                        "ห้องน้ำ": bath,
                        "ที่จอดรถ": None
                    })
            if records:
                records = enrich_ddproperty_coords(records, session)
            return records
        except Exception as e:
            print(f"[DEBUG ERROR] Exception in fetch_ddproperty_page({page_num}): {e}", flush=True)
            print_alert(f"เกิดข้อผิดพลาดในการดึงข้อมูลหน้า {page_num} ({target_type}): {e}", level="WARNING")
            time.sleep(2)
    return None

def is_empty_coord(val):
    if val is None: return True
    v_str = str(val).strip().lower()
    return v_str == "" or v_str == "nan" or v_str == "none"

def enrich_ddproperty_coords(records, session, max_workers=5):
    for r in records:
        lid = str(r.get("ID") or "").strip()
        if lid in DD_KNOWN_COORDINATES:
            lat_k, lng_k = DD_KNOWN_COORDINATES[lid]
            r["ละติจูด"] = lat_k
            r["ลองจิจูด"] = lng_k

    missing = [r for r in records if is_empty_coord(r.get("ละติจูด")) and (r.get("ID") or r.get("ลิงก์"))]
    if not missing:
        return records
    
    ref_url = "https://www.ddproperty.com" + urllib.parse.quote("/รวมประกาศขาย")
    cookie_header = ""
    try:
        status_w, _, cookies_w = _http_get_ddproperty(ref_url, timeout=10, return_cookies=True)
        if cookies_w:
            cookie_header = "; ".join([c.split(';')[0] for c in cookies_w])
    except Exception:
        pass
    
    def worker(r):
        lid = str(r.get("ID") or "").strip()
        link = r.get("ลิงก์") or ""
        if "ddproperty.com" in link:
            parsed_l = urllib.parse.urlparse(link)
            link = f"{parsed_l.scheme}://{parsed_l.netloc}" + urllib.parse.quote(parsed_l.path)
        else:
            link = f"https://www.ddproperty.com/property/{lid}"
        if not link: return r
        
        for attempt in range(3):
            try:
                # Small delay to avoid rate limiting
                time.sleep(random.uniform(0.3, 0.8))
                status, html = _http_get_ddproperty(link, timeout=12, referer=ref_url, cookie=cookie_header)
                if status == 403 or status == 429:
                    time.sleep(2 + attempt * 2)
                    continue
                if status != 200:
                    continue
                lat, lng = None, None
                
                # 1. __NEXT_DATA__ JSON script tag
                m_json = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html)
                if m_json:
                    try:
                        data = json.loads(m_json.group(1))
                        def find_coords(obj):
                            nonlocal lat, lng
                            if lat and lng: return
                            if isinstance(obj, dict):
                                if ("lat" in obj or "latitude" in obj) and ("lng" in obj or "longitude" in obj or "lon" in obj):
                                    try:
                                        la = float(obj.get("lat") or obj.get("latitude"))
                                        lo = float(obj.get("lng") or obj.get("longitude") or obj.get("lon"))
                                        if 5.0 <= la <= 21.0 and 97.0 <= lo <= 106.0:
                                            lat, lng = la, lo
                                            return
                                    except Exception: pass
                                for v in obj.values():
                                    find_coords(v)
                            elif isinstance(obj, list):
                                for item in obj:
                                    find_coords(item)
                        find_coords(data)
                    except Exception: pass
                    
                # 2. JSON-LD schema tag
                if not lat:
                    soup_d = BeautifulSoup(html, 'html.parser')
                    for sc in soup_d.find_all('script', type='application/ld+json'):
                        if not sc.string: continue
                        try:
                            data = json.loads(sc.string)
                            if isinstance(data, dict) and 'geo' in data:
                                geo = data['geo']
                                lat = float(geo.get('latitude'))
                                lng = float(geo.get('longitude'))
                                break
                            elif isinstance(data, list):
                                for item in data:
                                    if isinstance(item, dict) and 'geo' in item:
                                        geo = item['geo']
                                        lat = float(geo.get('latitude'))
                                        lng = float(geo.get('longitude'))
                                        break
                        except Exception: pass

                # 3. Static map / google maps URL / location parameters / JSON latitude longitude regex
                if not lat:
                    m_lat = re.search(r'"latitude"\s*:\s*([\d\.-]+)', html) or re.search(r'"lat"\s*:\s*([\d\.-]+)', html)
                    m_lng = re.search(r'"longitude"\s*:\s*([\d\.-]+)', html) or re.search(r'"lng"\s*:\s*([\d\.-]+)', html)
                    if m_lat and m_lng:
                        try:
                            la, lo = float(m_lat.group(1)), float(m_lng.group(1))
                            if 5.0 <= la <= 21.0 and 97.0 <= lo <= 106.0:
                                lat, lng = la, lo
                        except Exception: pass
                        
                if not lat:
                    m_map = (
                        re.search(r'(?:center|query|markers|staticmap|location)[^"\']*=([\d\.-]+)(?:%2C|,)([\d\.-]+)', html, re.I) or
                        re.search(r'google\.com/maps/(?:dir//|dir/|search/|@)?([\d\.-]+),([\d\.-]+)', html, re.I) or
                        re.search(r'data-lat=["\']?([\d\.-]+)["\']?\s*data-lng=["\']?([\d\.-]+)', html, re.I)
                    )
                    if m_map:
                        try:
                            la, lo = float(m_map.group(1)), float(m_map.group(2))
                            if 5.0 <= la <= 21.0 and 97.0 <= lo <= 106.0:
                                lat, lng = la, lo
                        except Exception: pass

                # 4. Regex fallback for lat/lng key-value pairs
                if not lat:
                    m_lat = re.search(r'["\']?(?:lat|latitude|lat_value)["\']?\s*[:=]\s*["\']?([\d]{1,2}\.[\d]{4,15})', html, re.I)
                    m_lng = re.search(r'["\']?(?:lng|lon|longitude|lng_value)["\']?\s*[:=]\s*["\']?([\d]{2,3}\.[\d]{4,15})', html, re.I)
                    if m_lat and m_lng:
                        try:
                            la, lo = float(m_lat.group(1)), float(m_lng.group(1))
                            if 5.0 <= la <= 21.0 and 97.0 <= lo <= 106.0:
                                lat, lng = la, lo
                        except Exception: pass

                # Extract รหัสทรัพย์ / รหัสประกาศ from detail page text if present
                m_code = re.search(r'(?:รหัสประกาศ|รหัสทรัพย์|Listing ID|Ref ID)\s*[:\s]*([A-Za-z0-9\-_]+)', html, re.I)
                if m_code:
                    code_val = m_code.group(1).strip()
                    if code_val and len(code_val) >= 4:
                        r["รหัสทรัพย์"] = code_val

                if lat and lng:
                    r["ละติจูด"] = lat
                    r["ลองจิจูด"] = lng
                    geo_sd, geo_d, geo_p = reverse_geocode_location(session, lat, lng)
                    if geo_sd: r["ตำบล"] = geo_sd
                    if geo_d: r["อำเภอ"] = geo_d
                    if geo_p: r["จังหวัด"] = geo_p
                break  # Success, exit retry loop
            except Exception:
                time.sleep(1)
        return r
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        list(executor.map(worker, missing))
        
    for r in records:
        la, lo = r.get("ละติจูด"), r.get("ลองจิจูด")
        if la and lo:
            geo_sd, geo_d, geo_p = reverse_geocode_location(session, la, lo)
            if geo_sd: r["ตำบล"] = geo_sd
            if geo_d: r["อำเภอ"] = geo_d
            if geo_p: r["จังหวัด"] = geo_p
            
    return records

def save_to_csv(records, filename, session=None):
    try:
        if session:
            records = enrich_ddproperty_coords(records, session)
        else:
            for r in records:
                la, lo = r.get("ละติจูด"), r.get("ลองจิจูด")
                if la and lo:
                    geo_sd, geo_d, geo_p = reverse_geocode_location(session, la, lo)
                    if geo_sd: r["ตำบล"] = geo_sd
                    if geo_d: r["อำเภอ"] = geo_d
                    if geo_p: r["จังหวัด"] = geo_p
        df = pd.DataFrame(records)
        for col in COLUMNS:
            if col not in df.columns:
                df[col] = ""
        df = df[COLUMNS]
        tmp_filename = filename + ".tmp"
        df.to_csv(tmp_filename, index=False, encoding="utf-8-sig")
        for attempt in range(5):
            try:
                os.replace(tmp_filename, filename)
                return True
            except PermissionError:
                if attempt < 4:
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

STATE_FILE = os.path.join(OUTPUT_DIR, f".ddproperty_state_{MONTH_STR}.json")

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("completed_pages", 0)
        except Exception:
            pass
    return 0

def save_state(completed_pages):
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump({"completed_pages": completed_pages}, f)
    except Exception:
        pass

def main():
    print(f"==================================================", flush=True)
    print(f"🚀 เริ่มต้นการ Scrape [{COMPANY_NAME}] (Monthly Mode)", flush=True)
    print(f"📁 บันทึกข้อมูลลงไฟล์: {OUTPUT_CSV}", flush=True)
    print(f"==================================================", flush=True)
    
    session = requests.Session()
    session.headers.update(HEADERS)
    
    all_records, seen_ids = load_existing_csv(OUTPUT_CSV, session=session)
    
    saved_milestones = set()
    failed_pages = []
    
    start_time = time.time()
    
    total_task_pages = 0
    cat_tasks = []
    last_code = 200
    
    for cat in CATEGORIES:
        code, tp = get_category_total_pages(session, cat["url"])
        if code > 0: last_code = code
        total_task_pages += tp
        cat_tasks.append((cat["type"], cat["url"], tp))
        
    status_msg = f"🌐 สถานะลิงก์: ปกติ (HTTP {last_code}) | ทั้งหมด 3 หมวด ({total_task_pages:,} หน้า) | {ITEMS_PER_PAGE} รายการ/หน้า ({total_task_pages*ITEMS_PER_PAGE:,} รายการ)"
    estimated_total = total_task_pages * ITEMS_PER_PAGE
    if estimated_total > 0 and len(all_records) > 0 and len(all_records) >= estimated_total:
        print(f"[{COMPANY_NAME}] 🎉 ข้อมูลใน CSV ครบถ้วน 100% แล้ว ({len(all_records):,}/{estimated_total:,} รายการ) -> สแครปเสร็จสมบูรณ์ทันที!", flush=True)
        save_to_csv(all_records, OUTPUT_CSV, session=session)
        return
        
    last_completed = load_state()
    if last_completed > 0:
        print(f"[{COMPANY_NAME}] ⏩ Fast-Forward: ข้ามหน้าที่เคยดึงสำเร็จแล้ว {last_completed:,} หน้า", flush=True)
        processed_pages = last_completed
    else:
        processed_pages = 0
        
    new_added = 0
    
    for ctype, curl, total_p in cat_tasks:
        pages_order = list(range(1, total_p + 1))
        if last_completed > 0:
            pages_order = [p for p in pages_order if p > last_completed]
            
        for p in pages_order:
            if estimated_total > 0 and len(all_records) >= estimated_total:
                print(f"\n[{COMPANY_NAME}] 🎉 สะสมข้อมูลครบถ้วนทั้งหมดแล้ว ({len(all_records):,}/{estimated_total:,} รายการ) -> สิ้นสุดการสแครป!", flush=True)
                break
            items = fetch_ddproperty_page(session, curl, ctype, p)
            if items is None:
                failed_pages.append(f"{ctype}-หน้า{p}")
                print(f"\n[{COMPANY_NAME}] ⚠️ ข้ามหมวด {ctype} หน้า {p} เนื่องจากดึงข้อมูลไม่สำเร็จ", flush=True)
                processed_pages += 1
                save_state(p)
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
                
            processed_pages += 1
            save_state(p)
            if page_added > 0:
                save_to_csv(all_records, OUTPUT_CSV, session=session)
                
            pct_pages = int((processed_pages / total_task_pages) * 100) if total_task_pages > 0 else 0
            pct_items = int((len(all_records) / estimated_total) * 100) if estimated_total > 0 else 0
            pct = min(100, max(pct_pages, pct_items))
            
            elapsed_sec = time.time() - start_time
            eta_msg = format_eta(elapsed_sec, processed_pages, total_task_pages)
            pbar = make_progress_bar(pct)
            
            print(f"[{COMPANY_NAME:<13s}] {pbar} | ({processed_pages:5,d}/{total_task_pages:5,d} หน้า) | สะสม: {len(all_records):>7,d} รายการ | {eta_msg}", flush=True)
            
            if len(all_records) >= 10 and "initial_10" not in saved_milestones:
                saved_milestones.add("initial_10")

            if total_task_pages > 0:
                for target_pct in [5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80, 85, 90, 95, 100]:
                    if pct >= target_pct and target_pct not in saved_milestones:
                        saved_milestones.add(target_pct)
                        
            time.sleep(0.5)
            
    print("", flush=True)
    save_to_csv(all_records, OUTPUT_CSV, session=session)
    elapsed = time.time() - start_time
    print(f"\n==================================================", flush=True)
    print(f"✅ [{COMPANY_NAME}] สแครปเสร็จสมบูรณ์!", flush=True)
    print(f"📊 ได้ข้อมูลทั้งหมด: {len(all_records):,} รายการ (เพิ่มใหม่ในรอบนี้: {new_added:,} รายการ)", flush=True)
    print(f"⏱️ ใช้เวลาทั้งหมด: {elapsed/60:.2f} นาที", flush=True)
    print(f"💾 ไฟล์ CSV: {OUTPUT_CSV}", flush=True)
    if failed_pages:
        print(f"⚠️ รายการหน้าที่ข้าม/ดึงไม่ได้ ({len(failed_pages)} หน้า): {failed_pages}", flush=True)
    else:
        print(f"✅ ดึงข้อมูลได้ครบถ้วนสำเร็จทุกหน้า (ไม่มีหน้าล้มเหลว)", flush=True)
    print(f"==================================================", flush=True)

if __name__ == "__main__":
    main()
