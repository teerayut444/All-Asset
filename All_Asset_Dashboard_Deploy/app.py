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
from sam_analytics import render_same_project_comparison, clean_project_name

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
                    u_df = pd.read_csv(uploaded_file)
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
_app_icon_file = os.path.join("assets", "app_icon.ico")
_app_page_icon = Image.open(_app_icon_file) if os.path.exists(_app_icon_file) else ":material/analytics:"

st.set_page_config(
    page_title="All Asset NPA Dashboard",
    page_icon=_app_page_icon,
    layout="wide",
    initial_sidebar_state="expanded"
)


# ----------------- LOGIN SYSTEM -----------------
def check_password(input_password):
    input_password = str(input_password).strip()
    if input_password in ["วันที่+7", "วันที่ + 7", "date+7", "date + 7", "DATE+7", "DATE + 7"]:
        return True
        
    import datetime
    # Check UTC and GMT+7 timezone offsets
    for tz_offset in [0, 7]:
        tz = datetime.timezone(datetime.timedelta(hours=tz_offset))
        now = datetime.datetime.now(tz)
        today = now.date()
        
        # 1. Date + 7 days
        future_date = today + datetime.timedelta(days=7)
        f_day = future_date.day
        f_day_str = str(f_day)
        f_day_zero = f"{f_day:02d}"
        
        # 2. Numerical day + 7
        num_day = today.day + 7
        num_day_str = str(num_day)
        
        valid_options = [
            f_day_str,
            f_day_zero,
            num_day_str,
            future_date.strftime("%d%m%Y"),
            future_date.strftime("%d%m%y"),
            future_date.strftime("%d-%m-%Y"),
            future_date.strftime("%d/%m/%Y"),
            future_date.strftime("%Y-%m-%d"),
            future_date.strftime("%Y/%m/%d"),
            future_date.strftime("%d%m") + str(future_date.year + 543),
            future_date.strftime("%d/%m/") + str(future_date.year + 543),
            future_date.strftime("%d-%m-") + str(future_date.year + 543),
        ]
        
        if input_password in valid_options:
            return True
            
    return False

# Auth Token System for Persistent Login across reloads/clear cache
AUTH_SECRET = "AllAssetNPA_SecretKey_2026"

def generate_auth_token():
    import hashlib
    return hashlib.sha256(AUTH_SECRET.encode()).hexdigest()[:32]

def is_valid_auth_token(token):
    if not token or not isinstance(token, str):
        return False
    return token.strip() == generate_auth_token()

if "logout" in st.query_params:
    st.session_state['logged_in'] = False
    del st.query_params["logout"]
    st.html("""
    <script>
    try {
        document.cookie = "npa_auth=; path=/; max-age=0; SameSite=Lax";
        sessionStorage.removeItem('npa_auth_token');
        localStorage.removeItem('npa_auth_token');
    } catch(e) {}
    </script>
    """, unsafe_allow_javascript=True)
    st.rerun()

# Determine authentication state
if st.session_state.get('logged_in'):
    pass
elif hasattr(st, 'context') and hasattr(st.context, 'cookies') and is_valid_auth_token(st.context.cookies.get("npa_auth", "")):
    st.session_state['logged_in'] = True
elif "_auth" in st.query_params and is_valid_auth_token(st.query_params.get("_auth", "")):
    st.session_state['logged_in'] = True
    del st.query_params["_auth"]
else:
    st.session_state['logged_in'] = False

if not st.session_state['logged_in']:
    # Auto-restore authentication from localStorage if available
    st.html("""
    <script>
    try {
        var saved = localStorage.getItem('npa_auth_token') || sessionStorage.getItem('npa_auth_token');
        if (saved && document.cookie.indexOf('npa_auth=') === -1) {
            document.cookie = "npa_auth=" + saved + "; path=/; max-age=2592000; SameSite=Lax";
            window.location.reload();
        }
    } catch(e) {}
    </script>
    """, unsafe_allow_javascript=True)

    # Inject CSS for a beautiful login interface (matching SAM Green theme)
    login_css = """<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=Noto+Sans+Thai:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=Noto+Sans+Thai:wght@300;400;500;600;700;800&display=swap');

html, body, .stApp, p, 
span:not([data-testid="stIconMaterial"]):not([class*="material"]):not([class*="fa"]), 
div, label, input, 
button:not([data-testid="stIconMaterial"]):not([class*="material"]):not([class*="fa"]), 
h1, h2, h3, h4, h5, h6 {
    font-family: 'Noto Sans Thai', 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif !important;
}

html, body, .stApp {
    background: linear-gradient(135deg, #f8fafc 0%, #f0fdf4 50%, #e2e8f0 100%) !important;
    height: 100vh !important;
    overflow: hidden !important;
}

div[data-testid="stAppViewContainer"] {
    background: linear-gradient(135deg, #f8fafc 0%, #f0fdf4 50%, #e2e8f0 100%) !important;
}

div[data-testid="stForm"] {
    background: #ffffff !important;
    border: 1.5px solid rgba(4, 120, 87, 0.2) !important;
    border-radius: 24px !important;
    padding: 40px !important;
    box-shadow: 0 20px 45px rgba(4, 120, 87, 0.08), 0 2px 8px rgba(0, 0, 0, 0.04) !important;
    max-width: 440px !important;
    margin: 12vh auto auto auto !important;
}

/* Force clean white background for input container and remove dark green */
div[data-testid="stForm"] [data-baseweb="input"],
div[data-testid="stForm"] [data-baseweb="base-input"],
div[data-testid="stForm"] div[data-baseweb="input"],
div[data-testid="stForm"] div[data-baseweb="base-input"],
div[data-testid="stForm"] .stTextInput div[data-baseweb="input"],
div[data-testid="stForm"] .stTextInput div[data-baseweb="base-input"] {
    border-radius: 12px !important;
    border: 1.5px solid #a7f3d0 !important;
    background-color: #ffffff !important;
    background: #ffffff !important;
    box-shadow: inset 0 1px 3px rgba(0, 0, 0, 0.03) !important;
    transition: all 0.25s ease !important;
}

div[data-testid="stForm"] div[data-baseweb="input"] > div,
div[data-testid="stForm"] div[data-baseweb="base-input"] > div {
    background-color: transparent !important;
    background: transparent !important;
    border: none !important;
}

div[data-testid="stForm"] div[data-baseweb="input"]:focus-within,
div[data-testid="stForm"] div[data-baseweb="base-input"]:focus-within {
    border-color: #047857 !important;
    box-shadow: 0 0 0 3px rgba(4, 120, 87, 0.2) !important;
    background-color: #ffffff !important;
    background: #ffffff !important;
}

div[data-testid="stForm"] input,
div[data-testid="stForm"] input[type="password"],
div[data-testid="stForm"] input[type="text"] {
    background-color: transparent !important;
    background: transparent !important;
    color: #0f172a !important;
    -webkit-text-fill-color: #0f172a !important;
    -webkit-opacity: 1 !important;
    opacity: 1 !important;
    caret-color: #047857 !important;
    border: none !important;
    height: 52px !important;
    font-size: 1.25rem !important;
    letter-spacing: 3px !important;
    text-align: center !important;
    width: 100% !important;
    font-weight: 700 !important;
}

div[data-testid="stForm"] input::placeholder {
    color: #94a3b8 !important;
    -webkit-text-fill-color: #94a3b8 !important;
    letter-spacing: normal !important;
    font-size: 0.95rem !important;
    font-weight: 400 !important;
}

/* Visibility toggle eye icon */
div[data-testid="stForm"] button[data-testid="stTextInputPasswordVisibilityToggle"],
div[data-testid="stForm"] [data-baseweb="input"] button {
    background: transparent !important;
    border: none !important;
    color: #047857 !important;
    font-size: 1.1rem !important;
}

div[data-testid="stFormSubmitButton"] button {
    background: linear-gradient(135deg, #059669 0%, #047857 100%) !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: 12px !important;
    font-weight: 700 !important;
    font-size: 1.1rem !important;
    height: 50px !important;
    width: 100% !important;
    box-shadow: 0 8px 20px rgba(4, 120, 87, 0.25) !important;
    transition: all 0.3s ease !important;
    margin-top: 15px !important;
}

div[data-testid="stFormSubmitButton"] button:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 12px 25px rgba(4, 120, 87, 0.4) !important;
    background: linear-gradient(135deg, #047857 0%, #065f46 100%) !important;
    color: #ffffff !important;
}

div[data-testid="stFormSubmitButton"] button:active {
    transform: translateY(0) !important;
}

section[data-testid="stSidebar"], header, footer {
    display: none !important;
    visibility: hidden !important;
}

/* Suppress Streamlit's grey skeleton wireframes and stale login overlay */
div[data-testid="stAppViewContainer"][data-stale="true"] div[data-testid="stForm"] {
    display: none !important;
}
.stSkeleton, div[data-testid="stSkeleton"] {
    display: none !important;
}
</style>"""
    st.html(login_css)
    
    logo_path = Path("assets/logo.png")
    if logo_path.exists():
        with open(logo_path, "rb") as img_f:
            logo_b64 = base64.b64encode(img_f.read()).decode("utf-8")
        logo_html = f'<img src="data:image/png;base64,{logo_b64}" style="width: 130px; height: 130px; object-fit: contain; margin-bottom: 16px; filter: drop-shadow(0 8px 24px rgba(5, 150, 105, 0.2));">'
    else:
        logo_html = '<div style="display: inline-flex; align-items: center; justify-content: center; width: 90px; height: 90px; background: #ecfdf5; border-radius: 50%; margin-bottom: 20px; border: 1px solid #a7f3d0;"><i class="fa-solid fa-lock" style="font-size: 2.5rem; color: #059669;"></i></div>'

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("login_form", clear_on_submit=False):
            header_html = f"""<div style="text-align: center; margin-bottom: 25px;">
{logo_html}
<h2 style="color: #0f172a; font-weight: 800; font-size: 2.2rem; margin: 0 0 8px 0; letter-spacing: -0.5px;">All Asset NPA</h2>
<p style="color: #64748b; font-size: 0.95rem; margin: 0;">กรุณาใส่รหัสผ่านเพื่อเข้าใช้งานระบบ</p>
</div>"""
            st.html(header_html)
            
            password = st.text_input("รหัสผ่าน (Password)", type="password", key="login_password", label_visibility="collapsed", placeholder="กรอกรหัสผ่าน...")
            
            submit = st.form_submit_button("เข้าสู่ระบบ")
            
            if submit:
                if check_password(password):
                    st.session_state['logged_in'] = True
                    auth_token = generate_auth_token()
                    if "_auth" in st.query_params:
                        del st.query_params["_auth"]
                    st.html(f'''
                    <script>
                    try {{
                        document.cookie = "npa_auth={auth_token}; path=/; max-age=2592000; SameSite=Lax";
                        sessionStorage.setItem('npa_auth_token', '{auth_token}');
                        localStorage.setItem('npa_auth_token', '{auth_token}');
                    }} catch(e) {{}}
                    </script>
                    <div id="login-loading-overlay" style="position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; background: #f8fafc; z-index: 9999999; display: flex; flex-direction: column; align-items: center; justify-content: center; font-family: 'Noto Sans Thai', 'Inter', sans-serif;">
                        <div style="width: 55px; height: 55px; border: 4px solid rgba(4, 120, 87, 0.15); border-top: 4px solid #047857; border-radius: 50%; animation: spin 0.8s linear infinite; margin-bottom: 22px;"></div>
                        <h3 style="color: #064e3b; font-weight: 800; font-size: 1.45rem; margin: 0 0 8px 0; letter-spacing: -0.3px;">เข้าสู่ระบบสำเร็จ</h3>
                        <p style="color: #047857; font-size: 0.95rem; margin: 0; font-weight: 600;">กำลังโหลดและจัดเตรียมข้อมูล All Asset NPA Dashboard...</p>
                    </div>
                    <style>
                    @keyframes spin {{ 0% {{ transform: rotate(0deg); }} 100% {{ transform: rotate(360deg); }} }}
                    div[data-testid="stForm"] {{ display: none !important; }}
                    section[data-testid="stSidebar"] {{ display: none !important; }}
                    </style>
                    ''', unsafe_allow_javascript=True)
                    st.rerun()
                else:
                    err_html = """<div style="background-color: #fef2f2; color: #dc2626; border: 1px solid #fecaca; border-radius: 10px; padding: 12px; margin-top: 15px; font-size: 0.9rem; text-align: center; font-weight: 500;">
<i class="fa-solid fa-triangle-exclamation"></i> รหัสผ่านไม่ถูกต้อง กรุณาลองใหม่อีกครั้ง
</div>"""
                    st.html(err_html)
    st.stop()

# Ensure active auth token is maintained in browser storage & clean URL
active_token = generate_auth_token()
st.html(f"""
<script>
try {{
    document.cookie = "npa_auth={active_token}; path=/; max-age=2592000; SameSite=Lax";
    sessionStorage.setItem('npa_auth_token', '{active_token}');
    localStorage.setItem('npa_auth_token', '{active_token}');
    if (window.location.search.indexOf('_auth') !== -1) {{
        var cleanUrl = new URL(window.location.href);
        cleanUrl.searchParams.delete('_auth');
        window.history.replaceState({{}}, '', cleanUrl.pathname + (cleanUrl.search ? cleanUrl.search : ''));
    }}
}} catch(e) {{}}
</script>
""", unsafe_allow_javascript=True)


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

def get_map_icon_atlas_and_mapping(icon_size=96):
    """Builds and caches a single sprite sheet atlas containing all company logo badges for rock-solid GPU rendering."""
    global _CACHED_ATLAS_URI, _CACHED_ICON_MAPPING
    if _CACHED_ATLAS_URI is not None and _CACHED_ICON_MAPPING is not None:
        return _CACHED_ATLAS_URI, _CACHED_ICON_MAPPING
        
    companies = [
        "LED", "SAM", "BAM", "Chayo555", "GHB", "KBANK", "KTB", "SCB", "GSB",
        "DDproperty", "Livinginsider", "NaYoo", "ZmyHome", "Baania", "จุดอ้างอิง"
    ]
    
    atlas_width = len(companies) * icon_size
    atlas_height = icon_size
    
    try:
        from PIL import Image, ImageDraw
        import io, base64
        
        atlas = Image.new("RGBA", (atlas_width, atlas_height), (0, 0, 0, 0))
        
        alias_map = {
            'led': 'led.png',
            'bam': 'bam.png',
            'sam': 'sam.png',
            'kbank': 'kbank.png',
            'scb': 'scb.png',
            'ktb': 'ktb.png',
            'ghb': 'ghb.png',
            'gsb': 'gsb.png',
            'chayo555': 'chayo555.png',
            'nayoo': 'nayoo.svg',
            'baania': 'baania.png',
            'zmyhome': 'zmyhome.png',
            'ddproperty': 'ddproperty.png',
            'livinginsider': 'livinginsider.png'
        }
        
        icon_mapping = {}
        margin = 4
        
        for i, name in enumerate(companies):
            x_offset = i * icon_size
            cell = Image.new("RGBA", (icon_size, icon_size), (0, 0, 0, 0))
            draw = ImageDraw.Draw(cell)
            
            if name == "จุดอ้างอิง":
                # Red target pin with white bullseye
                draw.ellipse([margin, margin, icon_size - margin, icon_size - margin], fill=(239, 68, 68, 250), outline=(255, 255, 255, 255), width=3)
                draw.ellipse([icon_size // 2 - 14, icon_size // 2 - 14, icon_size // 2 + 14, icon_size // 2 + 14], fill=(255, 255, 255, 255))
                draw.ellipse([icon_size // 2 - 7, icon_size // 2 - 7, icon_size // 2 + 7, icon_size // 2 + 7], fill=(239, 68, 68, 255))
            else:
                # White circular badge with slate border
                draw.ellipse([margin, margin, icon_size - margin, icon_size - margin], fill=(255, 255, 255, 250), outline=(203, 213, 225, 255), width=2)
                
                logo_path = None
                for base in [name, name.lower(), name.upper(), name.capitalize(), name.title()]:
                    for ext in ['.png', '.jpg', '.jpeg', '.webp']:
                        p = os.path.join("assets", "logos", f"{base}{ext}")
                        if os.path.exists(p):
                            logo_path = p
                            break
                    if logo_path:
                        break
                
                if logo_path:
                    try:
                        logo = Image.open(logo_path).convert("RGBA")
                        inner_max = int((icon_size - margin * 2) * 0.76)
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
                "x": x_offset,
                "y": 0,
                "width": icon_size,
                "height": icon_size,
                "mask": False,
                "anchorX": icon_size // 2,
                "anchorY": icon_size // 2
            }
            icon_mapping[name.lower()] = icon_mapping[name]
            icon_mapping[name.upper()] = icon_mapping[name]
            
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
            
            # 2. หมวดคอนโดมิเนียม / ห้องชุด
            "คอนโด": "ห้องชุดพักอาศัย",
            "คอนโดมิเนียม": "ห้องชุดพักอาศัย",
            "ห้องชุด/คอนโดมิเนียม": "ห้องชุดพักอาศัย",
            "ห้องชุด/ตอนโดมิเนียม": "ห้องชุดพักอาศัย",
            "คอนโดมิเนียม/อาคารชุด": "ห้องชุดพักอาศัย",
            "คอนโด/อาคารชุด/ห้องชุด": "ห้องชุดพักอาศัย",
            
            # 3. หมวดทาวน์เฮ้าส์ / ทาวน์โฮม
            "ทาวน์โฮม": "ทาวน์เฮ้าส์",
            "ทาวน์เฮาส์": "ทาวน์เฮ้าส์",
            
            # 4. หมวดที่ดิน
            "ที่ดิน": "ที่ดินเปล่า",
            "ที่ดินเปล่า": "ที่ดินเปล่า",
            "ที่ดินเกษตรกรรม": "ที่ดินเปล่า",
            "ที่ดินว่างเปล่า": "ที่ดินเปล่า",
            "สวนเกษตร": "ที่ดินเปล่า",
            
            # 5. หมวดโรงงาน / โกดัง
            "โรงงาน": "โรงงาน/โกดัง",
            "โกดัง": "โรงงาน/โกดัง",
            "อาคารโรงงาน": "โรงงาน/โกดัง",
            "โกดัง/โรงงาน": "โรงงาน/โกดัง",
            "โกดัง / โรงงาน": "โรงงาน/โกดัง",
            "มินิแฟคตอรี่": "โรงงาน/โกดัง",
            "โรงสี": "โรงงาน/โกดัง",
            
            # 6. หมวดอพาร์ทเมนท์ / หอพัก
            "อพาร์ทเม้นท์": "อพาร์ทเมนท์",
            "อพาร์ตเมนต์": "อพาร์ทเมนท์",
            "อพาตเมนต์": "อพาร์ทเมนท์",
            "หอพัก": "อพาร์ทเมนท์",
            "หอพัก/อพาร์ทเมนท์": "อพาร์ทเมนท์",
            "อพาร์ทเม้นท์/หอพัก": "อพาร์ทเมนท์",
            "แฟลต": "อพาร์ทเมนท์",
            "อาคารพักอาศัย": "อพาร์ทเมนท์",
            
            # 7. หมวดอาคารพาณิชย์ / ตึกแถว / ร้านค้า
            "ตึกแถว": "อาคารพาณิชย์",
            "ห้องแถว": "อาคารพาณิชย์",
            "ร้านค้า": "อาคารพาณิชย์",
            "ร้านอาหาร": "อาคารพาณิชย์",
            "ตลาดสด": "อาคารพาณิชย์",
            "ศูนย์จำหน่ายสินค้า": "อาคารพาณิชย์",
            "ห้างสรรพสินค้า": "อาคารพาณิชย์",
            "โชว์รูม": "อาคารพาณิชย์",
            
            # 8. หมวดสำนักงาน
            "สำนักงาน": "อาคารสำนักงาน",
            "โฮมออฟฟิศ": "อาคารสำนักงาน",
            "อาคารที่ทำการสาขา": "อาคารสำนักงาน",
            "ห้องชุดสำนักงาน": "ห้องชุดพาณิชยกรรม/สำนักงาน",
            "ห้องชุดพาณิชยกรรม": "ห้องชุดพาณิชยกรรม/สำนักงาน",
            
            # 9. หมวดโรงแรม / รีสอร์ท
            "Hotel Building": "โรงแรม/รีสอร์ท",
            "โรงแรม": "โรงแรม/รีสอร์ท",
            "รีสอร์ท": "โรงแรม/รีสอร์ท",
            
            # 10. หมวดสังหาริมทรัพย์ & อื่นๆ
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
        type_lut = {t: prop_type_map.get(str(t).strip(), str(t).strip()) for t in u_types}
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
        df['ภาค'] = df['จังหวัด'].map(PROVINCE_TO_REGION).fillna('อื่นๆ / ไม่ระบุ')

    if 'ชั้น' not in df.columns:
        df['ชั้น'] = None
    else:
        df['ชั้น'] = df['ชั้น'].replace({'nan': None, 'None': None, 'null': None, '<NA>': None, 'NaN': None, '-': None, '': None})

    if 'เลขโฉนด' not in df.columns:
        df['เลขโฉนด'] = None
    else:
        df['เลขโฉนด'] = df['เลขโฉนด'].replace({'nan': None, 'None': None, 'null': None, '<NA>': None, 'NaN': None, '-': None, '': None})

    # Ensure 'อำเภอ' and 'ตำบล' are 100% Thai without any English characters
    if 'อำเภอ' in df.columns:
        en_amp_mask = df['อำเภอ'].astype(str).str.contains(r'[a-zA-Z]', regex=True, na=False)
        if en_amp_mask.any():
            try:
                base_dir = os.path.dirname(os.path.abspath(__file__))
                for cand in [base_dir, os.path.join(base_dir, "Monthly all new")]:
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

    provinces_pool = sorted([str(p) for p in _df['จังหวัด'].dropna().unique() if str(p).strip() not in ['', 'nan', 'None']])
    if "ไม่ระบุ" in provinces_pool:
        provinces_pool.remove("ไม่ระบุ")
        provinces_pool.append("ไม่ระบุ")

    # Pre-compute full district lookup (province -> sorted list of districts)
    district_by_province = {}
    all_districts_formatted = []
    if 'อำเภอ' in _df.columns and 'จังหวัด' in _df.columns:
        dist_cols = _df[['อำเภอ', 'จังหวัด']].drop_duplicates().dropna()
        dist_cols = dist_cols[~dist_cols['อำเภอ'].astype(str).str.strip().str.lower().isin(["", "nan", "none", "null", "undefined", "-"])]
        dist_cols = dist_cols[~dist_cols['จังหวัด'].astype(str).str.strip().str.lower().isin(["", "nan", "none", "null", "undefined", "-"])]
        for a, p in zip(dist_cols['อำเภอ'], dist_cols['จังหวัด']):
            p_str, a_str = str(p).strip(), str(a).strip()
            if p_str not in district_by_province:
                district_by_province[p_str] = []
            district_by_province[p_str].append(a_str)
        for p_str in district_by_province:
            district_by_province[p_str] = sorted(set(district_by_province[p_str]))

        all_districts_formatted = sorted(
            (dist_cols['อำเภอ'].astype(str).str.strip() + " (" + dist_cols['จังหวัด'].astype(str).str.strip() + ")").unique().tolist()
        )

    # Pre-compute subdistrict lookup per (province, district) key
    subdistrict_by_province = {}
    subdistrict_by_district = {}
    if all(c in _df.columns for c in ['ตำบล', 'อำเภอ', 'จังหวัด']):
        sub_cols = _df[['ตำบล', 'อำเภอ', 'จังหวัด']].drop_duplicates().dropna()
        sub_cols = sub_cols[~sub_cols['ตำบล'].astype(str).str.strip().str.lower().isin(["", "nan", "none", "null", "undefined", "-"])]
        sub_cols = sub_cols[~sub_cols['อำเภอ'].astype(str).str.strip().str.lower().isin(["", "nan", "none", "null", "undefined", "-"])]
        sub_cols = sub_cols[~sub_cols['จังหวัด'].astype(str).str.strip().str.lower().isin(["", "nan", "none", "null", "undefined", "-"])]
        sub_formatted = sub_cols['ตำบล'].astype(str).str.strip() + " (" + sub_cols['อำเภอ'].astype(str).str.strip() + ", " + sub_cols['จังหวัด'].astype(str).str.strip() + ")"
        sub_cols['formatted'] = sub_formatted

        for p, f in zip(sub_cols['จังหวัด'], sub_cols['formatted']):
            p_str = str(p)
            if p_str not in subdistrict_by_province:
                subdistrict_by_province[p_str] = []
            subdistrict_by_province[p_str].append(f)
        for p_str in subdistrict_by_province:
            subdistrict_by_province[p_str] = sorted(set(subdistrict_by_province[p_str]))

        for p, d, f in zip(sub_cols['จังหวัด'], sub_cols['อำเภอ'], sub_cols['formatted']):
            k = (str(p), str(d))
            if k not in subdistrict_by_district:
                subdistrict_by_district[k] = []
            subdistrict_by_district[k].append(f)
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

def get_base_map_html(_mtime=None):
    try:
        with open("static/map_template.html", "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return ""

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
        sb_logo_path = os.path.join("assets", "logo.png")
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
                <div style="font-size: 1.35rem; font-weight: 800; color: #ffffff; line-height: 1.1; letter-spacing: -0.5px;">All Asset</div>
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
        month_year_str, exact_date_str = get_dataset_month_year(df_raw)
        st.markdown(f"""
        <div style="background: rgba(255, 255, 255, 0.08); border: 1px solid rgba(110, 231, 183, 0.25); border-radius: 8px; padding: 7px 10px; margin-top: 5px; margin-bottom: 8px; font-size: 0.8rem; color: #f0fdf4; font-weight: 600;">
            <i class="fa fa-database" style="color:#34d399;"></i> แหล่งข้อมูล: <code style="background:rgba(0,0,0,0.25); color:#a7f3d0; padding:1px 5px; border-radius:4px;">{src_name}</code><br/>
            <span style="font-size: 0.75rem; color: #d1fae5; font-weight: normal;"><i class="fa fa-list" style="margin-right: 3px; color:#34d399;"></i>ข้อมูลพร้อมใช้งาน: <b style="color:#ffffff;">{len(df_raw):,}</b> รายการ</span><br/>
            <span style="font-size: 0.75rem; color: #6ee7b7; font-weight: 600;"><i class="fa fa-calendar-check"></i> ข้อมูลประจำเดือน: <b style="color:#ffffff;">{month_year_str}</b></span><br/>
            <span style="font-size: 0.72rem; color: #a7f3d0; font-weight: normal;">(ดึงข้อมูล: <b style="color:#ffffff;">{exact_date_str}</b>)</span>
        </div>
        """, unsafe_allow_html=True)
        
    if st.button("รีโหลดฐานข้อมูล (Clear Cache)", icon=":material/refresh:", key="btn_clear_cache_main", use_container_width=True, help="ล้างแคชและรีเฟรชหน้าเว็บใหม่ล่าสุดทันที"):
        # 1. Clear all Streamlit caches
        st.cache_data.clear()
        st.cache_resource.clear()
        st.session_state.pop('data_loaded_once', None)
        
        # 2. Maintain authenticated login state
        auth_tok = generate_auth_token()
        st.session_state['logged_in'] = True
        
        # 3. Dynamic overlay theme
        overlay_bg = "rgba(15, 23, 42, 0.94)" if is_dark_mode else "rgba(255, 255, 255, 0.94)"
        overlay_title = "#34d399" if is_dark_mode else "#064e3b"
        overlay_desc = "#94a3b8" if is_dark_mode else "#047857"
        
        # 4. Display smooth loading overlay and trigger real browser window reload
        st.html(f"""
        <div style="position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; background: {overlay_bg}; backdrop-filter: blur(6px); z-index: 99999999; display: flex; flex-direction: column; align-items: center; justify-content: center; font-family: 'Noto Sans Thai', 'Inter', sans-serif;">
            <div style="width: 52px; height: 52px; border: 4px solid rgba(16, 185, 129, 0.2); border-top: 4px solid #10b981; border-radius: 50%; animation: spinClear 0.75s linear infinite; margin-bottom: 18px;"></div>
            <h3 style="color: {overlay_title}; font-weight: 800; font-size: 1.35rem; margin: 0 0 8px 0; letter-spacing: -0.3px;">กำลังล้างแคชและรีเฟรชหน้าเว็บ...</h3>
            <p style="color: {overlay_desc}; font-size: 0.92rem; margin: 0; font-weight: 500;">ระบบกำลังอ่านไฟล์ข้อมูลใหม่ล่าสุด กรุณารอสักครู่</p>
        </div>
        <style>
        @keyframes spinClear {{ 0% {{ transform: rotate(0deg); }} 100% {{ transform: rotate(360deg); }} }}
        </style>
        <script>
        try {{
            document.cookie = "npa_auth={auth_tok}; path=/; max-age=2592000; SameSite=Lax";
            sessionStorage.setItem('npa_auth_token', '{auth_tok}');
            localStorage.setItem('npa_auth_token', '{auth_tok}');
        }} catch(e) {{}}
        setTimeout(function() {{
            if (window.parent && window.parent !== window) {{
                try {{ window.parent.location.reload(); return; }} catch(err) {{}}
            }}
            window.location.reload();
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
    
    st.markdown("### <i class='fa-solid fa-filter' style='color:#34d399; margin-right:8px;'></i><span style='color:#ffffff;'>ตัวกรองข้อมูลทรัพย์สิน</span>", unsafe_allow_html=True)
    
    if df_raw is not None and not df_raw.empty:
        search_query = ""
        
        # Pre-cached metadata for instant zero-lag sidebar rendering
        side_meta = get_cached_sidebar_metadata(df_raw)
        co_counts = side_meta.get('co_counts', {})
        companies_list = side_meta.get('companies_list', [])
        
        sanitize_session_state("filter_companies", companies_list)
        selected_companies = st.pills(
            "บริษัททรัพย์สิน", 
            options=companies_list, 
            format_func=lambda x: f"{x} ({co_counts.get(x, 0):,})",
            selection_mode="multi", 
            default=None,
            key="filter_companies"
        )
        if not selected_companies:
            selected_companies = []
        
        # Property Type Filter (using cached type distributions)
        common_types = side_meta.get('common_types', [])
        rare_types = side_meta.get('rare_types', [])
        type_counts = side_meta.get('type_counts', {})
        
        display_type_keys = list(common_types)
        if len(rare_types) > 0:
            display_type_keys.append("เพิ่มเติม")
            
        sanitize_session_state("filter_types", display_type_keys)
        rare_count_sum = sum(type_counts.get(t, 0) for t in rare_types)
        selected_types = st.pills(
            "ประเภททรัพย์สิน", 
            options=display_type_keys, 
            format_func=lambda x: f"เพิ่มเติม ({rare_count_sum:,})" if x == "เพิ่มเติม" else f"{x} ({type_counts.get(x, 0):,})",
            selection_mode="multi", 
            default=None,
            key="filter_types"
        )
        if not selected_types:
            selected_types = []
        
        # If "เพิ่มเติม" is selected, show a multiselect for rare types
        if "เพิ่มเติม" in selected_types:
            rare_types_sorted = list(rare_types)
            rare_types_sorted.sort()
            rare_options = [f"{t} ({type_counts.get(t, 0):,})" for t in rare_types_sorted]
            sanitize_session_state("selected_rare_types", rare_options)
            st.multiselect(
                "เลือกประเภททรัพย์สินเพิ่มเติม",
                options=rare_options,
                default=[],
                key="selected_rare_types"
            )
        
        # Sale Type Filter (ประเภทการขาย)
        sale_type_counts = side_meta.get('sale_type_counts', {})
        available_sale_types = list(sale_type_counts.keys())
        
        sanitize_session_state("filter_sale_types", available_sale_types)
        selected_sale_types = st.pills(
            "ประเภทการขาย",
            options=available_sale_types,
            format_func=lambda x: f"{x} ({sale_type_counts.get(x, 0):,})",
            selection_mode="multi",
            default=None,
            key="filter_sale_types"
        )
        if not selected_sale_types:
            selected_sale_types = []
        
        # Region Filter (ภูมิภาค)
        region_counts = side_meta.get('region_counts', {})
        all_ordered_regions = ["ภาคกลาง", "ภาคเหนือ", "ภาคตะวันออกเฉียงเหนือ", "ภาคตะวันออก", "ภาคตะวันตก", "ภาคใต้"]
        available_regions = [r for r in all_ordered_regions if r in region_counts]
        for r in region_counts:
            if r not in available_regions and r not in ['', 'nan', 'None', 'อื่นๆ / ไม่ระบุ']:
                available_regions.append(r)
        if 'อื่นๆ / ไม่ระบุ' in region_counts:
            available_regions.append('อื่นๆ / ไม่ระบุ')
            
        sanitize_session_state("selected_regions", available_regions)
        selected_regions = st.multiselect(
            "ภูมิภาค",
            options=available_regions,
            default=[],
            key="selected_regions",
            format_func=lambda x: f"{x} ({region_counts.get(x, 0):,})",
            placeholder="เลือกภูมิภาค (เช่น ภาคกลาง, ภาคเหนือ...)"
        )
        
        # Province Filter (cascaded by selected regions if chosen)
        if selected_regions:
            provinces_pool = sorted([
                str(p) for p in df_raw[df_raw['ภาค'].isin(selected_regions)]['จังหวัด'].dropna().unique()
                if str(p).strip() not in ['', 'nan', 'None']
            ])
        else:
            provinces_pool = side_meta.get('unique_provinces', [])
        unique_provinces = sorted(provinces_pool)
        # Clean up province lists, removing "ไม่ระบุ" or blank
        if "ไม่ระบุ" in unique_provinces:
            unique_provinces.remove("ไม่ระบุ")
            unique_provinces.append("ไม่ระบุ")
        sanitize_session_state("selected_provinces", unique_provinces)
        selected_provinces = st.multiselect("จังหวัด", options=unique_provinces, default=[], key="selected_provinces", placeholder="เลือกจังหวัด...")
        
        # District Filter - use pre-cached lookup (zero recompute cost)
        district_by_province = side_meta.get('district_by_province', {})
        all_districts_formatted = side_meta.get('all_districts_formatted', [])
        subdistrict_by_province = side_meta.get('subdistrict_by_province', {})
        subdistrict_by_district = side_meta.get('subdistrict_by_district', {})

        if selected_provinces:
            unique_districts_formatted = sorted(set(
                d for prov in selected_provinces
                for d in [f"{dist} ({prov})" for dist in district_by_province.get(prov, [])]
            ))
        elif selected_regions:
            region_provs = [p for p in side_meta.get('unique_provinces', []) if get_region_by_province(p) in selected_regions]
            unique_districts_formatted = sorted(set(
                d for prov in region_provs
                for d in [f"{dist} ({prov})" for dist in district_by_province.get(prov, [])]
            ))
        else:
            unique_districts_formatted = all_districts_formatted

        selected_districts_formatted = st.multiselect("อำเภอ / เขต", options=unique_districts_formatted, default=[], placeholder="เลือกอำเภอ / เขต...")

        # Parse selected districts into tuples for subdistrict option filtering
        selected_districts_tuples = []
        for d_f in selected_districts_formatted:
            if " (" in d_f:
                parts = d_f.split(" (")
                d_name = parts[0].strip()
                p_name = parts[1].replace(")", "").strip()
                selected_districts_tuples.append((d_name, p_name))

        # Subdistrict Filter - use pre-cached lookup (zero recompute cost)
        if selected_districts_tuples:
            unique_subdistricts_formatted = sorted(set(
                s for (d_name, p_name) in selected_districts_tuples
                for s in subdistrict_by_district.get((p_name, d_name), [])
            ))
            selected_subdistricts_formatted = st.multiselect("ตำบล / แขวง", options=unique_subdistricts_formatted, default=[])
        elif selected_provinces:
            unique_subdistricts_formatted = sorted(set(
                s for prov in selected_provinces
                for s in subdistrict_by_province.get(prov, [])
            ))
            selected_subdistricts_formatted = st.multiselect("ตำบล / แขวง", options=unique_subdistricts_formatted, default=[], placeholder="เลือกตำบลในจังหวัดที่เลือก...")
        else:
            selected_subdistricts_formatted = st.multiselect(
                "ตำบล / แขวง",
                options=[],
                default=[],
                placeholder="เลือกจังหวัดหรืออำเภอก่อนเพื่อค้นหาตำบล"
            )
        
        # Price Filter - อิงราคาจริงที่มีในฐานข้อมูล
        valid_prices = df_raw['ราคา'].dropna()
        valid_prices = valid_prices[valid_prices > 0]
        min_p, max_p = 0.0, 100000000.0
        if not valid_prices.empty:
            min_p = float(valid_prices.min())
            max_p = float(valid_prices.max())
            if min_p >= max_p:
                max_p = min_p + 1000000.0
                
            price_span = max_p - min_p
            if price_span > 1000000000:
                step_p = 10000000.0
            elif price_span > 100000000:
                step_p = 1000000.0
            elif price_span > 10000000:
                step_p = 100000.0
            elif price_span > 1000000:
                step_p = 50000.0
            else:
                step_p = 10000.0

            # Quick Price Preset Buttons / Pills
            price_presets = ["ทั้งหมด", "< 1M", "1M - 3M", "3M - 5M", "5M - 10M", "> 10M"]
            
            if "prev_sidebar_price_preset" not in st.session_state:
                st.session_state["prev_sidebar_price_preset"] = "ทั้งหมด"
            if "sidebar_price_preset" not in st.session_state:
                st.session_state["sidebar_price_preset"] = "ทั้งหมด"

            selected_preset = st.pills(
                "กดเลือกช่วงราคาด่วน",
                options=price_presets,
                key="sidebar_price_preset"
            )

            # Detect preset click and synchronize slider value
            if selected_preset != st.session_state.get("prev_sidebar_price_preset"):
                st.session_state["prev_sidebar_price_preset"] = selected_preset
                if selected_preset == "< 1M":
                    st.session_state["sidebar_price_slider"] = (min_p, min(1000000.0, max_p))
                elif selected_preset == "1M - 3M":
                    st.session_state["sidebar_price_slider"] = (max(min_p, 1000000.0), min(3000000.0, max_p))
                elif selected_preset == "3M - 5M":
                    st.session_state["sidebar_price_slider"] = (max(min_p, 3000000.0), min(5000000.0, max_p))
                elif selected_preset == "5M - 10M":
                    st.session_state["sidebar_price_slider"] = (max(min_p, 5000000.0), min(10000000.0, max_p))
                elif selected_preset == "> 10M":
                    st.session_state["sidebar_price_slider"] = (max(min_p, 10000000.0), max_p)
                elif selected_preset == "ทั้งหมด" or selected_preset is None:
                    st.session_state["sidebar_price_slider"] = (min_p, max_p)

            # Ensure slider value is within current min_p and max_p bounds
            if "sidebar_price_slider" in st.session_state:
                curr_val = st.session_state["sidebar_price_slider"]
                if isinstance(curr_val, (list, tuple)) and len(curr_val) == 2:
                    c_low, c_high = curr_val
                    c_low = max(min_p, min(c_low, max_p))
                    c_high = min(max_p, max(c_high, min_p))
                    if c_low > c_high:
                        c_low, c_high = min_p, max_p
                    st.session_state["sidebar_price_slider"] = (c_low, c_high)
            else:
                st.session_state["sidebar_price_slider"] = (min_p, max_p)

            price_range = st.slider(
                "ช่วงราคาขาย (บาท)",
                min_value=min_p,
                max_value=max_p,
                value=st.session_state["sidebar_price_slider"],
                step=step_p,
                format="%,d",
                key="sidebar_price_slider"
            )
        else:
            price_range = (min_p, max_p)    
    else:
        st.warning("ไม่มีตัวกรองข้อมูลเนื่องจากยังไม่มีไฟล์ข้อมูล all_assets.parquet")

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
--seg-track-bg: rgba(15, 23, 42, 0.75);
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

/* Sidebar Select boxes, Number inputs, Text inputs */
section[data-testid="stSidebar"] div[data-baseweb="select"] > div,
section[data-testid="stSidebar"] div[data-baseweb="input"],
section[data-testid="stSidebar"] div[data-testid="stTextInput"] input,
section[data-testid="stSidebar"] div[data-testid="stNumberInput"] input {
    background-color: rgba(2, 44, 34, 0.85) !important;
    border: 1px solid rgba(52, 211, 153, 0.35) !important;
    color: #ffffff !important;
    -webkit-text-fill-color: #ffffff !important;
    border-radius: 8px !important;
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

.st-key-main_tabs_container [role="tab"]:nth-child(2) p::before,
.st-key-main_tabs_container div[role="tablist"] > div:nth-child(2) p::before {
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

.st-key-main_tabs_container [role="tab"]:nth-child(3) p::before,
.st-key-main_tabs_container div[role="tablist"] > div:nth-child(3) p::before {
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

.st-key-main_tabs_container [role="tab"]:nth-child(4) p::before,
.st-key-main_tabs_container div[role="tablist"] > div:nth-child(4) p::before {
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
    <div class="floating-card">
        <div class="floating-card-title"><i class="fa fa-list" style="color: #047857;"></i> ทรัพย์สินที่พบ</div>
        <div class="floating-card-value">{filtered_count_str}</div>
        <div class="floating-card-sub">{summary_text}</div>
    </div>
    <div class="floating-card">
        <div class="floating-card-title"><i class="fa fa-wallet" style="color: #059669;"></i> มูลค่ารวมทรัพย์สิน</div>
        <div class="floating-card-value">{total_value_str}</div>
        <div class="floating-card-sub">มูลค่ารวมตามตัวกรอง</div>
    </div>
    <div class="floating-card">
        <div class="floating-card-title"><i class="fa fa-arrow-down" style="color: #10b981;"></i> ราคาต่ำสุด (Min)</div>
        <div class="floating-card-value">{min_price_str}</div>
        <div class="floating-card-sub">ราคาเริ่มต้นต่ำสุด</div>
    </div>
    <div class="floating-card">
        <div class="floating-card-title"><i class="fa fa-tags" style="color: #047857;"></i> ราคากลาง (Median)</div>
        <div class="floating-card-value">{median_price_str}</div>
        <div class="floating-card-sub">ค่ามัธยฐานของกลุ่ม</div>
    </div>
    <div class="floating-card">
        <div class="floating-card-title"><i class="fa fa-calculator" style="color: #059669;"></i> ราคาเฉลี่ย (Mean)</div>
        <div class="floating-card-value">{mean_price_str}</div>
        <div class="floating-card-sub">ค่าเฉลี่ยเลขคณิต</div>
    </div>
    <div class="floating-card">
        <div class="floating-card-title"><i class="fa fa-arrow-up" style="color: #10b981;"></i> ราคาสูงสุด (Max)</div>
        <div class="floating-card-value">{max_price_str}</div>
        <div class="floating-card-sub">มูลค่าสูงสุดในกลุ่ม</div>
    </div>
    <div class="floating-card">
        <div class="floating-card-title"><i class="fa fa-chart-line" style="color: #047857;"></i> ส่วนเบี่ยงเบน (SD)</div>
        <div class="floating-card-value">{sd_price_str}</div>
        <div class="floating-card-sub">การกระจายตัวของราคา</div>
    </div>
</div>
"""

st.markdown(floating_kpi_html, unsafe_allow_html=True)

# ----------------- MAIN NAVIGATION (4 Tabs with Font Awesome Solid Icons) -----------------
with st.container(key="main_tabs_container"):
    tab1, tab2, tab3, tab4 = st.tabs([
        "ภาพรวม & แผนที่",
        "สถิติ & วิเคราะห์",
        "เปรียบเทียบตำแหน่ง",
        "รายการทรัพย์สิน",
    ], key="main_tabs")

# ----- TAB 1: BUBBLE & MAP -----
with tab1:
    with st.container(key="tab_map"):
        st.markdown("""
        <style>
        /* Container sizing & alignment */
        .st-key-tab1_view_toggle_container,
        .st-key-tab1_metric_toggle_container,
        .st-key-tab1_map_color_toggle_container {
            width: auto !important;
            display: inline-flex !important;
        }

        .st-key-tab1_metric_toggle_container,
        .st-key-tab1_map_color_toggle_container {
            margin-left: auto !important;
            display: flex !important;
            justify-content: flex-end !important;
        }

        /* Outer button group track (The Apple Pill Track - Compact) */
        .st-key-tab1_view_toggle_container div[data-testid="stButtonGroup"],
        .st-key-tab1_view_toggle_container div[role="radiogroup"],
        .st-key-tab1_view_toggle_container [data-baseweb="button-group"],
        .st-key-tab1_metric_toggle_container div[data-testid="stButtonGroup"],
        .st-key-tab1_metric_toggle_container div[role="radiogroup"],
        .st-key-tab1_metric_toggle_container [data-baseweb="button-group"],
        .st-key-tab1_map_color_toggle_container div[data-testid="stButtonGroup"],
        .st-key-tab1_map_color_toggle_container div[role="radiogroup"],
        .st-key-tab1_map_color_toggle_container [data-baseweb="button-group"],
        .st-key-tab1_main_view_mode div[data-testid="stButtonGroup"],
        .st-key-tab1_main_view_mode div[role="radiogroup"],
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
        .st-key-tab1_view_toggle_container button,
        .st-key-tab1_view_toggle_container button[data-variant="segmented_control"],
        .st-key-tab1_metric_toggle_container button,
        .st-key-tab1_metric_toggle_container button[data-variant="segmented_control"],
        .st-key-tab1_map_color_toggle_container button,
        .st-key-tab1_map_color_toggle_container button[data-variant="segmented_control"],
        .st-key-tab1_main_view_mode button,
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
        .st-key-tab1_view_toggle_container span[data-testid="stIconMaterial"],
        .st-key-tab1_metric_toggle_container span[data-testid="stIconMaterial"],
        .st-key-tab1_map_color_toggle_container span[data-testid="stIconMaterial"],
        .st-key-tab1_main_view_mode span[data-testid="stIconMaterial"],
        .st-key-tab1_bubble_metric_radio span[data-testid="stIconMaterial"],
        .st-key-tab1_map_color_mode span[data-testid="stIconMaterial"] {
            font-size: 15px !important;
            width: 15px !important;
            height: 15px !important;
            line-height: 15px !important;
            margin-right: 2px !important;
        }

        /* Inactive button hover */
        .st-key-tab1_view_toggle_container button:hover,
        .st-key-tab1_metric_toggle_container button:hover,
        .st-key-tab1_map_color_toggle_container button:hover,
        .st-key-tab1_main_view_mode button:hover,
        .st-key-tab1_bubble_metric_radio button:hover,
        .st-key-tab1_map_color_mode button:hover {
            color: var(--card-text, #0f172a) !important;
            -webkit-text-fill-color: var(--card-text, #0f172a) !important;
            background: rgba(255, 255, 255, 0.45) !important;
        }

        /* ACTIVE / SELECTED BUTTON (Apple Floating Pill) */
        .st-key-tab1_view_toggle_container button[aria-checked="true"],
        .st-key-tab1_view_toggle_container button[data-state="active"],
        .st-key-tab1_view_toggle_container button[kind="segmented_controlActive"],
        .st-key-tab1_metric_toggle_container button[aria-checked="true"],
        .st-key-tab1_metric_toggle_container button[data-state="active"],
        .st-key-tab1_metric_toggle_container button[kind="segmented_controlActive"],
        .st-key-tab1_map_color_toggle_container button[aria-checked="true"],
        .st-key-tab1_map_color_toggle_container button[data-state="active"],
        .st-key-tab1_map_color_toggle_container button[kind="segmented_controlActive"],
        .st-key-tab1_main_view_mode button[aria-checked="true"],
        .st-key-tab1_main_view_mode button[data-state="active"],
        .st-key-tab1_main_view_mode button[kind="segmented_controlActive"],
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
        .st-key-tab1_view_toggle_container button[aria-checked="true"] *,
        .st-key-tab1_metric_toggle_container button[aria-checked="true"] *,
        .st-key-tab1_map_color_toggle_container button[aria-checked="true"] *,
        .st-key-tab1_main_view_mode button[aria-checked="true"] *,
        .st-key-tab1_bubble_metric_radio button[aria-checked="true"] *,
        .st-key-tab1_map_color_mode button[aria-checked="true"] * {
            color: var(--seg-active-text, #065f46) !important;
            -webkit-text-fill-color: var(--seg-active-text, #065f46) !important;
            font-weight: 700 !important;
        }

        /* Inner elements for Inactive button */
        .st-key-tab1_view_toggle_container button:not([aria-checked="true"]) *,
        .st-key-tab1_metric_toggle_container button:not([aria-checked="true"]) *,
        .st-key-tab1_map_color_toggle_container button:not([aria-checked="true"]) *,
        .st-key-tab1_main_view_mode button:not([aria-checked="true"]) *,
        .st-key-tab1_bubble_metric_radio button:not([aria-checked="true"]) *,
        .st-key-tab1_map_color_mode button:not([aria-checked="true"]) * {
            color: var(--seg-inactive-text, #64748b) !important;
            -webkit-text-fill-color: var(--seg-inactive-text, #64748b) !important;
            font-weight: 600 !important;
        }

        /* Remove default dividers / pseudo lines */
        .st-key-tab1_view_toggle_container button::before,
        .st-key-tab1_view_toggle_container button::after,
        .st-key-tab1_metric_toggle_container button::before,
        .st-key-tab1_metric_toggle_container button::after,
        .st-key-tab1_map_color_toggle_container button::before,
        .st-key-tab1_map_color_toggle_container button::after,
        .st-key-tab1_main_view_mode button::before,
        .st-key-tab1_main_view_mode button::after {
            display: none !important;
            content: none !important;
            border: none !important;
        }

        /* Push the 2nd segmented control (metric toggle) to far right */
        .st-key-tab_map div[data-testid="column"]:last-child:has([data-testid="stButtonGroup"]),
        .st-key-tab_map div[data-testid="column"]:last-child:has([role="radiogroup"]),
        .st-key-tab_map div.stColumn:last-child {
            display: flex !important;
            flex-direction: row !important;
            justify-content: flex-end !important;
            align-items: center !important;
        }
        </style>
        """, unsafe_allow_html=True)
        c_mode1, c_spacer, c_mode2 = st.columns([0.34, 0.38, 0.28])
        with c_mode1:
            with st.container(key="tab1_view_toggle_container"):
                t1_view = st.segmented_control(
                    label="view_mode",
                    options=[":material/bubble_chart: Bubble View", ":material/map: Interactive Map"],
                    default=":material/bubble_chart: Bubble View",
                    key="tab1_main_view_mode",
                    label_visibility="collapsed"
                )
                if not t1_view:
                    t1_view = ":material/bubble_chart: Bubble View"
                
        if "Bubble" in t1_view:
            with c_mode2:
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
                stc.html(bubble_html, height=770)
            except Exception:
                st.html(bubble_html)
                
        else:
            with c_mode2:
                map_color_mode = st.segmented_control(
                    label="map_color",
                    options=[":material/corporate_fare: By Company", ":material/category: By Property Type"],
                    default=":material/corporate_fare: By Company",
                    key="tab1_map_color_mode",
                    label_visibility="collapsed"
                )
                if not map_color_mode:
                    map_color_mode = ":material/corporate_fare: By Company"

            # Map Rendering (Deck.gl OpenStreetMap Scatterplot Map with dynamic color mode)
            progress_bar = st.progress(0, text="กำลังเตรียมข้อมูลแผนที่...")
            
            # Step 1: Filter rows with coordinates (20%)
            progress_bar.progress(20, text="กำลังกรองจุดพิกัดในประเทศไทย (20%)...")
            map_data = df_filtered[
                df_filtered['ละติจูด'].notna() & df_filtered['ลองจิจูด'].notna() &
                df_filtered['ละติจูด'].between(5, 21) & df_filtered['ลองจิจูด'].between(97, 106)
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
                # Strategy 1: Vectorized string column extraction (no list comprehensions)
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

                # Step 3: Vectorized color mapping — no per-row Python loops
                if "Property Type" in map_color_mode:
                    progress_bar.progress(60, text="กำลังจัดเตรียมสีตามประเภททรัพย์สิน (60%)...")
                    PROP_TYPE_COLORS = {
                        "บ้านเดี่ยว": [37, 99, 235],
                        "ห้องชุดพักอาศัย": [139, 92, 246],
                        "ทาวน์เฮ้าส์": [245, 158, 11],
                        "ที่ดินเปล่า": [16, 185, 129],
                        "ที่ดินพร้อมสิ่งปลูกสร้าง": [5, 150, 105],
                        "อาคารพาณิชย์": [244, 63, 94],
                        "วิลล่า": [236, 72, 153],
                        "โรงงาน/โกดัง": [6, 182, 212],
                        "บ้านแฝด": [99, 102, 241],
                        "อพาร์ทเมนท์": [168, 85, 247],
                        "อาคารสำนักงาน": [100, 116, 139],
                        "โรงแรม/รีสอร์ท": [234, 179, 8],
                        "ห้องชุดพาณิชยกรรม/สำนักงาน": [14, 165, 233],
                        "ปั๊มน้ำมัน": [217, 119, 6],
                        "โชว์รูม": [249, 115, 22],
                        "โฮมออฟฟิศ": [79, 70, 229],
                        "สังหาริมทรัพย์": [120, 113, 108]
                    }
                    DEFAULT_PROP_COLOR = [148, 163, 184]
                    _upt = map_data['ประเภททรัพย์'].unique()
                    _r_pt = {t: PROP_TYPE_COLORS.get(t, DEFAULT_PROP_COLOR)[0] for t in _upt}
                    _g_pt = {t: PROP_TYPE_COLORS.get(t, DEFAULT_PROP_COLOR)[1] for t in _upt}
                    _b_pt = {t: PROP_TYPE_COLORS.get(t, DEFAULT_PROP_COLOR)[2] for t in _upt}
                    r_arr = map_data['ประเภททรัพย์'].map(_r_pt).fillna(DEFAULT_PROP_COLOR[0]).astype('uint8')
                    g_arr = map_data['ประเภททรัพย์'].map(_g_pt).fillna(DEFAULT_PROP_COLOR[1]).astype('uint8')
                    b_arr = map_data['ประเภททรัพย์'].map(_b_pt).fillna(DEFAULT_PROP_COLOR[2]).astype('uint8')

                    # Dynamic Legend for Property Types (with centroid counts)
                    type_counts = map_data['ประเภททรัพย์'].value_counts()
                    legend_items_html = ['<div style="font-weight: 600; font-size: 11px; text-transform: uppercase; color: #64748b; margin-bottom: 4px; letter-spacing: 0.5px;">ประเภททรัพย์สิน</div>']
                    for p_name, p_rgb in PROP_TYPE_COLORS.items():
                        c_cnt = type_counts.get(p_name, 0)
                        if c_cnt > 0:
                            hex_c = f"rgb({p_rgb[0]},{p_rgb[1]},{p_rgb[2]})"
                            c_centroid = centroid_per_type.get(p_name, 0)
                            centroid_tag = f' <span class="legend-centroid-badge" style="background:#fef3c7; color:#92400e; font-size:9.5px; font-weight:800; padding:0px 4px; border-radius:4px; border:1px solid #fde68a;">&#9651; {c_centroid:,}</span>' if c_centroid > 0 else ''
                            legend_items_html.append(f'<div class="legend-item"><span class="legend-color" style="background:{hex_c};"></span>{p_name} ({c_cnt:,}){centroid_tag}</div>')
                    other_cnt = sum(cnt for t, cnt in type_counts.items() if t not in PROP_TYPE_COLORS)
                    if other_cnt > 0:
                        other_types = [t for t in type_counts.index if t not in PROP_TYPE_COLORS]
                        other_pt_centroid = sum(centroid_per_type.get(t, 0) for t in other_types)
                        other_centroid_tag = f' <span class="legend-centroid-badge" style="background:#fef3c7; color:#92400e; font-size:9.5px; font-weight:800; padding:0px 4px; border-radius:4px; border:1px solid #fde68a;">&#9651; {other_pt_centroid:,}</span>' if other_pt_centroid > 0 else ''
                        legend_items_html.append(f'<div class="legend-item"><span class="legend-color" style="background:#94a3b8;"></span>อื่นๆ ({other_cnt:,}){other_centroid_tag}</div>')
                    total_centroid_count = sum(centroid_per_type.values())
                    if total_centroid_count > 0:
                        legend_items_html.append(f'<div class="legend-centroid-summary" style="border-top:1px dashed #e2e8f0; margin-top:5px; padding-top:5px; font-size:10.5px; color:#92400e; font-weight:700;">&#9651; พิกัดกึ่งกลาง {total_centroid_count:,} จาก {len(map_data):,} จุด</div>')
                    legend_content = "\n".join(legend_items_html)
                else:
                    progress_bar.progress(60, text="กำลังจัดเตรียมสีตามบริษัทคู่แข่ง (60%)...")
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

                # Step 4: Build compact CSV + lookup table, then GZIP compress both (80%)
                # GZIP reduces payload 6-10x → much faster browser decode
                progress_bar.progress(80, text="กำลังบีบอัด GZIP และแปลงเป็น Base64 (80%)...")

                # Lookup table for column compression (company / type / province / sale_type / region / district)
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

                lookup_obj = {
                    'co': _co_cat.categories.tolist(),
                    'ty': _ty_cat.categories.tolist(),
                    'pv': _pv_cat.categories.tolist(),
                    'st': _st_cat.categories.tolist(),
                    'rg': _rg_cat.categories.tolist(),
                    'dt': _dt_cat.categories.tolist(),
                    'subdt': _subdt_cat.categories.tolist(),
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
                    '_p':     _prices_num.fillna(0).astype('float32').values,
                    '_up':    _unit_prices.astype('float32'),
                    '_price_str': prices_list,
                    '_link':     links,
                    '_centroid': centroid_flags,
                    '_deed':     deeds,
                })

                # GZIP compress the CSV before base64 encoding
                csv_base64 = base64.b64encode(
                    gzip.compress(
                        csv_df.to_csv(index=False).encode('utf-8'),
                        compresslevel=1
                    )
                ).decode('utf-8')
                
                # Step 5: Render map template (90%)
                _tmpl_path = "static/map_template.html"
                _tmpl_mtime = os.path.getmtime(_tmpl_path) if os.path.exists(_tmpl_path) else None
                base_tmpl = get_base_map_html(_tmpl_mtime)
                html_content = base_tmpl.replace("CSV_BASE64_PLACEHOLDER", csv_base64)
                html_content = html_content.replace("LOOKUP_BASE64_PLACEHOLDER", lookup_b64)
                html_content = html_content.replace("LEGEND_ITEMS_PLACEHOLDER", legend_content)
                body_theme_class = "dark-theme" if is_dark_mode else ""
                html_content = html_content.replace("BODY_CLASS_PLACEHOLDER", body_theme_class)
                
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

# ----- TAB 2: ANALYTICS -----
with tab2:
    st.markdown("### <i class='fa-solid fa-chart-line' style='color:#059669; margin-right:8px;'></i>วิเคราะห์เชิงลึกและเปรียบเทียบสถิติของคู่แข่ง", unsafe_allow_html=True)
    
    if df_filtered.empty:
        st.warning("ไม่มีข้อมูลสำหรับจัดทำแผนภูมิวิเคราะห์สถิติ")
    else:
        # Create sub-tabs inside Tab 2
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


# ----- TAB 3: COMPARISON -----
with tab3:
    comp_sub_tab1, comp_sub_tab2, comp_sub_tab3 = st.tabs([
        "เปรียบเทียบตามรัศมีทำเล (Radius Location Analysis)",
        "เปรียบเทียบในโครงการเดียวกัน (Same-Project Comparison)",
        "สถิติค่ากลาง ราคาต่อหน่วยพื้นที่ (Median Price per Area Analysis)"
    ])

    with comp_sub_tab1:
        st.markdown("### <i class='fa-solid fa-crosshairs' style='color:#059669; margin-right:8px;'></i>เปรียบเทียบทำเลของทรัพย์สิน (Asset Location Comparison)", unsafe_allow_html=True)

        st.markdown("""
        <style>
        /* Prominent Reference Point Method Choice Options */
        .st-key-comp_ref_method_box {
            margin: 12px 0 20px 0 !important;
            width: 100% !important;
        }
        .st-key-comp_ref_method_box,
        .st-key-comp_ref_method_box > div,
        .st-key-comp_ref_method_box div[data-testid="stElementContainer"],
        .st-key-comp_ref_method_box div[data-testid="stButtonGroup"],
        .st-key-comp_ref_method_box div[role="radiogroup"] {
            width: 100% !important;
            max-width: 100% !important;
            display: flex !important;
        }
        .st-key-comp_ref_method_box div[role="radiogroup"] {
            gap: 16px !important;
            flex-direction: row !important;
            background: transparent !important;
            padding: 4px 0 !important;
            border: none !important;
        }
        .st-key-comp_ref_method_box button[data-variant="segmented_control"] {
            flex: 1 1 0% !important;
            width: 50% !important;
            min-height: 54px !important;
            padding: 12px 24px !important;
            border-radius: 14px !important;
            font-size: 1.05rem !important;
            font-weight: 700 !important;
            letter-spacing: -0.2px !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            gap: 12px !important;
            cursor: pointer !important;
            transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1) !important;
        }
        .st-key-comp_ref_method_box button[data-variant="segmented_control"] span,
        .st-key-comp_ref_method_box button[data-variant="segmented_control"] div[data-testid="stMarkdownContainer"],
        .st-key-comp_ref_method_box button[data-variant="segmented_control"] p {
            white-space: nowrap !important;
            margin: 0 !important;
            padding: 0 !important;
            line-height: 1.35 !important;
            font-size: inherit !important;
        }
        /* Inactive Choice Option */
        .st-key-comp_ref_method_box button[data-variant="segmented_control"][aria-checked="false"],
        .st-key-comp_ref_method_box button[data-variant="segmented_control"]:not([data-selected="true"]) {
            background: #ffffff !important;
            color: #064e3b !important;
            border: 2px solid #a7f3d0 !important;
            box-shadow: 0 4px 14px rgba(4, 120, 87, 0.08) !important;
            transform: none !important;
        }
        .st-key-comp_ref_method_box button[data-variant="segmented_control"][aria-checked="false"] *,
        .st-key-comp_ref_method_box button[data-variant="segmented_control"]:not([data-selected="true"]) * {
            color: #064e3b !important;
            -webkit-text-fill-color: #064e3b !important;
            font-weight: 700 !important;
        }
        .st-key-comp_ref_method_box button[data-variant="segmented_control"][aria-checked="false"]:hover,
        .st-key-comp_ref_method_box button[data-variant="segmented_control"]:not([data-selected="true"]):hover {
            background: #ecfdf5 !important;
            border-color: #047857 !important;
            box-shadow: 0 8px 24px rgba(4, 120, 87, 0.2) !important;
            transform: translateY(-2px) !important;
        }
        .st-key-comp_ref_method_box button[data-variant="segmented_control"][aria-checked="false"]:hover *,
        .st-key-comp_ref_method_box button[data-variant="segmented_control"]:not([data-selected="true"]):hover * {
            color: #047857 !important;
            -webkit-text-fill-color: #047857 !important;
        }
        /* Active Choice Option - Striking Executive Green */
        .st-key-comp_ref_method_box button[data-variant="segmented_control"][aria-checked="true"],
        .st-key-comp_ref_method_box button[data-variant="segmented_control"][data-selected="true"] {
            background: linear-gradient(135deg, #064e3b 0%, #047857 55%, #059669 100%) !important;
            color: #ffffff !important;
            border: 2px solid #34d399 !important;
            box-shadow: 0 10px 28px rgba(4, 120, 87, 0.38), 0 2px 6px rgba(0, 0, 0, 0.1) !important;
            transform: translateY(-2px) !important;
        }
        .st-key-comp_ref_method_box button[data-variant="segmented_control"][aria-checked="true"] *,
        .st-key-comp_ref_method_box button[data-variant="segmented_control"][data-selected="true"] * {
            color: #ffffff !important;
            -webkit-text-fill-color: #ffffff !important;
            font-weight: 800 !important;
            text-shadow: 0 1px 2px rgba(0, 0, 0, 0.25);
        }
        /* Icons inside the choice buttons */
        .st-key-comp_ref_method_box button[data-variant="segmented_control"] span[data-testid="stIconMaterial"] {
            font-size: 1.55rem !important;
            width: 1.55rem !important;
            height: 1.55rem !important;
            display: inline-flex !important;
            align-items: center !important;
            justify-content: center !important;
        }
        /* Dark mode support */
        [data-theme="dark"] .st-key-comp_ref_method_box button[data-variant="segmented_control"][aria-checked="false"],
        .stApp[data-theme="dark"] .st-key-comp_ref_method_box button[data-variant="segmented_control"][aria-checked="false"] {
            background: #1e293b !important;
            color: #a7f3d0 !important;
            border: 2.5px solid #064e3b !important;
        }
        [data-theme="dark"] .st-key-comp_ref_method_box button[data-variant="segmented_control"][aria-checked="false"] *,
        .stApp[data-theme="dark"] .st-key-comp_ref_method_box button[data-variant="segmented_control"][aria-checked="false"] * {
            color: #a7f3d0 !important;
            -webkit-text-fill-color: #a7f3d0 !important;
        }

        /* High-Contrast Dropdown / Selectbox Styling (Fix border blending into background) */
        div[data-testid="stSelectbox"] .react-aria-ComboBox > div,
        div[data-testid="stSelectbox"] div[role="group"],
        div[data-testid="stSelectbox"] div[data-baseweb="select"] > div {
            background: #ffffff !important;
            border: 1.8px solid #94a3b8 !important;
            border-radius: 10px !important;
            box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06) !important;
            transition: all 0.2s ease-in-out !important;
            min-height: 44px !important;
        }
        div[data-testid="stSelectbox"] .react-aria-ComboBox > div:hover,
        div[data-testid="stSelectbox"] div[role="group"]:hover,
        div[data-testid="stSelectbox"] div[data-baseweb="select"] > div:hover {
            border-color: #047857 !important;
            box-shadow: 0 3px 10px rgba(4, 120, 87, 0.15) !important;
        }
        div[data-testid="stSelectbox"] .react-aria-ComboBox > div:focus-within,
        div[data-testid="stSelectbox"] div[role="group"]:focus-within,
        div[data-testid="stSelectbox"] div[data-baseweb="select"] > div:focus-within {
            border-color: #047857 !important;
            box-shadow: 0 0 0 3px rgba(4, 120, 87, 0.22) !important;
        }
        div[data-testid="stSelectbox"] label[data-testid="stWidgetLabel"] p {
            font-weight: 700 !important;
            color: #0f172a !important;
            font-size: 0.95rem !important;
            margin-bottom: 4px !important;
        }
        div[data-testid="stSelectbox"] .react-aria-ComboBox input {
            color: #0f172a !important;
            -webkit-text-fill-color: #0f172a !important;
            font-weight: 600 !important;
            font-size: 0.95rem !important;
        }
        div[data-testid="stSelectbox"] .react-aria-ComboBox button {
            color: #047857 !important;
        }
        /* Dark mode selectbox */
        [data-theme="dark"] div[data-testid="stSelectbox"] .react-aria-ComboBox > div,
        [data-theme="dark"] div[data-testid="stSelectbox"] div[role="group"],
        [data-theme="dark"] div[data-testid="stSelectbox"] div[data-baseweb="select"] > div,
        .stApp[data-theme="dark"] div[data-testid="stSelectbox"] .react-aria-ComboBox > div,
        .stApp[data-theme="dark"] div[data-testid="stSelectbox"] div[role="group"] {
            background: #1e293b !important;
            border: 1.8px solid #64748b !important;
            box-shadow: 0 1px 4px rgba(0, 0, 0, 0.25) !important;
        }
        [data-theme="dark"] div[data-testid="stSelectbox"] .react-aria-ComboBox > div:hover,
        .stApp[data-theme="dark"] div[data-testid="stSelectbox"] div[role="group"]:hover {
            border-color: #34d399 !important;
            box-shadow: 0 3px 10px rgba(52, 211, 153, 0.18) !important;
        }
        [data-theme="dark"] div[data-testid="stSelectbox"] .react-aria-ComboBox > div:focus-within,
        .stApp[data-theme="dark"] div[data-testid="stSelectbox"] div[role="group"]:focus-within {
            border-color: #34d399 !important;
            box-shadow: 0 0 0 3px rgba(52, 211, 153, 0.28) !important;
        }
        [data-theme="dark"] div[data-testid="stSelectbox"] label[data-testid="stWidgetLabel"] p,
        .stApp[data-theme="dark"] div[data-testid="stSelectbox"] label[data-testid="stWidgetLabel"] p {
            color: #f1f5f9 !important;
        }
        [data-theme="dark"] div[data-testid="stSelectbox"] .react-aria-ComboBox input,
        .stApp[data-theme="dark"] div[data-testid="stSelectbox"] .react-aria-ComboBox input {
            color: #f8fafc !important;
            -webkit-text-fill-color: #f8fafc !important;
        }
        </style>
        """, unsafe_allow_html=True)
        with st.container(key="comp_ref_method_box"):
            ref_method = st.segmented_control(
                "วิธีการกำหนดจุดอ้างอิง",
                options=[
                    ":material/edit_location: ระบุพิกัดด้วยตัวเอง (Manual Coordinates)",
                    ":material/manage_search: เลือกจากในระบบ (Choose from Asset)"
                ],
                default=":material/edit_location: ระบุพิกัดด้วยตัวเอง (Manual Coordinates)",
                label_visibility="collapsed",
                key="comp_ref_method"
            )
        if not ref_method:
            ref_method = ":material/edit_location: ระบุพิกัดด้วยตัวเอง (Manual Coordinates)"

        # Reset results when ref_method changes so stale results don't persist
        if st.session_state.get("_prev_comp_ref_method") != ref_method:
            st.session_state["_prev_comp_ref_method"] = ref_method
            st.session_state["has_run_comp"] = False
            st.session_state["tab3_custom_selected_codes"] = set()
            st.session_state["tab3_active_coord_filter"] = None
            if "sel_map_lat" in st.query_params:
                del st.query_params["sel_map_lat"]
            if "sel_map_lon" in st.query_params:
                del st.query_params["sel_map_lon"]
            if "sel_custom_codes" in st.query_params:
                del st.query_params["sel_custom_codes"]

        inp_col1, inp_col2 = st.columns(2)
        with inp_col1:
            st.markdown("##### <i class='fa-solid fa-map-pin' style='color:#059669; margin-right:6px;'></i>ส่วนที่ 1: กำหนดพิกัดที่ต้องการค้นหา", unsafe_allow_html=True)

            # Initialize session state for Comparison coordinates if not present
            if "comp_ref_name" not in st.session_state:
                st.session_state["comp_ref_name"] = "จุดศูนย์กลางกรุงเทพฯ (อนุสาวรีย์ชัยฯ)"
            if "comp_ref_lat" not in st.session_state:
                st.session_state["comp_ref_lat"] = 13.7651
            if "comp_ref_lng" not in st.session_state:
                st.session_state["comp_ref_lng"] = 100.5383
            if "comp_ref_price" not in st.session_state:
                st.session_state["comp_ref_price"] = 5000000.0
            if "comp_ref_type" not in st.session_state:
                st.session_state["comp_ref_type"] = "บ้านเดี่ยว"
            if "has_run_comp" not in st.session_state:
                st.session_state["has_run_comp"] = False


            # Read coordinates from URL query params set by Leaflet picker JS
            # This is the reliable mechanism: JS does history.replaceState with _clat/_clng
            _qp_lat = st.query_params.get("_clat")
            _qp_lng = st.query_params.get("_clng")
            if _qp_lat and _qp_lng:
                try:
                    _qp_lat_f = float(_qp_lat)
                    _qp_lng_f = float(_qp_lng)
                    if _qp_lat_f != st.session_state.get("_last_qp_lat") or _qp_lng_f != st.session_state.get("_last_qp_lng"):
                        st.session_state["_last_qp_lat"] = _qp_lat_f
                        st.session_state["_last_qp_lng"] = _qp_lng_f
                        st.session_state["comp_manual_lat"] = _qp_lat_f
                        st.session_state["comp_manual_lng"] = _qp_lng_f
                except (ValueError, TypeError):
                    pass

            # Helper to parse land sqwah from pandas Series or Row
            def parse_land_sqwah(r):
                if r is None:
                    return np.nan
                # 1. Direct numeric column 'พื้นที่_ตารางวา'
                val = r.get('พื้นที่_ตารางวา')
                if pd.notna(val):
                    try:
                        f_val = float(val)
                        if f_val > 0:
                            return f_val
                    except (ValueError, TypeError):
                        pass
                    
                # 2. Derive from pre-calculated 'ราคาต่อตารางวา' if present
                price = r.get('ราคา')
                p_sqwah = r.get('ราคาต่อตารางวา')
                if pd.notna(price) and pd.notna(p_sqwah):
                    try:
                        fp = float(price)
                        fpsq = float(p_sqwah)
                        if fp > 0 and fpsq > 0:
                            return fp / fpsq
                    except (ValueError, TypeError):
                        pass
                    
                # 3. Parse text format e.g. "1-2-50" or "1 ไร่ 2 งาน 50 ตารางวา"
                txt = str(r.get('เนื้อที่ (ตร.ว.)', r.get('เนื้อที่', ''))).strip()
                if txt and txt not in ['nan', 'None', '-', '']:
                    rai_m = re.search(r'(\d+)\s*ไร่', txt)
                    ngan_m = re.search(r'(\d+)\s*งาน', txt)
                    wah_m = re.search(r'(\d+(?:\.\d+)?)\s*(?:วา|ตารางวา|ตร\.วา|ตร\.ว\.)', txt)
                    
                    if rai_m or ngan_m or wah_m:
                        rai = float(rai_m.group(1)) if rai_m else 0.0
                        ngan = float(ngan_m.group(1)) if ngan_m else 0.0
                        wah = float(wah_m.group(1)) if wah_m else 0.0
                        total_w = (rai * 400.0) + (ngan * 100.0) + wah
                        if total_w > 0:
                            return total_w
                            
                    dash_m = re.search(r'^(\d+)-(\d+)-(\d+(?:\.\d+)?)$', txt)
                    if dash_m:
                        rai = float(dash_m.group(1))
                        ngan = float(dash_m.group(2))
                        wah = float(dash_m.group(3))
                        total_w = (rai * 400.0) + (ngan * 100.0) + wah
                        if total_w > 0:
                            return total_w
                            
                    num_m = re.search(r'^(\d+(?:\.\d+)?)$', txt)
                    if num_m:
                        try:
                            return float(num_m.group(1))
                        except (ValueError, TypeError):
                            pass
                        
            # Helper to parse usable sqm for condos / apartments
            def parse_condo_sqm(r):
                if r is None:
                    return np.nan
                val = r.get('พื้นที่ใช้สอย (ตร.ม.)', r.get('พื้นที่ใช้สอย', np.nan))
                if pd.notna(val):
                    try:
                        f_val = float(val)
                        if f_val > 0:
                            return f_val
                    except (ValueError, TypeError):
                        pass
                txt = str(r.get('พื้นที่ใช้สอย (ตร.ม.)', r.get('พื้นที่ใช้สอย', ''))).strip()
                if txt and txt not in ['nan', 'None', '-', '']:
                    m = re.search(r'(\d+(?:\.\d+)?)', txt)
                    if m:
                        try:
                            return float(m.group(1))
                        except (ValueError, TypeError):
                            pass
                return np.nan

            # Initialize variables
            inp_name = ""
            inp_lat = 0.0
            inp_lng = 0.0
            inp_price = 0.0
            inp_type = ""

            # If they choose from existing assets
            if any(k in ref_method for k in ["เลือกจากในระบบ", "เลือกจากรายการทรัพย์สินในระบบ", "Choose from Asset"]):
                col_sel1, col_sel2 = st.columns(2)
                with col_sel1:
                    comp_opts = sorted([str(c) for c in df_raw['บริษัท'].dropna().unique()]) if df_raw is not None else ["SAM"]
                    sam_idx = comp_opts.index("SAM") if "SAM" in comp_opts else 0
                    sanitize_session_state("comp_sel_company", comp_opts, "SAM")
                    sel_ref_company = st.selectbox(
                        "บริษัททรัพย์สิน (เลือกจุดอ้างอิง)",
                        options=comp_opts,
                        index=sam_idx,
                        key="comp_sel_company"
                    )
                with col_sel2:
                    standard_prop_order = [
                        "บ้านเดี่ยว", "ทาวน์เฮ้าส์", "ห้องชุดพักอาศัย", "ที่ดินเปล่า",
                        "อาคารพาณิชย์", "ที่ดินพร้อมสิ่งปลูกสร้าง", "โรงงาน/โกดัง", "บ้านแฝด",
                        "อาคารสำนักงาน", "อพาร์ทเมนท์", "โรงแรม/รีสอร์ท", "ห้องชุดพาณิชยกรรม/สำนักงาน",
                        "สังหาริมทรัพย์", "ฟาร์ม", "ปั๊มน้ำมัน", "เพิงอเนกประสงค์", "อื่นๆ"
                    ]
                    raw_types_list = [str(t) for t in df_raw['ประเภททรัพย์'].dropna().unique()] if df_raw is not None else []
                    ordered_types = [t for t in standard_prop_order if t in raw_types_list] + sorted([t for t in raw_types_list if t not in standard_prop_order])
                    valid_ref_types = ["ทั้งหมด"] + ordered_types
                    sanitize_session_state("comp_sel_type", valid_ref_types, "ทั้งหมด")
                    sel_ref_type = st.selectbox(
                        "ประเภททรัพย์ (เลือกจุดอ้างอิง)",
                        options=valid_ref_types,
                        key="comp_sel_type"
                    )
                    ref_comp_df = df_raw[df_raw['บริษัท'] == sel_ref_company] if df_raw is not None else pd.DataFrame()

                # Filter assets
                ref_assets_df = ref_comp_df.copy()
                if not ref_assets_df.empty and sel_ref_type != "ทั้งหมด":
                    ref_assets_df = ref_assets_df[ref_assets_df['ประเภททรัพย์'] == sel_ref_type]

                # Filter assets with valid lat/lng and price
                if not ref_assets_df.empty:
                    ref_assets_df = ref_assets_df[
                        ref_assets_df['ละติจูด'].notna() & 
                        ref_assets_df['ลองจิจูด'].notna() &
                        ref_assets_df['ราคา'].notna()
                    ]

                if not ref_assets_df.empty:
                    # Limit options to top 100 first before creating labels to save massive memory & CPU!
                    total_matches = len(ref_assets_df)
                    display_df = ref_assets_df.head(100).copy()
                    display_df['label'] = display_df.apply(make_clean_dropdown_label, axis=1)
                    display_df = display_df.drop_duplicates(subset=['label'])

                    st.write(f"แสดงผล {len(display_df)} รายการแรก จากที่ค้นพบทั้งหมด {total_matches:,} รายการ (ใช้กล่องค้นหาในตัวเลือกเพื่อค้นเพิ่มได้)")

                    valid_labels = display_df['label'].tolist()
                    sanitize_session_state("comp_sel_asset", valid_labels)
                    selected_asset_label = st.selectbox(
                        "ค้นหาและเลือกรายการทรัพย์สินอ้างอิง",
                        options=valid_labels,
                        index=0,
                        key="comp_sel_asset"
                    )

                    # Reset custom comps if user selects a different reference asset
                    if "_prev_tab3_selected_asset" in st.session_state and st.session_state["_prev_tab3_selected_asset"] != selected_asset_label:
                        st.session_state["tab3_custom_selected_codes"] = set()
                        st.session_state["tab3_active_coord_filter"] = None
                        if "sel_map_lat" in st.query_params:
                            del st.query_params["sel_map_lat"]
                        if "sel_map_lon" in st.query_params:
                            del st.query_params["sel_map_lon"]
                        if "sel_custom_codes" in st.query_params:
                            del st.query_params["sel_custom_codes"]
                    st.session_state["_prev_tab3_selected_asset"] = selected_asset_label

                    # Retrieve the selected asset details
                    if selected_asset_label is not None:
                        matching_assets = display_df[display_df['label'] == selected_asset_label]
                        if not matching_assets.empty:
                            selected_asset = matching_assets.iloc[0]

                            # Set values directly from selected asset
                            inp_name = f"[{selected_asset['บริษัท']}] {selected_asset['ชื่อประกาศ']} ({selected_asset['รหัสทรัพย์']})"
                            inp_lat = float(selected_asset['ละติจูด'])
                            inp_lng = float(selected_asset['ลองจิจูด'])
                            inp_price = float(selected_asset['ราคา'])
                            if sel_ref_type != "ทั้งหมด":
                                inp_type = sel_ref_type
                            else:
                                inp_type = str(selected_asset['ประเภททรัพย์'])

                            inp_use_area = parse_condo_sqm(selected_asset)
                            inp_land_area = parse_land_sqwah(selected_asset)

                            # Location string
                            loc_parts = []
                            if pd.notna(selected_asset.get('ตำบล')) and str(selected_asset.get('ตำบล')).strip() not in ['', 'nan', '-']:
                                loc_parts.append(f"ต.{selected_asset['ตำบล']}")
                            if pd.notna(selected_asset.get('อำเภอ')) and str(selected_asset.get('อำเภอ')).strip() not in ['', 'nan', '-']:
                                loc_parts.append(f"อ.{selected_asset['อำเภอ']}")
                            if pd.notna(selected_asset.get('จังหวัด')) and str(selected_asset.get('จังหวัด')).strip() not in ['', 'nan', '-']:
                                loc_parts.append(f"จ.{selected_asset['จังหวัด']}")
                            loc_str = " ".join(loc_parts) if loc_parts else "ไม่ระบุ"

                            # Project / Title info
                            proj_name = str(selected_asset.get('ชื่อโครงการ', '')).strip()
                            has_proj = proj_name and proj_name not in ['nan', 'None', '-', '', selected_asset['ชื่อประกาศ']]
                            
                            # Price & Unit prices
                            price_str = f"฿{inp_price:,.0f} บาท" if inp_price > 0 else "ไม่ระบุราคา"
                            
                            # Area details
                            area_items = []
                            if pd.notna(inp_land_area) and inp_land_area > 0:
                                u_land_str = f" <span style='color:#64748b; font-size:0.8rem;'>(฿{inp_price/inp_land_area:,.0f}/ตร.ว.)</span>" if inp_price > 0 else ""
                                area_items.append(f"<b>เนื้อที่:</b> {inp_land_area:,.1f} ตร.ว.{u_land_str}")
                            if pd.notna(inp_use_area) and inp_use_area > 0:
                                u_sqm_str = f" <span style='color:#64748b; font-size:0.8rem;'>(฿{inp_price/inp_use_area:,.0f}/ตร.ม.)</span>" if inp_price > 0 else ""
                                area_items.append(f"<b>พื้นที่ใช้สอย:</b> {inp_use_area:,.1f} ตร.ม.{u_sqm_str}")
                            if not area_items:
                                area_items.append("<b>เนื้อที่ / พื้นที่ใช้สอย:</b> ไม่ระบุ")
                            area_html = "</div><div>".join(area_items)

                            # Specs
                            specs = []
                            bed = selected_asset.get('ห้องนอน')
                            bath = selected_asset.get('ห้องน้ำ')
                            park = selected_asset.get('ที่จอดรถ')
                            floor = selected_asset.get('ชั้น')
                            if pd.notna(bed) and str(bed).strip() not in ['', 'nan', '-']:
                                specs.append(f"{int(float(bed)) if str(bed).replace('.','',1).isdigit() else bed} ห้องนอน")
                            if pd.notna(bath) and str(bath).strip() not in ['', 'nan', '-']:
                                specs.append(f"{int(float(bath)) if str(bath).replace('.','',1).isdigit() else bath} ห้องน้ำ")
                            if pd.notna(park) and str(park).strip() not in ['', 'nan', '-']:
                                specs.append(f"{int(float(park)) if str(park).replace('.','',1).isdigit() else park} ที่จอดรถ")
                            if pd.notna(floor) and str(floor).strip() not in ['', 'nan', '-']:
                                f_str = str(floor).strip()
                                specs.append(f_str if 'ชั้น' in f_str else f"ชั้น {f_str}")
                            spec_div = f"<div><b>ฟังก์ชันอาคาร:</b> {' | '.join(specs)}</div>" if specs else ""

                            # Sale type & date
                            sale_type_val = str(selected_asset.get('ประเภทการขาย', 'ขาย')).strip()
                            sale_div = f"<div><b>ประเภทการขาย:</b> {sale_type_val}</div>" if sale_type_val not in ['', 'nan', 'None'] else ""
                            date_val = str(selected_asset.get('วันประกาศ', selected_asset.get('วันที่ดึงข้อมูล', ''))).strip()
                            date_div = f"<div><b>ข้อมูล ณ วันที่:</b> {date_val}</div>" if date_val not in ['', 'nan', 'None'] else ""
                            proj_div = f"<div><b>ชื่อโครงการ:</b> {proj_name}</div>" if has_proj else ""

                            # Link info
                            asset_url = str(selected_asset.get('ลิงก์', '')).strip()
                            if asset_url.startswith('http'):
                                link_html = f"<a href='{asset_url}' target='_blank' style='color:#059669; text-decoration:underline; font-weight:600;'>คลิกดูรายละเอียดบนเว็บต้นทาง ↗</a>"
                            else:
                                link_html = "<span style='color:#94a3b8;'>ไม่มีลิงก์ต้นทาง</span>"

                            card_html = f"""<div style="background: rgba(16, 185, 129, 0.05); border: 1px solid rgba(16, 185, 129, 0.25); border-radius: 12px; padding: 16px 20px; margin: 12px 0 16px 0; font-family: 'Noto Sans Thai', 'Inter', sans-serif;">
<div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid rgba(16, 185, 129, 0.15); padding-bottom: 8px; margin-bottom: 12px; flex-wrap: wrap; gap: 8px;">
<div style="font-size: 1.02rem; font-weight: 700; color: {'#34d399' if is_dark_mode else '#065f46'};"><i class="fa-solid fa-circle-info" style="color:#059669; margin-right:6px;"></i>รายละเอียดทรัพย์อ้างอิงที่เลือก</div>
<div>
<span style="background: #059669; color: #ffffff; font-size: 0.8rem; font-weight: 600; padding: 3px 10px; border-radius: 12px;">{selected_asset['บริษัท']}</span>
<span style="background: rgba(16, 185, 129, 0.12); color: #047857; font-size: 0.8rem; font-weight: 600; padding: 3px 8px; border-radius: 6px; margin-left: 4px;">{selected_asset['รหัสทรัพย์']}</span>
</div>
</div>
<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 8px 20px; font-size: 0.88rem; line-height: 1.6; color: var(--card-text, #334155);">
<div><i class="fa-solid fa-file-lines" style="color:#64748b; margin-right:6px;"></i><b>ชื่อประกาศ:</b> {selected_asset['ชื่อประกาศ']}</div>
{proj_div}
<div><i class="fa-solid fa-house" style="color:#64748b; margin-right:6px;"></i><b>ประเภททรัพย์:</b> <span style="font-weight: 600; color: #059669;">{inp_type}</span></div>
<div><i class="fa-solid fa-tag" style="color:#059669; margin-right:6px;"></i><b>ราคาขาย:</b> <span style="font-size: 1.05rem; font-weight: 800; color: #059669;">{price_str}</span></div>
{sale_div}
<div><i class="fa-solid fa-location-dot" style="color:#64748b; margin-right:6px;"></i><b>ทำเล:</b> {loc_str}</div>
<div><i class="fa-solid fa-crosshairs" style="color:#64748b; margin-right:6px;"></i><b>พิกัด:</b> <code>{inp_lat:.6f}, {inp_lng:.6f}</code></div>
<div>{area_html}</div>
{spec_div}
{date_div}
</div>
<div style="margin-top: 10px; padding-top: 8px; border-top: 1px dashed rgba(59, 130, 246, 0.2); font-size: 0.85rem;">
<i class="fa-solid fa-arrow-up-right-from-square" style="color:#059669; margin-right:4px;"></i><b>ลิงก์ประกาศ:</b> {link_html}
</div>
</div>"""
                            st.html(card_html)
                        else:
                            st.warning("เกิดข้อผิดพลาดในการดึงข้อมูลรายการที่เลือก")
                    else:
                        st.warning("กรุณาเลือกรายการทรัพย์สินอ้างอิง")
            else:
                # If they choose manual coordinates, render manual input widgets + interactive map picker
                st.markdown("**ระบุพิกัดเอง หรือคลิกเลือกหมุดบนแผนที่ด้านล่างเพื่อเลือกพิกัดได้ทันที:**")
                
                def_manual_lat = st.session_state.get("manual_map_clicked_lat", 13.7651)
                def_manual_lng = st.session_state.get("manual_map_clicked_lng", 100.5383)

                inp_name = f"พิกัด ({def_manual_lat:.4f}, {def_manual_lng:.4f})"

                # Define standard property type order
                standard_prop_order = [
                    "บ้านเดี่ยว",
                    "ทาวน์เฮ้าส์",
                    "ห้องชุดพักอาศัย",
                    "ที่ดินเปล่า",
                    "อาคารพาณิชย์",
                    "ที่ดินพร้อมสิ่งปลูกสร้าง",
                    "โรงงาน/โกดัง",
                    "บ้านแฝด",
                    "อาคารสำนักงาน",
                    "อพาร์ทเมนท์",
                    "โรงแรม/รีสอร์ท",
                    "ห้องชุดพาณิชยกรรม/สำนักงาน",
                    "สังหาริมทรัพย์",
                    "ฟาร์ม",
                    "ปั๊มน้ำมัน",
                    "เพิงอเนกประสงค์",
                    "อื่นๆ"
                ]
                raw_unique_types = [str(t) for t in df_raw['ประเภททรัพย์'].dropna().unique()] if df_raw is not None and not df_raw.empty else ["บ้านเดี่ยว"]
                prop_options = [t for t in standard_prop_order if t in raw_unique_types] + sorted([t for t in raw_unique_types if t not in standard_prop_order])

                # Track type changes to auto-adjust area defaults immediately
                if "prev_manual_comp_type" not in st.session_state:
                    st.session_state["prev_manual_comp_type"] = st.session_state.get("comp_manual_type", prop_options[0] if prop_options else "บ้านเดี่ยว")
                
                curr_type = st.session_state.get("comp_manual_type", prop_options[0] if prop_options else "บ้านเดี่ยว")
                if curr_type != st.session_state.get("prev_manual_comp_type"):
                    st.session_state["prev_manual_comp_type"] = curr_type
                    if any(kw in str(curr_type).lower() for kw in ['คอนโด', 'ห้องชุด', 'อพาร์ทเมนท์', 'แฟลต']):
                        st.session_state["comp_manual_land_area"] = 0.0
                        st.session_state["comp_manual_use_area"] = 35.0
                    elif any(kw in str(curr_type).lower() for kw in ['ที่ดิน', 'ที่ดินเปล่า']):
                        st.session_state["comp_manual_land_area"] = 100.0
                        st.session_state["comp_manual_use_area"] = 0.0
                    elif 'ทาวน์' in str(curr_type):
                        st.session_state["comp_manual_land_area"] = 20.0
                        st.session_state["comp_manual_use_area"] = 120.0
                    elif 'พาณิชย์' in str(curr_type) or 'ตึกแถว' in str(curr_type):
                        st.session_state["comp_manual_land_area"] = 20.0
                        st.session_state["comp_manual_use_area"] = 200.0
                    elif 'โรงงาน' in str(curr_type) or 'โกดัง' in str(curr_type):
                        st.session_state["comp_manual_land_area"] = 200.0
                        st.session_state["comp_manual_use_area"] = 500.0
                    elif 'สำนักงาน' in str(curr_type) or 'โฮมออฟฟิศ' in str(curr_type):
                        st.session_state["comp_manual_land_area"] = 30.0
                        st.session_state["comp_manual_use_area"] = 250.0
                    else:
                        st.session_state["comp_manual_land_area"] = 50.0
                        st.session_state["comp_manual_use_area"] = 150.0

                sanitize_session_state("comp_manual_type", prop_options, "บ้านเดี่ยว")
                inp_type = st.selectbox("ประเภททรัพย์ของจุดอ้างอิง", options=prop_options, key="comp_manual_type")

                c_m1, c_m2 = st.columns(2)
                with c_m1:
                    inp_lat = st.number_input("ละติจูด (Latitude)", value=def_manual_lat, format="%.6f", key="comp_manual_lat")
                    inp_lng = st.number_input("ลองจิจูด (Longitude)", value=def_manual_lng, format="%.6f", key="comp_manual_lng")
                    
                    if "comp_manual_price" not in st.session_state:
                        st.session_state["comp_manual_price"] = 5000000.0
                    
                    default_price_fmt = f"{float(st.session_state['comp_manual_price']):,.0f}"
                    raw_price_str = st.text_input(
                        "ราคาของจุดอ้างอิง (บาท)",
                        value=default_price_fmt,
                        key="comp_manual_price_txt",
                        help="สามารถกรอกราคา เช่น 5,000,000 หรือ 5000000"
                    )
                    try:
                        clean_p = re.sub(r'[^\d.]', '', raw_price_str)
                        inp_price = float(clean_p) if clean_p else 0.0
                    except Exception:
                        inp_price = 5000000.0
                    st.session_state["comp_manual_price"] = inp_price
                with c_m2:
                    is_condo_ref = any(kw in str(inp_type).lower() for kw in ['คอนโด', 'ห้องชุด', 'อพาร์ทเมนท์', 'แฟลต'])
                    is_land_ref = any(kw in str(inp_type).lower() for kw in ['ที่ดิน', 'ที่ดินเปล่า'])
                    default_land_w = 0.0 if is_condo_ref else (100.0 if is_land_ref else 50.0)
                    default_use_sqm = 0.0 if is_land_ref else (35.0 if is_condo_ref else 150.0)
                    
                    inp_land_area = st.number_input("เนื้อที่ของจุดอ้างอิง (ตารางวา)", min_value=0.0, value=default_land_w, step=5.0, format="%.1f", key="comp_manual_land_area", help="ระบุเนื้อที่ดิน (ตารางวา) หรือใส่ 0 หากไม่มี")
                    inp_use_area = st.number_input("พื้นที่ใช้สอยของจุดอ้างอิง (ตารางเมตร)", min_value=0.0, value=default_use_sqm, step=5.0, format="%.1f", key="comp_manual_use_area", help="ระบุพื้นที่ใช้สอยอาคาร (ตารางเมตร) หรือใส่ 0 หากไม่มี")

        with inp_col2:
            st.markdown("##### <i class='fa-solid fa-filter' style='color:#059669; margin-right:6px;'></i>ส่วนที่ 2: เงื่อนไขการค้นหา", unsafe_allow_html=True)
            search_radius = st.slider("รัศมีการค้นหา (กิโลเมตร)", min_value=0.5, max_value=10.0, value=5.0, step=0.5)

            # Company Filter for Comparison (Pills)
            PREFERRED_COMPANY_ORDER = ["LED", "SAM", "BAM", "Chayo555", "Chayo", "Chayo NPA", "GHB", "KBANK", "KTB", "SCB", "GSB", "DDproperty", "Livinginsider", "NaYoo", "ZmyHome", "Baania"]
            raw_comps = [str(c) for c in df_raw['บริษัท'].dropna().unique() if str(c).strip() not in ['', 'nan', 'None']] if df_raw is not None else PREFERRED_COMPANY_ORDER
            all_comp_list = sorted(
                raw_comps,
                key=lambda c: (PREFERRED_COMPANY_ORDER.index(c) if c in PREFERRED_COMPANY_ORDER else 999, c)
            )
            compare_companies = st.pills(
                "บริษัททรัพย์สิน (เปรียบเทียบ)",
                options=all_comp_list,
                selection_mode="multi",
                default=all_comp_list,
                key="comp_companies"
            )

            # Property Type Scope (3 clean options: Same type, Same + Land with building, All types)
            opt_same = f"ประเภทเดียวกัน ({inp_type})"
            opt_plus_land = f"{inp_type} + ที่ดินพร้อมสิ่งปลูกสร้าง" if inp_type != "ที่ดินพร้อมสิ่งปลูกสร้าง" else "ที่ดินพร้อมสิ่งปลูกสร้างหลัก"
            opt_all = "ทุกประเภท"
            type_scope_options = [opt_same, opt_plus_land, opt_all]

            # Auto reset default to same type if reference asset changed
            if "last_ref_type_choice" not in st.session_state or st.session_state["last_ref_type_choice"] != inp_type:
                st.session_state["last_ref_type_choice"] = inp_type
                st.session_state["prop_type_scope_sel"] = opt_same

            selected_type_scope = st.pills(
                "ขอบเขตประเภททรัพย์สิน (Property Type Matching)",
                options=type_scope_options,
                selection_mode="single",
                default=st.session_state.get("prop_type_scope_sel", opt_same),
                key="prop_type_scope_pills"
            )
            if selected_type_scope is None:
                selected_type_scope = opt_same
            st.session_state["prop_type_scope_sel"] = selected_type_scope

            # Use global min and max prices across all property groups as the absolute bounds and default
            if df_raw is not None and not df_raw.empty:
                all_prices = df_raw['ราคา'].dropna()
                all_prices = all_prices[all_prices > 0]
                min_price_val = float(all_prices.min()) if not all_prices.empty else 0.0
                max_price_val = float(all_prices.max()) if not all_prices.empty else 100000000.0
            else:
                min_price_val = 0.0
                max_price_val = 100000000.0

            if min_price_val >= max_price_val:
                max_price_val = min_price_val + 1000000.0

            # Step calculation based on price magnitude
            price_span = max_price_val - min_price_val
            if price_span > 1000000000:
                step_val = 10000000.0
            elif price_span > 100000000:
                step_val = 1000000.0
            elif price_span > 10000000:
                step_val = 100000.0
            elif price_span > 1000000:
                step_val = 50000.0
            else:
                step_val = 10000.0

            # Pre-validate session_state to prevent slider out-of-bound errors
            if "comp_price_slider" in st.session_state:
                curr_val = st.session_state["comp_price_slider"]
                if isinstance(curr_val, (list, tuple)) and len(curr_val) == 2:
                    c_low, c_high = curr_val
                    if c_low < min_price_val or c_high > max_price_val or c_low > c_high:
                        st.session_state["comp_price_slider"] = (min_price_val, max_price_val)

            compare_price_range = st.slider(
                "ช่วงราคาขาย (บาท) (เปรียบเทียบ)",
                min_value=min_price_val,
                max_value=max_price_val,
                value=(min_price_val, max_price_val),
                step=step_val,
                format="%,d",
                key="comp_price_slider"
            )
            st.caption(f"ราคาต่ำสุด: **฿{min_price_val:,.0f}** | สูงสุด: **฿{max_price_val:,.0f}** (ครอบคลุมทุกกลุ่มเป็นค่า Default)")

        # Clean Leaflet Coordinate Picker with Native Top-Right Layer Switcher
        if "ระบุพิกัดด้วยตัวเอง" in ref_method:
            st.markdown("<br/>", unsafe_allow_html=True)
            st.markdown("**คลิกหรือลากหมุดบนแผนที่ด้านล่าง (ปุ่มเปลี่ยนรูปแบบแผนที่อยู่มุมขวาบนของแผนที่เหมือนแผนที่หลัก):**")
            
            ref_pin_lat = float(st.session_state.get("comp_manual_lat", inp_lat if inp_lat != 0 else 13.7651))
            ref_pin_lng = float(st.session_state.get("comp_manual_lng", inp_lng if inp_lng != 0 else 100.5383))

            picker_leaflet_html = render_tab3_manual_leaflet_picker_html(ref_pin_lat, ref_pin_lng, is_dark_mode=is_dark_mode)
            st.components.v1.html(picker_leaflet_html, height=520, scrolling=False)

        st.markdown("<br/>", unsafe_allow_html=True)
        run_comp_btn = st.button("เริ่มเปรียบเทียบทำเล", icon=":material/radar:", type="primary", use_container_width=True, key="btn_run_comp_radius")

        if run_comp_btn or st.query_params.get("sel_map_lat") or st.query_params.get("sel_custom_codes"):
            st.session_state["has_run_comp"] = True

        # Only display comparison results if the user has clicked the button or navigated from map
        if st.session_state.get("has_run_comp", False):
            if inp_lat != 0.0 and inp_lng != 0.0:
                scope_choice = st.session_state.get("prop_type_scope_sel", opt_same)
                if "ทุกประเภท" in str(scope_choice):
                    m_type = None
                    badge_type_text = "ทุกประเภททรัพย์สิน"
                elif "+" in str(scope_choice) or "ที่ดินพร้อมสิ่งปลูกสร้าง" in str(scope_choice):
                    if inp_type == "ที่ดินพร้อมสิ่งปลูกสร้าง":
                        m_type = ["ที่ดินพร้อมสิ่งปลูกสร้าง", "บ้านเดี่ยว", "ทาวน์เฮ้าส์", "อาคารพาณิชย์", "บ้านแฝด", "วิลล่า", "โรงงาน/โกดัง"]
                    else:
                        m_type = [inp_type, "ที่ดินพร้อมสิ่งปลูกสร้าง"]
                    badge_type_text = f"{inp_type} + ที่ดินพร้อมสิ่งปลูกสร้าง"
                else:
                    m_type = [inp_type]
                    badge_type_text = f"เฉพาะ {inp_type}"

                nearby_df = find_nearby_properties(inp_lat, inp_lng, df_raw, search_radius, match_type=m_type)

                if not nearby_df.empty:
                    # Apply company filter
                    if compare_companies:
                        nearby_df = nearby_df[nearby_df['บริษัท'].isin(compare_companies)]

                    # Apply price range filter
                    if compare_price_range is not None and len(compare_price_range) == 2:
                        nearby_df = nearby_df[
                            (nearby_df['ราคา'].isna()) |
                            ((nearby_df['ราคา'] >= compare_price_range[0]) & (nearby_df['ราคา'] <= compare_price_range[1]))
                        ]

                if nearby_df.empty or 'ราคา' not in nearby_df.columns:
                    st.warning(f"ไม่พบทรัพย์สินตามเงื่อนไข ({badge_type_text}) ในรัศมี {search_radius:.1f} กิโลเมตร รอบจุดพิกัด ({inp_lat:.4f}, {inp_lng:.4f})")
                else:

                    st.markdown(f"""
                    <div style="
                        background: linear-gradient(135deg, #10b981 0%, #059669 100%);
                        color: #ffffff;
                        padding: 16px 24px;
                        border-radius: 14px;
                        box-shadow: 0 8px 24px rgba(16, 185, 129, 0.25);
                        margin: 15px 0 20px 0;
                        display: flex;
                        align-items: center;
                        justify-content: space-between;
                        flex-wrap: wrap;
                        gap: 10px;
                    ">
                        <div style="display: flex; align-items: center; gap: 14px;">
                            <span style="font-size: 1.6rem;"><i class="fa-solid fa-bullseye"></i></span>
                            <div>
                                <div style="font-size: 1.15rem; font-weight: 800; letter-spacing: 0.02em;">
                                    พบทรัพย์ NPA ทั้งหมด <span style="font-size: 1.45rem; text-decoration: underline; text-underline-offset: 4px; color: #fef08a;">{len(nearby_df):,}</span> รายการ ในรัศมี <span style="font-size: 1.35rem; color: #fef08a;">{search_radius:.1f}</span> กิโลเมตร!
                                </div>
                                <div style="font-size: 0.85rem; opacity: 0.95; margin-top: 3px;">
                                    <i class="fa-solid fa-location-dot" style="margin-right:4px;"></i><b>จุดอ้างอิง:</b> {inp_name} (พิกัด {inp_lat:.4f}, {inp_lng:.4f})
                                </div>
                            </div>
                        </div>
                        <div style="background: rgba(255,255,255,0.22); backdrop-filter: blur(8px); padding: 6px 16px; border-radius: 20px; font-weight: 700; font-size: 0.88rem; white-space: nowrap;">
                            <i class="fa-solid fa-house" style="margin-right:6px;"></i>{badge_type_text}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                    # ----------------- UNIT PRICE CALCULATIONS -----------------
                    def get_unit_info(r):
                        p_type = str(r.get('ประเภททรัพย์', '')).lower()
                        is_condo = any(kw in p_type for kw in ['คอนโด', 'ห้องชุด'])
                        price = r.get('ราคา')
                        if pd.isna(price) or float(price) <= 0:
                            return np.nan, "-", "-"
                            
                        if is_condo:
                            sqm = to_float_sqm(r.get('พื้นที่ใช้สอย (ตร.ม.)'))
                            if pd.notna(sqm) and float(sqm) > 0:
                                u_price = float(price) / float(sqm)
                                return u_price, "ตร.ม.", "พื้นที่ใช้สอย"
                        else:
                            sqwah = to_float_sqwah(r.get('เนื้อที่ (ตร.ว.)'))
                            if pd.isna(sqwah) or float(sqwah or 0) <= 0:
                                sqwah = to_float_sqwah(r.get('พื้นที่_ตารางวา'))
                            if pd.isna(sqwah) or float(sqwah or 0) <= 0:
                                sqwah = parse_land_sqwah(r)
                            if pd.notna(sqwah) and float(sqwah) > 0:
                                u_price = float(price) / float(sqwah)
                                return u_price, "ตร.ว.", "เนื้อที่"
                        return np.nan, "-", "-"

                    unit_results = nearby_df.apply(get_unit_info, axis=1)
                    nearby_df['ราคาต่อหน่วย'] = [res[0] for res in unit_results]
                    nearby_df['หน่วยวัด'] = [res[1] for res in unit_results]
                    nearby_df['ฐานพื้นที่คำนวณ'] = [res[2] for res in unit_results]

                    nearby_df['ราคาต่อหน่วย (แสดงผล)'] = nearby_df.apply(
                        lambda r: f"฿{r['ราคาต่อหน่วย']:,.0f} /{r['หน่วยวัด']} ({r['ฐานพื้นที่คำนวณ']})" if pd.notna(r['ราคาต่อหน่วย']) else "-", axis=1
                    )

                    # ----------------- PRICE & UNIT COMPARISON ANALYSIS -----------------
                    prices = nearby_df['ราคา'].dropna()
                    
                    if not prices.empty:
                        # 1. Selected Property Type Stats (เฉพาะประเภททรัพย์ที่เลือก)
                        sel_type_df = nearby_df[nearby_df['ประเภททรัพย์'] == inp_type]
                        has_sel_type = not sel_type_df.empty and sel_type_df['ราคา'].dropna().count() > 0

                        if has_sel_type:
                            st_prices = sel_type_df['ราคา'].dropna()
                            median_sel_type = float(st_prices.median())
                            count_sel_type = len(st_prices)
                            diff_st = median_sel_type - inp_price
                            pct_st = (diff_st / inp_price * 100) if inp_price > 0 else 0
                            if diff_st < 0:
                                sel_sub_html = f"<span style='color: #10b981; font-weight: 600;'><i class='fa fa-arrow-down'></i> ถูกกว่า {abs(pct_st):.1f}%</span> (ต่าง ฿{abs(diff_st):,.0f}) ({count_sel_type:,} รายการ)"
                            elif diff_st > 0:
                                sel_sub_html = f"<span style='color: #ef4444; font-weight: 600;'><i class='fa fa-arrow-up'></i> แพงกว่า {pct_st:.1f}%</span> (ต่าง ฿{abs(diff_st):,.0f}) ({count_sel_type:,} รายการ)"
                            else:
                                sel_sub_html = f"<span style='color: #64748b; font-weight: 600;'>ราคาเท่ากัน</span> ({count_sel_type:,} รายการ)"
                        else:
                            median_sel_type = 0.0
                            count_sel_type = 0
                            sel_sub_html = f"ไม่พบรายการประเภท {inp_type} ในพื้นที่"

                        # 2. Selected Property Type Unit Price Stats (ราคาต่อหน่วยของประเภททรัพย์ที่เลือก)
                        is_condo_ref = any(kw in str(inp_type).lower() for kw in ['คอนโด', 'ห้องชุด'])

                        if has_sel_type:
                            if is_condo_ref:
                                # For condo/apartment, strictly calculate price per Usable Area (บาท/ตร.ม.)
                                cond_sqm_df = sel_type_df.copy()
                                cond_sqm_df['calc_sqm'] = cond_sqm_df['พื้นที่ใช้สอย (ตร.ม.)'].apply(pd.to_numeric, errors='coerce')
                                valid_condo = cond_sqm_df[
                                    (cond_sqm_df['ราคา'] > 0) & 
                                    (cond_sqm_df['calc_sqm'].notna()) & 
                                    (cond_sqm_df['calc_sqm'] > 0)
                                ]
                                if not valid_condo.empty:
                                    u_sel = valid_condo['ราคา'] / valid_condo['calc_sqm']
                                    unit_lbl_sel = "ตร.ม."
                                    count_u_sel = len(u_sel)
                                    median_u_sel = float(u_sel.median())
                                    min_u_sel = float(u_sel.min())
                                    max_u_sel = float(u_sel.max())
                                    has_sel_u_stats = True
                                else:
                                    has_sel_u_stats = False
                            else:
                                u_sel = sel_type_df['ราคาต่อหน่วย'].dropna() if 'ราคาต่อหน่วย' in sel_type_df.columns else pd.Series()
                                if not u_sel.empty:
                                    median_u_sel = float(u_sel.median())
                                    min_u_sel = float(u_sel.min())
                                    max_u_sel = float(u_sel.max())
                                    unit_lbl_sel = sel_type_df[sel_type_df['หน่วยวัด'] != '-']['หน่วยวัด'].mode()[0] if not sel_type_df[sel_type_df['หน่วยวัด'] != '-'].empty else "ตร.ว."
                                    if unit_lbl_sel == "วา":
                                        unit_lbl_sel = "ตร.ว."
                                    count_u_sel = len(u_sel)
                                    has_sel_u_stats = True
                                else:
                                    has_sel_u_stats = False
                        else:
                            has_sel_u_stats = False

                        # Fallback for unit price if not enough specific property type unit stats
                        if not has_sel_u_stats:
                            all_u = nearby_df['ราคาต่อหน่วย'].dropna()
                            if not all_u.empty:
                                median_u_sel = float(all_u.median())
                                min_u_sel = float(all_u.min())
                                max_u_sel = float(all_u.max())
                                unit_lbl_sel = nearby_df[nearby_df['หน่วยวัด'] != '-']['หน่วยวัด'].mode()[0] if not nearby_df[nearby_df['หน่วยวัด'] != '-'].empty else "หน่วย"
                                if unit_lbl_sel == "วา":
                                    unit_lbl_sel = "ตร.ว."
                                count_u_sel = len(all_u)
                                has_sel_u_stats = True
                            else:
                                median_u_sel = min_u_sel = max_u_sel = 0.0
                                unit_lbl_sel = "หน่วย"
                                count_u_sel = 0

                        # 3. Raw Land Price per Sq.Wah Stats (ราคากลางที่ดินเปล่า บาท/วา - ดึงข้อมูลที่ดินเปล่าในรัศมีจากฐานข้อมูลทั้งหมด)
                        if m_type is None and 'nearby_df' in locals() and not nearby_df.empty:
                            all_radius_df = nearby_df
                        else:
                            all_radius_df = find_nearby_properties(inp_lat, inp_lng, df_raw, search_radius, match_type=None)
                        
                        p_str = all_radius_df['ประเภททรัพย์'].astype(str)
                        is_pure_land = p_str.str.contains('ที่ดินเปล่า|ที่ดิน', regex=True, na=False) & \
                                       ~p_str.str.contains('บ้าน|อาคาร|ทาวน์|คอนโด|ตึก|โรงงาน|พาณิชย์|หอพัก', regex=True, na=False)
                        raw_land_df = all_radius_df[is_pure_land & (all_radius_df['ราคา'] > 0)].copy()

                        if not raw_land_df.empty:
                            raw_land_df['sqwah'] = raw_land_df.apply(parse_land_sqwah, axis=1)
                            raw_land_df['u_price'] = np.where(
                                (raw_land_df['sqwah'].notna()) & (raw_land_df['sqwah'] > 0),
                                raw_land_df['ราคา'] / raw_land_df['sqwah'],
                                np.nan
                            )
                            rl_prices = raw_land_df['u_price'].dropna()
                            rl_prices = rl_prices[rl_prices > 0]
                            has_raw_land = not rl_prices.empty and len(rl_prices) > 0
                        else:
                            has_raw_land = False

                        if has_raw_land:
                            median_raw_land = float(rl_prices.median())
                            min_raw_land = float(rl_prices.min())
                            max_raw_land = float(rl_prices.max())
                            count_raw_land = len(rl_prices)
                        else:
                            median_raw_land = min_raw_land = max_raw_land = 0.0
                            count_raw_land = 0

                        st.markdown(f"#### <i class='fa-solid fa-chart-simple' style='color:#059669; margin-right:6px;'></i>ผลการวิเคราะห์ราคากลางต่อหน่วย (Median Analysis) เฉพาะประเภททรัพย์: **{inp_type}**", unsafe_allow_html=True)

                        is_land_type = any(kw in str(inp_type).lower() for kw in ['ที่ดิน', 'ที่ดินเปล่า'])

                        # Render 2 columns if property type is raw land (to prevent duplicate cards), else 3 columns
                        if is_land_type:
                            m_col1, m_col2 = st.columns(2)
                            m_col3 = None
                        else:
                            m_col1, m_col2, m_col3 = st.columns(3)

                        # Col 1: Reference Point Unit Price
                        is_condo_ref = any(kw in str(inp_type).lower() for kw in ['คอนโด', 'ห้องชุด'])
                        has_land = 'inp_land_area' in locals() and pd.notna(inp_land_area) and float(inp_land_area) > 0
                        has_sqm = 'inp_use_area' in locals() and pd.notna(inp_use_area) and float(inp_use_area) > 0

                        if is_condo_ref and has_sqm:
                            ref_u_p = inp_price / float(inp_use_area)
                            ref_val_html = f"฿{ref_u_p:,.0f} <span style='font-size:0.85rem; font-weight:normal; color:#475569;'>/ตร.ม.</span>"
                            ref_sub_html = f"""
                            <div style='margin-top: 6px; line-height: 1.55; font-size: 0.82rem; color: #475569;'>
                                <div><i class="fa-solid fa-wallet" style="color:#64748b; margin-right:4px;"></i><b>ราคารวม:</b> ฿{inp_price:,.0f}</div>
                                <div><i class="fa-solid fa-house" style="color:#64748b; margin-right:4px;"></i><b>ทรัพย์สิน:</b> {inp_type} ({float(inp_use_area):,.1f} ตร.ม.)</div>
                                <div style='color: #64748b; font-size: 0.76rem; margin-top: 2px;'><i class="fa-solid fa-ruler-combined" style="margin-right:3px;"></i>คำนวณจากพื้นที่ใช้สอย (ตารางเมตร)</div>
                            </div>
                            """
                        elif not is_condo_ref and has_land:
                            ref_u_p = inp_price / float(inp_land_area)
                            ref_val_html = f"฿{ref_u_p:,.0f} <span style='font-size:0.85rem; font-weight:normal; color:#475569;'>/ตร.ว.</span>"
                            sqm_sub = f" | ใช้สอย {float(inp_use_area):,.1f} ตร.ม." if has_sqm else ""
                            ref_sub_html = f"""
                            <div style='margin-top: 6px; line-height: 1.55; font-size: 0.82rem; color: #475569;'>
                                <div><i class="fa-solid fa-wallet" style="color:#64748b; margin-right:4px;"></i><b>ราคารวม:</b> ฿{inp_price:,.0f}</div>
                                <div><i class="fa-solid fa-house" style="color:#64748b; margin-right:4px;"></i><b>ทรัพย์สิน:</b> {inp_type} ({float(inp_land_area):,.1f} ตร.ว{sqm_sub})</div>
                                <div style='color: #64748b; font-size: 0.76rem; margin-top: 2px;'><i class="fa-solid fa-ruler-combined" style="margin-right:3px;"></i>คำนวณจากเนื้อที่ (ตารางวา)</div>
                            </div>
                            """
                        elif has_sqm:
                            ref_u_p = inp_price / float(inp_use_area)
                            ref_val_html = f"฿{ref_u_p:,.0f} <span style='font-size:0.85rem; font-weight:normal; color:#475569;'>/ตร.ม.</span>"
                            ref_sub_html = f"""
                            <div style='margin-top: 6px; line-height: 1.55; font-size: 0.82rem; color: #475569;'>
                                <div><i class="fa-solid fa-wallet" style="color:#64748b; margin-right:4px;"></i><b>ราคารวม:</b> ฿{inp_price:,.0f}</div>
                                <div><i class="fa-solid fa-house" style="color:#64748b; margin-right:4px;"></i><b>ทรัพย์สิน:</b> {inp_type} (พื้นที่ใช้สอย {float(inp_use_area):,.1f} ตร.ม.)</div>
                                <div style='color: #64748b; font-size: 0.76rem; margin-top: 2px;'><i class="fa-solid fa-ruler-combined" style="margin-right:3px;"></i>คำนวณจากพื้นที่ใช้สอย (ตารางเมตร)</div>
                            </div>
                            """
                        else:
                            ref_val_html = f"฿{inp_price:,.0f}"
                            ref_sub_html = f"""
                            <div style='margin-top: 6px; line-height: 1.55; font-size: 0.82rem; color: #475569;'>
                                <div><i class="fa-solid fa-house" style="color:#64748b; margin-right:4px;"></i><b>ทรัพย์สิน:</b> {inp_type}</div>
                                <div style='color: #94a3b8; font-size: 0.76rem;'>ไม่ระบุขนาดพื้นที่</div>
                            </div>
                            """

                        ref_html = f"""
                        <div class="metric-card">
                            <div class="metric-title"><i class="fa-solid fa-location-crosshairs" style="color: #ef4444; margin-right:4px;"></i> พิกัดอ้างอิงของคุณ</div>
                            <div class="metric-value">{ref_val_html}</div>
                            <div class="metric-sub">{ref_sub_html}</div>
                        </div>
                        """
                        m_col1.markdown(ref_html, unsafe_allow_html=True)

                        # Col 2: Selected Property Type Unit Price (Median)
                        if has_sel_u_stats:
                            area_source_label = "คำนวณจากพื้นที่ใช้สอย (ตารางเมตร)" if (is_condo_ref or "ตร.ม." in str(unit_lbl_sel)) else "คำนวณจากเนื้อที่ (ตารางวา)"
                            unit_val_html = f"฿{median_u_sel:,.0f} <span style='font-size:0.85rem; font-weight:normal; color:#475569;'>/{unit_lbl_sel}</span>"
                            unit_sub_html = f"""
                            <div style='margin-top: 6px; line-height: 1.55; font-size: 0.82rem; color: #334155;'>
                                <div><i class="fa-solid fa-chart-simple" style="color:#64748b; margin-right:4px;"></i><b>ช่วงราคา:</b> ฿{min_u_sel:,.0f} - ฿{max_u_sel:,.0f} /{unit_lbl_sel}</div>
                                <div><i class="fa-solid fa-boxes-stacked" style="color:#64748b; margin-right:4px;"></i><b>จำนวน:</b> {count_u_sel:,} รายการในรัศมี {search_radius:.1f} กม.</div>
                                <div style='color: #64748b; font-size: 0.76rem; margin-top: 2px;'><i class="fa-solid fa-ruler-combined" style="margin-right:3px;"></i>{area_source_label}</div>
                            </div>
                            """
                        else:
                            unit_val_html = "ไม่มีข้อมูล"
                            unit_sub_html = f"<div style='color: #94a3b8; font-size: 0.8rem; margin-top: 6px;'>ไม่พบข้อมูลพื้นที่ของ {inp_type} ในรัศมี {search_radius:.1f} กม.</div>"

                        unit_html = f"""
                        <div class="metric-card" style="background: rgba(59, 130, 246, 0.04); border: 1px solid rgba(59, 130, 246, 0.2);">
                            <div class="metric-title"><i class="fa-solid fa-tag" style="color: #10b981; margin-right:4px;"></i> ราคากลางต่อหน่วย (Median ในรัศมี {search_radius:.1f} กม.) - {inp_type}</div>
                            <div class="metric-value" style="color: #059669;">{unit_val_html}</div>
                            <div class="metric-sub">{unit_sub_html}</div>
                        </div>
                        """
                        m_col2.markdown(unit_html, unsafe_allow_html=True)

                        # Col 3: Raw Land Price per Sq.Wah (Median)
                        if has_raw_land:
                            rl_val_html = f"฿{median_raw_land:,.0f} <span style='font-size:0.85rem; font-weight:normal; color:#475569;'>/ตร.ว.</span>"
                            rl_sub_html = f"""
                            <div style='margin-top: 6px; line-height: 1.55; font-size: 0.82rem; color: #334155;'>
                                <div><i class="fa-solid fa-chart-simple" style="color:#64748b; margin-right:4px;"></i><b>ช่วงราคา:</b> ฿{min_raw_land:,.0f} - ฿{max_raw_land:,.0f} /ตร.ว.</div>
                                <div><i class="fa-solid fa-boxes-stacked" style="color:#64748b; margin-right:4px;"></i><b>จำนวน:</b> {count_raw_land:,} รายการในรัศมี {search_radius:.1f} กม.</div>
                                <div style='color: #64748b; font-size: 0.76rem; margin-top: 2px;'><i class="fa-solid fa-ruler-combined" style="margin-right:3px;"></i>คำนวณจากเนื้อที่ (ตารางวา)</div>
                            </div>
                            """
                        else:
                            rl_val_html = "ไม่มีข้อมูล"
                            rl_sub_html = f"<div style='color: #94a3b8; font-size: 0.8rem; margin-top: 6px;'>ไม่พบรายการที่ดินเปล่าในรัศมี {search_radius:.1f} กม.</div>"

                        rl_html = f"""
                        <div class="metric-card" style="background: rgba(16, 185, 129, 0.04); border: 1px solid rgba(16, 185, 129, 0.2);">
                            <div class="metric-title"><i class="fa-solid fa-tree" style="color: #10b981; margin-right:4px;"></i> ราคากลางที่ดินเปล่า (Median ในรัศมี {search_radius:.1f} กม.)</div>
                            <div class="metric-value" style="color: #059669;">{rl_val_html}</div>
                            <div class="metric-sub">{rl_sub_html}</div>
                        </div>
                        """
                        if m_col3 is not None:
                            m_col3.markdown(rl_html, unsafe_allow_html=True)

                    # Prepare map data
                    total_found = len(nearby_df)
                    map_nearby_df = nearby_df[
                        nearby_df['ละติจูด'].notna() & 
                        nearby_df['ลองจิจูด'].notna() & 
                        (nearby_df['ละติจูด'] != 0) & 
                        (nearby_df['ลองจิจูด'] != 0)
                    ].sort_values("ระยะทาง (กม.)").reset_index(drop=True)

                    valid_geo_count = len(map_nearby_df)
                    unique_geo_count = len(map_nearby_df.drop_duplicates(subset=['ละติจูด', 'ลองจิจูด'])) if not map_nearby_df.empty else 0
                    dup_geo_count = valid_geo_count - unique_geo_count
                    missing_geo_count = total_found - valid_geo_count
                    pct_geo = (valid_geo_count / total_found * 100) if total_found > 0 else 0.0
                    pct_missing = 100.0 - pct_geo
                    st.markdown("##### <i class='fa-solid fa-map-location-dot' style='color:#059669; margin-right:6px;'></i>แผนที่ตำแหน่งจุดอ้างอิงเทียบกับตำแหน่งทรัพย์ NPA ที่พบ (คลิกที่หมุดเพื่อดูเฉพาะทรัพย์สินนั้นในตาราง)", unsafe_allow_html=True)
                    
                    geo_info_msg = f"<i class='fa-solid fa-location-dot' style='color:#ef4444; margin-right:3px;'></i><b>มีพิกัดปักหมุดบนแผนที่ได้:</b> <b>{valid_geo_count:,}</b> รายการ (คิดเป็น <b>{pct_geo:.1f}%</b>)"
                    if dup_geo_count > 0:
                        geo_info_msg += f" | <i class='fa-solid fa-building' style='color:#64748b; margin-right:3px;'></i><b>พิกัดซ้ำกัน (เช่น คอนโด/โครงการเดียวกัน):</b> <b>{dup_geo_count:,}</b> รายการ (ปักรวม <b>{unique_geo_count:,}</b> ตำแหน่งหมุดบนแผนที่)"
                    if missing_geo_count > 0:
                        geo_info_msg += f" | <i class='fa-solid fa-triangle-exclamation' style='color:#f59e0b; margin-right:3px;'></i><b>ไม่มีข้อมูลพิกัดในระบบ:</b> <b>{missing_geo_count:,}</b> รายการ ({pct_missing:.1f}% - แสดงเฉพาะในตารางข้อมูล)"
                    
                    st.caption(f"{geo_info_msg} จากทรัพย์ NPA ทั้งหมด {total_found:,} รายการที่พบในทำเล", unsafe_allow_html=True)

                    # 1. Render Interactive Leaflet Radius Map with Company Logo Badges & Comprehensive Metadata
                    # Calculate true comprehensive legend statistics over all found items
                    legend_stats_dict = {}
                    if "ประเภททรัพย์" in str(color_by if 'color_by' in locals() else ""):
                        legend_stats_dict = map_nearby_df['ประเภททรัพย์'].fillna('อื่นๆ').value_counts().to_dict()
                    elif "ราคา" in str(color_by if 'color_by' in locals() else ""):
                        def get_price_tier(p_num):
                            if pd.isna(p_num) or p_num <= 0: return "< 1M"
                            if p_num < 1000000: return "< 1M"
                            if p_num < 3000000: return "1M - 3M"
                            if p_num < 5000000: return "3M - 5M"
                            if p_num < 10000000: return "5M - 10M"
                            if p_num < 20000000: return "10M - 20M"
                            return "> 20M"
                        p_series = pd.to_numeric(map_nearby_df['ราคา'], errors='coerce')
                        legend_stats_dict = p_series.apply(get_price_tier).value_counts().to_dict()
                    else:
                        legend_stats_dict = map_nearby_df['บริษัท'].fillna('อื่นๆ').value_counts().to_dict()

                    # Group properties by rounded coordinate so EVERY location in the radius is pinned!
                    coord_grouped = {}
                    for r in map_nearby_df.to_dict('records'):
                        lat_val = r.get('ละติจูด')
                        lon_val = r.get('ลองจิจูด')
                        if pd.notna(lat_val) and pd.notna(lon_val):
                            try:
                                lat_f = round(float(lat_val), 5)
                                lon_f = round(float(lon_val), 5)
                                key = (lat_f, lon_f)
                                if key not in coord_grouped:
                                    coord_grouped[key] = []
                                coord_grouped[key].append(r)
                            except (ValueError, TypeError):
                                pass

                    nearby_list_for_map = []
                    MAX_UNIQUE_COORDS = 1200
                    MAX_UNITS_PER_COORD = 10
                    MAX_TOTAL_MAP_ITEMS = 4000

                    def _get_coord_sort_key(item):
                        p = item.get('ราคา')
                        price_val = float(p) if pd.notna(p) and float(p) > 0 else float('inf')
                        
                        # Unit price: ฿/ตร.ว. หรือ ฿/ตร.ม.
                        p_wah = item.get('ราคาต่อตารางวา')
                        p_sqm = item.get('ราคาต่อตารางเมตร')
                        if (pd.isna(p_wah) or float(p_wah) <= 0) and price_val < float('inf'):
                            land_w = to_float_sqwah(item.get('เนื้อที่ (ตร.ว.)'))
                            if pd.isna(land_w) or land_w <= 0:
                                land_w = to_float_sqwah(item.get('พื้นที่_ตารางวา'))
                            if pd.notna(land_w) and land_w > 0:
                                p_wah = price_val / land_w
                        if (pd.isna(p_sqm) or float(p_sqm) <= 0) and price_val < float('inf'):
                            sqm_a = to_float_sqm(item.get('พื้นที่ใช้สอย (ตร.ม.)'))
                            if pd.notna(sqm_a) and sqm_a > 0:
                                p_sqm = price_val / sqm_a
                        
                        pw_ok = pd.notna(p_wah) and float(p_wah) > 0
                        pm_ok = pd.notna(p_sqm) and float(p_sqm) > 0
                        ptype = str(item.get('ประเภททรัพย์', ''))
                        if any(k in ptype for k in ['ห้องชุด', 'คอนโด', 'อาคารชุด']):
                            if pm_ok: unit_val = float(p_sqm)
                            elif pw_ok: unit_val = float(p_wah)
                            else: unit_val = float('inf')
                        else:
                            if pw_ok: unit_val = float(p_wah)
                            elif pm_ok: unit_val = float(p_sqm)
                            else: unit_val = float('inf')
                            
                        return (price_val, unit_val)

                    unique_coords_count = 0
                    for (lat_f, lon_f), group_rows in coord_grouped.items():
                        unique_coords_count += 1
                        if unique_coords_count > MAX_UNIQUE_COORDS:
                            break
                        
                        # Sort properties at same coordinate: lowest offering price, then lowest unit price first (น้อยไปมาก)
                        group_rows.sort(key=_get_coord_sort_key)

                        total_in_this_coord = len(group_rows)
                        for r in group_rows[:MAX_UNITS_PER_COORD]:
                            if len(nearby_list_for_map) >= MAX_TOTAL_MAP_ITEMS:
                                break
                            sort_p, sort_u = _get_coord_sort_key(r)
                            formatted_price = f"฿{r['ราคา']:,.0f}" if pd.notna(r.get('ราคา')) else "ไม่ระบุ"
                            asset_code = str(r.get('รหัสทรัพย์', '-'))
                            dist_km_val = f"{r['ระยะทาง (กม.)']:.2f} กม." if pd.notna(r.get('ระยะทาง (กม.)')) else "-"
                            prop_type_val = str(r.get('ประเภททรัพย์', '-'))
                            company_name_val = str(r.get('บริษัท', '-'))
                            project_val = str(r.get('ชื่อโครงการ', ''))
                            sale_type_val = str(r.get('ประเภทการขาย', 'ขาย'))
                            
                            # Areas
                            land_sqwah = to_float_sqwah(r.get('เนื้อที่ (ตร.ว.)'))
                            if pd.isna(land_sqwah) or land_sqwah <= 0:
                                land_sqwah = to_float_sqwah(r.get('พื้นที่_ตารางวา'))
                                
                            land_area_val = format_to_rai_ngan_wah(r.get('เนื้อที่ (ตร.ว.)'))
                            if land_area_val == '-':
                                land_area_val = format_to_rai_ngan_wah(land_sqwah)
                            if land_area_val != '-' and pd.notna(land_sqwah) and land_sqwah > 0:
                                land_area_val += f" ({land_sqwah:,.1f} ตร.ว.)"
                            
                            sqm_val = to_float_sqm(r.get('พื้นที่ใช้สอย (ตร.ม.)'))
                            usable_area_val = f"{sqm_val:,.1f} ตร.ม." if pd.notna(sqm_val) and sqm_val > 0 else "-"
                            
                            price_num = pd.to_numeric(r.get('ราคา'), errors='coerce')
                            price_per_wah_str = f"฿{price_num/land_sqwah:,.0f}/ตร.ว." if (pd.notna(price_num) and pd.notna(land_sqwah) and land_sqwah > 0 and price_num > 0) else ""
                            price_per_sqm_str = f"฿{price_num/sqm_val:,.0f}/ตร.ม." if (pd.notna(price_num) and pd.notna(sqm_val) and sqm_val > 0 and price_num > 0) else ""
                            u_price_val = str(r.get('ราคาต่อหน่วย (แสดงผล)', '-'))
                            
                            link_val = str(r.get('ลิงก์', ''))
                            subdist_val = str(r.get('ตำบล', ''))
                            dist_name_val = str(r.get('อำเภอ', ''))
                            prov_val = str(r.get('จังหวัด', ''))
                            gps_str = f"{lat_f:.5f}, {lon_f:.5f}"
                            
                            nearby_list_for_map.append({
                                "lat": lat_f,
                                "lon": lon_f,
                                "name": str(r.get('ชื่อประกาศ', 'ทรัพย์สิน NPA')),
                                "project": project_val,
                                "code": asset_code,
                                "price": formatted_price,
                                "raw_price": sort_p if sort_p != float('inf') else 0,
                                "raw_unit_price": sort_u if sort_u != float('inf') else 0,
                                "type": prop_type_val,
                                "sale_type": sale_type_val,
                                "dist": dist_km_val,
                                "company": company_name_val,
                                "land_area": land_area_val,
                                "usable_area": usable_area_val,
                                "price_per_wah": price_per_wah_str,
                                "price_per_sqm": price_per_sqm_str,
                                "unit_price": u_price_val,
                                "link": link_val,
                                "subdist": subdist_val,
                                "district": dist_name_val,
                                "province": prov_val,
                                "gps": gps_str,
                                "coord_total": total_in_this_coord,
                                "is_centroid": is_true_centroid(r.get('is_centroid'), company_name_val)
                            })
                    
                    leaflet_html = render_tab3_radius_leaflet_map_html(
                        float(inp_lat), float(inp_lng), float(search_radius), nearby_list_for_map, 
                        is_dark_mode=is_dark_mode,
                        color_mode=color_by if 'color_by' in locals() else "จำแนกตามบริษัท (By Company)",
                        tile_style=map_tile_style if 'map_tile_style' in locals() else "มาตรฐาน (Street Map)",
                        legend_stats_dict=legend_stats_dict
                    )
                    st.components.v1.html(leaflet_html, height=1100, scrolling=False)
                    if len(coord_grouped) > MAX_UNIQUE_COORDS:
                        st.caption(f"*แผนที่แสดงหมุดทรัพย์สินครอบคลุม {MAX_UNIQUE_COORDS:,} ตำแหน่งพิกัดทั่วรัศมีค้นหา (ตารางด้านล่างแสดงครบทั้งหมด {len(nearby_df):,} รายการ)*")

                    # State & Query Parameters Management for Tab 3


                    # -------------------------------------------------------------
                    # State & Query Parameters Management for Tab 3
                    # -------------------------------------------------------------
                    if "tab3_custom_selected_codes" not in st.session_state:
                        st.session_state.tab3_custom_selected_codes = set()
                    if "tab3_active_coord_filter" not in st.session_state:
                        st.session_state.tab3_active_coord_filter = None

                    # Read incoming query params — updated by NPA Bridge JS via history.pushState + popstate
                    q_lat = st.query_params.get("sel_map_lat")
                    q_lon = st.query_params.get("sel_map_lon")
                    q_custom_codes = st.query_params.get("sel_custom_codes")

                    if q_custom_codes:
                        for c in q_custom_codes.split(","):
                            c_clean = str(c).strip()
                            if c_clean and c_clean != "-" and c_clean != "None":
                                st.session_state.tab3_custom_selected_codes.add(c_clean)

                    if q_lat and q_lon:
                        try:
                            st.session_state.tab3_active_coord_filter = f"{float(q_lat):.5f},{float(q_lon):.5f}"
                            st.session_state["has_run_comp"] = True
                        except Exception:
                            pass


                    # Format full display dataframe
                    nearby_show = nearby_df.sort_values("ระยะทาง (กม.)").copy()
                    if 'ราคา' in nearby_show.columns:
                        nearby_show['ราคาขาย (บาท)'] = pd.to_numeric(nearby_show['ราคา'], errors='coerce')
                    
                    # Calculate square wah numeric for division
                    sqwah_col = nearby_show['เนื้อที่ (ตร.ว.)'].apply(to_float_sqwah) if 'เนื้อที่ (ตร.ว.)' in nearby_show.columns else pd.Series(np.nan, index=nearby_show.index)
                    if 'พื้นที่_ตารางวา' in nearby_show.columns:
                        sqwah_col = sqwah_col.fillna(nearby_show['พื้นที่_ตารางวา'].apply(to_float_sqwah))
                    nearby_show['sqwah_calc'] = sqwah_col
                    
                    # Display format as ไร่-งาน-ตร.ว.
                    nearby_show['เนื้อที่ (ไร่-งาน-ตร.ว.)'] = nearby_show['เนื้อที่ (ตร.ว.)'].apply(format_to_rai_ngan_wah) if 'เนื้อที่ (ตร.ว.)' in nearby_show.columns else nearby_show['sqwah_calc'].apply(format_to_rai_ngan_wah)

                    if 'พื้นที่ใช้สอย (ตร.ม.)' in nearby_show.columns:
                        nearby_show['พื้นที่ใช้สอย (ตร.ม.)'] = nearby_show['พื้นที่ใช้สอย (ตร.ม.)'].apply(to_float_sqm)

                    # 1. ราคา/ตร.ว. (บาท) = ราคาขาย / sqwah_calc
                    nearby_show['ราคา/ตร.ว. (บาท)'] = nearby_show.apply(
                        lambda r: round(r['ราคาขาย (บาท)'] / r['sqwah_calc']) if (pd.notna(r.get('ราคาขาย (บาท)')) and pd.notna(r.get('sqwah_calc')) and float(r.get('sqwah_calc', 0)) > 0 and float(r.get('ราคาขาย (บาท)', 0)) > 0) else np.nan,
                        axis=1
                    )
                    
                    # 2. ราคา/ตร.ม. (บาท) = ราคาขาย / พื้นที่ใช้สอย (ตร.ม.)
                    nearby_show['ราคา/ตร.ม. (บาท)'] = nearby_show.apply(
                        lambda r: round(r['ราคาขาย (บาท)'] / r['พื้นที่ใช้สอย (ตร.ม.)']) if (pd.notna(r.get('ราคาขาย (บาท)')) and pd.notna(r.get('พื้นที่ใช้สอย (ตร.ม.)')) and float(r.get('พื้นที่ใช้สอย (ตร.ม.)', 0)) > 0 and float(r.get('ราคาขาย (บาท)', 0)) > 0) else np.nan,
                        axis=1
                    )

                    # Group coordinates to identify duplicate points (> 1 items)
                    nearby_show['coord_key'] = nearby_show.apply(
                        lambda r: f"{float(r['ละติจูด']):.5f},{float(r['ลองจิจูด']):.5f}" if pd.notna(r.get('ละติจูด')) and pd.notna(r.get('ลองจิจูด')) else None,
                        axis=1
                    )
                    nearby_show = nearby_show.sort_values(
                        by=['ระยะทาง (กม.)', 'coord_key', 'ราคาขาย (บาท)', 'ราคา/ตร.ว. (บาท)', 'ราคา/ตร.ม. (บาท)'],
                        ascending=[True, True, True, True, True],
                        na_position='last'
                    )
                    coord_counts = nearby_show['coord_key'].value_counts()
                    multi_coord_keys = coord_counts[coord_counts > 1].index.tolist()

                    nearby_show['รูปแปลงที่ดิน'] = nearby_show['บริษัท'].apply(
                        lambda c: "https://landsmaps.dol.go.th/" if str(c).strip().upper() == "LED" else None
                    )
                    nearby_show['ความแม่นยำพิกัด'] = nearby_show.apply(
                        lambda r: "⚠️ กึ่งกลางตำบล" if is_true_centroid(r.get('is_centroid'), r.get('บริษัท')) else "📍 แปลงจริง",
                        axis=1
                    )

                    # Standard Column Ordering
                    cols_nearby_order = [
                        "บริษัท", "รหัสทรัพย์", "ชื่อโครงการ", "ประเภททรัพย์", "ประเภทการขาย", "ราคาขาย (บาท)",
                        "ตำบล", "อำเภอ", "จังหวัด", "ระยะทาง (กม.)", "ลิงก์", "รูปแปลงที่ดิน", "ความแม่นยำพิกัด",
                        "เนื้อที่ (ไร่-งาน-ตร.ว.)", "ราคา/ตร.ว. (บาท)", "พื้นที่ใช้สอย (ตร.ม.)", "ราคา/ตร.ม. (บาท)", "วันที่ดึงข้อมูล",
                        "ห้องนอน", "ห้องน้ำ", "ที่จอดรถ", "ชั้น", "วันประกาศ", "coord_key"
                    ]
                    cols_present = [c for c in cols_nearby_order if c in nearby_show.columns]
                    cols_display = [c for c in cols_present if c != "coord_key"]

                    df_col_config = {
                        "ราคาขาย (บาท)": st.column_config.NumberColumn("ราคาขาย (บาท)", format="฿%,d"),
                        "เนื้อที่ (ไร่-งาน-ตร.ว.)": st.column_config.TextColumn("เนื้อที่ (ไร่-งาน-ตร.ว.)"),
                        "ราคา/ตร.ว. (บาท)": st.column_config.NumberColumn("ราคา/ตร.ว. (บาท)", format="฿%,d"),
                        "พื้นที่ใช้สอย (ตร.ม.)": st.column_config.NumberColumn("พื้นที่ใช้สอย (ตร.ม.)", format="%.1f"),
                        "ราคา/ตร.ม. (บาท)": st.column_config.NumberColumn("ราคา/ตร.ม. (บาท)", format="฿%,d"),
                        "ระยะทาง (กม.)": st.column_config.NumberColumn("ระยะทาง (กม.)", format="%.2f กม."),
                        "ชั้น": st.column_config.TextColumn("ชั้น", help="ชั้นที่ตั้งของทรัพย์สิน หรือจำนวนชั้นของอาคาร"),
                        "ลิงก์": st.column_config.LinkColumn("ลิงก์ประกาศ", display_text="เปิดดูทรัพย์"),
                        "รูปแปลงที่ดิน": st.column_config.LinkColumn("รูปแปลงที่ดิน (LED)", display_text="LandsMaps", help="คลิกเพื่อเปิดระบบค้นหารูปแปลงที่ดิน กรมที่ดิน (เฉพาะกรมบังคับคดี)"),
                        "ความแม่นยำพิกัด": st.column_config.TextColumn("ความแม่นยำพิกัด", help="ระบุว่าเป็นพิกัดแปลงจริงจากประกาศ หรือพิกัดจุดกึ่งกลางตำบล/อำเภอ")
                    }

                    # -------------------------------------------------------------
                    # Tab 3 Structured View: 3 Clean Dedicated Sub-Tabs
                    # -------------------------------------------------------------
                    st.markdown("---")

                    st.markdown("""
                    <style>
                    /* Custom Dedicated Font Awesome Icons for Tab 3 Sub-tabs (No Emojis) */
                    .st-key-tab3_sub_tables_container [role="tab"]:nth-child(1) p::before,
                    .st-key-tab3_sub_tables_container div[role="tablist"] > div:nth-child(1) p::before {
                        font-family: "Font Awesome 6 Free", "FontAwesome" !important;
                        font-weight: 900 !important;
                        content: "\\f03a\\a0" !important; /* fa-list */
                        color: #475569 !important;
                        -webkit-text-fill-color: #475569 !important;
                        display: inline-block !important;
                        margin-right: 4px !important;
                    }
                    .st-key-tab3_sub_tables_container [role="tab"]:nth-child(2) p::before,
                    .st-key-tab3_sub_tables_container div[role="tablist"] > div:nth-child(2) p::before {
                        font-family: "Font Awesome 6 Free", "FontAwesome" !important;
                        font-weight: 900 !important;
                        content: "\\f3c5\\a0" !important; /* fa-location-dot */
                        color: #0284c7 !important;
                        -webkit-text-fill-color: #0284c7 !important;
                        display: inline-block !important;
                        margin-right: 4px !important;
                    }
                    .st-key-tab3_sub_tables_container [role="tab"]:nth-child(3) p::before,
                    .st-key-tab3_sub_tables_container div[role="tablist"] > div:nth-child(3) p::before {
                        font-family: "Font Awesome 6 Free", "FontAwesome" !important;
                        font-weight: 900 !important;
                        content: "\\f005\\a0" !important; /* fa-star */
                        color: #059669 !important;
                        -webkit-text-fill-color: #059669 !important;
                        display: inline-block !important;
                        margin-right: 4px !important;
                    }
                    </style>
                    """, unsafe_allow_html=True)

                    # Synchronize and pre-filter custom comps matching current search radius
                    chosen_codes = st.session_state.get("tab3_custom_selected_codes", set())
                    if chosen_codes and not nearby_show.empty:
                        custom_df = nearby_show[
                            nearby_show['รหัสทรัพย์'].astype(str).str.strip().isin(chosen_codes) |
                            (nearby_show['ID'].astype(str).str.strip().isin(chosen_codes) if 'ID' in nearby_show.columns else False)
                        ].copy()
                        cnt_custom = len(custom_df)
                        # Synchronize session state to only retain active matching codes
                        valid_active_codes = set(custom_df['รหัสทรัพย์'].dropna().astype(str).str.strip().tolist())
                        if 'ID' in custom_df.columns:
                            valid_active_codes.update(custom_df['ID'].dropna().astype(str).str.strip().tolist())
                        st.session_state.tab3_custom_selected_codes = chosen_codes.intersection(valid_active_codes)
                    else:
                        custom_df = pd.DataFrame()
                        cnt_custom = 0

                    badge_custom = f" ({cnt_custom:,} รายการ)" if cnt_custom > 0 else ""
                    tab_comp_title = f"วิเคราะห์เปรียบเทียบเฉพาะที่เลือก{badge_custom}"

                    active_k = st.session_state.tab3_active_coord_filter
                    badge_coord = ""
                    if active_k:
                        sub_cnt_c = len(nearby_show[nearby_show['coord_key'] == active_k])
                        badge_coord = f" ({sub_cnt_c:,} รายการ)"
                    tab_coord_title = f"เจาะลึกตามพิกัด{badge_coord}"

                    tab_all_title = f"รายการทั้งหมดในรัศมี ({len(nearby_df):,} รายการ)"

                    with st.container(key="tab3_sub_tables_container"):
                        sub_view_tab1, sub_view_tab2, sub_view_tab3 = st.tabs([
                            tab_all_title,
                            tab_coord_title,
                            tab_comp_title
                        ])

                        # =============================================================
                        # SUB-TAB 1: รายการทรัพย์สิน NPA ทั้งหมดในรัศมี (เดิม SUB-TAB 3)
                        # =============================================================
                        with sub_view_tab1:
                            st.markdown(f"##### <i class='fa-solid fa-table-list' style='color:#059669; margin-right:6px;'></i>รายการทรัพย์สิน NPA ที่พบในรัศมีค้นหาทั้งหมด {len(nearby_df):,} รายการ (พร้อมราคาต่อตารางวา / ตารางเมตร)", unsafe_allow_html=True)
                            
                            col_tb_info1, col_tb_info2 = st.columns([3, 1])
                            with col_tb_info1:
                                st.caption("*ท่านสามารถติ๊กเลือกช่องหน้ารายการ (Checkbox) เพื่อนำไปวิเคราะห์ในตารางเปรียบเทียบเฉพาะที่เลือกได้*")
                            with col_tb_info2:
                                if cnt_custom > 0:
                                    st.markdown(f"<div style='text-align:right; font-size:12.5px; color:#059669; font-weight:700; padding-top:4px;'><i class='fa-solid fa-check-double' style='margin-right:4px;'></i>เลือกแล้ว {cnt_custom:,} รายการ</div>", unsafe_allow_html=True)

                            # Support multi-row selection from dataframe
                            table_selection = st.dataframe(
                                nearby_show[cols_display],
                                width="stretch",
                                column_config=df_col_config,
                                on_select="rerun",
                                selection_mode="multi-row",
                                key="tab3_main_nearby_table"
                            )

                            if table_selection and hasattr(table_selection, "selection") and table_selection.selection and getattr(table_selection.selection, "rows", None):
                                raw_rows = table_selection.selection.rows
                                selected_row_indices = [int(r) for r in raw_rows if r is not None and (isinstance(r, (int, np.integer)) or (isinstance(r, str) and r.isdigit()))]
                                if len(selected_row_indices) > 0:
                                    if st.button(f"➕ เพิ่ม {len(selected_row_indices)} รายการที่ติ๊กเลือก ลงในตารางเปรียบเทียบเฉพาะที่เลือก", icon=":material/add:", key="btn_add_selected_rows_tab3", type="primary"):
                                        for idx_r in selected_row_indices:
                                            if idx_r < len(nearby_show):
                                                row_val = nearby_show.iloc[idx_r]
                                                c_code = str(row_val.get('รหัสทรัพย์', '')).strip() or str(row_val.get('ID', '')).strip()
                                                if c_code and c_code != '-' and c_code != 'None':
                                                    st.session_state.tab3_custom_selected_codes.add(c_code)
                                        st.success(f"เพิ่ม {len(selected_row_indices)} รายการลงในตารางเปรียบเทียบเรียบร้อยแล้ว!")
                                        st.rerun()

                            render_import_export_section(nearby_show[cols_display], filename_prefix="npa_radius_search", key_suffix="radius_tab3")

                        # =============================================================
                        # SUB-TAB 2: ตัวกรองพิกัดและตารางวิเคราะห์ทรัพย์สิน ณ จุดเดียวกัน
                        # =============================================================
                        with sub_view_tab2:
                            st.markdown("##### <i class='fa-solid fa-crosshairs' style='color:#059669; margin-right:6px;'></i>ตัวกรองพิกัดและตารางวิเคราะห์ทรัพย์สิน ณ จุดเดียวกัน", unsafe_allow_html=True)

                            coord_options = ["แสดงทรัพย์สินทั้งหมดในรัศมีค้นหา"]
                            coord_map_dict = {}
                            for mk in multi_coord_keys:
                                sub_grp = nearby_show[nearby_show['coord_key'] == mk]
                                cnt = len(sub_grp)
                                comps = ", ".join(sub_grp['บริษัท'].dropna().unique()[:3])
                                loc_desc = []
                                if pd.notna(sub_grp['ตำบล'].iloc[0]) and str(sub_grp['ตำบล'].iloc[0]).strip():
                                    loc_desc.append(str(sub_grp['ตำบล'].iloc[0]))
                                if pd.notna(sub_grp['อำเภอ'].iloc[0]) and str(sub_grp['อำเภอ'].iloc[0]).strip():
                                    loc_desc.append(str(sub_grp['อำเภอ'].iloc[0]))
                                loc_str = " - " + "/".join(loc_desc) if loc_desc else ""
                                opt_label = f"พิกัด [{mk}] • พบ {cnt} รายการ ({comps}){loc_str}"
                                coord_options.append(opt_label)
                                coord_map_dict[mk] = opt_label

                            # If active_coord_filter was selected from map pin (even if single property), add to options!
                            if st.session_state.tab3_active_coord_filter and st.session_state.tab3_active_coord_filter not in coord_map_dict:
                                act_k = st.session_state.tab3_active_coord_filter
                                sub_grp = nearby_show[nearby_show['coord_key'] == act_k]
                                if not sub_grp.empty:
                                    comps = ", ".join(sub_grp['บริษัท'].dropna().unique()[:3])
                                    opt_label = f"พิกัด [{act_k}] • {len(sub_grp)} รายการ ({comps})"
                                    coord_options.append(opt_label)
                                    coord_map_dict[act_k] = opt_label

                            # Calculate active label
                            active_label = "แสดงทรัพย์สินทั้งหมดในรัศมีค้นหา"
                            if st.session_state.tab3_active_coord_filter and st.session_state.tab3_active_coord_filter in coord_map_dict:
                                active_label = coord_map_dict[st.session_state.tab3_active_coord_filter]

                            default_idx = coord_options.index(active_label) if active_label in coord_options else 0

                            col_sel1, col_sel2 = st.columns([3, 1])
                            with col_sel1:
                                chosen_opt = st.selectbox(
                                    "เลือกดูเฉพาะพิกัดที่มีทรัพย์ซ้ำกัน (>1 รายการ) หรือคลิกจากหมุดบนแผนที่:",
                                    options=coord_options,
                                    index=default_idx,
                                    key=f"tab3_coord_select_box_{st.session_state.tab3_active_coord_filter}"
                                )
                            with col_sel2:
                                st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
                                if st.button("ล้างการเลือกพิกัด", icon=":material/clear:", use_container_width=True, key="btn_clear_coord_filter"):
                                    st.session_state.tab3_active_coord_filter = None
                                    if "sel_map_lat" in st.query_params:
                                        del st.query_params["sel_map_lat"]
                                    if "sel_map_lon" in st.query_params:
                                        del st.query_params["sel_map_lon"]
                                    st.rerun()

                            # Update active coord from dropdown if user manually selected a different item
                            if chosen_opt != "แสดงทรัพย์สินทั้งหมดในรัศมีค้นหา":
                                for k, v in coord_map_dict.items():
                                    if v == chosen_opt:
                                        st.session_state.tab3_active_coord_filter = k
                                        break
                            elif chosen_opt == "แสดงทรัพย์สินทั้งหมดในรัศมีค้นหา" and active_label == "แสดงทรัพย์สินทั้งหมดในรัศมีค้นหา":
                                st.session_state.tab3_active_coord_filter = None

                            # Highlight Table for the Selected Coordinate
                            if st.session_state.tab3_active_coord_filter:
                                active_k = st.session_state.tab3_active_coord_filter
                                coord_sub_df = nearby_show[nearby_show['coord_key'] == active_k].copy()
                                if not coord_sub_df.empty:
                                    coord_sub_df = coord_sub_df.sort_values(
                                        by=['ราคาขาย (บาท)', 'ราคา/ตร.ว. (บาท)', 'ราคา/ตร.ม. (บาท)'],
                                        ascending=[True, True, True],
                                        na_position='last'
                                    )
                                    cnt_coord = len(coord_sub_df)
                                    c_lat, c_lon = active_k.split(",")
                                    comps_at_pt = ", ".join(coord_sub_df['บริษัท'].dropna().unique())
                                    min_p = coord_sub_df['ราคาขาย (บาท)'].min()
                                    max_p = coord_sub_df['ราคาขาย (บาท)'].max()
                                    dist_val = coord_sub_df['ระยะทาง (กม.)'].iloc[0] if 'ระยะทาง (กม.)' in coord_sub_df.columns else None

                                    st.markdown(f"""
                                    <div style="background:linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%); border:1.5px solid #0284c7; border-radius:12px; padding:12px 18px; margin: 12px 0 16px 0;">
                                        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;">
                                            <div>
                                                <div style="font-size:15px; font-weight:800; color:#0369a1;">
                                                    <i class="fa-solid fa-location-crosshairs" style="margin-right:6px;"></i>ทรัพย์สิน NPA ณ พิกัดที่เลือก ({c_lat}, {c_lon})
                                                </div>
                                                <div style="font-size:12.5px; color:#334155; margin-top:3px;">
                                                    <i class="fa-solid fa-building" style="margin-right:4px;"></i>สถาบันที่พบ: <b>{comps_at_pt}</b> | <i class="fa-solid fa-ruler" style="margin-right:4px;"></i>ระยะห่างจากจุดค้นหา: <b>{dist_val:.2f} กม.</b>
                                                </div>
                                            </div>
                                            <div style="text-align:right;">
                                                <span style="background:#0284c7; color:#ffffff; font-weight:800; padding:4px 12px; border-radius:20px; font-size:13px;">
                                                    พบทั้งหมด {cnt_coord:,} รายการ ณ จุดนี้
                                                </span>
                                            </div>
                                        </div>
                                    </div>
                                    """, unsafe_allow_html=True)

                                    # Prominent Action Button Styling
                                    st.markdown("""
                                    <style>
                                    div.st-key-btn_add_all_coord_to_compare button {
                                        background: linear-gradient(135deg, #059669 0%, #047857 100%) !important;
                                        color: #ffffff !important;
                                        font-size: 15.5px !important;
                                        font-weight: 800 !important;
                                        padding: 12px 24px !important;
                                        border: 1.5px solid #10b981 !important;
                                        border-radius: 12px !important;
                                        box-shadow: 0 4px 16px rgba(5, 150, 105, 0.4) !important;
                                        transition: all 0.25s ease !important;
                                        letter-spacing: 0.2px !important;
                                    }
                                    div.st-key-btn_add_all_coord_to_compare button:hover {
                                        background: linear-gradient(135deg, #10b981 0%, #059669 100%) !important;
                                        border-color: #34d399 !important;
                                        box-shadow: 0 8px 24px rgba(5, 150, 105, 0.55) !important;
                                        transform: translateY(-2px) !important;
                                        color: #ffffff !important;
                                    }
                                    div.st-key-btn_add_all_coord_to_compare button:active {
                                        transform: translateY(0) !important;
                                    }
                                    div.st-key-btn_add_all_coord_to_compare button p {
                                        color: #ffffff !important;
                                        font-weight: 800 !important;
                                        font-size: 15.5px !important;
                                    }
                                    </style>
                                    """, unsafe_allow_html=True)

                                    if st.button(
                                        f"✨ เพิ่มทั้ง {cnt_coord} รายการในพิกัดนี้ ลงในตารางเปรียบเทียบเฉพาะที่เลือก", 
                                        icon=":material/playlist_add_check:", 
                                        key="btn_add_all_coord_to_compare", 
                                        use_container_width=True, 
                                        type="primary"
                                    ):
                                        for _, row_item in coord_sub_df.iterrows():
                                            c_code = str(row_item.get('รหัสทรัพย์', '')).strip() or str(row_item.get('ID', '')).strip()
                                            if c_code and c_code != '-' and c_code != 'None':
                                                st.session_state.tab3_custom_selected_codes.add(c_code)
                                        st.success(f"เพิ่ม {cnt_coord} รายการในพิกัดนี้ลงในตารางเปรียบเทียบเรียบร้อยแล้ว!")
                                        st.rerun()

                                    st.caption("*ท่านสามารถคลิกปุ่มสีเขียวด้านบนเพื่อเพิ่มทรัพย์ทั้งหมดในพิกัดนี้ทันที หรือติ๊กเลือกเฉพาะแปลงที่ต้องการในตารางด้านล่างได้ครับ*")

                                    coord_table_selection = st.dataframe(
                                        coord_sub_df[cols_display],
                                        width="stretch",
                                        column_config=df_col_config,
                                        on_select="rerun",
                                        selection_mode="multi-row",
                                        key=f"tab3_coord_sub_table_{active_k}"
                                    )

                                    if coord_table_selection and hasattr(coord_table_selection, "selection") and coord_table_selection.selection and getattr(coord_table_selection.selection, "rows", None):
                                        raw_coord_rows = coord_table_selection.selection.rows
                                        sel_coord_indices = [int(r) for r in raw_coord_rows if r is not None and (isinstance(r, (int, np.integer)) or (isinstance(r, str) and r.isdigit()))]
                                        if len(sel_coord_indices) > 0:
                                            if st.button(f"เพิ่ม {len(sel_coord_indices)} รายการที่ติ๊กเลือก ลงในตารางเปรียบเทียบเฉพาะที่เลือก", icon=":material/add:", key=f"btn_add_sel_coord_rows_{active_k}", type="primary"):
                                                for idx_r in sel_coord_indices:
                                                    if idx_r < len(coord_sub_df):
                                                        row_val = coord_sub_df.iloc[idx_r]
                                                        c_code = str(row_val.get('รหัสทรัพย์', '')).strip() or str(row_val.get('ID', '')).strip()
                                                        if c_code and c_code != '-' and c_code != 'None':
                                                            st.session_state.tab3_custom_selected_codes.add(c_code)
                                                st.success(f"เพิ่ม {len(sel_coord_indices)} รายการลงในตารางเปรียบเทียบเรียบร้อยแล้ว!")
                                                st.rerun()

                                    render_import_export_section(coord_sub_df[cols_display], filename_prefix=f"npa_coord_{c_lat}_{c_lon}", key_suffix="coord_sub_tab3")
                            else:
                                st.markdown("""
                                <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:10px; padding:18px 20px; color:#475569; font-size:13px; line-height:1.6; margin-top:8px;">
                                    <i class="fa-solid fa-circle-info" style="color:#0284c7; margin-right:6px;"></i><b>คำแนะนำ:</b> เลือกพิกัดจากเมนูด้านบน หรือคลิกที่หมุดบนแผนที่ด้านบน เพื่อเจาะลึกดูรายการทรัพย์สินทั้งหมดที่ตั้งอยู่ ณ จุดพิกัดเดียวกัน (เช่น โครงการคอนโดมิเนียมเดียวกัน หรือที่ดินแปลงติดกัน)
                                </div>
                                """, unsafe_allow_html=True)

                        # =============================================================
                        # SUB-TAB 3: ตารางเปรียบเทียบเฉพาะทรัพย์สินที่เลือก (เดิม SUB-TAB 1)
                        # =============================================================
                        with sub_view_tab3:
                            if cnt_custom > 0 and not custom_df.empty:
                                with st.container(border=True):
                                        # User Property statistics
                                        user_has_price = (inp_price is not None and inp_price > 0)
                                        user_has_land = (inp_land_area is not None and inp_land_area > 0)
                                        user_has_use = (inp_use_area is not None and inp_use_area > 0)
                                        user_price_per_wah = (inp_price / inp_land_area) if (user_has_price and user_has_land) else None
                                        user_price_per_sqm = (inp_price / inp_use_area) if (user_has_price and user_has_use) else None

                                        # Market Comps Statistics
                                        mean_price = custom_df['ราคาขาย (บาท)'].dropna().mean()
                                        median_price = custom_df['ราคาขาย (บาท)'].dropna().median()

                                        s_wah = custom_df['ราคา/ตร.ว. (บาท)'].dropna()
                                        mean_wah = s_wah.mean() if not s_wah.empty else np.nan
                                        median_wah = s_wah.median() if not s_wah.empty else np.nan

                                        s_sqm = custom_df['ราคา/ตร.ม. (บาท)'].dropna()
                                        mean_sqm = s_sqm.mean() if not s_sqm.empty else np.nan
                                        median_sqm = s_sqm.median() if not s_sqm.empty else np.nan

                                        # Size Summary for custom comps
                                        s_land_wah = custom_df['sqwah_calc'].dropna()
                                        median_cust_land = s_land_wah.median() if not s_land_wah.empty else None
                                        s_usable = custom_df['พื้นที่ใช้สอย (ตร.ม.)'].dropna()
                                        median_cust_use = s_usable.median() if not s_usable.empty else None

                                        if len(custom_df) == 1:
                                            cust_land_part = str(custom_df['เนื้อที่ (ไร่-งาน-ตร.ว.)'].iloc[0]) if ('เนื้อที่ (ไร่-งาน-ตร.ว.)' in custom_df.columns and pd.notna(custom_df['เนื้อที่ (ไร่-งาน-ตร.ว.)'].iloc[0])) else "-"
                                            cust_use_part = f"{custom_df['พื้นที่ใช้สอย (ตร.ม.)'].iloc[0]:,.1f} ตร.ม." if ('พื้นที่ใช้สอย (ตร.ม.)' in custom_df.columns and pd.notna(custom_df['พื้นที่ใช้สอย (ตร.ม.)'].iloc[0]) and custom_df['พื้นที่ใช้สอย (ตร.ม.)'].iloc[0] > 0) else "-"
                                        else:
                                            cust_land_part = f"ที่ดินกลาง {median_cust_land:,.1f} ตร.ว." if pd.notna(median_cust_land) else "ที่ดิน -"
                                            cust_use_part = f"ใช้สอยกลาง {median_cust_use:,.1f} ตร.ม." if pd.notna(median_cust_use) else "ใช้สอย -"

                                        # Modern High-Impact Diff Badges
                                        if pd.notna(median_price) and median_price > 0 and user_has_price:
                                            dp_pct = ((inp_price - median_price) / median_price) * 100
                                            dp_baht = inp_price - median_price
                                            if dp_pct < -0.1:
                                                p_diff_badge = f'<div style="display:inline-flex; align-items:center; gap:6px; background:#ecfdf5; border:1.5px solid #a7f3d0; border-radius:24px; padding:6px 14px; color:#065f46; font-size:13.5px; font-weight:800; box-shadow:0 1px 4px rgba(5,150,105,0.12);"><i class="fa-solid fa-arrow-down" style="color:#059669;"></i> ถูกกว่าค่ากลาง <b>{abs(dp_pct):.1f}%</b> <span style="font-weight:600; color:#047857; font-size:12px;">(-฿{abs(dp_baht):,.0f})</span></div>'
                                            elif dp_pct > 0.1:
                                                p_diff_badge = f'<div style="display:inline-flex; align-items:center; gap:6px; background:#fef2f2; border:1.5px solid #fecaca; border-radius:24px; padding:6px 14px; color:#991b1b; font-size:13.5px; font-weight:800; box-shadow:0 1px 4px rgba(220,38,38,0.12);"><i class="fa-solid fa-arrow-up" style="color:#dc2626;"></i> สูงกว่าค่ากลาง <b>{dp_pct:.1f}%</b> <span style="font-weight:600; color:#b91c1c; font-size:12px;">(+฿{dp_baht:,.0f})</span></div>'
                                            else:
                                                p_diff_badge = '<div style="display:inline-flex; align-items:center; gap:6px; background:#f0fdf4; border:1.5px solid #bbf7d0; border-radius:24px; padding:6px 14px; color:#166534; font-size:13.5px; font-weight:800;"><i class="fa-solid fa-check" style="color:#16a34a;"></i> เท่ากับค่ากลางพอดี</div>'
                                        else:
                                            p_diff_badge = '<span style="color:#94a3b8; font-size:13px;">-</span>'

                                        if user_price_per_wah and pd.notna(median_wah) and median_wah > 0:
                                            d_pct = ((user_price_per_wah - median_wah) / median_wah) * 100
                                            diff_baht = user_price_per_wah - median_wah
                                            if d_pct < -0.1:
                                                wah_diff_badge = f'<div style="display:inline-flex; align-items:center; gap:6px; background:#ecfdf5; border:1.5px solid #a7f3d0; border-radius:24px; padding:6px 14px; color:#065f46; font-size:13.5px; font-weight:800; box-shadow:0 1px 4px rgba(5,150,105,0.12);"><i class="fa-solid fa-arrow-down" style="color:#059669;"></i> ถูกกว่าค่ากลาง <b>{abs(d_pct):.1f}%</b> <span style="font-weight:600; color:#047857; font-size:12px;">(-฿{abs(diff_baht):,.0f}/ตร.ว.)</span></div>'
                                            elif d_pct > 0.1:
                                                wah_diff_badge = f'<div style="display:inline-flex; align-items:center; gap:6px; background:#fef2f2; border:1.5px solid #fecaca; border-radius:24px; padding:6px 14px; color:#991b1b; font-size:13.5px; font-weight:800; box-shadow:0 1px 4px rgba(220,38,38,0.12);"><i class="fa-solid fa-arrow-up" style="color:#dc2626;"></i> สูงกว่าค่ากลาง <b>{d_pct:.1f}%</b> <span style="font-weight:600; color:#b91c1c; font-size:12px;">(+฿{diff_baht:,.0f}/ตร.ว.)</span></div>'
                                            else:
                                                wah_diff_badge = '<div style="display:inline-flex; align-items:center; gap:6px; background:#f0fdf4; border:1.5px solid #bbf7d0; border-radius:24px; padding:6px 14px; color:#166534; font-size:13.5px; font-weight:800;"><i class="fa-solid fa-check" style="color:#16a34a;"></i> เท่ากับค่ากลางพอดี</div>'
                                        else:
                                            wah_diff_badge = '<span style="color:#94a3b8; font-size:13px;">-</span>'

                                        if user_price_per_sqm and pd.notna(median_sqm) and median_sqm > 0:
                                            d_sqm = ((user_price_per_sqm - median_sqm) / median_sqm) * 100
                                            diff_sqm_baht = user_price_per_sqm - median_sqm
                                            if d_sqm < -0.1:
                                                sqm_diff_badge = f'<div style="display:inline-flex; align-items:center; gap:6px; background:#ecfdf5; border:1.5px solid #a7f3d0; border-radius:24px; padding:6px 14px; color:#065f46; font-size:13.5px; font-weight:800; box-shadow:0 1px 4px rgba(5,150,105,0.12);"><i class="fa-solid fa-arrow-down" style="color:#059669;"></i> ถูกกว่าค่ากลาง <b>{abs(d_sqm):.1f}%</b> <span style="font-weight:600; color:#047857; font-size:12px;">(-฿{abs(diff_sqm_baht):,.0f}/ตร.ม.)</span></div>'
                                            elif d_sqm > 0.1:
                                                sqm_diff_badge = f'<div style="display:inline-flex; align-items:center; gap:6px; background:#fef2f2; border:1.5px solid #fecaca; border-radius:24px; padding:6px 14px; color:#991b1b; font-size:13.5px; font-weight:800; box-shadow:0 1px 4px rgba(220,38,38,0.12);"><i class="fa-solid fa-arrow-up" style="color:#dc2626;"></i> สูงกว่าค่ากลาง <b>{d_sqm:.1f}%</b> <span style="font-weight:600; color:#b91c1c; font-size:12px;">(+฿{diff_sqm_baht:,.0f}/ตร.ม.)</span></div>'
                                            else:
                                                sqm_diff_badge = '<div style="display:inline-flex; align-items:center; gap:6px; background:#f0fdf4; border:1.5px solid #bbf7d0; border-radius:24px; padding:6px 14px; color:#166534; font-size:13.5px; font-weight:800;"><i class="fa-solid fa-check" style="color:#16a34a;"></i> เท่ากับค่ากลางพอดี</div>'
                                        else:
                                            sqm_diff_badge = '<span style="color:#94a3b8; font-size:13px;">-</span>'

                                        user_w_display = f"฿{user_price_per_wah:,.0f}/ตร.ว." if user_price_per_wah else "ไม่ระบุ"
                                        med_w_display = f"฿{median_wah:,.0f}/ตร.ว." if pd.notna(median_wah) else "-"
                                        mean_w_display = f"฿{mean_wah:,.0f}/ตร.ว." if pd.notna(mean_wah) else "-"

                                        user_p_display = f"฿{inp_price:,.0f}" if user_has_price else "ไม่ระบุ"
                                        med_p_display = f"฿{median_price:,.0f}" if pd.notna(median_price) else "-"
                                        mean_p_display = f"฿{mean_price:,.0f}" if pd.notna(mean_price) else "-"

                                        user_sqm_display = f"฿{user_price_per_sqm:,.0f}/ตร.ม." if user_price_per_sqm else "ไม่ระบุ"
                                        med_sqm_display = f"฿{median_sqm:,.0f}/ตร.ม." if pd.notna(median_sqm) else "-"
                                        mean_sqm_display = f"฿{mean_sqm:,.0f}/ตร.ม." if pd.notna(mean_sqm) else "-"

                                        user_land_display = f"{inp_land_area:,.1f} ตร.ว." if user_has_land else "ไม่ระบุ"
                                        user_use_display = f"{inp_use_area:,.1f} ตร.ม." if user_has_use else "ไม่ระบุ"

                                        # Modern Large Matrix Table (Full-Width, Big Typography, Clear Badges)
                                        table_html_raw = f"""
                                        <div style="background:#ffffff; border:1.5px solid #cbd5e1; border-radius:16px; box-shadow:0 4px 20px rgba(0,0,0,0.04); margin-bottom:22px; overflow:hidden;">
                                            <div style="background:linear-gradient(135deg, #0f172a 0%, #1e293b 100%); padding:16px 22px; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px;">
                                                <div>
                                                    <div style="font-size:17.5px; font-weight:800; color:#ffffff; display:flex; align-items:center; gap:9px;">
                                                        <i class="fa-solid fa-table-columns" style="color:#10b981; font-size:19px;"></i>
                                                        <span>ตารางวิเคราะห์เปรียบเทียบเชิงลึก: ทรัพย์สินของคุณ VS ทรัพย์สินที่เลือก ({len(custom_df)} รายการ)</span>
                                                    </div>
                                                    <div style="font-size:13px; color:#94a3b8; margin-top:3px;">
                                                        เปรียบเทียบราคาเสนอขาย, ราคาต่อหน่วยพื้นที่ และขนาดทรัพย์สิน กับสถิติค่ากลาง (Median) และค่าเฉลี่ย (Mean)
                                                    </div>
                                                </div>
                                                <div style="background:rgba(255,255,255,0.1); border:1px solid rgba(255,255,255,0.18); border-radius:20px; padding:5px 14px; font-size:12.5px; color:#e2e8f0; font-weight:800;">
                                                    <i class="fa-solid fa-layer-group" style="color:#38bdf8; margin-right:4px;"></i> {len(custom_df)} ทรัพย์สินเปรียบเทียบ
                                                </div>
                                            </div>
                                            
                                            <div style="overflow-x:auto;">
                                                <table style="width:100%; border-collapse:separate; border-spacing:0; font-size:14.5px; text-align:left;">
                                                    <thead>
                                                        <tr style="background:#f1f5f9; color:#334155; border-bottom:2px solid #cbd5e1;">
                                                            <th style="padding:15px 20px; font-weight:800; width:25%; font-size:14px; color:#475569; letter-spacing:0.3px;"><i class="fa-solid fa-list-check" style="margin-right:6px;"></i>หัวข้อการเปรียบเทียบ</th>
                                                            <th style="padding:15px 20px; background:#e0f2fe; color:#0369a1; font-weight:900; width:22%; font-size:15px; border-top:3.5px solid #0284c7; border-left:1px solid #bae6fd; border-right:1px solid #bae6fd;"><i class="fa-solid fa-bullseye" style="margin-right:6px;"></i>ทรัพย์สินของคุณ</th>
                                                            <th style="padding:15px 20px; background:#ecfdf5; color:#065f46; font-weight:900; width:21%; font-size:15px; border-top:3.5px solid #059669; border-right:1px solid #a7f3d0;"><i class="fa-solid fa-chart-simple" style="margin-right:6px;"></i>ค่ากลางตลาด (Median)</th>
                                                            <th style="padding:15px 20px; background:#f8fafc; color:#334155; font-weight:800; width:15%; font-size:14px; border-right:1px solid #e2e8f0;"><i class="fa-solid fa-chart-line" style="margin-right:6px;"></i>ค่าเฉลี่ยตลาด (Mean)</th>
                                                            <th style="padding:15px 20px; background:#f8fafc; color:#0f172a; font-weight:900; width:17%; font-size:14px;"><i class="fa-solid fa-scale-balanced" style="margin-right:6px;"></i>ส่วนต่างเทียบค่ากลาง</th>
                                                        </tr>
                                                    </thead>
                                                    <tbody>
                                                        <!-- Row 1: ราคาเสนอขายรวม -->
                                                        <tr style="border-bottom:1px solid #e2e8f0; background:#ffffff;">
                                                            <td style="padding:18px 20px;">
                                                                <div style="display:flex; align-items:center; gap:10px;">
                                                                    <div style="width:36px; height:36px; border-radius:10px; background:#ecfdf5; display:flex; align-items:center; justify-content:center; color:#059669; font-size:16px; flex-shrink:0;"><i class="fa-solid fa-tag"></i></div>
                                                                    <div>
                                                                        <div style="font-weight:800; font-size:15.5px; color:#0f172a;">ราคาเสนอขายรวม</div>
                                                                        <div style="font-size:12px; color:#64748b; font-weight:500;">ราคาเสนอขายทรัพย์สิน (บาท)</div>
                                                                    </div>
                                                                </div>
                                                            </td>
                                                            <td style="padding:18px 20px; background:#f0f9ff; border-left:1px solid #bae6fd; border-right:1px solid #bae6fd;">
                                                                <div style="font-size:20px; font-weight:900; color:#0284c7; letter-spacing:-0.3px;">{user_p_display}</div>
                                                                <div style="font-size:12px; color:#0369a1; font-weight:600;">(จุดอ้างอิงของคุณ)</div>
                                                            </td>
                                                            <td style="padding:18px 20px; background:#f0fdf4; border-right:1px solid #a7f3d0;">
                                                                <div style="font-size:20px; font-weight:900; color:#059669; letter-spacing:-0.3px;">{med_p_display}</div>
                                                                <div style="font-size:12px; color:#047857; font-weight:600;">(ค่ามัธยฐาน {len(custom_df)} ทรัพย์)</div>
                                                            </td>
                                                            <td style="padding:18px 20px; background:#ffffff; border-right:1px solid #e2e8f0;">
                                                                <div style="font-size:16px; font-weight:800; color:#334155;">{mean_p_display}</div>
                                                            </td>
                                                            <td style="padding:18px 20px; background:#ffffff;">
                                                                {p_diff_badge}
                                                            </td>
                                                        </tr>

                                                        <!-- Row 2: ราคาต่อ ตร.ว. -->
                                                        <tr style="border-bottom:1px solid #e2e8f0; background:#fbfcfe;">
                                                            <td style="padding:18px 20px;">
                                                                <div style="display:flex; align-items:center; gap:10px;">
                                                                    <div style="width:36px; height:36px; border-radius:10px; background:#eff6ff; display:flex; align-items:center; justify-content:center; color:#2563eb; font-size:16px; flex-shrink:0;"><i class="fa-solid fa-vector-square"></i></div>
                                                                    <div>
                                                                        <div style="font-weight:800; font-size:15.5px; color:#0f172a;">ราคาต่อ ตร.ว. (ที่ดิน)</div>
                                                                        <div style="font-size:12px; color:#64748b; font-weight:500;">ราคาขาย ÷ เนื้อที่ตารางวา</div>
                                                                    </div>
                                                                </div>
                                                            </td>
                                                            <td style="padding:18px 20px; background:#f0f9ff; border-left:1px solid #bae6fd; border-right:1px solid #bae6fd;">
                                                                <div style="font-size:19px; font-weight:900; color:#0284c7; letter-spacing:-0.3px;">{user_w_display}</div>
                                                            </td>
                                                            <td style="padding:18px 20px; background:#f0fdf4; border-right:1px solid #a7f3d0;">
                                                                <div style="font-size:19px; font-weight:900; color:#059669; letter-spacing:-0.3px;">{med_w_display}</div>
                                                            </td>
                                                            <td style="padding:18px 20px; background:#fbfcfe; border-right:1px solid #e2e8f0;">
                                                                <div style="font-size:16px; font-weight:800; color:#334155;">{mean_w_display}</div>
                                                            </td>
                                                            <td style="padding:18px 20px; background:#fbfcfe;">
                                                                {wah_diff_badge}
                                                            </td>
                                                        </tr>

                                                        <!-- Row 3: ราคาต่อ ตร.ม. -->
                                                        <tr style="border-bottom:1px solid #e2e8f0; background:#ffffff;">
                                                            <td style="padding:18px 20px;">
                                                                <div style="display:flex; align-items:center; gap:10px;">
                                                                    <div style="width:36px; height:36px; border-radius:10px; background:#f5f3ff; display:flex; align-items:center; justify-content:center; color:#7c3aed; font-size:16px; flex-shrink:0;"><i class="fa-solid fa-building"></i></div>
                                                                    <div>
                                                                        <div style="font-weight:800; font-size:15.5px; color:#0f172a;">ราคาต่อ ตร.ม. (ใช้สอย)</div>
                                                                        <div style="font-size:12px; color:#64748b; font-weight:500;">ราคาขาย ÷ พื้นที่ใช้สอย ตร.ม.</div>
                                                                    </div>
                                                                </div>
                                                            </td>
                                                            <td style="padding:18px 20px; background:#f0f9ff; border-left:1px solid #bae6fd; border-right:1px solid #bae6fd;">
                                                                <div style="font-size:19px; font-weight:900; color:#0284c7; letter-spacing:-0.3px;">{user_sqm_display}</div>
                                                            </td>
                                                            <td style="padding:18px 20px; background:#f0fdf4; border-right:1px solid #a7f3d0;">
                                                                <div style="font-size:19px; font-weight:900; color:#059669; letter-spacing:-0.3px;">{med_sqm_display}</div>
                                                            </td>
                                                            <td style="padding:18px 20px; background:#ffffff; border-right:1px solid #e2e8f0;">
                                                                <div style="font-size:16px; font-weight:800; color:#334155;">{mean_sqm_display}</div>
                                                            </td>
                                                            <td style="padding:18px 20px; background:#ffffff;">
                                                                {sqm_diff_badge}
                                                            </td>
                                                        </tr>

                                                        <!-- Row 4: ขนาดพื้นที่ -->
                                                        <tr style="background:#f8fafc;">
                                                            <td style="padding:18px 20px;">
                                                                <div style="display:flex; align-items:center; gap:10px;">
                                                                    <div style="width:36px; height:36px; border-radius:10px; background:#f1f5f9; display:flex; align-items:center; justify-content:center; color:#475569; font-size:16px; flex-shrink:0;"><i class="fa-solid fa-ruler-combined"></i></div>
                                                                    <div>
                                                                        <div style="font-weight:800; font-size:15.5px; color:#0f172a;">ขนาดเนื้อที่ / พื้นที่ใช้สอย</div>
                                                                        <div style="font-size:12px; color:#64748b; font-weight:500;">(เนื้อที่ดิน / พื้นที่ใช้สอยอาคาร)</div>
                                                                    </div>
                                                                </div>
                                                            </td>
                                                            <td style="padding:18px 20px; background:#f0f9ff; border-left:1px solid #bae6fd; border-right:1px solid #bae6fd;">
                                                                <div style="font-size:16.5px; font-weight:800; color:#0369a1;">{user_land_display}</div>
                                                                <div style="font-size:13.5px; color:#475569; margin-top:2px;">ใช้สอย: <b>{user_use_display}</b></div>
                                                            </td>
                                                            <td style="padding:18px 20px; background:#f0fdf4; border-right:1px solid #a7f3d0;">
                                                                <div style="font-size:16.5px; font-weight:800; color:#047857;">{cust_land_part}</div>
                                                                <div style="font-size:13.5px; color:#475569; margin-top:2px;">ใช้สอย: <b>{cust_use_part}</b></div>
                                                            </td>
                                                            <td style="padding:18px 20px; background:#f8fafc; border-right:1px solid #e2e8f0; color:#64748b; font-size:13px;">
                                                                -
                                                            </td>
                                                            <td style="padding:18px 20px; background:#f8fafc;">
                                                                <span style="background:#f1f5f9; border:1px solid #cbd5e1; color:#475569; padding:6px 12px; border-radius:16px; font-size:12.5px; font-weight:700; display:inline-block;"><i class="fa-solid fa-eye" style="margin-right:4px;"></i>ดูแยกแต่ละแปลงในตารางล่าง</span>
                                                            </td>
                                                        </tr>
                                                    </tbody>
                                                </table>
                                            </div>
                                        </div>
                                        """
                                        st.markdown("\n".join([line.strip() for line in table_html_raw.splitlines() if line.strip()]), unsafe_allow_html=True)

                                        # Metrics Cards Row
                                        kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
                                        kpi1.metric("จำนวนทรัพย์ที่เลือก", f"{len(custom_df):,} รายการ")

                                        p_delta = f"{((inp_price - median_price)/median_price*100):+.1f}% vs ทรัพย์เรา" if (user_has_price and median_price > 0) else None
                                        kpi2.metric(
                                            "ราคาเสนอขาย (ค่ากลาง)", 
                                            f"฿{median_price:,.0f}" if pd.notna(median_price) else "-",
                                            delta=p_delta,
                                            help=f"ราคาเสนอขายเฉลี่ย: ฿{mean_price:,.0f}" if pd.notna(mean_price) else None
                                        )

                                        w_med_delta = f"{((user_price_per_wah - median_wah)/median_wah*100):+.1f}% vs ทรัพย์เรา" if (user_price_per_wah and pd.notna(median_wah) and median_wah > 0) else None
                                        kpi3.metric(
                                            "ราคา/ตร.ว. (ค่ากลาง)",
                                            f"฿{median_wah:,.0f}" if pd.notna(median_wah) else "-",
                                            delta=w_med_delta,
                                            help="ค่ามัธยฐาน (Median) ราคาต่อตารางวาของทรัพย์สินที่เลือก"
                                        )

                                        w_mean_delta = f"{((user_price_per_wah - mean_wah)/mean_wah*100):+.1f}% vs ทรัพย์เรา" if (user_price_per_wah and pd.notna(mean_wah) and mean_wah > 0) else None
                                        kpi4.metric(
                                            "ราคา/ตร.ว. (ค่าเฉลี่ย)",
                                            f"฿{mean_wah:,.0f}" if pd.notna(mean_wah) else "-",
                                            delta=w_mean_delta,
                                            help="ค่าเฉลี่ย (Mean) ราคาต่อตารางวาของทรัพย์สินที่เลือก"
                                        )

                                        sqm_delta = f"ค่ากลาง ฿{median_sqm:,.0f}" if pd.notna(median_sqm) else None
                                        kpi5.metric(
                                            "ราคา/ตร.ม. (ค่าเฉลี่ย)",
                                            f"฿{mean_sqm:,.0f}" if pd.notna(mean_sqm) else "-",
                                            delta=sqm_delta,
                                            delta_color="off",
                                            help=f"ราคาต่อตารางเมตรพื้นที่ใช้สอย (เฉลี่ย: ฿{mean_sqm:,.0f} | ค่ากลาง: ฿{median_sqm:,.0f})" if pd.notna(mean_sqm) else None
                                        )

                                        col_cust_act1, col_cust_act2 = st.columns([3, 1])
                                        with col_cust_act1:
                                            show_ref_row = st.checkbox(
                                                "รวมแถว 'ทรัพย์สินของคุณ' ไว้ด้านบนสุดของตาราง เพื่อเปรียบเทียบแบบเคียงข้าง",
                                                value=True,
                                                key="tab3_show_ref_row_in_compare_table"
                                            )
                                        with col_cust_act2:
                                            if st.button("ล้างรายการที่เลือกทั้งหมด", icon=":material/delete_sweep:", key="btn_clear_all_custom_sel", use_container_width=True):
                                                st.session_state.tab3_custom_selected_codes = set()
                                                if "sel_custom_codes" in st.query_params:
                                                    del st.query_params["sel_custom_codes"]
                                                st.rerun()

                                        # Prepare dataframe to display
                                        df_to_show = custom_df.copy()
                                        if show_ref_row and user_has_price:
                                            ref_row = {}
                                            for c_col in cols_display:
                                                ref_row[c_col] = None
                                            ref_row["บริษัท"] = "ทรัพย์ของคุณ"
                                            ref_row["รหัสทรัพย์"] = "จุดอ้างอิง"
                                            ref_row["ชื่อโครงการ"] = str(inp_name) if 'inp_name' in locals() else "ทรัพย์สินของคุณ"
                                            ref_row["ประเภททรัพย์"] = str(inp_type) if 'inp_type' in locals() else "-"
                                            ref_row["ประเภทการขาย"] = "อ้างอิง"
                                            ref_row["ราคาขาย (บาท)"] = float(inp_price) if user_has_price else np.nan
                                            ref_row["ตำบล"] = "-"
                                            ref_row["อำเภอ"] = "-"
                                            ref_row["จังหวัด"] = "-"
                                            ref_row["ระยะทาง (กม.)"] = 0.0
                                            ref_row["ลิงก์"] = None
                                            ref_row["รูปแปลงที่ดิน"] = None
                                            ref_row["เนื้อที่ (ไร่-งาน-ตร.ว.)"] = f"{inp_land_area:,.1f} ตร.ว." if user_has_land else "-"
                                            ref_row["ราคา/ตร.ว. (บาท)"] = float(user_price_per_wah) if user_price_per_wah else np.nan
                                            ref_row["พื้นที่ใช้สอย (ตร.ม.)"] = float(inp_use_area) if user_has_use else np.nan
                                            ref_row["ราคา/ตร.ม. (บาท)"] = float(user_price_per_sqm) if user_price_per_sqm else np.nan
                                            df_to_show = pd.concat([pd.DataFrame([ref_row]), df_to_show], ignore_index=True)

                                        st.dataframe(
                                            df_to_show[cols_display],
                                            width="stretch",
                                            column_config=df_col_config
                                        )
                                        render_import_export_section(df_to_show[cols_display], filename_prefix="npa_custom_comparison", key_suffix="custom_compare_tab3")
                            else:
                                st.markdown(f"""
                                <div style="background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%); border: 1.5px dashed #cbd5e1; border-radius: 14px; padding: 36px 24px; text-align: center; margin: 16px 0;">
                                    <div style="font-size: 36px; color: #059669; margin-bottom: 10px;">
                                        <i class="fa-solid fa-table-columns"></i>
                                    </div>
                                    <div style="font-size: 16px; font-weight: 800; color: #1e293b; margin-bottom: 6px;">
                                        ยังไม่มีรายการทรัพย์สินที่เลือกเปรียบเทียบ
                                    </div>
                                    <div style="font-size: 13.5px; color: #64748b; max-width: 600px; margin: 0 auto; line-height: 1.6;">
                                        ขณะนี้พบทรัพย์ NPA ทั้งหมด <b>{len(nearby_df):,}</b> รายการในรัศมีค้นหา<br>
                                        ท่านสามารถสลับไปที่แท็บ <b>'เจาะลึกตามพิกัด'</b> หรือแท็บ <b>'รายการทั้งหมดในรัศมี'</b> ด้านบน<br>
                                        แล้วติ๊กเลือกทรัพย์สินที่น่าสนใจเพื่อนำมาวิเคราะห์เปรียบเทียบเคียงข้างกับทรัพย์สินของคุณได้ทันที
                                    </div>
                                </div>
                                """, unsafe_allow_html=True)

    with comp_sub_tab2:
        render_same_project_comparison(
            df_all_source=df_raw,
            is_dark_mode=is_dark_mode,
            plotly_template=plotly_template,
            style_plotly_fig=style_plotly_fig,
            key_prefix="tab3_same_proj"
        )

    # -----------------------------------------------------------------
    # SUB-TAB 3: สถิติค่ากลาง ราคา/พื้นที่ (Price per Area Market Analysis)
    # -----------------------------------------------------------------
    # -----------------------------------------------------------------
    with comp_sub_tab3:
        st.markdown("#### <i class='fa-solid fa-chart-area' style='color:#059669; margin-right:6px;'></i>สถิติค่ากลาง ราคาต่อหน่วยพื้นที่ (Median Price per Area Analysis)", unsafe_allow_html=True)
        st.caption("วิเคราะห์เปรียบเทียบค่ากลาง ราคา/ตร.ว. (สำหรับเนื้อที่ดิน) และ ค่ากลาง ราคา/ตร.ม. (สำหรับพื้นที่ใช้สอย) พร้อมตัวกรองทำเลเจาะลึก 4 ระดับ")

        # Region Definitions
        REGION_PROVINCES = {
            "กรุงเทพฯ และปริมณฑล": ["กรุงเทพมหานคร", "นนทบุรี", "ปทุมธานี", "สมุทรปราการ", "สมุทรสาคร", "นครปฐม"],
            "ภาคกลาง": ["พระนครศรีอยุธยา", "สระบุรี", "ลพบุรี", "ชัยนาท", "สิงห์บุรี", "อ่างทอง", "สุพรรณบุรี", "นครนายก"],
            "ภาคเหนือ": ["เชียงใหม่", "เชียงราย", "ลำปาง", "ลำพูน", "แม่ฮ่องสอน", "น่าน", "พะเยา", "แพร่", "อุตรดิตถ์", "พิษณุโลก", "สุโขทัย", "เพชรบูรณ์", "พิจิตร", "กำแพงเพชร", "นครสวรรค์", "อุทัยธานี", "ตาก"],
            "ภาคตะวันออกเฉียงเหนือ": ["นครราชสีมา", "ขอนแก่น", "อุดรธานี", "อุบลราชธานี", "บุรีรัมย์", "สุรินทร์", "ศรีสะเกษ", "ร้อยเอ็ด", "มหาสารคาม", "ชัยภูมิ", "กาฬสินธุ์", "สกลนคร", "นครพนม", "มุกดาหาร", "ยโสธร", "อำนาจเจริญ", "หนองคาย", "เลย", "หนองบัวลำภู", "บึงกาฬ"],
            "ภาคตะวันออก": ["ชลบุรี", "ระยอง", "ฉะเชิงเทรา", "จันทบุรี", "ตราด", "สระแก้ว", "ปราจีนบุรี"],
            "ภาคตะวันตก": ["กาญจนบุรี", "ราชบุรี", "เพชรบุรี", "ประจวบคีรีขันธ์", "สมุทรสงคราม"],
            "ภาคใต้": ["ภูเก็ต", "สุราษฎร์ธานี", "สงขลา", "นครศรีธรรมราช", "กระบี่", "พังงา", "ตรัง", "ชุมพร", "ระนอง", "พัทลุง", "สตูล", "ปัตตานี", "ยะลา", "นราธิวาส"]
        }

        def get_province_region(prov):
            if not prov or pd.isna(prov):
                return "อื่นๆ"
            p = str(prov).strip()
            for reg, prov_list in REGION_PROVINCES.items():
                for base_prov in prov_list:
                    if base_prov in p or (base_prov == "พระนครศรีอยุธยา" and "อยุธยา" in p):
                        return reg
            return "อื่นๆ"

        # 1. Minimal & Smart Location Filter Bar
        cur_reg = st.session_state.get("sub4_sel_region", "ทั้งหมดทุกภาค")
        cur_prov = st.session_state.get("sub4_sel_province", "ทั้งหมดทุกจังหวัด")
        cur_dist = st.session_state.get("sub4_sel_district", "ทั้งหมดทุกอำเภอ/เขต")
        cur_subdist = st.session_state.get("sub4_sel_subdistrict", "ทั้งหมดทุกตำบล/แขวง")
        
        active_loc_tokens = []
        if cur_reg != "ทั้งหมดทุกภาค":
            active_loc_tokens.append(cur_reg)
        if cur_prov != "ทั้งหมดทุกจังหวัด":
            active_loc_tokens.append(cur_prov)
        if cur_dist != "ทั้งหมดทุกอำเภอ/เขต":
            active_loc_tokens.append(cur_dist)
        if cur_subdist != "ทั้งหมดทุกตำบล/แขวง":
            active_loc_tokens.append(cur_subdist)

        with st.container(border=True):
            col_h_left, col_h_right = st.columns([8, 2])
            
            loc_badge_html = f" <span style='font-size: 0.78rem; font-weight: 500; color: #06b6d4; background: rgba(6, 182, 212, 0.1); border: 1px solid rgba(6, 182, 212, 0.25); padding: 2px 8px; border-radius: 6px;'>{' › '.join(active_loc_tokens)}</span>" if active_loc_tokens else ""

            with col_h_left:
                st.markdown(
                    f"<div style='font-size: 0.92rem; font-weight: 600; color: {'#94a3b8' if is_dark_mode else '#64748b'}; display: flex; align-items: center; gap: 8px; padding-top: 4px;'>"
                    f"<i class='fa-solid fa-location-dot' style='color: #06b6d4;'></i> <span style='color: {'#f8fafc' if is_dark_mode else '#0f172a'}; font-weight: 700;'>เลือกพื้นที่ทำเล</span>{loc_badge_html}"
                    f"</div>",
                    unsafe_allow_html=True
                )

            with col_h_right:
                if active_loc_tokens:
                    def reset_sub4_loc_callback():
                        st.session_state["sub4_sel_region"] = "ทั้งหมดทุกภาค"
                        st.session_state["sub4_sel_province"] = "ทั้งหมดทุกจังหวัด"
                        st.session_state["sub4_sel_district"] = "ทั้งหมดทุกอำเภอ/เขต"
                        st.session_state["sub4_sel_subdistrict"] = "ทั้งหมดทุกตำบล/แขวง"
                    st.button("↺ ล้างตัวกรอง", on_click=reset_sub4_loc_callback, key="sub4_reset_loc_btn", use_container_width=True)

            col_l1, col_l2, col_l3, col_l4 = st.columns(4)

            with col_l1:
                sel_region = st.selectbox("ภาค", ["ทั้งหมดทุกภาค"] + list(REGION_PROVINCES.keys()), key="sub4_sel_region")

            if sel_region != "ทั้งหมดทุกภาค":
                avail_provinces = sorted([p for p in df_filtered['จังหวัด'].dropna().unique() if get_province_region(p) == sel_region and str(p).strip() not in ['', '-', 'nan', 'None']])
            else:
                avail_provinces = sorted([p for p in df_filtered['จังหวัด'].dropna().unique() if str(p).strip() not in ['', '-', 'nan', 'None']])

            if st.session_state.get("sub4_sel_province") not in ["ทั้งหมดทุกจังหวัด"] + avail_provinces:
                st.session_state["sub4_sel_province"] = "ทั้งหมดทุกจังหวัด"

            with col_l2:
                sel_province = st.selectbox("จังหวัด", ["ทั้งหมดทุกจังหวัด"] + avail_provinces, key="sub4_sel_province")

            df_prov_scoped = df_filtered.copy()
            if sel_region != "ทั้งหมดทุกภาค":
                df_prov_scoped = df_prov_scoped[df_prov_scoped['จังหวัด'].apply(get_province_region) == sel_region]
            if sel_province != "ทั้งหมดทุกจังหวัด":
                df_prov_scoped = df_prov_scoped[df_prov_scoped['จังหวัด'] == sel_province]

            avail_districts = sorted([d for d in df_prov_scoped['อำเภอ'].dropna().unique() if str(d).strip() not in ['', '-', 'nan', 'None']])
            if st.session_state.get("sub4_sel_district") not in ["ทั้งหมดทุกอำเภอ/เขต"] + avail_districts:
                st.session_state["sub4_sel_district"] = "ทั้งหมดทุกอำเภอ/เขต"

            with col_l3:
                sel_district = st.selectbox("อำเภอ/เขต", ["ทั้งหมดทุกอำเภอ/เขต"] + avail_districts, key="sub4_sel_district")

            df_dist_scoped = df_prov_scoped.copy()
            if sel_district != "ทั้งหมดทุกอำเภอ/เขต":
                df_dist_scoped = df_dist_scoped[df_dist_scoped['อำเภอ'] == sel_district]

            avail_subdistricts = sorted([s for s in df_dist_scoped['ตำบล'].dropna().unique() if str(s).strip() not in ['', '-', 'nan', 'None']])
            if st.session_state.get("sub4_sel_subdistrict") not in ["ทั้งหมดทุกตำบล/แขวง"] + avail_subdistricts:
                st.session_state["sub4_sel_subdistrict"] = "ทั้งหมดทุกตำบล/แขวง"

            with col_l4:
                sel_subdistrict = st.selectbox("ตำบล/แขวง", ["ทั้งหมดทุกตำบล/แขวง"] + avail_subdistricts, key="sub4_sel_subdistrict")

            df_scope = df_dist_scoped.copy()
            if sel_subdistrict != "ทั้งหมดทุกตำบล/แขวง":
                df_scope = df_scope[df_scope['ตำบล'] == sel_subdistrict]

        card_bg_sub4 = 'rgba(15, 23, 42, 0.75)' if is_dark_mode else 'linear-gradient(135deg, #ffffff 0%, #f8fafc 100%)'
        card_border_sub4 = 'rgba(255, 255, 255, 0.1)' if is_dark_mode else 'rgba(226, 232, 240, 0.8)'

        PROP_TYPE_BAR_COLORS = {
            "ห้องชุดพักอาศัย": "#06b6d4",
            "อาคารพาณิชย์": "#f43f5e",
            "อพาร์ทเมนท์": "#a855f7",
            "วิลล่า": "#ec4899",
            "ทาวน์เฮ้าส์": "#f59e0b",
            "บ้านเดี่ยว": "#2563eb",
            "บ้านแฝด": "#6366f1",
            "อาคารสำนักงาน": "#64748b",
            "โรงแรม/รีสอร์ท": "#eab308",
            "โรงงาน/โกดัง": "#06b6d4",
            "ปั๊มน้ำมัน": "#d97706",
            "ที่ดินพร้อมสิ่งปลูกสร้าง": "#059669",
            "อื่นๆ": "#94a3b8",
            "เพิงอเนกประสงค์": "#78716c",
            "ฟาร์ม": "#84cc16",
            "ที่ดินเปล่า": "#10b981",
            "ห้องชุดพาณิชยกรรม/สำนักงาน": "#38bdf8"
        }

        # Nested Sub-tabs (Option 1: Clean & Elegant)
        tab_land_sub4, tab_usable_sub4 = st.tabs([
            "เนื้อที่ (ตร.ว.)",
            "พื้นที่ใช้สอย (ตร.ม.)"
        ])

        # =========================================================================
        # CASE A: เนื้อที่ (ค่ากลาง ราคา/ตร.ว.)
        # =========================================================================
        with tab_land_sub4:
            is_landed_sub4 = ~df_scope['ประเภททรัพย์'].str.contains('ห้องชุด|คอนโด', na=False)
            df_land_sub4 = df_scope[
                is_landed_sub4 & 
                (df_scope['ราคา'].notna()) & 
                (df_scope['ราคา'] > 0) & 
                (df_scope['พื้นที่_ตารางวา'].notna()) & 
                (df_scope['พื้นที่_ตารางวา'] > 0) & 
                (df_scope['พื้นที่_ตารางวา'] <= 10000)
            ].copy()

            if not df_land_sub4.empty:
                df_land_sub4['ราคา_ต่อ_ตรว'] = df_land_sub4['ราคา'] / df_land_sub4['พื้นที่_ตารางวา']
                df_clean_sub4 = df_land_sub4[(df_land_sub4['ราคา_ต่อ_ตรว'] >= 100) & (df_land_sub4['ราคา_ต่อ_ตรว'] <= 2000000)].copy()

                tot_land_units = len(df_clean_sub4)
                overall_median_sqw = float(df_clean_sub4['ราคา_ต่อ_ตรว'].median()) if tot_land_units > 0 else 0.0
                
                df_single_house = df_clean_sub4[df_clean_sub4['ประเภททรัพย์'].str.contains('บ้านเดี่ยว', na=False)]
                med_house = float(df_single_house['ราคา_ต่อ_ตรว'].median()) if not df_single_house.empty else 0.0

                df_townhouse = df_clean_sub4[df_clean_sub4['ประเภททรัพย์'].str.contains('ทาวน์', na=False)]
                med_townhouse = float(df_townhouse['ราคา_ต่อ_ตรว'].median()) if not df_townhouse.empty else 0.0

                # =========================================================================
                # 1. STANDOUT BLOCK: โฟกัสพิเศษ ที่ดินเปล่า (Pure Vacant Land Spotlight)
                # =========================================================================
                df_pure_land = df_clean_sub4[df_clean_sub4['ประเภททรัพย์'] == 'ที่ดินเปล่า'].copy()

                if not df_pure_land.empty:
                    tot_pure_land = len(df_pure_land)
                    med_land = float(df_pure_land['ราคา_ต่อ_ตรว'].median())
                    med_land_sqw = float(df_pure_land['พื้นที่_ตารางวา'].median())
                    med_land_price = float(df_pure_land['ราคา'].median())
                    
                    small_plots = df_pure_land[df_pure_land['พื้นที่_ตารางวา'] < 100]
                    med_land_small = float(small_plots['ราคา_ต่อ_ตรว'].median()) if not small_plots.empty else 0.0

                    with st.container(border=True):
                        st.markdown(f"""
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; flex-wrap: wrap; gap: 8px;">
                            <div style="display: flex; align-items: center; gap: 10px;">
                                <div style="background: linear-gradient(135deg, #10b981, #059669); width: 36px; height: 36px; border-radius: 10px; display: flex; align-items: center; justify-content: center; box-shadow: 0 4px 12px rgba(16, 185, 129, 0.35); font-size: 18px; color: white;">
                                    <i class="fa-solid fa-tree"></i>
                                </div>
                                <div>
                                    <div style="font-size: 1.05rem; font-weight: 700; color: {'#f8fafc' if is_dark_mode else '#0f172a'}; letter-spacing: -0.2px;">
                                        โฟกัสพิเศษ: สถิติค่ากลาง "ที่ดินเปล่า" (Pure Vacant Land Spotlight)
                                    </div>
                                    <div style="font-size: 0.78rem; color: #94a3b8;">
                                        วิเคราะห์ราคาเนื้อที่ดินแท้จริง (ไม่มีสิ่งปลูกสร้าง) พร้อมการกระจายตัวตามขนาดแปลงและทำเลศักยภาพ
                                    </div>
                                </div>
                            </div>
                            <div style="background: rgba(16, 185, 129, 0.12); border: 1px solid rgba(16, 185, 129, 0.35); color: #10b981; padding: 4px 12px; border-radius: 20px; font-size: 0.8rem; font-weight: 700; display: inline-flex; align-items: center; gap: 6px;">
                                <span style="width: 7px; height: 7px; border-radius: 50%; background: #10b981; box-shadow: 0 0 8px #10b981;"></span>
                                พบ {tot_pure_land:,} แปลงในพื้นที่
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

                        col_land_c1, col_land_c2 = st.columns([5, 7])
                        
                        # Giant Standout Hero Card (แทนกราฟ 10 อันดับเดิม)
                        with col_land_c1:
                            hero_land_bg = 'linear-gradient(145deg, rgba(16, 185, 129, 0.12) 0%, rgba(5, 150, 105, 0.05) 100%)' if is_dark_mode else 'linear-gradient(145deg, #f0fdf4 0%, #ecfdf5 100%)'
                            hero_land_border = 'rgba(16, 185, 129, 0.35)' if is_dark_mode else '#bbf7d0'

                            st.markdown(f"""
                            <div style="background: {hero_land_bg}; border: 1.5px solid {hero_land_border}; border-radius: 16px; height: 360px; display: flex; flex-direction: column; justify-content: center; align-items: center; text-align: center; padding: 24px; box-shadow: 0 8px 24px rgba(16, 185, 129, 0.08); position: relative; overflow: hidden;">
                                <div style="position: absolute; top: -35px; right: -35px; width: 130px; height: 130px; background: radial-gradient(circle, rgba(16, 185, 129, 0.25) 0%, transparent 70%); border-radius: 50%;"></div>
                                <div style="background: rgba(16, 185, 129, 0.15); border: 1px solid rgba(16, 185, 129, 0.35); border-radius: 20px; padding: 6px 16px; font-size: 0.88rem; font-weight: 700; color: #10b981; margin-bottom: 14px; display: inline-flex; align-items: center; gap: 6px;">
                                    <span><i class="fa-solid fa-tag"></i></span> ค่ากลาง ราคา/ตร.ว. (ที่ดินเปล่า)
                                </div>
                                <div style="font-size: 3.4rem; font-weight: 900; color: #10b981; line-height: 1.1; letter-spacing: -1px; text-shadow: 0 4px 20px rgba(16, 185, 129, 0.3);">
                                    ฿{med_land:,.0f}
                                </div>
                                <div style="font-size: 1.1rem; font-weight: 600; color: #94a3b8; margin-top: 4px; margin-bottom: 18px;">
                                    บาท / ตารางวา
                                </div>
                                <div style="display: flex; gap: 8px; flex-wrap: wrap; justify-content: center;">
                                    <div style="background: {'rgba(255,255,255,0.06)' if is_dark_mode else '#ffffff'}; border: 1px solid {'rgba(255,255,255,0.1)' if is_dark_mode else '#e2e8f0'}; border-radius: 10px; padding: 6px 14px; font-size: 0.8rem; color: {'#cbd5e1' if is_dark_mode else '#475569'};">
                                        มัธยฐานทั้งพื้นที่ (<b>{tot_pure_land:,}</b> แปลง)
                                    </div>
                                    <div style="background: {'rgba(255,255,255,0.06)' if is_dark_mode else '#ffffff'}; border: 1px solid {'rgba(255,255,255,0.1)' if is_dark_mode else '#e2e8f0'}; border-radius: 10px; padding: 6px 14px; font-size: 0.8rem; color: {'#cbd5e1' if is_dark_mode else '#475569'};">
                                        แปลงมัธยฐาน <b>{med_land_sqw:,.1f}</b> ตร.ว. (~ <b>{med_land_sqw/400:.1f}</b> ไร่)
                                    </div>
                                </div>
                            </div>
                            """, unsafe_allow_html=True)

                        # Chart 2: Land Price by Plot Size Category
                        with col_land_c2:
                            def categorize_plot_size(sqw):
                                if sqw < 100:
                                    return "< 100 ตร.ว. (แปลงเล็ก)"
                                elif sqw <= 400:
                                    return "100-400 ตร.ว. (แปลงกลาง)"
                                elif sqw <= 2000:
                                    return "1-5 ไร่ (แปลงใหญ่)"
                                else:
                                    return "> 5 ไร่ (แปลงใหญ่มาก)"

                            df_pure_land['กลุ่มขนาด'] = df_pure_land['พื้นที่_ตารางวา'].apply(categorize_plot_size)
                            size_order = ["< 100 ตร.ว. (แปลงเล็ก)", "100-400 ตร.ว. (แปลงกลาง)", "1-5 ไร่ (แปลงใหญ่)", "> 5 ไร่ (แปลงใหญ่มาก)"]
                            size_stats = df_pure_land.groupby('กลุ่มขนาด').agg(
                                count=('ราคา_ต่อ_ตรว', 'count'),
                                median_u=('ราคา_ต่อ_ตรว', 'median')
                            ).reindex(size_order).dropna().reset_index()

                            max_land_u = float(size_stats['median_u'].max()) if not size_stats.empty and size_stats['median_u'].max() > 0 else 1000.0

                            fig_land_size = go.Figure(go.Bar(
                                x=size_stats['กลุ่มขนาด'],
                                y=size_stats['median_u'],
                                marker=dict(
                                    color=['#10b981', '#059669', '#0d9488', '#0284c7'],
                                    cornerradius=10,
                                    line=dict(width=1.2, color='rgba(255, 255, 255, 0.4)')
                                ),
                                text=[f"<b style='font-size:18px;'>฿{v:,.0f}</b><br><span style='font-size:11px;color:#94a3b8;'>({c:,} แปลง)</span>" for v, c in zip(size_stats['median_u'], size_stats['count'])],
                                textposition='outside',
                                cliponaxis=False,
                                textfont=dict(size=17, family="Noto Sans Thai", weight="bold"),
                                hovertemplate="กลุ่มขนาด: <b>%{x}</b><br>ค่ากลาง: <b>฿%{y:,.0f} / ตร.ว.</b><extra></extra>"
                            ))
                            fig_land_size.update_layout(
                                xaxis=dict(showgrid=False, tickfont=dict(size=11, family="Noto Sans Thai")),
                                yaxis=dict(
                                    title='ค่ากลาง ราคา/ตร.ว. (บาท)',
                                    range=[0, max_land_u * 1.35],
                                    showgrid=True,
                                    gridcolor='rgba(255,255,255,0.06)' if is_dark_mode else 'rgba(0,0,0,0.05)',
                                    zeroline=False
                                ),
                                title=dict(text='ค่ากลาง ราคา/ตร.ว. ที่ดินเปล่า จำแนกตามขนาดแปลงที่ดิน', font=dict(size=13.5, family="Noto Sans Thai", weight="bold")),
                                height=360,
                                margin=dict(t=45, b=15, l=10, r=10),
                                template=plotly_template,
                                plot_bgcolor='rgba(0,0,0,0)',
                                paper_bgcolor='rgba(0,0,0,0)'
                            )
                            st.plotly_chart(style_plotly_fig(fig_land_size), width="stretch", theme=None)

                # =========================================================================
                # 2. COMPARISON: ทรัพย์แนวราบพร้อมสิ่งปลูกสร้าง
                # =========================================================================
                st.markdown("---")
                st.markdown(f"""
                <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 6px;">
                    <span style="font-size: 1rem; font-weight: 700; color: {'#f8fafc' if is_dark_mode else '#0f172a'};">สถิติเปรียบเทียบทรัพย์แนวราบประเภทอื่นๆ (บ้านเดี่ยว / ทาวน์เฮ้าส์ / อาคารพาณิชย์)</span>
                </div>
                """, unsafe_allow_html=True)
                st.caption("หมายเหตุ: ทรัพย์สินกลุ่มนี้รวมมูลค่าสิ่งปลูกสร้าง (ตัวบ้าน/อาคาร) เข้าไปในราคาแล้ว ทำให้ค่าเฉลี่ยต่อตารางวาสูงกว่าที่ดินเปล่าตามธรรมชาติ")

                df_commercial = df_clean_sub4[df_clean_sub4['ประเภททรัพย์'].str.contains('อาคารพาณิชย์', na=False)]
                med_commercial = float(df_commercial['ราคา_ต่อ_ตรว'].median()) if not df_commercial.empty else 0.0

                st.markdown(f"""
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 14px; margin-top: 8px; margin-bottom: 20px;">
                    <div style="background: {card_bg_sub4}; border: 1px solid {card_border_sub4}; border-left: 4px solid #059669; border-radius: 12px; padding: 14px 16px; box-shadow: 0 4px 16px rgba(0,0,0,0.06);">
                        <div style="font-size: 0.78rem; font-weight: 700; color: #64748b; margin-bottom: 4px;"><i class="fa fa-home"></i> ค่ากลาง ราคา/ตร.ว. บ้านเดี่ยว</div>
                        <div style="font-size: 1.35rem; font-weight: 800; color: #059669;">฿{med_house:,.0f} <span style="font-size: 0.8rem; color: #94a3b8;">/ ตร.ว.</span></div>
                        <div style="font-size: 0.75rem; color: #94a3b8; margin-top: 2px;">{len(df_single_house):,} รายการ</div>
                    </div>
                    <div style="background: {card_bg_sub4}; border: 1px solid {card_border_sub4}; border-left: 4px solid #f59e0b; border-radius: 12px; padding: 14px 16px; box-shadow: 0 4px 16px rgba(0,0,0,0.06);">
                        <div style="font-size: 0.78rem; font-weight: 700; color: #64748b; margin-bottom: 4px;"><i class="fa fa-city"></i> ค่ากลาง ราคา/ตร.ว. ทาวน์เฮ้าส์</div>
                        <div style="font-size: 1.35rem; font-weight: 800; color: #f59e0b;">฿{med_townhouse:,.0f} <span style="font-size: 0.8rem; color: #94a3b8;">/ ตร.ว.</span></div>
                        <div style="font-size: 0.75rem; color: #94a3b8; margin-top: 2px;">{len(df_townhouse):,} รายการ</div>
                    </div>
                    <div style="background: {card_bg_sub4}; border: 1px solid {card_border_sub4}; border-left: 4px solid #f43f5e; border-radius: 12px; padding: 14px 16px; box-shadow: 0 4px 16px rgba(0,0,0,0.06);">
                        <div style="font-size: 0.78rem; font-weight: 700; color: #64748b; margin-bottom: 4px;"><i class="fa fa-store"></i> ค่ากลาง ราคา/ตร.ว. อาคารพาณิชย์</div>
                        <div style="font-size: 1.35rem; font-weight: 800; color: #f43f5e;">฿{med_commercial:,.0f} <span style="font-size: 0.8rem; color: #94a3b8;">/ ตร.ว.</span></div>
                        <div style="font-size: 0.75rem; color: #94a3b8; margin-top: 2px;">{len(df_commercial):,} รายการ</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                # Full-Width Chart: Median Price per Sq.Wah by Property Type
                prop_sqw_stats = df_clean_sub4.groupby('ประเภททรัพย์').agg(
                    count=('ราคา_ต่อ_ตรว', 'count'),
                    median_u_price=('ราคา_ต่อ_ตรว', 'median'),
                    median_total_price=('ราคา', 'median')
                ).reset_index()
                prop_sqw_stats = prop_sqw_stats[prop_sqw_stats['count'] >= 3].sort_values('median_u_price', ascending=False)

                fig_prop_sqw = go.Figure(go.Bar(
                    x=prop_sqw_stats['ประเภททรัพย์'],
                    y=prop_sqw_stats['median_u_price'],
                    marker=dict(
                        color=[PROP_TYPE_BAR_COLORS.get(t, '#3b82f6') for t in prop_sqw_stats['ประเภททรัพย์']],
                        cornerradius=10,
                        line=dict(width=1.2, color='rgba(255, 255, 255, 0.4)')
                    ),
                    text=[f"<b>฿{v:,.0f}</b><br><span style='font-size:9.5px;color:#94a3b8;'>({c:,} รายการ)</span>" for v, c in zip(prop_sqw_stats['median_u_price'], prop_sqw_stats['count'])],
                    textposition='outside',
                    textfont=dict(size=11, family="Noto Sans Thai"),
                    hovertemplate="ประเภท: <b>%{x}</b><br>ค่ากลาง ราคา/ตร.ว.: <b>฿%{y:,.0f}</b><extra></extra>"
                ))
                if overall_median_sqw > 0:
                    fig_prop_sqw.add_hline(
                        y=overall_median_sqw,
                        line_dash="dot",
                        line_color="#ef4444",
                        line_width=2,
                        annotation_text=f"ค่ากลางตลาด: ฿{overall_median_sqw:,.0f}/ตร.ว.",
                        annotation_position="top right",
                        annotation_font=dict(size=11, color="#ef4444", family="Noto Sans Thai", weight="bold")
                    )
                fig_prop_sqw.update_layout(
                    title=dict(text='ค่ากลาง ราคาต่อตารางวา (Median Price / Sq.Wah) จำแนกตามแต่ละประเภททรัพย์สิน', font=dict(size=15, family="Noto Sans Thai")),
                    yaxis=dict(title='ค่ากลาง ราคา/ตร.ว. (บาท)', showgrid=True, gridcolor='rgba(255,255,255,0.06)' if is_dark_mode else 'rgba(0,0,0,0.05)', zeroline=False),
                    xaxis=dict(showgrid=False, tickfont=dict(size=11, family="Noto Sans Thai")),
                    height=500,
                    margin=dict(t=50, b=40, l=10, r=10),
                    template=plotly_template,
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)'
                )
                st.plotly_chart(style_plotly_fig(fig_prop_sqw), width="stretch", theme=None)

                st.markdown("---")
                col_sub4_3, col_sub4_4 = st.columns(2)

                # Row 2 Left: Dynamic Drilldown Locations
                with col_sub4_3:
                    drill_col = 'ตำบล' if sel_district != "ทั้งหมดทุกอำเภอ/เขต" else ('อำเภอ' if sel_province != "ทั้งหมดทุกจังหวัด" else 'จังหวัด')
                    drill_label = f"ตำบล/แขวง ใน {sel_district}" if sel_district != "ทั้งหมดทุกอำเภอ/เขต" else (f"อำเภอ/เขต ใน {sel_province}" if sel_province != "ทั้งหมดทุกจังหวัด" else "จังหวัด")

                    loc_sqw_stats = df_clean_sub4.groupby(drill_col).agg(
                        count=('ราคา_ต่อ_ตรว', 'count'),
                        median_u_price=('ราคา_ต่อ_ตรว', 'median')
                    ).reset_index()
                    loc_sqw_stats = loc_sqw_stats[loc_sqw_stats['count'] >= 3].sort_values('median_u_price', ascending=False).head(10)

                    fig_loc_sqw = go.Figure(go.Bar(
                        x=loc_sqw_stats['median_u_price'],
                        y=loc_sqw_stats[drill_col],
                        orientation='h',
                        marker=dict(
                            color=loc_sqw_stats['median_u_price'],
                            colorscale=[[0, '#06b6d4'], [0.45, '#3b82f6'], [1, '#4f46e5']],
                            cornerradius=10,
                            line=dict(width=1.2, color='rgba(255, 255, 255, 0.4)')
                        ),
                        text=[f"฿{v:,.0f} ({c:,} รายการ)" for v, c in zip(loc_sqw_stats['median_u_price'], loc_sqw_stats['count'])],
                        textposition='outside',
                        textfont=dict(size=10.5, family="Noto Sans Thai", weight="bold"),
                        hovertemplate=f"{drill_label}: <b>%{{y}}</b><br>ค่ากลาง ราคา/ตร.ว.: <b>฿%{{x:,.0f}}</b><extra></extra>"
                    ))
                    fig_loc_sqw.update_layout(
                        yaxis=dict(autorange="reversed"),
                        xaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.06)' if is_dark_mode else 'rgba(0,0,0,0.05)', zeroline=False),
                        title=dict(text=f'10 อันดับ {drill_label} ที่มีค่ากลาง ราคา/ตร.ว. สูงสุด', font=dict(size=14, family="Noto Sans Thai")),
                        height=460,
                        margin=dict(t=50, b=20, l=10, r=10),
                        template=plotly_template,
                        plot_bgcolor='rgba(0,0,0,0)',
                        paper_bgcolor='rgba(0,0,0,0)'
                    )
                    st.plotly_chart(style_plotly_fig(fig_loc_sqw), width="stretch", theme=None)

                # Row 2 Right: Summary Table
                with col_sub4_4:
                    st.markdown("##### ตารางสรุปค่ากลาง ราคา/ตร.ว. และเนื้อที่ดินเฉลี่ยรายประเภททรัพย์")
                    df_table_sqw = df_clean_sub4.groupby('ประเภททรัพย์').agg(
                        รายการ=('ราคา_ต่อ_ตรว', 'count'),
                        ราคากลาง_ตรว=('ราคา_ต่อ_ตรว', 'median'),
                        ขนาดที่ดิน_มัธยฐาน=('พื้นที่_ตารางวา', 'median'),
                        ราคากลางรวม=('ราคา', 'median')
                    ).reset_index().sort_values('ราคากลาง_ตรว', ascending=False)

                    df_table_sqw['ค่ากลาง ราคา/ตร.ว.'] = df_table_sqw['ราคากลาง_ตรว'].apply(lambda v: f"฿{v:,.0f}")
                    df_table_sqw['เนื้อที่ดินเฉลี่ย (ตร.ว.)'] = df_table_sqw['ขนาดที่ดิน_มัธยฐาน'].apply(lambda v: f"{v:,.1f} ตร.ว.")
                    df_table_sqw['ราคากลางรวม (บาท)'] = df_table_sqw['ราคากลางรวม'].apply(lambda v: f"฿{v:,.0f}")
                    df_table_sqw['จำนวนทรัพย์ (รายการ)'] = df_table_sqw['รายการ'].apply(lambda v: f"{v:,}")

                    display_tbl = df_table_sqw[['ประเภททรัพย์', 'จำนวนทรัพย์ (รายการ)', 'ค่ากลาง ราคา/ตร.ว.', 'เนื้อที่ดินเฉลี่ย (ตร.ว.)', 'ราคากลางรวม (บาท)']]
                    st.dataframe(display_tbl, width="stretch", hide_index=True, height=410)
            else:
                st.info("ℹ️ ไม่พบข้อมูลทรัพย์สินที่มีเนื้อที่ดินในขอบเขตทำเลที่เลือก")

        # =========================================================================
        # CASE B: พื้นที่ใช้สอย (ค่ากลาง ราคา/ตร.ม.)
        # =========================================================================
        with tab_usable_sub4:
            def parse_usable_sqm(val):
                if pd.isna(val) or val is None:
                    return np.nan
                try:
                    val_str = str(val).replace(',', '').strip()
                    v = float(val_str)
                    return v if 10.0 <= v <= 5000.0 else np.nan
                except:
                    return np.nan

            # Focus on properties with usable area (exclude vacant land)
            is_usable_sub4 = (df_scope['ประเภททรัพย์'] != 'ที่ดินเปล่า') & (df_scope['ราคา'].notna()) & (df_scope['ราคา'] > 0)
            df_usable_sub4 = df_scope[is_usable_sub4].copy()

            if not df_usable_sub4.empty and 'พื้นที่ใช้สอย (ตร.ม.)' in df_usable_sub4.columns:
                df_usable_sub4['พื้นที่ใช้สอย_ตรม'] = df_usable_sub4['พื้นที่ใช้สอย (ตร.ม.)'].apply(parse_usable_sqm)
                df_clean_usable = df_usable_sub4[df_usable_sub4['พื้นที่ใช้สอย_ตรม'].notna()].copy()
                
                if not df_clean_usable.empty:
                    df_clean_usable['ราคา_ต่อ_ตรม'] = df_clean_usable['ราคา'] / df_clean_usable['พื้นที่ใช้สอย_ตรม']
                    df_clean_usable = df_clean_usable[(df_clean_usable['ราคา_ต่อ_ตรม'] >= 1000) & (df_clean_usable['ราคา_ต่อ_ตรม'] <= 600000)].copy()

                tot_usable_units = len(df_clean_usable)

                if tot_usable_units > 0:
                    overall_usable_psqm = float(df_clean_usable['ราคา_ต่อ_ตรม'].median())
                    
                    df_condo_u = df_clean_usable[df_clean_usable['ประเภททรัพย์'].str.contains('ห้องชุด|คอนโด', na=False)]
                    med_condo_psqm = float(df_condo_u['ราคา_ต่อ_ตรม'].median()) if not df_condo_u.empty else 0.0

                    df_house_u = df_clean_usable[df_clean_usable['ประเภททรัพย์'].str.contains('บ้านเดี่ยว', na=False)]
                    med_house_psqm = float(df_house_u['ราคา_ต่อ_ตรม'].median()) if not df_house_u.empty else 0.0

                    df_th_u = df_clean_usable[df_clean_usable['ประเภททรัพย์'].str.contains('ทาวน์', na=False)]
                    med_th_psqm = float(df_th_u['ราคา_ต่อ_ตรม'].median()) if not df_th_u.empty else 0.0

                    # Usable Area KPI Cards
                    st.markdown(f"""
                    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 14px; margin-top: 8px; margin-bottom: 20px;">
                        <div style="background: {card_bg_sub4}; border: 1px solid {card_border_sub4}; border-left: 4px solid #06b6d4; border-radius: 12px; padding: 14px 16px; box-shadow: 0 4px 16px rgba(0,0,0,0.06);">
                            <div style="font-size: 0.78rem; font-weight: 700; color: #64748b; margin-bottom: 4px;"><i class="fa fa-chart-line"></i> ค่ากลาง ราคา/ตร.ม. (ภาพรวม)</div>
                            <div style="font-size: 1.35rem; font-weight: 800; color: #06b6d4;">฿{overall_usable_psqm:,.0f} <span style="font-size: 0.8rem; color: #94a3b8;">/ ตร.ม.</span></div>
                            <div style="font-size: 0.75rem; color: #94a3b8; margin-top: 2px;">รวม {tot_usable_units:,} รายการ</div>
                        </div>
                        <div style="background: {card_bg_sub4}; border: 1px solid {card_border_sub4}; border-left: 4px solid #8b5cf6; border-radius: 12px; padding: 14px 16px; box-shadow: 0 4px 16px rgba(0,0,0,0.06);">
                            <div style="font-size: 0.78rem; font-weight: 700; color: #64748b; margin-bottom: 4px;"><i class="fa fa-building"></i> ค่ากลาง ราคา/ตร.ม. คอนโด</div>
                            <div style="font-size: 1.35rem; font-weight: 800; color: #8b5cf6;">฿{med_condo_psqm:,.0f} <span style="font-size: 0.8rem; color: #94a3b8;">/ ตร.ม.</span></div>
                            <div style="font-size: 0.75rem; color: #94a3b8; margin-top: 2px;">{len(df_condo_u):,} รายการ</div>
                        </div>
                        <div style="background: {card_bg_sub4}; border: 1px solid {card_border_sub4}; border-left: 4px solid #059669; border-radius: 12px; padding: 14px 16px; box-shadow: 0 4px 16px rgba(0,0,0,0.06);">
                            <div style="font-size: 0.78rem; font-weight: 700; color: #64748b; margin-bottom: 4px;"><i class="fa fa-home"></i> ค่ากลาง ราคา/ตร.ม. บ้านเดี่ยว</div>
                            <div style="font-size: 1.35rem; font-weight: 800; color: #059669;">฿{med_house_psqm:,.0f} <span style="font-size: 0.8rem; color: #94a3b8;">/ ตร.ม.</span></div>
                            <div style="font-size: 0.75rem; color: #94a3b8; margin-top: 2px;">{len(df_house_u):,} รายการ</div>
                        </div>
                        <div style="background: {card_bg_sub4}; border: 1px solid {card_border_sub4}; border-left: 4px solid #f59e0b; border-radius: 12px; padding: 14px 16px; box-shadow: 0 4px 16px rgba(0,0,0,0.06);">
                            <div style="font-size: 0.78rem; font-weight: 700; color: #64748b; margin-bottom: 4px;"><i class="fa fa-city"></i> ค่ากลาง ราคา/ตร.ม. ทาวน์เฮ้าส์</div>
                            <div style="font-size: 1.35rem; font-weight: 800; color: #f59e0b;">฿{med_th_psqm:,.0f} <span style="font-size: 0.8rem; color: #94a3b8;">/ ตร.ม.</span></div>
                            <div style="font-size: 0.75rem; color: #94a3b8; margin-top: 2px;">{len(df_th_u):,} รายการ</div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                    # Full-Width Chart: Median Price per Sq.M. by Property Type
                    prop_sqm_stats = df_clean_usable.groupby('ประเภททรัพย์').agg(
                        count=('ราคา_ต่อ_ตรม', 'count'),
                        median_u_price=('ราคา_ต่อ_ตรม', 'median'),
                        median_total_price=('ราคา', 'median')
                    ).reset_index()
                    prop_sqm_stats = prop_sqm_stats[prop_sqm_stats['count'] >= 3].sort_values('median_u_price', ascending=False)

                    fig_prop_sqm = go.Figure(go.Bar(
                        x=prop_sqm_stats['ประเภททรัพย์'],
                        y=prop_sqm_stats['median_u_price'],
                        marker=dict(
                            color=[PROP_TYPE_BAR_COLORS.get(t, '#3b82f6') for t in prop_sqm_stats['ประเภททรัพย์']],
                            cornerradius=10,
                            line=dict(width=1.2, color='rgba(255, 255, 255, 0.4)')
                        ),
                        text=[f"<b>฿{v:,.0f}</b><br><span style='font-size:9.5px;color:#94a3b8;'>({c:,} รายการ)</span>" for v, c in zip(prop_sqm_stats['median_u_price'], prop_sqm_stats['count'])],
                        textposition='outside',
                        textfont=dict(size=11, family="Noto Sans Thai"),
                        hovertemplate="ประเภท: <b>%{x}</b><br>ค่ากลาง ราคา/ตร.ม.: <b>฿%{y:,.0f}</b><extra></extra>"
                    ))
                    if overall_usable_psqm > 0:
                        fig_prop_sqm.add_hline(
                            y=overall_usable_psqm,
                            line_dash="dot",
                            line_color="#ef4444",
                            line_width=2,
                            annotation_text=f"ค่ากลางตลาด: ฿{overall_usable_psqm:,.0f}/ตร.ม.",
                            annotation_position="top right",
                            annotation_font=dict(size=11, color="#ef4444", family="Noto Sans Thai", weight="bold")
                        )
                    fig_prop_sqm.update_layout(
                        title=dict(text='ค่ากลาง ราคาต่อตารางเมตร (Median Price / Sq.M.) จำแนกตามแต่ละประเภททรัพย์สิน', font=dict(size=15, family="Noto Sans Thai")),
                        yaxis=dict(title='ค่ากลาง ราคา/ตร.ม. (บาท)', showgrid=True, gridcolor='rgba(255,255,255,0.06)' if is_dark_mode else 'rgba(0,0,0,0.05)', zeroline=False),
                        xaxis=dict(showgrid=False, tickfont=dict(size=11, family="Noto Sans Thai")),
                        height=500,
                        margin=dict(t=50, b=40, l=10, r=10),
                        template=plotly_template,
                        plot_bgcolor='rgba(0,0,0,0)',
                        paper_bgcolor='rgba(0,0,0,0)'
                    )
                    st.plotly_chart(style_plotly_fig(fig_prop_sqm), width="stretch", theme=None)

                    st.markdown("---")
                    col_sqm3, col_sqm4 = st.columns(2)

                    # Row 2 Left: Dynamic Drilldown Locations by ฿/Sq.M.
                    with col_sqm3:
                        drill_usable_col = 'ตำบล' if sel_district != "ทั้งหมดทุกอำเภอ/เขต" else ('อำเภอ' if sel_province != "ทั้งหมดทุกจังหวัด" else 'จังหวัด')
                        drill_usable_label = f"ตำบล/แขวง ใน {sel_district}" if sel_district != "ทั้งหมดทุกอำเภอ/เขต" else (f"อำเภอ/เขต ใน {sel_province}" if sel_province != "ทั้งหมดทุกจังหวัด" else "จังหวัด")

                        loc_sqm_stats = df_clean_usable.groupby(drill_usable_col).agg(
                            count=('ราคา_ต่อ_ตรม', 'count'),
                            median_psqm=('ราคา_ต่อ_ตรม', 'median')
                        ).reset_index()
                        loc_sqm_stats = loc_sqm_stats[loc_sqm_stats['count'] >= 3].sort_values('median_psqm', ascending=False).head(10)

                        fig_loc_sqm = go.Figure(go.Bar(
                            x=loc_sqm_stats['median_psqm'],
                            y=loc_sqm_stats[drill_usable_col],
                            orientation='h',
                            marker=dict(
                                color=loc_sqm_stats['median_psqm'],
                                colorscale=[[0, '#38bdf8'], [0.5, '#6366f1'], [1, '#ec4899']],
                                cornerradius=10,
                                line=dict(width=1.2, color='rgba(255, 255, 255, 0.4)')
                            ),
                            text=[f"฿{v:,.0f} ({c:,} รายการ)" for v, c in zip(loc_sqm_stats['median_psqm'], loc_sqm_stats['count'])],
                            textposition='outside',
                            textfont=dict(size=10.5, family="Noto Sans Thai", weight="bold"),
                            hovertemplate=f"{drill_usable_label}: <b>%{{y}}</b><br>ค่ากลาง ราคา/ตร.ม.: <b>฿%{{x:,.0f}}</b><extra></extra>"
                        ))
                        fig_loc_sqm.update_layout(
                            yaxis=dict(autorange="reversed"),
                            xaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.06)' if is_dark_mode else 'rgba(0,0,0,0.05)', zeroline=False),
                            title=dict(text=f'10 อันดับ {drill_usable_label} ที่มีค่ากลาง ราคา/ตร.ม. สูงสุด', font=dict(size=14, family="Noto Sans Thai")),
                            height=460,
                            margin=dict(t=50, b=20, l=10, r=10),
                            template=plotly_template,
                            plot_bgcolor='rgba(0,0,0,0)',
                            paper_bgcolor='rgba(0,0,0,0)'
                        )
                        st.plotly_chart(style_plotly_fig(fig_loc_sqm), width="stretch", theme=None)

                    # Row 2 Right: Summary Table
                    with col_sqm4:
                        st.markdown("##### ตารางสรุปค่ากลาง ราคา/ตร.ม. และพื้นที่ใช้สอยเฉลี่ยรายประเภททรัพย์")
                        df_table_sqm = df_clean_usable.groupby('ประเภททรัพย์').agg(
                            รายการ=('ราคา_ต่อ_ตรม', 'count'),
                            ราคากลาง_ตรม=('ราคา_ต่อ_ตรม', 'median'),
                            ขนาดใช้สอย_มัธยฐาน=('พื้นที่ใช้สอย_ตรม', 'median'),
                            ราคากลางรวม=('ราคา', 'median')
                        ).reset_index().sort_values('ราคากลาง_ตรม', ascending=False)

                        df_table_sqm['ค่ากลาง ราคา/ตร.ม.'] = df_table_sqm['ราคากลาง_ตรม'].apply(lambda v: f"฿{v:,.0f}")
                        df_table_sqm['พื้นที่ใช้สอยเฉลี่ย (ตร.ม.)'] = df_table_sqm['ขนาดใช้สอย_มัธยฐาน'].apply(lambda v: f"{v:,.1f} ตร.ม.")
                        df_table_sqm['ราคากลางรวม (บาท)'] = df_table_sqm['ราคากลางรวม'].apply(lambda v: f"฿{v:,.0f}")
                        df_table_sqm['จำนวนทรัพย์ (รายการ)'] = df_table_sqm['รายการ'].apply(lambda v: f"{v:,}")

                        display_tbl_sqm = df_table_sqm[['ประเภททรัพย์', 'จำนวนทรัพย์ (รายการ)', 'ค่ากลาง ราคา/ตร.ม.', 'พื้นที่ใช้สอยเฉลี่ย (ตร.ม.)', 'ราคากลางรวม (บาท)']]
                        st.dataframe(display_tbl_sqm, width="stretch", hide_index=True, height=410)
                else:
                    st.info("ℹ️ ไม่พบข้อมูลพื้นที่ใช้สอยในขอบเขตทำเลที่เลือก")
            else:
                st.info("ไม่พบข้อมูลทรัพย์สินที่มีพื้นที่ใช้สอยในขอบเขตทำเลที่เลือก")



# ----- TAB 4: PROPERTY LISTING -----
with tab4:
    st.markdown(f"### <i class='fa-solid fa-table-list' style='color:#059669; margin-right:8px;'></i>รายการทรัพย์สินที่ค้นพบ ({len(df_filtered):,} รายการ)", unsafe_allow_html=True)
    
    if df_filtered.empty:
        st.warning("ไม่พบข้อมูลตามเงื่อนไข")
    else:
        col_s1, col_s2 = st.columns([3, 2])
        with col_s1:
            # Search Box to filter Tab 4 Property Listing table (รหัสทรัพย์ / ชื่อโครงการ / ชื่อประกาศ)
            tab4_search_query = st.text_input(
                "ค้นหารหัสทรัพย์ / ชื่อโครงการ / ชื่อประกาศ",
                icon=":material/search:",
                value="",
                placeholder="พิมพ์รหัสทรัพย์ (เช่น 12345), ชื่อโครงการ หรือชื่อประกาศ...",
                key="tab4_property_listing_search"
            )
            
        with col_s2:
            display_limit = st.number_input(
                "จำนวนรายการที่ต้องการแสดง (Rows)",
                icon=":material/format_list_numbered:",
                min_value=0,
                max_value=100000,
                value=0,
                step=50,
                key="tab4_direct_row_limit",
                help="กรอกจำนวนแถวที่ต้องการแสดงในตาราง (ค่าเริ่มต้นคือ 0 เพื่อแสดงเฉพาะหัวข้อคอลัมน์เพื่อความรวดเร็ว)"
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
            st.caption("ปัจจุบันแสดงเฉพาะ **หัวข้อคอลัมน์** เพื่อความเร็วสูงสุด (พิมพ์ค้นหารหัสทรัพย์ หรือเลือกจำนวนแถวที่ต้องการแสดง)")
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

# reload trigger: 2026-09-15 13:48:00 (Removed outer track border to eliminate nested border look)
