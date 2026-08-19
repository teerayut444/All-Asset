import os
import sys
import json
import re
import time
import subprocess
import threading
import pandas as pd
from datetime import datetime

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

COMPANY_NAME = "GSB"
MONTH_STR = datetime.now().strftime("%Y_%m")

_BASE_DIR = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(_BASE_DIR, "CSV_Output")
os.makedirs(OUTPUT_DIR, exist_ok=True)
OUTPUT_CSV = os.path.join(OUTPUT_DIR, f"GSB_NPA_New_{MONTH_STR}.csv")

SUBDISTRICT_GEOJSON = os.path.join(_BASE_DIR, "subdistricts.geojson")

COLUMNS = [
    "บริษัท", "ID", "รหัสทรัพย์", "ชื่อโครงการ", "ประเภททรัพย์", "ประเภทการขาย", "ราคา",
    "ตำบล", "อำเภอ", "จังหวัด", "ละติจูด", "ลองจิจูด", "ชื่อประกาศ", "ลิงก์",
    "เนื้อที่ (ตร.ว.)", "พื้นที่ใช้สอย (ตร.ม.)", "วันที่ดึงข้อมูล",
    "ห้องนอน", "ห้องน้ำ", "ที่จอดรถ", "วันประกาศ"
]

print_lock = threading.Lock()
geo_lookup = {}

def make_progress_bar(pct, length=20):
    filled = int(length * pct / 100)
    bar = '█' * filled + '░' * (length - filled)
    return f"[{bar}] {pct:3d}%"

def clean_text(t):
    if t is None:
        return ""
    return re.sub(r'\s+', ' ', str(t)).strip()

def load_geo_lookup():
    global geo_lookup
    if os.path.exists(SUBDISTRICT_GEOJSON):
        try:
            with open(SUBDISTRICT_GEOJSON, 'r', encoding='utf-8') as fp:
                data = json.load(fp)
            for feat in data.get('features', []):
                props = feat.get('properties', {})
                geom = feat.get('geometry', {})
                t_name = clean_text(props.get('tam_th'))
                a_name = clean_text(props.get('amp_th'))
                p_name = clean_text(props.get('pro_th'))
                
                coords = geom.get('coordinates', [])
                if coords:
                    def get_centroid(c_list):
                        pts = []
                        def extract_pts(cl):
                            if isinstance(cl, (list, tuple)) and len(cl) == 2 and isinstance(cl[0], (int, float)):
                                pts.append(cl)
                            elif isinstance(cl, (list, tuple)):
                                for sub in cl:
                                    extract_pts(sub)
                        extract_pts(c_list)
                        if pts:
                            avg_lon = sum(p[0] for p in pts) / len(pts)
                            avg_lat = sum(p[1] for p in pts) / len(pts)
                            return avg_lat, avg_lon
                        return None, None
                    lat, lon = get_centroid(coords)
                    if lat and lon:
                        key = f"{t_name}|{a_name}|{p_name}"
                        geo_lookup[key] = (round(lat, 6), round(lon, 6))
                        key_short = f"{a_name}|{p_name}"
                        if key_short not in geo_lookup:
                            geo_lookup[key_short] = (round(lat, 6), round(lon, 6))
        except Exception:
            pass

def get_coordinates(sub_d, dist, prov):
    t = clean_text(sub_d).replace("ต.", "").replace("ตำบล", "").strip()
    a = clean_text(dist).replace("อ.", "").replace("อำเภอ", "").replace("เขต", "").strip()
    p = clean_text(prov).replace("จ.", "").replace("จังหวัด", "").strip()
    
    key1 = f"{t}|{a}|{p}"
    if key1 in geo_lookup:
        return geo_lookup[key1]
        
    key2 = f"{a}|{p}"
    if key2 in geo_lookup:
        return geo_lookup[key2]
        
    return None, None

def parse_rai_ngan_wah_robust(s):
    if s is None or pd.isna(s):
        return None, None, None
    s = str(s).strip()
    if not s or s.lower() in ["nan", "none", "null", "$undefined", "-", "0", "0.0", "."]:
        return None, None, None
    
    m_dash = re.match(r'^(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)$', s)
    if m_dash:
        try:
            return float(m_dash.group(1)), float(m_dash.group(2)), float(m_dash.group(3))
        except ValueError:
            pass
        
    has_thai_units = any(u in s for u in ['ไร่', 'งาน', 'วา', 'ตร.ว', 'ตารางวา', 'ตร.ว.'])
    if has_thai_units:
        m_r = re.search(r'([\d\.,]+)\s*ไร่', s)
        m_g = re.search(r'([\d\.,]+)\s*งาน', s)
        m_w = re.search(r'([\d\.,]+)\s*(?:ตร\.?ว\.?|ตารางวา|วา)', s)
        
        r, g, w = 0.0, 0.0, 0.0
        try:
            if m_r: r = float(m_r.group(1).replace(',', ''))
        except ValueError: pass
        try:
            if m_g: g = float(m_g.group(1).replace(',', ''))
        except ValueError: pass
        try:
            if m_w: w = float(m_w.group(1).replace(',', ''))
        except ValueError: pass
        
        if r > 0 or g > 0 or w > 0:
            return r, g, w

    clean_num = re.sub(r'[^\d\.]', '', s)
    if clean_num and clean_num != '.' and clean_num != '..':
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

def fetch_json_via_curl(url, timeout_sec=15, max_attempts=4):
    for attempt in range(1, max_attempts + 1):
        try:
            cmd = [
                "curl.exe", "-s", "--max-time", str(timeout_sec),
                "-H", "x-nextjs-data: 1",
                "-H", "Accept: application/json, text/plain, */*",
                "-H", "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                url
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="ignore")
            if res.returncode == 0 and res.stdout:
                txt = res.stdout.strip()
                if txt.startswith("{") and txt.endswith("}"):
                    return json.loads(txt)
        except Exception:
            pass
        time.sleep(1.0)
    return None

def fetch_build_id():
    url = "https://npa-assets.gsb.or.th/"
    cmd = ["curl.exe", "-s", "--max-time", "15", url]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="ignore")
        if res.returncode == 0 and res.stdout:
            m = re.search(r'"buildId":"([^"]+)"', res.stdout)
            if m:
                return m.group(1)
            m2 = re.search(r'/_next/static/([^/]+)/_buildManifest\.js', res.stdout)
            if m2:
                return m2.group(1)
    except Exception:
        pass
    return "xBTQnpgUyEeVm1cFaJ68z"

def parse_gsb_item(item, dev_type, today_str):
    if not isinstance(item, dict):
        return None
        
    p_id = clean_text(item.get("asset_id") or item.get("id"))
    if not p_id:
        return None
        
    code = clean_text(item.get("asset_group_id_npa") or item.get("asset_group_id_npl") or item.get("asset_group_id") or p_id)
    p_type = clean_text(item.get("asset_type_desc") or item.get("asset_subtype_desc") or "ทรัพย์สิน")
    
    price = None
    for p_field in ["xprice", "current_offer_price", "xprice_normal", "group_sell_price"]:
        if item.get(p_field) is not None:
            try:
                price = float(str(item[p_field]).replace(",", ""))
                if price > 0:
                    break
            except Exception:
                pass
                
    sub_d = clean_text(item.get("sub_district_name"))
    dist = clean_text(item.get("district_name"))
    prov = clean_text(item.get("province_name"))
    
    lat, lng = None, None
    for lat_k in ["latitude", "lat", "geo_lat"]:
        if item.get(lat_k):
            try: lat = float(item[lat_k])
            except Exception: pass
    for lng_k in ["longitude", "long", "lng", "geo_long"]:
        if item.get(lng_k):
            try: lng = float(item[lng_k])
            except Exception: pass
            
    if lat is None or lng is None:
        lat, lng = get_coordinates(sub_d, dist, prov)
        
    proj_name = clean_text(item.get("asset_name") or item.get("building_name") or item.get("village_head"))
    if proj_name == "-":
        proj_name = ""
    title = f"ขาย{p_type} {proj_name}".strip() if proj_name else f"ขาย{p_type} {dist} {prov}".strip()
    
    # Area
    rai = item.get("sum_rai") or 0
    ngan = item.get("sum_ngan") or 0
    wah = item.get("sum_square_wa") or 0
    rai_str = item.get("rai_ngan_wa") or ""
    
    if rai or ngan or wah:
        area_fmt = convert_to_rai_ngan_wah(f"{rai}-{ngan}-{wah}")
    elif rai_str:
        area_fmt = convert_to_rai_ngan_wah(rai_str)
    else:
        area_fmt = ""
        
    usable_area = None
    sqm = item.get("square_meter")
    if sqm:
        try: usable_area = float(str(sqm).replace(",", ""))
        except Exception: pass
        
    sale_type = "ทรัพย์ธนาคาร"
    if dev_type.lower() == "npl":
        sale_type = "ทรัพย์ NPL"
    elif dev_type.lower() == "gsb":
        sale_type = "ทรัพย์ธนาคาร (GSB)"

    link = f"https://npa-assets.gsb.or.th/asset/{dev_type}/{p_id}"
    
    return {
        "บริษัท": COMPANY_NAME,
        "ID": p_id,
        "รหัสทรัพย์": code,
        "ชื่อโครงการ": proj_name,
        "ประเภททรัพย์": p_type,
        "ประเภทการขาย": sale_type,
        "ราคา": price,
        "ตำบล": sub_d,
        "อำเภอ": dist,
        "จังหวัด": prov,
        "ละติจูด": lat,
        "ลองจิจูด": lng,
        "ชื่อประกาศ": title,
        "ลิงก์": link,
        "เนื้อที่ (ตร.ว.)": area_fmt,
        "พื้นที่ใช้สอย (ตร.ม.)": usable_area,
        "วันที่ดึงข้อมูล": today_str,
        "ห้องนอน": None,
        "ห้องน้ำ": None,
        "ที่จอดรถ": None,
        "วันประกาศ": None
    }

def main():
    print(f"[{COMPANY_NAME}] 🚀 เริ่มต้นการดึงข้อมูลประจำเดือน {MONTH_STR}", flush=True)
    load_geo_lookup()
    
    build_id = fetch_build_id()
    print(f"[{COMPANY_NAME}] 🌐 ตรวจพบ Next.js buildId: {build_id}", flush=True)
    
    today_str = datetime.now().strftime("%Y-%m-%d")
    all_records = []
    seen_ids = set()
    
    categories = [
        ("npa", f"https://npa-assets.gsb.or.th/_next/data/{build_id}/asset/npa/all.json", 100),
        ("npl", f"https://npa-assets.gsb.or.th/_next/data/{build_id}/asset/npl.json", 100)
    ]
    
    for cat_dev, base_url, page_size in categories:
        print(f"[{COMPANY_NAME}] 🔍 กำลังดึงข้อมูลหมวด {cat_dev.upper()}...", flush=True)
        page = 1
        max_page = 1
        
        while page <= max_page:
            url = f"{base_url}?page={page}&page_size={page_size}"
            data = fetch_json_via_curl(url, timeout_sec=15, max_attempts=4)
            if not data:
                print(f"\n[{COMPANY_NAME}] ⚠️ ข้ามหน้า {page} ของหมวด {cat_dev.upper()}", flush=True)
                page += 1
                continue
                
            pageProps = data.get("pageProps", {})
            list_obj = pageProps.get("list") or pageProps.get("listNpa") or pageProps.get("listGsb") or pageProps.get("listNpl") or {}
            data_obj = list_obj.get("data", {})
            
            rows = data_obj.get("rows", []) if isinstance(data_obj, dict) else (data_obj if isinstance(data_obj, list) else [])
            total_count = data_obj.get("count") if isinstance(data_obj, dict) else (list_obj.get("asset_count") or len(rows))
            
            if total_count and max_page == 1:
                max_page = (int(total_count) + page_size - 1) // page_size
                print(f"[{COMPANY_NAME}] 📦 หมวด {cat_dev.upper()}: พบทั้งหมด {total_count:,} รายการ (~{max_page} หน้า)", flush=True)
                
            for it in rows:
                rec = parse_gsb_item(it, cat_dev, today_str)
                if rec and rec["ID"] not in seen_ids:
                    seen_ids.add(rec["ID"])
                    all_records.append(rec)
                    
            pct = int(page * 100 / max_page) if max_page > 0 else 100
            p_bar = make_progress_bar(pct, length=20)
            print(f"\r[{COMPANY_NAME:<13s}] {p_bar} | หมวด {cat_dev.upper():<3s} หน้า {page:2d}/{max_page:2d} | สะสม: {len(all_records):5,d} รายการ", end="", flush=True)
            
            if not rows and page > 1:
                break
            page += 1
            time.sleep(0.1)
            
        print()

    df = pd.DataFrame(all_records, columns=COLUMNS)
    df.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")
    print(f"[{COMPANY_NAME}] ✅ ดึงข้อมูลเสร็จสิ้น! บันทึกไฟล์ที่: {OUTPUT_CSV} รวม {len(df):,} รายการ", flush=True)

if __name__ == "__main__":
    main()
