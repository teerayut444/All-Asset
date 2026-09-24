import os
import sys
import re
import ast
import datetime
import urllib.parse
from pathlib import Path
import numpy as np
import pandas as pd
import streamlit as st

from modules.config.constants import (
    PROPERTY_TYPE_MAPPING,
    SALE_TYPE_MAPPING,
    PROVINCE_TO_REGION,
    is_true_centroid,
    get_price_tier
)
try:
    from clean_project_util import clean_sam_project_name as clean_project_name
except ImportError:
    try:
        import sys
        _scr_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "Py Scraper")
        if _scr_dir not in sys.path:
            sys.path.insert(0, _scr_dir)
        from clean_project_util import clean_sam_project_name as clean_project_name
    except Exception:
        from sam_analytics import clean_project_name

def parse_area_to_sqwah(area_str):
    """Helper function to parse 'พื้นที่ (ไร่-งาน-วา)' to square wah."""
    if pd.isna(area_str) or not isinstance(area_str, str) or str(area_str).strip() == "":
        return np.nan
    area_str = area_str.strip()
    
    parts = area_str.split('-')
    if len(parts) == 3:
        try:
            rai = float(parts[0]) if parts[0] else 0.0
            ngan = float(parts[1]) if parts[1] else 0.0
            wah = float(parts[2]) if parts[2] else 0.0
            return (rai * 400.0) + (ngan * 100.0) + wah
        except ValueError:
            pass
    elif len(parts) == 1:
        try:
            return float(parts[0])
        except ValueError:
            pass
            
    try:
        rai_match = re.search(r'(\d+(?:\.\d+)?)\s*ไร่', area_str)
        rai = float(rai_match.group(1)) if rai_match else 0.0
        
        ngan_match = re.search(r'(\d+(?:\.\d+)?)\s*งาน', area_str)
        ngan = float(ngan_match.group(1)) if ngan_match else 0.0
        
        wah_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:ตารางวา|ตร\.ว\.|วา)', area_str)
        wah = float(wah_match.group(1)) if wah_match else 0.0
        
        if rai > 0 or ngan > 0 or wah > 0:
            return (rai * 400.0) + (ngan * 100.0) + wah
    except Exception:
        pass
        
    return np.nan

def to_float_sqwah(val):
    """Converts any value (numeric or string like '2-0-57', '1 ไร่ 2 งาน', '50.5') to float square wah."""
    if pd.isna(val):
        return np.nan
    if isinstance(val, (int, float, np.number)):
        return float(val) if float(val) > 0 else np.nan
    val_str = str(val).strip()
    if not val_str or val_str in ['nan', 'None', '-', '']:
        return np.nan
    try:
        f = float(val_str)
        return f if f > 0 else np.nan
    except (ValueError, TypeError):
        return parse_area_to_sqwah(val_str)

def to_float_sqm(val):
    """Converts any usable area value to float square meters."""
    if pd.isna(val):
        return np.nan
    if isinstance(val, (int, float, np.number)):
        return float(val) if float(val) > 0 else np.nan
    val_str = str(val).strip()
    if not val_str or val_str in ['nan', 'None', '-', '']:
        return np.nan
    try:
        val_clean = re.sub(r'[^\d.]', '', val_str)
        f = float(val_clean)
        return f if f > 0 else np.nan
    except (ValueError, TypeError):
        return np.nan

def format_to_rai_ngan_wah(val):
    """Formats any land area value (sqwah float or text like '0-0-67' or '1 ไร่ 2 งาน') to 'X-Y-Z' (ไร่-งาน-ตร.ว.)"""
    if pd.isna(val):
        return "-"
    val_str = str(val).strip()
    if not val_str or val_str in ['nan', 'None', '-', '0', '0-0-0', '0-0-0.0']:
        return "-"
    if re.match(r'^\d+-\d+-\d+(?:\.\d+)?$', val_str):
        return "-" if val_str in ['0-0-0', '0-0-0.0'] else val_str
    sqwah = to_float_sqwah(val)
    if pd.isna(sqwah) or sqwah <= 0:
        return "-"
    sqwah = round(sqwah, 4)
    rai = int(sqwah // 400)
    rem = round(sqwah % 400, 4)
    ngan = int(rem // 100)
    wah = round(rem % 100, 2)
    wah_str = str(int(wah)) if wah == int(wah) else f"{wah:.1f}"
    return f"{rai}-{ngan}-{wah_str}"

def format_num_val(val):
    """Safely format numeric fields (e.g., bedrooms, area) to nice string."""
    if pd.isna(val) or str(val).strip() == "" or str(val).lower() == "nan" or val is None or str(val).lower() == "$undefined":
        return ""
    try:
        f_val = float(val)
        if f_val.is_integer():
            return str(int(f_val))
        return str(f_val)
    except ValueError:
        return str(val)

def get_clean_title(val):
    """Clean property title string."""
    if not val or pd.isna(val):
        return "ไม่มีชื่อประกาศ"
    val_str = str(val).strip()
    if val_str.startswith("{") and val_str.endswith("}"):
        try:
            d = ast.literal_eval(val_str)
            if isinstance(d, dict):
                return d.get('th') or d.get('en') or val_str
        except Exception:
            pass
    return val_str

def get_clean_link(val):
    """Clean property link string."""
    if not val or pd.isna(val):
        return ""
    val_str = str(val).strip()
    if val_str.startswith("{") and val_str.endswith("}"):
        try:
            d = ast.literal_eval(val_str)
            if isinstance(d, dict):
                return d.get('th') or d.get('en') or val_str
        except Exception:
            pass
    return val_str

@st.cache_data(show_spinner=False)
def get_dataset_month_year(_df):
    """Formats dataset date into Thai Month & Year (e.g. สิงหาคม 2569) and date range from start to latest extraction date."""
    thai_full_months = [
        'มกราคม', 'กุมภาพันธ์', 'มีนาคม', 'เมษายน', 'พฤษภาคม', 'มิถุนายน',
        'กรกฎาคม', 'สิงหาคม', 'กันยายน', 'ตุลาคม', 'พฤศจิกายน', 'ธันวาคม'
    ]
    thai_short_months = ['ม.ค.', 'ก.พ.', 'มี.ค.', 'เม.ย.', 'พ.ค.', 'มิ.ย.', 'ก.ค.', 'ส.ค.', 'ก.ย.', 'ต.ค.', 'พ.ย.', 'ธ.ค.']
    
    if _df is not None and not _df.empty and 'วันที่ดึงข้อมูล' in _df.columns:
        s_date = _df['วันที่ดึงข้อมูล'].dropna().astype(str).str.strip()
        s_date = s_date[~s_date.isin(['', 'nan', 'None', '-'])]
        if not s_date.empty:
            try:
                is_iso = s_date.str.match(r'^\d{4}[-/]\d{1,2}[-/]\d{1,2}')
                dts = pd.Series(index=s_date.index, dtype='datetime64[ns]')
                if is_iso.any():
                    dts.loc[is_iso] = pd.to_datetime(s_date[is_iso], format='mixed', dayfirst=False, errors='coerce')
                if (~is_iso).any():
                    dts.loc[~is_iso] = pd.to_datetime(s_date[~is_iso], format='mixed', dayfirst=True, errors='coerce')
                dts = dts.dropna()
                
                if not dts.empty:
                    min_dt = dts.min()
                    max_dt = dts.max()
                    
                    max_year = max_dt.year + 543 if max_dt.year < 2500 else max_dt.year
                    min_year = min_dt.year + 543 if min_dt.year < 2500 else min_dt.year
                    
                    month_name = thai_full_months[max_dt.month - 1]
                    max_short_m = thai_short_months[max_dt.month - 1]
                    min_short_m = thai_short_months[min_dt.month - 1]
                    
                    month_year_str = f"{month_name} {max_year}"
                    
                    if min_dt.date() == max_dt.date():
                        exact_date_str = f"{max_dt.day} {max_short_m} {max_year}"
                    elif min_dt.year == max_dt.year and min_dt.month == max_dt.month:
                        exact_date_str = f"{min_dt.day} - {max_dt.day} {max_short_m} {max_year}"
                    elif min_dt.year == max_dt.year:
                        exact_date_str = f"{min_dt.day} {min_short_m} - {max_dt.day} {max_short_m} {max_year}"
                    else:
                        exact_date_str = f"{min_dt.day} {min_short_m} {min_year} - {max_dt.day} {max_short_m} {max_year}"
                        
                    return month_year_str, exact_date_str
            except Exception:
                pass
    try:
        p_path = Path("all_asset.parquet") if Path("all_asset.parquet").exists() else Path("all_assets.parquet")
        if p_path.exists():
            dt = datetime.datetime.fromtimestamp(p_path.stat().st_mtime)
            thai_year = dt.year + 543 if dt.year < 2500 else dt.year
            month_name = thai_full_months[dt.month - 1]
            short_month = thai_short_months[dt.month - 1]
            return f"{month_name} {thai_year}", f"{dt.day} {short_month} {thai_year}"
    except Exception:
        pass
    return "สิงหาคม 2569", "11 - 20 ส.ค. 2569"

def ensure_derived_cols(df):
    """Enriches and normalizes the properties dataset with standard columns, categories, and parsed values."""
    if df is None or df.empty:
        return df

    if 'ประเภททรัพย์' in df.columns:
        prop_type_map = PROPERTY_TYPE_MAPPING
        u_types = df['ประเภททรัพย์'].dropna().unique()
        lower_prop_map = {k.lower(): v for k, v in prop_type_map.items()}

        def _resolve_single_type(t):
            s = str(t).strip()
            if s in prop_type_map:
                return prop_type_map[s]
            sl = s.lower()
            if sl in lower_prop_map:
                return lower_prop_map[sl]
            if sl.startswith('semi-detached') or 'twin house' in sl:
                return 'บ้านแฝด'
            if sl.startswith('town'):
                return 'ทาวน์เฮ้าส์'
            if 'condo' in sl or sl in ['penthouse', 'duplex']:
                return 'ห้องชุดพักอาศัย'
            if sl.startswith('villa'):
                return 'วิลล่า'
            if sl == 'land' or sl.startswith('land '):
                return 'ที่ดินพร้อมสิ่งปลูกสร้าง' if 'building' in sl else 'ที่ดินเปล่า'
            if 'detached house' in sl or sl == 'single house' or sl == 'house':
                return 'บ้านเดี่ยว'
            if 'shophouse' in sl or 'commercial' in sl or sl == 'retail':
                return 'อาคารพาณิชย์'
            if 'apartment' in sl:
                return 'อพาร์ทเมนท์'
            if 'warehouse' in sl or 'factory' in sl:
                return 'โรงงาน/โกดัง'
            if 'office' in sl:
                return 'อาคารสำนักงาน'
            if 'hotel' in sl or 'resort' in sl:
                return 'โรงแรม/รีสอร์ท'
            return s

        type_lut = {t: _resolve_single_type(t) for t in u_types}
        df['ประเภททรัพย์'] = df['ประเภททรัพย์'].map(type_lut).fillna('อื่นๆ')
        
        mixed_mask = df['ประเภททรัพย์'].astype(str).str.contains('บ้านเดี่ยว/ทาวน์', na=False)
        if mixed_mask.any():
            def resolve_row(row):
                title = (str(row.get('ชื่อประกาศ', '')) + ' ' + str(row.get('ชื่อโครงการ', ''))).lower()
                if any(k in title for k in ['ตึกแถว', 'อาคารพาณิชย์', 'shophouse', 'พาณิชย์']):
                    return 'อาคารพาณิชย์'
                if any(k in title for k in ['โฮมออฟฟิศ', 'สำนักงาน', 'office', 'home office']):
                    return 'อาคารสำนักงาน'
                if any(k in title for k in ['โกดัง', 'โรงงาน', 'warehouse', 'factory']):
                    return 'โรงงาน/โกดัง'
                if any(k in title for k in ['ทาวน์โฮม', 'ทาวน์เฮ้าส์', 'ทาวน์เฮาส์', 'townhome', 'townhouse', 'ทาวน์']):
                    return 'ทาวน์เฮ้าส์'
                if any(k in title for k in ['ที่ดิน', 'land']):
                    return 'ที่ดินเปล่า'
                if any(k in title for k in ['คอนโด', 'ห้องชุด', 'condo']):
                    return 'ห้องชุดพักอาศัย'
                return 'บ้านเดี่ยว'
            df.loc[mixed_mask, 'ประเภททรัพย์'] = df[mixed_mask].apply(resolve_row, axis=1)

    if 'ประเภทการขาย' in df.columns:
        df = df[df['ประเภทการขาย'].astype(str).str.strip() != 'ให้เช่า']
        df = df[~df['ประเภทการขาย'].astype(str).str.contains('NPL', case=False, na=False)]
        sale_map = SALE_TYPE_MAPPING
        u_sales = df['ประเภทการขาย'].dropna().unique()
        sale_lut = {s: sale_map.get(str(s).strip(), str(s).strip()) for s in u_sales}
        df['ประเภทการขาย'] = df['ประเภทการขาย'].map(sale_lut).fillna('ขาย')

    if 'ชื่อโครงการ' in df.columns:
        u_proj = df['ชื่อโครงการ'].dropna().unique()
        p_lut = {p: clean_project_name(p) for p in u_proj}
        df['ชื่อโครงการ'] = df['ชื่อโครงการ'].map(p_lut)

    if 'ชื่อประกาศ' not in df.columns:
        if 'ชื่อโครงการ' in df.columns:
            df['ชื่อประกาศ'] = df['ชื่อโครงการ'].fillna('ไม่มีชื่อ').astype(str)
        else:
            df['ชื่อประกาศ'] = df['รหัสทรัพย์'].fillna('ทรัพย์สิน NPA').astype(str)
    else:
        df['ชื่อประกาศ'] = df['ชื่อประกาศ'].fillna('ไม่มีชื่อ').astype(str)

    if 'ลิงก์' not in df.columns:
        df['ลิงก์'] = ""
    else:
        df['ลิงก์'] = df['ลิงก์'].astype(object).fillna("").astype(str)

    # Ensure LED links use the smart lawsuit Auto-POST bridge
    if 'บริษัท' in df.columns and 'รหัสทรัพย์' in df.columns:
        led_mask = (df['บริษัท'] == 'LED')
        if led_mask.any():
            def make_led_bridge_url(code):
                s = str(code).strip()
                if not s or s in ['nan', 'None', '-']:
                    return "https://asset.led.go.th/newbidreg/asset_search_law_suit.asp"
                if '/' in s:
                    parts = s.split('/')
                    s_no, s_yr = parts[0].strip(), parts[1].strip()
                    return f"app/static/led_bridge.html?suit_no={urllib.parse.quote(s_no)}&suit_year={urllib.parse.quote(s_yr)}"
                return f"app/static/led_bridge.html?suit_no={urllib.parse.quote(s)}"
            
            df.loc[led_mask, 'ลิงก์'] = df.loc[led_mask, 'รหัสทรัพย์'].apply(make_led_bridge_url)

    if 'ราคา' in df.columns:
        df['ราคา'] = pd.to_numeric(df['ราคา'], errors='coerce')
        df.loc[df['ราคา'] < 1000, 'ราคา'] = np.nan
    else:
        df['ราคา'] = np.nan

    if 'พื้นที่_ตารางวา' not in df.columns:
        if 'เนื้อที่_ตารางวา' in df.columns:
            df['พื้นที่_ตารางวา'] = pd.to_numeric(df['เนื้อที่_ตารางวา'], errors='coerce')
        elif 'เนื้อที่ (ตร.ว.)' in df.columns:
            df['พื้นที่_ตารางวา'] = df['เนื้อที่ (ตร.ว.)'].apply(parse_area_to_sqwah)
        elif 'พื้นที่ (ไร่-งาน-วา)' in df.columns:
            df['พื้นที่_ตารางวา'] = df['พื้นที่ (ไร่-งาน-วา)'].apply(parse_area_to_sqwah)
        else:
            df['พื้นที่_ตารางวา'] = np.nan
    else:
        df['พื้นที่_ตารางวา'] = pd.to_numeric(df['พื้นที่_ตารางวา'], errors='coerce')

    if 'พื้นที่ใช้สอย (ตร.ม.)' not in df.columns:
        df['พื้นที่ใช้สอย (ตร.ม.)'] = np.nan
    else:
        df['พื้นที่ใช้สอย (ตร.ม.)'] = pd.to_numeric(df['พื้นที่ใช้สอย (ตร.ม.)'], errors='coerce')
        bad_area_mask = (df['ราคา'] > 10000) & (df['พื้นที่ใช้สอย (ตร.ม.)'] == df['ราคา'])
        if 'ประเภททรัพย์' in df.columns:
            bad_area_mask |= (df['ประเภททรัพย์'].isin(['คอนโด', 'ห้องชุด', 'ทาวน์เฮ้าส์', 'ทาวน์โฮม']) & (df['พื้นที่ใช้สอย (ตร.ม.)'] > 5000))
        df.loc[bad_area_mask, 'พื้นที่ใช้สอย (ตร.ม.)'] = np.nan

    if 'ราคาต่อตารางวา' not in df.columns:
        df['ราคาต่อตารางวา'] = np.where((df['พื้นที่_ตารางวา'] > 0) & (df['ราคา'] > 0), df['ราคา'] / df['พื้นที่_ตารางวา'], np.nan)
    else:
        df['ราคาต่อตารางวา'] = pd.to_numeric(df['ราคาต่อตารางวา'], errors='coerce')

    if 'ราคาต่อตารางเมตร' not in df.columns or df['ราคาต่อตารางเมตร'].isna().sum() > 0:
        df['ราคาต่อตารางเมตร'] = np.where((df['พื้นที่ใช้สอย (ตร.ม.)'] > 0) & (df['ราคา'] > 0), df['ราคา'] / df['พื้นที่ใช้สอย (ตร.ม.)'], np.nan)
    else:
        df['ราคาต่อตารางเมตร'] = pd.to_numeric(df['ราคาต่อตารางเมตร'], errors='coerce')

    if 'จังหวัด' in df.columns:
        def _clean_prov_val(v):
            if pd.isna(v):
                return np.nan
            s = str(v).strip().strip(" ,;.-'\"/\\")
            s = re.sub(r'^(จ\.|จังหวัด)\s*', '', s).strip()
            if s in ['กทม', 'กทม.', 'กรุงเทพ', 'กรุงเทพฯ']:
                s = 'กรุงเทพมหานคร'
            elif s in ['อยุธยา']:
                s = 'พระนครศรีอยุธยา'
            if s in ['', '-', 'nan', 'None', '<NA>', 'ไม่มีข้อมูล']:
                return np.nan
            return s

        df['จังหวัด'] = df['จังหวัด'].apply(_clean_prov_val)
        df['ภาค'] = df['จังหวัด'].map(PROVINCE_TO_REGION).fillna('อื่นๆ / ไม่ระบุ')

    if 'ชั้น' not in df.columns:
        df['ชั้น'] = None
    else:
        df['ชั้น'] = df['ชั้น'].replace({'nan': None, 'None': None, 'null': None, '<NA>': None, 'NaN': None, '-': None, '': None})

    if 'เลขโฉนด' not in df.columns:
        df['เลขโฉนด'] = None
    else:
        df['เลขโฉนด'] = df['เลขโฉนด'].replace({'nan': None, 'None': None, 'null': None, '<NA>': None, 'NaN': None, '-': None, '': None})

    if 'ยอดเข้าชม' not in df.columns:
        df['ยอดเข้าชม'] = None
    else:
        df['ยอดเข้าชม'] = pd.to_numeric(df['ยอดเข้าชม'], errors='coerce').astype('Int32')

    if 'ยอดคลิก' not in df.columns:
        df['ยอดคลิก'] = None
    else:
        df['ยอดคลิก'] = pd.to_numeric(df['ยอดคลิก'], errors='coerce').astype('Int32')

    if 'อำเภอ' in df.columns:
        df['อำเภอ'] = df['อำเภอ'].astype(str).str.strip().str.strip(" ,;.-'\"/\\")
        df['อำเภอ'] = df['อำเภอ'].replace({'nan': np.nan, 'None': np.nan, '<NA>': np.nan, '-': np.nan, '': np.nan})
        en_amp_mask = df['อำเภอ'].astype(str).str.contains(r'[a-zA-Z]', regex=True, na=False)
        if en_amp_mask.any():
            try:
                base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                for cand in [base_dir, os.path.join(base_dir, "Py Scraper"), os.path.join(base_dir, "Monthly all new")]:
                    if cand not in sys.path and os.path.exists(cand):
                        sys.path.insert(0, cand)
                from clean_location_util import translate_amphoe_en_to_th
                def _safe_clean_amp(val):
                    res = translate_amphoe_en_to_th(val)
                    return res if re.match(r'^[ก-๙]', str(res or '')) else 'ไม่มีข้อมูล'
                df.loc[en_amp_mask, 'อำเภอ'] = df.loc[en_amp_mask, 'อำเภอ'].apply(_safe_clean_amp)
            except Exception:
                df.loc[en_amp_mask, 'อำเภอ'] = df.loc[en_amp_mask, 'อำเภอ'].astype(str).apply(
                    lambda s: re.sub(r'[a-zA-Z\(\)\[\]]+', '', s).strip() if re.search(r'[ก-๙]', s) else 'ไม่มีข้อมูล'
                )

    if 'ตำบล' in df.columns:
        df['ตำบล'] = df['ตำบล'].astype(str).str.strip().str.strip(" ,;.-'\"/\\")
        df['ตำบล'] = df['ตำบล'].replace({'nan': np.nan, 'None': np.nan, '<NA>': np.nan, '-': np.nan, '': np.nan})
        en_tam_mask = df['ตำบล'].astype(str).str.contains(r'[a-zA-Z]', regex=True, na=False)
        if en_tam_mask.any():
            df.loc[en_tam_mask, 'ตำบล'] = df.loc[en_tam_mask, 'ตำบล'].astype(str).apply(
                lambda s: re.sub(r'[a-zA-Z\(\)\[\]]+', '', s).strip() if re.search(r'[ก-๙]', s) else 'ไม่มีข้อมูล'
            )

    # Convert repeated string columns to category for 5x faster filtering and 70% less RAM
    for col in ['บริษัท', 'ประเภททรัพย์', 'จังหวัด', 'ภาค', 'ประเภทการขาย']:
        if col in df.columns:
            df[col] = df[col].astype('category')

    return df
