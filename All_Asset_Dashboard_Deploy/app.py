import os
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import pydeck as pdk
import re
import json
import math
import ast
import io
import datetime
import time
import gzip
from pathlib import Path
import base64
from PIL import Image

from dashboard_metrics import build_kpi_summary_text
from bubble_chart import generate_3d_glossy_bubble_chart_html
import sam_analytics
from sam_analytics import clean_project_name
import user_logger

def make_clean_dropdown_label(row, show_company=True):
    """Creates clean, highly informative dropdown labels with company, property type, name/project, code, location, and price."""
    co = str(row.get('บริษัท', '')).strip()
    title = str(row.get('ชื่อประกาศ', '')).strip()
    proj = str(row.get('ชื่อโครงการ', '')).strip()
    code = str(row.get('รหัสทรัพย์', '')).strip()
    ptype = str(row.get('ประเภททรัพย์', '')).strip()
    prov = str(row.get('จังหวัด', '')).strip()
    dist = str(row.get('อำเภอ', '')).strip()
    price = row.get('ราคา', 0)
    
    try:
        f_price = float(price)
        price_str = f"฿{f_price:,.0f}" if f_price > 0 else "ไม่ระบุราคา"
    except (ValueError, TypeError):
        price_str = "ไม่ระบุราคา"
        
    # Pick the best descriptive name
    name = title
    if (not name or name in ['SAM', 'BAM', 'ไม่มีชื่อ', 'ทรัพย์สิน NPA', '-', 'nan']) and proj and proj not in ['nan', 'None', '-']:
        name = proj
    elif proj and proj not in ['nan', 'None', '-', ''] and proj.lower() not in title.lower() and len(name) < 25:
        name = f"{name} ({proj})"
        
    if len(name) > 40:
        name = name[:38] + "..."
        
    loc_parts = []
    if dist and dist not in ['nan', 'None', '-']:
        loc_parts.append(dist)
    if prov and prov not in ['nan', 'None', '-']:
        loc_parts.append(prov)
    loc_joined = ', '.join(loc_parts)
    loc_str = f" [{loc_joined}]" if loc_parts else ""
    
    code_str = f" ({code})" if code and code not in ['nan', 'None', '-'] else ""
    ptype_str = f"{ptype}: " if ptype and ptype not in ['nan', 'None', '-'] else ""
    prefix = f"[{co}] " if show_company and co and co not in ['nan', 'None', '-'] else ""
    
    return f"{prefix}{ptype_str}{name}{code_str}{loc_str} - {price_str}"

REGION_PROVINCES = {
    'ภาคกลาง': [
        'กรุงเทพมหานคร', 'นนทบุรี', 'ปทุมธานี', 'สมุทรปราการ', 'สมุทรสาคร', 'สมุทรสงคราม',
        'นครปฐม', 'พระนครศรีอยุธยา', 'สระบุรี', 'ลพบุรี', 'สุพรรณบุรี', 'ชัยนาท', 'สิงห์บุรี', 'อ่างทอง'
    ],
    'ภาคเหนือ': [
        'เชียงใหม่', 'เชียงราย', 'ลำปาง', 'ลำพูน', 'แม่ฮ่องสอน', 'น่าน', 'พะเยา', 'แพร่',
        'อุตรดิตถ์', 'พิษณุโลก', 'สุโขทัย', 'เพชรบูรณ์', 'พิจิตร', 'กำแพงเพชร', 'นครสวรรค์', 'อุทัยธานี', 'ตาก'
    ],
    'ภาคตะวันออกเฉียงเหนือ': [
        'นครราชสีมา', 'ขอนแก่น', 'อุดรธานี', 'อุบลราชธานี', 'ร้อยเอ็ด', 'บุรีรัมย์', 'สุรินทร์',
        'ศรีสะเกษ', 'มหาสารคาม', 'ชัยภูมิ', 'กาฬสินธุ์', 'สกลนคร', 'นครพนม', 'มุกดาหาร',
        'ยโสธร', 'อำนาจเจริญ', 'หนองคาย', 'เลย', 'หนองบัวลำภู', 'บึงกาฬ'
    ],
    'ภาคตะวันออก': [
        'ชลบุรี', 'ระยอง', 'ฉะเชิงเทรา', 'จันทบุรี', 'ตราด', 'นครนายก', 'ปราจีนบุรี', 'สระแก้ว'
    ],
    'ภาคตะวันตก': [
        'กาญจนบุรี', 'ราชบุรี', 'เพชรบุรี', 'ประจวบคีรีขันธ์'
    ],
    'ภาคใต้': [
        'ภูเก็ต', 'สุราษฎร์ธานี', 'สงขลา', 'นครศรีธรรมราช', 'กระบี่', 'พังงา', 'ตรัง',
        'ชุมพร', 'ระนอง', 'พัทลุง', 'สตูล', 'ปัตตานี', 'ยะลา', 'นราธิวาส'
    ]
}

PROVINCE_TO_REGION = {p: r for r, plist in REGION_PROVINCES.items() for p in plist}

# Global Company Brand Colors & Gradients
COMPANY_COLORS = {
    "LED": "#0891b2",
    "SAM": "#10b981", 
    "BAM": "#3b82f6", 
    "Chayo555": "#f97316", 
    "Chayo": "#f97316", 
    "Chayo NPA": "#f97316", 
    "GHB": "#ca8a04", 
    "KBANK": "#059669", 
    "KTB": "#0284c7", 
    "SCB": "#7e22ce", 
    "GSB": "#eb1985",
    "DDproperty": "#a855f7",
    "Livinginsider": "#14b8a6",
    "NaYoo": "#8b5cf6", 
    "ZmyHome": "#ec4899",
    "Baania": "#f59e0b"
}
COMP_BRAND_COLORS = COMPANY_COLORS

COMP_GRADIENT_PALETTES = {
    "LED": ["#0e7490", "#0891b2", "#06b6d4", "#22d3ee", "#38bdf8", "#7dd3fc"],
    "SAM": ["#047857", "#059669", "#10b981", "#34d399", "#6ee7b7", "#a7f3d0"],
    "BAM": ["#1d4ed8", "#2563eb", "#3b82f6", "#60a5fa", "#93c5fd", "#bfdbfe"],
    "Chayo555": ["#c2410c", "#ea580c", "#f97316", "#fb923c", "#fdba74", "#fed7aa"],
    "Chayo": ["#c2410c", "#ea580c", "#f97316", "#fb923c", "#fdba74", "#fed7aa"],
    "Chayo NPA": ["#c2410c", "#ea580c", "#f97316", "#fb923c", "#fdba74", "#fed7aa"],
    "GHB": ["#a16207", "#ca8a04", "#eab308", "#facc15", "#fde047", "#fef08a"],
    "KBANK": ["#064e3b", "#047857", "#059669", "#10b981", "#34d399", "#6ee7b7"],
    "KTB": ["#075985", "#0369a1", "#0284c7", "#38bdf8", "#7dd3fc", "#bae6fd"],
    "SCB": ["#581c87", "#6b21a8", "#7e22ce", "#9333ea", "#a855f7", "#c084fc"],
    "GSB": ["#86198f", "#a21caf", "#c026d3", "#d946ef", "#f472b6", "#fbcfe8"],
    "DDproperty": ["#701a75", "#86198f", "#9333ea", "#a855f7", "#c084fc", "#e9d5ff"],
    "Livinginsider": ["#115e59", "#0d9488", "#14b8a6", "#2dd4bf", "#5eead4", "#99f6e4"],
    "NaYoo": ["#312e81", "#3730a3", "#4338ca", "#6366f1", "#818cf8", "#a5b4fc"],
    "ZmyHome": ["#881337", "#9f1239", "#be123c", "#e11d48", "#f43f5e", "#fda4af"],
    "Baania": ["#78350f", "#92400e", "#b45309", "#d97706", "#f59e0b", "#fde68a"]
}

def get_gradient_palette(comp_name, count=6):
    palette = COMP_GRADIENT_PALETTES.get(comp_name, ["#3b82f6"] * 6)
    if count == len(palette):
        return palette
    elif count < len(palette):
        indices = np.linspace(0, len(palette) - 1, count, dtype=int)
        return [palette[i] for i in indices]
    else:
        return palette + [palette[-1]] * (count - len(palette))

def get_region_by_province(prov):
    return PROVINCE_TO_REGION.get(str(prov).strip(), 'อื่นๆ / ไม่ระบุ')

def is_true_centroid(val, company=None):
    """Safely checks if a value represents a centroid coordinate, avoiding the Python bool(np.nan) == True gotcha."""
    if company is not None and str(company).strip().upper() == 'LED':
        return True
    if val is None or pd.isna(val):
        return False
    if isinstance(val, (bool, np.bool_)):
        return bool(val)
    if isinstance(val, (int, float, np.number)):
        return bool(val != 0)
    s = str(val).strip().lower()
    return s in ['true', '1', 'yes', 't']

PRICE_TIER_ORDER = [
    "< 1 ล้านบาท",
    "1 - 3 ล้านบาท",
    "3 - 5 ล้านบาท",
    "5 - 10 ล้านบาท",
    "10 - 20 ล้านบาท",
    "> 20 ล้านบาท"
]

def get_price_tier(price):
    """Classify a numeric property price into standardized Thai price tiers."""
    if pd.isna(price) or price is None or price <= 0:
        return "ไม่ระบุราคา"
    if price < 1_000_000:
        return "< 1 ล้านบาท"
    elif price < 3_000_000:
        return "1 - 3 ล้านบาท"
    elif price < 5_000_000:
        return "3 - 5 ล้านบาท"
    elif price < 10_000_000:
        return "5 - 10 ล้านบาท"
    elif price < 20_000_000:
        return "10 - 20 ล้านบาท"
    else:
        return "> 20 ล้านบาท"


@st.cache_data(show_spinner=False)
def get_dataset_month_year(_df):
    """Formats the dataset date into Thai Month & Year (e.g. สิงหาคม 2569) and date range from start to latest extraction date."""
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
                # Distinguish ISO YYYY-MM-DD from Slash DD/MM/YYYY to avoid swapping month and day
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
        p_path = Path("all_assets.parquet")
        if p_path.exists():
            dt = datetime.datetime.fromtimestamp(p_path.stat().st_mtime)
            thai_year = dt.year + 543 if dt.year < 2500 else dt.year
            month_name = thai_full_months[dt.month - 1]
            short_month = thai_short_months[dt.month - 1]
            return f"{month_name} {thai_year}", f"{dt.day} {short_month} {thai_year}"
    except Exception:
        pass
    return "สิงหาคม 2569", "11 - 20 ส.ค. 2569"

@st.cache_data
def convert_df_to_csv(_df):
    """Cached CSV generator to prevent blocking rerun loops."""
    if _df is None or _df.empty:
        return b""
    return _df.to_csv(index=False).encode('utf-8-sig')

@st.cache_data
def convert_df_to_excel(_df):
    """Cached Excel generator to prevent blocking rerun loops."""
    if _df is None or _df.empty:
        return b""
    excel_buffer = io.BytesIO()
    with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
        _df.to_excel(writer, index=False, sheet_name='Assets')
    return excel_buffer.getvalue()

def render_import_export_section(df_to_export, filename_prefix="npa_data", key_suffix=""):
    """Renders side-by-side Import (Excel/CSV) and Export (Excel/CSV) UI."""
    st.markdown("<br/>", unsafe_allow_html=True)
    st.markdown("##### <i class='fa-solid fa-arrow-right-arrow-left' style='color:#059669; margin-right:6px;'></i>นำเข้าและส่งออกข้อมูล (Import & Export Data)", unsafe_allow_html=True)
    col_imp, col_exp = st.columns(2)
    
    # Left: Import File
    with col_imp:
        st.markdown("###### <i class='fa-solid fa-file-import' style='color:#64748b; margin-right:6px;'></i>นำเข้าข้อมูลเพิ่มเติม (Import File)", unsafe_allow_html=True)
        uploaded_file = st.file_uploader(
            "เลือกไฟล์ Excel หรือ CSV เพื่อเพิ่มข้อมูล", 
            type=["xlsx", "xls", "csv"], 
            key=f"custom_file_uploader_{key_suffix}",
            help="รองรับไฟล์ที่มีคอลัมน์: บริษัท, ประเภททรัพย์, ราคา, ละติจูด, ลองจิจูด, จังหวัด ฯลฯ"
        )
        if uploaded_file is not None:
            try:
                if uploaded_file.name.endswith('.csv'):
                    u_df = None
                    for enc in ['utf-8-sig', 'utf-8', 'cp874', 'tis-620']:
                        try:
                            uploaded_file.seek(0)
                            u_df = pd.read_csv(uploaded_file, encoding=enc)
                            break
                        except Exception:
                            continue
                    if u_df is None:
                        uploaded_file.seek(0)
                        u_df = pd.read_csv(uploaded_file, encoding='utf-8', encoding_errors='replace')
                else:
                    u_df = pd.read_excel(uploaded_file)
                
                if not u_df.empty:
                    st.success(f"อ่านไฟล์สำเร็จ ({len(u_df):,} รายการ)")
                    if st.button("รวมเข้ากับฐานข้อมูลหลัก", icon=":material/merge:", key=f"btn_apply_import_{key_suffix}", use_container_width=True):
                        st.session_state["imported_custom_df"] = u_df
                        st.success("นำเข้าข้อมูลสำเร็จแล้ว!")
                        st.rerun()
            except Exception as ex:
                st.error(f"อ่านไฟล์ไม่สำเร็จ: {ex}")
                
        if "imported_custom_df" in st.session_state and st.session_state["imported_custom_df"] is not None:
            st.info(f"มีข้อมูลนำเข้าเพิ่มอยู่ {len(st.session_state['imported_custom_df']):,} รายการ")
            if st.button("ล้างข้อมูลที่นำเข้า", icon=":material/delete_outline:", key=f"btn_clear_import_{key_suffix}", use_container_width=True):
                del st.session_state["imported_custom_df"]
                st.rerun()

    # Right: Export File
    with col_exp:
        st.markdown("###### <i class='fa-solid fa-file-export' style='color:#64748b; margin-right:6px;'></i>ส่งออกข้อมูลในตาราง (Export Data)", unsafe_allow_html=True)
        if df_to_export is not None and not df_to_export.empty:
            n_rows = len(df_to_export)
            st.caption(f"ข้อมูลพร้อมส่งออกทั้งหมด **{n_rows:,}** รายการ")
            
            c_exp1, c_exp2 = st.columns(2)
            with c_exp1:
                csv_key = f"csv_data_{key_suffix}"
                csv_rows_key = f"csv_rows_{key_suffix}"
                if n_rows <= 10000:
                    st.download_button(
                        label="ส่งออก CSV (.csv)",
                        data=convert_df_to_csv(df_to_export),
                        file_name=f"{filename_prefix}.csv",
                        mime="text/csv",
                        icon=":material/download:",
                        use_container_width=True,
                        key=f"btn_export_csv_{key_suffix}",
                        help="ดาวน์โหลดทันที รองรับภาษาไทย UTF-8"
                    )
                else:
                    if st.session_state.get(csv_rows_key) == n_rows and csv_key in st.session_state:
                        st.download_button(
                            label=f"ดาวน์โหลด CSV ({n_rows:,} รายการ)",
                            data=st.session_state[csv_key],
                            file_name=f"{filename_prefix}.csv",
                            mime="text/csv",
                            icon=":material/download:",
                            use_container_width=True,
                            key=f"btn_export_csv_{key_suffix}"
                        )
                    else:
                        if st.button("สร้างไฟล์ CSV (.csv)", icon=":material/description:", key=f"btn_prep_csv_{key_suffix}", use_container_width=True, help="คลิกเพื่อสร้างไฟล์ CSV สำหรับดาวน์โหลด"):
                            with st.spinner(f"กำลังแปลงข้อมูล {n_rows:,} รายการเป็นไฟล์ CSV..."):
                                csv_bytes = convert_df_to_csv(df_to_export)
                                st.session_state[csv_key] = csv_bytes
                                st.session_state[csv_rows_key] = n_rows
                                st.rerun()
            with c_exp2:
                excel_key = f"excel_data_{key_suffix}"
                excel_rows_key = f"excel_rows_{key_suffix}"
                
                # Check if Excel was already prepared for this exact row count
                if st.session_state.get(excel_rows_key) == n_rows and excel_key in st.session_state:
                    st.download_button(
                        label="ดาวน์โหลด Excel (.xlsx)",
                        data=st.session_state[excel_key],
                        file_name=f"{filename_prefix}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        icon=":material/download:",
                        use_container_width=True,
                        key=f"btn_export_excel_{key_suffix}"
                    )
                else:
                    if st.button("สร้างไฟล์ Excel (.xlsx)", icon=":material/table_view:", key=f"btn_prep_excel_{key_suffix}", use_container_width=True, help="คลิกเพื่อเริ่มแปลงข้อมูลเป็นไฟล์ Excel (.xlsx)"):
                        with st.spinner(f"กำลังแปลงข้อมูล {n_rows:,} รายการเป็นไฟล์ Excel..."):
                            excel_bytes = convert_df_to_excel(df_to_export)
                            st.session_state[excel_key] = excel_bytes
                            st.session_state[excel_rows_key] = n_rows
                            st.rerun()
                    if n_rows > 10000:
                        st.caption("แนะนำ **CSV** สำหรับไฟล์ขนาดใหญ่ จะสร้างไฟล์และดาวน์โหลดได้เร็วที่สุด")
        else:
            st.info("ไม่มีข้อมูลสำหรับส่งออก")

# Haversine distance calculation (km)
# Haversine distance calculation (km)
def haversine_distance(lat1, lon1, lat2, lon2):
    R = 6371  # Earth radius in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def haversine_distance_vectorized(lat1, lon1, lats, lons):
    """Vectorized Haversine distance computation using NumPy."""
    R = 6371.0  # Earth radius in km
    
    # Convert degrees to radians
    lat1_rad = np.radians(lat1)
    lon1_rad = np.radians(lon1)
    lats_rad = np.radians(lats)
    lons_rad = np.radians(lons)
    
    dlat = lats_rad - lat1_rad
    dlon = lons_rad - lon1_rad
    
    a = np.sin(dlat / 2.0) ** 2 + np.cos(lat1_rad) * np.cos(lats_rad) * np.sin(dlon / 2.0) ** 2
    c = 2.0 * np.arcsin(np.sqrt(np.clip(a, 0.0, 1.0)))
    return R * c

def sanitize_session_state(key, valid_options, default_val=None):
    """Ensure st.session_state[key] only contains items present in valid_options to prevent desync errors."""
    if key in st.session_state and st.session_state[key] is not None:
        val = st.session_state[key]
        if isinstance(val, (list, set, tuple)):
            sanitized = [v for v in val if v in valid_options]
            if len(sanitized) != len(val):
                st.session_state[key] = sanitized
        else:
            if val not in valid_options:
                if default_val is not None and default_val in valid_options:
                    st.session_state[key] = default_val
                elif valid_options:
                    st.session_state[key] = valid_options[0]
                else:
                    st.session_state[key] = None

@st.cache_data
def get_thailand_clean_grid(ref_lat, ref_lng):
    """Cached multi-scale Thailand grid generator for instant clean map rendering."""
    # 1. Ultra-fine grid around reference pin (±0.03 deg ~3.3km, 35x35)
    u_lat, u_lng = np.meshgrid(
        np.linspace(ref_lat - 0.03, ref_lat + 0.03, 35),
        np.linspace(ref_lng - 0.03, ref_lng + 0.03, 35)
    )
    # 2. Fine grid around reference pin (±0.15 deg ~16.5km, 25x25)
    f_lat, f_lng = np.meshgrid(
        np.linspace(ref_lat - 0.15, ref_lat + 0.15, 25),
        np.linspace(ref_lng - 0.15, ref_lng + 0.15, 25)
    )
    # 3. Medium grid around reference pin (±0.8 deg ~88km, 20x20)
    m_lat, m_lng = np.meshgrid(
        np.linspace(ref_lat - 0.8, ref_lat + 0.8, 20),
        np.linspace(ref_lng - 0.8, ref_lng + 0.8, 20)
    )
    # 4. Country-wide Thailand grid (35x35)
    c_lat, c_lng = np.meshgrid(
        np.linspace(5.5, 20.5, 35),
        np.linspace(97.5, 105.5, 35)
    )

    all_lats = np.concatenate([u_lat.flatten(), f_lat.flatten(), m_lat.flatten(), c_lat.flatten()])
    all_lngs = np.concatenate([u_lng.flatten(), f_lng.flatten(), m_lng.flatten(), c_lng.flatten()])

    r1 = (all_lats >= 5.6) & (all_lats < 7.2) & (all_lngs >= 99.8) & (all_lngs <= 102.2)
    r2 = (all_lats >= 7.2) & (all_lats < 9.0) & (all_lngs >= 98.2) & (all_lngs <= 100.5)
    r3 = (all_lats >= 9.0) & (all_lats < 10.2) & (all_lngs >= 98.5) & (all_lngs <= 100.2)
    r4 = (all_lats >= 10.2) & (all_lats < 11.2) & (all_lngs >= 98.5) & (all_lngs <= 99.6)
    r5 = (all_lats >= 11.2) & (all_lats < 13.2) & (all_lngs >= 99.0) & (all_lngs <= 100.1)
    r6 = (all_lats >= 13.2) & (all_lats < 14.5) & (all_lngs >= 99.4) & (all_lngs <= 101.0)
    r7 = (all_lats >= 13.8) & (all_lats < 15.6) & (all_lngs >= 98.7) & (all_lngs <= 101.4)
    r8 = (all_lats >= 11.7) & (all_lats < 13.6) & (all_lngs >= 100.8) & (all_lngs <= 102.9)
    r9 = (all_lats >= 13.4) & (all_lats < 14.3) & (all_lngs >= 101.0) & (all_lngs <= 103.0)
    r10 = (all_lats >= 14.0) & (all_lats < 15.8) & (all_lngs >= 101.2) & (all_lngs <= 105.6)
    r11 = (all_lats >= 15.8) & (all_lats < 18.5) & (all_lngs >= 101.5) & (all_lngs <= 105.0)
    r12 = (all_lats >= 16.8) & (all_lats < 18.3) & (all_lngs >= 101.0) & (all_lngs <= 102.6)
    r13 = (all_lats >= 14.8) & (all_lats < 17.5) & (all_lngs >= 97.8) & (all_lngs <= 101.4)
    r14 = (all_lats >= 17.5) & (all_lats <= 20.46) & (all_lngs >= 97.35) & (all_lngs <= 101.4)

    mask = r1 | r2 | r3 | r4 | r5 | r6 | r7 | r8 | r9 | r10 | r11 | r12 | r13 | r14
    return all_lats[mask], all_lngs[mask]

def find_nearby_properties(input_lat, input_lon, df_all, radius_km, match_type=None, company=None):
    """Find properties within radius_km of the given coordinates (ultra-fast Bounding Box + Haversine)."""
    if df_all is None or df_all.empty:
        return pd.DataFrame()
    empty_res = df_all.head(0).copy()
    if input_lat is None or input_lon is None or pd.isna(input_lat) or pd.isna(input_lon):
        return empty_res
        
    # Fast Bounding Box pre-filter (1 deg lat ~= 111km, 1 deg lon ~= 100km)
    lat_margin = (radius_km / 105.0) + 0.015
    lon_margin = (radius_km / 90.0) + 0.015
    
    mask = (
        df_all['ละติจูด'].notna() & 
        df_all['ลองจิจูด'].notna() & 
        df_all['ละติจูด'].between(input_lat - lat_margin, input_lat + lat_margin) & 
        df_all['ลองจิจูด'].between(input_lon - lon_margin, input_lon + lon_margin)
    )
    
    if company:
        mask &= (df_all['บริษัท'] == company)
        
    if match_type:
        if isinstance(match_type, (list, tuple, set)):
            clean_types = [str(t).strip() for t in match_type if str(t).strip() not in ['', 'nan', 'None']]
            if clean_types:
                mask &= (df_all['ประเภททรัพย์'].isin(clean_types))
        elif str(match_type).strip() not in ['', 'nan', 'None']:
            mask &= (df_all['ประเภททรัพย์'] == str(match_type).strip())
        
    df_sub = df_all[mask]
    if df_sub.empty:
        return empty_res
        
    lats = df_sub['ละติจูด'].to_numpy(dtype=float)
    lons = df_sub['ลองจิจูด'].to_numpy(dtype=float)
    
    distances = haversine_distance_vectorized(input_lat, input_lon, lats, lons)
    nearby_mask = distances <= radius_km
    
    if not np.any(nearby_mask):
        return empty_res
        
    df_result = df_sub[nearby_mask].copy()
    df_result['ระยะทาง (กม.)'] = np.round(distances[nearby_mask], 2)
    return df_result

# Helper function to parse 'พื้นที่ (ไร่-งาน-วา)' to square wah
def parse_area_to_sqwah(area_str):
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
    rai = int(sqwah // 400)
    rem = sqwah % 400
    ngan = int(rem // 100)
    wah = rem % 100
    wah_str = str(int(wah)) if wah == int(wah) else f"{wah:.1f}"
    return f"{rai}-{ngan}-{wah_str}"


# Configure Streamlit page layout
_app_icon_file = os.path.join("logo", "app_icon.ico") if os.path.exists(os.path.join("logo", "app_icon.ico")) else os.path.join("assets", "app_icon.ico")
_app_page_icon = Image.open(_app_icon_file) if os.path.exists(_app_icon_file) else ":material/analytics:"

st.set_page_config(
    page_title="NOVA NPA Dashboard",
    page_icon=_app_page_icon,
    layout="wide",
    initial_sidebar_state="expanded"
)

# (Login system removed - direct dashboard access)

# Helper function to safely format numeric fields (e.g., bedrooms, area) to nice string
def format_num_val(val):
    if pd.isna(val) or str(val).strip() == "" or str(val).lower() == "nan" or val is None or str(val).lower() == "$undefined":
        return ""
    try:
        f_val = float(val)
        if f_val.is_integer():
            return str(int(f_val))
        return str(f_val)
    except ValueError:
        return str(val)

# Helper functions to clean title and link for Baania
def get_clean_title(val):
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
    if not val or pd.isna(val):
        return ""
    val_str = str(val).strip()
    if val_str.startswith("{") and val_str.endswith("}"):
        try:
            d = ast.literal_eval(val_str)
            if isinstance(d, dict):
                src_url = d.get('source_url', '')
                if src_url:
                    return f"https://www.baania.com/th/{src_url.lstrip('/')}"
        except Exception:
            pass
    return val_str


# -------------------------------------------------------------
# TAB 3 MAP LOGO ICON ATLAS & MAPPING (Deck.gl IconLayer)
# -------------------------------------------------------------
_CACHED_ATLAS_URI = None
_CACHED_ICON_MAPPING = None

def get_map_icon_atlas_and_mapping(icon_size=128):
    """Builds and caches a single high-resolution Retina sprite sheet atlas containing all company logo badges and property type pins."""
    global _CACHED_ATLAS_URI, _CACHED_ICON_MAPPING
    if _CACHED_ATLAS_URI is not None and _CACHED_ICON_MAPPING is not None:
        return _CACHED_ATLAS_URI, _CACHED_ICON_MAPPING
        
    companies = [
        "LED", "SAM", "BAM", "Chayo555", "GHB", "KBANK", "KTB", "SCB", "GSB",
        "DDproperty", "Livinginsider", "NaYoo", "ZmyHome", "Baania", "จุดอ้างอิง"
    ]
    
    company_colors_map = {
        "LED": (8, 145, 178, 255), "SAM": (16, 185, 129, 255), "BAM": (59, 130, 246, 255),
        "Chayo555": (249, 115, 22, 255), "Chayo": (249, 115, 22, 255), "GHB": (202, 138, 4, 255),
        "KBANK": (5, 150, 105, 255), "KTB": (2, 132, 199, 255), "SCB": (126, 34, 206, 255),
        "GSB": (235, 25, 133, 255), "DDproperty": (168, 85, 247, 255), "Livinginsider": (20, 184, 166, 255),
        "NaYoo": (139, 92, 246, 255), "ZmyHome": (236, 72, 153, 255), "Baania": (245, 158, 11, 255)
    }

    prop_types = [
        ("บ้านเดี่ยว", (59, 130, 246, 255), "บ้าน"),
        ("ห้องชุดพักอาศัย", (139, 92, 246, 255), "คอนโด"),
        ("คอนโด", (139, 92, 246, 255), "คอนโด"),
        ("คอนโดมิเนียม", (139, 92, 246, 255), "คอนโด"),
        ("ทาวน์เฮ้าส์", (16, 185, 129, 255), "ทาวน์"),
        ("ทาวน์โฮม", (16, 185, 129, 255), "ทาวน์"),
        ("ที่ดินเปล่า", (139, 69, 19, 255), "ที่ดิน"),
        ("ที่ดิน", (139, 69, 19, 255), "ที่ดิน"),
        ("ที่ดินพร้อมสิ่งปลูกสร้าง", (160, 82, 45, 255), "ที่ดิน+"),
        ("อาคารพาณิชย์", (245, 158, 11, 255), "พาณิชย์"),
        ("โรงงาน/โกดัง", (239, 68, 68, 255), "โรงงาน"),
        ("อพาร์ทเมนท์", (168, 85, 247, 255), "อพาร์ท"),
        ("บ้านแฝด", (14, 165, 233, 255), "แฝด"),
        ("อาคารสำนักงาน", (100, 116, 139, 255), "สำนักงาน"),
        ("โรงแรม/รีสอร์ท", (234, 179, 8, 255), "โรงแรม"),
        ("วิลล่า", (217, 70, 239, 255), "วิลล่า"),
        ("อื่นๆ", (100, 116, 139, 255), "อื่นๆ")
    ]
    
    total_slots = len(companies) + len(prop_types)
    atlas_width = total_slots * icon_size
    atlas_height = icon_size
    
    try:
        from PIL import Image, ImageDraw, ImageFont
        import io, base64
        
        atlas = Image.new("RGBA", (atlas_width, atlas_height), (0, 0, 0, 0))
        icon_mapping = {}
        margin = 4
        border_w = max(5, int(icon_size * 0.065))
        
        # 1. Render Company Badges
        for i, name in enumerate(companies):
            x_offset = i * icon_size
            cell = Image.new("RGBA", (icon_size, icon_size), (0, 0, 0, 0))
            draw = ImageDraw.Draw(cell)
            
            if name == "จุดอ้างอิง":
                draw.ellipse([margin, margin, icon_size - margin, icon_size - margin], fill=(239, 68, 68, 255), outline=(255, 255, 255, 255), width=border_w)
                c_mid = icon_size // 2
                draw.ellipse([c_mid - 24, c_mid - 24, c_mid + 24, c_mid + 24], fill=(255, 255, 255, 255))
                draw.ellipse([c_mid - 12, c_mid - 12, c_mid + 12, c_mid + 12], fill=(239, 68, 68, 255))
            else:
                b_col = company_colors_map.get(name, (59, 130, 246, 255))
                draw.ellipse([margin, margin, icon_size - margin, icon_size - margin], fill=(255, 255, 255, 255), outline=b_col, width=border_w)
                
                logo_path = None
                for base in [name, name.lower(), name.upper(), name.capitalize(), name.title()]:
                    for ext in ['.png', '.jpg', '.jpeg', '.webp']:
                        p = os.path.join("logo", "logos", f"{base}{ext}")
                        if not os.path.exists(p):
                            p = os.path.join("assets", "logos", f"{base}{ext}")
                        if os.path.exists(p):
                            logo_path = p
                            break
                    if logo_path:
                        break
                
                if logo_path:
                    try:
                        logo = Image.open(logo_path).convert("RGBA")
                        bbox = logo.getbbox()
                        if bbox:
                            logo = logo.crop(bbox)
                        inner_max = int((icon_size - margin * 2) * 0.72)
                        logo.thumbnail((inner_max, inner_max), Image.Resampling.LANCZOS)
                        off_x = (icon_size - logo.width) // 2
                        off_y = (icon_size - logo.height) // 2
                        cell.paste(logo, (off_x, off_y), logo)
                    except Exception:
                        draw.text((icon_size // 2, icon_size // 2), name[:4].upper(), fill=(15, 23, 42, 255), anchor="mm")
                else:
                    draw.text((icon_size // 2, icon_size // 2), name[:4].upper(), fill=(15, 23, 42, 255), anchor="mm")
                    
            atlas.paste(cell, (x_offset, 0), cell)
            
            icon_mapping[name] = {
                "x": x_offset, "y": 0, "width": icon_size, "height": icon_size,
                "mask": False, "anchorX": icon_size // 2, "anchorY": icon_size // 2
            }
            icon_mapping[name.lower()] = icon_mapping[name]
            icon_mapping[name.upper()] = icon_mapping[name]
            
        # 2. Render Property Type Badges
        start_idx = len(companies)
        for j, (p_type, p_col, p_short) in enumerate(prop_types):
            x_offset = (start_idx + j) * icon_size
            cell = Image.new("RGBA", (icon_size, icon_size), (0, 0, 0, 0))
            draw = ImageDraw.Draw(cell)
            
            # Colored background circle with crisp white outline
            draw.ellipse([margin, margin, icon_size - margin, icon_size - margin], fill=p_col, outline=(255, 255, 255, 255), width=border_w)
            
            # Clean central geometric shapes based on property type
            c = icon_size // 2
            if "บ้าน" in p_type or p_type == "วิลล่า":
                # House roof polygon + base
                draw.polygon([(c, c - 26), (c - 28, c - 2), (c + 28, c - 2)], fill=(255, 255, 255, 255))
                draw.rectangle([c - 20, c - 2, c + 20, c + 24], fill=(255, 255, 255, 255))
                draw.rectangle([c - 7, c + 6, c + 7, c + 24], fill=p_col)
            elif "คอนโด" in p_type or "ห้องชุด" in p_type:
                # Tall building with grid windows
                draw.rectangle([c - 22, c - 28, c + 22, c + 28], fill=(255, 255, 255, 255))
                for wy in [-18, -6, 6, 18]:
                    for wx in [-14, 2]:
                        draw.rectangle([c + wx, c + wy, c + wx + 9, c + wy + 8], fill=p_col)
            elif "ทาวน์" in p_type:
                # Two connected townhouses
                draw.polygon([(c - 16, c - 24), (c - 32, c - 6), (c, c - 6)], fill=(255, 255, 255, 255))
                draw.rectangle([c - 28, c - 6, c - 4, c + 24], fill=(255, 255, 255, 255))
                draw.polygon([(c + 16, c - 24), (c, c - 6), (c + 32, c - 6)], fill=(255, 255, 255, 255))
                draw.rectangle([c + 4, c - 6, c + 28, c + 24], fill=(255, 255, 255, 255))
            elif "ที่ดิน" in p_type:
                # Tree crown + ground
                draw.polygon([(c, c - 26), (c - 24, c + 4), (c + 24, c + 4)], fill=(255, 255, 255, 255))
                draw.polygon([(c, c - 14), (c - 20, c + 14), (c + 20, c + 14)], fill=(255, 255, 255, 255))
                draw.rectangle([c - 5, c + 14, c + 5, c + 26], fill=(255, 255, 255, 255))
            elif "พาณิชย์" in p_type:
                # Storefront building
                draw.rectangle([c - 25, c - 18, c + 25, c + 25], fill=(255, 255, 255, 255))
                draw.polygon([(c, c - 28), (c - 28, c - 18), (c + 28, c - 18)], fill=(255, 255, 255, 255))
                draw.rectangle([c - 16, c - 2, c - 3, c + 12], fill=p_col)
                draw.rectangle([c + 3, c - 2, c + 16, c + 12], fill=p_col)
                draw.rectangle([c - 8, c + 14, c + 8, c + 25], fill=p_col)
            elif "โรงงาน" in p_type:
                # Saw-tooth factory roof
                draw.polygon([(c - 26, c - 6), (c - 10, c - 20), (c - 10, c - 6), (c + 8, c - 20), (c + 8, c - 6), (c + 24, c - 6), (c + 24, c + 24), (c - 26, c + 24)], fill=(255, 255, 255, 255))
                draw.rectangle([c + 14, c - 26, c + 20, c - 6], fill=(255, 255, 255, 255))
            else:
                # Modern clean diamond/circle glyph
                draw.ellipse([c - 16, c - 16, c + 16, c + 16], fill=(255, 255, 255, 255))
                
            atlas.paste(cell, (x_offset, 0), cell)
            icon_mapping[p_type] = {
                "x": x_offset, "y": 0, "width": icon_size, "height": icon_size,
                "mask": False, "anchorX": icon_size // 2, "anchorY": icon_size // 2
            }
            
        buf = io.BytesIO()
        atlas.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
        data_uri = f"data:image/png;base64,{b64}"
        
        _CACHED_ATLAS_URI = data_uri
        _CACHED_ICON_MAPPING = icon_mapping
        return data_uri, icon_mapping
    except Exception:
        fallback = "https://raw.githubusercontent.com/visgl/deck.gl-data/master/website/icon-atlas.png"
        return fallback, {}


def create_map_circle_coords(lat, lon, radius_km, num_points=64):
    """Generates lat/lon coordinates for a smooth circular polygon on Plotly map."""
    angles = np.linspace(0, 2 * np.pi, num_points)
    d_lat = (radius_km / 111.32) * np.sin(angles)
    d_lon = (radius_km / (111.32 * np.cos(np.radians(lat)))) * np.cos(angles)
    return lat + d_lat, lon + d_lon


# -------------------------------------------------------------
# TAB 3 INTERACTIVE LEAFLET MAP WITH COMPANY LOGO PINS & RICH DETAILS
# -------------------------------------------------------------
_LEAFLET_LOGO_CACHE = {}

def get_leaflet_logo_dict(size=72):
    """Generates optimized base64 dictionary of all company logos for Leaflet pins with healthy margin."""
    global _LEAFLET_LOGO_CACHE
    if _LEAFLET_LOGO_CACHE:
        return _LEAFLET_LOGO_CACHE
        
    base_dir = Path(__file__).resolve().parent
    logo_dir = base_dir / "logo" / "logos"
    if not logo_dir.exists():
        logo_dir = Path("logo/logos")
    if not logo_dir.exists():
        logo_dir = base_dir / "assets" / "logos"
    if not logo_dir.exists():
        logo_dir = Path("assets/logos")
        
    logo_dict = {}
    if not logo_dir.exists():
        _LEAFLET_LOGO_CACHE = logo_dict
        return logo_dict
        
    from PIL import Image
    import io, base64
    
    for fname in os.listdir(logo_dir):
        if fname.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
            path = logo_dir / fname
            base_name = os.path.splitext(fname)[0].strip()
            try:
                im = Image.open(path).convert("RGBA")
                bbox = im.getbbox()
                if bbox:
                    im = im.crop(bbox)
                max_side = max(im.width, im.height)
                square = Image.new("RGBA", (max_side, max_side), (0, 0, 0, 0))
                ox = (max_side - im.width) // 2
                oy = (max_side - im.height) // 2
                square.paste(im, (ox, oy), im)
                square = square.resize((size, size), Image.Resampling.LANCZOS)
                buf = io.BytesIO()
                square.save(buf, format="PNG", optimize=True)
                b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
                data_uri = f"data:image/png;base64,{b64}"
                
                logo_dict[base_name] = data_uri
                logo_dict[base_name.lower()] = data_uri
                logo_dict[base_name.upper()] = data_uri
                clean_name = base_name.replace("logo", "").replace(" ", "").strip()
                if clean_name:
                    logo_dict[clean_name] = data_uri
                    logo_dict[clean_name.lower()] = data_uri
                    logo_dict[clean_name.upper()] = data_uri
            except Exception:
                pass
                
    _LEAFLET_LOGO_CACHE = logo_dict
    return logo_dict

def render_tab3_manual_leaflet_picker_html(lat, lng, is_dark_mode=False):
    """Renders an interactive Leaflet map picker for manual coordinate selection with native top-right layer switcher."""
    lat_val = float(lat) if lat and lat != 0 else 13.7651
    lng_val = float(lng) if lng and lng != 0 else 100.5383
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
        <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=Noto+Sans+Thai:wght@300;400;500;600;700;800&display=swap');
            html, body {{
                width: 100%;
                height: 100%;
                margin: 0;
                padding: 0;
                overflow: hidden;
            }}
            #picker-map {{
                width: 100%;
                height: 100vh;
                min-height: 480px;
                margin: 0;
                padding: 0;
                font-family: 'Noto Sans Thai', 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
                background: {'#0f172a' if is_dark_mode else '#f8fafc'};
                border-radius: 14px;
            }}
            .custom-picker-pin {{
                display: flex;
                justify-content: center;
                align-items: center;
                width: 40px;
                height: 40px;
                background: #ef4444;
                border-radius: 50%;
                border: 3.5px solid #ffffff;
                box-shadow: 0 4px 16px rgba(239, 68, 68, 0.45);
                cursor: grab;
                animation: pulsePin 2.2s infinite ease-in-out;
            }}
            .custom-picker-pin:active {{
                cursor: grabbing;
            }}
            @keyframes pulsePin {{
                0% {{ box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.7); transform: scale(1); }}
                50% {{ box-shadow: 0 0 0 14px rgba(239, 68, 68, 0); transform: scale(1.05); }}
                100% {{ box-shadow: 0 0 0 0 rgba(239, 68, 68, 0); transform: scale(1); }}
            }}
            .custom-picker-pin-inner {{
                width: 12px;
                height: 12px;
                background: #ffffff;
                border-radius: 50%;
            }}
            .coord-floating-bar {{
                position: absolute;
                bottom: 16px;
                left: 16px;
                z-index: 1000;
                background: {'rgba(15, 23, 42, 0.88)' if is_dark_mode else 'rgba(255, 255, 255, 0.94)'};
                backdrop-filter: blur(10px);
                border: 1px solid {'rgba(255, 255, 255, 0.12)' if is_dark_mode else 'rgba(0, 0, 0, 0.08)'};
                border-radius: 12px;
                padding: 9px 16px;
                font-size: 13px;
                box-shadow: 0 6px 20px rgba(0,0,0,0.15);
                color: {'#f8fafc' if is_dark_mode else '#0f172a'};
                display: flex;
                align-items: center;
                gap: 12px;
                pointer-events: auto;
            }}
            .leaflet-control-layers {{
                border-radius: 12px !important;
                box-shadow: 0 6px 20px rgba(0,0,0,0.15) !important;
                border: 1px solid #e2e8f0 !important;
                font-family: 'Noto Sans Thai', 'Inter', sans-serif !important;
                font-size: 12.5px !important;
                padding: 6px !important;
            }}
            .leaflet-control-layers-base label {{
                color: #1e293b !important;
                margin-bottom: 4px !important;
                cursor: pointer !important;
                display: flex !important;
                align-items: center !important;
                gap: 6px !important;
            }}
            .copy-btn {{
                background: #059669;
                color: #ffffff;
                border: none;
                padding: 4px 10px;
                border-radius: 6px;
                font-size: 11.5px;
                font-weight: 700;
                cursor: pointer;
                transition: background 0.15s ease;
            }}
            .copy-btn:hover {{
                background: #047857;
            }}
        </style>
    </head>
    <body>
        <div id="picker-map"></div>
        <div class="coord-floating-bar" id="coordBar">
            <span><b>พิกัดที่เลือก:</b> <span id="latlngDisplay" style="font-weight:800; color:#ef4444; font-family:'Inter', monospace;">{lat_val:.6f}, {lng_val:.6f}</span></span>
            <span style="color:{'#94a3b8' if is_dark_mode else '#64748b'}; font-size:11.5px;">(คลิกหรือลากหมุดบนแผนที่เพื่อเปลี่ยนจุด)</span>
            <button type="button" class="copy-btn" onclick="copyCoord()">คัดลอก</button>
        </div>
        <script>
            var curLat = {lat_val};
            var curLng = {lng_val};

            var map = L.map('picker-map', {{
                zoomControl: true,
                attributionControl: false
            }}).setView([curLat, curLng], 12);

            // Base Tile Layers (Identical to main Leaflet map)
            var streetLayer = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{{z}}/{{y}}/{{x}}', {{ maxZoom: 19 }});
            var osmLayer = L.tileLayer('https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{ maxZoom: 19 }});
            var satLayer = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}', {{ maxZoom: 19 }});
            var topoLayer = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{{z}}/{{y}}/{{x}}', {{ maxZoom: 19 }});
            var darkLayer = L.tileLayer('https://{{s}}.basemaps.cartocdn.com/dark_all/{{z}}/{{x}}/{{y}}{{r}}.png', {{ maxZoom: 19 }});

            streetLayer.addTo(map);

            // Add Leaflet Layer Switcher Control inside top-right of map
            var baseMaps = {{
                "แผนที่ถนนมาตรฐาน (Esri Street)": streetLayer,
                "OpenStreetMap": osmLayer,
                "ภาพถ่ายดาวเทียม (Satellite)": satLayer,
                "ภูมิประเทศ (Topographic)": topoLayer,
                "โหมดมืด (Dark Canvas)": darkLayer
            }};
            L.control.layers(baseMaps, null, {{ position: 'topright' }}).addTo(map);

            var pickerIcon = L.divIcon({{
                className: 'custom-picker-icon',
                html: '<div class="custom-picker-pin"><div class="custom-picker-pin-inner"></div></div>',
                iconSize: [40, 40],
                iconAnchor: [20, 20],
                popupAnchor: [0, -20]
            }});

            var marker = L.marker([curLat, curLng], {{ icon: pickerIcon, draggable: true }}).addTo(map);

            function updateCoord(lat, lng, openPop) {{
                curLat = lat;
                curLng = lng;
                document.getElementById('latlngDisplay').innerText = lat.toFixed(6) + ', ' + lng.toFixed(6);
                marker.setLatLng([lat, lng]);
                
                var popupContent = '<div style="font-size:13px; font-weight:800; color:#ef4444; margin-bottom:3px;">จุดอ้างอิงของคุณ</div>' +
                    '<div style="font-size:12px; color:#334155;">ละติจูด: <b>' + lat.toFixed(6) + '</b><br/>ลองจิจูด: <b>' + lng.toFixed(6) + '</b></div>' +
                    '<div style="margin-top:6px; font-size:11px; color:#64748b;">ระบบตั้งค่าพิกัดนี้เป็นจุดอ้างอิงแล้ว</div>';
                marker.bindPopup(popupContent);
                if (openPop) marker.openPopup();

                // Synchronize parent React number inputs using native value setter (React-compatible)
                try {{
                    var parentDoc = window.parent.document;
                    var nativeSetter = Object.getOwnPropertyDescriptor(window.parent.HTMLInputElement.prototype, 'value').set;
                    var containers = parentDoc.querySelectorAll('[data-testid="stNumberInput"]');
                    containers.forEach(function(container) {{
                        var labelEl = container.querySelector('label, p');
                        var inputEl = container.querySelector('input');
                        if (!labelEl || !inputEl) return;
                        var t = (labelEl.textContent || '').toLowerCase();
                        if (t.indexOf('latitude') !== -1 || t.indexOf('\u0e25\u0e30\u0e15\u0e34\u0e08\u0e39\u0e14') !== -1) {{
                            nativeSetter.call(inputEl, lat.toFixed(6));
                            inputEl.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        }} else if (t.indexOf('longitude') !== -1 || t.indexOf('\u0e25\u0e2d\u0e07\u0e08\u0e34\u0e08\u0e39\u0e14') !== -1) {{
                            nativeSetter.call(inputEl, lng.toFixed(6));
                            inputEl.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        }}
                    }});
                }} catch(e) {{ /* cross-origin or no parent */ }}
            }}

            function copyCoord() {{
                var txt = curLat.toFixed(6) + ', ' + curLng.toFixed(6);
                navigator.clipboard.writeText(txt).then(function() {{
                    var btn = document.querySelector('.copy-btn');
                    btn.innerText = 'คัดลอกแล้ว!';
                    setTimeout(function() {{ btn.innerText = 'คัดลอก'; }}, 1800);
                }});
            }}

            marker.on('dragend', function(e) {{
                var pos = e.target.getLatLng();
                updateCoord(pos.lat, pos.lng, true);
                try {{
                    var url = new URL(window.parent.location.href);
                    url.searchParams.set('_clat', pos.lat.toFixed(6));
                    url.searchParams.set('_clng', pos.lng.toFixed(6));
                    window.parent.history.replaceState({{}}, '', url.toString());
                }} catch(e2) {{}}
            }});

            map.on('click', function(e) {{
                updateCoord(e.latlng.lat, e.latlng.lng, true);
                try {{
                    var url = new URL(window.parent.location.href);
                    url.searchParams.set('_clat', e.latlng.lat.toFixed(6));
                    url.searchParams.set('_clng', e.latlng.lng.toFixed(6));
                    window.parent.history.replaceState({{}}, '', url.toString());
                }} catch(e2) {{}}
            }});

            setTimeout(function() {{ map.invalidateSize(); }}, 250);
            window.addEventListener('resize', function() {{ map.invalidateSize(); }});
        </script>
    </body>
    </html>
    """
    return html

def render_tab3_radius_leaflet_map_html(inp_lat, inp_lng, search_radius_km, nearby_props, is_dark_mode=False, color_mode="จำแนกตามบริษัท (By Company)", tile_style="มาตรฐาน (Street Map)", legend_stats_dict=None):
    """Renders complete Leaflet map HTML with multi-unit interactive carousel popups, genuine company logo markers, layer switcher, and dynamic legend."""
    import json
    
    logo_dict = get_leaflet_logo_dict()
    props_json = json.dumps(nearby_props, ensure_ascii=False).replace("</script>", "<\\/script>")
    logos_json = json.dumps(logo_dict, ensure_ascii=False).replace("</script>", "<\\/script>")
    legend_stats_json = json.dumps(legend_stats_dict or {}, ensure_ascii=False).replace("</script>", "<\\/script>")
    
    # Selected base tile URL based on tile_style parameter
    if "ดาวเทียม" in tile_style or "satellite" in tile_style.lower():
        default_base = "satellite"
    elif "มืด" in tile_style or "dark" in tile_style.lower():
        default_base = "dark"
    elif "สว่าง" in tile_style or "light" in tile_style.lower():
        default_base = "light"
    else:
        default_base = "street"
        
    # Determine active color mode code
    if "ประเภททรัพย์" in color_mode:
        active_color_mode_code = "property_type"
    elif "ราคา" in color_mode:
        active_color_mode_code = "price_level"
    else:
        active_color_mode_code = "company"
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" />
        <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=Noto+Sans+Thai:wght@300;400;500;600;700;800&display=swap');
            html, body {{
                width: 100%;
                height: 100%;
                margin: 0;
                padding: 0;
                overflow: hidden;
            }}
            #map {{
                width: 100%;
                height: 100vh;
                min-height: 1100px;
                margin: 0;
                padding: 0;
                font-family: 'Noto Sans Thai', 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
                background: {'#0f172a' if is_dark_mode else '#f8fafc'};
                border-radius: 14px;
            }}
            .logo-marker-pin {{
                display: flex;
                justify-content: center;
                align-items: center;
                width: 34px;
                height: 34px;
                background: #ffffff;
                border-radius: 50%;
                border: 2.5px solid #3b82f6;
                box-shadow: 0 3px 10px rgba(0, 0, 0, 0.25);
                transition: transform 0.2s ease, box-shadow 0.2s ease;
                cursor: pointer;
                overflow: visible;
                box-sizing: border-box;
                padding: 0;
                position: relative;
            }}
            .logo-marker-pin:hover {{
                transform: scale(1.25);
                box-shadow: 0 6px 20px rgba(0, 0, 0, 0.4);
                z-index: 1000 !important;
            }}
            .logo-marker-pin img {{
                width: 22px;
                height: 22px;
                max-width: 22px;
                max-height: 22px;
                object-fit: contain;
                display: block;
                margin: 0 auto;
                border-radius: 4px;
            }}
            .cluster-badge-count {{
                position: absolute;
                top: -7px;
                right: -7px;
                background: #059669;
                color: #ffffff;
                font-size: 11px;
                font-weight: 800;
                padding: 1.5px 6px;
                border-radius: 12px;
                border: 1.5px solid #ffffff;
                box-shadow: 0 2px 6px rgba(0,0,0,0.3);
                font-family: 'Noto Sans Thai', 'Inter', sans-serif;
                line-height: 1.1;
                white-space: nowrap !important;
                display: inline-flex !important;
                align-items: center !important;
                justify-content: center !important;
                z-index: 1000 !important;
            }}
            .centroid-badge {{
                background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%) !important;
                color: #ffffff !important;
                border-color: #ffffff !important;
                font-weight: 900 !important;
                box-shadow: 0 2px 8px rgba(217, 119, 6, 0.6) !important;
                white-space: nowrap !important;
            }}
            .type-marker-pin {{
                display: flex;
                justify-content: center;
                align-items: center;
                width: 32px;
                height: 32px;
                border-radius: 50%;
                border: 2px solid #ffffff;
                box-shadow: 0 3px 10px rgba(0, 0, 0, 0.35);
                transition: transform 0.2s ease;
                cursor: pointer;
                font-size: 15px;
                box-sizing: border-box;
                color: #ffffff;
            }}
            .type-marker-pin:hover {{
                transform: scale(1.35);
                box-shadow: 0 6px 20px rgba(0, 0, 0, 0.5);
                z-index: 1000 !important;
            }}
            /* Multi-Asset Cluster Pin */
            .cluster-marker-pin {{
                display: flex;
                flex-direction: column;
                justify-content: center;
                align-items: center;
                width: 42px;
                height: 42px;
                background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
                border-radius: 50%;
                border: 2.5px solid #38bdf8;
                box-shadow: 0 4px 16px rgba(56, 189, 248, 0.5);
                cursor: pointer;
                transition: transform 0.25s cubic-bezier(0.34, 1.56, 0.64, 1), box-shadow 0.25s ease, border-color 0.2s ease;
                box-sizing: border-box;
                position: relative;
            }}
            .cluster-marker-pin:hover {{
                transform: scale(1.25);
                box-shadow: 0 8px 25px rgba(56, 189, 248, 0.85);
                border-color: #ffffff;
                z-index: 1000 !important;
            }}
            .cluster-marker-count {{
                font-size: 14px;
                font-weight: 900;
                color: #ffffff;
                line-height: 1;
                font-family: 'Noto Sans Thai', 'Inter', sans-serif;
            }}
            .cluster-marker-sub {{
                font-size: 8px;
                font-weight: 700;
                color: #38bdf8;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                margin-top: 1px;
            }}
            .cluster-brand-dots {{
                position: absolute;
                bottom: -5px;
                display: flex;
                gap: 2px;
                background: rgba(15, 23, 42, 0.9);
                padding: 1px 4px;
                border-radius: 6px;
                border: 1px solid rgba(255, 255, 255, 0.25);
            }}
            .cluster-dot {{
                width: 5px;
                height: 5px;
                border-radius: 50%;
            }}
            /* Spider Leg Lines */
            .spider-leg-line {{
                stroke: #38bdf8;
                stroke-width: 2px;
                stroke-dasharray: 4, 3;
                opacity: 0.85;
            }}
            .ref-marker-pin {{
                display: flex;
                justify-content: center;
                align-items: center;
                width: 44px;
                height: 44px;
                background: #ef4444;
                border-radius: 50%;
                border: 3.5px solid #ffffff;
                box-shadow: 0 4px 16px rgba(239, 68, 68, 0.65);
                animation: pulse-ring 2s infinite;
                box-sizing: border-box;
            }}
            .ref-marker-pin-inner {{
                width: 16px;
                height: 16px;
                background: #ffffff;
                border-radius: 50%;
                box-shadow: 0 1px 4px rgba(0,0,0,0.35);
            }}
            @keyframes pulse-ring {{
                0% {{ box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.7); }}
                70% {{ box-shadow: 0 0 0 18px rgba(239, 68, 68, 0); }}
                100% {{ box-shadow: 0 0 0 0 rgba(239, 68, 68, 0); }}
            }}
            .leaflet-popup-content-wrapper {{
                background: #ffffff !important;
                color: #0f172a !important;
                border-radius: 16px !important;
                border: 1px solid rgba(0, 0, 0, 0.12) !important;
                box-shadow: 0 16px 40px rgba(0, 0, 0, 0.22) !important;
                padding: 4px !important;
            }}
            .leaflet-popup-tip {{
                background: #ffffff !important;
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.14) !important;
            }}
            .leaflet-popup-content {{
                margin: 12px 14px !important;
                line-height: 1.45 !important;
                color: #0f172a !important;
            }}
            .leaflet-tooltip {{
                background: rgba(15, 23, 42, 0.94) !important;
                color: #ffffff !important;
                border-radius: 8px !important;
                border: 1px solid rgba(255, 255, 255, 0.18) !important;
                box-shadow: 0 6px 18px rgba(0,0,0,0.3) !important;
                padding: 6px 10px !important;
                font-size: 12.5px !important;
            }}
            .leaflet-tooltip-top:before {{
                border-top-color: rgba(15, 23, 42, 0.94) !important;
            }}
            .multi-pill-scroll {{
                display: flex;
                gap: 6px;
                overflow-x: auto;
                padding: 3px 2px 7px 2px;
                margin-bottom: 9px;
                scrollbar-width: thin;
                scrollbar-color: #cbd5e1 transparent;
                scroll-behavior: smooth;
            }}
            .multi-pill-scroll::-webkit-scrollbar {{
                height: 4px;
            }}
            .multi-pill-scroll::-webkit-scrollbar-thumb {{
                background: #cbd5e1;
                border-radius: 4px;
            }}
            .multi-pill-tab {{
                background: #f8fafc;
                border: 1.5px solid #cbd5e1;
                color: #334155;
                border-radius: 16px;
                padding: 5px 11px;
                font-size: 12.5px;
                cursor: pointer;
                white-space: nowrap;
                transition: all 0.15s ease;
                font-family: 'Noto Sans Thai', 'Inter', sans-serif;
                font-weight: 600;
                outline: none;
            }}
            .multi-pill-tab:hover {{
                background: #f1f5f9;
                color: #0f172a;
                border-color: #94a3b8;
            }}
            .multi-pill-tab.active {{
                background: #059669;
                color: #ffffff;
                border-color: #047857;
                font-weight: 800;
                box-shadow: 0 3px 10px rgba(5, 150, 105, 0.4);
            }}
            .unit-nav-btn {{
                background: #ffffff;
                border: 1px solid #cbd5e1;
                color: #047857;
                width: 22px;
                height: 22px;
                border-radius: 50%;
                display: inline-flex;
                align-items: center;
                justify-content: center;
                cursor: pointer;
                font-size: 10px;
                padding: 0;
                transition: all 0.15s ease;
                box-shadow: 0 1px 2px rgba(0,0,0,0.06);
            }}
            .unit-nav-btn:hover {{
                background: #ecfdf5;
                border-color: #059669;
                color: #047857;
                transform: scale(1.12);
            }}
            .unit-nav-bar-btn {{
                background: #ffffff;
                border: 1.5px solid #cbd5e1;
                border-radius: 8px;
                padding: 6px 14px;
                font-size: 12.5px;
                font-weight: 700;
                color: #1e293b;
                cursor: pointer;
                display: flex;
                align-items: center;
                gap: 6px;
                box-shadow: 0 1px 3px rgba(0,0,0,0.06);
                transition: all 0.15s ease;
                font-family: 'Noto Sans Thai', 'Inter', sans-serif;
            }}
            .unit-nav-bar-btn:hover {{
                background: #ecfdf5;
                border-color: #059669;
                color: #047857;
                box-shadow: 0 2px 6px rgba(5, 150, 105, 0.18);
                transform: translateY(-1px);
            }}
            .unit-nav-bar-btn:active, .unit-nav-btn:active {{
                transform: translateY(0);
            }}
            .view-toggle-btn {{
                display: block;
                width: 100%;
                background: #f8fafc;
                border: 1.5px solid #cbd5e1;
                color: #1e293b;
                border-radius: 9px;
                padding: 8px 12px;
                font-size: 13px;
                font-weight: 700;
                text-align: center;
                cursor: pointer;
                margin-top: 9px;
                transition: all 0.15s ease;
                font-family: 'Noto Sans Thai', 'Inter', sans-serif;
            }}
            .view-toggle-btn:hover {{
                background: #f1f5f9;
                border-color: #94a3b8;
                color: #0f172a;
            }}
            .map-legend-box {{
                background: rgba(255, 255, 255, 0.95);
                backdrop-filter: blur(10px);
                border: 1px solid rgba(0, 0, 0, 0.1);
                color: #0f172a;
                padding: 10px 14px;
                border-radius: 12px;
                font-size: 11.5px;
                box-shadow: 0 8px 24px rgba(0,0,0,0.12);
                max-height: 240px;
                overflow-y: auto;
                line-height: 1.5;
            }}
            .map-legend-title {{
                font-weight: 800;
                font-size: 12px;
                margin-bottom: 6px;
                color: #1e293b;
                border-bottom: 1px solid #e2e8f0;
                padding-bottom: 4px;
            }}
            .map-legend-item {{
                display: flex;
                align-items: center;
                gap: 7px;
                margin-bottom: 3px;
                color: #334155;
            }}
            .map-legend-color {{
                width: 13px;
                height: 13px;
                border-radius: 50%;
                border: 1.5px solid #ffffff;
                box-shadow: 0 1px 3px rgba(0,0,0,0.2);
                flex-shrink: 0;
            }}
            .leaflet-control-layers {{
                background: rgba(255, 255, 255, 0.95) !important;
                backdrop-filter: blur(10px) !important;
                border: 1px solid rgba(0, 0, 0, 0.1) !important;
                color: #0f172a !important;
                border-radius: 10px !important;
                font-family: 'Noto Sans Thai', 'Inter', sans-serif !important;
                font-size: 12px !important;
                box-shadow: 0 4px 16px rgba(0,0,0,0.12) !important;
            }}
            .leaflet-control-layers-base label {{
                color: #1e293b !important;
                margin-bottom: 3px !important;
                cursor: pointer !important;
            }}
        </style>
    </head>
    <body>
        <div id="map"></div>
        <script>
            var map = L.map('map', {{
                zoomControl: true,
                attributionControl: false,
                dragging: true,
                touchZoom: true,
                scrollWheelZoom: true,
                doubleClickZoom: true,
                boxZoom: true,
                keyboard: true
            }}).setView([{inp_lat}, {inp_lng}], 13);

            // Base Tile Layers (Crystal-clear, 100% free with no watermark)
            var streetLayer = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{{z}}/{{y}}/{{x}}', {{ maxZoom: 19 }});
            var osmLayer = L.tileLayer('https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{ maxZoom: 19 }});
            var satLayer = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}', {{ maxZoom: 19 }});
            var topoLayer = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{{z}}/{{y}}/{{x}}', {{ maxZoom: 19 }});
            var darkLayer = L.tileLayer('https://{{s}}.basemaps.cartocdn.com/dark_all/{{z}}/{{x}}/{{y}}{{r}}.png', {{ maxZoom: 19 }});

            // Set default base layer
            var defaultBaseKey = "{default_base}";
            if (defaultBaseKey === "satellite") {{
                satLayer.addTo(map);
            }} else if (defaultBaseKey === "dark") {{
                darkLayer.addTo(map);
            }} else if (defaultBaseKey === "osm") {{
                osmLayer.addTo(map);
            }} else {{
                streetLayer.addTo(map);
            }}

            // Add Leaflet Layer Switcher Control
            var baseMaps = {{
                "แผนที่ถนนมาตรฐาน (Esri Street)": streetLayer,
                "OpenStreetMap": osmLayer,
                "ภาพถ่ายดาวเทียม (Satellite)": satLayer,
                "ภูมิประเทศ (Topographic)": topoLayer,
                "โหมดมืด (Dark Canvas)": darkLayer
            }};
            L.control.layers(baseMaps, null, {{ position: 'topright' }}).addTo(map);

            var logos = {logos_json};
            var properties = {props_json};
            var colorMode = "{active_color_mode_code}";
            var legendStats = {legend_stats_json};

            // Color Palettes
            var companyColors = {{
                "LED": "#0891b2", "SAM": "#10b981", "BAM": "#3b82f6", "Chayo555": "#f97316", "Chayo": "#f97316",
                "GHB": "#ca8a04", "KBANK": "#059669", "KTB": "#0284c7", "SCB": "#7e22ce", "GSB": "#eb1985",
                "DDproperty": "#a855f7", "Livinginsider": "#14b8a6", "NaYoo": "#8b5cf6", "ZmyHome": "#ec4899", "Baania": "#f59e0b"
            }};

            var propTypeColors = {{
                "บ้านเดี่ยว": "#059669", "ห้องชุดพักอาศัย": "#2563eb", "คอนโด": "#2563eb", "คอนโดมิเนียม": "#2563eb",
                "ทาวน์เฮ้าส์": "#f59e0b", "ทาวน์โฮม": "#f59e0b", "ที่ดินเปล่า": "#10b981", "ที่ดิน": "#10b981",
                "อาคารพาณิชย์": "#7c3aed", "โรงงาน/โกดัง": "#d97706", "อพาร์ทเมนท์": "#db2777", "บ้านแฝด": "#0284c7"
            }};
            var propTypeIcons = {{
                "บ้านเดี่ยว": '<i class="fa-solid fa-house" style="color:#ffffff; font-size:13px;"></i>',
                "ห้องชุดพักอาศัย": '<i class="fa-solid fa-building" style="color:#ffffff; font-size:13px;"></i>',
                "คอนโด": '<i class="fa-solid fa-building" style="color:#ffffff; font-size:13px;"></i>',
                "คอนโดมิเนียม": '<i class="fa-solid fa-building" style="color:#ffffff; font-size:13px;"></i>',
                "ทาวน์เฮ้าส์": '<i class="fa-solid fa-city" style="color:#ffffff; font-size:13px;"></i>',
                "ทาวน์โฮม": '<i class="fa-solid fa-city" style="color:#ffffff; font-size:13px;"></i>',
                "ที่ดินเปล่า": '<i class="fa-solid fa-tree" style="color:#ffffff; font-size:13px;"></i>',
                "ที่ดิน": '<i class="fa-solid fa-tree" style="color:#ffffff; font-size:13px;"></i>',
                "อาคารพาณิชย์": '<i class="fa-solid fa-store" style="color:#ffffff; font-size:13px;"></i>',
                "โรงงาน/โกดัง": '<i class="fa-solid fa-industry" style="color:#ffffff; font-size:13px;"></i>',
                "อพาร์ทเมนท์": '<i class="fa-solid fa-hotel" style="color:#ffffff; font-size:13px;"></i>',
                "บ้านแฝด": '<i class="fa-solid fa-house-chimney-window" style="color:#ffffff; font-size:13px;"></i>'
            }};

            function getPriceColor(priceNum) {{
                if (!priceNum || priceNum <= 0) return "#64748b";
                if (priceNum < 1000000) return "#10b981";
                if (priceNum < 3000000) return "#06b6d4";
                if (priceNum < 5000000) return "#3b82f6";
                if (priceNum < 10000000) return "#f59e0b";
                if (priceNum < 20000000) return "#f97316";
                return "#ef4444";
            }}

            function parseRawPrice(priceStr) {{
                if (!priceStr) return 0;
                var num = parseFloat(priceStr.toString().replace(/[^0-9.]/g, ''));
                return isNaN(num) ? 0 : num;
            }}

            // 1. Search Radius Buffer Circle
            var radiusCircle = L.circle([{inp_lat}, {inp_lng}], {{
                radius: {search_radius_km * 1000},
                color: '#6366f1',
                fillColor: '#6366f1',
                fillOpacity: 0.12,
                weight: 2.5,
                dashArray: '6, 6'
            }}).addTo(map);

            // 2. Reference Target Pin
            var refIcon = L.divIcon({{
                className: 'custom-ref-icon',
                html: '<div class="ref-marker-pin"><div class="ref-marker-pin-inner"></div></div>',
                iconSize: [44, 44],
                iconAnchor: [22, 22]
            }});

            var refMarker = L.marker([{inp_lat}, {inp_lng}], {{ icon: refIcon }}).addTo(map);
            refMarker.bindPopup('<div style="font-size:13.5px; font-weight:800; color:#ef4444; margin-bottom:3px;">จุดอ้างอิงของคุณ</div><div style="font-size:12px; color:#64748b;">ศูนย์กลางการค้นหารัศมี ({search_radius_km} กม.)</div><div style="font-size:11px; color:#475569; margin-top:3px;">พิกัด: {inp_lat:.5f}, {inp_lng:.5f}</div>');
            refMarker.bindTooltip('จุดอ้างอิง ({search_radius_km} กม.)', {{ direction: 'top', offset: [0, -22] }});

            // Helper to copy text to clipboard with fallback
            window.copyTextVal = function(btn, text, successMsg) {{
                if (!text) return;
                var showFeedback = function() {{
                    if (!btn) return;
                    var oldHtml = btn.innerHTML;
                    btn.innerHTML = successMsg || '<i class="fa-solid fa-check" style="color:#10b981; margin-right:4px;"></i>คัดลอกแล้ว!';
                    btn.style.borderColor = '#10b981';
                    btn.style.color = '#059669';
                    setTimeout(function() {{
                        btn.innerHTML = oldHtml;
                        btn.style.borderColor = '';
                        btn.style.color = '';
                    }}, 2000);
                }};

                if (navigator.clipboard && navigator.clipboard.writeText) {{
                    navigator.clipboard.writeText(text).then(function() {{
                        showFeedback();
                    }})['catch'](function() {{
                        fallbackCopy();
                    }});
                }} else {{
                    fallbackCopy();
                }}

                function fallbackCopy() {{
                    try {{
                        var ta = document.createElement('textarea');
                        ta.value = text;
                        ta.style.position = 'fixed';
                        ta.style.opacity = '0';
                        document.body.appendChild(ta);
                        ta.focus();
                        ta.select();
                        document.execCommand('copy');
                        document.body.removeChild(ta);
                        showFeedback();
                    }} catch(e) {{
                        console.log('NPA copy error:', e);
                    }}
                }}
            }};

            window.copyCoordBtn = function(btn) {{
                var c = btn.getAttribute('data-coord') || '';
                window.copyTextVal(btn, c, '<i class="fa-solid fa-check" style="color:#10b981; margin-right:4px;"></i>คัดลอกพิกัดแล้ว!');
            }};

            window.copyCodeBtn = function(btn) {{
                var c = btn.getAttribute('data-code') || '';
                window.copyTextVal(btn, c, '<i class="fa-solid fa-check" style="color:#10b981; margin-right:4px;"></i>คัดลอกรหัสแล้ว!');
            }};

            window.copyAllCodesBtn = function(btn) {{
                var c = btn.getAttribute('data-codes') || '';
                window.copyTextVal(btn, c, '<i class="fa-solid fa-check" style="color:#10b981; margin-right:4px;"></i>คัดลอกรหัสทั้งหมด!');
            }};

            // Robust Logo Finder in JS
            function getCompanyLogo(comp) {{
                if (!comp || !logos || typeof logos !== 'object') return '';
                var c = String(comp).trim();
                if (logos[c]) return logos[c];
                if (logos[c.toLowerCase()]) return logos[c.toLowerCase()];
                if (logos[c.toUpperCase()]) return logos[c.toUpperCase()];
                var cLower = c.toLowerCase();
                for (var k in logos) {{
                    var kLower = k.toLowerCase();
                    if (cLower === kLower || cLower.indexOf(kLower) !== -1 || kLower.indexOf(cLower) !== -1) {{
                        return logos[k];
                    }}
                }}
                return '';
            }}

            // Helper to create single property marker icon
            function createPropertyIcon(p, isCentroid) {{
                var comp = p.company || 'BAM';
                var pType = p.type || 'อื่นๆ';
                var rawP = parseRawPrice(p.price);
                var compColor = companyColors[comp] || '#2563eb';
                var typeColor = propTypeColors[pType] || '#64748b';
                var priceColor = getPriceColor(rawP);
                var isApprox = Boolean(isCentroid || p.is_centroid);
                var approxBadge = isApprox ? '<span class="cluster-badge-count centroid-badge" style="position:absolute; top:-7px; right:-7px; background:linear-gradient(135deg, #f59e0b 0%, #d97706 100%); color:#ffffff; font-size:10px; font-weight:900; padding:1px 5px; border-radius:10px; border:1.5px solid #ffffff; box-shadow:0 2px 6px rgba(0,0,0,0.3); z-index:10; white-space:nowrap !important;">!</span>' : '';
                var borderColor = isApprox ? '#f59e0b' : compColor;

                if (colorMode === "property_type") {{
                    var iconEmoji = propTypeIcons[pType] || '<i class="fa-solid fa-location-dot" style="color:#ffffff; font-size:13px;"></i>';
                    return L.divIcon({{
                        className: 'custom-type-icon',
                        html: '<div class="type-marker-pin" style="background:' + typeColor + '; position:relative;">' + iconEmoji + approxBadge + '</div>',
                        iconSize: [32, 32],
                        iconAnchor: [16, 16],
                        popupAnchor: [0, -16]
                    }});
                }} else if (colorMode === "price_level") {{
                    return L.divIcon({{
                        className: 'custom-price-icon',
                        html: '<div class="type-marker-pin" style="background:' + priceColor + '; font-size:12px; font-weight:800; position:relative;">฿' + approxBadge + '</div>',
                        iconSize: [32, 32],
                        iconAnchor: [16, 16],
                        popupAnchor: [0, -16]
                    }});
                }} else {{
                    var logoUrl = getCompanyLogo(comp);
                    var logoHtml = logoUrl ? '<img src="' + logoUrl + '" alt="' + comp + '" />' : '<span style="font-weight:800; font-size:11px; color:#0f172a;">' + comp.substring(0,3) + '</span>';
                    return L.divIcon({{
                        className: 'custom-logo-icon',
                        html: '<div class="logo-marker-pin" style="border-color:' + borderColor + '; position:relative;">' + logoHtml + approxBadge + '</div>',
                        iconSize: [36, 36],
                        iconAnchor: [18, 18],
                        popupAnchor: [0, -18]
                    }});
                }}
            }}

            // Function to build Single Item Detail HTML
            function buildItemDetailHTML(p, idxInGroup, totalInGroup, groupKey) {{
                groupKey = groupKey || '';
                var comp = p.company || 'BAM';
                var isLED = (comp === 'LED' || String(comp).toUpperCase().indexOf('LED') !== -1 || String(comp).indexOf('กรมบังคับคดี') !== -1);
                var locParts = [p.subdist, p.district, p.province].filter(function(v) {{
                    return v && v !== 'nan' && v !== 'None' && v !== '-' && String(v).trim() !== '';
                }});
                var locStr = locParts.join(', ');
                var compColor = companyColors[comp] || '#2563eb';
                var logoUrl = getCompanyLogo(comp);
                var logoImg = logoUrl ? '<img src="' + logoUrl + '" style="width:16px;height:16px;object-fit:contain;vertical-align:middle;margin-right:5px;border-radius:3px;" />' : '';

                var validProject = (p.project && p.project !== '-' && p.project !== 'nan') ? p.project : '';

                var landStr = (p.land_area && p.land_area !== '-' && p.land_area !== 'nan') ? p.land_area : '-';
                var usableStr = (p.usable_area && p.usable_area !== '-' && p.usable_area !== 'nan') ? p.usable_area : '-';
                var pricePerWah = (p.price_per_wah && p.price_per_wah !== '-' && p.price_per_wah !== 'nan') ? p.price_per_wah : '';
                var pricePerSqm = (p.price_per_sqm && p.price_per_sqm !== '-' && p.price_per_sqm !== 'nan') ? p.price_per_sqm : '';

                var linksHTML = '';
                if (isLED) {{
                    var pLinkHtml = (p.link && p.link !== '-' && p.link !== '') ? '<a href="' + p.link + '" target="_blank" style="flex:1; text-align:center; background:linear-gradient(135deg, #059669 0%, #047857 100%); color:#ffffff; padding:9px 10px; border-radius:9px; text-decoration:none; font-size:13px; font-weight:800; box-shadow:0 3px 10px rgba(5,150,105,0.3); transition:all 0.15s ease; white-space:nowrap;"><i class="fa-solid fa-arrow-up-right-from-square"></i> เปิดดูประกาศ ↗</a>' : '';
                    linksHTML = '<div style="display:flex; gap:6px; margin-bottom:6px;">' +
                        pLinkHtml +
                        '<a href="https://landsmaps.dol.go.th/" target="_blank" style="flex:1; text-align:center; background:linear-gradient(135deg, #0d9488 0%, #0f766e 100%); color:#ffffff; padding:9px 10px; border-radius:9px; text-decoration:none; font-size:13px; font-weight:800; box-shadow:0 3px 10px rgba(13,148,136,0.3); transition:all 0.15s ease; white-space:nowrap;"><i class="fa-solid fa-map-location-dot"></i> ดูแปลงที่ดิน (LandsMaps) ↗</a>' +
                        '</div>';
                }} else if (p.link && p.link !== '-' && p.link !== '') {{
                    linksHTML = '<a href="' + p.link + '" target="_blank" style="display:block; text-align:center; background:linear-gradient(135deg, #059669 0%, #047857 100%); color:#ffffff; padding:9px 14px; border-radius:9px; text-decoration:none; font-size:13.5px; font-weight:800; box-shadow:0 3px 10px rgba(5,150,105,0.3); margin-bottom:6px; transition:all 0.15s ease;"><i class="fa-solid fa-arrow-up-right-from-square"></i> เปิดดูประกาศทรัพย์สิน ↗</a>';
                }}

                return '<div class="item-card-inner" style="padding: 2px 0;">' +
                    (p.is_centroid ? '<div style="background:#fffbeb; border:1.5px solid #fde68a; border-radius:8px; padding:5px 9px; margin-bottom:8px; font-size:12px; color:#b45309; font-weight:700; display:flex; align-items:center; gap:5px;"><i class="fa-solid fa-triangle-exclamation"></i> <span><b>พิกัดโดยประมาณ</b> (คำนวณจากจุดกึ่งกลางตำบล/อำเภอ)</span></div>' : '') +
                    '<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">' +
                    '  <div style="display:flex; gap:6px; align-items:center; flex-wrap:wrap;">' +
                    '    <span style="background:#f8fafc; border-left:4px solid ' + compColor + '; border-top:1px solid #e2e8f0; border-right:1px solid #e2e8f0; border-bottom:1px solid #e2e8f0; color:#0f172a; padding:3px 9px; border-radius:6px; font-size:13px; font-weight:800;">' + logoImg + comp + '</span>' +
                    '    <span style="background:#fef3c7; border:1px solid #fde68a; color:#92400e; padding:3px 8px; border-radius:6px; font-size:12.5px; font-weight:700;">' + (p.type || '-') + '</span>' +
                    (p.sale_type && p.sale_type !== '-' && p.sale_type !== 'nan' ? '<span style="background:#f1f5f9; color:#334155; padding:3px 7px; border-radius:6px; font-size:12px; font-weight:600;">' + p.sale_type + '</span>' : '') +
                    '  </div>' +
                    (totalInGroup > 1 ?
                        '<div style="display:inline-flex; align-items:center; gap:2px; background:#ecfdf5; border:1.5px solid #a7f3d0; border-radius:14px; padding:2px 4px; box-shadow:0 1px 3px rgba(0,0,0,0.05);">' +
                        '  <button type="button" class="unit-nav-btn" data-group="' + groupKey + '" onclick="window.stepMultiUnitSlide(this.dataset.group, -1, ' + totalInGroup + ')" title="ดูทรัพย์ก่อนหน้า (ยูนิตที่แล้ว)"><i class="fa-solid fa-chevron-left"></i></button>' +
                        '  <span style="font-weight:800; font-size:12px; color:#047857; min-width:30px; text-align:center; padding:0 2px;">' + (idxInGroup + 1) + '/' + totalInGroup + '</span>' +
                        '  <button type="button" class="unit-nav-btn" data-group="' + groupKey + '" onclick="window.stepMultiUnitSlide(this.dataset.group, 1, ' + totalInGroup + ')" title="ดูทรัพย์ถัดไป"><i class="fa-solid fa-chevron-right"></i></button>' +
                        '</div>' : '') +
                    '</div>' +

                    '<div style="font-weight:800; font-size:15.5px; color:#0f172a; line-height:1.4; margin-bottom:6px; word-break:break-word;">' + (p.name || 'ทรัพย์สิน') + '</div>' +

                    '<div style="color:#475569; font-size:12.5px; margin-bottom:10px;">' +
                    '<i class="fa-solid fa-hashtag" style="color:#64748b; font-size:11px;"></i> รหัส: <b style="color:#0f172a; font-size:13px;">' + (p.code || '-') + '</b>' +
                    (validProject ? ' • <i class="fa-solid fa-building" style="color:#64748b; font-size:11px;"></i> <span style="color:#1e293b; font-weight:600;">' + validProject + '</span>' : '') +
                    '</div>' +

                    '<div style="background:linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%); border:1.5px solid #86efac; border-radius:10px; padding:9px 12px; margin-bottom:10px;">' +
                    '  <div style="display:flex; justify-content:space-between; align-items:center;">' +
                    '    <div><span style="font-size:11px; color:#166534; text-transform:uppercase; font-weight:800; letter-spacing:0.3px;">ราคาเสนอขาย</span><br/><b style="font-size:21px; color:#15803d; font-family:Noto Sans Thai,Inter,sans-serif; letter-spacing:0.3px; font-weight:900;">' + (p.price || '-') + '</b></div>' +
                    (p.dist ? '<div style="text-align:right;"><span style="font-size:11px; color:#9f1239; font-weight:800;">ระยะห่าง</span><br/><b style="font-size:15px; color:#be123c; font-family:Noto Sans Thai,Inter,sans-serif; font-weight:800;">' + p.dist + '</b></div>' : '') +
                    '  </div>' +
                    '</div>' +

                    '<div style="background:#f8fafc; border-radius:10px; padding:8px 11px; font-size:13px; margin-bottom:10px; border:1px solid #e2e8f0; color:#334155;">' +
                    '  <div style="display:flex; justify-content:space-between; margin-bottom:4px;">' +
                    '    <span><i class="fa-solid fa-ruler-combined" style="color:#64748b; margin-right:3px; font-size:11px;"></i>เนื้อที่: <b style="color:#0f172a;">' + landStr + '</b></span>' +
                    (pricePerWah ? '<span style="color:#059669; font-weight:800;">(' + pricePerWah + ')</span>' : '') +
                    '  </div>' +
                    '  <div style="display:flex; justify-content:space-between;">' +
                    '    <span><i class="fa-solid fa-house-chimney" style="color:#64748b; margin-right:3px; font-size:11px;"></i>ใช้สอย: <b style="color:#0f172a;">' + usableStr + '</b></span>' +
                    (pricePerSqm ? '<span style="color:#059669; font-weight:800;">(' + pricePerSqm + ')</span>' : '') +
                    '  </div>' +
                    '</div>' +

                    (locStr ? '<div style="font-size:12.5px; color:#475569; margin-bottom:10px; line-height:1.4;"><i class="fa-solid fa-location-dot" style="color:#64748b; margin-right:4px;"></i><span style="color:#1e293b; font-weight:500;">' + locStr + '</span></div>' : '') +

                    linksHTML +

                    (totalInGroup === 1 ? '<div style="display:flex; gap:6px; margin-top:8px;">' +
                    '  <button type="button" data-coord="' + parseFloat(p.lat || 0).toFixed(5) + ',' + parseFloat(p.lon || 0).toFixed(5) + '" onclick="window.copyCoordBtn(this)" style="flex:1; background:#f8fafc; border:1.5px solid #cbd5e1; color:#334155; padding:8px 10px; border-radius:8px; font-size:13px; font-weight:700; cursor:pointer; display:flex; align-items:center; justify-content:center; gap:5px; box-shadow:0 1px 3px rgba(0,0,0,0.05); transition:all 0.15s ease;"><i class="fa-regular fa-copy"></i> คัดลอกพิกัด</button>' +
                    '  <button type="button" data-code="' + (p.code || p.id || '') + '" onclick="window.copyCodeBtn(this)" style="flex:1; background:#f8fafc; border:1.5px solid #cbd5e1; color:#334155; padding:8px 10px; border-radius:8px; font-size:13px; font-weight:700; cursor:pointer; display:flex; align-items:center; justify-content:center; gap:5px; box-shadow:0 1px 3px rgba(0,0,0,0.05); transition:all 0.15s ease;"><i class="fa-regular fa-copy"></i> คัดลอกรหัสทรัพย์</button>' +
                    '</div>' : '') +
                    '</div>';
            }}

            // Function to build Multi-Unit Interactive Popup (Clean White Card Theme)
            function buildMultiUnitPopupHTML(group) {{
                var total = group.items.length;
                var groupKey = group.key;
                var companiesInGroup = [];
                var allCodesList = [];
                group.items.forEach(function(item) {{
                    if (item.company && companiesInGroup.indexOf(item.company) === -1) {{
                        companiesInGroup.push(item.company);
                    }}
                    var c = item.code || item.id;
                    if (c && c !== '-' && allCodesList.indexOf(c) === -1) {{
                        allCodesList.push(c);
                    }}
                }});

                var allCodesStr = allCodesList.join(',');
                var grpLatStr = parseFloat(group.lat).toFixed(5);
                var grpLonStr = parseFloat(group.lon).toFixed(5);

                var maxTabs = Math.min(total, 50);
                var tabsHTML = '<div class="multi-pill-scroll" id="pills_' + groupKey + '">';
                var cardsHTML = '<div id="card_view_' + groupKey + '">';
                var tableRowsHTML = '';

                group.items.forEach(function(item, i) {{
                    var comp = item.company || 'BAM';
                    var cColor = companyColors[comp] || '#64748b';
                    var activeClass = i === 0 ? 'active' : '';
                    var activeDisplay = i === 0 ? 'block' : 'none';
                    var itemLogo = getCompanyLogo(comp);
                    var pillLogo = itemLogo ? '<img src="' + itemLogo + '" style="width:15px;height:15px;object-fit:contain;vertical-align:middle;margin-right:4px;border-radius:2px;" />' : '';

                    var itemUnitTag = item.price_per_wah || item.price_per_sqm || '';
                    var itemUnitHtml = itemUnitTag ? ' <span style="font-size:10px; color:#059669; font-weight:700;">(' + itemUnitTag + ')</span>' : '';
                    if (i < maxTabs) {{
                        tabsHTML += '<button type="button" class="multi-pill-tab ' + activeClass + '" data-group="' + groupKey + '" data-idx="' + i + '" onclick="window.switchMultiUnitTab(this.dataset.group, parseInt(this.dataset.idx))" id="tab_' + groupKey + '_' + i + '" style="border-left:3.5px solid ' + cColor + ';">' +
                            pillLogo + (i + 1) + '. ' + comp + ' ' + (item.price || '-') + itemUnitHtml +
                            '</button>';
                    }}

                    cardsHTML += '<div class="unit-slide" id="slide_' + groupKey + '_' + i + '" style="display:' + activeDisplay + ';">' +
                        buildItemDetailHTML(item, i, total, groupKey) +
                        '</div>';

                    if (i < 25) {{
                        var landOrUse = (item.land_area && item.land_area !== '-' && item.land_area !== 'nan') ? item.land_area : (item.usable_area || '-');
                        var rowLogo = getCompanyLogo(comp);
                        var rowLogoImg = rowLogo ? '<img src="' + rowLogo + '" style="width:15px;height:15px;object-fit:contain;vertical-align:middle;margin-right:4px;border-radius:2px;" />' : '';
                        var rowCode = item.code || item.id || '';
                        var isRowLED = (comp === 'LED' || String(comp).toUpperCase().indexOf('LED') !== -1 || String(comp).indexOf('กรมบังคับคดี') !== -1);
                        tableRowsHTML += '<tr style="border-bottom:1px solid #f1f5f9;">' +
                            '<td style="padding:6px 8px; font-weight:700; color:' + cColor + '; white-space:nowrap;">' + rowLogoImg + comp + '</td>' +
                            '<td style="padding:6px 8px; color:#0f172a; font-weight:600;">' + (item.code || '-') + '</td>' +
                            '<td style="padding:6px 8px; font-weight:800; color:#15803d;">' + (item.price || '-') + '</td>' +
                            '<td style="padding:6px 8px; color:#475569;">' + landOrUse + '</td>' +
                            '<td style="padding:6px 8px; text-align:right; white-space:nowrap;">' +
                            (item.link ? '<a href="' + item.link + '" target="_blank" style="color:#2563eb; text-decoration:none; font-weight:700; margin-right:6px;" title="เปิดดูประกาศ"><i class="fa-solid fa-arrow-up-right-from-square"></i> ดู</a>' : '') +
                            (isRowLED ? '<a href="https://landsmaps.dol.go.th/" target="_blank" style="color:#0d9488; text-decoration:none; font-weight:700; margin-right:6px;" title="ระบบค้นหารูปแปลงที่ดิน (LandsMaps)"><i class="fa-solid fa-map-location-dot"></i> แปลง LandsMaps</a>' : '') +
                            '<button type="button" data-code="' + rowCode + '" onclick="window.copyCodeBtn(this)" style="background:#f8fafc; border:1px solid #cbd5e1; color:#475569; padding:3px 7px; border-radius:5px; font-size:11px; font-weight:700; cursor:pointer; display:inline-block;"><i class="fa-regular fa-copy"></i> คัดลอก</button>' +
                            '</td>' +
                            '</tr>';
                    }}
                }});

                if (total > maxTabs) {{
                    tabsHTML += '<span style="font-size:11.5px; font-weight:700; color:#64748b; align-self:center; white-space:nowrap; padding:0 6px;">+' + (total - maxTabs) + '</span>';
                }}

                tabsHTML += '</div>';
                cardsHTML += '</div>';

                var navBarHTML = '';
                if (total > 1) {{
                    navBarHTML = '<div id="nav_bar_' + groupKey + '" class="multi-unit-nav-bar" style="display:flex; justify-content:space-between; align-items:center; background:#f8fafc; border:1.5px solid #e2e8f0; border-radius:10px; padding:6px 10px; margin-top:8px; margin-bottom:6px; box-shadow:0 1px 3px rgba(0,0,0,0.04);">' +
                        '  <button type="button" class="unit-nav-bar-btn" data-group="' + groupKey + '" onclick="window.stepMultiUnitSlide(this.dataset.group, -1, ' + total + ')" title="ดูทรัพย์ก่อนหน้า"><i class="fa-solid fa-chevron-left" style="color:#059669;"></i> ก่อนหน้า</button>' +
                        '  <div style="display:flex; flex-direction:column; align-items:center; line-height:1.2;">' +
                        '    <span style="font-size:10.5px; color:#64748b; font-weight:700;">เลื่อนดูทรัพย์</span>' +
                        '    <b id="nav_counter_' + groupKey + '" style="font-size:13.5px; color:#059669; font-weight:900;">1 / ' + total + '</b>' +
                        '  </div>' +
                        '  <button type="button" class="unit-nav-bar-btn" data-group="' + groupKey + '" onclick="window.stepMultiUnitSlide(this.dataset.group, 1, ' + total + ')" title="ดูทรัพย์ถัดไป">ถัดไป <i class="fa-solid fa-chevron-right" style="color:#059669;"></i></button>' +
                        '</div>';
                }}

                var compareTableHTML = '<div id="table_view_' + groupKey + '" style="display:none; margin-top:6px;">' +
                    '<div style="max-height:180px; overflow-y:auto; background:#ffffff; border-radius:9px; border:1px solid #e2e8f0;">' +
                    '<table style="width:100%; border-collapse:collapse; font-size:12px; text-align:left;">' +
                    '<thead><tr style="background:#f8fafc; color:#475569; border-bottom:1px solid #e2e8f0;"><th style="padding:6px 8px;">บริษัท</th><th style="padding:6px 8px;">รหัส</th><th style="padding:6px 8px;">ราคา</th><th style="padding:6px 8px;">พื้นที่</th><th style="padding:6px 8px; text-align:right;">การกระทำ</th></tr></thead>' +
                    '<tbody>' + tableRowsHTML + '</tbody>' +
                    '</table>' +
                    '</div>' +
                    '</div>';

                var toggleBtnHTML = '<button type="button" class="view-toggle-btn" data-group="' + groupKey + '" data-total="' + total + '" onclick="window.toggleMultiUnitView(this.dataset.group, parseInt(this.dataset.total))" id="btn_toggle_' + groupKey + '"><i class="fa-solid fa-table-list" style="margin-right:4px;"></i>สลับดูตารางเปรียบเทียบยูนิต (' + total + ' รายการ)</button>';

                var totalDisplay = (group.items.length > 0 && group.items[0].coord_total) ? group.items[0].coord_total : total;
                var isGroupCentroid = group.items.some(function(item) {{ return Boolean(item.is_centroid); }});
                var centroidBadgeHeader = isGroupCentroid ? '<span style="background:#fef3c7; border:1px solid #fde68a; color:#92400e; font-size:11.5px; padding:1.5px 7px; border-radius:6px; font-weight:800; margin-left:5px; vertical-align:middle;"><i class="fa-solid fa-triangle-exclamation"></i> พิกัดกึ่งกลาง</span>' : '';

                var mainActionsHTML = '<div style="margin-bottom:10px;">' +
                    '  <button type="button" data-coord="' + grpLatStr + ',' + grpLonStr + '" onclick="window.copyCoordBtn(this)" style="width:100%; background:#f8fafc; border:1.5px solid #cbd5e1; color:#334155; padding:8px 10px; border-radius:8px; font-size:13px; font-weight:700; cursor:pointer; display:flex; align-items:center; justify-content:center; gap:5px; box-shadow:0 1px 3px rgba(0,0,0,0.05); transition:all 0.15s ease;"><i class="fa-regular fa-copy"></i> คัดลอกพิกัด</button>' +
                    '</div>';

                return '<div class="multi-unit-popup" style="min-width:340px; max-width:390px;">' +
                    '<div class="multi-popup-header" style="margin-bottom:8px; padding-bottom:6px; border-bottom:1px solid #e2e8f0;">' +
                    '  <div style="font-weight:800; font-size:14.5px; color:#0f172a;"><i class="fa-solid fa-building" style="color:#059669; margin-right:4px;"></i>พิกัดนี้พบ ' + totalDisplay + ' ทรัพย์สิน ' + centroidBadgeHeader + ' <span style="font-weight:500; font-size:12.5px; color:#64748b;">(' + companiesInGroup.join(', ') + ')</span></div>' +
                    '  <div style="font-size:11px; color:#059669; font-weight:700; margin-top:2px;"><i class="fa-solid fa-arrow-down-short-wide" style="margin-right:3px;"></i>เรียงจากราคาเสนอขาย / ราคาต่อหน่วยต่ำสุดขึ้นก่อน</div>' +
                    '</div>' +
                    mainActionsHTML +
                    tabsHTML +
                    cardsHTML +
                    navBarHTML +
                    compareTableHTML +
                    toggleBtnHTML +
                    '</div>';
            }}

            // Tab switcher function exposed to window
            window.switchMultiUnitTab = function(groupKey, targetIdx) {{
                var cardView = document.getElementById('card_view_' + groupKey);
                var tableView = document.getElementById('table_view_' + groupKey);
                var toggleBtn = document.getElementById('btn_toggle_' + groupKey);
                var navBar = document.getElementById('nav_bar_' + groupKey);
                
                // Ensure card view is visible
                if (cardView) cardView.style.display = 'block';
                if (tableView) tableView.style.display = 'none';
                if (navBar) navBar.style.display = 'flex';
                if (toggleBtn) toggleBtn.innerHTML = '<i class="fa-solid fa-table-list" style="margin-right:4px;"></i>สลับดูตารางเปรียบเทียบทุกยูนิต';

                var tabs = document.querySelectorAll('[id^="tab_' + groupKey + '_"]');
                tabs.forEach(function(t) {{ t.classList.remove('active'); }});
                
                var slides = document.querySelectorAll('[id^="slide_' + groupKey + '_"]');
                slides.forEach(function(s) {{ s.style.display = 'none'; }});
                
                var targetTab = document.getElementById('tab_' + groupKey + '_' + targetIdx);
                if (targetTab) {{
                    targetTab.classList.add('active');
                    try {{
                        targetTab.scrollIntoView({{ behavior: 'smooth', block: 'nearest', inline: 'center' }});
                    }} catch(e) {{}}
                }}
                
                var targetSlide = document.getElementById('slide_' + groupKey + '_' + targetIdx);
                if (targetSlide) targetSlide.style.display = 'block';

                var counterEl = document.getElementById('nav_counter_' + groupKey);
                if (counterEl) {{
                    var total = slides.length;
                    counterEl.textContent = (targetIdx + 1) + ' / ' + total;
                }}
            }};

            // Step function to go prev / next (+1 or -1)
            window.stepMultiUnitSlide = function(groupKey, delta, total) {{
                var currentIdx = 0;
                var activeTab = document.querySelector('[id^="tab_' + groupKey + '_"].active');
                if (activeTab && activeTab.dataset.idx !== undefined) {{
                    currentIdx = parseInt(activeTab.dataset.idx, 10);
                }}
                var nextIdx = currentIdx + delta;
                if (nextIdx < 0) {{
                    nextIdx = total - 1;
                }} else if (nextIdx >= total) {{
                    nextIdx = 0;
                }}
                window.switchMultiUnitTab(groupKey, nextIdx);
            }};

            // View toggle function exposed to window
            window.toggleMultiUnitView = function(groupKey, total) {{
                var cardView = document.getElementById('card_view_' + groupKey);
                var tableView = document.getElementById('table_view_' + groupKey);
                var toggleBtn = document.getElementById('btn_toggle_' + groupKey);
                var navBar = document.getElementById('nav_bar_' + groupKey);
                if (!cardView || !tableView) return;

                if (tableView.style.display === 'none' || tableView.style.display === '') {{
                    cardView.style.display = 'none';
                    tableView.style.display = 'block';
                    if (navBar) navBar.style.display = 'none';
                    if (toggleBtn) toggleBtn.innerHTML = '<i class="fa-regular fa-id-card" style="margin-right:4px;"></i>สลับกลับมาดูการ์ดรายยูนิต';
                }} else {{
                    cardView.style.display = 'block';
                    tableView.style.display = 'none';
                    if (navBar) navBar.style.display = 'flex';
                    if (toggleBtn) toggleBtn.innerHTML = '<i class="fa-solid fa-table-list" style="margin-right:4px;"></i>สลับดูตารางเปรียบเทียบยูนิต (' + total + ' รายการ)';
                }}
            }};

            // 3. Group Properties by Coordinates (Exact same lat/lon)
            var coordGroups = {{}};
            properties.forEach(function(p) {{
                if (!p.lat || !p.lon) return;
                var key = parseFloat(p.lat).toFixed(5) + '_' + parseFloat(p.lon).toFixed(5);
                if (!coordGroups[key]) {{
                    coordGroups[key] = {{
                        key: key,
                        lat: parseFloat(p.lat),
                        lon: parseFloat(p.lon),
                        items: []
                    }};
                }}
                coordGroups[key].items.push(p);

                // Track legend stats for all items
                var comp = p.company || 'BAM';
                var pType = p.type || 'อื่นๆ';
                var rawP = parseRawPrice(p.price);
                if (colorMode === "property_type") {{
                    legendStats[pType] = (legendStats[pType] || 0) + 1;
                }} else if (colorMode === "price_level") {{
                    var priceTier = rawP < 1000000 ? "< 1M" : (rawP < 3000000 ? "1M - 3M" : (rawP < 5000000 ? "3M - 5M" : (rawP < 10000000 ? "5M - 10M" : (rawP < 20000000 ? "10M - 20M" : "> 20M"))));
                    legendStats[priceTier] = (legendStats[priceTier] || 0) + 1;
                }} else {{
                    legendStats[comp] = (legendStats[comp] || 0) + 1;
                }}
            }});

            // 3.1 Sort each coordinate group: lowest offering price first, then lowest unit price first (น้อยไปมาก)
            for (var grpKey in coordGroups) {{
                coordGroups[grpKey].items.sort(function(a, b) {{
                    var pA = (typeof a.raw_price === 'number' && a.raw_price > 0) ? a.raw_price : parseRawPrice(a.price);
                    var pB = (typeof b.raw_price === 'number' && b.raw_price > 0) ? b.raw_price : parseRawPrice(b.price);
                    var vPA = (pA > 0) ? pA : Infinity;
                    var vPB = (pB > 0) ? pB : Infinity;
                    if (vPA !== vPB) return vPA - vPB;

                    var uA = (typeof a.raw_unit_price === 'number' && a.raw_unit_price > 0) ? a.raw_unit_price : parseRawPrice(a.unit_price || a.price_per_wah || a.price_per_sqm);
                    var uB = (typeof b.raw_unit_price === 'number' && b.raw_unit_price > 0) ? b.raw_unit_price : parseRawPrice(b.unit_price || b.price_per_wah || b.price_per_sqm);
                    var vUA = (uA > 0) ? uA : Infinity;
                    var vUB = (uB > 0) ? uB : Infinity;
                    return vUA - vUB;
                }});
            }}

            // 4. Render Markers for each coordinate group
            for (var k in coordGroups) {{
                (function(group) {{
                    var count = group.items.length;
                    var displayCount = (group.items.length > 0 && group.items[0].coord_total) ? group.items[0].coord_total : count;
                    var isGroupCentroid = group.items.some(function(it) {{ return Boolean(it.is_centroid); }});
                    if (displayCount === 1) {{
                        var p = group.items[0];
                        var markerIcon = createPropertyIcon(p, isGroupCentroid);
                        var marker = L.marker([group.lat, group.lon], {{ icon: markerIcon }}).addTo(map);
                        
                        var popupContent = buildItemDetailHTML(p, 0, 1);
                        marker.bindPopup(popupContent, {{ maxWidth: 390 }});

                        var locStr = [p.subdist, p.district, p.province].filter(Boolean).join(', ');
                        var tooltipContent = '<div style="font-size:12px; line-height:1.4;">' +
                            '<b style="color:#059669;">' + (p.name || 'ทรัพย์สิน') + (isGroupCentroid ? ' (พิกัดกึ่งกลาง)' : '') + '</b><br/>' +
                            '<b>' + (p.company || '-') + '</b> | ' + (p.type || '-') + '<br/>' +
                            '<b style="color:#15803d;">' + (p.price || '-') + '</b> | ' + (p.dist || '-') +
                            (locStr ? '<br/><span style="color:#64748b;">' + locStr + '</span>' : '') +
                            '</div>';
                        marker.bindTooltip(tooltipContent, {{ direction: 'top', offset: [0, -17] }});
                    }} else {{
                        // Multi-Asset Point (> 1 item at exact same coordinate)
                        var uniqueComps = [];
                        group.items.forEach(function(item) {{
                            if (item.company && uniqueComps.indexOf(item.company) === -1) {{
                                uniqueComps.push(item.company);
                            }}
                        }});

                        var primaryComp = group.items[0].company || 'SAM';
                        var primaryLogo = getCompanyLogo(primaryComp);
                        var cColor = companyColors[primaryComp] || '#2563eb';
                        var pinBorderColor = isGroupCentroid ? '#f59e0b' : cColor;
                        
                        var logoImgHtml = primaryLogo ? '<img src="' + primaryLogo + '" alt="' + primaryComp + '" />' : '<span style="font-weight:800; font-size:11px; color:#0f172a;">' + primaryComp.substring(0,3) + '</span>';

                        var badgeClass = isGroupCentroid ? 'cluster-badge-count centroid-badge' : 'cluster-badge-count';
                        var badgeStyle = isGroupCentroid ? 'style="background:linear-gradient(135deg, #f59e0b 0%, #d97706 100%); color:#ffffff; border-color:#ffffff; font-weight:900; box-shadow:0 2px 8px rgba(217,119,6,0.6); white-space:nowrap !important;"' : 'style="white-space:nowrap !important;"';
                        var badgeText = isGroupCentroid ? (displayCount + '<span style="font-weight:900; margin-left:1.5px;">!</span>') : displayCount;

                        var clusterIconHTML = '<div class="logo-marker-pin" style="border-color:' + pinBorderColor + '; width:38px; height:38px;">' +
                            logoImgHtml +
                            '<span class="' + badgeClass + '" ' + badgeStyle + '>' + badgeText + '</span>' +
                            '</div>';

                        var clusterIcon = L.divIcon({{
                            className: 'custom-cluster-icon',
                            html: clusterIconHTML,
                            iconSize: [38, 38],
                            iconAnchor: [19, 19],
                            popupAnchor: [0, -19]
                        }});

                        var clusterMarker = L.marker([group.lat, group.lon], {{ icon: clusterIcon }}).addTo(map);

                        // Bind Multi-Unit Interactive Popup
                        var multiPopupHTML = buildMultiUnitPopupHTML(group);
                        clusterMarker.bindPopup(multiPopupHTML, {{ maxWidth: 410 }});

                        var clusterTooltip = '<div style="font-size:12px; line-height:1.4;">' +
                            '<b style="color:#059669;">พิกัดนี้มี ' + displayCount + ' ทรัพย์สิน' + (isGroupCentroid ? ' (พิกัดกึ่งกลาง)' : '') + '</b><br/>' +
                            'สถาบัน: <b>' + uniqueComps.join(', ') + '</b><br/>' +
                            '<span style="color:#64748b; font-size:10.5px;">คลิกเพื่อดูรายละเอียดและตารางเปรียบเทียบยูนิต</span>' +
                            '</div>';
                        clusterMarker.bindTooltip(clusterTooltip, {{ direction: 'top', offset: [0, -19] }});
                    }}
                }})(coordGroups[k]);
            }}

            // 5. Add Dynamic Map Legend Control
            var legendControl = L.control({{ position: 'bottomright' }});
            legendControl.onAdd = function(map) {{
                var div = L.DomUtil.create('div', 'map-legend-box');
                var titleText = colorMode === "property_type" ? "ประเภททรัพย์" : (colorMode === "price_level" ? "ระดับราคา" : "บริษัททรัพย์สิน");
                var html = '<div class="map-legend-title">' + titleText + ' (พบในรัศมี)</div>';

                var priceColorsMap = {{
                    "< 1M": "#10b981", "1M - 3M": "#06b6d4", "3M - 5M": "#3b82f6",
                    "5M - 10M": "#f59e0b", "10M - 20M": "#f97316", "> 20M": "#ef4444"
                }};

                var customLegendStats = {legend_stats_json};
                var activeStats = (customLegendStats && Object.keys(customLegendStats).length > 0) ? customLegendStats : legendStats;

                for (var key in activeStats) {{
                    var dotColor = "#64748b";
                    if (colorMode === "property_type") {{
                        dotColor = propTypeColors[key] || "#64748b";
                    }} else if (colorMode === "price_level") {{
                        dotColor = priceColorsMap[key] || "#64748b";
                    }} else {{
                        dotColor = companyColors[key] || "#64748b";
                    }}
                    var countVal = activeStats[key];
                    var countFmt = typeof countVal === 'number' ? countVal.toLocaleString() : countVal;
                    html += '<div class="map-legend-item">' +
                        '<span class="map-legend-color" style="background:' + dotColor + ';"></span>' +
                        '<span><b>' + key + '</b> (' + countFmt + ')</span>' +
                        '</div>';
                }}
                div.innerHTML = html;
                return div;
            }};
            legendControl.addTo(map);

            // Auto-fit view to radius circle with padding
            var group = new L.featureGroup([radiusCircle]);
            map.fitBounds(group.getBounds(), {{ padding: [30, 30] }});

            // Ensure Leaflet recalculates dimensions immediately to avoid blank iframe issues
            setTimeout(function() {{
                map.invalidateSize();
            }}, 250);
            window.addEventListener('resize', function() {{
                map.invalidateSize();
            }});
        </script>
    </body>
    </html>
    """
    return html

def get_latest_parquet_path():
    candidates = list(Path(".").glob("all_assets_*.parquet"))
    dated = [p for p in candidates if not p.name.endswith("_no_centroid.parquet") and re.match(r'^all_assets_\d{4}_\d{2}_\d{2}\.parquet$', p.name)]
    if dated:
        dated.sort(key=lambda p: (p.name, p.stat().st_mtime), reverse=True)
        return dated[0]
    return Path("all_assets.parquet")

def get_data_mtime():
    p = get_latest_parquet_path()
    if p.exists():
        return p.stat().st_mtime
    p_fallback = Path("all_assets.parquet")
    if p_fallback.exists():
        return p_fallback.stat().st_mtime
    return 0

def ensure_derived_cols(df):
    if df is None or df.empty:
        return df

    if 'ประเภททรัพย์' in df.columns:
        prop_type_map = {
            # 1. หมวดบ้านเดี่ยว
            "บ้าน": "บ้านเดี่ยว",
            "บ้านครึ่งตึกครึ่งไม้": "บ้านเดี่ยว",
            "บ้านพร้อมกิจการ": "บ้านเดี่ยว",
            "Detached House": "บ้านเดี่ยว",
            "Single House": "บ้านเดี่ยว",
            "House": "บ้านเดี่ยว",
            
            # 2. หมวดคอนโดมิเนียม / ห้องชุด
            "คอนโด": "ห้องชุดพักอาศัย",
            "คอนโดมิเนียม": "ห้องชุดพักอาศัย",
            "ห้องชุด": "ห้องชุดพักอาศัย",
            "ห้องชุด/คอนโดมิเนียม": "ห้องชุดพักอาศัย",
            "ห้องชุด/ตอนโดมิเนียม": "ห้องชุดพักอาศัย",
            "คอนโดมิเนียม/อาคารชุด": "ห้องชุดพักอาศัย",
            "คอนโด/อาคารชุด/ห้องชุด": "ห้องชุดพักอาศัย",
            "Condo": "ห้องชุดพักอาศัย",
            "Condominium": "ห้องชุดพักอาศัย",
            "Penthouse": "ห้องชุดพักอาศัย",
            "Duplex": "ห้องชุดพักอาศัย",
            
            # 3. หมวดทาวน์เฮ้าส์ / ทาวน์โฮม
            "ทาวน์โฮม": "ทาวน์เฮ้าส์",
            "ทาวน์เฮาส์": "ทาวน์เฮ้าส์",
            "Townhouse": "ทาวน์เฮ้าส์",
            "Townhome": "ทาวน์เฮ้าส์",
            "Town House": "ทาวน์เฮ้าส์",
            "Town Home": "ทาวน์เฮ้าส์",
            
            # 4. หมวดที่ดิน
            "ที่ดิน": "ที่ดินเปล่า",
            "ที่ดินเปล่า": "ที่ดินเปล่า",
            "ที่ดินเกษตรกรรม": "ที่ดินเปล่า",
            "ที่ดินว่างเปล่า": "ที่ดินเปล่า",
            "ที่ดินพร้อมสิ่งปลูกสร้าง": "ที่ดินพร้อมสิ่งปลูกสร้าง",
            "สวนเกษตร": "ที่ดินเปล่า",
            "Land": "ที่ดินเปล่า",
            "Land with Building": "ที่ดินพร้อมสิ่งปลูกสร้าง",
            "Land with Buildings": "ที่ดินพร้อมสิ่งปลูกสร้าง",
            
            # 5. หมวดบ้านแฝด
            "บ้านแฝด": "บ้านแฝด",
            "Semi-Detached House (Twin House)": "บ้านแฝด",
            "Semi-Detached House": "บ้านแฝด",
            "Semi-detached House": "บ้านแฝด",
            "Twin House": "บ้านแฝด",
            
            # 6. หมวดวิลล่า
            "วิลล่า": "วิลล่า",
            "Villa": "วิลล่า",
            "Pool Villa": "วิลล่า",
            
            # 7. หมวดโรงงาน / โกดัง
            "โรงงาน": "โรงงาน/โกดัง",
            "โกดัง": "โรงงาน/โกดัง",
            "อาคารโรงงาน": "โรงงาน/โกดัง",
            "โกดัง/โรงงาน": "โรงงาน/โกดัง",
            "โกดัง / โรงงาน": "โรงงาน/โกดัง",
            "มินิแฟคตอรี่": "โรงงาน/โกดัง",
            "โรงสี": "โรงงาน/โกดัง",
            "Factory": "โรงงาน/โกดัง",
            "Warehouse": "โรงงาน/โกดัง",
            "Mini Factory": "โรงงาน/โกดัง",
            
            # 8. หมวดอพาร์ทเมนท์ / หอพัก
            "อพาร์ทเม้นท์": "อพาร์ทเมนท์",
            "อพาร์ตเมนต์": "อพาร์ทเมนท์",
            "อพาตเมนต์": "อพาร์ทเมนท์",
            "หอพัก": "อพาร์ทเมนท์",
            "หอพัก/อพาร์ทเมนท์": "อพาร์ทเมนท์",
            "อพาร์ทเม้นท์/หอพัก": "อพาร์ทเมนท์",
            "แฟลต": "อพาร์ทเมนท์",
            "อาคารพักอาศัย": "อพาร์ทเมนท์",
            "Apartment": "อพาร์ทเมนท์",
            "Dormitory": "อพาร์ทเมนท์",
            "Flat": "อพาร์ทเมนท์",
            
            # 9. หมวดอาคารพาณิชย์ / ตึกแถว / ร้านค้า
            "ตึกแถว": "อาคารพาณิชย์",
            "ห้องแถว": "อาคารพาณิชย์",
            "ร้านค้า": "อาคารพาณิชย์",
            "ร้านอาหาร": "อาคารพาณิชย์",
            "ตลาดสด": "อาคารพาณิชย์",
            "ศูนย์จำหน่ายสินค้า": "อาคารพาณิชย์",
            "ห้างสรรพสินค้า": "อาคารพาณิชย์",
            "โชว์รูม": "อาคารพาณิชย์",
            "Commercial Property": "อาคารพาณิชย์",
            "Commercial Space": "อาคารพาณิชย์",
            "Commercial Building": "อาคารพาณิชย์",
            "Shophouse": "อาคารพาณิชย์",
            "Shop House": "อาคารพาณิชย์",
            "Retail": "อาคารพาณิชย์",
            "Showroom": "อาคารพาณิชย์",
            
            # 10. หมวดสำนักงาน
            "สำนักงาน": "อาคารสำนักงาน",
            "โฮมออฟฟิศ": "อาคารสำนักงาน",
            "อาคารที่ทำการสาขา": "อาคารสำนักงาน",
            "ห้องชุดสำนักงาน": "ห้องชุดพาณิชยกรรม/สำนักงาน",
            "ห้องชุดพาณิชยกรรม": "ห้องชุดพาณิชยกรรม/สำนักงาน",
            "Office": "อาคารสำนักงาน",
            "Office Building": "อาคารสำนักงาน",
            "Home Office": "อาคารสำนักงาน",
            
            # 11. หมวดโรงแรม / รีสอร์ท
            "Hotel Building": "โรงแรม/รีสอร์ท",
            "โรงแรม": "โรงแรม/รีสอร์ท",
            "รีสอร์ท": "โรงแรม/รีสอร์ท",
            "Hotel": "โรงแรม/รีสอร์ท",
            "Resort": "โรงแรม/รีสอร์ท",
            
            # 12. หมวดสังหาริมทรัพย์ & อื่นๆ
            "เครื่องจักร": "สังหาริมทรัพย์",
            "บัตรสมาชิกสนามกอล์ฟ": "สังหาริมทรัพย์",
            "ส่วนโล่งหลังคาคลุม": "อื่นๆ",
            "ฟาร์มเลี้ยงสัตว์": "ฟาร์ม",
            "สถานีบริการน้ำมัน": "ปั๊มน้ำมัน",
            "ศูนย์บริการ/โชว์รูม/ปั้มน้ำมัน": "ปั๊มน้ำมัน",
            "โรงภาพยนต์": "อื่นๆ",
            "สวนน้ำ": "อื่นๆ",
            "โรงพยาบาล": "อื่นๆ",
            "อาคารจอดรถ": "อื่นๆ",
            "บ้านพักคนงาน": "อื่นๆ",
            "อาคาร": "อื่นๆ",
            "Public Service": "อื่นๆ",
            "โครงการที่พักอาศัย/พาณิชยกรรม": "อื่นๆ",
            "อสังหาริมทรัพย์อื่นๆ": "อื่นๆ",
        }
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
        
        # Resolve any mixed types (e.g. บ้านเดี่ยว/ทาวน์เฮาส์) based on title/project name
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
        sale_map = {
            # ขายทอดตลาด (ปลอดจำนอง)
            'ปลอดการจำนอง': 'ขายทอดตลาด (ปลอดจำนอง)',
            'ไม่มีภาระจำนอง': 'ขายทอดตลาด (ปลอดจำนอง)',
            'ปลอดภาระผูกพัน': 'ขายทอดตลาด (ปลอดจำนอง)',
            'ไม่มีภาระจำนำ': 'ขายทอดตลาด (ปลอดจำนอง)',
            'ประมูล': 'ขายทอดตลาด (ปลอดจำนอง)',
            
            # ขายทอดตลาด (จำนองติดไป)
            'การจำนองติดไป': 'ขายทอดตลาด (จำนองติดไป)',
            'การจำนำติดไป': 'ขายทอดตลาด (จำนองติดไป)',
            
            # ขายตรง
            'ซื้อตรง': 'ขาย',
            'ทรัพย์ธนาคาร': 'ขาย',
            'ทรัพย์โปรโมชั่นราคาพิเศษ': 'ขาย',
            'ทรัพย์โปรโมชันราคาพิเศษ': 'ขาย',
            'โปรโมชั่น': 'ขาย',
            'โปรโมชัน': 'ขาย',
            'ทรัพย์ฝากขาย': 'ขาย',
            'ฝากขาย': 'ขาย',
            'ขายดาวน์': 'ขาย',
            'ขาย/เช่า': 'ขาย',
        }
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
            import urllib.parse
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

    # Ensure 'อำเภอ' and 'ตำบล' are 100% Thai without any English characters or trailing punctuation
    if 'อำเภอ' in df.columns:
        df['อำเภอ'] = df['อำเภอ'].astype(str).str.strip().str.strip(" ,;.-'\"/\\")
        df['อำเภอ'] = df['อำเภอ'].replace({'nan': np.nan, 'None': np.nan, '<NA>': np.nan, '-': np.nan, '': np.nan})
        en_amp_mask = df['อำเภอ'].astype(str).str.contains(r'[a-zA-Z]', regex=True, na=False)
        if en_amp_mask.any():
            try:
                base_dir = os.path.dirname(os.path.abspath(__file__))
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

# Cached function to load data – strictly parquet only for maximum speed
@st.cache_data(ttl=3600, show_spinner="กำลังโหลดฐานข้อมูลทรัพย์สิน (Parquet)...")
def load_properties_data(data_version=0):
    parquet_file = get_latest_parquet_path()
    if not parquet_file.exists():
        parquet_file = Path("all_assets.parquet")
    
    if not parquet_file.exists():
        st.error("ไม่พบไฟล์ข้อมูล 'all_assets.parquet' กรุณารันสคริปต์ convert_csv_to_parquet.py เพื่อสร้างไฟล์")
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
def get_official_gis_reference():
    gis_candidates = [
        os.path.join(os.path.dirname(__file__), "references", "thailand_provinces_districts_subdistricts.json"),
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "references", "thailand_provinces_districts_subdistricts.json"),
        os.path.join(os.getcwd(), "references", "thailand_provinces_districts_subdistricts.json")
    ]
    gis_path = next((p for p in gis_candidates if os.path.exists(p)), None)
    if not gis_path:
        return set(), set(), set()
    try:
        with open(gis_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        pairs = {(item['อำเภอ/เขต (ไทย)'].strip(), item['จังหวัด (ไทย)'].strip()) for item in data if 'อำเภอ/เขต (ไทย)' in item and 'จังหวัด (ไทย)' in item}
        provs = {item['จังหวัด (ไทย)'].strip() for item in data if 'จังหวัด (ไทย)' in item}
        dists = {item['อำเภอ/เขต (ไทย)'].strip() for item in data if 'อำเภอ/เขต (ไทย)' in item}
        return pairs, provs, dists
    except Exception:
        return set(), set(), set()

INVALID_LOC_VALUES = {"", "nan", "none", "null", "undefined", "-", "ไม่มีข้อมูล", "ไม่ระบุ"}

@st.cache_data(show_spinner=False)
def get_sam_project_options(_df):
    """Pre-computes and caches list of SAM projects and their unit counts across all companies."""
    if _df is None or _df.empty or 'ชื่อโครงการ' not in _df.columns or 'บริษัท' not in _df.columns:
        return [], {}
    sam_mask = _df['บริษัท'] == 'SAM'
    sam_projs = set(_df[sam_mask]['ชื่อโครงการ'].dropna().astype(str).str.strip())
    sam_projs = {p for p in sam_projs if p and p not in ['-', 'ไม่มีชื่อ', 'nan', 'None']}
    
    valid_df = _df[_df['ชื่อโครงการ'].astype(str).str.strip().isin(sam_projs)]
    sam_cnt = valid_df[valid_df['บริษัท'] == 'SAM']['ชื่อโครงการ'].astype(str).str.strip().value_counts()
    other_cnt = valid_df[valid_df['บริษัท'] != 'SAM']['ชื่อโครงการ'].astype(str).str.strip().value_counts()
    
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
            # Enforce official GIS pairing if available
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

    # Pre-compute subdistrict lookup per (province, district) key
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

fragment_decorator = getattr(st, "fragment", getattr(st, "experimental_fragment", None))
if fragment_decorator is None:
    def fragment_decorator(func):
        return func

def get_base_map_html(_mtime=None):
    try:
        with open("static/map_template.html", "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return ""

@fragment_decorator
def render_tab2_reference_analytics_fragment(
    df_raw,
    is_dark_mode,
    active_ref_lat,
    active_ref_lon,
    active_ref_prop,
    active_ref_radius,
    tab2_types=None
):
    # 0. Hidden synchronization bridge between map iframe and Streamlit
    st.markdown("""
    <style>
    /* Position sync button and bridge input offscreen while remaining active and clickable via JS */
    .st-key-btn_map_filter_sync,
    div[data-testid="stElementContainer"]:has(.st-key-btn_map_filter_sync),
    div[data-testid="stButton"]:has(.st-key-btn_map_filter_sync),
    .st-key-map_sync_bridge_payload,
    div[data-testid="stElementContainer"]:has(.st-key-map_sync_bridge_payload),
    div[data-testid="stTextInput"]:has(.st-key-map_sync_bridge_payload) {
        position: fixed !important;
        bottom: -9999px !important;
        right: -9999px !important;
        opacity: 0 !important;
        z-index: -9999 !important;
    }
    </style>
    <div id="map-sync-anchor" style="position:fixed; bottom:-9999px; right:-9999px;"></div>
    """, unsafe_allow_html=True)
    
    sync_bridge_val = st.text_input("map_sync_bridge", key="map_sync_bridge_payload", label_visibility="collapsed")
    sync_btn_clicked = st.button("sync_map_filter", key="btn_map_filter_sync")
    
    if sync_bridge_val or sync_btn_clicked:
        payload_obj = None
        if sync_bridge_val and str(sync_bridge_val).strip():
            try:
                payload_obj = json.loads(str(sync_bridge_val).strip())
            except Exception:
                pass

        if payload_obj and isinstance(payload_obj, dict):
            p_prov = str(payload_obj.get("prov", "")).strip()
            if p_prov and p_prov not in ["ALL", "__ALL__", "all", "-"]:
                st.session_state["tab2_filter_provinces"] = [p_prov]
                st.query_params["map_prov"] = p_prov
            elif "prov" in payload_obj:
                st.session_state["tab2_filter_provinces"] = []
                st.query_params.pop("map_prov", None)

            p_dist = str(payload_obj.get("dist", "")).strip()
            if p_dist and p_dist not in ["ALL", "__ALL__", "all", "-"]:
                st.session_state["tab2_filter_districts"] = [p_dist]
                st.query_params["map_dist"] = p_dist
            elif "dist" in payload_obj:
                st.session_state["tab2_filter_districts"] = []
                st.query_params.pop("map_dist", None)

            p_subdist = str(payload_obj.get("subdist", "")).strip()
            if p_subdist and p_subdist not in ["ALL", "__ALL__", "all", "-"]:
                st.session_state["tab2_filter_subdistricts"] = [p_subdist]
                st.query_params["map_subdist"] = p_subdist
            elif "subdist" in payload_obj:
                st.session_state["tab2_filter_subdistricts"] = []
                st.query_params.pop("map_subdist", None)

            p_id = str(payload_obj.get("id", "")).strip()
            if p_id:
                st.session_state["tab2_search_prop_id"] = p_id
                st.query_params["map_ref_id"] = p_id
                if df_raw is not None and not df_raw.empty:
                    m = df_raw[df_raw['รหัสทรัพย์'].astype(str).str.strip().str.lower() == p_id.lower()]
                    if not m.empty:
                        active_ref_prop = m.iloc[0].to_dict()
                        st.session_state["tab2_ref_prop"] = active_ref_prop
                        prop_p = str(active_ref_prop.get('จังหวัด', '')).strip()
                        prop_d = str(active_ref_prop.get('อำเภอ', '')).strip()
                        prop_s = str(active_ref_prop.get('ตำบล', '')).strip()
                        if prop_p and prop_p not in ['-', 'ไม่มีข้อมูล', 'nan']:
                            st.session_state["tab2_filter_provinces"] = [prop_p]
                            st.query_params["map_prov"] = prop_p
                        if prop_d and prop_d not in ['-', 'ไม่มีข้อมูล', 'nan']:
                            st.session_state["tab2_filter_districts"] = [prop_d]
                            st.query_params["map_dist"] = prop_d
                        if prop_s and prop_s not in ['-', 'ไม่มีข้อมูล', 'nan']:
                            st.session_state["tab2_filter_subdistricts"] = [prop_s]
                            st.query_params["map_subdist"] = prop_s

            p_lat = payload_obj.get("lat")
            p_lon = payload_obj.get("lon")
            if p_lat and p_lon:
                try:
                    active_ref_lat = float(p_lat)
                    active_ref_lon = float(p_lon)
                    st.session_state["tab2_ref_lat"] = active_ref_lat
                    st.session_state["tab2_ref_lon"] = active_ref_lon
                except (ValueError, TypeError):
                    pass

            p_rad = payload_obj.get("radius")
            if p_rad:
                try:
                    active_ref_radius = float(p_rad)
                    st.session_state["tab2_ref_radius"] = active_ref_radius
                except (ValueError, TypeError):
                    pass

            p_mode = payload_obj.get("mode")
            if p_mode:
                st.session_state["tab2_pin_mode"] = str(p_mode).strip()

            if payload_obj.get("compare_active", True):
                st.session_state["tab2_compared_active"] = True

        else:
            q_prov = st.query_params.get("map_prov", None)
            if q_prov is not None:
                q_p = str(q_prov).strip()
                if q_p and q_p not in ["ALL", "__ALL__", "all"]:
                    st.session_state["tab2_filter_provinces"] = [q_p]
                else:
                    st.session_state["tab2_filter_provinces"] = []

            q_dist = st.query_params.get("map_dist", None)
            if q_dist is not None:
                q_d = str(q_dist).strip()
                if q_d and q_d not in ["ALL", "__ALL__", "all"]:
                    st.session_state["tab2_filter_districts"] = [q_d]
                else:
                    st.session_state["tab2_filter_districts"] = []

            q_subdist = st.query_params.get("map_subdist", None)
            if q_subdist is not None:
                q_s = str(q_subdist).strip()
                if q_s and q_s not in ["ALL", "__ALL__", "all"]:
                    st.session_state["tab2_filter_subdistricts"] = [q_s]
                else:
                    st.session_state["tab2_filter_subdistricts"] = []

            q_lat = st.query_params.get("map_ref_lat")
            q_lon = st.query_params.get("map_ref_lon")
            if q_lat and q_lon:
                try:
                    active_ref_lat = float(q_lat)
                    active_ref_lon = float(q_lon)
                    st.session_state["tab2_ref_lat"] = active_ref_lat
                    st.session_state["tab2_ref_lon"] = active_ref_lon
                    st.session_state["tab2_compared_active"] = True
                except (ValueError, TypeError):
                    pass

            q_id = st.query_params.get("map_ref_id")
            if q_id and df_raw is not None and not df_raw.empty:
                clean_id = str(q_id).strip()
                st.session_state["tab2_search_prop_id"] = clean_id
                f_prop = df_raw[df_raw['รหัสทรัพย์'].astype(str).str.strip().str.lower() == clean_id.lower()]
                if not f_prop.empty:
                    prop_row = f_prop.iloc[0]
                    active_ref_prop = prop_row.to_dict()
                    st.session_state["tab2_ref_prop"] = active_ref_prop
                    r_prov = str(prop_row.get('จังหวัด', '')).strip()
                    r_dist = str(prop_row.get('อำเภอ', '')).strip()
                    r_subdist = str(prop_row.get('ตำบล', '')).strip()
                    if r_prov and r_prov not in ['-', 'ไม่มีข้อมูล', 'nan']:
                        st.session_state["tab2_filter_provinces"] = [r_prov]
                    if r_dist and r_dist not in ['-', 'ไม่มีข้อมูล', 'nan']:
                        st.session_state["tab2_filter_districts"] = [r_dist]
                    if r_subdist and r_subdist not in ['-', 'ไม่มีข้อมูล', 'nan']:
                        st.session_state["tab2_filter_subdistricts"] = [r_subdist]

            # Auto-compare when location filter is synced (province/district/subdistrict selected on map)
            has_loc_synced = (
                (q_prov is not None and str(q_prov).strip() not in ["", "ALL", "__ALL__", "all"]) or
                (q_dist is not None and str(q_dist).strip() not in ["", "ALL", "__ALL__", "all"]) or
                (q_subdist is not None and str(q_subdist).strip() not in ["", "ALL", "__ALL__", "all"]) or
                bool(q_id)
            )
            if has_loc_synced:
                st.session_state["tab2_compared_active"] = True

        try:
            st.rerun(scope="fragment")
        except Exception:
            st.rerun()

    # 1. Recovery of reference coordinates & radius from query_params or session_state
    q_lat_check = st.query_params.get("map_ref_lat")
    if q_lat_check:
        try:
            if float(q_lat_check) > 0 and "map_ref_cleared" in st.query_params:
                del st.query_params["map_ref_cleared"]
        except (ValueError, TypeError):
            pass

    if st.query_params.get("map_ref_cleared") == "1":
        active_ref_lat = 0.0
        active_ref_lon = 0.0
        active_ref_prop = None
        st.session_state["tab2_ref_lat"] = 0.0
        st.session_state["tab2_ref_lon"] = 0.0
        st.session_state["tab2_ref_prop"] = None
        st.session_state["tab2_compared_active"] = False
        try:
            del st.query_params["map_ref_cleared"]
        except Exception:
            pass
    else:
        try:
            q_lat = st.query_params.get("map_ref_lat")
            q_lon = st.query_params.get("map_ref_lon")
            if q_lat and q_lon and float(q_lat) > 0 and float(q_lon) > 0:
                active_ref_lat = float(q_lat)
                active_ref_lon = float(q_lon)
                st.session_state["tab2_ref_lat"] = active_ref_lat
                st.session_state["tab2_ref_lon"] = active_ref_lon
            q_rad = st.query_params.get("map_ref_radius")
            if q_rad and float(q_rad) > 0:
                active_ref_radius = float(q_rad)
        except (ValueError, TypeError):
            pass

    if not active_ref_lat or not active_ref_lon:
        s_lat = st.session_state.get("tab2_ref_lat", 0.0)
        s_lon = st.session_state.get("tab2_ref_lon", 0.0)
        if s_lat > 0 and s_lon > 0:
            active_ref_lat = s_lat
            active_ref_lon = s_lon

    # Auto-resolve active_ref_prop if missing or if query params has map_ref_id
    q_id = st.query_params.get("map_ref_id") or st.session_state.get("tab2_search_prop_id")
    if q_id and df_raw is not None and not df_raw.empty:
        clean_id = str(q_id).strip()
        if active_ref_prop is None or str(active_ref_prop.get('รหัสทรัพย์', '')).strip().lower() != clean_id.lower():
            found = df_raw[df_raw['รหัสทรัพย์'].astype(str).str.strip().str.lower() == clean_id.lower()]
            if not found.empty:
                active_ref_prop = found.iloc[0].to_dict()
                st.session_state["tab2_ref_prop"] = active_ref_prop
                st.session_state["tab2_search_prop_id"] = clean_id
                # Sync found property's location
                p_prov = str(active_ref_prop.get('จังหวัด', '')).strip()
                p_dist = str(active_ref_prop.get('อำเภอ', '')).strip()
                p_subdist = str(active_ref_prop.get('ตำบล', '')).strip()
                if p_prov and p_prov not in ['-', 'ไม่มีข้อมูล', 'nan']:
                    st.session_state["tab2_filter_provinces"] = [p_prov]
                    st.query_params["map_prov"] = p_prov
                if p_dist and p_dist not in ['-', 'ไม่มีข้อมูล', 'nan']:
                    st.session_state["tab2_filter_districts"] = [p_dist]
                    st.query_params["map_dist"] = p_dist
                if p_subdist and p_subdist not in ['-', 'ไม่มีข้อมูล', 'nan']:
                    st.session_state["tab2_filter_subdistricts"] = [p_subdist]
                    st.query_params["map_subdist"] = p_subdist
    elif active_ref_prop is None and active_ref_lat and active_ref_lon and df_raw is not None and not df_raw.empty:
        if 'ละติจูด' in df_raw.columns and 'ลองจิจูด' in df_raw.columns:
            match = df_raw[
                (df_raw['ละติจูด'].sub(active_ref_lat).abs() < 0.0001) &
                (df_raw['ลองจิจูด'].sub(active_ref_lon).abs() < 0.0001)
            ]
            if not match.empty:
                active_ref_prop = match.iloc[0].to_dict()
                st.session_state["tab2_ref_prop"] = active_ref_prop

    # 2. Extract and resolve all current map filters
    q_prov = st.query_params.get("map_prov", None)
    if q_prov and str(q_prov).strip() not in ["ALL", "__ALL__", "all", ""]:
        active_prov = [str(q_prov).strip()]
    else:
        active_prov = st.session_state.get("tab2_filter_provinces", [])

    q_dist = st.query_params.get("map_dist", None)
    if q_dist and str(q_dist).strip() not in ["ALL", "__ALL__", "all", ""]:
        active_dist = [str(q_dist).strip()]
    else:
        active_dist = st.session_state.get("tab2_filter_districts", [])

    q_subdist = st.query_params.get("map_subdist", None)
    if q_subdist and str(q_subdist).strip() not in ["ALL", "__ALL__", "all", ""]:
        active_subdist = [str(q_subdist).strip()]
    else:
        active_subdist = st.session_state.get("tab2_filter_subdistricts", [])

    q_proj = st.query_params.get("map_proj", None)
    active_proj = str(q_proj).strip() if q_proj and str(q_proj).strip() not in ["ALL", "__ALL__", "all", ""] else None

    raw_cos = st.query_params.get("map_filter_cos", "")
    map_cos = [c.strip() for c in raw_cos.split(",") if c.strip()] if raw_cos else []

    raw_types = st.query_params.get("map_filter_types", "")
    map_types = [t.strip() for t in raw_types.split(",") if t.strip()] if raw_types else []

    try:
        map_min_p = float(st.query_params.get("map_filter_min_p", 0))
    except (ValueError, TypeError):
        map_min_p = 0.0

    try:
        map_max_p = float(st.query_params.get("map_filter_max_p", 0))
    except (ValueError, TypeError):
        map_max_p = 0.0

    try:
        map_min_sqw = float(st.query_params.get("map_filter_min_sqw", 0))
    except (ValueError, TypeError):
        map_min_sqw = 0.0

    try:
        map_max_sqw = float(st.query_params.get("map_filter_max_sqw", 0))
    except (ValueError, TypeError):
        map_max_sqw = 0.0

    try:
        map_min_sqm = float(st.query_params.get("map_filter_min_sqm", 0))
    except (ValueError, TypeError):
        map_min_sqm = 0.0

    try:
        map_max_sqm = float(st.query_params.get("map_filter_max_sqm", 0))
    except (ValueError, TypeError):
        map_max_sqm = 0.0

    pin_mode = st.query_params.get("map_pin_mode", "radius")
    has_ref_point = bool(active_ref_lat and active_ref_lon and float(active_ref_lat) > 0 and float(active_ref_lon) > 0)
    has_loc_filter = bool(active_prov or active_dist or active_subdist or active_proj)

    # 3. Compute matching count and summary labels for Filter Status Bar
    status_df = df_raw.copy() if df_raw is not None else pd.DataFrame()
    if not status_df.empty:
        if has_ref_point and pin_mode == 'radius':
            status_df = find_nearby_properties(active_ref_lat, active_ref_lon, status_df, active_ref_radius)
        else:
            if active_prov and 'จังหวัด' in status_df.columns:
                status_df = status_df[status_df['จังหวัด'].astype(str).str.strip().isin(active_prov)]
            if active_dist and 'อำเภอ' in status_df.columns:
                clean_target_dists = [d.split(' (')[0].strip() for d in active_dist]
                status_df = status_df[status_df['อำเภอ'].astype(str).str.strip().isin(clean_target_dists)]
            if active_subdist and 'ตำบล' in status_df.columns:
                clean_target_subs = [s.split(' (')[0].strip() for s in active_subdist]
                status_df = status_df[status_df['ตำบล'].astype(str).str.strip().isin(clean_target_subs)]
            if active_proj and 'ชื่อโครงการ' in status_df.columns:
                p_list = [p.strip() for p in active_proj.split(",") if p.strip()]
                status_df = status_df[status_df['ชื่อโครงการ'].astype(str).str.strip().isin(p_list)]

        if map_cos and 'บริษัท' in status_df.columns:
            status_df = status_df[status_df['บริษัท'].isin(map_cos)]
        if map_types and 'ประเภททรัพย์' in status_df.columns:
            status_df = status_df[status_df['ประเภททรัพย์'].isin(map_types)]
        if map_min_p > 0 and 'ราคา' in status_df.columns:
            status_df = status_df[status_df['ราคา'] >= map_min_p]
        if map_max_p > 0 and 'ราคา' in status_df.columns:
            status_df = status_df[status_df['ราคา'] <= map_max_p]
        if map_min_sqw > 0:
            col_sqw = 'เนื้อที่ (ตร.ว.)' if 'เนื้อที่ (ตร.ว.)' in status_df.columns else ('พื้นที่_ตารางวา' if 'พื้นที่_ตารางวา' in status_df.columns else None)
            if col_sqw:
                status_df = status_df[status_df[col_sqw].apply(to_float_sqwah) >= map_min_sqw]
        if map_max_sqw > 0:
            col_sqw = 'เนื้อที่ (ตร.ว.)' if 'เนื้อที่ (ตร.ว.)' in status_df.columns else ('พื้นที่_ตารางวา' if 'พื้นที่_ตารางวา' in status_df.columns else None)
            if col_sqw:
                status_df = status_df[status_df[col_sqw].apply(to_float_sqwah) <= map_max_sqw]
        if map_min_sqm > 0 and 'พื้นที่ใช้สอย (ตร.ม.)' in status_df.columns:
            status_df = status_df[status_df['พื้นที่ใช้สอย (ตร.ม.)'].apply(to_float_sqm) >= map_min_sqm]
        if map_max_sqm > 0 and 'พื้นที่ใช้สอย (ตร.ม.)' in status_df.columns:
            status_df = status_df[status_df['พื้นที่ใช้สอย (ตร.ม.)'].apply(to_float_sqm) <= map_max_sqm]

    matched_count = len(status_df)

    # Human-readable labels
    if active_subdist:
        clean_s = active_subdist[0].split(' (')[0].strip()
        clean_d = active_dist[0].split(' (')[0].strip() if active_dist else "-"
        loc_str = f"จ.{active_prov[0] if active_prov else '-'} > อ.{clean_d} > ต.{clean_s}"
    elif active_dist:
        clean_d = active_dist[0].split(' (')[0].strip()
        loc_str = f"จ.{active_prov[0] if active_prov else '-'} > อ.{clean_d}"
    elif active_prov:
        loc_str = f"จ.{active_prov[0]}"
    else:
        loc_str = "ทุกทำเล (ทั่วประเทศ)"

    if active_proj:
        loc_str += f" &bull; โครงการ: {active_proj}"

    if has_ref_point:
        if active_ref_prop:
            rad_str = f"{active_ref_radius:.1f} กม. รอบ [{active_ref_prop.get('บริษัท', '-')}] {active_ref_prop.get('รหัสทรัพย์', '')}"
        else:
            rad_str = f"{active_ref_radius:.1f} กม. ({active_ref_lat:.4f}, {active_ref_lon:.4f})"
    else:
        rad_str = f"รัศมี {active_ref_radius:.1f} กม. (ยังไม่ได้ปักหมุด)"

    cos_str = f"{', '.join(map_cos)} ({len(map_cos)} บริษัท)" if map_cos else "ทุกบริษัท"
    types_str = f"{', '.join(map_types)}" if map_types else "ทุกประเภททรัพย์"

    if map_min_p > 0 and map_max_p > 0:
        price_str = f"฿{format_price_kpi(map_min_p)} - ฿{format_price_kpi(map_max_p)}"
    elif map_min_p > 0:
        price_str = f">= ฿{format_price_kpi(map_min_p)}"
    elif map_max_p > 0:
        price_str = f"<= ฿{format_price_kpi(map_max_p)}"
    else:
        price_str = "ทุกช่วงราคา"

    area_parts = []
    if map_min_sqw > 0 or map_max_sqw > 0:
        area_parts.append(f"{map_min_sqw:,.0f}-{map_max_sqw:,.0f} ตร.ว." if map_max_sqw > 0 else f">= {map_min_sqw:,.0f} ตร.ว.")
    if map_min_sqm > 0 or map_max_sqm > 0:
        area_parts.append(f"{map_min_sqm:,.0f}-{map_max_sqm:,.0f} ตร.ม." if map_max_sqm > 0 else f">= {map_min_sqm:,.0f} ตร.ม.")
    area_str = " / ".join(area_parts) if area_parts else "ทุกขนาด (ทุก Plan)"

    mode_badge_lbl = "ตามรัศมี (Radius)" if (pin_mode == 'radius' and has_ref_point) else "ตามทำเล (Location)"

    # Theme colors for status card
    card_bg = "rgba(2, 44, 34, 0.45)" if is_dark_mode else "#f8fafc"
    card_border = "rgba(52, 211, 153, 0.35)" if is_dark_mode else "#e2e8f0"
    chip_bg = "rgba(2, 44, 34, 0.7)" if is_dark_mode else "#ffffff"
    chip_border = "rgba(52, 211, 153, 0.25)" if is_dark_mode else "#e2e8f0"
    text_c = "#f1f5f9" if is_dark_mode else "#1e293b"
    sub_c = "#94a3b8" if is_dark_mode else "#64748b"

    # --- RENDER FILTER STATUS BANNER (นอกแผนที่ ข้างใต้แผนที่) ---
    st.markdown(f"""
    <div id='ref-analytics-section' style='height: 0px; margin: 0px; padding: 0px; scroll-margin-top: 80px;'></div>
    <div id="map-active-filters-banner" style="background: {card_bg}; border: 1.5px solid {card_border}; border-radius: 14px; padding: 12px 16px; margin-top: -18px; margin-bottom: 12px; position: relative; z-index: 10; box-shadow: 0 4px 14px rgba(0,0,0,0.04);">
        <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px; margin-bottom: 10px; padding-bottom: 8px; border-bottom: 1px solid {chip_border};">
            <div style="display: flex; align-items: center; gap: 8px;">
                <span style="background: linear-gradient(135deg, #059669, #10b981); color: #ffffff; padding: 3px 10px; border-radius: 6px; font-size: 0.78rem; font-weight: 800; display: inline-flex; align-items: center; gap: 5px;">
                    <i class="fa-solid fa-sliders"></i> สถานะตัวกรองแผนที่ (Active Map Filters)
                </span>
                <span style="font-size: 0.82rem; font-weight: 700; color: #10b981;" id="active-filter-mode-val">
                    โหมด: <b>{mode_badge_lbl}</b>
                </span>
            </div>
            <div style="font-size: 0.82rem; font-weight: 700; color: #059669; background: rgba(16, 185, 129, 0.12); padding: 3px 10px; border-radius: 20px; display: inline-flex; align-items: center; gap: 5px;" id="active-filter-count-val">
                <i class="fa-solid fa-layer-group"></i> ทรัพย์ที่ตรงเงื่อนไข: <b>{matched_count:,}</b> รายการ
            </div>
        </div>
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 8px;">
            <div style="background: {chip_bg}; border: 1px solid {chip_border}; border-radius: 8px; padding: 7px 10px;">
                <div style="font-size: 0.70rem; font-weight: 700; color: {sub_c}; text-transform: uppercase;">
                    <i class="fa-solid fa-location-dot" style="color: #10b981; margin-right: 3px;"></i>ทำเล (Location)
                </div>
                <div id="active-filter-loc-val" style="font-size: 0.84rem; font-weight: 700; color: {text_c}; margin-top: 2px; word-break: break-word;">
                    {loc_str}
                </div>
            </div>
            <div style="background: {chip_bg}; border: 1px solid {chip_border}; border-radius: 8px; padding: 7px 10px;">
                <div style="font-size: 0.70rem; font-weight: 700; color: {sub_c}; text-transform: uppercase;">
                    <i class="fa-solid fa-bullseye" style="color: #06b6d4; margin-right: 3px;"></i>รัศมีตรวจ (Radius)
                </div>
                <div id="active-filter-rad-val" style="font-size: 0.84rem; font-weight: 700; color: {text_c}; margin-top: 2px;">
                    {rad_str}
                </div>
            </div>
            <div style="background: {chip_bg}; border: 1px solid {chip_border}; border-radius: 8px; padding: 7px 10px;">
                <div style="font-size: 0.70rem; font-weight: 700; color: {sub_c}; text-transform: uppercase;">
                    <i class="fa-solid fa-building" style="color: #3b82f6; margin-right: 3px;"></i>บริษัท (Company)
                </div>
                <div id="active-filter-co-val" style="font-size: 0.84rem; font-weight: 700; color: {text_c}; margin-top: 2px;">
                    {cos_str}
                </div>
            </div>
            <div style="background: {chip_bg}; border: 1px solid {chip_border}; border-radius: 8px; padding: 7px 10px;">
                <div style="font-size: 0.70rem; font-weight: 700; color: {sub_c}; text-transform: uppercase;">
                    <i class="fa-solid fa-house" style="color: #f59e0b; margin-right: 3px;"></i>ประเภททรัพย์ (Type)
                </div>
                <div id="active-filter-type-val" style="font-size: 0.84rem; font-weight: 700; color: {text_c}; margin-top: 2px;">
                    {types_str}
                </div>
            </div>
            <div style="background: {chip_bg}; border: 1px solid {chip_border}; border-radius: 8px; padding: 7px 10px;">
                <div style="font-size: 0.70rem; font-weight: 700; color: {sub_c}; text-transform: uppercase;">
                    <i class="fa-solid fa-tag" style="color: #10b981; margin-right: 3px;"></i>ราคา (Price)
                </div>
                <div id="active-filter-price-val" style="font-size: 0.84rem; font-weight: 700; color: {text_c}; margin-top: 2px;">
                    {price_str}
                </div>
            </div>
            <div style="background: {chip_bg}; border: 1px solid {chip_border}; border-radius: 8px; padding: 7px 10px;">
                <div style="font-size: 0.70rem; font-weight: 700; color: {sub_c}; text-transform: uppercase;">
                    <i class="fa-solid fa-ruler-combined" style="color: #8b5cf6; margin-right: 3px;"></i>ขนาด/Plan (Area)
                </div>
                <div id="active-filter-area-val" style="font-size: 0.84rem; font-weight: 700; color: {text_c}; margin-top: 2px;">
                    {area_str}
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 4. Track comparison state
    is_compared = st.session_state.get("tab2_compared_active", False)

    if not is_compared:
        # Comparison Button ALWAYS present and prominent above details!
        st.markdown("""
        <style>
        .st-key-tab2_hero_compare_container {
            display: flex !important;
            justify-content: center !important;
            align-items: center !important;
            margin-top: -6px !important;
            margin-bottom: 12px !important;
            position: relative !important;
            z-index: 100 !important;
        }
        .st-key-tab2_hero_compare_container div[data-testid="stButton"] {
            display: flex !important;
            justify-content: center !important;
            width: 100% !important;
        }
        .st-key-tab2_hero_compare_container button {
            background: linear-gradient(135deg, #059669 0%, #10b981 50%, #047857 100%) !important;
            color: #ffffff !important;
            font-size: 1.12rem !important;
            font-weight: 800 !important;
            font-family: 'Noto Sans Thai', 'Outfit', sans-serif !important;
            letter-spacing: 0.3px !important;
            padding: 12px 36px !important;
            min-height: 52px !important;
            max-width: 480px !important;
            width: 100% !important;
            border-radius: 50px !important;
            border: 1.5px solid rgba(255, 255, 255, 0.45) !important;
            box-shadow: 0 6px 20px rgba(16, 185, 129, 0.38), 0 2px 6px rgba(0, 0, 0, 0.1) !important;
            transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1) !important;
            cursor: pointer !important;
        }
        .st-key-tab2_hero_compare_container button:hover {
            transform: translateY(-2px) scale(1.02) !important;
            background: linear-gradient(135deg, #10b981 0%, #34d399 50%, #059669 100%) !important;
            box-shadow: 0 10px 28px rgba(16, 185, 129, 0.52), 0 4px 12px rgba(0, 0, 0, 0.15) !important;
            border-color: rgba(255, 255, 255, 0.8) !important;
            color: #ffffff !important;
        }
        .st-key-tab2_hero_compare_container button:active {
            transform: translateY(1px) scale(0.99) !important;
            box-shadow: 0 2px 10px rgba(16, 185, 129, 0.3) !important;
        }
        .st-key-tab2_hero_compare_container button p {
            font-size: 1.12rem !important;
            font-weight: 800 !important;
            color: #ffffff !important;
            margin: 0 !important;
            display: inline-flex !important;
            align-items: center !important;
            gap: 8px !important;
        }
        .st-key-tab2_hero_compare_container button span[data-testid="stIconMaterial"] {
            font-size: 1.35rem !important;
            color: #ffffff !important;
        }
        </style>
        """, unsafe_allow_html=True)
        with st.container(key="tab2_hero_compare_container"):
            col_b1, col_b2, col_b3 = st.columns([1, 1.8, 1])
            with col_b2:
                # Dynamic Compare Button Label
                if has_ref_point and pin_mode == 'radius' and not has_loc_filter:
                    btn_compare_label = f"กดเปรียบเทียบรอบจุดอ้างอิง ({active_ref_radius:.1f} กม.)"
                    btn_help_text = f"ประมวลผลการคำนวณราคากลางรอบจุดอ้างอิงในรัศมี {active_ref_radius:.1f} กม."
                elif active_subdist:
                    clean_s = active_subdist[0].split(' (')[0].strip()
                    clean_d = active_dist[0].split(' (')[0].strip() if active_dist else ""
                    btn_compare_label = f"กดเปรียบเทียบตามทำเล: ต.{clean_s} อ.{clean_d}"
                    btn_help_text = f"ประมวลผลการคำนวณราคากลางและวิเคราะห์ทรัพย์สินในตำบล {clean_s}"
                elif active_dist:
                    clean_d = active_dist[0].split(' (')[0].strip()
                    btn_compare_label = f"กดเปรียบเทียบตามทำเล: อ.{clean_d} จ.{active_prov[0] if active_prov else ''}"
                    btn_help_text = f"ประมวลผลการคำนวณราคากลางและวิเคราะห์ทรัพย์สินในอำเภอ {clean_d}"
                elif active_prov:
                    btn_compare_label = f"กดเปรียบเทียบตามทำเล: จังหวัด {active_prov[0]}"
                    btn_help_text = f"ประมวลผลการคำนวณราคากลางและวิเคราะห์ทรัพย์สินในจังหวัด {active_prov[0]}"
                elif active_proj:
                    btn_compare_label = f"กดเปรียบเทียบตามโครงการ: {active_proj}"
                    btn_help_text = f"ประมวลผลการคำนวณราคากลางในโครงการ {active_proj}"
                else:
                    btn_compare_label = "กดเปรียบเทียบสถิติและราคากลางทั้งหมด"
                    btn_help_text = "ประมวลผลการคำนวณราคากลางและวิเคราะห์ทรัพย์สินทั้งหมดตามตัวกรอง"

                btn_do_compare = st.button(
                    btn_compare_label,
                    icon=":material/compare_arrows:",
                    key="btn_do_ref_compare",
                    type="primary",
                    use_container_width=True,
                    help=btn_help_text
                )
                if btn_do_compare:
                    cur_lat = active_ref_lat or float(st.query_params.get("map_ref_lat", 0.0) or 0.0) or float(st.session_state.get("tab2_ref_lat", 0.0) or 0.0)
                    cur_lon = active_ref_lon or float(st.query_params.get("map_ref_lon", 0.0) or 0.0) or float(st.session_state.get("tab2_ref_lon", 0.0) or 0.0)
                    if cur_lat and cur_lon and cur_lat > 0 and cur_lon > 0:
                        active_ref_lat = cur_lat
                        active_ref_lon = cur_lon
                        st.session_state["tab2_ref_lat"] = cur_lat
                        st.session_state["tab2_ref_lon"] = cur_lon
                        st.session_state["tab2_compared_lat"] = cur_lat
                        st.session_state["tab2_compared_lon"] = cur_lon
                    st.session_state["tab2_compared_active"] = True
                    try:
                        st.rerun(scope="fragment")
                    except TypeError:
                        st.rerun()


    else:

        # 5. Calculation results (Cards & Table) with Live Filters
        # Determine comparison data scope
        if has_ref_point and (pin_mode == 'radius' or not has_loc_filter):
            nearby_df = find_nearby_properties(active_ref_lat, active_ref_lon, df_raw, active_ref_radius)
            scope_header = f"ในรัศมี {active_ref_radius:.1f} กม. รอบจุดอ้างอิง"
        else:
            nearby_df = df_raw.copy() if df_raw is not None else pd.DataFrame()
            if active_subdist:
                clean_s = active_subdist[0].split(' (')[0].strip()
                clean_d = active_dist[0].split(' (')[0].strip() if active_dist else ""
                scope_header = f"ในทำเล ตำบล{clean_s} อำเภอ{clean_d} จังหวัด{active_prov[0] if active_prov else ''}"
            elif active_dist:
                clean_d = active_dist[0].split(' (')[0].strip()
                scope_header = f"ในทำเล อำเภอ{clean_d} จังหวัด{active_prov[0] if active_prov else ''}"
            elif active_prov:
                scope_header = f"ในทำเล จังหวัด{active_prov[0]}"
            elif active_proj:
                scope_header = f"ในโครงการ {active_proj}"
            else:
                scope_header = "ภาพรวมตามตัวกรองที่เลือก"

        def get_tab2_unit_info(r):
            p_type = str(r.get('ประเภททรัพย์', '')).lower()
            is_condo = any(kw in p_type for kw in ['คอนโด', 'ห้องชุด'])
            price = r.get('ราคา')
            if pd.isna(price) or float(price) <= 0:
                return np.nan, "-", "-"
            if is_condo:
                sqm = to_float_sqm(r.get('พื้นที่ใช้สอย (ตร.ม.)'))
                if pd.notna(sqm) and float(sqm) > 0:
                    return float(price) / float(sqm), "ตร.ม.", "พื้นที่ใช้สอย"
            else:
                sqwah = to_float_sqwah(r.get('เนื้อที่ (ตร.ว.)', r.get('พื้นที่_ตารางวา', np.nan)))
                if pd.notna(sqwah) and float(sqwah) > 0:
                    return float(price) / float(sqwah), "ตร.ว.", "เนื้อที่"
            return np.nan, "-", "-"

        if not nearby_df.empty:
            unit_info_tuples = nearby_df.apply(get_tab2_unit_info, axis=1)
            nearby_df['ราคาต่อหน่วย'] = [t[0] for t in unit_info_tuples]
            nearby_df['หน่วยวัด'] = [t[1] for t in unit_info_tuples]
            nearby_df['ประเภทพื้นที่'] = [t[2] for t in unit_info_tuples]

        # Target type determination
        target_type = None
        if active_ref_prop is not None:
            target_type = active_ref_prop.get('ประเภททรัพย์')
        elif tab2_types and len(tab2_types) == 1:
            target_type = tab2_types[0]
        elif map_types and len(map_types) == 1:
            target_type = map_types[0]

        # Header row with title
        st.markdown(
            f"#### <i class='fa-solid fa-chart-simple' style='color:#059669; margin-right:6px;'></i>ผลการวิเคราะห์ราคากลางต่อหน่วย (Median Analysis) {scope_header}",
            unsafe_allow_html=True
        )

        # Apply active in-map filters to nearby_df
        filtered_nearby = nearby_df.copy()
        active_cos = map_cos
        active_types = map_types

        if active_prov and not filtered_nearby.empty and 'จังหวัด' in filtered_nearby.columns:
            filtered_nearby = filtered_nearby[filtered_nearby['จังหวัด'].astype(str).str.strip().isin(active_prov)]

        if active_dist and not filtered_nearby.empty and 'อำเภอ' in filtered_nearby.columns:
            clean_target_dists = [d.split(' (')[0].strip() for d in active_dist]
            filtered_nearby = filtered_nearby[filtered_nearby['อำเภอ'].astype(str).str.strip().isin(clean_target_dists)]

        if active_subdist and not filtered_nearby.empty and 'ตำบล' in filtered_nearby.columns:
            clean_target_subs = [s.split(' (')[0].strip() for s in active_subdist]
            filtered_nearby = filtered_nearby[filtered_nearby['ตำบล'].astype(str).str.strip().isin(clean_target_subs)]

        if active_proj and not filtered_nearby.empty and 'ชื่อโครงการ' in filtered_nearby.columns:
            p_list = [p.strip() for p in active_proj.split(",") if p.strip()]
            filtered_nearby = filtered_nearby[filtered_nearby['ชื่อโครงการ'].astype(str).str.strip().isin(p_list)]

        if active_cos and not filtered_nearby.empty and 'บริษัท' in filtered_nearby.columns:
            filtered_nearby = filtered_nearby[filtered_nearby['บริษัท'].isin(active_cos)]
        if active_types and not filtered_nearby.empty and 'ประเภททรัพย์' in filtered_nearby.columns:
            filtered_nearby = filtered_nearby[filtered_nearby['ประเภททรัพย์'].isin(active_types)]
        if map_min_p > 0 and not filtered_nearby.empty and 'ราคา' in filtered_nearby.columns:
            filtered_nearby = filtered_nearby[filtered_nearby['ราคา'] >= map_min_p]
        if map_max_p > 0 and not filtered_nearby.empty and 'ราคา' in filtered_nearby.columns:
            filtered_nearby = filtered_nearby[filtered_nearby['ราคา'] <= map_max_p]
        if map_min_sqw > 0 and not filtered_nearby.empty:
            col_sqw = 'เนื้อที่ (ตร.ว.)' if 'เนื้อที่ (ตร.ว.)' in filtered_nearby.columns else ('พื้นที่_ตารางวา' if 'พื้นที่_ตารางวา' in filtered_nearby.columns else None)
            if col_sqw:
                filtered_nearby = filtered_nearby[filtered_nearby[col_sqw].apply(to_float_sqwah) >= map_min_sqw]
        if map_max_sqw > 0 and not filtered_nearby.empty:
            col_sqw = 'เนื้อที่ (ตร.ว.)' if 'เนื้อที่ (ตร.ว.)' in filtered_nearby.columns else ('พื้นที่_ตารางวา' if 'พื้นที่_ตารางวา' in filtered_nearby.columns else None)
            if col_sqw:
                filtered_nearby = filtered_nearby[filtered_nearby[col_sqw].apply(to_float_sqwah) <= map_max_sqw]
        if map_min_sqm > 0 and not filtered_nearby.empty and 'พื้นที่ใช้สอย (ตร.ม.)' in filtered_nearby.columns:
            filtered_nearby = filtered_nearby[filtered_nearby['พื้นที่ใช้สอย (ตร.ม.)'].apply(to_float_sqm) >= map_min_sqm]
        if map_max_sqm > 0 and not filtered_nearby.empty and 'พื้นที่ใช้สอย (ตร.ม.)' in filtered_nearby.columns:
            filtered_nearby = filtered_nearby[filtered_nearby['พื้นที่ใช้สอย (ตร.ม.)'].apply(to_float_sqm) <= map_max_sqm]

        # Calculate Median for Target Type
        has_sel_u_stats = False
        median_u_sel = min_u_sel = max_u_sel = 0.0
        unit_lbl_sel = "ตร.ว."
        count_u_sel = 0
        
        if active_types:
            calc_type_df = filtered_nearby[filtered_nearby['ประเภททรัพย์'].isin(active_types)].copy() if not filtered_nearby.empty else pd.DataFrame()
            t_lbl = ", ".join(active_types)
        elif target_type:
            calc_type_df = filtered_nearby[filtered_nearby['ประเภททรัพย์'] == target_type].copy() if not filtered_nearby.empty else pd.DataFrame()
            t_lbl = target_type
        else:
            calc_type_df = filtered_nearby.copy()
            t_lbl = "ทรัพย์ทั้งหมดตามตัวกรอง"

        if not calc_type_df.empty:
            u_sel = calc_type_df['ราคาต่อหน่วย'].dropna()
            u_sel = u_sel[u_sel > 0]
            if not u_sel.empty:
                median_u_sel = float(u_sel.median())
                min_u_sel = float(u_sel.min())
                max_u_sel = float(u_sel.max())
                modes = calc_type_df[calc_type_df['หน่วยวัด'] != '-']['หน่วยวัด'].mode()
                unit_lbl_sel = modes[0] if not modes.empty else "ตร.ว."
                count_u_sel = len(u_sel)
                has_sel_u_stats = True

        # Calculate Median for Pure Land
        p_str = filtered_nearby['ประเภททรัพย์'].astype(str) if not filtered_nearby.empty else pd.Series()
        is_pure_land = p_str.str.contains('ที่ดินเปล่า|ที่ดิน', regex=True, na=False) & \
                       ~p_str.str.contains('บ้าน|อาคาร|ทาวน์|คอนโด|ตึก|โรงงาน|พาณิชย์|หอพัก', regex=True, na=False)
        raw_land_df = filtered_nearby[is_pure_land & (filtered_nearby['ราคา'] > 0)].copy() if not filtered_nearby.empty else pd.DataFrame()
        
        has_raw_land = False
        median_raw_land = min_raw_land = max_raw_land = 0.0
        count_raw_land = 0
        if not raw_land_df.empty:
            rl_u = raw_land_df['ราคาต่อหน่วย'].dropna()
            rl_u = rl_u[rl_u > 0]
            if not rl_u.empty:
                median_raw_land = float(rl_u.median())
                min_raw_land = float(rl_u.min())
                max_raw_land = float(rl_u.max())
                count_raw_land = len(rl_u)
                has_raw_land = True

        # Calculate Median for All Sq. Wah (เนื้อที่ดิน) in filtered_nearby
        has_sqw_median = False
        median_sqw_val = 0.0
        count_sqw_val = 0
        min_sqw_val = max_sqw_val = 0.0
        if not filtered_nearby.empty:
            col_sqw_name = 'เนื้อที่ (ตร.ว.)' if 'เนื้อที่ (ตร.ว.)' in filtered_nearby.columns else ('พื้นที่_ตารางวา' if 'พื้นที่_ตารางวา' in filtered_nearby.columns else None)
            if col_sqw_name:
                sqw_vals = filtered_nearby[col_sqw_name].apply(to_float_sqwah)
                price_vals = pd.to_numeric(filtered_nearby['ราคา'], errors='coerce') if 'ราคา' in filtered_nearby.columns else pd.Series(dtype=float)
                valid_mask_sqw = (sqw_vals > 0) & (price_vals > 0)
                sqw_rates = (price_vals[valid_mask_sqw] / sqw_vals[valid_mask_sqw]).dropna()
                sqw_rates = sqw_rates[sqw_rates > 0]
                if not sqw_rates.empty:
                    median_sqw_val = float(sqw_rates.median())
                    min_sqw_val = float(sqw_rates.min())
                    max_sqw_val = float(sqw_rates.max())
                    count_sqw_val = len(sqw_rates)
                    has_sqw_median = True

        # Calculate Median for All Sq. Metre (พื้นที่ใช้สอย) in filtered_nearby
        has_sqm_median = False
        median_sqm_val = 0.0
        count_sqm_val = 0
        min_sqm_val = max_sqm_val = 0.0
        if not filtered_nearby.empty and 'พื้นที่ใช้สอย (ตร.ม.)' in filtered_nearby.columns:
            sqm_vals = filtered_nearby['พื้นที่ใช้สอย (ตร.ม.)'].apply(to_float_sqm)
            price_vals = pd.to_numeric(filtered_nearby['ราคา'], errors='coerce') if 'ราคา' in filtered_nearby.columns else pd.Series(dtype=float)
            valid_mask_sqm = (sqm_vals > 0) & (price_vals > 0)
            sqm_rates = (price_vals[valid_mask_sqm] / sqm_vals[valid_mask_sqm]).dropna()
            sqm_rates = sqm_rates[sqm_rates > 0]
            if not sqm_rates.empty:
                median_sqm_val = float(sqm_rates.median())
                min_sqm_val = float(sqm_rates.min())
                max_sqm_val = float(sqm_rates.max())
                count_sqm_val = len(sqm_rates)
                has_sqm_median = True

        # Render 5 Metric Cards (Separating Total Count, Sq. Wah, Sq. Metre, Target Type, Land)
        card_c1, card_c2, card_c3, card_c4, card_c5 = st.columns(5)
        total_nearby_cnt = len(filtered_nearby)
        co_tag = f" [{', '.join(active_cos)}]" if active_cos else ""

        # Card 1: Reference Info (Total Count as Primary Metric)
        if active_ref_prop is not None:
            p_co = active_ref_prop.get('บริษัท', '-')
            p_code = active_ref_prop.get('รหัสทรัพย์', '-')
            p_price_val = active_ref_prop.get('ราคา', 0)
            p_type_str = str(active_ref_prop.get('ประเภททรัพย์', '-'))
            price_disp = f"฿{float(p_price_val):,.0f}" if pd.notna(p_price_val) and float(p_price_val) > 0 else "ไม่ระบุราคา"
            sub_ref_info = f"<div style='color: #94a3b8; font-size: 0.74rem; margin-top: 2px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;'>[{p_co}] {p_code} &bull; {p_type_str}</div>"
        elif active_ref_lat and active_ref_lon:
            sub_ref_info = "<div style='color: #94a3b8; font-size: 0.74rem; margin-top: 2px;'>กำหนดจากพิกัดแผนที่</div>"
        else:
            sub_ref_info = f"<div style='color: #94a3b8; font-size: 0.74rem; margin-top: 2px;'>{scope_header}</div>"

        card1_loc_detail = f"{active_ref_lat:.5f}, {active_ref_lon:.5f} (รัศมี {active_ref_radius:.1f} กม.)" if (active_ref_lat and active_ref_lon) else scope_header
        card1_html = (
            f"<div class='metric-card' style='background: rgba(16, 185, 129, 0.04); border: 1px solid rgba(16, 185, 129, 0.25); border-radius: 12px; padding: 12px 14px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); min-height: 140px; display: flex; flex-direction: column; justify-content: space-between;'>"
            f"<div>"
            f"<div style='font-size: 0.78rem; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.4px;'><i class='fa-solid fa-layer-group' style='color: #10b981; margin-right:4px;'></i> จำนวนทรัพย์ทั้งหมด</div>"
            f"<div style='font-size: 1.55rem; font-weight: 800; color: #059669; margin: 3px 0;'>{total_nearby_cnt:,} <span style='font-size:0.85rem; font-weight:600; color:#64748b;'>รายการ</span></div>"
            f"</div>"
            f"<div>"
            f"<div style='color: #64748b; font-size: 0.76rem;'><i class='fa-solid fa-location-dot' style='color:#10b981; font-size:0.72rem; margin-right:3px;'></i>{card1_loc_detail}</div>"
            f"{sub_ref_info}"
            f"</div>"
            f"</div>"
        )

        # Card 2: Median Sq. Wah (All Properties)
        if has_sqw_median:
            c2_main = f"฿{median_sqw_val:,.0f}"
            c2_unit = "/ตร.ว."
            c2_sub = f"ต่ำสุด ฿{min_sqw_val:,.0f} &bull; สูงสุด ฿{max_sqw_val:,.0f}"
            c2_badge = f"<span style='font-size:0.74rem; font-weight:600; color:#10b981;'>({count_sqw_val:,} แปลง)</span>"
        else:
            c2_main = "-"
            c2_unit = ""
            c2_sub = "ไม่มีข้อมูลเนื้อที่ดิน"
            c2_badge = ""

        card2_html = (
            f"<div class='metric-card' style='background: rgba(16, 185, 129, 0.04); border: 1px solid rgba(16, 185, 129, 0.25); border-radius: 12px; padding: 12px 14px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); min-height: 140px; display: flex; flex-direction: column; justify-content: space-between;'>"
            f"<div>"
            f"<div style='font-size: 0.78rem; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.4px;'><i class='fa-solid fa-chart-line' style='color: #10b981; margin-right:4px;'></i> ราคากลาง / ตร.ว. {c2_badge}</div>"
            f"<div style='font-size: 1.55rem; font-weight: 800; color: #059669; margin: 3px 0;'>{c2_main} <span style='font-size:0.85rem; font-weight:600; color:#64748b;'>{c2_unit}</span></div>"
            f"</div>"
            f"<div style='color: #64748b; font-size: 0.76rem;'>{c2_sub}</div>"
            f"</div>"
        )

        # Card 3: Median Sq. Metre (All Properties)
        if has_sqm_median:
            c3_main = f"฿{median_sqm_val:,.0f}"
            c3_unit = "/ตร.ม."
            c3_sub = f"ต่ำสุด ฿{min_sqm_val:,.0f} &bull; สูงสุด ฿{max_sqm_val:,.0f}"
            c3_badge = f"<span style='font-size:0.74rem; font-weight:600; color:#10b981;'>({count_sqm_val:,} แปลง)</span>"
        else:
            c3_main = "-"
            c3_unit = ""
            c3_sub = "ไม่มีข้อมูลพื้นที่ใช้สอย"
            c3_badge = ""

        card3_html = (
            f"<div class='metric-card' style='background: rgba(16, 185, 129, 0.04); border: 1px solid rgba(16, 185, 129, 0.25); border-radius: 12px; padding: 12px 14px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); min-height: 140px; display: flex; flex-direction: column; justify-content: space-between;'>"
            f"<div>"
            f"<div style='font-size: 0.78rem; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.4px;'><i class='fa-solid fa-ruler-combined' style='color: #10b981; margin-right:4px;'></i> ราคากลาง / ตร.ม. {c3_badge}</div>"
            f"<div style='font-size: 1.55rem; font-weight: 800; color: #059669; margin: 3px 0;'>{c3_main} <span style='font-size:0.85rem; font-weight:600; color:#64748b;'>{c3_unit}</span></div>"
            f"</div>"
            f"<div style='color: #64748b; font-size: 0.76rem;'>{c3_sub}</div>"
            f"</div>"
        )

        # Card 4: Target Type
        if has_sel_u_stats:
            c4_main = f"฿{median_u_sel:,.0f}"
            c4_unit = f"/{unit_lbl_sel}"
            c4_sub = f"ต่ำสุด ฿{min_u_sel:,.0f} &bull; สูงสุด ฿{max_u_sel:,.0f}"
            c4_badge = f"<span style='font-size:0.74rem; font-weight:600; color:#10b981;'>({count_u_sel:,} แปลง)</span>"
        else:
            c4_main = "-"
            c4_unit = ""
            c4_sub = f"ไม่มีข้อมูลราคาสำหรับ {t_lbl}"
            c4_badge = ""

        card4_html = (
            f"<div class='metric-card' style='background: rgba(16, 185, 129, 0.04); border: 1px solid rgba(16, 185, 129, 0.25); border-radius: 12px; padding: 12px 14px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); min-height: 140px; display: flex; flex-direction: column; justify-content: space-between;'>"
            f"<div>"
            f"<div style='font-size: 0.78rem; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.4px;'><i class='fa-solid fa-house' style='color: #10b981; margin-right:4px;'></i> ราคากลาง {t_lbl} {c4_badge}</div>"
            f"<div style='font-size: 1.55rem; font-weight: 800; color: #059669; margin: 3px 0;'>{c4_main} <span style='font-size:0.85rem; font-weight:600; color:#64748b;'>{c4_unit}</span></div>"
            f"</div>"
            f"<div style='color: #64748b; font-size: 0.76rem;'>{c4_sub}</div>"
            f"</div>"
        )

        # Card 5: Pure Land
        if has_raw_land:
            c5_main = f"฿{median_raw_land:,.0f}"
            c5_unit = "/ตร.ว."
            c5_sub = f"ต่ำสุด ฿{min_raw_land:,.0f} &bull; สูงสุด ฿{max_raw_land:,.0f}"
            c5_badge = f"<span style='font-size:0.74rem; font-weight:600; color:#10b981;'>({count_raw_land:,} แปลง)</span>"
        else:
            c5_main = "-"
            c5_unit = ""
            c5_sub = "ไม่พบข้อมูลที่ดินเปล่า"
            c5_badge = ""

        card5_html = (
            f"<div class='metric-card' style='background: rgba(16, 185, 129, 0.04); border: 1px solid rgba(16, 185, 129, 0.25); border-radius: 12px; padding: 12px 14px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); min-height: 140px; display: flex; flex-direction: column; justify-content: space-between;'>"
            f"<div>"
            f"<div style='font-size: 0.78rem; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.4px;'><i class='fa-solid fa-mountain-sun' style='color: #10b981; margin-right:4px;'></i> ราคากลางที่ดินเปล่า {c5_badge}</div>"
            f"<div style='font-size: 1.55rem; font-weight: 800; color: #059669; margin: 3px 0;'>{c5_main} <span style='font-size:0.85rem; font-weight:600; color:#64748b;'>{c5_unit}</span></div>"
            f"</div>"
            f"<div>{c5_sub}</div>"
            f"</div>"
        )

        with card_c1:
            st.html(card1_html)
        with card_c2:
            st.html(card2_html)
        with card_c3:
            st.html(card3_html)
        with card_c4:
            st.html(card4_html)
        with card_c5:
            st.html(card5_html)

        # Nearby Assets Table (Direct display with icon instead of expander)
        filter_summary_str = f" [กรอง: {', '.join(active_cos)}]" if active_cos else ""
        if not filtered_nearby.empty:
            st.markdown(
                f"<div style='margin-top: 22px; margin-bottom: 12px; font-weight: 700; font-size: 1.06rem; display: flex; align-items: center; justify-content: space-between;'>"
                f"<span><i class='fa-solid fa-table-list' style='color:#059669; margin-right:8px;'></i>"
                f"รายการทรัพย์สิน ({len(filtered_nearby):,} รายการ {scope_header}{filter_summary_str})</span>"
                f"<span style='font-size: 0.8rem; font-weight: 600; color: #059669; background: rgba(16, 185, 129, 0.1); padding: 4px 12px; border-radius: 20px; border: 1.2px solid rgba(16, 185, 129, 0.3);'>"
                f"<i class='fa-solid fa-layer-group' style='margin-right:5px;'></i>ตารางเปรียบเทียบข้อมูลทรัพย์</span>"
                f"</div>",
                unsafe_allow_html=True
            )
            # Build detailed analysis dataframe for display
            show_df = pd.DataFrame(index=filtered_nearby.index)
            
            # 1. บริษัท, รหัสทรัพย์, ประเภททรัพย์
            for col in ['บริษัท', 'รหัสทรัพย์', 'ประเภททรัพย์']:
                if col in filtered_nearby.columns:
                    show_df[col] = filtered_nearby[col]
            
            # 2. ราคา (บาท)
            price_num = pd.to_numeric(filtered_nearby['ราคา'], errors='coerce') if 'ราคา' in filtered_nearby.columns else pd.Series(np.nan, index=filtered_nearby.index)
            show_df['ราคา (บาท)'] = price_num
            
            # 3. เนื้อที่ (ตร.ว.)
            col_sqw_name = 'พื้นที่_ตารางวา' if 'พื้นที่_ตารางวา' in filtered_nearby.columns else ('เนื้อที่ (ตร.ว.)' if 'เนื้อที่ (ตร.ว.)' in filtered_nearby.columns else None)
            sqw_vals = filtered_nearby[col_sqw_name].apply(to_float_sqwah) if col_sqw_name else pd.Series(np.nan, index=filtered_nearby.index)
            show_df['เนื้อที่ (ตร.ว.)'] = sqw_vals

            # 4. ราคาต่อตร.ว. (บาท)
            if 'ราคาต่อตารางวา' in filtered_nearby.columns:
                calc_p_sqw = pd.to_numeric(filtered_nearby['ราคาต่อตารางวา'], errors='coerce')
                fallback_sqw = np.where((price_num > 0) & (sqw_vals > 0), price_num / sqw_vals, np.nan)
                calc_p_sqw = np.where(calc_p_sqw > 0, calc_p_sqw, fallback_sqw)
            else:
                calc_p_sqw = np.where((price_num > 0) & (sqw_vals > 0), price_num / sqw_vals, np.nan)
            show_df['ราคาต่อตร.ว. (บาท)'] = calc_p_sqw

            # 5. เทียบราคากลางต่อ ตร.ว.
            def _fmt_diff_pct(val, med):
                if pd.isna(val) or val <= 0 or pd.isna(med) or med <= 0:
                    return "-"
                diff = ((val - med) / med) * 100.0
                if diff > 0:
                    return f"↑ +{diff:.1f}%"
                elif diff < 0:
                    return f"↓ {diff:.1f}%"
                else:
                    return "0.0%"

            show_df['เทียบราคากลางต่อ ตร.ว.'] = [_fmt_diff_pct(v, median_sqw_val) for v in calc_p_sqw]

            # 6. เทียบราคากับ ตร.ว. ของที่ดินเปล่า
            show_df['เทียบราคากับ ตร.ว. ของที่ดินเปล่า'] = [_fmt_diff_pct(v, median_raw_land) for v in calc_p_sqw]

            # 7. พื้นที่ใช้สอย (ตร.ม.)
            sqm_vals = filtered_nearby['พื้นที่ใช้สอย (ตร.ม.)'].apply(to_float_sqm) if 'พื้นที่ใช้สอย (ตร.ม.)' in filtered_nearby.columns else pd.Series(np.nan, index=filtered_nearby.index)
            show_df['พื้นที่ใช้สอย (ตร.ม.)'] = sqm_vals

            # 8. ราคาต่อตร.ม. (บาท)
            if 'ราคาต่อตารางเมตร' in filtered_nearby.columns:
                calc_p_sqm = pd.to_numeric(filtered_nearby['ราคาต่อตารางเมตร'], errors='coerce')
                fallback_sqm = np.where((price_num > 0) & (sqm_vals > 0), price_num / sqm_vals, np.nan)
                calc_p_sqm = np.where(calc_p_sqm > 0, calc_p_sqm, fallback_sqm)
            else:
                calc_p_sqm = np.where((price_num > 0) & (sqm_vals > 0), price_num / sqm_vals, np.nan)
            show_df['ราคาต่อตร.ม. (บาท)'] = calc_p_sqm

            # 9. เทียบราคากลางต่อ ตร.ม.
            show_df['เทียบราคากลางต่อ ตร.ม.'] = [_fmt_diff_pct(v, median_sqm_val) for v in calc_p_sqm]

            # 10. ระยะทาง (กม.) (ถ้ามีการค้นหาตามพิกัดรัศมี)
            if 'ระยะทาง (กม.)' in filtered_nearby.columns:
                show_df['ระยะทาง (กม.)'] = pd.to_numeric(filtered_nearby['ระยะทาง (กม.)'], errors='coerce')
                show_df = show_df.sort_values(by='ระยะทาง (กม.)', ascending=True)

            # 11. ตำบล, อำเภอ, จังหวัด
            for loc_c in ['ตำบล', 'อำเภอ', 'จังหวัด']:
                if loc_c in filtered_nearby.columns:
                    show_df[loc_c] = filtered_nearby[loc_c]

            # 12. เปิดลิงก์
            if 'ลิงก์' in filtered_nearby.columns:
                show_df['เปิดลิงก์'] = filtered_nearby['ลิงก์']

            table_col_config = {
                "ราคา (บาท)": st.column_config.NumberColumn("ราคา (บาท)", format="฿%,d"),
                "เนื้อที่ (ตร.ว.)": st.column_config.NumberColumn("เนื้อที่ (ตร.ว.)", format="%,.1f"),
                "ราคาต่อตร.ว. (บาท)": st.column_config.NumberColumn("ราคาต่อตร.ว. (บาท)", format="฿%,d"),
                "เทียบราคากลางต่อ ตร.ว.": st.column_config.TextColumn(
                    "เทียบราคากลางต่อ ตร.ว.",
                    help=f"เทียบกับราคากลาง ตร.ว. ในพื้นที่ (฿{median_sqw_val:,.0f}/ตร.ว.) ค่าบวก = สูงกว่าราคากลาง, ค่าลบ = ถูกกว่าราคากลาง" if median_sqw_val > 0 else "เทียบราคากลางต่อ ตร.ว."
                ),
                "เทียบราคากับ ตร.ว. ของที่ดินเปล่า": st.column_config.TextColumn(
                    "เทียบราคากับ ตร.ว. ของที่ดินเปล่า",
                    help=f"เทียบกับราคากลาง ตร.ว. ที่ดินเปล่า (฿{median_raw_land:,.0f}/ตร.ว.) ค่าบวก = สูงกว่าที่ดินเปล่า, ค่าลบ = ถูกกว่า" if median_raw_land > 0 else "เทียบราคากลางที่ดินเปล่า"
                ),
                "พื้นที่ใช้สอย (ตร.ม.)": st.column_config.NumberColumn("พื้นที่ใช้สอย (ตร.ม.)", format="%,.1f"),
                "ราคาต่อตร.ม. (บาท)": st.column_config.NumberColumn("ราคาต่อตร.ม. (บาท)", format="฿%,d"),
                "เทียบราคากลางต่อ ตร.ม.": st.column_config.TextColumn(
                    "เทียบราคากลางต่อ ตร.ม.",
                    help=f"เทียบกับราคากลาง ตร.ม. ในพื้นที่ (฿{median_sqm_val:,.0f}/ตร.ม.) ค่าบวก = สูงกว่าราคากลาง, ค่าลบ = ถูกกว่าราคากลาง" if median_sqm_val > 0 else "เทียบราคากลางต่อ ตร.ม."
                ),
                "ระยะทาง (กม.)": st.column_config.NumberColumn("ระยะทาง (กม.)", format="%.2f กม."),
                "เปิดลิงก์": st.column_config.LinkColumn("เปิดลิงก์", display_text="เปิดดูทรัพย์"),
            }

            def highlight_diff_cells(val):
                s = str(val).strip()
                if s in ["-", "", "nan", "None", "0.0%"]:
                    return ""
                if s.startswith("↑") or s.startswith("▲"):
                    return "color: #047857; font-weight: 700; background-color: rgba(16, 185, 129, 0.12); border: 1.5px solid rgba(16, 185, 129, 0.4); border-radius: 6px;"
                elif s.startswith("↓") or s.startswith("▼"):
                    return "color: #b91c1c; font-weight: 700; background-color: rgba(239, 68, 68, 0.12); border: 1.5px solid rgba(239, 68, 68, 0.4); border-radius: 6px;"
                return ""

            diff_target_cols = [c for c in ['เทียบราคากลางต่อ ตร.ว.', 'เทียบราคากับ ตร.ว. ของที่ดินเปล่า', 'เทียบราคากลางต่อ ตร.ม.'] if c in show_df.columns]
            
            # Pandas Styler has a cell rendering cap (default 262,144 cells).
            # When viewing large datasets (e.g. nationwide or thousands of rows), render show_df
            # directly via Arrow to maintain ultra-fast virtualized scrolling and avoid Styler memory exceptions.
            df_to_render = show_df
            if diff_target_cols and show_df.size <= 200_000:
                try:
                    df_to_render = show_df.style.map(highlight_diff_cells, subset=diff_target_cols)
                except Exception:
                    df_to_render = show_df

            try:
                st.dataframe(df_to_render, use_container_width=True, height=380, column_config=table_col_config)
            except Exception:
                st.dataframe(show_df, use_container_width=True, height=380, column_config=table_col_config)
            # ── Import / Export (same style as Tab 1) ──
            render_import_export_section(show_df, filename_prefix=f"comparison_{scope_header.replace(' ', '_')}", key_suffix="tab2_compare")
        else:
            st.info(f"ไม่พบรายการทรัพย์สินที่ตรงตามเงื่อนไขตัวกรอง {scope_header}")

@st.cache_data(show_spinner=False)
def load_raw_districts_geojson():
    path = os.path.join("data", "districts.geojson")
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None
    return None

@st.cache_data(show_spinner=False)
def load_raw_subdistricts_geojson():
    path = os.path.join("data", "subdistricts.geojson")
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None
    return None

def _calc_polygon_centroid(geometry):
    if not geometry or 'coordinates' not in geometry:
        return None
    coords = geometry['coordinates']
    lons, lats = [], []
    def _extract(c):
        if isinstance(c, (list, tuple)):
            if len(c) >= 2 and isinstance(c[0], (int, float)) and isinstance(c[1], (int, float)):
                lons.append(float(c[0]))
                lats.append(float(c[1]))
            else:
                for item in c:
                    _extract(item)
    _extract(coords)
    if lons and lats:
        avg_lon = (min(lons) + max(lons)) / 2.0
        avg_lat = (min(lats) + max(lats)) / 2.0
        return (avg_lon, avg_lat)
    return None

def get_boundary_geojson_features(prov_list=None, dist_list=None, subdist_list=None):
    """Filters districts or subdistricts GeoJSON to get boundary frames, dashed district lines, and labels."""
    if not prov_list and not dist_list and not subdist_list:
        return None

    # Clean district names (e.g. 'เมืองนนทบุรี (นนทบุรี)' -> 'เมืองนนทบุรี')
    clean_dists = set()
    if dist_list:
        for d in dist_list:
            d_str = str(d).strip()
            clean_dists.add(d_str.split(" (")[0].strip())
            clean_dists.add(d_str)

    clean_provs = set(str(p).strip() for p in (prov_list or []))
    clean_subdists = set(str(s).strip() for s in (subdist_list or []))

    district_labels = []

    # Case 1: Subdistrict selected
    if clean_subdists:
        sd_data = load_raw_subdistricts_geojson()
        if sd_data and 'features' in sd_data:
            matched = []
            for feat in sd_data['features']:
                props = feat.get('properties', {})
                tam_th = str(props.get('tam_th', '')).strip()
                amp_th = str(props.get('amp_th', '')).strip()
                pro_th = str(props.get('pro_th', '')).strip()
                if tam_th in clean_subdists:
                    if clean_dists and amp_th not in clean_dists:
                        continue
                    if clean_provs and pro_th not in clean_provs:
                        continue
                    matched.append(feat)
                    centroid = _calc_polygon_centroid(feat.get('geometry'))
                    if centroid:
                        district_labels.append({"name": tam_th, "lon": centroid[0], "lat": centroid[1]})
            if matched:
                return {"type": "FeatureCollection", "level": "single_subdistrict", "features": matched, "district_labels": district_labels}

    # Case 2: District selected -> subdivide into subdistricts (ตำบล) with dashed lines
    if clean_dists:
        sd_data = load_raw_subdistricts_geojson()
        if sd_data and 'features' in sd_data:
            matched = []
            for feat in sd_data['features']:
                props = feat.get('properties', {})
                tam_th = str(props.get('tam_th', '')).strip()
                amp_th = str(props.get('amp_th', '')).strip()
                pro_th = str(props.get('pro_th', '')).strip()
                if amp_th in clean_dists:
                    if clean_provs and pro_th not in clean_provs:
                        continue
                    matched.append(feat)
                    centroid = _calc_polygon_centroid(feat.get('geometry'))
                    if centroid:
                        district_labels.append({"name": tam_th, "lon": centroid[0], "lat": centroid[1]})
            if matched:
                return {
                    "type": "FeatureCollection",
                    "level": "subdistrict",
                    "features": matched,
                    "district_labels": district_labels
                }

        # Fallback to district boundaries if subdistricts not found
        dist_data = load_raw_districts_geojson()
        if dist_data and 'features' in dist_data:
            matched = []
            for feat in dist_data['features']:
                props = feat.get('properties', {})
                amp_th = str(props.get('amp_th', '')).strip()
                pro_th = str(props.get('pro_th', '')).strip()
                if amp_th in clean_dists:
                    if clean_provs and pro_th not in clean_provs:
                        continue
                    matched.append(feat)
                    centroid = _calc_polygon_centroid(feat.get('geometry'))
                    if centroid:
                        district_labels.append({"name": amp_th, "lon": centroid[0], "lat": centroid[1]})
            if matched:
                return {
                    "type": "FeatureCollection",
                    "level": "district",
                    "features": matched,
                    "district_labels": district_labels
                }

    # Case 3: Province selected (extract all district boundaries within the province)
    if clean_provs:
        dist_data = load_raw_districts_geojson()
        if dist_data and 'features' in dist_data:
            matched = []
            for feat in dist_data['features']:
                props = feat.get('properties', {})
                pro_th = str(props.get('pro_th', '')).strip()
                amp_th = str(props.get('amp_th', '')).strip()
                if pro_th in clean_provs:
                    matched.append(feat)
                    centroid = _calc_polygon_centroid(feat.get('geometry'))
                    if centroid:
                        district_labels.append({"name": amp_th, "lon": centroid[0], "lat": centroid[1]})
            if matched:
                return {"type": "FeatureCollection", "level": "district", "features": matched, "district_labels": district_labels}

    return None

# Load the properties data (auto-invalidates cache whenever all_assets.parquet is modified)
df_raw = load_properties_data(get_data_mtime())

# Merge user uploaded data if available
if "imported_custom_df" in st.session_state and st.session_state["imported_custom_df"] is not None:
    imp_df = st.session_state["imported_custom_df"].copy()
    if 'บริษัท' not in imp_df.columns:
        imp_df['บริษัท'] = 'ไฟล์นำเข้า'
    imp_df = ensure_derived_cols(imp_df)
    if df_raw is not None and not df_raw.empty:
        cat_cols = ['บริษัท', 'ประเภททรัพย์', 'จังหวัด', 'ภาค', 'ประเภทการขาย']
        for c in cat_cols:
            if c in df_raw.columns and isinstance(df_raw[c].dtype, pd.CategoricalDtype):
                df_raw[c] = df_raw[c].astype(str)
            if c in imp_df.columns and isinstance(imp_df[c].dtype, pd.CategoricalDtype):
                imp_df[c] = imp_df[c].astype(str)
        df_raw = pd.concat([df_raw, imp_df], ignore_index=True)
        for c in cat_cols:
            if c in df_raw.columns:
                df_raw[c] = df_raw[c].astype('category')
    else:
        df_raw = imp_df

# ----------------- SIDEBAR -----------------
with st.sidebar:
    col_side_title, col_side_theme = st.columns([0.72, 0.28])
    with col_side_title:
        sb_logo_path = os.path.join("logo", "logo.png") if os.path.exists(os.path.join("logo", "logo.png")) else os.path.join("assets", "logo.png")
        if os.path.exists(sb_logo_path):
            with open(sb_logo_path, "rb") as f_logo:
                sb_logo_b64 = base64.b64encode(f_logo.read()).decode("utf-8")
            sb_logo_img = f'<div style="width: 40px; height: 40px; min-width: 40px; display: flex; align-items: center; justify-content: center;"><img src="data:image/png;base64,{sb_logo_b64}" style="width: 100%; height: 100%; object-fit: contain; filter: drop-shadow(0 2px 6px rgba(0,0,0,0.3));"></div>'
        else:
            sb_logo_img = '<i class="fa-solid fa-city" style="margin-right:6px; font-size:1.25rem; color:#34d399;"></i>'
            
        st.markdown(f'''
        <div style="display: flex; align-items: center; gap: 9px; margin-bottom: 2px; padding-top: 2px;">
            {sb_logo_img}
            <div style="display: flex; flex-direction: column;">
                <div style="font-size: 1.35rem; font-weight: 800; color: #ffffff; line-height: 1.1; letter-spacing: -0.5px;">NOVA</div>
                <div style="font-size: 0.68rem; font-weight: 700; color: #a7f3d0; letter-spacing: 0.8px;">NPA DASHBOARD</div>
            </div>
        </div>
        ''', unsafe_allow_html=True)
    with col_side_theme:
        col_t1, col_t2 = st.columns([0.65, 0.35])
        with col_t1:
            is_dark_mode = st.toggle("โหมดมืด", value=False, key="app_theme_mode", label_visibility="collapsed", help="สลับระหว่างโหมดมืดและโหมดสว่าง (Dark / Light Mode)")
        with col_t2:
            st.markdown(f'''<div style="padding-top: 6px; font-size: 1.15rem; color: {'#34d399' if is_dark_mode else '#6ee7b7'};"><i class="fa-solid fa-moon"></i></div>''', unsafe_allow_html=True)
    
    if df_raw is not None and not df_raw.empty:
        src_name = getattr(df_raw, 'attrs', {}).get('source', 'all_assets.parquet')
        _, exact_date_str = get_dataset_month_year(df_raw)
        st.markdown(f"""
        <div style="background: rgba(255, 255, 255, 0.08); border: 1px solid rgba(110, 231, 183, 0.25); border-radius: 8px; padding: 7px 10px; margin-top: 5px; margin-bottom: 8px; font-size: 0.8rem; color: #f0fdf4; font-weight: 600;">
            <i class="fa fa-database" style="color:#34d399;"></i> แหล่งข้อมูล: <code style="background:rgba(0,0,0,0.25); color:#a7f3d0; padding:1px 5px; border-radius:4px;">{src_name}</code><br/>
            <span style="font-size: 0.75rem; color: #6ee7b7; font-weight: 600;"><i class="fa fa-calendar-check" style="margin-right: 3px; color:#34d399;"></i> ดึงข้อมูล: <b style="color:#ffffff;">{exact_date_str}</b></span>
        </div>
        """, unsafe_allow_html=True)
        
    if st.button("รีโหลดฐานข้อมูล (Clear Cache)", icon=":material/refresh:", key="btn_clear_cache_main", use_container_width=True, help="ล้างแคชและรีเฟรชหน้าเว็บใหม่ล่าสุดทันที"):
        # 1. Clear all Streamlit caches, query params, and session state
        st.cache_data.clear()
        st.cache_resource.clear()
        try:
            st.query_params.clear()
        except Exception:
            pass
        for k in list(st.session_state.keys()):
            st.session_state.pop(k, None)
        
        # 2. Dynamic overlay theme
        overlay_bg = "rgba(15, 23, 42, 0.94)" if is_dark_mode else "rgba(255, 255, 255, 0.94)"
        overlay_title = "#34d399" if is_dark_mode else "#064e3b"
        overlay_desc = "#94a3b8" if is_dark_mode else "#047857"
        
        # 3. Display smooth loading overlay and navigate browser to clean base URL (origin + pathname)
        st.html(f"""
        <div style="position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; background: {overlay_bg}; backdrop-filter: blur(6px); z-index: 99999999; display: flex; flex-direction: column; align-items: center; justify-content: center; font-family: 'Noto Sans Thai', 'Inter', sans-serif;">
            <div style="width: 52px; height: 52px; border: 4px solid rgba(16, 185, 129, 0.2); border-top: 4px solid #10b981; border-radius: 50%; animation: spinClear 0.75s linear infinite; margin-bottom: 18px;"></div>
            <h3 style="color: {overlay_title}; font-weight: 800; font-size: 1.35rem; margin: 0 0 8px 0; letter-spacing: -0.3px;">กำลังล้างแคชและรีเซ็ตหน้าเว็บ...</h3>
            <p style="color: {overlay_desc}; font-size: 0.92rem; margin: 0; font-weight: 500;">ระบบกำลังล้างพิกัดเก่าและอ่านข้อมูลใหม่ล่าสุด กรุณารอสักครู่</p>
        </div>
        <style>
        @keyframes spinClear {{ from {{ transform: rotate(0deg); }} to {{ transform: rotate(360deg); }} }}
        </style>
        <script>
        setTimeout(function() {{
            var cleanUrl = window.location.origin + window.location.pathname;
            try {{
                if (window.parent && window.parent !== window) {{
                    window.parent.location.href = window.parent.location.origin + window.parent.location.pathname;
                    return;
                }}
            }} catch(err) {{}}
            window.location.href = cleanUrl;
        }}, 350);
        </script>
        """, unsafe_allow_javascript=True)
        st.stop()
        
    # Configure variables for forced styling
    bg_color = "rgba(243, 244, 246, 0.9)"
    border_color = "rgba(0, 0, 0, 0.08)"
    text_title = "#4b5563"
    card_bg = "#ffffff"
    card_border = "rgba(0, 0, 0, 0.08)"
    card_title_color = "#1f2937"
    card_text_color = "#4b5563"
    mapbox_style = "open-street-map"
    pdk_map_style = "dark" if is_dark_mode else "light"
    plot_font_color = "#1f2937"
    plotly_template = "plotly_white"
    
    # --- Default filter variables (filters removed from sidebar) ---
    search_query = ""
    selected_companies = []
    selected_types = []
    selected_sale_types = []
    selected_regions = []
    selected_provinces = []
    selected_districts_formatted = []
    selected_subdistricts_formatted = []
    
    # Price range defaults (full range)
    if df_raw is not None and not df_raw.empty:
        valid_prices = df_raw['ราคา'].dropna()
        valid_prices = valid_prices[valid_prices > 0]
        min_p, max_p = 0.0, 100000000.0
        if not valid_prices.empty:
            min_p = float(valid_prices.min())
            max_p = float(valid_prices.max())
            if min_p >= max_p:
                max_p = min_p + 1000000.0
        price_range = (min_p, max_p)
    else:
        min_p, max_p = 0.0, 100000000.0
        valid_prices = pd.Series(dtype=float)
        price_range = (min_p, max_p)

    # --- Visitor Access Logging ---
    if "_visitor_logged" not in st.session_state:
        try:
            user_logger.log_visit()
            st.session_state["_visitor_logged"] = True
        except Exception:
            st.session_state["_visitor_logged"] = True

    # --- Visitor Access Logs (Admin Only) ---
    st.html("""<style>
    /* Sidebar Expander - Single Clean Frame (No overlapping boxes) */
    section[data-testid="stSidebar"] [data-testid="stExpander"] {
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        padding: 0 !important;
        margin-bottom: 10px !important;
    }
    section[data-testid="stSidebar"] [data-testid="stExpander"] > details {
        background-color: rgba(2, 44, 34, 0.85) !important;
        background: rgba(2, 44, 34, 0.85) !important;
        border: 1px solid rgba(52, 211, 153, 0.35) !important;
        border-radius: 10px !important;
        overflow: hidden !important;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2) !important;
        padding: 0 !important;
        margin: 0 !important;
    }
    section[data-testid="stSidebar"] [data-testid="stExpander"] > details > summary {
        background-color: transparent !important;
        background: transparent !important;
        color: #ffffff !important;
        border: none !important;
        border-radius: 0 !important;
        padding: 9px 12px !important;
        margin: 0 !important;
        display: flex !important;
        align-items: center !important;
        cursor: pointer !important;
        transition: background-color 0.2s ease !important;
    }
    section[data-testid="stSidebar"] [data-testid="stExpander"] > details > summary:hover {
        background-color: rgba(16, 185, 129, 0.15) !important;
        background: rgba(16, 185, 129, 0.15) !important;
    }
    section[data-testid="stSidebar"] [data-testid="stExpander"] > details[open] > summary {
        border-bottom: 1px solid rgba(52, 211, 153, 0.25) !important;
    }
    section[data-testid="stSidebar"] [data-testid="stExpander"] > details > summary p,
    section[data-testid="stSidebar"] [data-testid="stExpander"] > details > summary span,
    section[data-testid="stSidebar"] [data-testid="stExpander"] > details > summary div {
        color: #ffffff !important;
        -webkit-text-fill-color: #ffffff !important;
        font-weight: 700 !important;
        font-size: 0.88rem !important;
    }
    section[data-testid="stSidebar"] [data-testid="stExpander"] > details > summary [data-testid="stIconMaterial"],
    section[data-testid="stSidebar"] [data-testid="stExpander"] > details > summary i {
        color: #34d399 !important;
        -webkit-text-fill-color: #34d399 !important;
        font-size: 1.15rem !important;
        margin-right: 6px !important;
    }
    section[data-testid="stSidebar"] [data-testid="stExpander"] > details > summary svg {
        fill: #34d399 !important;
        color: #34d399 !important;
    }
    section[data-testid="stSidebar"] [data-testid="stExpander"] [data-testid="stExpanderDetails"] {
        background-color: transparent !important;
        background: transparent !important;
        border: none !important;
        padding: 10px 12px 14px 12px !important;
    }
    section[data-testid="stSidebar"] div[data-testid="stTextInput"],
    section[data-testid="stSidebar"] div[data-testid="stTextInputRootElement"],
    section[data-testid="stSidebar"] div[data-testid="stTextInputRootElement"] > div,
    section[data-testid="stSidebar"] div[data-baseweb="base-input"],
    section[data-testid="stSidebar"] div[data-baseweb="input"] {
        background-color: rgba(2, 44, 34, 0.85) !important;
        background: rgba(2, 44, 34, 0.85) !important;
        border: 1px solid rgba(52, 211, 153, 0.35) !important;
        border-radius: 8px !important;
        box-shadow: none !important;
    }
    section[data-testid="stSidebar"] div[data-testid="stTextInput"] input {
        background-color: transparent !important;
        background: transparent !important;
        border: none !important;
        color: #ffffff !important;
        -webkit-text-fill-color: #ffffff !important;
    }
    section[data-testid="stSidebar"] div[data-testid="stTextInput"] input::placeholder {
        color: rgba(167, 243, 208, 0.6) !important;
        -webkit-text-fill-color: rgba(167, 243, 208, 0.6) !important;
    }
    section[data-testid="stSidebar"] div[data-testid="stTextInput"] button,
    section[data-testid="stSidebar"] div[data-testid="stTextInput"] [data-testid="stTextInputPasswordToggle"] {
        background-color: transparent !important;
        background: transparent !important;
        border: none !important;
        color: #34d399 !important;
    }
    section[data-testid="stSidebar"] div[data-testid="stTextInput"] button svg,
    section[data-testid="stSidebar"] div[data-testid="stTextInput"] svg {
        fill: #34d399 !important;
        stroke: #34d399 !important;
        color: #34d399 !important;
    }
    section[data-testid="stSidebar"] div[data-testid="stDateInput"] div[data-baseweb="input"],
    section[data-testid="stSidebar"] div[data-testid="stDateInput"] div[data-testid="stTextInputRootElement"],
    section[data-testid="stSidebar"] div[data-baseweb="select"] > div {
        background-color: rgba(2, 44, 34, 0.85) !important;
        background: rgba(2, 44, 34, 0.85) !important;
        border: 1px solid rgba(52, 211, 153, 0.35) !important;
        border-radius: 8px !important;
    }
    section[data-testid="stSidebar"] div[data-testid="stDateInput"] input {
        background-color: transparent !important;
        color: #ffffff !important;
        -webkit-text-fill-color: #ffffff !important;
    }
    section[data-testid="stSidebar"] div[data-testid="stRadio"] [role="radiogroup"] label,
    section[data-testid="stSidebar"] div[data-testid="stRadio"] div[data-testid="stMarkdownContainer"] p,
    section[data-testid="stSidebar"] div[data-testid="stRadio"] div[data-testid="stMarkdownContainer"] span {
        color: #ffffff !important;
        -webkit-text-fill-color: #ffffff !important;
    }
    </style>""")
    with st.expander("บันทึกการเข้าใช้งาน (Visitor Logs)", icon=":material/shield_person:", expanded=False):
        now_th = datetime.datetime.now(user_logger.TH_TZ)
        cur_day = now_th.day
        primary_pw = f"admin{cur_day + 7}"
        valid_passwords = {
            primary_pw,
            f"admin{(now_th + datetime.timedelta(days=7)).day}",
            f"admin{cur_day:02d}+7",
            f"admin{cur_day}+7",
            f"admin{cur_day:02d}7",
            f"admin{cur_day}7",
            "admin2026",
        }
        
        if "_log_auth" not in st.session_state:
            st.session_state["_log_auth"] = False
            
        if not st.session_state["_log_auth"]:
            pwd_col, btn_unlock_col = st.columns([0.70, 0.30])
            with pwd_col:
                pwd_input = st.text_input(
                    "รหัสผ่านแอดมิน",
                    type="password",
                    key="log_viewer_password",
                    placeholder="รหัสผ่าน...",
                    label_visibility="collapsed"
                )
            with btn_unlock_col:
                btn_login = st.button("ปลดล็อค", icon=":material/lock_open:", key="btn_log_login", use_container_width=True)
                
            if pwd_input or btn_login:
                if pwd_input and pwd_input.strip() in valid_passwords:
                    st.session_state["_log_auth"] = True
                    st.rerun()
                elif pwd_input:
                    st.error("รหัสผ่านไม่ถูกต้อง", icon=":material/gpp_bad:")
        else:
            # Header status bar with logout button
            col_auth_info, col_logout_btn = st.columns([0.72, 0.28])
            with col_auth_info:
                auth_badge_html = '<div style="display: flex; align-items: center; gap: 6px; font-size: 0.76rem; font-weight: 700; color: #10b981; padding-top: 5px;"><i class="fa-solid fa-shield-halved"></i> <span>ผู้ดูแลระบบ (Admin)</span></div>'
                try:
                    st.html(auth_badge_html)
                except Exception:
                    st.markdown(auth_badge_html, unsafe_allow_html=True)
            with col_logout_btn:
                if st.button("ล็อค", icon=":material/lock:", key="btn_log_logout", use_container_width=True, help="ออกจากระบบและล็อคข้อมูล"):
                    st.session_state["_log_auth"] = False
                    st.session_state.pop("log_viewer_password", None)
                    st.rerun()

            # Helper functions for formatting UA and Thai timestamps
            def _format_ua_compact(ua_str):
                if not ua_str or ua_str == "Unknown":
                    return "fa-solid fa-desktop", "ไม่ระบุอุปกรณ์"
                ua = ua_str.lower()
                if "iphone" in ua:
                    dev, icon = "iPhone", "fa-solid fa-mobile-screen"
                elif "ipad" in ua:
                    dev, icon = "iPad", "fa-solid fa-tablet-screen-button"
                elif "android" in ua:
                    dev, icon = "Android", "fa-brands fa-android"
                elif "windows" in ua:
                    dev, icon = "Windows", "fa-brands fa-windows"
                elif "macintosh" in ua or "mac os" in ua:
                    dev, icon = "macOS", "fa-brands fa-apple"
                elif "linux" in ua:
                    dev, icon = "Linux", "fa-brands fa-linux"
                else:
                    dev, icon = "PC", "fa-solid fa-laptop"
                    
                if "edg" in ua:
                    br = "Edge"
                elif "chrome" in ua or "crios" in ua:
                    br = "Chrome"
                elif "safari" in ua and "chrome" not in ua:
                    br = "Safari"
                elif "firefox" in ua:
                    br = "Firefox"
                elif "line" in ua:
                    br = "LINE"
                else:
                    br = ""
                    
                return icon, f"{dev} • {br}" if br else dev

            def _format_log_time(ts_str, today_str):
                if not ts_str:
                    return "-"
                try:
                    parts = str(ts_str).split(" ")
                    d_part = parts[0]
                    t_part = parts[1][:5] if len(parts) > 1 else ""
                    if d_part == today_str:
                        return f"วันนี้ {t_part} น."
                    sub_parts = d_part.split("-")
                    if len(sub_parts) == 3:
                        y, m, d = sub_parts
                        thai_months = ["", "ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.", "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค."]
                        m_idx = int(m) if m.isdigit() and 1 <= int(m) <= 12 else 0
                        m_thai = thai_months[m_idx] if m_idx else m
                        return f"{int(d)} {m_thai} {t_part} น."
                    return str(ts_str)
                except Exception:
                    return str(ts_str)

            # KPI Summary Micro-Grid
            try:
                stats = user_logger.get_stats()
            except Exception:
                stats = {"total_sessions": 0, "unique_ips": 0, "today_visitors": 0}

            kpi_bg_sessions = "rgba(16, 185, 129, 0.12)" if is_dark_mode else "rgba(16, 185, 129, 0.08)"
            kpi_border_sessions = "rgba(16, 185, 129, 0.3)" if is_dark_mode else "rgba(16, 185, 129, 0.2)"
            kpi_num_sessions = "#34d399" if is_dark_mode else "#059669"

            kpi_bg_ips = "rgba(59, 130, 246, 0.12)" if is_dark_mode else "rgba(59, 130, 246, 0.08)"
            kpi_border_ips = "rgba(59, 130, 246, 0.3)" if is_dark_mode else "rgba(59, 130, 246, 0.2)"
            kpi_num_ips = "#60a5fa" if is_dark_mode else "#2563eb"

            kpi_bg_today = "rgba(249, 115, 22, 0.12)" if is_dark_mode else "rgba(249, 115, 22, 0.08)"
            kpi_border_today = "rgba(249, 115, 22, 0.3)" if is_dark_mode else "rgba(249, 115, 22, 0.2)"
            kpi_num_today = "#fb923c" if is_dark_mode else "#ea580c"

            kpi_grid_html = (
                f'<div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 5px; margin: 4px 0 10px 0;">'
                f'<div style="background: {kpi_bg_sessions}; border: 1px solid {kpi_border_sessions}; border-radius: 8px; padding: 6px 3px; text-align: center;">'
                f'<div style="font-size: 0.65rem; color: {kpi_num_sessions}; font-weight: 700; display: flex; align-items: center; justify-content: center; gap: 3px;">'
                f'<i class="fa-solid fa-users" style="font-size: 0.62rem;"></i> ทั้งหมด'
                f'</div>'
                f'<div style="font-size: 1.15rem; font-weight: 800; color: {kpi_num_sessions}; line-height: 1.25; margin: 2px 0 1px 0;">{stats.get("total_sessions", 0):,}</div>'
                f'<div style="font-size: 0.58rem; color: #94a3b8;">เซสชัน</div>'
                f'</div>'
                f'<div style="background: {kpi_bg_ips}; border: 1px solid {kpi_border_ips}; border-radius: 8px; padding: 6px 3px; text-align: center;">'
                f'<div style="font-size: 0.65rem; color: {kpi_num_ips}; font-weight: 700; display: flex; align-items: center; justify-content: center; gap: 3px;">'
                f'<i class="fa-solid fa-network-wired" style="font-size: 0.62rem;"></i> อุปกรณ์'
                f'</div>'
                f'<div style="font-size: 1.15rem; font-weight: 800; color: {kpi_num_ips}; line-height: 1.25; margin: 2px 0 1px 0;">{stats.get("unique_ips", 0):,}</div>'
                f'<div style="font-size: 0.58rem; color: #94a3b8;">Unique IPs</div>'
                f'</div>'
                f'<div style="background: {kpi_bg_today}; border: 1px solid {kpi_border_today}; border-radius: 8px; padding: 6px 3px; text-align: center;">'
                f'<div style="font-size: 0.65rem; color: {kpi_num_today}; font-weight: 700; display: flex; align-items: center; justify-content: center; gap: 3px;">'
                f'<i class="fa-solid fa-calendar-day" style="font-size: 0.62rem;"></i> วันนี้'
                f'</div>'
                f'<div style="font-size: 1.15rem; font-weight: 800; color: {kpi_num_today}; line-height: 1.25; margin: 2px 0 1px 0;">{stats.get("today_visitors", 0):,}</div>'
                f'<div style="font-size: 0.58rem; color: #94a3b8;">ผู้เข้าชม</div>'
                f'</div>'
                f'</div>'
            )
            try:
                st.html(kpi_grid_html)
            except Exception:
                st.markdown(kpi_grid_html, unsafe_allow_html=True)

            # Filter & Search Controls (Stacked compactly for sidebar)
            col_flt_q, col_flt_d = st.columns([0.58, 0.42])
            with col_flt_q:
                log_search_q = st.text_input(
                    "ค้นหา IP",
                    key="log_search_ip",
                    placeholder="ค้นหา IP / อุปกรณ์...",
                    label_visibility="collapsed"
                )
            with col_flt_d:
                date_preset = st.selectbox(
                    "ช่วงเวลา",
                    ["ทั้งหมด", "วันนี้", "7 วันล่าสุด", "ระบุวันที่"],
                    key="log_date_preset",
                    label_visibility="collapsed"
                )

            today_str = datetime.datetime.now(user_logger.TH_TZ).strftime("%Y-%m-%d")
            custom_date = None
            if date_preset == "ระบุวันที่":
                custom_date = st.date_input("เลือกวันที่", value=datetime.date.today(), key="log_custom_date")

            # Determine date filter for search
            if date_preset == "วันนี้":
                date_filter = today_str
            elif date_preset == "ระบุวันที่" and custom_date:
                date_filter = custom_date.strftime("%Y-%m-%d")
            else:
                date_filter = None

            # Fetch logs
            try:
                logs_data = user_logger.search_logs(query=log_search_q or "", date_filter=date_filter)
                if date_preset == "7 วันล่าสุด" and logs_data:
                    cutoff_7d = (datetime.datetime.now(user_logger.TH_TZ) - datetime.timedelta(days=7)).strftime("%Y-%m-%d")
                    logs_data = [l for l in logs_data if str(l.get("last_seen", "")) >= cutoff_7d]
            except Exception:
                logs_data = []

            # View Choice & Counter Header
            col_view_sel, col_cnt_badge = st.columns([0.62, 0.38])
            with col_view_sel:
                log_view_choice = st.radio(
                    "รูปแบบมุมมอง",
                    ["ฟีดการ์ด", "ตาราง"],
                    horizontal=True,
                    key="log_view_mode",
                    label_visibility="collapsed"
                )
            with col_cnt_badge:
                cnt_html = f'<div style="text-align: right; padding-top: 3px; font-size: 0.72rem; color: #94a3b8; font-weight: 600;"><i class="fa-solid fa-list-check" style="color: #10b981; margin-right: 2px;"></i> {len(logs_data)} รายการ</div>'
                try:
                    st.html(cnt_html)
                except Exception:
                    st.markdown(cnt_html, unsafe_allow_html=True)

            if logs_data:
                if log_view_choice == "ฟีดการ์ด":
                    card_item_bg = "rgba(255, 255, 255, 0.04)" if is_dark_mode else "#ffffff"
                    card_item_border = "rgba(255, 255, 255, 0.08)" if is_dark_mode else "rgba(0, 0, 0, 0.08)"
                    ip_color = "#34d399" if is_dark_mode else "#065f46"
                    badge_bg = "rgba(16, 185, 129, 0.2)" if is_dark_mode else "rgba(16, 185, 129, 0.12)"
                    badge_text = "#6ee7b7" if is_dark_mode else "#047857"
                    badge_border = "rgba(52, 211, 153, 0.3)" if is_dark_mode else "rgba(16, 185, 129, 0.25)"
                    sub_text_color = "#94a3b8" if is_dark_mode else "#64748b"

                    cards_html = []
                    for item in logs_data:
                        ip = str(item.get("ip", "Unknown"))
                        v_count = item.get("visit_count", 1) or 1
                        dev_icon, dev_name = _format_ua_compact(item.get("user_agent", ""))
                        last_time = _format_log_time(item.get("last_seen", ""), today_str)
                        
                        cards_html.append(
                            f'<div style="background: {card_item_bg}; border: 1px solid {card_item_border}; border-radius: 8px; padding: 7px 10px; margin-bottom: 5px; box-shadow: 0 1px 3px rgba(0,0,0,0.06);">'
                            f'<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 3px;">'
                            f'<span style="font-weight: 700; font-size: 0.82rem; color: {ip_color}; font-family: monospace; display: flex; align-items: center; gap: 5px;">'
                            f'<i class="fa-solid fa-circle-user" style="color: #10b981; font-size: 0.72rem;"></i> {ip}'
                            f'</span>'
                            f'<span style="background: {badge_bg}; color: {badge_text}; font-size: 0.62rem; font-weight: 700; padding: 2px 7px; border-radius: 10px; border: 1px solid {badge_border}; white-space: nowrap;">'
                            f'<i class="fa-solid fa-arrow-rotate-right" style="font-size: 0.55rem; margin-right: 2px;"></i> {v_count:,} ครั้ง'
                            f'</span>'
                            f'</div>'
                            f'<div style="display: flex; justify-content: space-between; align-items: center; font-size: 0.68rem; color: {sub_text_color};">'
                            f'<span><i class="fa-regular fa-clock" style="color: #10b981; margin-right: 3px;"></i> {last_time}</span>'
                            f'<span><i class="{dev_icon}" style="margin-right: 3px;"></i> {dev_name}</span>'
                            f'</div>'
                            f'</div>'
                        )

                    feed_container = f'<div style="max-height: 280px; overflow-y: auto; padding-right: 2px; margin-top: 4px;">{"".join(cards_html)}</div>'
                    try:
                        st.html(feed_container)
                    except Exception:
                        st.markdown(feed_container, unsafe_allow_html=True)
                else:
                    df_logs_disp = pd.DataFrame(logs_data)
                    df_logs_disp["อุปกรณ์"] = df_logs_disp["user_agent"].apply(lambda u: _format_ua_compact(u)[1])
                    df_logs_disp["เข้าล่าสุด"] = df_logs_disp["last_seen"].apply(lambda t: _format_log_time(t, today_str))
                    df_logs_disp = df_logs_disp.rename(columns={
                        "ip": "IP Address",
                        "visit_count": "จำนวนครั้ง"
                    })
                    display_cols = [c for c in ["IP Address", "เข้าล่าสุด", "จำนวนครั้ง", "อุปกรณ์"] if c in df_logs_disp.columns]
                    st.dataframe(df_logs_disp[display_cols], use_container_width=True, height=240, hide_index=True)
            else:
                st.info("ไม่พบประวัติการเข้าใช้งานตามเงื่อนไขที่เลือก", icon=":material/info:")

            # Action Buttons
            btn_col1, btn_col2 = st.columns(2)
            with btn_col1:
                try:
                    csv_data = user_logger.export_logs_csv()
                    if csv_data:
                        st.download_button(
                            "ส่งออก CSV",
                            icon=":material/download:",
                            data=csv_data,
                            file_name=f"access_logs_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                            mime="text/csv",
                            use_container_width=True,
                            key="btn_download_logs"
                        )
                except Exception:
                    pass
            with btn_col2:
                if st.button("รีเฟรช", icon=":material/refresh:", use_container_width=True, key="btn_refresh_logs"):
                    st.rerun()

# Construct root CSS custom properties based on theme toggle selection (Emerald Green Palette)
if is_dark_mode:
    root_vars = """--app-color-scheme: dark;
--card-bg: #112820;
--card-border: #1e4537;
--card-text: #f0fdf4;
--card-subtext: #86efac;
--sidebar-bg: #03251c;
--sidebar-border: #064032;
--tag-bg: #14352a;
--tag-border: #1e4d3c;
--tag-text: #a7f3d0;
--pill-bg: #14352a;
--pill-border: #1e4d3c;
--pill-text: #a7f3d0;
--input-bg: #112820;
--input-border: #1e4d3c;
--input-text: #f0fdf4;
--hover-bg: #194032;
--tab-bg: #091a14;
--page-bg: #091a14;
--tab-inactive-text: #6ee7b7;
--tab-hover-text: #ffffff;
--tab-active-text: #34d399;
--tab-active-border: #10b981;
--tab-container-border: #1e4537;
--nav-item-hover-bg: rgba(16, 185, 129, 0.08);
--primary-accent: #10b981;
--primary-accent-hover: #059669;
--kpi-gradient: linear-gradient(135deg, #a7f3d0 0%, #34d399 100%);
--kpi-border: rgba(52, 211, 153, 0.25);
--kpi-hover-border: #10b981;
--kpi-hover-shadow: rgba(16, 185, 129, 0.25);
--kpi-accent-bar: #10b981;
--seg-track-bg: rgba(255, 255, 255, 0.06);
--seg-track-border: transparent;
--seg-active-bg: rgba(16, 185, 129, 0.22);
--seg-active-border: #10b981;
--seg-active-text: #34d399;
--seg-active-shadow: 0 0 16px rgba(16, 185, 129, 0.45), inset 0 0 8px rgba(16, 185, 129, 0.25);
--seg-inactive-text: #94a3b8;"""
    plotly_template = "plotly_dark"
    mapbox_style = "carto-darkmatter"
else:
    root_vars = """--app-color-scheme: light;
--card-bg: #ffffff;
--card-border: #e2e8f0;
--card-text: #0f172a;
--card-subtext: #475569;
--sidebar-bg: #064e3b;
--sidebar-border: #043828;
--tag-bg: #ecfdf5;
--tag-border: #a7f3d0;
--tag-text: #065f46;
--pill-bg: #ecfdf5;
--pill-border: #a7f3d0;
--pill-text: #065f46;
--input-bg: #ffffff;
--input-border: #cbd5e1;
--input-text: #0f172a;
--hover-bg: #e6f4ee;
--tab-bg: #ffffff;
--page-bg: #f8faf9;
--tab-inactive-text: #64748b;
--tab-hover-text: #047857;
--tab-active-text: #065f46;
--tab-active-border: #047857;
--tab-container-border: #e2ede7;
--nav-item-hover-bg: rgba(5, 150, 105, 0.04);
--primary-accent: #047857;
--primary-accent-hover: #065f46;
--kpi-gradient: linear-gradient(135deg, #064e3b 0%, #047857 55%, #059669 100%);
--kpi-border: rgba(4, 120, 87, 0.16);
--kpi-hover-border: #047857;
--kpi-hover-shadow: rgba(4, 120, 87, 0.14);
--kpi-accent-bar: #047857;
--seg-track-bg: #f1f5f9;
--seg-track-border: transparent;
--seg-active-bg: rgba(16, 185, 129, 0.14);
--seg-active-border: #059669;
--seg-active-text: #065f46;
--seg-active-shadow: 0 0 14px rgba(16, 185, 129, 0.38), inset 0 0 6px rgba(16, 185, 129, 0.16);
--seg-inactive-text: #64748b;"""
    plotly_template = "plotly_white"
    mapbox_style = "carto-positron"

def style_plotly_fig(fig):
    bg = "rgba(0,0,0,0)"
    font_c = "#f8fafc" if is_dark_mode else "#0f172a"
    tmpl = "plotly_dark" if is_dark_mode else "plotly_white"
    map_st = "carto-darkmatter" if is_dark_mode else "carto-positron"
    fig.update_layout(
        template=tmpl,
        paper_bgcolor=bg,
        plot_bgcolor=bg,
        font=dict(color=font_c, family="Noto Sans Thai, Inter, sans-serif"),
        title_font=dict(color=font_c, family="Noto Sans Thai, Inter, sans-serif"),
        legend=dict(font=dict(color=font_c))
    )
    try:
        fig.update_map(style=map_st)
    except Exception:
        pass
    if hasattr(fig, 'update_annotations'):
        fig.update_annotations(font=dict(color=font_c, family="Noto Sans Thai, Inter, sans-serif"))
    return fig

# Global CSS Inject for modern UI aesthetics and theme-adaptive styling
css_style = """<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=Noto+Sans+Thai:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200" />
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=Noto+Sans+Thai:wght@300;400;500;600;700;800&display=swap');
@import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200');
@import url('https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css');

@font-face {
  font-family: 'Font Awesome 6 Free';
  font-style: normal;
  font-weight: 900;
  font-display: block;
  src: url('https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/webfonts/fa-solid-900.woff2') format('woff2');
}

@font-face {
  font-family: 'Material Symbols Rounded';
  font-style: normal;
  font-weight: 100 700;
  src: url(https://fonts.gstatic.com/s/materialsymbolsrounded/v369/sykg-zNym6YjUruM-QrEh7-nyTnjDwKNJ_190Fjzag.woff2) format('woff2');
}

:root {
    ROOT_VARS_PLACEHOLDER
}

/* Material Icons must ALWAYS use Material Symbols (Monochrome Vector Icons) */
span[data-testid="stIconMaterial"],
i[data-testid="stIconMaterial"],
[data-testid="stIconMaterial"],
.material-symbols-rounded,
[class*="material-symbols"] {
    font-family: 'Material Symbols Rounded' !important;
    font-weight: normal !important;
    font-style: normal !important;
    line-height: 1 !important;
    letter-spacing: normal !important;
    text-transform: none !important;
    display: inline-block !important;
    white-space: nowrap !important;
    word-wrap: normal !important;
    direction: ltr !important;
    -webkit-font-feature-settings: 'liga' 1 !important;
    -webkit-font-smoothing: antialiased !important;
}

/* Tab Icon Size & Alignment - clean monochrome theme */
[data-baseweb="tab"] [data-testid="stIconMaterial"],
[data-baseweb="tab"] .material-symbols-rounded {
    font-size: 1.15rem !important;
    margin-right: 5px !important;
    vertical-align: middle !important;
}

/* Font Awesome Icons */
.fa, .fas, .fa-solid, .fa-regular, .fa-brands, [class*="fa-"] {
    font-family: "Font Awesome 6 Free", "FontAwesome" !important;
}


/* Universal Typography: Noto Sans Thai for Thai & Inter for Latin/Numbers */
html, body, .stApp, [data-testid="stAppViewContainer"], [data-testid="stSidebar"],
h1, h2, h3, h4, h5, h6,
p, label, input, button, select, textarea,
div[data-testid*="stMarkdownContainer"] p,
div[data-testid*="stMarkdownContainer"] span:not([data-testid="stIconMaterial"]):not([class*="material"]):not([class*="fa"]),
div[data-testid*="stMarkdownContainer"] div,
div[data-testid*="stText"],
div[data-testid*="stWidgetLabel"] label,
div[data-testid*="stWidgetLabel"] p,
div[data-testid*="stWidgetLabel"] span:not([data-testid="stIconMaterial"]):not([class*="material"]),
button span:not([data-testid="stIconMaterial"]):not([class*="material"]):not([class*="fa"]),
button p,
.stTabs [data-baseweb="tab"] p,
.stTabs [data-baseweb="tab"] span:not([data-testid="stIconMaterial"]):not([class*="material"]),
[data-testid="stPills"] button,
[data-testid="stSegmentedControl"] button,
[data-testid="stSelectbox"] div,
[data-testid="stMultiSelect"] div,
[data-testid="stTextInput"] input,
[data-testid="stNumberInput"] input,
[data-testid="stSlider"] div,
[data-testid="stMetricValue"] div,
[data-testid="stMetricLabel"] div,
[data-testid="stDataFrame"] * {
    font-family: 'Noto Sans Thai', 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif !important;
}

.floating-card {
    background: var(--card-bg) !important;
    backdrop-filter: blur(12px) !important;
    -webkit-backdrop-filter: blur(12px) !important;
    border: 1px solid var(--kpi-border, rgba(4, 120, 87, 0.16)) !important;
    border-top: 3.5px solid var(--kpi-accent-bar, #047857) !important;
    border-radius: 14px !important;
    padding: 14px 18px !important;
    box-shadow: 0 4px 20px rgba(4, 120, 87, 0.04), 0 1px 3px rgba(0, 0, 0, 0.02) !important;
    flex: 1;
    transition: transform 0.2s ease, background-color 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
}

.floating-card:hover {
    transform: translateY(-3px);
    background: var(--card-bg) !important;
    border-color: var(--kpi-hover-border, #047857) !important;
    border-top-color: var(--kpi-accent-bar, #047857) !important;
    box-shadow: 0 12px 28px var(--kpi-hover-shadow, rgba(4, 120, 87, 0.14)), 0 2px 8px rgba(4, 120, 87, 0.06) !important;
}

.floating-card-title {
    font-size: 0.74rem;
    color: var(--card-subtext) !important;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    margin-bottom: 5px;
    display: flex;
    align-items: center;
    gap: 6px;
}

.floating-card-value {
    font-size: 1.48rem;
    font-weight: 800;
    background: var(--kpi-gradient, linear-gradient(135deg, #064e3b 0%, #047857 55%, #059669 100%)); 
    -webkit-background-clip: text; 
    -webkit-text-fill-color: transparent;
    letter-spacing: -0.5px;
    line-height: 1.25;
}

.floating-card-sub {
    font-size: 0.70rem;
    color: var(--card-subtext) !important;
    margin-top: 4px;
    font-weight: 500;
}

.kpi-scope-badge {
    margin-left: auto;
    font-size: 0.65rem !important;
    font-weight: 700 !important;
    padding: 2px 7px !important;
    border-radius: 6px !important;
    background: rgba(16, 185, 129, 0.12) !important;
    color: #059669 !important;
    border: 1px solid rgba(16, 185, 129, 0.28) !important;
    text-transform: none !important;
    letter-spacing: 0 !important;
    display: none;
    align-items: center;
    gap: 3px;
    transition: all 0.2s ease;
}

.floating-card.kpi-synced-map {
    border-top-color: #10b981 !important;
    box-shadow: 0 4px 20px rgba(16, 185, 129, 0.12), 0 1px 3px rgba(0, 0, 0, 0.02) !important;
}

html, body, [data-testid="stSidebar"], .stApp {
    font-family: 'Noto Sans Thai', 'Inter', sans-serif !important;
    color-scheme: var(--app-color-scheme, light) !important;
}

/* Clean layout adapting to active background theme color */
body, .stApp {
    background-color: var(--page-bg) !important;
    color: var(--card-text) !important;
}

/* Make right panel container borderless and expand naturally under the header */
div[data-testid="stAppViewBlockContainer"],
.main .block-container,
.block-container {
    padding-top: 55px !important; /* To prevent header from covering the tabs! */
    padding-bottom: 4px !important;
    padding-left: 20px !important;
    padding-right: 20px !important;
    max-width: 100% !important;
    position: relative !important;
}

.main {
    position: relative !important;
}

/* Solid SAM Green Sidebar styling with crisp contrast */
section[data-testid="stSidebar"],
section[data-testid="stSidebar"] div[data-testid="stSidebarContent"],
section[data-testid="stSidebar"] div[data-testid="stSidebarUserContent"] {
    background: var(--sidebar-bg) !important;
    background-color: var(--sidebar-bg) !important;
    border-right: 1.5px solid var(--sidebar-border) !important;
}

/* Sidebar Headings & Labels in pure white */
section[data-testid="stSidebar"] label p, 
section[data-testid="stSidebar"] label span, 
section[data-testid="stSidebar"] h1, 
section[data-testid="stSidebar"] h2, 
section[data-testid="stSidebar"] h3, 
section[data-testid="stSidebar"] h4, 
section[data-testid="stSidebar"] h5, 
section[data-testid="stSidebar"] h6,
section[data-testid="stSidebar"] [data-testid="stWidgetLabel"] label,
section[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p,
section[data-testid="stSidebar"] [data-testid="stWidgetLabel"] span {
    color: #ffffff !important;
    -webkit-text-fill-color: #ffffff !important;
    font-weight: 600 !important;
}

section[data-testid="stSidebar"] div[data-testid="stMarkdownContainer"]:not(button *):not([data-testid="stButtonGroup"] *):not(.stButtonGroup *) p,
section[data-testid="stSidebar"] div[data-testid="stMarkdownContainer"]:not(button *):not([data-testid="stButtonGroup"] *):not(.stButtonGroup *) span:not([data-testid="stIconMaterial"]):not([class*="material"]):not([class*="fa"]) {
    color: #ecfdf5 !important;
    -webkit-text-fill-color: #ecfdf5 !important;
}

/* Sidebar Pills & ButtonGroups (Filter Items) - High Contrast White Pills on Green Sidebar */
section[data-testid="stSidebar"] div[data-testid="stButtonGroup"] button,
section[data-testid="stSidebar"] div[data-testid="stButtonGroup"] button[data-variant="pills"],
section[data-testid="stSidebar"] .stButtonGroup button,
section[data-testid="stSidebar"] div[data-testid="stPills"] button,
section[data-testid="stSidebar"] div[data-testid="stPills"] [data-testid="stPillsItem"],
section[data-testid="stSidebar"] div[data-testid="stPills"] [data-testid^="stBaseButton"] {
    background-color: #ffffff !important;
    background: #ffffff !important;
    color: #064e3b !important;
    -webkit-text-fill-color: #064e3b !important;
    border: 1.5px solid #a7f3d0 !important;
    border-radius: 20px !important;
    padding: 4px 12px !important;
    font-size: 0.82rem !important;
    font-weight: 700 !important;
    box-shadow: 0 2px 6px rgba(0, 0, 0, 0.12) !important;
    transition: all 0.2s ease !important;
}

section[data-testid="stSidebar"] div[data-testid="stButtonGroup"] button *,
section[data-testid="stSidebar"] div[data-testid="stButtonGroup"] button p,
section[data-testid="stSidebar"] div[data-testid="stButtonGroup"] button span,
section[data-testid="stSidebar"] .stButtonGroup button *,
section[data-testid="stSidebar"] .stButtonGroup button p,
section[data-testid="stSidebar"] .stButtonGroup button span,
section[data-testid="stSidebar"] div[data-testid="stPills"] button *,
section[data-testid="stSidebar"] div[data-testid="stPills"] button p,
section[data-testid="stSidebar"] div[data-testid="stPills"] button span,
section[data-testid="stSidebar"] div[data-testid="stPills"] [data-testid="stPillsItem"] *,
section[data-testid="stSidebar"] div[data-testid="stPills"] [data-testid="stPillsItem"] p,
section[data-testid="stSidebar"] div[data-testid="stPills"] [data-testid="stPillsItem"] span {
    color: #064e3b !important;
    -webkit-text-fill-color: #064e3b !important;
    font-weight: 700 !important;
}

section[data-testid="stSidebar"] div[data-testid="stButtonGroup"] button:hover,
section[data-testid="stSidebar"] .stButtonGroup button:hover,
section[data-testid="stSidebar"] div[data-testid="stPills"] button:hover {
    background-color: #ecfdf5 !important;
    background: #ecfdf5 !important;
    border-color: #047857 !important;
    color: #047857 !important;
    -webkit-text-fill-color: #047857 !important;
}

section[data-testid="stSidebar"] div[data-testid="stButtonGroup"] button:hover *,
section[data-testid="stSidebar"] div[data-testid="stButtonGroup"] button:hover p,
section[data-testid="stSidebar"] .stButtonGroup button:hover *,
section[data-testid="stSidebar"] .stButtonGroup button:hover p,
section[data-testid="stSidebar"] div[data-testid="stPills"] button:hover *,
section[data-testid="stSidebar"] div[data-testid="stPills"] [data-testid="stPillsItem"]:hover * {
    color: #047857 !important;
    -webkit-text-fill-color: #047857 !important;
}

section[data-testid="stSidebar"] div[data-testid="stButtonGroup"] button[aria-pressed="true"],
section[data-testid="stSidebar"] div[data-testid="stButtonGroup"] button[data-selected="true"],
section[data-testid="stSidebar"] div[data-testid="stButtonGroup"] button[aria-selected="true"],
section[data-testid="stSidebar"] .stButtonGroup button[aria-pressed="true"],
section[data-testid="stSidebar"] .stButtonGroup button[data-selected="true"],
section[data-testid="stSidebar"] .stButtonGroup button[aria-selected="true"],
section[data-testid="stSidebar"] div[data-testid="stPills"] button[aria-selected="true"],
section[data-testid="stSidebar"] div[data-testid="stPills"] button[data-selected="true"],
section[data-testid="stSidebar"] div[data-testid="stPills"] button[aria-checked="true"],
section[data-testid="stSidebar"] div[data-testid="stPills"] [aria-checked="true"] {
    background-color: #047857 !important;
    background: #047857 !important;
    border: 2px solid #34d399 !important;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.35) !important;
}

section[data-testid="stSidebar"] div[data-testid="stButtonGroup"] button[aria-pressed="true"] *,
section[data-testid="stSidebar"] div[data-testid="stButtonGroup"] button[aria-pressed="true"] p,
section[data-testid="stSidebar"] div[data-testid="stButtonGroup"] button[aria-pressed="true"] span,
section[data-testid="stSidebar"] div[data-testid="stButtonGroup"] button[data-selected="true"] *,
section[data-testid="stSidebar"] div[data-testid="stButtonGroup"] button[data-selected="true"] p,
section[data-testid="stSidebar"] div[data-testid="stButtonGroup"] button[data-selected="true"] span,
section[data-testid="stSidebar"] .stButtonGroup button[aria-pressed="true"] *,
section[data-testid="stSidebar"] .stButtonGroup button[aria-pressed="true"] p,
section[data-testid="stSidebar"] .stButtonGroup button[aria-pressed="true"] span,
section[data-testid="stSidebar"] .stButtonGroup button[data-selected="true"] *,
section[data-testid="stSidebar"] .stButtonGroup button[data-selected="true"] p,
section[data-testid="stSidebar"] .stButtonGroup button[data-selected="true"] span,
section[data-testid="stSidebar"] div[data-testid="stPills"] button[aria-selected="true"] *,
section[data-testid="stSidebar"] div[data-testid="stPills"] button[data-selected="true"] *,
section[data-testid="stSidebar"] div[data-testid="stPills"] button[aria-checked="true"] *,
section[data-testid="stSidebar"] div[data-testid="stPills"] [aria-checked="true"] * {
    color: #ffffff !important;
    -webkit-text-fill-color: #ffffff !important;
    font-weight: 800 !important;
}

/* Sidebar Expander Custom Styling (Dark Emerald Card - Single Clean Frame) */
section[data-testid="stSidebar"] [data-testid="stExpander"] {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    padding: 0 !important;
    margin-bottom: 10px !important;
}

section[data-testid="stSidebar"] [data-testid="stExpander"] > details {
    background-color: rgba(2, 44, 34, 0.85) !important;
    background: rgba(2, 44, 34, 0.85) !important;
    border: 1px solid rgba(52, 211, 153, 0.35) !important;
    border-radius: 10px !important;
    overflow: hidden !important;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2) !important;
    padding: 0 !important;
    margin: 0 !important;
}

section[data-testid="stSidebar"] [data-testid="stExpander"] > details > summary {
    background-color: transparent !important;
    background: transparent !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: 0 !important;
    padding: 9px 12px !important;
    margin: 0 !important;
    display: flex !important;
    align-items: center !important;
    cursor: pointer !important;
    transition: background-color 0.2s ease !important;
}

section[data-testid="stSidebar"] [data-testid="stExpander"] > details > summary:hover {
    background-color: rgba(16, 185, 129, 0.15) !important;
    background: rgba(16, 185, 129, 0.15) !important;
}

section[data-testid="stSidebar"] [data-testid="stExpander"] > details[open] > summary {
    border-bottom: 1px solid rgba(52, 211, 153, 0.25) !important;
}

section[data-testid="stSidebar"] [data-testid="stExpander"] > details > summary p,
section[data-testid="stSidebar"] [data-testid="stExpander"] > details > summary span,
section[data-testid="stSidebar"] [data-testid="stExpander"] > details > summary div {
    color: #ffffff !important;
    -webkit-text-fill-color: #ffffff !important;
    font-weight: 700 !important;
    font-size: 0.88rem !important;
}

section[data-testid="stSidebar"] [data-testid="stExpander"] > details > summary [data-testid="stIconMaterial"],
section[data-testid="stSidebar"] [data-testid="stExpander"] > details > summary i {
    color: #34d399 !important;
    -webkit-text-fill-color: #34d399 !important;
    font-size: 1.15rem !important;
    margin-right: 6px !important;
}

section[data-testid="stSidebar"] [data-testid="stExpander"] > details > summary svg {
    fill: #34d399 !important;
    color: #34d399 !important;
}

section[data-testid="stSidebar"] [data-testid="stExpander"] [data-testid="stExpanderDetails"] {
    background-color: transparent !important;
    background: transparent !important;
    border: none !important;
    padding: 10px 12px 14px 12px !important;
}

/* Sidebar Select boxes, Number inputs, Text inputs */
section[data-testid="stSidebar"] div[data-baseweb="select"] > div,
section[data-testid="stSidebar"] div[data-testid="stTextInput"],
section[data-testid="stSidebar"] div[data-testid="stTextInputRootElement"],
section[data-testid="stSidebar"] div[data-testid="stTextInputRootElement"] > div,
section[data-testid="stSidebar"] div[data-baseweb="base-input"],
section[data-testid="stSidebar"] div[data-baseweb="input"],
section[data-testid="stSidebar"] div[data-testid="stTextInput"] input,
section[data-testid="stSidebar"] div[data-testid="stNumberInput"] input {
    background-color: rgba(2, 44, 34, 0.85) !important;
    border: 1px solid rgba(52, 211, 153, 0.35) !important;
    color: #ffffff !important;
    -webkit-text-fill-color: #ffffff !important;
    border-radius: 8px !important;
}

section[data-testid="stSidebar"] div[data-testid="stTextInput"] input {
    background-color: transparent !important;
    border: none !important;
}

section[data-testid="stSidebar"] div[data-testid="stTextInput"] button {
    background-color: transparent !important;
    border: none !important;
    color: #34d399 !important;
}

section[data-testid="stSidebar"] div[data-testid="stTextInput"] button svg,
section[data-testid="stSidebar"] div[data-testid="stTextInput"] svg {
    fill: #34d399 !important;
    color: #34d399 !important;
}

section[data-testid="stSidebar"] div[data-baseweb="select"] div,
section[data-testid="stSidebar"] div[data-baseweb="select"] span {
    color: #ffffff !important;
    -webkit-text-fill-color: #ffffff !important;
}

section[data-testid="stSidebar"] div[data-testid="stNumberInput"] button {
    background-color: rgba(2, 44, 34, 0.85) !important;
    color: #ffffff !important;
    border: 1px solid rgba(52, 211, 153, 0.35) !important;
}

/* Sidebar Clear Cache button */
section[data-testid="stSidebar"] button[kind="secondary"],
section[data-testid="stSidebar"] button[kind="primary"] {
    background-color: rgba(255, 255, 255, 0.12) !important;
    color: #ffffff !important;
    border: 1px solid rgba(110, 231, 183, 0.35) !important;
    border-radius: 8px !important;
    font-weight: 700 !important;
    transition: all 0.2s ease !important;
}

section[data-testid="stSidebar"] button[kind="secondary"] *,
section[data-testid="stSidebar"] button[kind="primary"] * {
    color: #ffffff !important;
    -webkit-text-fill-color: #ffffff !important;
}

section[data-testid="stSidebar"] button[kind="secondary"]:hover,
section[data-testid="stSidebar"] button[kind="primary"]:hover {
    background-color: #10b981 !important;
    color: #022c22 !important;
    border-color: #34d399 !important;
    box-shadow: 0 4px 12px rgba(16, 185, 129, 0.45) !important;
}

section[data-testid="stSidebar"] button[kind="secondary"]:hover *,
section[data-testid="stSidebar"] button[kind="primary"]:hover * {
    color: #022c22 !important;
    -webkit-text-fill-color: #022c22 !important;
}

/* Sidebar Sliders */
section[data-testid="stSidebar"] div[data-testid="stSlider"] div,
section[data-testid="stSidebar"] div[data-testid="stSlider"] span,
section[data-testid="stSidebar"] div[data-testid="stSlider"] p {
    color: #ecfdf5 !important;
    -webkit-text-fill-color: #ecfdf5 !important;
}

section[data-testid="stSidebar"] div[data-testid="stSlider"] [data-baseweb="slider"] div[role="slider"] {
    background-color: #34d399 !important;
    border: 2px solid #ffffff !important;
}

header[data-testid="stHeader"] {
    background-color: var(--page-bg) !important;
    border-bottom: 1px solid var(--sidebar-border) !important;
    height: 55px !important;
}

/* Universal Label overrides across all forms in Main Page & Sidebar */
label p, label span, h1, h2, h3, h4, h5, h6 {
    color: var(--card-text) !important;
    -webkit-text-fill-color: var(--card-text) !important;
}

/* Universal Radio Buttons styling */
div[data-testid="stRadio"] *,
div[data-testid="stRadio"] label p,
div[data-testid="stRadio"] label span,
div[data-testid="stRadio"] div[role="radiogroup"] label p,
div[data-testid="stRadio"] div[role="radiogroup"] label span {
    color: var(--card-text) !important;
    -webkit-text-fill-color: var(--card-text) !important;
}

/* BaseWeb Select dropdowns and input boxes */
div[data-baseweb="select"] > div {
    background-color: var(--input-bg) !important;
    border: 1px solid var(--input-border) !important;
    border-radius: 8px !important;
}

div[data-baseweb="select"] div,
div[data-baseweb="select"] span,
div[data-baseweb="select"] input {
    color: var(--input-text) !important;
    -webkit-text-fill-color: var(--input-text) !important;
}

/* Number Input & Text Input styling across Main Page and Sidebar */
div[data-testid="stNumberInput"] input,
div[data-testid="stNumberInput"] div[data-baseweb="input"],
div[data-testid="stNumberInput"] button,
div[data-testid="stTextInput"] input {
    background-color: var(--input-bg) !important;
    color: var(--input-text) !important;
    -webkit-text-fill-color: var(--input-text) !important;
    border: 1px solid var(--input-border) !important;
    border-radius: 8px !important;
}

div[data-testid="stNumberInput"] label p,
div[data-testid="stNumberInput"] label span,
div[data-testid="stTextInput"] label p,
div[data-testid="stTextInput"] label span {
    color: var(--card-text) !important;
    -webkit-text-fill-color: var(--card-text) !important;
}

/* Multiselect selected items (chips/tags) override */
span[data-baseweb="tag"] {
    background-color: var(--tag-bg) !important;
    border: 1px solid var(--tag-border) !important;
    border-radius: 6px !important;
}

span[data-baseweb="tag"] span {
    color: var(--tag-text) !important;
    -webkit-text-fill-color: var(--tag-text) !important;
    background-color: transparent !important;
}

span[data-baseweb="tag"] svg {
    fill: var(--card-subtext) !important;
}

/* Dropdown listbox items (when expanding dropdown) */
div[role="listbox"], ul[role="listbox"], div[data-baseweb="menu"] {
    background-color: var(--input-bg) !important;
    border: 1px solid var(--card-border) !important;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.25) !important;
}

div[role="listbox"] div, ul[role="listbox"] li, div[data-baseweb="menu"] div {
    background-color: var(--input-bg) !important;
    color: var(--input-text) !important;
    -webkit-text-fill-color: var(--input-text) !important;
}

div[role="option"]:hover, li[role="option"]:hover, div[data-baseweb="menu"] div:hover {
    background-color: var(--hover-bg) !important;
    color: var(--input-text) !important;
}

/* Slider values styling */
div[data-testid="stSlider"] div,
div[data-testid="stSlider"] span,
div[data-testid="stSlider"] p {
    color: var(--card-text) !important;
    -webkit-text-fill-color: var(--card-text) !important;
}

/* Toggle (Checkbox/Switch) label styling */
div[data-testid="stCheckbox"] label span,
div[data-testid="stCheckbox"] label p,
div[data-testid="stToggle"] label span,
div[data-testid="stToggle"] label p {
    color: var(--card-text) !important;
    -webkit-text-fill-color: var(--card-text) !important;
}

/* Custom st.dataframe styling to align with active Light/Dark theme */
div[data-testid="stDataFrame"],
div[data-testid="stDataFrame"] > div,
div[data-testid="stDataFrame"] iframe,
div[data-testid="stDataFrame"] canvas {
    color-scheme: var(--app-color-scheme, light) !important;
}

div[data-testid="stDataFrame"] {
    background-color: var(--card-bg) !important;
    border: 1px solid var(--card-border) !important;
    border-radius: 10px !important;
    overflow: hidden !important;
}


/* Card container styling for bordered containers across dashboard */
div[data-testid="stVerticalBlockBorderWrapper"] {
    background: var(--card-bg, #ffffff) !important;
    border: 1.5px solid var(--kpi-border, rgba(4, 120, 87, 0.18)) !important;
    border-radius: 16px !important;
    box-shadow: 0 4px 20px rgba(4, 120, 87, 0.04), 0 1px 3px rgba(0, 0, 0, 0.02) !important;
    transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

div[data-testid="stVerticalBlockBorderWrapper"]:hover {
    border-color: var(--kpi-hover-border, #047857) !important;
    box-shadow: 0 8px 24px rgba(4, 120, 87, 0.09), 0 2px 6px rgba(0, 0, 0, 0.03) !important;
}

/* Custom st.pills styling - Guaranteed high contrast in Light and Dark modes */
div[data-testid="stPills"] {
    gap: 8px !important;
    padding-top: 4px !important;
}
div[data-testid="stPills"] button,
div[data-testid="stPills"] button[kind],
div[data-testid="stPills"] [data-testid="stPillsItem"],
div[data-testid="stPills"] [data-testid^="stBaseButton"] {
    background-color: var(--pill-bg) !important;
    color: var(--pill-text) !important;
    border: 1px solid var(--pill-border) !important;
    border-radius: 20px !important;
    padding: 4px 14px !important;
    font-size: 0.82rem !important;
    font-weight: 600 !important;
    transition: all 0.2s ease !important;
}
div[data-testid="stPills"] button *,
div[data-testid="stPills"] button p,
div[data-testid="stPills"] button span,
div[data-testid="stPills"] [data-testid="stPillsItem"] *,
div[data-testid="stPills"] [data-testid="stPillsItem"] p,
div[data-testid="stPills"] [data-testid="stPillsItem"] span {
    color: var(--pill-text) !important;
    -webkit-text-fill-color: var(--pill-text) !important;
}

div[data-testid="stPills"] button:hover,
div[data-testid="stPills"] [data-testid="stPillsItem"]:hover {
    border-color: var(--primary-accent, #047857) !important;
    background-color: var(--hover-bg) !important;
}
div[data-testid="stPills"] button:hover *,
div[data-testid="stPills"] button:hover p,
div[data-testid="stPills"] button:hover span,
div[data-testid="stPills"] [data-testid="stPillsItem"]:hover *,
div[data-testid="stPills"] [data-testid="stPillsItem"]:hover p,
div[data-testid="stPills"] [data-testid="stPillsItem"]:hover span {
    color: var(--primary-accent, #047857) !important;
    -webkit-text-fill-color: var(--primary-accent, #047857) !important;
}

/* Style selected pill buttons with explicit SAM green background and white text */
div[data-testid="stPills"] button[aria-checked="true"],
div[data-testid="stPills"] button[aria-pressed="true"],
div[data-testid="stPills"] button[data-selected="true"],
div[data-testid="stPills"] button[aria-selected="true"],
div[data-testid="stPills"] [data-testid="stPillsItem"][aria-checked="true"],
div[data-testid="stPills"] [data-testid="stPillsItem"][data-selected="true"] {
    background-color: var(--primary-accent, #047857) !important;
    border-color: var(--primary-accent, #047857) !important;
    box-shadow: 0 4px 12px rgba(4, 120, 87, 0.35) !important;
}
div[data-testid="stPills"] button[aria-checked="true"] *,
div[data-testid="stPills"] button[aria-checked="true"] p,
div[data-testid="stPills"] button[aria-checked="true"] span,
div[data-testid="stPills"] button[aria-pressed="true"] *,
div[data-testid="stPills"] button[aria-pressed="true"] p,
div[data-testid="stPills"] button[aria-pressed="true"] span,
div[data-testid="stPills"] button[data-selected="true"] *,
div[data-testid="stPills"] button[data-selected="true"] p,
div[data-testid="stPills"] button[data-selected="true"] span,
div[data-testid="stPills"] button[aria-selected="true"] *,
div[data-testid="stPills"] button[aria-selected="true"] p,
div[data-testid="stPills"] button[aria-selected="true"] span,
div[data-testid="stPills"] [data-testid="stPillsItem"][aria-checked="true"] *,
div[data-testid="stPills"] [data-testid="stPillsItem"][aria-checked="true"] p,
div[data-testid="stPills"] [data-testid="stPillsItem"][aria-checked="true"] span {
    color: #ffffff !important;
    -webkit-text-fill-color: #ffffff !important;
}

/* =========================================================================
   ULTRA-SPECIFIC OVERRIDE FOR SIDEBAR PILLS & BUTTON GROUPS (CRISP WHITE PILLS + DEEP GREEN TEXT)
   ========================================================================= */
section[data-testid="stSidebar"] div[data-testid="stButtonGroup"],
section[data-testid="stSidebar"] .stButtonGroup,
section[data-testid="stSidebar"] div[data-testid="stPills"] {
    gap: 6px !important;
}

section[data-testid="stSidebar"] div[data-testid="stButtonGroup"] button,
section[data-testid="stSidebar"] div[data-testid="stButtonGroup"] button[data-variant="pills"],
section[data-testid="stSidebar"] .stButtonGroup button,
section[data-testid="stSidebar"] div[data-testid="stPills"] button,
section[data-testid="stSidebar"] div[data-testid="stPills"] button[kind],
section[data-testid="stSidebar"] div[data-testid="stPills"] [data-testid="stPillsItem"],
section[data-testid="stSidebar"] div[data-testid="stPills"] [data-testid^="stBaseButton"] {
    background-color: #ffffff !important;
    background: #ffffff !important;
    border: 1.5px solid #a7f3d0 !important;
    border-radius: 20px !important;
    padding: 5px 12px !important;
    font-size: 0.82rem !important;
    font-weight: 700 !important;
    color: #064e3b !important;
    -webkit-text-fill-color: #064e3b !important;
    box-shadow: 0 2px 5px rgba(0, 0, 0, 0.15) !important;
    transition: all 0.2s ease !important;
}

section[data-testid="stSidebar"] div[data-testid="stButtonGroup"] button *,
section[data-testid="stSidebar"] div[data-testid="stButtonGroup"] button p,
section[data-testid="stSidebar"] div[data-testid="stButtonGroup"] button span,
section[data-testid="stSidebar"] .stButtonGroup button *,
section[data-testid="stSidebar"] .stButtonGroup button p,
section[data-testid="stSidebar"] .stButtonGroup button span,
section[data-testid="stSidebar"] div[data-testid="stPills"] button *,
section[data-testid="stSidebar"] div[data-testid="stPills"] button p,
section[data-testid="stSidebar"] div[data-testid="stPills"] button span,
section[data-testid="stSidebar"] div[data-testid="stPills"] [data-testid="stPillsItem"] *,
section[data-testid="stSidebar"] div[data-testid="stPills"] [data-testid="stPillsItem"] p,
section[data-testid="stSidebar"] div[data-testid="stPills"] [data-testid="stPillsItem"] span {
    color: #064e3b !important;
    -webkit-text-fill-color: #064e3b !important;
    font-weight: 700 !important;
}

/* Sidebar Pills: Hover State */
section[data-testid="stSidebar"] div[data-testid="stButtonGroup"] button:hover,
section[data-testid="stSidebar"] .stButtonGroup button:hover,
section[data-testid="stSidebar"] div[data-testid="stPills"] button:hover,
section[data-testid="stSidebar"] div[data-testid="stPills"] [data-testid="stPillsItem"]:hover {
    background-color: #ecfdf5 !important;
    background: #ecfdf5 !important;
    border-color: #047857 !important;
    color: #047857 !important;
    -webkit-text-fill-color: #047857 !important;
    transform: translateY(-1px) !important;
}

section[data-testid="stSidebar"] div[data-testid="stButtonGroup"] button:hover *,
section[data-testid="stSidebar"] div[data-testid="stButtonGroup"] button:hover p,
section[data-testid="stSidebar"] .stButtonGroup button:hover *,
section[data-testid="stSidebar"] .stButtonGroup button:hover p,
section[data-testid="stSidebar"] div[data-testid="stPills"] button:hover *,
section[data-testid="stSidebar"] div[data-testid="stPills"] [data-testid="stPillsItem"]:hover * {
    color: #047857 !important;
    -webkit-text-fill-color: #047857 !important;
}

/* Sidebar Pills: Active / Selected State (Deep SAM Green Background with Pure White Bold Text) */
section[data-testid="stSidebar"] div[data-testid="stButtonGroup"] button[aria-pressed="true"],
section[data-testid="stSidebar"] div[data-testid="stButtonGroup"] button[data-selected="true"],
section[data-testid="stSidebar"] div[data-testid="stButtonGroup"] button[aria-selected="true"],
section[data-testid="stSidebar"] .stButtonGroup button[aria-pressed="true"],
section[data-testid="stSidebar"] .stButtonGroup button[data-selected="true"],
section[data-testid="stSidebar"] .stButtonGroup button[aria-selected="true"],
section[data-testid="stSidebar"] div[data-testid="stPills"] button[aria-checked="true"],
section[data-testid="stSidebar"] div[data-testid="stPills"] button[aria-pressed="true"],
section[data-testid="stSidebar"] div[data-testid="stPills"] button[data-selected="true"],
section[data-testid="stSidebar"] div[data-testid="stPills"] button[aria-selected="true"],
section[data-testid="stSidebar"] div[data-testid="stPills"] [data-testid="stPillsItem"][aria-checked="true"],
section[data-testid="stSidebar"] div[data-testid="stPills"] [data-testid="stPillsItem"][data-selected="true"] {
    background-color: #047857 !important;
    background: #047857 !important;
    border: 2px solid #34d399 !important;
    box-shadow: 0 4px 14px rgba(0, 0, 0, 0.4) !important;
}

section[data-testid="stSidebar"] div[data-testid="stButtonGroup"] button[aria-pressed="true"] *,
section[data-testid="stSidebar"] div[data-testid="stButtonGroup"] button[aria-pressed="true"] p,
section[data-testid="stSidebar"] div[data-testid="stButtonGroup"] button[aria-pressed="true"] span,
section[data-testid="stSidebar"] div[data-testid="stButtonGroup"] button[data-selected="true"] *,
section[data-testid="stSidebar"] div[data-testid="stButtonGroup"] button[data-selected="true"] p,
section[data-testid="stSidebar"] div[data-testid="stButtonGroup"] button[data-selected="true"] span,
section[data-testid="stSidebar"] .stButtonGroup button[aria-pressed="true"] *,
section[data-testid="stSidebar"] .stButtonGroup button[aria-pressed="true"] p,
section[data-testid="stSidebar"] .stButtonGroup button[aria-pressed="true"] span,
section[data-testid="stSidebar"] .stButtonGroup button[data-selected="true"] *,
section[data-testid="stSidebar"] .stButtonGroup button[data-selected="true"] p,
section[data-testid="stSidebar"] .stButtonGroup button[data-selected="true"] span,
section[data-testid="stSidebar"] div[data-testid="stPills"] button[aria-checked="true"] *,
section[data-testid="stSidebar"] div[data-testid="stPills"] button[aria-checked="true"] p,
section[data-testid="stSidebar"] div[data-testid="stPills"] button[aria-checked="true"] span,
section[data-testid="stSidebar"] div[data-testid="stPills"] button[aria-pressed="true"] *,
section[data-testid="stSidebar"] div[data-testid="stPills"] button[aria-pressed="true"] p,
section[data-testid="stSidebar"] div[data-testid="stPills"] button[aria-pressed="true"] span,
section[data-testid="stSidebar"] div[data-testid="stPills"] button[data-selected="true"] *,
section[data-testid="stSidebar"] div[data-testid="stPills"] button[data-selected="true"] p,
section[data-testid="stSidebar"] div[data-testid="stPills"] button[data-selected="true"] span,
section[data-testid="stSidebar"] div[data-testid="stPills"] button[aria-selected="true"] *,
section[data-testid="stSidebar"] div[data-testid="stPills"] button[aria-selected="true"] p,
section[data-testid="stSidebar"] div[data-testid="stPills"] button[aria-selected="true"] span,
section[data-testid="stSidebar"] div[data-testid="stPills"] [data-testid="stPillsItem"][aria-checked="true"] *,
section[data-testid="stSidebar"] div[data-testid="stPills"] [data-testid="stPillsItem"][aria-checked="true"] p,
section[data-testid="stSidebar"] div[data-testid="stPills"] [data-testid="stPillsItem"][aria-checked="true"] span {
    color: #ffffff !important;
    -webkit-text-fill-color: #ffffff !important;
    font-weight: 800 !important;
}

/* Metrics panel styling with executive SAM green theme */
.metric-card {
    background: var(--card-bg) !important;
    border: 1px solid var(--kpi-border, rgba(4, 120, 87, 0.16)) !important;
    border-top: 3.5px solid var(--kpi-accent-bar, #047857) !important;
    border-radius: 16px;
    padding: 24px;
    text-align: center;
    box-shadow: 0 4px 20px rgba(4, 120, 87, 0.04);
    transition: transform 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
}
.metric-card:hover {
    transform: translateY(-3px);
    border-color: var(--kpi-hover-border, #047857) !important;
    border-top-color: var(--kpi-accent-bar, #047857) !important;
    box-shadow: 0 12px 28px var(--kpi-hover-shadow, rgba(4, 120, 87, 0.12)), 0 2px 10px rgba(4, 120, 87, 0.06) !important;
    background: var(--card-bg) !important;
}
.metric-title {
    font-size: 0.85rem;
    color: var(--card-subtext) !important;
    margin-bottom: 8px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}
.metric-value {
    font-size: 1.9rem;
    font-weight: 800;
    background: var(--kpi-gradient, linear-gradient(135deg, #064e3b 0%, #047857 100%)); 
    -webkit-background-clip: text; 
    -webkit-text-fill-color: transparent;
}
.metric-sub {
    font-size: 0.78rem;
    color: var(--card-subtext) !important;
    margin-top: 6px;
    font-weight: 500;
}

/* =========================================================================
   EXECUTIVE MODERN UNDERLINE BAR (OPTION 2 - BLOOMBERG / VERCEL / GITHUB)
   ========================================================================= */

/* Container Spacing: Tighten top and bottom vertical whitespace */
.stTabs, div[data-testid="stTabs"] {
    margin-top: 0px !important;
    padding-top: 0px !important;
}

/* Main Tab Row Container */
.stTabs [data-baseweb="tab-list"],
div[data-baseweb="tab-list"],
div[role="tablist"] {
    background: transparent !important;
    border: none !important;
    border-bottom: 1px solid var(--tab-container-border, #e2e8f0) !important;
    border-radius: 0px !important;
    padding: 0px 4px !important;
    gap: 24px !important;
    display: flex !important;
    flex-wrap: wrap !important;
    align-items: flex-end !important;
    box-shadow: none !important;
    margin-top: 0px !important;
    margin-bottom: 6px !important;
    width: 100% !important;
}

/* Remove default Streamlit highlight line */
div[data-baseweb="tab-highlight"],
div[data-baseweb="tab-border"],
[data-baseweb="tab-highlight"],
[data-baseweb="tab-border"] {
    display: none !important;
    height: 0px !important;
    visibility: hidden !important;
    opacity: 0 !important;
}

/* Individual Tab Button - Sleek, Flat */
.stTabs [data-baseweb="tab"],
div[data-baseweb="tab"],
div[role="tab"],
button[data-baseweb="tab"] {
    background: transparent !important;
    border: none !important;
    border-bottom: 3px solid transparent !important;
    border-radius: 6px 6px 0 0 !important;
    padding: 6px 12px 8px 12px !important;
    margin-bottom: -1px !important;
    color: var(--tab-inactive-text, #64748b) !important;
    -webkit-text-fill-color: var(--tab-inactive-text, #64748b) !important;
    font-weight: 600 !important;
    font-size: 1.10rem !important;
    transition: color 0.15s ease, border-color 0.15s ease, background-color 0.15s ease !important;
    cursor: pointer !important;
    outline: none !important;
    height: auto !important;
    box-shadow: none !important;
    transform: none !important;
}

.stTabs [data-baseweb="tab"] p,
div[data-baseweb="tab"] p,
div[data-baseweb="tab"] div {
    color: inherit !important;
    -webkit-text-fill-color: inherit !important;
    margin: 0 !important;
    line-height: 1.4 !important;
    display: flex !important;
    align-items: center !important;
    gap: 8px !important;
    font-size: 1.10rem !important;
}

/* Hover Tab State */
.stTabs [data-baseweb="tab"]:hover,
div[data-baseweb="tab"]:hover,
div[role="tab"]:hover {
    background: var(--nav-item-hover-bg, rgba(0, 0, 0, 0.03)) !important;
    color: var(--tab-hover-text, #0f172a) !important;
    -webkit-text-fill-color: var(--tab-hover-text, #0f172a) !important;
    border-bottom: 3px solid var(--card-border, #cbd5e1) !important;
}

.stTabs [data-baseweb="tab"]:hover p,
div[data-baseweb="tab"]:hover p {
    color: var(--tab-hover-text, #0f172a) !important;
    -webkit-text-fill-color: var(--tab-hover-text, #0f172a) !important;
}

/* Active Tab (Underline Indicator) */
.stTabs [data-baseweb="tab"][aria-selected="true"],
div[data-baseweb="tab"][aria-selected="true"],
div[role="tab"][aria-selected="true"] {
    background: transparent !important;
    color: var(--tab-active-text, #065f46) !important;
    -webkit-text-fill-color: var(--tab-active-text, #065f46) !important;
    border: none !important;
    border-bottom: 3.5px solid var(--tab-active-border, #059669) !important;
    border-radius: 0 !important;
    font-weight: 700 !important;
    font-size: 1.10rem !important;
    box-shadow: none !important;
    transform: none !important;
}

.stTabs [data-baseweb="tab"][aria-selected="true"] p,
div[data-baseweb="tab"][aria-selected="true"] p,
div[data-baseweb="tab"][aria-selected="true"] div {
    color: var(--tab-active-text, #065f46) !important;
    -webkit-text-fill-color: var(--tab-active-text, #065f46) !important;
    font-weight: 700 !important;
    font-size: 1.10rem !important;
}

/* Main Navigation Tabs: Font Awesome Solid Icons scoped strictly to main tabs container */
.st-key-main_tabs_container [role="tab"]:nth-child(1) p::before,
.st-key-main_tabs_container div[role="tablist"] > div:nth-child(1) p::before {
    font-family: "Font Awesome 6 Free", "FontAwesome" !important;
    font-weight: 900 !important;
    content: "\\f200\\a0" !important;
    color: inherit !important;
    -webkit-text-fill-color: inherit !important;
    display: inline-block !important;
    margin-right: 4px !important;
    font-style: normal !important;
    font-variant: normal !important;
    text-rendering: auto !important;
    -webkit-font-smoothing: antialiased !important;
}

.st-key-main_tabs_container [role="tab"]:nth-child(2) p::before,
.st-key-main_tabs_container div[role="tablist"] > div:nth-child(2) p::before {
    font-family: "Font Awesome 6 Free", "FontAwesome" !important;
    font-weight: 900 !important;
    content: "\\f279\\a0" !important;
    color: inherit !important;
    -webkit-text-fill-color: inherit !important;
    display: inline-block !important;
    margin-right: 4px !important;
    font-style: normal !important;
    font-variant: normal !important;
    text-rendering: auto !important;
    -webkit-font-smoothing: antialiased !important;
}

.st-key-main_tabs_container [role="tab"]:nth-child(3) p::before,
.st-key-main_tabs_container div[role="tablist"] > div:nth-child(3) p::before {
    font-family: "Font Awesome 6 Free", "FontAwesome" !important;
    font-weight: 900 !important;
    content: "\\f080\\a0" !important;
    color: inherit !important;
    -webkit-text-fill-color: inherit !important;
    display: inline-block !important;
    margin-right: 4px !important;
    font-style: normal !important;
    font-variant: normal !important;
    text-rendering: auto !important;
    -webkit-font-smoothing: antialiased !important;
}

.st-key-main_tabs_container [role="tab"]:nth-child(4) p::before,
.st-key-main_tabs_container div[role="tablist"] > div:nth-child(4) p::before {
    font-family: "Font Awesome 6 Free", "FontAwesome" !important;
    font-weight: 900 !important;
    content: "\\f3c5\\a0" !important;
    color: inherit !important;
    -webkit-text-fill-color: inherit !important;
    display: inline-block !important;
    margin-right: 4px !important;
    font-style: normal !important;
    font-variant: normal !important;
    text-rendering: auto !important;
    -webkit-font-smoothing: antialiased !important;
}

.st-key-main_tabs_container [role="tab"]:nth-child(5) p::before,
.st-key-main_tabs_container div[role="tablist"] > div:nth-child(5) p::before {
    font-family: "Font Awesome 6 Free", "FontAwesome" !important;
    font-weight: 900 !important;
    content: "\\f03a\\a0" !important;
    color: inherit !important;
    -webkit-text-fill-color: inherit !important;
    display: inline-block !important;
    margin-right: 4px !important;
    font-style: normal !important;
    font-variant: normal !important;
    text-rendering: auto !important;
    -webkit-font-smoothing: antialiased !important;
}


.st-key-main_tabs_container [role="tab"][aria-selected="true"] p::before,
.st-key-main_tabs_container div[role="tablist"] > div[aria-selected="true"] p::before {
    color: var(--tab-active-border, #059669) !important;
    -webkit-text-fill-color: var(--tab-active-border, #059669) !important;
}

/* ========================================================================= */
/* Apple / macOS Elevated Floating Pill Segmented Control (Compact) */
/* ========================================================================= */
div[data-testid="stSegmentedControl"] {
    background: var(--seg-track-bg, rgba(148, 163, 184, 0.14)) !important;
    border: none !important;
    border-color: transparent !important;
    border-radius: 9999px !important;
    padding: 2px !important;
    box-shadow: none !important;
    display: inline-flex !important;
    align-items: center !important;
    width: fit-content !important;
}

div[data-testid="stSegmentedControl"] div[data-testid="stButtonGroup"],
div[data-testid="stSegmentedControl"] div[role="radiogroup"] {
    border: none !important;
    background: transparent !important;
    gap: 2px !important;
    padding: 0 !important;
    border-radius: 9999px !important;
    display: flex !important;
    align-items: center !important;
}

div[data-testid="stSegmentedControl"] button,
div[data-testid="stSegmentedControl"] button[data-variant="segmented_control"],
div[data-testid="stSegmentedControl"] button[data-testid*="stBaseButton"],
div[data-testid="stSegmentedControl"] div[role="radiogroup"] > button {
    border: none !important;
    border-color: transparent !important;
    outline: none !important;
    background: transparent !important;
    background-color: transparent !important;
    border-radius: 9999px !important;
    padding: 3px 12px !important;
    min-height: 28px !important;
    font-weight: 600 !important;
    font-size: 0.80rem !important;
    letter-spacing: -0.01em !important;
    color: var(--seg-inactive-text, #64748b) !important;
    -webkit-text-fill-color: var(--seg-inactive-text, #64748b) !important;
    transition: all 0.22s cubic-bezier(0.16, 1, 0.3, 1) !important;
    box-shadow: none !important;
    cursor: pointer !important;
}

div[data-testid="stSegmentedControl"] button span[data-testid="stIconMaterial"] {
    font-size: 15px !important;
    width: 15px !important;
    height: 15px !important;
    line-height: 15px !important;
    margin-right: 2px !important;
}

div[data-testid="stSegmentedControl"] button:hover {
    color: var(--card-text, #0f172a) !important;
    -webkit-text-fill-color: var(--card-text, #0f172a) !important;
    background: rgba(255, 255, 255, 0.3) !important;
}

/* Active Segment: Cyber Frosted Glass & Neon Aura */
div[data-testid="stSegmentedControl"] button[aria-checked="true"],
div[data-testid="stSegmentedControl"] button[data-checked="true"],
div[data-testid="stSegmentedControl"] button[aria-pressed="true"],
div[data-testid="stSegmentedControl"] button[data-variant="segmented_control"][aria-checked="true"],
div[data-testid="stSegmentedControl"] div[role="radiogroup"] > button[aria-checked="true"] {
    background: var(--seg-active-bg, rgba(16, 185, 129, 0.14)) !important;
    backdrop-filter: blur(8px) !important;
    -webkit-backdrop-filter: blur(8px) !important;
    color: var(--seg-active-text, #065f46) !important;
    -webkit-text-fill-color: var(--seg-active-text, #065f46) !important;
    border: 1.5px solid var(--seg-active-border, #059669) !important;
    border-radius: 9999px !important;
    box-shadow: var(--seg-active-shadow, 0 0 14px rgba(16, 185, 129, 0.38)) !important;
    font-weight: 700 !important;
    transform: translateY(-0.5px) !important;
}

/* Inner Text & Icons */
div[data-testid="stSegmentedControl"] button[aria-checked="true"] *,
div[data-testid="stSegmentedControl"] button[aria-checked="true"] p,
div[data-testid="stSegmentedControl"] button[aria-checked="true"] span,
div[data-testid="stSegmentedControl"] button[aria-checked="true"] [data-testid="stIconMaterial"] {
    color: var(--seg-active-text, #065f46) !important;
    -webkit-text-fill-color: var(--seg-active-text, #065f46) !important;
    font-weight: 700 !important;
}

div[data-testid="stSegmentedControl"] button:not([aria-checked="true"]) *,
div[data-testid="stSegmentedControl"] button:not([aria-checked="true"]) p,
div[data-testid="stSegmentedControl"] button:not([aria-checked="true"]) span,
div[data-testid="stSegmentedControl"] button:not([aria-checked="true"]) [data-testid="stIconMaterial"] {
    color: var(--seg-inactive-text, #64748b) !important;
    -webkit-text-fill-color: var(--seg-inactive-text, #64748b) !important;
    font-weight: 600 !important;
}

div[data-testid="stSegmentedControl"] hr,
div[data-testid="stSegmentedControl"] button::before,
div[data-testid="stSegmentedControl"] button::after {
    display: none !important;
    border: none !important;
}

/* Tab Panel content area styling */
div[data-baseweb="tab-panel"], div[data-testid="stTabPanel"] {
    position: relative !important;
    padding-top: 4px !important;
    padding-left: 0px !important;
    padding-right: 0px !important;
}

.floating-kpi-container {
    position: relative !important;
    margin: 10px 0px 4px 0px !important;
    z-index: 999;
    display: grid !important;
    grid-template-columns: repeat(auto-fit, minmax(145px, 1fr)) !important;
    gap: 12px !important;
}



#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
</style>"""

st.html(css_style.replace("ROOT_VARS_PLACEHOLDER", root_vars))

# ----------------- MAIN VIEW -----------------
# Check if data exists
if df_raw is None or df_raw.empty:
    st.markdown("""
    <div style="background-color: rgba(239, 68, 68, 0.08); border: 1px solid rgba(239, 68, 68, 0.2); border-radius: 12px; padding: 40px; text-align: center; margin-top: 50px; max-width: 800px; margin-left: auto; margin-right: auto; box-shadow: 0 10px 30px rgba(0,0,0,0.04);">
        <i class="fa-solid fa-triangle-exclamation" style="font-size: 4rem; color: #ef4444; margin-bottom: 20px;"></i>
        <h2 style="color: #ef4444; margin-bottom: 15px; font-weight: 700;">ไม่พบไฟล์ข้อมูล 'all_assets.parquet'</h2>
        <p style="color: #475569; font-size: 1rem;">กรุณารันคำสั่ง <code>python convert_csv_to_parquet.py</code> เพื่อแปลงไฟล์และเริ่มต้นใช้งานแดชบอร์ด</p>
    </div>
    """)
    st.stop()

# ----------------- DATA FILTERING LOGIC -----------------
df_filtered = df_raw.copy()

# 1. Search Query
if search_query:
    search_pattern = re.escape(search_query)
    df_filtered = df_filtered[
        df_filtered['ชื่อประกาศ'].str.contains(search_pattern, case=False, na=False) |
        df_filtered['รหัสทรัพย์'].str.contains(search_pattern, case=False, na=False) |
        df_filtered['ชื่อโครงการ'].str.contains(search_pattern, case=False, na=False) |
        df_filtered['จังหวัด'].str.contains(search_pattern, case=False, na=False)
    ]

# 2. Company
if selected_companies:
    df_filtered = df_filtered[df_filtered['บริษัท'].isin(selected_companies)]

# 3. Property Types
if selected_types:
    if "เพิ่มเติม" in selected_types:
        if selected_companies:
            df_by_company = df_raw[df_raw['บริษัท'].isin(selected_companies)]
        else:
            df_by_company = df_raw
        type_counts = df_by_company['ประเภททรัพย์'].value_counts()
        PROMINENT_TYPES = [
            "บ้านเดี่ยว", "ห้องชุดพักอาศัย", "ทาวน์เฮ้าส์", "ที่ดินเปล่า",
            "อาคารพาณิชย์", "วิลล่า", "โรงงาน/โกดัง", "บ้านแฝด",
            "อพาร์ทเมนท์", "อาคารสำนักงาน", "โรงแรม/รีสอร์ท"
        ]
        common_types = [t for t in PROMINENT_TYPES if t in type_counts]
        for t in type_counts.index:
            if t not in common_types and type_counts[t] >= 80 and t != "อื่นๆ":
                common_types.append(t)
        rare_types = [t for t in type_counts.index if t not in common_types]
        selected_rare = st.session_state.get("selected_rare_types", [])
        selected_rare_clean = [t.rsplit(" (", 1)[0] for t in selected_rare] if selected_rare else []
        if selected_rare_clean:
            actual_selected_types = [t for t in selected_types if t != "เพิ่มเติม"] + selected_rare_clean
        else:
            actual_selected_types = [t for t in selected_types if t != "เพิ่มเติม"] + rare_types
    else:
        actual_selected_types = selected_types
    df_filtered = df_filtered[df_filtered['ประเภททรัพย์'].isin(actual_selected_types)]

# 3.5. Sale Types
if selected_sale_types:
    df_filtered = df_filtered[df_filtered['ประเภทการขาย'].astype(str).str.strip().isin(selected_sale_types)]

# 3.8. Regions (ภูมิภาค)
if selected_regions:
    df_filtered = df_filtered[df_filtered['ภาค'].isin(selected_regions)]

# 4. Provinces
if selected_provinces:
    df_filtered = df_filtered[df_filtered['จังหวัด'].isin(selected_provinces)]

# 5. Districts
if selected_districts_formatted:
    if 'อำเภอ' in df_filtered.columns and 'จังหวัด' in df_filtered.columns:
        formatted_dists = df_filtered['อำเภอ'].astype(str).str.strip() + " (" + df_filtered['จังหวัด'].astype(str).str.strip() + ")"
        df_filtered = df_filtered[formatted_dists.isin(selected_districts_formatted)]

# 6. Subdistricts
if selected_subdistricts_formatted:
    if 'ตำบล' in df_filtered.columns and 'อำเภอ' in df_filtered.columns and 'จังหวัด' in df_filtered.columns:
        formatted_subs = df_filtered['ตำบล'].astype(str).str.strip() + " (" + df_filtered['อำเภอ'].astype(str).str.strip() + ", " + df_filtered['จังหวัด'].astype(str).str.strip() + ")"
        df_filtered = df_filtered[formatted_subs.isin(selected_subdistricts_formatted)]

# 7. Price Range Filter
if not valid_prices.empty:
    is_default_price_range = (price_range[0] <= min_p and price_range[1] >= max_p)
    if not is_default_price_range:
        df_filtered = df_filtered[
            (df_filtered['ราคา'].notna()) & 
            (df_filtered['ราคา'] >= price_range[0]) & 
            (df_filtered['ราคา'] <= price_range[1])
        ]

# ----------------- GLOBAL KPI METRICS COMPUTATION -----------------
total_count = len(df_raw) if df_raw is not None else 0
filtered_count = len(df_filtered)
valid_prices_filtered = df_filtered['ราคา'].dropna()
valid_prices_filtered = valid_prices_filtered[valid_prices_filtered > 0]

def format_price_kpi(val_baht):
    if pd.isna(val_baht) or val_baht is None or val_baht <= 0:
        return "฿0"
    if val_baht >= 1e9:
        return f"฿{val_baht / 1e9:,.2f}B"
    elif val_baht >= 1e6:
        return f"฿{val_baht / 1e6:,.2f}M"
    elif val_baht >= 1e3:
        return f"฿{val_baht / 1e3:,.1f}K"
    else:
        return f"฿{val_baht:,.0f}"

if not valid_prices_filtered.empty:
    total_value = valid_prices_filtered.sum()
    min_price = valid_prices_filtered.min()
    median_price = valid_prices_filtered.median()
    mean_price = valid_prices_filtered.mean()
    max_price = valid_prices_filtered.max()
    sd_price = valid_prices_filtered.std() if len(valid_prices_filtered) > 1 else 0.0
    
    total_value_str = format_price_kpi(total_value)
    min_price_str = format_price_kpi(min_price)
    median_price_str = format_price_kpi(median_price)
    mean_price_str = format_price_kpi(mean_price)
    max_price_str = format_price_kpi(max_price)
    sd_price_str = f"±{format_price_kpi(sd_price)}" if sd_price > 0 else "฿0"
else:
    total_value_str = "฿0"
    min_price_str = "฿0"
    median_price_str = "฿0"
    mean_price_str = "฿0"
    max_price_str = "฿0"
    sd_price_str = "฿0"

total_count_str = f"{total_count:,.0f}"
filtered_count_str = f"{filtered_count:,.0f}"

summary_text = build_kpi_summary_text(total_count, filtered_count)
month_year_str, exact_date_str = get_dataset_month_year(df_filtered if not df_filtered.empty else df_raw)

floating_kpi_html = f"""
<div class="floating-kpi-container" style="margin-top: 10px; margin-bottom: 20px;">
    <div class="floating-card" id="kpi-card-count" data-default-val="{filtered_count_str}" data-default-sub="{summary_text}">
        <div class="floating-card-title"><i class="fa fa-list" style="color: #047857;"></i> ทรัพย์สินที่พบ <span class="kpi-scope-badge" style="display:none;"></span></div>
        <div class="floating-card-value">{filtered_count_str}</div>
        <div class="floating-card-sub">{summary_text}</div>
    </div>
    <div class="floating-card" id="kpi-card-total-val" data-default-val="{total_value_str}" data-default-sub="มูลค่ารวมตามตัวกรอง">
        <div class="floating-card-title"><i class="fa fa-wallet" style="color: #059669;"></i> มูลค่ารวมทรัพย์สิน <span class="kpi-scope-badge" style="display:none;"></span></div>
        <div class="floating-card-value">{total_value_str}</div>
        <div class="floating-card-sub">มูลค่ารวมตามตัวกรอง</div>
    </div>
    <div class="floating-card" id="kpi-card-min-price" data-default-val="{min_price_str}" data-default-sub="ราคาเริ่มต้นต่ำสุด">
        <div class="floating-card-title"><i class="fa fa-arrow-down" style="color: #10b981;"></i> ราคาต่ำสุด (Min) <span class="kpi-scope-badge" style="display:none;"></span></div>
        <div class="floating-card-value">{min_price_str}</div>
        <div class="floating-card-sub">ราคาเริ่มต้นต่ำสุด</div>
    </div>
    <div class="floating-card" id="kpi-card-median-price" data-default-val="{median_price_str}" data-default-sub="ค่ามัธยฐานของกลุ่ม">
        <div class="floating-card-title"><i class="fa fa-tags" style="color: #047857;"></i> ราคากลาง (Median) <span class="kpi-scope-badge" style="display:none;"></span></div>
        <div class="floating-card-value">{median_price_str}</div>
        <div class="floating-card-sub">ค่ามัธยฐานของกลุ่ม</div>
    </div>
    <div class="floating-card" id="kpi-card-mean-price" data-default-val="{mean_price_str}" data-default-sub="ค่าเฉลี่ยเลขคณิต">
        <div class="floating-card-title"><i class="fa fa-calculator" style="color: #059669;"></i> ราคาเฉลี่ย (Mean) <span class="kpi-scope-badge" style="display:none;"></span></div>
        <div class="floating-card-value">{mean_price_str}</div>
        <div class="floating-card-sub">ค่าเฉลี่ยเลขคณิต</div>
    </div>
    <div class="floating-card" id="kpi-card-max-price" data-default-val="{max_price_str}" data-default-sub="มูลค่าสูงสุดในกลุ่ม">
        <div class="floating-card-title"><i class="fa fa-arrow-up" style="color: #10b981;"></i> ราคาสูงสุด (Max) <span class="kpi-scope-badge" style="display:none;"></span></div>
        <div class="floating-card-value">{max_price_str}</div>
        <div class="floating-card-sub">มูลค่าสูงสุดในกลุ่ม</div>
    </div>
    <div class="floating-card" id="kpi-card-sd-price" data-default-val="{sd_price_str}" data-default-sub="การกระจายตัวของราคา">
        <div class="floating-card-title"><i class="fa fa-chart-line" style="color: #047857;"></i> ส่วนเบี่ยงเบน (SD) <span class="kpi-scope-badge" style="display:none;"></span></div>
        <div class="floating-card-value">{sd_price_str}</div>
        <div class="floating-card-sub">การกระจายตัวของราคา</div>
    </div>
</div>
"""

st.markdown(floating_kpi_html, unsafe_allow_html=True)

# ----------------- MAIN NAVIGATION (4 Tabs with Font Awesome Solid Icons) -----------------
with st.container(key="main_tabs_container"):
    tab1, tab2, tab3, tab4 = st.tabs([
        "ภาพรวม (Bubble Chart)",
        "แผนที่ (Interactive Map)",
        "สถิติ & วิเคราะห์",
        "รายการทรัพย์สิน",
    ], key="main_tabs")

# ----- TAB 1: BUBBLE CHART -----
with tab1:
    with st.container(key="tab_bubble"):
        st.markdown("""
        <style>
        /* Container sizing & alignment */
        .st-key-tab1_metric_toggle_container,
        .st-key-tab1_map_color_toggle_container {
            width: auto !important;
            display: inline-flex !important;
            margin-left: auto !important;
            justify-content: flex-end !important;
        }

        /* Outer button group track (The Apple Pill Track - Compact) */
        .st-key-tab1_metric_toggle_container div[data-testid="stButtonGroup"],
        .st-key-tab1_metric_toggle_container div[role="radiogroup"],
        .st-key-tab1_metric_toggle_container [data-baseweb="button-group"],
        .st-key-tab1_map_color_toggle_container div[data-testid="stButtonGroup"],
        .st-key-tab1_map_color_toggle_container div[role="radiogroup"],
        .st-key-tab1_map_color_toggle_container [data-baseweb="button-group"],
        .st-key-tab1_bubble_metric_radio div[data-testid="stButtonGroup"],
        .st-key-tab1_bubble_metric_radio div[role="radiogroup"],
        .st-key-tab1_map_color_mode div[data-testid="stButtonGroup"],
        .st-key-tab1_map_color_mode div[role="radiogroup"] {
            background: var(--seg-track-bg, #f1f5f9) !important;
            border: none !important;
            border-color: transparent !important;
            border-radius: 9999px !important;
            padding: 2px !important;
            box-shadow: none !important;
            display: inline-flex !important;
            flex-direction: row !important;
            align-items: center !important;
            gap: 2px !important;
            width: fit-content !important;
        }

        /* All buttons inside - Compact Size */
        .st-key-tab1_metric_toggle_container button,
        .st-key-tab1_metric_toggle_container button[data-variant="segmented_control"],
        .st-key-tab1_map_color_toggle_container button,
        .st-key-tab1_map_color_toggle_container button[data-variant="segmented_control"],
        .st-key-tab1_bubble_metric_radio button,
        .st-key-tab1_map_color_mode button {
            border: none !important;
            border-color: transparent !important;
            border-width: 0 !important;
            outline: none !important;
            background: transparent !important;
            background-color: transparent !important;
            border-radius: 9999px !important;
            padding: 3px 12px !important;
            min-height: 28px !important;
            font-weight: 600 !important;
            font-size: 0.80rem !important;
            letter-spacing: -0.01em !important;
            color: var(--seg-inactive-text, #64748b) !important;
            -webkit-text-fill-color: var(--seg-inactive-text, #64748b) !important;
            transition: all 0.22s cubic-bezier(0.16, 1, 0.3, 1) !important;
            box-shadow: none !important;
            cursor: pointer !important;
        }

        /* Compact icon sizing */
        .st-key-tab1_metric_toggle_container span[data-testid="stIconMaterial"],
        .st-key-tab1_map_color_toggle_container span[data-testid="stIconMaterial"],
        .st-key-tab1_bubble_metric_radio span[data-testid="stIconMaterial"],
        .st-key-tab1_map_color_mode span[data-testid="stIconMaterial"] {
            font-size: 15px !important;
            width: 15px !important;
            height: 15px !important;
            line-height: 15px !important;
            margin-right: 2px !important;
        }

        /* Inactive button hover */
        .st-key-tab1_metric_toggle_container button:hover,
        .st-key-tab1_map_color_toggle_container button:hover,
        .st-key-tab1_bubble_metric_radio button:hover,
        .st-key-tab1_map_color_mode button:hover {
            color: #047857 !important;
            -webkit-text-fill-color: #047857 !important;
            background: rgba(16, 185, 129, 0.09) !important;
        }

        /* ACTIVE / SELECTED BUTTON (Vibrant Emerald Tech Gradient) */
        .st-key-tab1_metric_toggle_container button[aria-checked="true"],
        .st-key-tab1_metric_toggle_container button[data-state="active"],
        .st-key-tab1_metric_toggle_container button[kind="segmented_controlActive"],
        .st-key-tab1_map_color_toggle_container button[aria-checked="true"],
        .st-key-tab1_map_color_toggle_container button[data-state="active"],
        .st-key-tab1_map_color_toggle_container button[kind="segmented_controlActive"],
        .st-key-tab1_bubble_metric_radio button[aria-checked="true"],
        .st-key-tab1_bubble_metric_radio button[data-state="active"],
        .st-key-tab1_bubble_metric_radio button[kind="segmented_controlActive"],
        .st-key-tab1_map_color_mode button[aria-checked="true"],
        .st-key-tab1_map_color_mode button[data-state="active"],
        .st-key-tab1_map_color_mode button[kind="segmented_controlActive"] {
            background: var(--seg-active-bg, rgba(16, 185, 129, 0.14)) !important;
            backdrop-filter: blur(8px) !important;
            -webkit-backdrop-filter: blur(8px) !important;
            color: var(--seg-active-text, #065f46) !important;
            -webkit-text-fill-color: var(--seg-active-text, #065f46) !important;
            border: 1.5px solid var(--seg-active-border, #059669) !important;
            border-radius: 9999px !important;
            box-shadow: var(--seg-active-shadow, 0 0 14px rgba(16, 185, 129, 0.38)) !important;
            font-weight: 700 !important;
            transform: translateY(-0.5px) !important;
        }

        /* Inner elements for Active button */
        .st-key-tab1_metric_toggle_container button[aria-checked="true"] *,
        .st-key-tab1_map_color_toggle_container button[aria-checked="true"] *,
        .st-key-tab1_bubble_metric_radio button[aria-checked="true"] *,
        .st-key-tab1_map_color_mode button[aria-checked="true"] * {
            color: var(--seg-active-text, #065f46) !important;
            -webkit-text-fill-color: var(--seg-active-text, #065f46) !important;
            font-weight: 700 !important;
        }

        /* Inner elements for Inactive button */
        .st-key-tab1_metric_toggle_container button:not([aria-checked="true"]) *,
        .st-key-tab1_map_color_toggle_container button:not([aria-checked="true"]) *,
        .st-key-tab1_bubble_metric_radio button:not([aria-checked="true"]) *,
        .st-key-tab1_map_color_mode button:not([aria-checked="true"]) * {
            color: var(--seg-inactive-text, #64748b) !important;
            -webkit-text-fill-color: var(--seg-inactive-text, #64748b) !important;
            font-weight: 600 !important;
        }

        /* Remove default dividers / pseudo lines */
        .st-key-tab1_metric_toggle_container button::before,
        .st-key-tab1_metric_toggle_container button::after,
        .st-key-tab1_map_color_toggle_container button::before,
        .st-key-tab1_map_color_toggle_container button::after {
            display: none !important;
            content: none !important;
            border: none !important;
        }

        /* Push segmented control to far right and pull Tab 1 content flush to top */
        .st-key-tab_bubble {
            margin-top: -14px !important;
        }
        .st-key-tab_bubble div[data-testid="stHorizontalBlock"] {
            margin-bottom: -18px !important;
        }
        .st-key-tab_bubble iframe {
            margin-top: -8px !important;
        }
        .st-key-tab_bubble div.stColumn:last-child,
        .st-key-tab_map div.stColumn:last-child {
            display: flex !important;
            flex-direction: row !important;
            justify-content: flex-end !important;
            align-items: center !important;
        }
        </style>
        """, unsafe_allow_html=True)
        _, col_b2 = st.columns([0.65, 0.35])
        with col_b2:
            with st.container(key="tab1_metric_toggle_container"):
                bubble_metric = st.segmented_control(
                    label="bubble_metric",
                    options=[":material/tag: จำนวนทรัพย์สิน", ":material/payments: มูลค่ารวม"],
                    default=":material/tag: จำนวนทรัพย์สิน",
                    key="tab1_bubble_metric_radio",
                    label_visibility="collapsed"
                )
                if not bubble_metric:
                    bubble_metric = ":material/tag: จำนวนทรัพย์สิน"

        # Render 3D Glossy Bubble Chart matching AMC NPA Monitor style
        bubble_html = generate_3d_glossy_bubble_chart_html(
            df_filtered, 
            bubble_metric=bubble_metric, 
            is_dark_mode=is_dark_mode
        )
        
        try:
            import streamlit.components.v1 as stc
            stc.html(bubble_html, height=860)
        except Exception:
            st.html(bubble_html)


# ----- TAB 2: INTERACTIVE MAP -----
with tab2:
    with st.container(key="tab_map"):
        # TOP IN-PAGE FILTERS & REFERENCE POINT PICKER (No Border, FontAwesome Icons)
        # Ensure FontAwesome is available
        st.markdown('<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">', unsafe_allow_html=True)

        tab2_regions = []
        tab2_provs = st.session_state.get("tab2_filter_provinces", [])
        tab2_dists = st.session_state.get("tab2_filter_districts", [])
        tab2_subdists = st.session_state.get("tab2_filter_subdistricts", [])
        tab2_types = []

        # Resolve active reference point
        active_ref_prop = st.session_state.get("tab2_ref_prop")
        active_ref_lat = None
        active_ref_lon = None
        try:
            active_ref_radius = float(st.query_params.get("map_ref_radius", 5.0))
        except (ValueError, TypeError):
            active_ref_radius = 5.0

        # Check if reference property ID came from map search, click, or query params
        q_id = st.query_params.get("map_ref_id")
        search_prop_id = q_id or st.session_state.get("tab2_search_prop_id", "")

        if search_prop_id and search_prop_id.strip():
            clean_id = search_prop_id.strip()
            if active_ref_prop is None or str(active_ref_prop.get('รหัสทรัพย์', '')).strip().lower() != clean_id.lower():
                match_df = df_raw[df_raw['รหัสทรัพย์'].astype(str).str.strip().str.lower() == clean_id.lower()]
                if not match_df.empty:
                    r0 = match_df.iloc[0]
                    if pd.notna(r0.get('ละติจูด')) and pd.notna(r0.get('ลองจิจูด')) and float(r0['ละติจูด']) > 0 and float(r0['ลองจิจูด']) > 0:
                        active_ref_prop = r0
                        active_ref_lat = float(r0['ละติจูด'])
                        active_ref_lon = float(r0['ลองจิจูด'])
                        st.session_state["tab2_ref_lat"] = active_ref_lat
                        st.session_state["tab2_ref_lon"] = active_ref_lon
                        st.session_state["tab2_ref_prop"] = active_ref_prop
                        st.session_state["tab2_search_prop_id"] = clean_id
                        p_prov = str(r0.get('จังหวัด', '')).strip()
                        p_dist = str(r0.get('อำเภอ', '')).strip()
                        p_subdist = str(r0.get('ตำบล', '')).strip()
                        if p_prov and p_prov not in ['-', 'ไม่มีข้อมูล', 'nan']:
                            st.session_state["tab2_filter_provinces"] = [p_prov]
                            st.query_params["map_prov"] = p_prov
                        if p_dist and p_dist not in ['-', 'ไม่มีข้อมูล', 'nan']:
                            st.session_state["tab2_filter_districts"] = [p_dist]
                            st.query_params["map_dist"] = p_dist
                        if p_subdist and p_subdist not in ['-', 'ไม่มีข้อมูล', 'nan']:
                            st.session_state["tab2_filter_subdistricts"] = [p_subdist]
                            st.query_params["map_subdist"] = p_subdist
            else:
                active_ref_lat = float(active_ref_prop['ละติจูด'])
                active_ref_lon = float(active_ref_prop['ลองจิจูด'])

        if active_ref_lat is None:
            q_lat = st.query_params.get("map_ref_lat")
            q_lon = st.query_params.get("map_ref_lon")
            if q_lat and q_lon:
                try:
                    active_ref_lat = float(q_lat)
                    active_ref_lon = float(q_lon)
                    if active_ref_prop is not None:
                        p_lat = float(active_ref_prop.get('ละติจูด', 0))
                        p_lon = float(active_ref_prop.get('ลองจิจูด', 0))
                        if abs(p_lat - active_ref_lat) > 0.0005 or abs(p_lon - active_ref_lon) > 0.0005:
                            active_ref_prop = None
                            st.session_state["tab2_ref_prop"] = None
                            st.session_state["tab2_search_prop_id"] = ""
                            st.session_state["tab2_input_prop_id"] = ""
                except ValueError:
                    pass
            elif st.session_state.get("tab2_ref_lat") and st.session_state.get("tab2_ref_lon"):
                active_ref_lat = float(st.session_state["tab2_ref_lat"])
                active_ref_lon = float(st.session_state["tab2_ref_lon"])



        # 3. FILTER MAP DATA WITH IN-PAGE TAB 2 FILTERS (Geographic Scope)
        tab2_filtered = df_filtered.copy()
        if tab2_regions:
            tab2_filtered = tab2_filtered[tab2_filtered['ภาค'].isin(tab2_regions)]
        if tab2_provs:
            tab2_filtered = tab2_filtered[tab2_filtered['จังหวัด'].isin(tab2_provs)]
        if tab2_dists:
            clean_dists = [d.split(' (')[0] if ' (' in d else d for d in tab2_dists]
            tab2_filtered = tab2_filtered[tab2_filtered['อำเภอ'].isin(clean_dists)]
        if tab2_subdists:
            clean_subdists = [s.split(' (')[0] if ' (' in s else s for s in tab2_subdists]
            tab2_filtered = tab2_filtered[tab2_filtered['ตำบล'].isin(clean_subdists)]

        # Map Rendering (Deck.gl OpenStreetMap Map with dynamic marker mode, compass, and slider)
        progress_bar = st.progress(0, text="กำลังเตรียมข้อมูลแผนที่...")
        
        # Step 1: Filter rows with coordinates (20%)
        progress_bar.progress(20, text="กำลังกรองจุดพิกัดในประเทศไทย (20%)...")
        map_data = tab2_filtered[
            tab2_filtered['ละติจูด'].notna() & tab2_filtered['ลองจิจูด'].notna() &
            tab2_filtered['ละติจูด'].between(5, 21) & tab2_filtered['ลองจิจูด'].between(97, 106)
        ].copy()
        
        map_data_full_len = len(map_data)
            
        if not map_data.empty:
            # Step 2: Vectorized price formatting (no .apply() loop)
            progress_bar.progress(40, text="กำลังจัดรูปแบบราคาและชื่อประกาศ (40%)...")
            _prices_num = pd.to_numeric(map_data['ราคา'], errors='coerce')
            _valid_price = _prices_num.notna() & (_prices_num > 0)
            map_data['ราคาขาย'] = 'ไม่ระบุ'
            if _valid_price.any():
                map_data.loc[_valid_price, 'ราคาขาย'] = (
                    '฿' + _prices_num[_valid_price].map('{:,.0f}'.format) + ' บาท'
                )

            # Vectorized unit price (฿/ตร.ว. หรือ ฿/ตร.ม.)
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
            
        if map_data.empty:
            progress_bar.empty()
            st.warning("ไม่พบพิกัดตำแหน่ง ละติจูด/ลองจิจูด ในรายการทรัพย์สินที่คุณเลือกค้นหา")
        else:
            title_col = 'ชื่อประกาศ' if 'ชื่อประกาศ' in map_data.columns else ('ชื่อโครงการ' if 'ชื่อโครงการ' in map_data.columns else 'รหัสทรัพย์')
            titles  = map_data[title_col].fillna('ไม่มีชื่อ').astype(str).str.strip().str[:80].tolist()
            ids     = map_data['รหัสทรัพย์'].fillna('-').astype(str).str.strip().tolist()
            prices_list = map_data['ราคาขาย'].astype(str).tolist()

            # Centroid flag: is_centroid column OR LED company (vectorized)
            led_mask = map_data['บริษัท'].fillna('').astype(str).str.upper().str.strip() == 'LED'
            if 'is_centroid' in map_data.columns:
                centroid_mask = (map_data['is_centroid'].fillna(False).astype(bool)) | led_mask
            else:
                centroid_mask = led_mask
            centroid_flags = centroid_mask.astype('uint8').tolist()

            # Vectorized centroid count per company & per property type
            centroid_per_company = (
                map_data.loc[centroid_mask, 'บริษัท'].fillna('-').value_counts().to_dict()
            )
            centroid_per_type = (
                map_data.loc[centroid_mask, 'ประเภททรัพย์'].fillna('-').value_counts().to_dict()
            )

            # Colors for fallback / ScatterplotLayer
            COMPANY_MAP_RGB = {
                "LED": [8, 145, 178],
                "SAM": [16, 185, 129],
                "BAM": [59, 130, 246],
                "Chayo555": [249, 115, 22],
                "GHB": [202, 138, 4],
                "KBANK": [5, 150, 105],
                "KTB": [2, 132, 199],
                "SCB": [126, 34, 206],
                "GSB": [235, 25, 133],
                "DDproperty": [168, 85, 247],
                "Livinginsider": [20, 184, 166],
                "NaYoo": [139, 92, 246],
                "ZmyHome": [236, 72, 153],
                "Baania": [245, 158, 11]
            }
            DEFAULT_COLOR = [148, 163, 184]
            _uco = map_data['บริษัท'].unique()
            _r_co = {c: COMPANY_MAP_RGB.get(c, DEFAULT_COLOR)[0] for c in _uco}
            _g_co = {c: COMPANY_MAP_RGB.get(c, DEFAULT_COLOR)[1] for c in _uco}
            _b_co = {c: COMPANY_MAP_RGB.get(c, DEFAULT_COLOR)[2] for c in _uco}
            r_arr = map_data['บริษัท'].map(_r_co).fillna(DEFAULT_COLOR[0]).astype('uint8')
            g_arr = map_data['บริษัท'].map(_g_co).fillna(DEFAULT_COLOR[1]).astype('uint8')
            b_arr = map_data['บริษัท'].map(_b_co).fillna(DEFAULT_COLOR[2]).astype('uint8')

            # Dynamic Legend for Companies (with centroid counts)
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

            # Vectorized links extraction
            if 'ลิงก์' in map_data.columns:
                _lnk = map_data['ลิงก์'].fillna('').astype(str).str.strip()
                links = _lnk.where(~_lnk.isin(['', 'nan', 'None', '-']), '').tolist()
            else:
                links = [''] * len(map_data)

            # Lookup table for column compression
            progress_bar.progress(80, text="กำลังบีบอัด GZIP และแปลงเป็น Base64 (80%)...")

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

            sam_projs_list, _ = get_sam_project_options(df_raw) if df_raw is not None and not df_raw.empty else ([], {})

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
                '_prji':  _prj_cat.codes.astype('int16'),
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
            
            # Step 5: Render map template
            _tmpl_path = "static/map_template.html"
            _tmpl_mtime = os.path.getmtime(_tmpl_path) if os.path.exists(_tmpl_path) else None
            base_tmpl = get_base_map_html(_tmpl_mtime)

            atlas_uri, icon_mapping = get_map_icon_atlas_and_mapping(128)
            icon_mapping_json = json.dumps(icon_mapping, ensure_ascii=False)

            html_content = base_tmpl.replace("CSV_BASE64_PLACEHOLDER", csv_base64)
            html_content = html_content.replace("LOOKUP_BASE64_PLACEHOLDER", lookup_b64)
            html_content = html_content.replace("LEGEND_ITEMS_PLACEHOLDER", legend_content)
            body_theme_class = "dark-theme" if is_dark_mode else ""
            html_content = html_content.replace("BODY_CLASS_PLACEHOLDER", body_theme_class)
            html_content = html_content.replace("ATLAS_BASE64_PLACEHOLDER", atlas_uri)
            html_content = html_content.replace("ICON_MAPPING_PLACEHOLDER", icon_mapping_json)
            html_content = html_content.replace("INIT_REF_LAT_PLACEHOLDER", str(active_ref_lat) if active_ref_lat else "")
            html_content = html_content.replace("INIT_REF_LON_PLACEHOLDER", str(active_ref_lon) if active_ref_lon else "")
            html_content = html_content.replace("INIT_RADIUS_PLACEHOLDER", str(active_ref_radius) if active_ref_radius else "5.0")
            html_content = html_content.replace("INIT_REF_ID_PLACEHOLDER", str(st.session_state.get("tab2_search_prop_id") or st.query_params.get("map_ref_id") or search_prop_id or "").strip())
            
            # Step 5.1: Boundary GeoJSON (จังหวัด / อำเภอ / ตำบล)
            effective_provs = tab2_provs if tab2_provs else (st.session_state.get("tab2_filter_provinces", []) or (loc_prov if 'loc_prov' in locals() and loc_prov else st.session_state.get("selected_provinces", [])))
            effective_dists = tab2_dists if tab2_dists else (st.session_state.get("tab2_filter_districts", []) or (loc_dist if 'loc_dist' in locals() and loc_dist else st.session_state.get("selected_districts_formatted", [])))
            effective_subdists = tab2_subdists if tab2_subdists else (st.session_state.get("tab2_filter_subdistricts", []) or (loc_sub if 'loc_sub' in locals() and loc_sub else st.session_state.get("selected_subdistricts_formatted", [])))
            boundary_obj = get_boundary_geojson_features(effective_provs, effective_dists, effective_subdists)
            boundary_json = json.dumps(boundary_obj, ensure_ascii=False) if boundary_obj else "null"
            html_content = html_content.replace("BOUNDARY_GEOJSON_PLACEHOLDER", boundary_json)

            # Step 5.1.1: In-Map Province list and current selected province
            all_provinces_list = sorted(list({
                str(p).strip().strip(" ,;.-'\"")
                for p in df_raw['จังหวัด'].dropna().unique()
                if str(p).strip().strip(" ,;.-'\"") and str(p).strip().strip(" ,;.-'\"") not in ['-', 'ไม่มีข้อมูล', 'nan', 'None']
            })) if df_raw is not None and not df_raw.empty else []
            all_provinces_json = json.dumps(all_provinces_list, ensure_ascii=False)
            current_prov_str = effective_provs[0] if (effective_provs and len(effective_provs) > 0) else ""
            html_content = html_content.replace("ALL_PROVINCES_PLACEHOLDER", all_provinces_json)
            html_content = html_content.replace("CURRENT_PROV_PLACEHOLDER", current_prov_str)
            
            # Step 5.2: Individual Crisp Company Logos for HTML Pin Markers (Matching Tab 4)
            company_logos_dict = get_leaflet_logo_dict(72)
            company_logos_json = json.dumps(company_logos_dict, ensure_ascii=False)
            html_content = html_content.replace("COMPANY_LOGOS_PLACEHOLDER", company_logos_json)
            
            # Step 6: Finish (100%)
            progress_bar.progress(100, text="เรนเดอร์แผนที่สำเร็จแล้ว (100%)")
            progress_bar.empty()
            
            map_rendered = False
            try:
                import streamlit.components.v1 as stc
                stc.html(html_content, height=870)
                map_rendered = True
            except Exception:
                pass
            
            if not map_rendered:
                try:
                    st.html(html_content, unsafe_allow_javascript=True)
                    map_rendered = True
                except Exception:
                    pass
            
            if not map_rendered:
                st.error("ไม่สามารถแสดงแผนที่ได้ กรุณาลองรีเฟรชหน้าเว็บ")

        # ----------------- BELOW MAP: ANALYTICS CARDS & NEARBY ASSET LISTING -----------------
        render_tab2_reference_analytics_fragment(
            df_raw=df_raw,
            is_dark_mode=is_dark_mode,
            active_ref_lat=active_ref_lat,
            active_ref_lon=active_ref_lon,
            active_ref_prop=active_ref_prop,
            active_ref_radius=active_ref_radius,
            tab2_types=tab2_types
        )


# ----- TAB 3: ANALYTICS -----
with tab3:
    st.markdown("### <i class='fa-solid fa-chart-line' style='color:#059669; margin-right:8px;'></i>วิเคราะห์เชิงลึกและเปรียบเทียบสถิติของคู่แข่ง", unsafe_allow_html=True)
    
    if df_filtered.empty:
        st.warning("ไม่มีข้อมูลสำหรับจัดทำแผนภูมิวิเคราะห์สถิติ")
    else:
        # Create sub-tabs inside Tab 3
        sub_tab1, sub_tab2, sub_tab3 = st.tabs([
            "ภาพรวมตลาด (Market Overview)",
            "สัดส่วนสินค้าคู่แข่ง (Asset Type Focus)",
            "การกระจายตัวพอร์ตโฟลิโอรายบริษัท (Portfolio Deep Dive)"
        ])
        
        with sub_tab1:
            import streamlit.components.v1 as components
            import json
            
            # Explicit Brand Colors mapping in valid HEX strings for Plotly charts
            COMPANY_BRAND_COLORS = {
                "LED": "#0891b2",          # Cyan/Teal (#0891b2) - กรมบังคับคดี
                "SAM": "#10b981",          # Emerald (#10b981) - สุขุมวิท
                "BAM": "#3b82f6",          # Royal Blue (#3b82f6) - กรุงเทพพาณิชย์
                "Chayo555": "#f97316",     # Orange (#f97316) - ชโย
                "Chayo": "#f97316",
                "Chayo NPA": "#f97316",
                "GHB": "#ca8a04",          # Gold/Amber (#ca8a04) - ธอส.
                "KBANK": "#059669",        # Green (#059669) - กสิกร
                "KTB": "#0284c7",          # Sky Blue (#0284c7) - กรุงไทย
                "SCB": "#7e22ce",          # Purple (#7e22ce) - ไทยพาณิชย์
                "GSB": "#eb1985",          # Pink (#eb1985) - ออมสิน
                "DDproperty": "#a855f7",   # Violet (#a855f7)
                "Livinginsider": "#14b8a6",# Teal (#14b8a6)
                "NaYoo": "#8b5cf6",        # Violet (#8b5cf6)
                "ZmyHome": "#ec4899",      # Rose (#ec4899)
                "Baania": "#f59e0b"        # Amber (#f59e0b)
            }
            
            def get_comp_hex_color(c_name):
                if not c_name or pd.isna(c_name):
                    return '#3b82f6'
                return COMPANY_BRAND_COLORS.get(str(c_name).strip(), '#3b82f6')
            
            col_c1, col_c2 = st.columns(2)
            
            # 1. Total Assets by Company with Brand Colors & % Share Badges
            with col_c1:
                with st.container(border=True):
                    comp_counts = df_filtered['บริษัท'].value_counts().reset_index()
                    comp_counts.columns = ['บริษัท', 'จำนวนทรัพย์สิน']
                    tot_units_all = comp_counts['จำนวนทรัพย์สิน'].sum() if not comp_counts.empty else 1
                    comp_counts['pct_share'] = (comp_counts['จำนวนทรัพย์สิน'] / tot_units_all) * 100
                    
                    fig_comp = go.Figure(go.Bar(
                        x=comp_counts['บริษัท'],
                        y=comp_counts['จำนวนทรัพย์สิน'],
                        marker=dict(
                            color=[get_comp_hex_color(c) for c in comp_counts['บริษัท']],
                            cornerradius=10,
                            line=dict(width=1.2, color='rgba(255, 255, 255, 0.4)')
                        ),
                        text=[f"<b>{c:,}</b><br><span style='font-size:9.5px;color:#94a3b8;'>({p:.1f}%)</span>" for c, p in zip(comp_counts['จำนวนทรัพย์สิน'], comp_counts['pct_share'])],
                        textposition='outside',
                        textfont=dict(size=10.5, family="Noto Sans Thai, Inter, sans-serif"),
                        hovertemplate="<b>%{x}</b><br>จำนวนทรัพย์: <b>%{y:,}</b> รายการ<extra></extra>"
                    ))
                    fig_comp.update_layout(
                        title=dict(text='จำนวนรายการทรัพย์สินเปรียบเทียบแต่ละบริษัท (Market Share)', font=dict(size=14, family="Noto Sans Thai, Inter, sans-serif")),
                        yaxis=dict(title='จำนวนทรัพย์ (รายการ)', showgrid=True, gridcolor='rgba(255,255,255,0.06)' if is_dark_mode else 'rgba(0,0,0,0.05)', zeroline=False),
                        xaxis=dict(showgrid=False),
                        height=450,
                        margin=dict(t=50, b=20, l=10, r=10),
                        template=plotly_template,
                        plot_bgcolor='rgba(0,0,0,0)',
                        paper_bgcolor='rgba(0,0,0,0)'
                    )
                    st.plotly_chart(style_plotly_fig(fig_comp), width="stretch", theme=None)
                
            # 2. Distribution of Property Type in 3D Donut Chart
            with col_c2:
                with st.container(border=True):
                    type_counts = df_filtered['ประเภททรัพย์'].value_counts().head(8).reset_index()
                    type_counts.columns = ['ประเภททรัพย์', 'จำนวนประกาศ']
                    
                    vibrant_donut_colors = ['#10b981', '#3b82f6', '#f59e0b', '#06b6d4', '#8b5cf6', '#ec4899', '#14b8a6', '#64748b']
                    c2_series_data = [
                        {"name": row['ประเภททรัพย์'], "y": int(row['จำนวนประกาศ']), "color": vibrant_donut_colors[i % len(vibrant_donut_colors)]}
                        for i, (_, row) in enumerate(type_counts.iterrows())
                    ]
                    
                    text_color = "#f8fafc" if is_dark_mode else "#0f172a"
                    label_color = "#cbd5e1" if is_dark_mode else "#334155"
                    
                    html_c2 = f"""
                    <!DOCTYPE html>
                    <html>
                    <head>
                        <meta charset="utf-8">
                        <link rel="preconnect" href="https://fonts.googleapis.com">
                        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
                        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=Noto+Sans+Thai:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
                        <script src="https://cdnjs.cloudflare.com/ajax/libs/highcharts/11.4.3/highcharts.js"></script>
                        <script src="https://cdnjs.cloudflare.com/ajax/libs/highcharts/11.4.3/highcharts-3d.js"></script>
                        <style>
                            * {{ 
                                box-sizing: border-box; 
                                font-family: 'Noto Sans Thai', 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif !important;
                            }}
                            body {{
                                background: transparent;
                                margin: 0;
                                padding: 4px;
                                font-family: 'Noto Sans Thai', 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                                color: {text_color};
                                overflow: hidden;
                            }}
                            #chart_type_3d {{
                                height: 430px;
                                width: 100%;
                            }}
                        </style>
                    </head>
                    <body>
                        <div id="chart_type_3d"></div>
                        <script>
                            Highcharts.setOptions({{
                                chart: {{
                                    style: {{
                                        fontFamily: "'Noto Sans Thai', 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
                                    }}
                                }}
                            }});
                            Highcharts.chart('chart_type_3d', {{
                                chart: {{
                                    type: 'pie',
                                    options3d: {{
                                        enabled: true,
                                        alpha: 50,
                                        depth: 38
                                    }},
                                    backgroundColor: 'transparent',
                                    margin: [45, 10, 10, 10]
                                }},
                                title: {{
                                    text: 'สัดส่วนประเภททรัพย์หลัก (3D Asset Share)',
                                    align: 'left',
                                    style: {{ color: '{text_color}', fontSize: '14px', fontFamily: "'Noto Sans Thai', 'Inter', sans-serif", fontWeight: '700' }}
                                }},
                                subtitle: {{
                                    text: 'รวมทั้งหมด: <b style="color:#047857;">{tot_units_all:,} รายการ</b>',
                                    align: 'left',
                                    style: {{ color: '#64748b', fontSize: '12px', fontFamily: "'Noto Sans Thai', 'Inter', sans-serif" }}
                                }},
                                tooltip: {{
                                    headerFormat: '',
                                    pointFormat: '<b>{{point.name}}</b>: <b>{{point.y:,.0f}} รายการ</b> ({{point.percentage:.1f}}%)',
                                    style: {{ fontSize: '13px', fontFamily: "'Noto Sans Thai', 'Inter', sans-serif" }}
                                }},
                                plotOptions: {{
                                    pie: {{
                                        innerSize: 0,
                                        depth: 38,
                                        size: '72%',
                                        center: ['50%', '52%'],
                                        dataLabels: {{
                                            enabled: true,
                                            format: '{{point.name}}<br><b>{{point.percentage:.1f}}%</b>',
                                            distance: 14,
                                            style: {{
                                                color: '{label_color}',
                                                textOutline: 'none',
                                                fontSize: '12px',
                                                fontFamily: "'Noto Sans Thai', 'Inter', sans-serif",
                                                fontWeight: '600'
                                            }}
                                        }}
                                    }}
                                }},
                                series: [{{
                                    name: 'สัดส่วน',
                                    data: {json.dumps(c2_series_data)}
                                }}],
                                credits: {{ enabled: false }}
                            }});
                        </script>
                    </body>
                    </html>
                    """
                    components.html(html_c2, height=450, scrolling=False)
                
            st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)
            col_c3, col_c4 = st.columns(2)
            
            # 3. Top 10 Provinces with Cyber Gradient Horizontal Bars
            with col_c3:
                with st.container(border=True):
                    top_prov = df_filtered['จังหวัด'].value_counts().head(10).reset_index()
                    top_prov.columns = ['จังหวัด', 'จำนวนทรัพย์']
                    prov_tot = df_filtered['จังหวัด'].count() if not df_filtered.empty else 1
                    top_prov['pct'] = (top_prov['จำนวนทรัพย์'] / prov_tot) * 100
                    
                    fig_prov = go.Figure(go.Bar(
                        x=top_prov['จำนวนทรัพย์'],
                        y=top_prov['จังหวัด'],
                        orientation='h',
                        marker=dict(
                            color=top_prov['จำนวนทรัพย์'],
                            colorscale=[[0, '#06b6d4'], [0.45, '#3b82f6'], [1, '#4f46e5']],
                            cornerradius=10,
                            line=dict(width=1.5, color='rgba(255, 255, 255, 0.5)')
                        ),
                        text=[f"{c:,} ({p:.1f}%)" for c, p in zip(top_prov['จำนวนทรัพย์'], top_prov['pct'])],
                        textposition='outside',
                        textfont=dict(size=10.5, family="Noto Sans Thai, Inter, sans-serif", weight="bold"),
                        hovertemplate="จังหวัด: <b>%{y}</b><br>จำนวนทรัพย์: <b>%{x:,}</b> รายการ<extra></extra>"
                    ))
                    fig_prov.update_layout(
                        yaxis=dict(autorange="reversed"),
                        xaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.06)' if is_dark_mode else 'rgba(0,0,0,0.05)', zeroline=False),
                        title=dict(text='10 อันดับจังหวัดที่มีทรัพย์สินหนาแน่นที่สุด (Top 10 Locations)', font=dict(size=14, family="Noto Sans Thai, Inter, sans-serif")),
                        height=500,
                        margin=dict(t=50, b=20, l=10, r=10),
                        template=plotly_template,
                        plot_bgcolor='rgba(0,0,0,0)',
                        paper_bgcolor='rgba(0,0,0,0)'
                    )
                    st.plotly_chart(style_plotly_fig(fig_prov), width="stretch", theme=None)
                
            # 4. Price Distribution (Capped at 25 Million Baht)
            with col_c4:
                with st.container(border=True):
                    df_price_capped = df_filtered[(df_filtered['ราคา'].notna()) & (df_filtered['ราคา'] <= 25000000)].copy()
                    
                    # Simplify property type mapping for visualization
                    def map_simplified_type(t):
                        t_str = str(t).strip()
                        if 'ที่ดิน' in t_str:
                            return 'ที่ดินเปล่า'
                        elif 'คอนโด' in t_str or 'ห้องชุด' in t_str:
                            return 'ห้องชุดพักอาศัย'
                        elif 'บ้านเดี่ยว' in t_str or 'บ้านแฝด' in t_str or 'พูลวิลล่า' in t_str or 'บ้าน' in t_str:
                            return 'บ้านเดี่ยว'
                        elif 'ทาวน์โฮม' in t_str or 'ทาวน์เฮ้าส์' in t_str or 'ทาวน์เฮาส์' in t_str:
                            return 'ทาวน์เฮ้าส์'
                        return np.nan
                    
                    df_price_capped['ประเภททรัพย์_กลุ่ม'] = df_price_capped['ประเภททรัพย์'].apply(map_simplified_type)
                    df_price_capped = df_price_capped[df_price_capped['ประเภททรัพย์_กลุ่ม'].notna()]
                    
                    # Optimize by subsetting and sampling to 50k rows to prevent browser crash
                    df_hist_data = df_price_capped[['ราคา', 'ประเภททรัพย์_กลุ่ม']]
                    if len(df_hist_data) > 50000:
                        df_hist_data = df_hist_data.sample(n=50000, random_state=42)
                    
                    color_map_dist = {
                        "ที่ดินเปล่า": "#06b6d4",
                        "บ้านเดี่ยว": "#10b981", 
                        "ห้องชุดพักอาศัย": "#3b82f6",
                        "คอนโด": "#3b82f6", 
                        "ทาวน์เฮ้าส์": "#f59e0b"
                    }
                    
                    fig_price_dist = px.histogram(
                        df_hist_data,
                        x='ราคา',
                        color='ประเภททรัพย์_กลุ่ม',
                        nbins=40,
                        title='การกระจายตัวของราคาทรัพย์สิน (ไม่เกิน 25 ล้านบาท)',
                        labels={'ราคา': 'ราคาเริ่มต้น (บาท)', 'ประเภททรัพย์_กลุ่ม': 'ประเภททรัพย์'},
                        color_discrete_map=color_map_dist,
                        template=plotly_template,
                        marginal="box",
                        barmode="stack"
                    )
                    fig_price_dist.update_traces(
                        marker=dict(line=dict(width=0.8, color='rgba(255, 255, 255, 0.4)'), opacity=0.88)
                    )
                    fig_price_dist.update_layout(
                        title_font=dict(size=14, family="Noto Sans Thai, Inter, sans-serif"), 
                        yaxis_title="จำนวนรายการ",
                        xaxis_title="ราคาเริ่มต้น (บาท)",
                        height=500,
                        margin=dict(l=60, r=40, t=50, b=90),
                        plot_bgcolor='rgba(0,0,0,0)',
                        paper_bgcolor='rgba(0,0,0,0)'
                    )
                    st.plotly_chart(style_plotly_fig(fig_price_dist), width="stretch", theme=None)
                
        with sub_tab2:
            st.markdown("#### <i class='fa-solid fa-home-user' style='color:#059669; margin-right:6px;'></i>สัดส่วนประเภททรัพย์สินคู่แข่งเชิงลึก (Asset Type Focus)", unsafe_allow_html=True)
            
            st.markdown(
                f"<div style='font-size: 0.9rem; font-weight: 700; color: {'#f8fafc' if is_dark_mode else '#0f172a'}; margin-bottom: 4px; display: flex; align-items: center; gap: 6px;'>"
                f"<i class='fa-solid fa-sliders' style='color: #059669;'></i> เลือกเกณฑ์การวิเคราะห์:"
                f"</div>",
                unsafe_allow_html=True
            )
            focus_metric = st.radio(
                "เลือกเกณฑ์การวิเคราะห์", 
                ["จำนวนทรัพย์สิน (Asset Count)", "มูลค่าทรัพย์สินรวม (Total Value)"], 
                horizontal=True, 
                label_visibility="collapsed",
                key="focus_metric_type"
            )
            
            is_val_metric = (focus_metric == "มูลค่าทรัพย์สินรวม (Total Value)")
            
            if is_val_metric:
                value_col = 'มูลค่าทรัพย์สินรวม'
                # Group by and sum price
                comp_type_df = df_filtered.groupby(['บริษัท', 'ประเภททรัพย์'])['ราคา'].sum().reset_index(name=value_col)
                # Filter out types with 0 or NaN sum to avoid pie chart errors
                comp_type_df = comp_type_df[comp_type_df[value_col] > 0]
                hover_tmpl = "<b>%{label}</b><br>มูลค่ารวม: ฿%{value:,.0f}<br>สัดส่วน: %{percent}<extra>%{name}</extra>"
            else:
                value_col = 'จำนวนทรัพย์สิน'
                # Group by and count
                comp_type_df = df_filtered.groupby(['บริษัท', 'ประเภททรัพย์']).size().reset_index(name=value_col)
                hover_tmpl = "<b>%{label}</b><br>จำนวน: %{value:,} รายการ<br>สัดส่วน: %{percent}<extra>%{name}</extra>"
                
            # Curated modern property type palette
            PROPERTY_TYPE_COLORS = {
                'บ้านเดี่ยว': '#059669',       # Vibrant Emerald
                'ห้องชุดพักอาศัย': '#2563eb', # Royal Blue
                'ทาวน์เฮ้าส์': '#f59e0b',     # Vibrant Amber
                'ที่ดินเปล่า': '#06b6d4',     # Vivid Cyan
                'อาคารพาณิชย์': '#8b5cf6',    # Deep Violet
                'โรงงาน/โกดัง': '#ec4899',    # Bright Rose/Pink
                'บ้านแฝด': '#14b8a6',         # Fresh Teal
                'อื่นๆ': '#94a3b8'            # Slate Gray
            }
            other_color = '#94a3b8'

            # Sort with LED, SAM, BAM, Chayo555 / Chayo prioritized
            PREFERRED_COMPANY_ORDER = ["LED", "SAM", "BAM", "Chayo555", "Chayo", "Chayo NPA", "GHB", "KBANK", "KTB", "SCB", "GSB", "DDproperty", "Livinginsider", "NaYoo", "ZmyHome", "Baania"]
            all_comps = list(comp_type_df['บริษัท'].unique())
            companies = sorted(
                all_comps, 
                key=lambda c: (PREFERRED_COMPANY_ORDER.index(c) if c in PREFERRED_COMPANY_ORDER else 999, c)
            )

            if len(companies) > 0:
                import streamlit.components.v1 as components
                import json
                
                # Build data for 3D Donut Charts
                companies_3d_data = []
                for comp in companies:
                    comp_color = COMPANY_COLORS.get(comp, '#3b82f6')
                    cdf = comp_type_df[comp_type_df['บริษัท'] == comp].sort_values(value_col, ascending=False)
                    total = cdf[value_col].sum()
                    if total <= 0:
                        continue
                    
                    cdf = cdf.copy()
                    cdf['pct'] = (cdf[value_col] / total) * 100
                    major = cdf[cdf['pct'] >= 3.0]
                    minor = cdf[cdf['pct'] < 3.0]
                    
                    series_data = []
                    for _, r in major.iterrows():
                        t_name = r['ประเภททรัพย์']
                        t_pct = round(float(r['pct']), 1)
                        t_c = PROPERTY_TYPE_COLORS.get(t_name, '#6366f1')
                        series_data.append({"name": t_name, "y": t_pct, "color": t_c})
                        
                    if not minor.empty:
                        other_pct = round(float(minor['pct'].sum()), 1)
                        series_data.append({"name": "อื่นๆ", "y": other_pct, "color": other_color})
                        
                    total_display = f"฿{total/1e6:,.0f}M" if is_val_metric and total >= 1e6 else (f"{int(total):,} รายการ" if not is_val_metric else f"฿{total:,.0f}")
                    
                    pills = []
                    for _, r in cdf.head(3).iterrows():
                        t_name = r['ประเภททรัพย์']
                        t_pct = r['pct']
                        t_c = PROPERTY_TYPE_COLORS.get(t_name, '#6366f1')
                        pills.append({"name": t_name, "pct": t_pct, "color": t_c})
                        
                    companies_3d_data.append({
                        "company": comp,
                        "color": comp_color,
                        "total_str": total_display,
                        "pills": pills,
                        "series_data": series_data
                    })
                
                # HTML Theme styling
                card_bg = "rgba(15, 23, 42, 0.82)" if is_dark_mode else "linear-gradient(135deg, #ffffff 0%, #f8fafc 100%)"
                card_border = "rgba(255, 255, 255, 0.12)" if is_dark_mode else "rgba(226, 232, 240, 0.9)"
                text_color = "#f8fafc" if is_dark_mode else "#0f172a"
                label_color = "#e2e8f0" if is_dark_mode else "#1e293b"
                
                cards_html = ""
                js_init = ""
                for idx, item in enumerate(companies_3d_data):
                    comp = item['company']
                    comp_color = item['color']
                    total_str = item['total_str']
                    top_pills_html = "".join([
                        f"<span style='display:inline-block;background:{p['color']}18;color:{p['color']};border:1px solid {p['color']}40;border-radius:6px;padding:3px 8px;font-size:12px;font-weight:700;margin:2px 3px;'>{p['name']} {p['pct']:.0f}%</span>"
                        for p in item['pills']
                    ])
                    
                    cards_html += f"""
                    <div class="donut-card" style="border-top: 4px solid {comp_color};">
                        <div class="card-header">
                            <span style="color: {comp_color}; font-weight: 800; font-size: 18px;"><i class="fa-solid fa-building" style="margin-right:6px; font-size:15px;"></i>{comp}</span>
                            <span style="color: #64748b; font-weight: 700; font-size: 14.5px;">รวม: <b style="color:{text_color};">{total_str}</b></span>
                        </div>
                        <div style="text-align:center; margin-top:4px; margin-bottom: 6px;">{top_pills_html}</div>
                        <div id="chart3d_{idx}" class="chart-box"></div>
                    </div>
                    """
                    
                    series_json = json.dumps(item['series_data'])
                    js_init += f"""
                    Highcharts.chart('chart3d_{idx}', {{
                        chart: {{
                            type: 'pie',
                            options3d: {{
                                enabled: true,
                                alpha: 48,
                                beta: 0,
                                depth: 36
                            }},
                            backgroundColor: 'transparent',
                            margin: [10, 24, 10, 24]
                        }},
                        title: {{ text: null }},
                        tooltip: {{
                            headerFormat: '',
                            pointFormat: '<b>{{point.name}}</b>: <b>{{point.y:.1f}}%</b>',
                            style: {{ fontSize: '13px', fontFamily: 'Noto Sans Thai' }}
                        }},
                        plotOptions: {{
                            pie: {{
                                innerSize: 0,
                                depth: 36,
                                size: '64%',
                                center: ['50%', '50%'],
                                dataLabels: {{
                                    enabled: true,
                                    crop: false,
                                    overflow: 'allow',
                                    distance: 10,
                                    connectorPadding: 2,
                                    connectorWidth: 1.2,
                                    formatter: function() {{
                                        var n = this.point.name;
                                        if (n === 'ที่ดินพร้อมสิ่งปลูกสร้าง') n = 'ที่ดิน+สิ่งปลูกสร้าง';
                                        return n + '<br><b>' + this.point.y.toFixed(1) + '%</b>';
                                    }},
                                    style: {{
                                        color: '{label_color}',
                                        textOutline: 'none',
                                        fontSize: '11.5px',
                                        fontWeight: '700',
                                        fontFamily: 'Noto Sans Thai, Inter, sans-serif'
                                    }}
                                }}
                            }}
                        }},
                        series: [{{
                            name: 'สัดส่วน',
                            data: {series_json}
                        }}],
                        credits: {{ enabled: false }}
                    }});
                    """
                
                # Responsive height estimate based on flexible wrapping (~2-3 cards per row baseline)
                n_items = len(companies_3d_data)
                est_rows = (n_items + 1) // 2
                total_height = max(580, est_rows * 520 + 40)
                
                full_html = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <meta charset="utf-8">
                    <link rel="preconnect" href="https://fonts.googleapis.com">
                    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
                    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=Noto+Sans+Thai:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
                    <script src="https://cdnjs.cloudflare.com/ajax/libs/highcharts/11.4.3/highcharts.js"></script>
                    <script src="https://cdnjs.cloudflare.com/ajax/libs/highcharts/11.4.3/highcharts-3d.js"></script>
                    <style>
                        * {{ 
                            box-sizing: border-box; 
                            font-family: 'Noto Sans Thai', 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif !important;
                        }}
                        body {{
                            background: transparent;
                            margin: 0;
                            padding: 4px;
                            font-family: 'Noto Sans Thai', 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                            color: {text_color};
                        }}
                        .grid-container {{
                            display: grid;
                            grid-template-columns: repeat(auto-fill, minmax(460px, 1fr));
                            gap: 20px;
                            width: 100%;
                        }}
                        .donut-card {{
                            background: {card_bg};
                            border: 1px solid {card_border};
                            border-radius: 16px;
                            padding: 18px 10px 12px 10px;
                            box-shadow: 0 8px 24px rgba(0,0,0,0.08);
                            display: flex;
                            flex-direction: column;
                            justify-content: space-between;
                            min-width: 0;
                            transition: transform 0.2s ease, box-shadow 0.2s ease;
                        }}
                        .donut-card:hover {{
                            transform: translateY(-3px);
                            box-shadow: 0 12px 30px rgba(0,0,0,0.14);
                        }}
                        .card-header {{
                            display: flex;
                            justify-content: space-between;
                            align-items: center;
                            margin-bottom: 8px;
                        }}
                        .chart-box {{
                            height: 390px;
                            width: 100%;
                        }}
                    </style>
                </head>
                <body>
                    <div class="grid-container">
                        {cards_html}
                    </div>
                    <script>
                        Highcharts.setOptions({{
                            chart: {{
                                style: {{
                                    fontFamily: "'Noto Sans Thai', 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
                                }}
                            }}
                        }});
                        {js_init}
                        
                        function notifyResize() {{
                            try {{
                                const docH = Math.max(
                                    document.body.scrollHeight, 
                                    document.documentElement.scrollHeight,
                                    document.body.offsetHeight,
                                    document.documentElement.offsetHeight
                                );
                                if (window.frameElement) {{
                                    window.frameElement.style.height = (docH + 25) + 'px';
                                }}
                                window.parent.postMessage({{
                                    type: 'streamlit:setFrameHeight',
                                    height: docH + 25
                                }}, '*');
                            }} catch(e) {{}}
                        }}

                        window.addEventListener('DOMContentLoaded', notifyResize);
                        window.addEventListener('load', function() {{
                            notifyResize();
                            setTimeout(notifyResize, 250);
                            setTimeout(notifyResize, 600);
                        }});
                        window.addEventListener('resize', function() {{
                            if (window.Highcharts && Highcharts.charts) {{
                                Highcharts.charts.forEach(function(c) {{
                                    if (c) c.reflow();
                                }});
                            }}
                            notifyResize();
                        }});
                        if (window.ResizeObserver) {{
                            new ResizeObserver(function() {{
                                notifyResize();
                            }}).observe(document.body);
                        }}
                    </script>
                </body>
                </html>
                """
                
                components.html(full_html, height=total_height, scrolling=False)

        # -----------------------------------------------------------------
        # SUB-TAB 3: การกระจายตัวพอร์ตโฟลิโอรายบริษัท (Company Portfolio Deep Dive)
        # -----------------------------------------------------------------
        with sub_tab3:
            col_head1, col_head2, col_head3 = st.columns([1.8, 1.1, 1.1])
            with col_head1:
                st.markdown("#### <i class='fa-solid fa-scale-balanced' style='color:#059669; margin-right:6px;'></i>การกระจายตัวเชิงลึกของพอร์ตโฟลิโอรายบริษัท", unsafe_allow_html=True)
                st.caption("วิเคราะห์และเปรียบเทียบการกระจายตัวตามช่วงราคา และประเภททรัพย์สินหลักระหว่างบริษัท")
            
            # Extract list of available companies
            comp_list_avail = []
            if not df_filtered.empty:
                comp_list_avail = list(df_filtered['บริษัท'].dropna().unique())
            elif df_raw is not None and not df_raw.empty:
                comp_list_avail = list(df_raw['บริษัท'].dropna().unique())
                
            PREFERRED_COMPANY_ORDER = ["LED", "SAM", "BAM", "Chayo555", "Chayo", "Chayo NPA", "GHB", "KBANK", "KTB", "SCB", "GSB", "DDproperty", "Livinginsider", "NaYoo", "ZmyHome", "Baania"]
            comp_options = sorted(
                comp_list_avail, 
                key=lambda c: (PREFERRED_COMPANY_ORDER.index(c) if c in PREFERRED_COMPANY_ORDER else 999, c)
            )
            
            default_idx1 = comp_options.index("SAM") if "SAM" in comp_options else 0
            
            with col_head2:
                st.markdown(
                    f"<div style='font-size: 0.9rem; font-weight: 700; color: {'#f8fafc' if is_dark_mode else '#0f172a'}; margin-bottom: 4px; display: flex; align-items: center; gap: 6px;'>"
                    f"<i class='fa-solid fa-building' style='color: #059669;'></i> บริษัทหลัก (Company 1):"
                    f"</div>",
                    unsafe_allow_html=True
                )
                selected_company = st.selectbox(
                    "บริษัทหลัก (Company 1):",
                    options=comp_options,
                    index=default_idx1,
                    label_visibility="collapsed",
                    key="tab2_subtab3_selected_company"
                )
                
            comp_2_options = ["(ไม่เปรียบเทียบ - ดูบริษัทเดียว)"] + [c for c in comp_options if c != selected_company]
            if selected_company == "SAM" and "BAM" in comp_2_options:
                def_idx2 = comp_2_options.index("BAM")
            elif selected_company == "BAM" and "SAM" in comp_2_options:
                def_idx2 = comp_2_options.index("SAM")
            elif len(comp_2_options) > 1:
                def_idx2 = 1
            else:
                def_idx2 = 0

            with col_head3:
                st.markdown(
                    f"<div style='font-size: 0.9rem; font-weight: 700; color: {'#f8fafc' if is_dark_mode else '#0f172a'}; margin-bottom: 4px; display: flex; align-items: center; gap: 6px;'>"
                    f"<i class='fa-solid fa-arrows-left-right' style='color: #059669;'></i> เปรียบเทียบกับ (Company 2):"
                    f"</div>",
                    unsafe_allow_html=True
                )
                compare_company = st.selectbox(
                    "เปรียบเทียบกับ (Company 2):",
                    options=comp_2_options,
                    index=def_idx2,
                    label_visibility="collapsed",
                    key="tab2_subtab3_compare_company"
                )
                
            comp_bar_color = COMP_BRAND_COLORS.get(selected_company, "#10b981")
            comp2_bar_color = COMP_BRAND_COLORS.get(compare_company, "#3b82f6")

            comp_df_tab2 = df_filtered[df_filtered['บริษัท'] == selected_company].copy() if not df_filtered.empty else pd.DataFrame()
            if comp_df_tab2.empty and df_raw is not None:
                comp_df_tab2 = df_raw[df_raw['บริษัท'] == selected_company].copy()

            # Check if comparison mode is active
            is_comparing = (compare_company != "(ไม่เปรียบเทียบ - ดูบริษัทเดียว)")
            comp_df_2 = pd.DataFrame()
            if is_comparing:
                comp_df_2 = df_filtered[df_filtered['บริษัท'] == compare_company].copy() if not df_filtered.empty else pd.DataFrame()
                if comp_df_2.empty and df_raw is not None:
                    comp_df_2 = df_raw[df_raw['บริษัท'] == compare_company].copy()

            if comp_df_tab2.empty and (not is_comparing or comp_df_2.empty):
                st.warning(f"ไม่พบข้อมูลทรัพย์สินของ {selected_company} ในตัวกรองปัจจุบัน")
            elif is_comparing and not comp_df_2.empty:
                # ==========================================
                # COMPARISON MODE: Company 1 vs Company 2
                # ==========================================
                comp_df_tab2['Price_Tier'] = comp_df_tab2['ราคา'].apply(get_price_tier)
                comp_df_2['Price_Tier'] = comp_df_2['ราคา'].apply(get_price_tier)

                # 1. Summary KPI Comparison Cards
                c1_cnt, c2_cnt = len(comp_df_tab2), len(comp_df_2)
                c1_val, c2_val = comp_df_tab2['ราคา'].sum() / 1e6, comp_df_2['ราคา'].sum() / 1e6
                c1_avg, c2_avg = (comp_df_tab2['ราคา'].mean() / 1e6) if c1_cnt > 0 else 0, (comp_df_2['ราคา'].mean() / 1e6) if c2_cnt > 0 else 0
                c1_med, c2_med = (comp_df_tab2['ราคา'].median() / 1e6) if c1_cnt > 0 else 0, (comp_df_2['ราคา'].median() / 1e6) if c2_cnt > 0 else 0

                card_bg = 'rgba(15, 23, 42, 0.75)' if is_dark_mode else 'linear-gradient(135deg, #ffffff 0%, #f8fafc 100%)'
                card_border = 'rgba(255, 255, 255, 0.1)' if is_dark_mode else 'rgba(226, 232, 240, 0.8)'

                st.markdown(f"""
                <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin-top: 6px; margin-bottom: 20px;">
                    <div style="background: {card_bg}; border: 1px solid {card_border}; border-left: 4px solid {comp_bar_color}; border-radius: 12px; padding: 14px 16px; box-shadow: 0 4px 16px rgba(0,0,0,0.06);">
                        <div style="font-size: 0.78rem; font-weight: 700; color: #64748b; margin-bottom: 6px;"><i class="fa fa-boxes"></i> จำนวนทรัพย์รวม (Units)</div>
                        <div style="display: flex; justify-content: space-between; align-items: baseline; margin-top: 4px;">
                            <span style="font-size: 1.05rem; font-weight: 800; color: {comp_bar_color};">{selected_company}: <b>{c1_cnt:,}</b></span>
                            <span style="font-size: 1.05rem; font-weight: 800; color: {comp2_bar_color};">{compare_company}: <b>{c2_cnt:,}</b></span>
                        </div>
                    </div>
                    <div style="background: {card_bg}; border: 1px solid {card_border}; border-left: 4px solid #f59e0b; border-radius: 12px; padding: 14px 16px; box-shadow: 0 4px 16px rgba(0,0,0,0.06);">
                        <div style="font-size: 0.78rem; font-weight: 700; color: #64748b; margin-bottom: 6px;"><i class="fa fa-coins"></i> มูลค่าพอร์ตโฟลิโอรวม (MB)</div>
                        <div style="display: flex; justify-content: space-between; align-items: baseline; margin-top: 4px;">
                            <span style="font-size: 1.05rem; font-weight: 800; color: {comp_bar_color};">{selected_company}: <b>฿{c1_val:,.0f}M</b></span>
                            <span style="font-size: 1.05rem; font-weight: 800; color: {comp2_bar_color};">{compare_company}: <b>฿{c2_val:,.0f}M</b></span>
                        </div>
                    </div>
                    <div style="background: {card_bg}; border: 1px solid {card_border}; border-left: 4px solid #8b5cf6; border-radius: 12px; padding: 14px 16px; box-shadow: 0 4px 16px rgba(0,0,0,0.06);">
                        <div style="font-size: 0.78rem; font-weight: 700; color: #64748b; margin-bottom: 6px;"><i class="fa fa-tag"></i> ราคาเฉลี่ยต่อยูนิต (Avg Price)</div>
                        <div style="display: flex; justify-content: space-between; align-items: baseline; margin-top: 4px;">
                            <span style="font-size: 1.05rem; font-weight: 800; color: {comp_bar_color};">{selected_company}: <b>฿{c1_avg:,.2f}M</b></span>
                            <span style="font-size: 1.05rem; font-weight: 800; color: {comp2_bar_color};">{compare_company}: <b>฿{c2_avg:,.2f}M</b></span>
                        </div>
                    </div>
                    <div style="background: {card_bg}; border: 1px solid {card_border}; border-left: 4px solid #06b6d4; border-radius: 12px; padding: 14px 16px; box-shadow: 0 4px 16px rgba(0,0,0,0.06);">
                        <div style="font-size: 0.78rem; font-weight: 700; color: #64748b; margin-bottom: 6px;"><i class="fa fa-balance-scale"></i> ราคามัธยฐาน (Median Price)</div>
                        <div style="display: flex; justify-content: space-between; align-items: baseline; margin-top: 4px;">
                            <span style="font-size: 1.05rem; font-weight: 800; color: {comp_bar_color};">{selected_company}: <b>฿{c1_med:,.2f}M</b></span>
                            <span style="font-size: 1.05rem; font-weight: 800; color: {comp2_bar_color};">{compare_company}: <b>฿{c2_med:,.2f}M</b></span>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                col_c1, col_c2 = st.columns(2)
                with col_c1:
                    # Chart 1: Grouped Price Tier Bar with Gradients & Total Value Lines
                    tier1 = comp_df_tab2.groupby('Price_Tier', observed=False).agg(count=('ราคา', 'count'), val=('ราคา', 'sum')).reindex(PRICE_TIER_ORDER).reset_index().fillna(0)
                    tier2 = comp_df_2.groupby('Price_Tier', observed=False).agg(count=('ราคา', 'count'), val=('ราคา', 'sum')).reindex(PRICE_TIER_ORDER).reset_index().fillna(0)
                    tier1['val_million'] = tier1['val'] / 1e6
                    tier2['val_million'] = tier2['val'] / 1e6

                    grad1 = get_gradient_palette(selected_company, len(PRICE_TIER_ORDER))
                    grad2 = get_gradient_palette(compare_company, len(PRICE_TIER_ORDER))

                    fig_tier_comp = go.Figure()
                    # Bars (Count)
                    fig_tier_comp.add_trace(go.Bar(
                        x=tier1['Price_Tier'],
                        y=tier1['count'],
                        name=f'{selected_company} (จำนวนทรัพย์)',
                        yaxis='y',
                        marker=dict(
                            color=grad1,
                            cornerradius=8,
                            line=dict(width=1.2, color='rgba(255, 255, 255, 0.4)')
                        ),
                        text=[f"{int(c):,}" for c in tier1['count']],
                        textposition='outside',
                        textfont=dict(size=11, family="Noto Sans Thai", weight="bold"),
                        hovertemplate=f"<b>{selected_company}</b><br>ช่วงราคา: %{{x}}<br>จำนวนทรัพย์: <b>%{{y:,}}</b> รายการ<extra></extra>"
                    ))
                    fig_tier_comp.add_trace(go.Bar(
                        x=tier2['Price_Tier'],
                        y=tier2['count'],
                        name=f'{compare_company} (จำนวนทรัพย์)',
                        yaxis='y',
                        marker=dict(
                            color=grad2,
                            cornerradius=8,
                            line=dict(width=1.2, color='rgba(255, 255, 255, 0.4)')
                        ),
                        text=[f"{int(c):,}" for c in tier2['count']],
                        textposition='outside',
                        textfont=dict(size=11, family="Noto Sans Thai", weight="bold"),
                        hovertemplate=f"<b>{compare_company}</b><br>ช่วงราคา: %{{x}}<br>จำนวนทรัพย์: <b>%{{y:,}}</b> รายการ<extra></extra>"
                    ))
                    # Lines (Total Value MB)
                    fig_tier_comp.add_trace(go.Scatter(
                        x=tier1['Price_Tier'],
                        y=tier1['val_million'],
                        name=f'{selected_company} (มูลค่ารวม MB)',
                        yaxis='y2',
                        mode='lines+markers+text',
                        line=dict(width=3, color=comp_bar_color, shape='spline'),
                        marker=dict(size=8, color=comp_bar_color, line=dict(width=2, color='#ffffff')),
                        text=[f"฿{v:,.0f}M" if v > 0 else "" for v in tier1['val_million']],
                        textposition='top center',
                        textfont=dict(size=10, family="Noto Sans Thai", color=comp_bar_color, weight="bold"),
                        hovertemplate=f"มูลค่ารวม {selected_company}: <b>฿%{{y:,.1f}}M</b><extra></extra>"
                    ))
                    fig_tier_comp.add_trace(go.Scatter(
                        x=tier2['Price_Tier'],
                        y=tier2['val_million'],
                        name=f'{compare_company} (มูลค่ารวม MB)',
                        yaxis='y2',
                        mode='lines+markers+text',
                        line=dict(width=3, color=comp2_bar_color, shape='spline', dash='dot'),
                        marker=dict(size=8, color=comp2_bar_color, line=dict(width=2, color='#ffffff')),
                        text=[f"฿{v:,.0f}M" if v > 0 else "" for v in tier2['val_million']],
                        textposition='top center',
                        textfont=dict(size=10, family="Noto Sans Thai", color=comp2_bar_color, weight="bold"),
                        hovertemplate=f"มูลค่ารวม {compare_company}: <b>฿%{{y:,.1f}}M</b><extra></extra>"
                    ))

                    fig_tier_comp.update_layout(
                        title=dict(text=f'เปรียบเทียบจำนวนทรัพย์และมูลค่าตามช่วงราคา ({selected_company} vs {compare_company})', font=dict(size=14, family="Noto Sans Thai")),
                        barmode='group',
                        bargroupgap=0.1,
                        bargap=0.25,
                        yaxis=dict(title='จำนวนทรัพย์ (รายการ)', showgrid=True, gridcolor='rgba(255,255,255,0.06)' if is_dark_mode else 'rgba(0,0,0,0.05)', zeroline=False),
                        yaxis2=dict(title='มูลค่ารวม (ล้านบาท)', overlaying='y', side='right', showgrid=False, zeroline=False),
                        xaxis=dict(showgrid=False),
                        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(family="Noto Sans Thai", size=11)),
                        height=480,
                        margin=dict(t=60, b=20, l=10, r=10),
                        template=plotly_template,
                        plot_bgcolor='rgba(0,0,0,0)',
                        paper_bgcolor='rgba(0,0,0,0)'
                    )
                    st.plotly_chart(style_plotly_fig(fig_tier_comp), width="stretch", theme=None)

                with col_c2:
                    # Chart 2: Grouped Box Plot of Top Common Property Types
                    top_types1 = comp_df_tab2['ประเภททรัพย์'].value_counts().head(6).index.tolist()
                    top_types2 = comp_df_2['ประเภททรัพย์'].value_counts().head(6).index.tolist()
                    combined_top = list(dict.fromkeys(top_types1 + top_types2))[:6]

                    box_df = pd.concat([comp_df_tab2, comp_df_2], ignore_index=True)
                    box_df = box_df[box_df['ประเภททรัพย์'].isin(combined_top) & (box_df['ราคา'] > 0)]
                    box_df['val_million'] = box_df['ราคา'] / 1e6

                    fig_box = px.box(
                        box_df,
                        x='ประเภททรัพย์',
                        y='val_million',
                        color='บริษัท',
                        color_discrete_map={selected_company: comp_bar_color, compare_company: comp2_bar_color},
                        title=f'เปรียบเทียบการกระจายราคาของ 6 ประเภททรัพย์หลัก ({selected_company} vs {compare_company})',
                        template=plotly_template,
                        points=False
                    )
                    fig_box.update_traces(
                        boxmean=True,
                        line=dict(width=1.5),
                        marker=dict(opacity=0.85)
                    )
                    fig_box.update_layout(
                        title_font=dict(size=14, family="Noto Sans Thai"),
                        height=460, 
                        yaxis_type="log",
                        yaxis_title="ราคา (ล้านบาท - สเกล Log)",
                        yaxis=dict(
                            showgrid=True, 
                            gridcolor='rgba(255,255,255,0.06)' if is_dark_mode else 'rgba(0,0,0,0.05)',
                            tickmode='array',
                            tickvals=[0.5, 1, 2, 5, 10, 20, 50, 100],
                            ticktext=['฿0.5M', '฿1M', '฿2M', '฿5M', '฿10M', '฿20M', '฿50M', '฿100M']
                        ),
                        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(family="Noto Sans Thai", size=12)),
                        margin=dict(t=50, b=20, l=10, r=10),
                        plot_bgcolor='rgba(0,0,0,0)',
                        paper_bgcolor='rgba(0,0,0,0)'
                    )
                    st.plotly_chart(style_plotly_fig(fig_box), width="stretch", theme=None)

                col_c3, col_c4 = st.columns(2)
                with col_c3:
                    # Chart 3: Asset Type Share (%) with Sleek Horizontal Gradient Bars
                    t_share1 = comp_df_tab2['ประเภททรัพย์'].value_counts(normalize=True).head(6).reset_index()
                    t_share1.columns = ['ประเภททรัพย์', 'pct']
                    t_share1['pct'] = t_share1['pct'] * 100
                    t_share1['บริษัท'] = selected_company

                    t_share2 = comp_df_2['ประเภททรัพย์'].value_counts(normalize=True).head(6).reset_index()
                    t_share2.columns = ['ประเภททรัพย์', 'pct']
                    t_share2['pct'] = t_share2['pct'] * 100
                    t_share2['บริษัท'] = compare_company

                    # Use combined order so both companies align
                    common_types = list(dict.fromkeys(t_share1['ประเภททรัพย์'].tolist() + t_share2['ประเภททรัพย์'].tolist()))[:6]
                    t_share1_full = t_share1.set_index('ประเภททรัพย์').reindex(common_types).fillna(0).reset_index()
                    t_share2_full = t_share2.set_index('ประเภททรัพย์').reindex(common_types).fillna(0).reset_index()

                    grad_share1 = get_gradient_palette(selected_company, len(common_types))
                    grad_share2 = get_gradient_palette(compare_company, len(common_types))

                    fig_share = go.Figure()
                    fig_share.add_trace(go.Bar(
                        y=common_types,
                        x=t_share1_full['pct'],
                        name=f'{selected_company}',
                        orientation='h',
                        marker=dict(
                            color=grad_share1,
                            cornerradius=8,
                            line=dict(width=1.2, color='rgba(255, 255, 255, 0.4)')
                        ),
                        text=[f"{p:.1f}%" if p > 0 else "" for p in t_share1_full['pct']],
                        textposition='outside',
                        textfont=dict(size=11, family="Noto Sans Thai", weight="bold"),
                        hovertemplate=f"<b>{selected_company}</b><br>ประเภท: %{{y}}<br>สัดส่วน: <b>%{{x:.1f}}%</b><extra></extra>"
                    ))
                    fig_share.add_trace(go.Bar(
                        y=common_types,
                        x=t_share2_full['pct'],
                        name=f'{compare_company}',
                        orientation='h',
                        marker=dict(
                            color=grad_share2,
                            cornerradius=8,
                            line=dict(width=1.2, color='rgba(255, 255, 255, 0.4)')
                        ),
                        text=[f"{p:.1f}%" if p > 0 else "" for p in t_share2_full['pct']],
                        textposition='outside',
                        textfont=dict(size=11, family="Noto Sans Thai", weight="bold"),
                        hovertemplate=f"<b>{compare_company}</b><br>ประเภท: %{{y}}<br>สัดส่วน: <b>%{{x:.1f}}%</b><extra></extra>"
                    ))
                    fig_share.update_layout(
                        title=dict(text=f'สัดส่วนประเภททรัพย์ในพอร์ตโฟลิโอ (% Share)', font=dict(size=14, family="Noto Sans Thai")),
                        barmode='group',
                        bargroupgap=0.1,
                        bargap=0.25,
                        xaxis_title="สัดส่วนในพอร์ตโฟลิโอ (%)",
                        xaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.06)' if is_dark_mode else 'rgba(0,0,0,0.05)', zeroline=False),
                        yaxis_title="",
                        yaxis=dict(autorange="reversed"),
                        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(family="Noto Sans Thai", size=12)),
                        height=440,
                        margin=dict(t=50, b=20, l=10, r=10),
                        template=plotly_template,
                        plot_bgcolor='rgba(0,0,0,0)',
                        paper_bgcolor='rgba(0,0,0,0)'
                    )
                    st.plotly_chart(style_plotly_fig(fig_share), width="stretch", theme=None)

                with col_c4:
                    # Chart 4: Region distribution with Rounded Gradient Bars
                    if 'ภาค' in comp_df_tab2.columns and 'ภาค' in comp_df_2.columns:
                        regions_all = ["ภาคกลาง", "ภาคเหนือ", "ภาคตะวันออกเฉียงเหนือ", "ภาคตะวันออก", "ภาคใต้", "ภาคตะวันตก"]
                        r1 = comp_df_tab2['ภาค'].value_counts().reindex(regions_all).fillna(0).reset_index()
                        r1.columns = ['ภาค', 'count']
                        r2 = comp_df_2['ภาค'].value_counts().reindex(regions_all).fillna(0).reset_index()
                        r2.columns = ['ภาค', 'count']

                        grad_reg1 = get_gradient_palette(selected_company, len(regions_all))
                        grad_reg2 = get_gradient_palette(compare_company, len(regions_all))

                        fig_region = go.Figure()
                        fig_region.add_trace(go.Bar(
                            x=regions_all,
                            y=r1['count'],
                            name=f'{selected_company}',
                            marker=dict(
                                color=grad_reg1,
                                cornerradius=8,
                                line=dict(width=1.2, color='rgba(255, 255, 255, 0.4)')
                            ),
                            text=[f"{int(c):,}" if c > 0 else "" for c in r1['count']],
                            textposition='outside',
                            textfont=dict(size=11, family="Noto Sans Thai", weight="bold"),
                            hovertemplate=f"<b>{selected_company}</b><br>ภูมิภาค: %{{x}}<br>จำนวน: <b>%{{y:,}}</b> รายการ<extra></extra>"
                        ))
                        fig_region.add_trace(go.Bar(
                            x=regions_all,
                            y=r2['count'],
                            name=f'{compare_company}',
                            marker=dict(
                                color=grad_reg2,
                                cornerradius=8,
                                line=dict(width=1.2, color='rgba(255, 255, 255, 0.4)')
                            ),
                            text=[f"{int(c):,}" if c > 0 else "" for c in r2['count']],
                            textposition='outside',
                            textfont=dict(size=11, family="Noto Sans Thai", weight="bold"),
                            hovertemplate=f"<b>{compare_company}</b><br>ภูมิภาค: %{{x}}<br>จำนวน: <b>%{{y:,}}</b> รายการ<extra></extra>"
                        ))
                        fig_region.update_layout(
                            title=dict(text=f'เปรียบเทียบการกระจายตัวตามภูมิภาค ({selected_company} vs {compare_company})', font=dict(size=14, family="Noto Sans Thai")),
                            barmode='group',
                            bargroupgap=0.1,
                            bargap=0.25,
                            xaxis_title="ภูมิภาค",
                            xaxis=dict(showgrid=False),
                            yaxis_title="จำนวนทรัพย์ (รายการ)",
                            yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.06)' if is_dark_mode else 'rgba(0,0,0,0.05)', zeroline=False),
                            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(family="Noto Sans Thai", size=12)),
                            height=440,
                            margin=dict(t=50, b=20, l=10, r=10),
                            template=plotly_template,
                            plot_bgcolor='rgba(0,0,0,0)',
                            paper_bgcolor='rgba(0,0,0,0)'
                        )
                        st.plotly_chart(style_plotly_fig(fig_region), width="stretch", theme=None)
            else:
                # ==========================================
                # SINGLE COMPANY MODE: Rich Gradients & Dual Y-Axis Glow
                # ==========================================
                comp_df_tab2['Price_Tier'] = comp_df_tab2['ราคา'].apply(get_price_tier)

                col_s1, col_s2 = st.columns(2)
                with col_s1:
                    tier_df = comp_df_tab2.groupby('Price_Tier', observed=False).agg(
                        count=('รหัสทรัพย์', 'count') if 'รหัสทรัพย์' in comp_df_tab2.columns else ('ราคา', 'count'),
                        total_val=('ราคา', 'sum')
                    ).reindex(PRICE_TIER_ORDER).reset_index()
                    tier_df['count'] = tier_df['count'].fillna(0)
                    tier_df['val_million'] = tier_df['total_val'].fillna(0) / 1e6

                    single_grad = get_gradient_palette(selected_company, len(PRICE_TIER_ORDER))

                    fig_tier = go.Figure()
                    fig_tier.add_trace(go.Bar(
                        x=tier_df['Price_Tier'],
                        y=tier_df['count'],
                        name='จำนวนทรัพย์ (รายการ)',
                        marker=dict(
                            color=single_grad,
                            cornerradius=8,
                            line=dict(width=1.2, color='rgba(255, 255, 255, 0.45)')
                        ),
                        yaxis='y',
                        text=tier_df['count'].astype(int),
                        textposition='outside',
                        textfont=dict(size=11, family="Noto Sans Thai", weight="bold"),
                        hovertemplate=f"<b>{selected_company}</b><br>ช่วงราคา: %{{x}}<br>จำนวนทรัพย์: <b>%{{y:,}}</b> รายการ<extra></extra>"
                    ))
                    fig_tier.add_trace(go.Scatter(
                        x=tier_df['Price_Tier'],
                        y=tier_df['val_million'],
                        name='มูลค่ารวม (ล้านบาท)',
                        mode='lines+markers+text',
                        text=[f"฿{v:,.0f}M" for v in tier_df['val_million']],
                        textposition='top center',
                        textfont=dict(size=11, family="Noto Sans Thai", color="#3b82f6", weight="bold"),
                        yaxis='y2',
                        line=dict(width=3.5, color='#3b82f6', shape='spline'),
                        marker=dict(size=9, color='#3b82f6', line=dict(width=2, color='#ffffff')),
                        fill='tozeroy',
                        fillcolor='rgba(59, 130, 246, 0.08)',
                        hovertemplate="มูลค่ารวม: <b>฿%{y:,.1f}M</b><extra></extra>"
                    ))
                    fig_tier.update_layout(
                        title=dict(text=f'การกระจายตัวตามช่วงราคา {selected_company} (Price Tier Pyramid)', font=dict(size=14, family="Noto Sans Thai")),
                        yaxis=dict(title='จำนวนทรัพย์ (รายการ)', showgrid=True, gridcolor='rgba(255,255,255,0.06)' if is_dark_mode else 'rgba(0,0,0,0.05)', zeroline=False),
                        yaxis2=dict(title='มูลค่ารวม (ล้านบาท)', overlaying='y', side='right', showgrid=False),
                        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(family="Noto Sans Thai", size=12)),
                        height=460,
                        margin=dict(t=50, b=20, l=10, r=10),
                        template=plotly_template,
                        plot_bgcolor='rgba(0,0,0,0)',
                        paper_bgcolor='rgba(0,0,0,0)'
                    )
                    st.plotly_chart(style_plotly_fig(fig_tier), width="stretch", theme=None)

                with col_s2:
                    top_types = comp_df_tab2['ประเภททรัพย์'].value_counts().head(6).index.tolist()
                    box_data = comp_df_tab2[comp_df_tab2['ประเภททรัพย์'].isin(top_types) & (comp_df_tab2['ราคา'] > 0)].copy()
                    box_data['val_million'] = box_data['ราคา'] / 1e6
                    
                    fig_box = px.box(
                        box_data,
                        x='ประเภททรัพย์',
                        y='val_million',
                        color='ประเภททรัพย์',
                        title=f'การกระจายราคาของ 6 ประเภททรัพย์หลัก {selected_company} (Box Plot - ล้านบาท)',
                        template=plotly_template,
                        color_discrete_sequence=get_gradient_palette(selected_company, len(top_types)),
                        points=False
                    )
                    fig_box.update_traces(
                        boxmean=True,
                        line=dict(width=1.5),
                        marker=dict(opacity=0.85)
                    )
                    fig_box.update_layout(
                        title_font=dict(size=14, family="Noto Sans Thai"),
                        height=460, 
                        showlegend=False, 
                        yaxis_type="log",
                        yaxis_title="ราคา (ล้านบาท - สเกล Log)",
                        yaxis=dict(
                            showgrid=True, 
                            gridcolor='rgba(255,255,255,0.06)' if is_dark_mode else 'rgba(0,0,0,0.05)',
                            tickmode='array',
                            tickvals=[0.5, 1, 2, 5, 10, 20, 50, 100],
                            ticktext=['฿0.5M', '฿1M', '฿2M', '฿5M', '฿10M', '฿20M', '฿50M', '฿100M']
                        ),
                        margin=dict(t=50, b=20, l=10, r=10),
                        plot_bgcolor='rgba(0,0,0,0)',
                        paper_bgcolor='rgba(0,0,0,0)'
                    )
                    st.plotly_chart(style_plotly_fig(fig_box), width="stretch", theme=None)




# ----- TAB 4: PROPERTY LISTING -----
with tab4:
    st.markdown(f"### <i class='fa-solid fa-table-list' style='color:#059669; margin-right:8px;'></i>รายการทรัพย์สินที่ค้นพบ ({len(df_filtered):,} รายการ)", unsafe_allow_html=True)
    
    if df_filtered.empty:
        st.warning("ไม่พบข้อมูลตามเงื่อนไข")
    else:
        col_s1, col_s2 = st.columns([3.5, 1.2])
        with col_s1:
            # Search Box to filter Tab 4 Property Listing table (รหัสทรัพย์ / ชื่อโครงการ / ชื่อประกาศ)
            tab4_search_query = st.text_input(
                "ค้นหารหัสทรัพย์ / ชื่อโครงการ / ชื่อประกาศ",
                icon=":material/search:",
                value="",
                placeholder="พิมพ์รหัสทรัพย์, ชื่อโครงการ หรือชื่อประกาศ...",
                key="tab4_property_listing_search"
            )

        with col_s2:
            display_limit = st.number_input(
                "จำนวนแถว (Rows)",
                icon=":material/format_list_numbered:",
                min_value=0,
                max_value=100000,
                value=0,
                step=50,
                key="tab4_direct_row_limit",
                help="กรอกจำนวนแถวที่ต้องการแสดงในตาราง (ค่าเริ่มต้นคือ 0 เพื่อความรวดเร็ว)"
            )
            display_limit = int(display_limit)

        # Quick Sort & Filter Presets (Clean & Smart)
        quick_presets = [
            "ค่าเริ่มต้น", 
            "ราคาต่ำสุด (Top 100)", 
            "ราคาสูงสุด (Top 100)", 
            "฿/ตร.ว. ถูกสุด (Top 100)", 
            "฿/ตร.ม. ถูกสุด (Top 100)", 
            "อัปเดตล่าสุด (Top 100)", 
            "พื้นที่ใหญ่สุด (Top 100)"
        ]
        st.markdown(
            f"<div style='font-size: 0.95rem; font-weight: 700; color: {'#f8fafc' if is_dark_mode else '#0f172a'}; margin-top: 10px; margin-bottom: 6px; display: flex; align-items: center; gap: 6px;'>"
            f"<i class='fa-solid fa-sliders' style='color: #059669;'></i> กดดูด่วน (Quick Sort Presets):"
            f"</div>",
            unsafe_allow_html=True
        )
        selected_quick_sort = st.pills(
            "กดดูด่วน (Quick Sort Presets):",
            options=quick_presets,
            default="ค่าเริ่มต้น",
            label_visibility="collapsed",
            key="tab4_quick_sort_preset"
        )

        # Fast Tab 4 Data Pipeline
        if display_limit == 0 and not tab4_search_query and selected_quick_sort == "ค่าเริ่มต้น":
            df_table = df_filtered.head(0)
            df_table_source = df_table
            active_sort_label = ""
        else:
            df_table_source = df_filtered

            if tab4_search_query:
                q_tab4 = tab4_search_query.strip()
                q_tab4_lower = q_tab4.lower()
                
                # 1. Exact match on รหัสทรัพย์ or ID
                exact_code = df_table_source['รหัสทรัพย์'].astype(str).str.strip().str.lower() == q_tab4_lower if 'รหัสทรัพย์' in df_table_source.columns else False
                exact_id = df_table_source['ID'].astype(str).str.strip().str.lower() == q_tab4_lower if 'ID' in df_table_source.columns else False
                exact_match_mask = exact_code | exact_id

                if exact_match_mask.any():
                    df_table_source = df_table_source[exact_match_mask]
                else:
                    # 2. Substring matching across title, project, code, and id
                    q_tab4_esc = re.escape(q_tab4)
                    cond_title = df_table_source['ชื่อประกาศ'].astype(str).str.contains(q_tab4_esc, case=False, na=False) if 'ชื่อประกาศ' in df_table_source.columns else False
                    cond_code = df_table_source['รหัสทรัพย์'].astype(str).str.contains(q_tab4_esc, case=False, na=False) if 'รหัสทรัพย์' in df_table_source.columns else False
                    cond_id = df_table_source['ID'].astype(str).str.contains(q_tab4_esc, case=False, na=False) if 'ID' in df_table_source.columns else False
                    cond_proj = df_table_source['ชื่อโครงการ'].astype(str).str.contains(q_tab4_esc, case=False, na=False) if 'ชื่อโครงการ' in df_table_source.columns else False
                    df_table_source = df_table_source[cond_title | cond_code | cond_id | cond_proj]

            # Apply Quick Sort logic
            active_sort_label = ""
            if selected_quick_sort == "ราคาต่ำสุด (Top 100)":
                p_mask = df_table_source['ราคา'].notna() & (pd.to_numeric(df_table_source['ราคา'], errors='coerce') > 0)
                df_table_source = df_table_source[p_mask].sort_values(by='ราคา', ascending=True)
                active_sort_label = "ราคาต่ำสุด (น้อยไปมาก)"
            elif selected_quick_sort == "ราคาสูงสุด (Top 100)":
                p_mask = df_table_source['ราคา'].notna() & (pd.to_numeric(df_table_source['ราคา'], errors='coerce') > 0)
                df_table_source = df_table_source[p_mask].sort_values(by='ราคา', ascending=False)
                active_sort_label = "ราคาสูงสุด (มากไปน้อย)"
            elif selected_quick_sort == "฿/ตร.ว. ถูกสุด (Top 100)":
                if 'ราคาต่อตารางวา' in df_table_source.columns:
                    p_mask = df_table_source['ราคาต่อตารางวา'].notna() & (pd.to_numeric(df_table_source['ราคาต่อตารางวา'], errors='coerce') > 0)
                    df_table_source = df_table_source[p_mask].sort_values(by='ราคาต่อตารางวา', ascending=True)
                active_sort_label = "ราคาต่อตารางวาถูกที่สุด"
            elif selected_quick_sort == "฿/ตร.ม. ถูกสุด (Top 100)":
                if 'ราคาต่อตารางเมตร' in df_table_source.columns:
                    p_mask = df_table_source['ราคาต่อตารางเมตร'].notna() & (pd.to_numeric(df_table_source['ราคาต่อตารางเมตร'], errors='coerce') > 0)
                    df_table_source = df_table_source[p_mask].sort_values(by='ราคาต่อตารางเมตร', ascending=True)
                active_sort_label = "ราคาต่อตารางเมตรถูกที่สุด"
            elif selected_quick_sort == "อัปเดตล่าสุด (Top 100)":
                for dcol in ['วันที่ดึงข้อมูล', 'วันประกาศ']:
                    if dcol in df_table_source.columns:
                        df_table_source = df_table_source.sort_values(by=dcol, ascending=False, na_position='last')
                        break
                active_sort_label = "วันที่อัปเดตล่าสุด"
            elif selected_quick_sort == "พื้นที่ใหญ่สุด (Top 100)":
                for acol in ['พื้นที่_ตารางวา', 'เนื้อที่ (ตร.ว.)']:
                    if acol in df_table_source.columns:
                        p_mask = df_table_source[acol].notna() & (pd.to_numeric(df_table_source[acol], errors='coerce') > 0)
                        df_table_source = df_table_source[p_mask].sort_values(by=acol, ascending=False)
                        break
                active_sort_label = "ขนาดพื้นที่ใหญ่ที่สุด"

            # Slice the requested number of rows (Auto-display when searching or sorting)
            if display_limit > 0:
                df_table = df_table_source.head(display_limit)
            elif tab4_search_query or selected_quick_sort != "ค่าเริ่มต้น":
                df_table = df_table_source.head(100)
            else:
                df_table = df_table_source.head(0)

        # Status text
        if display_limit == 0 and not tab4_search_query and selected_quick_sort == "ค่าเริ่มต้น":
            st.caption("ปัจจุบันแสดงเฉพาะ **หัวข้อคอลัมน์** เพื่อความเร็วสูงสุด (พิมพ์ค้นหารหัสทรัพย์, เลือกตัวจัดเรียงด่วน หรือเลือกจำนวนแถวที่ต้องการแสดง)")
        elif tab4_search_query:
            st.caption(f"พบข้อมูลตรงกับการค้นหา **{len(df_table_source):,}** รายการ (แสดง **{len(df_table):,}** รายการแรกในตาราง)")
        else:
            sort_info_str = f" | จัดเรียง: **{active_sort_label}**" if active_sort_label else ""
            total_matches = len(df_table_source) if len(df_table_source) > 0 else len(df_filtered)
            st.caption(f"แสดงข้อมูล **{len(df_table):,}** รายการ จากที่พบทั้งหมด **{total_matches:,}** รายการ{sort_info_str}")
            
        df_table_show = df_table.copy()
        
        # Prepare clean numeric columns on sliced subset only
        if not df_table_show.empty:
            df_table_show['รูปแปลงที่ดิน'] = df_table_show['บริษัท'].apply(
                lambda c: "https://landsmaps.dol.go.th/" if str(c).strip().upper() == "LED" else None
            )
            df_table_show['ความแม่นยำพิกัด'] = df_table_show.apply(
                lambda r: "⚠️ กึ่งกลางตำบล" if is_true_centroid(r.get('is_centroid'), r.get('บริษัท')) else "📍 แปลงจริง",
                axis=1
            )
            if 'ราคา' in df_table_show.columns:
                df_table_show['ราคาขาย (บาท)'] = pd.to_numeric(df_table_show['ราคา'], errors='coerce')
            
            sqwah_t4 = df_table_show['เนื้อที่ (ตร.ว.)'].apply(to_float_sqwah) if 'เนื้อที่ (ตร.ว.)' in df_table_show.columns else pd.Series(np.nan, index=df_table_show.index)
            if 'พื้นที่_ตารางวา' in df_table_show.columns:
                sqwah_t4 = sqwah_t4.fillna(df_table_show['พื้นที่_ตารางวา'].apply(to_float_sqwah))
            df_table_show['sqwah_calc'] = sqwah_t4
            
            df_table_show['เนื้อที่ (ไร่-งาน-ตร.ว.)'] = df_table_show['เนื้อที่ (ตร.ว.)'].apply(format_to_rai_ngan_wah) if 'เนื้อที่ (ตร.ว.)' in df_table_show.columns else df_table_show['sqwah_calc'].apply(format_to_rai_ngan_wah)
                
            if 'พื้นที่ใช้สอย (ตร.ม.)' in df_table_show.columns:
                df_table_show['พื้นที่ใช้สอย (ตร.ม.)'] = df_table_show['พื้นที่ใช้สอย (ตร.ม.)'].apply(to_float_sqm)

            for num_col in ['ละติจูด', 'ลองจิจูด']:
                if num_col in df_table_show.columns:
                    df_table_show[num_col] = pd.to_numeric(df_table_show[num_col], errors='coerce')

        cols_table_raw = [
            "บริษัท", "ID", "รหัสทรัพย์", "ชื่อโครงการ", "ประเภททรัพย์", "ประเภทการขาย", "ราคาขาย (บาท)",
            "ตำบล", "อำเภอ", "จังหวัด", "ละติจูด", "ลองจิจูด", "ความแม่นยำพิกัด", "ชื่อประกาศ", "ลิงก์", "รูปแปลงที่ดิน",
            "เนื้อที่ (ไร่-งาน-ตร.ว.)", "พื้นที่ใช้สอย (ตร.ม.)", "วันที่ดึงข้อมูล",
            "ห้องนอน", "ห้องน้ำ", "ที่จอดรถ", "ชั้น", "วันประกาศ"
        ]
        cols_present = [c for c in cols_table_raw if c in df_table_show.columns]
        df_table_show = df_table_show[cols_present]

        st.dataframe(
            df_table_show,
            width="stretch",
            column_config={
                "ราคาขาย (บาท)": st.column_config.NumberColumn("ราคาขาย (บาท)", format="฿%,d"),
                "เนื้อที่ (ไร่-งาน-ตร.ว.)": st.column_config.TextColumn("เนื้อที่ (ไร่-งาน-ตร.ว.)"),
                "พื้นที่ใช้สอย (ตร.ม.)": st.column_config.NumberColumn("พื้นที่ใช้สอย (ตร.ม.)", format="%.1f"),
                "ละติจูด": st.column_config.NumberColumn(format="%.6f"),
                "ลองจิจูด": st.column_config.NumberColumn(format="%.6f"),
                "ความแม่นยำพิกัด": st.column_config.TextColumn("ความแม่นยำพิกัด", help="ระบุว่าเป็นพิกัดแปลงจริงจากประกาศ หรือพิกัดจุดกึ่งกลางตำบล/อำเภอ"),
                "ชั้น": st.column_config.TextColumn("ชั้น", help="ชั้นที่ตั้งของทรัพย์สิน หรือจำนวนชั้นของอาคาร"),
                "ลิงก์": st.column_config.LinkColumn("ลิงก์ประกาศ", display_text="เปิดดูทรัพย์"),
                "รูปแปลงที่ดิน": st.column_config.LinkColumn("รูปแปลงที่ดิน (LED)", display_text="LandsMaps", help="คลิกเพื่อเปิดระบบค้นหารูปแปลงที่ดิน กรมที่ดิน (เฉพาะกรมบังคับคดี)")
            }
        )
        render_import_export_section(df_table_source if not df_table_source.empty else df_filtered, filename_prefix="npa_property_listing", key_suffix="tab4")

# reload trigger: 2026-09-17 10:53:00 (v3: container-based sync hiding + text-based button finder + comfortable zoom)
