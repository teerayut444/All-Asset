import os
import re
import json
import gzip
import base64
from pathlib import Path
import numpy as np
import pandas as pd
import streamlit as st

from modules.services.data_cleaner import ensure_derived_cols
from modules.services.geo_service import (
    get_map_icon_atlas_and_mapping,
    get_leaflet_logo_dict,
    get_official_gis_reference
)

def get_latest_parquet_path():
    """Find the newest dated all_assets_YYYY_MM_DD.parquet file, fallback to all_asset.parquet or all_assets.parquet."""
    candidates = list(Path(".").glob("all_assets_*.parquet"))
    dated = [p for p in candidates if not p.name.endswith("_no_centroid.parquet") and re.match(r'^all_assets_\d{4}_\d{2}_\d{2}\.parquet$', p.name)]
    if dated:
        dated.sort(key=lambda p: (p.name, p.stat().st_mtime), reverse=True)
        return dated[0]
    if Path("all_asset.parquet").exists():
        return Path("all_asset.parquet")
    return Path("all_assets.parquet")

def get_data_mtime():
    """Get modification timestamp of the active parquet data file."""
    p = get_latest_parquet_path()
    if p.exists():
        return p.stat().st_mtime
    for fallback_name in ["all_asset.parquet", "all_assets.parquet"]:
        p_fallback = Path(fallback_name)
        if p_fallback.exists():
            return p_fallback.stat().st_mtime
    return 0

@st.cache_data(ttl=3600, show_spinner="กำลังโหลดฐานข้อมูลทรัพย์สิน (Parquet)...")
def load_properties_data(data_version=0):
    """Load property dataset from Parquet file and run initial derivation/enrichment."""
    parquet_file = get_latest_parquet_path()
    if not parquet_file.exists():
        if Path("all_asset.parquet").exists():
            parquet_file = Path("all_asset.parquet")
        elif Path("all_assets.parquet").exists():
            parquet_file = Path("all_assets.parquet")
    
    if not parquet_file.exists():
        st.error("ไม่พบไฟล์ข้อมูล 'all_asset.parquet' กรุณารันสคริปต์ convert_csv_to_parquet.py เพื่อสร้างไฟล์")
        return None

    try:
        df = pd.read_parquet(parquet_file)
        df = ensure_derived_cols(df)
        df.attrs['source'] = parquet_file.name
        return df
    except Exception as e:
        st.error(f"เกิดข้อผิดพลาดในการโหลดไฟล์ Parquet: {e}")
        return None

@st.cache_data(show_spinner=False)
def get_sam_project_options(_df):
    """Pre-computes and caches list of SAM projects and their unit counts across all companies."""
    if _df is None or _df.empty or 'ชื่อโครงการ' not in _df.columns or 'บริษัท' not in _df.columns:
        return [], {}
    sam_mask = _df['บริษัท'].astype(str).str.strip().str.upper() == 'SAM'
    sam_projs = set(_df[sam_mask]['ชื่อโครงการ'].dropna().astype(str).str.strip())
    sam_projs = {p for p in sam_projs if p and p not in ['-', 'ไม่มีชื่อ', 'nan', 'None', 'ไม่ระบุ', 'null', 'undefined']}
    
    valid_df = _df[_df['ชื่อโครงการ'].astype(str).str.strip().isin(sam_projs)]
    sam_cnt = valid_df[valid_df['บริษัท'].astype(str).str.strip().str.upper() == 'SAM']['ชื่อโครงการ'].astype(str).str.strip().value_counts()
    other_cnt = valid_df[valid_df['บริษัท'].astype(str).str.strip().str.upper() != 'SAM']['ชื่อโครงการ'].astype(str).str.strip().value_counts()
    
    # Strictly filter for projects where sam_cnt > 0
    sam_projs = {p for p in sam_projs if int(sam_cnt.get(p, 0)) > 0}
    
    def sort_key(p):
        o = int(other_cnt.get(p, 0))
        s = int(sam_cnt.get(p, 0))
        return (1 if o > 0 else 0, o, s)
    
    sorted_projs = sorted(list(sam_projs), key=sort_key, reverse=True)
    labels = {}
    for p in sorted_projs:
        s = int(sam_cnt.get(p, 0))
        o = int(other_cnt.get(p, 0))
        if o > 0:
            labels[p] = f"{p} (SAM: {s}, คู่แข่ง: {o})"
        else:
            labels[p] = f"{p} (SAM: {s})"
    return sorted_projs, labels

@st.cache_data(show_spinner=False)
def get_cached_sidebar_metadata(_df):
    """Pre-computes and caches unique values for sidebar dropdowns and pills to prevent recalculation overhead."""
    if _df is None or _df.empty:
        return {}
    
    co_counts = _df['บริษัท'].value_counts().to_dict()
    raw_comps = [str(c) for c in _df['บริษัท'].dropna().unique() if str(c).strip() not in ['', 'nan', 'None']]
    COMPANY_PRIORITY = ["LED", "SAM", "BAM", "Chayo555", "Chayo", "GHB", "KBANK", "KTB", "SCB", "GSB", "DDproperty", "Livinginsider", "NaYoo", "ZmyHome", "Baania"]
    companies_list = sorted(
        raw_comps,
        key=lambda c: (COMPANY_PRIORITY.index(c) if c in COMPANY_PRIORITY else 999, c)
    )
    if not companies_list:
        companies_list = ["LED", "SAM", "BAM", "Chayo555", "GHB", "KBANK", "KTB", "SCB", "GSB", "DDproperty", "Livinginsider", "NaYoo", "ZmyHome", "Baania"]

    PROMINENT_TYPES = [
        "บ้านเดี่ยว", "ห้องชุดพักอาศัย", "ทาวน์เฮ้าส์", "ที่ดินเปล่า",
        "ที่ดินพร้อมสิ่งปลูกสร้าง", "อาคารพาณิชย์", "วิลล่า", "โรงงาน/โกดัง", "บ้านแฝด",
        "อพาร์ทเมนท์", "อาคารสำนักงาน", "โรงแรม/รีสอร์ท", "ห้องชุดพาณิชยกรรม/สำนักงาน"
    ]
    type_counts = _df['ประเภททรัพย์'].value_counts().to_dict()
    common_types = [t for t in PROMINENT_TYPES if t in type_counts]
    for t in type_counts:
        if t not in common_types and type_counts[t] >= 80 and t != "อื่นๆ":
            common_types.append(t)
    rare_types = [t for t in type_counts if t not in common_types]

    sale_type_counts = {}
    if 'ประเภทการขาย' in _df.columns:
        s_series = _df['ประเภทการขาย'].dropna().astype(str).str.strip()
        sale_type_counts = s_series[~s_series.isin(["", "nan", "None"])].value_counts().to_dict()

    region_counts = {}
    if 'ภาค' in _df.columns:
        r_series = _df['ภาค'].dropna().astype(str).str.strip()
        region_counts = r_series.value_counts().to_dict()

    official_pairs, official_provs, official_dists = get_official_gis_reference()
    INVALID_LOC_VALUES = {"", "nan", "none", "null", "undefined", "-", "ไม่มีข้อมูล", "ไม่ระบุ"}

    provinces_pool = sorted(list({
        str(p).strip().strip(" ,;.-'\"") for p in _df['จังหวัด'].dropna().unique()
        if str(p).strip().strip(" ,;.-'\"") and str(p).strip().strip(" ,;.-'\"").lower() not in INVALID_LOC_VALUES
    }))
    if official_provs:
        provinces_pool = [p for p in provinces_pool if p in official_provs]
    if "ไม่ระบุ" in provinces_pool:
        provinces_pool.remove("ไม่ระบุ")

    # Pre-compute full district lookup (province -> sorted list of districts)
    district_by_province = {}
    all_districts_formatted = []
    if 'อำเภอ' in _df.columns and 'จังหวัด' in _df.columns:
        dist_cols = _df[['อำเภอ', 'จังหวัด']].drop_duplicates().dropna()
        dist_cols = dist_cols[
            ~dist_cols['อำเภอ'].astype(str).str.strip().str.lower().isin(INVALID_LOC_VALUES) &
            ~dist_cols['จังหวัด'].astype(str).str.strip().str.lower().isin(INVALID_LOC_VALUES) &
            (dist_cols['อำเภอ'].astype(str).str.strip().str.len() > 1)
        ]
        for a, p in zip(dist_cols['อำเภอ'], dist_cols['จังหวัด']):
            p_str, a_str = str(p).strip(), str(a).strip()
            if official_pairs and (a_str, p_str) not in official_pairs:
                continue
            if p_str not in district_by_province:
                district_by_province[p_str] = []
            district_by_province[p_str].append(a_str)
        for p_str in district_by_province:
            district_by_province[p_str] = sorted(set(district_by_province[p_str]))

        all_dist_formatted_list = []
        for p_str, d_list in district_by_province.items():
            for d_str in d_list:
                all_dist_formatted_list.append(f"{d_str} ({p_str})")
        all_districts_formatted = sorted(set(all_dist_formatted_list))

    subdistrict_by_province = {}
    subdistrict_by_district = {}
    if all(c in _df.columns for c in ['ตำบล', 'อำเภอ', 'จังหวัด']):
        sub_cols = _df[['ตำบล', 'อำเภอ', 'จังหวัด']].drop_duplicates().dropna()
        sub_cols = sub_cols[
            ~sub_cols['ตำบล'].astype(str).str.strip().str.lower().isin(INVALID_LOC_VALUES) &
            ~sub_cols['อำเภอ'].astype(str).str.strip().str.lower().isin(INVALID_LOC_VALUES) &
            ~sub_cols['จังหวัด'].astype(str).str.strip().str.lower().isin(INVALID_LOC_VALUES) &
            (sub_cols['ตำบล'].astype(str).str.strip().str.len() > 1)
        ]

        for p, d, t in zip(sub_cols['จังหวัด'], sub_cols['อำเภอ'], sub_cols['ตำบล']):
            p_str, d_str, t_str = str(p).strip(), str(d).strip(), str(t).strip()
            if official_pairs and (d_str, p_str) not in official_pairs:
                continue
            fmt = f"{t_str} ({d_str}, {p_str})"
            if p_str not in subdistrict_by_province:
                subdistrict_by_province[p_str] = []
            subdistrict_by_province[p_str].append(fmt)

            k = (p_str, d_str)
            if k not in subdistrict_by_district:
                subdistrict_by_district[k] = []
            subdistrict_by_district[k].append(fmt)

        for p_str in subdistrict_by_province:
            subdistrict_by_province[p_str] = sorted(set(subdistrict_by_province[p_str]))
        for k in subdistrict_by_district:
            subdistrict_by_district[k] = sorted(set(subdistrict_by_district[k]))

    return {
        'co_counts': co_counts,
        'companies_list': companies_list,
        'common_types': common_types,
        'rare_types': rare_types,
        'type_counts': type_counts,
        'sale_type_counts': sale_type_counts,
        'region_counts': region_counts,
        'unique_provinces': provinces_pool,
        'district_by_province': district_by_province,
        'all_districts_formatted': all_districts_formatted,
        'subdistrict_by_province': subdistrict_by_province,
        'subdistrict_by_district': subdistrict_by_district,
    }

@st.cache_data(show_spinner=False)
def get_base_map_html(_mtime=None):
    """Load the base HTML template for Leaflet/Deck.gl interactive map."""
    try:
        with open("static/map_template.html", "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""

@st.cache_data(show_spinner=False)
def get_precomputed_map_payload(data_mtime):
    """Precomputes and caches the entire 440k dataset map data, GZIP csv_base64, and lookup_b64."""
    df = load_properties_data(data_mtime)
    if df is None or df.empty:
        return "", "", "", 0

    map_data = df[
        df['ละติจูด'].notna() & df['ลองจิจูด'].notna() &
        df['ละติจูด'].between(5, 21) & df['ลองจิจูด'].between(97, 106)
    ].copy()
    if map_data.empty:
        return "", "", "", 0

    map_data_full_len = len(map_data)
    _prices_num = pd.to_numeric(map_data['ราคา'], errors='coerce')
    _valid_price = _prices_num.notna() & (_prices_num > 0)
    map_data['ราคาขาย'] = 'ไม่ระบุ'
    if _valid_price.any():
        map_data.loc[_valid_price, 'ราคาขาย'] = (
            '฿' + _prices_num[_valid_price].map('{:,.0f}'.format) + ' บาท'
        )

    _p_wah = pd.to_numeric(map_data['ราคาต่อตารางวา'], errors='coerce') if 'ราคาต่อตารางวา' in map_data.columns else pd.Series(np.nan, index=map_data.index)
    _p_sqm = pd.to_numeric(map_data['ราคาต่อตารางเมตร'], errors='coerce') if 'ราคาต่อตารางเมตร' in map_data.columns else pd.Series(np.nan, index=map_data.index)
    _sqw_calc = pd.to_numeric(map_data.get('พื้นที่_ตารางวา', np.nan), errors='coerce')
    _sqm_calc = pd.to_numeric(map_data.get('พื้นที่ใช้สอย (ตร.ม.)', np.nan), errors='coerce')
    _p_wah_calc = np.where((_p_wah > 0), _p_wah, np.where((_sqw_calc > 0) & (_prices_num > 0), _prices_num / _sqw_calc, np.nan))
    _p_sqm_calc = np.where((_p_sqm > 0), _p_sqm, np.where((_sqm_calc > 0) & (_prices_num > 0), _prices_num / _sqm_calc, np.nan))
    _ptype_str = map_data['ประเภททรัพย์'].astype(str) if 'ประเภททรัพย์' in map_data.columns else pd.Series('', index=map_data.index)
    _is_condo = _ptype_str.str.contains('ห้องชุด|คอนโด|อาคารชุด', na=False)
    _unit_prices = np.where(
        _is_condo,
        np.where(pd.notna(_p_sqm_calc) & (_p_sqm_calc > 0), _p_sqm_calc, np.where(pd.notna(_p_wah_calc) & (_p_wah_calc > 0), _p_wah_calc, 0.0)),
        np.where(pd.notna(_p_wah_calc) & (_p_wah_calc > 0), _p_wah_calc, np.where(pd.notna(_p_sqm_calc) & (_p_sqm_calc > 0), _p_sqm_calc, 0.0))
    )

    title_col = 'ชื่อประกาศ' if 'ชื่อประกาศ' in map_data.columns else ('ชื่อโครงการ' if 'ชื่อโครงการ' in map_data.columns else 'รหัสทรัพย์')
    titles = map_data[title_col].fillna('ไม่มีชื่อ').astype(str).str.strip().str[:80].tolist()
    ids = map_data['รหัสทรัพย์'].fillna('-').astype(str).str.strip().tolist()
    prices_list = map_data['ราคาขาย'].astype(str).tolist()

    led_mask = map_data['บริษัท'].fillna('').astype(str).str.upper().str.strip() == 'LED'
    if 'is_centroid' in map_data.columns:
        centroid_mask = (map_data['is_centroid'].fillna(False).astype(bool)) | led_mask
    else:
        centroid_mask = led_mask
    centroid_flags = centroid_mask.astype('uint8').tolist()

    centroid_per_company = (
        map_data.loc[centroid_mask, 'บริษัท'].fillna('-').value_counts().to_dict()
    )

    COMPANY_MAP_RGB = {
        "LED": [8, 145, 178], "SAM": [16, 185, 129], "BAM": [59, 130, 246],
        "Chayo555": [249, 115, 22], "GHB": [202, 138, 4], "KBANK": [5, 150, 105],
        "KTB": [2, 132, 199], "SCB": [126, 34, 206], "GSB": [235, 25, 133],
        "DDproperty": [168, 85, 247], "Livinginsider": [20, 184, 166],
        "NaYoo": [139, 92, 246], "ZmyHome": [236, 72, 153], "Baania": [245, 158, 11]
    }
    DEFAULT_COLOR = [148, 163, 184]
    _uco = map_data['บริษัท'].unique()
    _r_co = {c: COMPANY_MAP_RGB.get(c, DEFAULT_COLOR)[0] for c in _uco}
    _g_co = {c: COMPANY_MAP_RGB.get(c, DEFAULT_COLOR)[1] for c in _uco}
    _b_co = {c: COMPANY_MAP_RGB.get(c, DEFAULT_COLOR)[2] for c in _uco}
    r_arr = map_data['บริษัท'].map(_r_co).fillna(DEFAULT_COLOR[0]).astype('uint8')
    g_arr = map_data['บริษัท'].map(_g_co).fillna(DEFAULT_COLOR[1]).astype('uint8')
    b_arr = map_data['บริษัท'].map(_b_co).fillna(DEFAULT_COLOR[2]).astype('uint8')

    co_counts = map_data['บริษัท'].value_counts()
    legend_items_html = ['<div style="font-weight: 600; font-size: 11px; text-transform: uppercase; color: #64748b; margin-bottom: 4px; letter-spacing: 0.5px;">บริษัททรัพย์สิน</div>']
    for co_name, co_rgb in COMPANY_MAP_RGB.items():
        c_cnt = co_counts.get(co_name, 0)
        if c_cnt > 0:
            hex_c = f"rgb({co_rgb[0]},{co_rgb[1]},{co_rgb[2]})"
            c_centroid = centroid_per_company.get(co_name, 0)
            centroid_tag = f' <span class="legend-centroid-badge" style="background:#fef3c7; color:#92400e; font-size:9.5px; font-weight:800; padding:0px 4px; border-radius:4px; border:1px solid #fde68a;">&#9651; {c_centroid:,}</span>' if c_centroid > 0 else ''
            legend_items_html.append(f'<div class="legend-item"><span class="legend-color" style="background:{hex_c};"></span>{co_name} ({c_cnt:,}){centroid_tag}</div>')
    other_co_cnt = sum(cnt for co, cnt in co_counts.items() if co not in COMPANY_MAP_RGB)
    if other_co_cnt > 0:
        other_co_names = [co for co in co_counts.index if co not in COMPANY_MAP_RGB]
        other_co_centroid = sum(centroid_per_company.get(co, 0) for co in other_co_names)
        other_centroid_tag = f' <span class="legend-centroid-badge" style="background:#fef3c7; color:#92400e; font-size:9.5px; font-weight:800; padding:0px 4px; border-radius:4px; border:1px solid #fde68a;">&#9651; {other_co_centroid:,}</span>' if other_co_centroid > 0 else ''
        legend_items_html.append(f'<div class="legend-item"><span class="legend-color" style="background:#94a3b8;"></span>อื่นๆ ({other_co_cnt:,}){other_centroid_tag}</div>')
    total_centroid_count = sum(centroid_per_company.values())
    if total_centroid_count > 0:
        legend_items_html.append(f'<div class="legend-centroid-summary" style="border-top:1px dashed #e2e8f0; margin-top:5px; padding-top:5px; font-size:10.5px; color:#92400e; font-weight:700;">&#9651; พิกัดกึ่งกลาง {total_centroid_count:,} จาก {len(map_data):,} จุด</div>')
    legend_content = "\n".join(legend_items_html)

    if 'ลิงก์' in map_data.columns:
        _lnk = map_data['ลิงก์'].fillna('').astype(str).str.strip()
        links = _lnk.where(~_lnk.isin(['', 'nan', 'None', '-']), '').tolist()
    else:
        links = [''] * len(map_data)

    _co_cat = pd.Categorical(map_data['บริษัท'].fillna('-').astype(str).str.strip())
    _ty_cat = pd.Categorical(map_data['ประเภททรัพย์'].fillna('-').astype(str).str.strip())
    _pv_cat = pd.Categorical(map_data['จังหวัด'].fillna('-').astype(str).str.strip())
    _st_col = map_data['ประเภทการขาย'].fillna('ไม่ระบุ').astype(str).str.strip() if 'ประเภทการขาย' in map_data.columns else pd.Series(['ไม่ระบุ'] * len(map_data), index=map_data.index)
    _st_cat = pd.Categorical(_st_col)
    _rg_col = map_data['ภาค'].fillna('ไม่ระบุ').astype(str).str.strip() if 'ภาค' in map_data.columns else pd.Series(['ไม่ระบุ'] * len(map_data), index=map_data.index)
    _rg_cat = pd.Categorical(_rg_col)
    _dt_col = map_data['อำเภอ'].fillna('ไม่ระบุ').astype(str).str.strip() if 'อำเภอ' in map_data.columns else pd.Series(['ไม่ระบุ'] * len(map_data), index=map_data.index)
    _dt_cat = pd.Categorical(_dt_col)
    _subdt_col = map_data['ตำบล'].fillna('ไม่ระบุ').astype(str).str.strip() if 'ตำบล' in map_data.columns else pd.Series(['ไม่ระบุ'] * len(map_data), index=map_data.index)
    _subdt_cat = pd.Categorical(_subdt_col)
    _prj_col = map_data['โครงการ'].fillna('-').astype(str).str.strip() if 'โครงการ' in map_data.columns else (
        map_data['ชื่อโครงการ'].fillna('-').astype(str).str.strip() if 'ชื่อโครงการ' in map_data.columns else pd.Series(['-'] * len(map_data), index=map_data.index)
    )
    _prj_col = _prj_col.replace({'': '-', 'nan': '-', 'None': '-', 'null': '-', 'undefined': '-'})
    _prj_cat = pd.Categorical(_prj_col)

    sam_projs_list, _ = get_sam_project_options(df)

    lookup_obj = {
        'co': _co_cat.categories.tolist(),
        'ty': _ty_cat.categories.tolist(),
        'pv': _pv_cat.categories.tolist(),
        'st': _st_cat.categories.tolist(),
        'rg': _rg_cat.categories.tolist(),
        'dt': _dt_cat.categories.tolist(),
        'subdt': _subdt_cat.categories.tolist(),
        'prj': _prj_cat.categories.tolist(),
        'sam_prj': sam_projs_list,
    }
    lookup_b64 = base64.b64encode(
        gzip.compress(
            json.dumps(lookup_obj, ensure_ascii=False).encode('utf-8'),
            compresslevel=1
        )
    ).decode('utf-8')

    deeds = map_data['เลขโฉนด'].fillna('').astype(str).values if 'เลขโฉนด' in map_data.columns else [''] * len(map_data)
    csv_df = pd.DataFrame({
        'lon': map_data['ลองจิจูด'].values.astype('float32'),
        'lat': map_data['ละติจูด'].values.astype('float32'),
        'r':   r_arr.values,
        'g':   g_arr.values,
        'b':   b_arr.values,
        '_title': titles,
        '_id':    ids,
        '_ci':    _co_cat.codes.astype('int16'),
        '_ti':    _ty_cat.codes.astype('int16'),
        '_pi':    _pv_cat.codes.astype('int16'),
        '_sti':   _st_cat.codes.astype('int16'),
        '_rgi':   _rg_cat.codes.astype('int16'),
        '_dti':   _dt_cat.codes.astype('int16'),
        '_subdti': _subdt_cat.codes.astype('int16'),
        '_prji':  _prj_cat.codes.astype('int32'),
        '_p':     _prices_num.fillna(0).astype('float32').values,
        '_up':    _unit_prices.astype('float32'),
        '_sqw':   np.nan_to_num(_sqw_calc, nan=0.0).round(1).astype('float32'),
        '_sqm':   np.nan_to_num(_sqm_calc, nan=0.0).round(1).astype('float32'),
        '_puw':   np.nan_to_num(_p_wah_calc, nan=0.0).round(0).astype('float32'),
        '_pum':   np.nan_to_num(_p_sqm_calc, nan=0.0).round(0).astype('float32'),
        '_price_str': prices_list,
        '_link':     links,
        '_centroid': centroid_flags,
        '_deed':     deeds,
    })

    csv_base64 = base64.b64encode(
        gzip.compress(
            csv_df.to_csv(index=False).encode('utf-8'),
            compresslevel=1
        )
    ).decode('utf-8')

    return csv_base64, lookup_b64, legend_content, map_data_full_len

def precompute_full_map_html(data_mtime):
    """Pre-assembles the map HTML with all heavy data injected into the template."""
    if "cached_map_html_base" in st.session_state:
        return

    csv_base64, lookup_b64, legend_content, map_data_full_len = get_precomputed_map_payload(data_mtime)
    if map_data_full_len == 0:
        return

    _tmpl_path = "static/map_template.html"
    _tmpl_mtime = os.path.getmtime(_tmpl_path) if os.path.exists(_tmpl_path) else None
    base_tmpl = get_base_map_html(_tmpl_mtime)
    if not base_tmpl:
        return

    atlas_uri, icon_mapping = get_map_icon_atlas_and_mapping(128)
    icon_mapping_json = json.dumps(icon_mapping, ensure_ascii=False)

    company_logos_dict = get_leaflet_logo_dict(72)
    company_logos_json = json.dumps(company_logos_dict, ensure_ascii=False)

    df = load_properties_data(data_mtime)
    all_provinces_list = sorted(list({
        str(p).strip().strip(" ,;.-'\"")
        for p in df['จังหวัด'].dropna().unique()
        if str(p).strip().strip(" ,;.-'\"") and str(p).strip().strip(" ,;.-'\"") not in ['-', 'ไม่มีข้อมูล', 'nan', 'None']
    })) if df is not None and not df.empty else []
    all_provinces_json = json.dumps(all_provinces_list, ensure_ascii=False)

    html = base_tmpl.replace("CSV_BASE64_PLACEHOLDER", csv_base64)
    html = html.replace("LOOKUP_BASE64_PLACEHOLDER", lookup_b64)
    html = html.replace("LEGEND_ITEMS_PLACEHOLDER", legend_content)
    html = html.replace("ATLAS_BASE64_PLACEHOLDER", atlas_uri)
    html = html.replace("ICON_MAPPING_PLACEHOLDER", icon_mapping_json)
    html = html.replace("COMPANY_LOGOS_PLACEHOLDER", company_logos_json)
    html = html.replace("ALL_PROVINCES_PLACEHOLDER", all_provinces_json)

    st.session_state["cached_map_html_base"] = html
    st.session_state["cached_map_data_len"] = map_data_full_len
