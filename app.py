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
from pathlib import Path
import base64

from dashboard_metrics import build_kpi_summary_text
from bubble_chart import generate_3d_glossy_bubble_chart_html
import sam_analytics
from sam_analytics import render_same_project_comparison

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

def get_region_by_province(prov):
    p_str = str(prov).strip()
    for region, p_list in REGION_PROVINCES.items():
        for p in p_list:
            if p in p_str:
                return region
    return 'อื่นๆ / ไม่ระบุ'

def get_dataset_month_year(df):
    """Formats the dataset date into Thai Month & Year (e.g. สิงหาคม 2569) and date range from start to latest extraction date."""
    thai_full_months = [
        'มกราคม', 'กุมภาพันธ์', 'มีนาคม', 'เมษายน', 'พฤษภาคม', 'มิถุนายน',
        'กรกฎาคม', 'สิงหาคม', 'กันยายน', 'ตุลาคม', 'พฤศจิกายน', 'ธันวาคม'
    ]
    thai_short_months = ['ม.ค.', 'ก.พ.', 'มี.ค.', 'เม.ย.', 'พ.ค.', 'มิ.ย.', 'ก.ค.', 'ส.ค.', 'ก.ย.', 'ต.ค.', 'พ.ย.', 'ธ.ค.']
    
    if df is not None and not df.empty and 'วันที่ดึงข้อมูล' in df.columns:
        s_date = df['วันที่ดึงข้อมูล'].dropna().astype(str).str.strip()
        s_date = s_date[~s_date.isin(['', 'nan', 'None'])]
        if not s_date.empty:
            try:
                dts = pd.to_datetime(s_date, dayfirst=True, format='mixed', errors='coerce').dropna()
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
def convert_df_to_csv(df):
    """Cached CSV generator to prevent blocking rerun loops."""
    if df is None or df.empty:
        return b""
    return df.to_csv(index=False).encode('utf-8-sig')

@st.cache_data
def convert_df_to_excel(df):
    """Cached Excel generator to prevent blocking rerun loops."""
    if df is None or df.empty:
        return b""
    excel_buffer = io.BytesIO()
    with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Assets')
    return excel_buffer.getvalue()

def render_import_export_section(df_to_export, filename_prefix="npa_data", key_suffix=""):
    """Renders side-by-side Import (Excel/CSV) and Export (Excel/CSV) UI."""
    st.markdown("<br/>", unsafe_allow_html=True)
    st.markdown("##### 📥 นำเข้าและส่งออกข้อมูล (Import & Export Data)")
    col_imp, col_exp = st.columns(2)
    
    # Left: Import File
    with col_imp:
        st.markdown("###### 📂 นำเข้าข้อมูลเพิ่มเติม (Import File)")
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
                    st.success(f"✅ อ่านไฟล์สำเร็จ ({len(u_df):,} รายการ)")
                    if st.button("➕ รวมเข้ากับฐานข้อมูลหลัก", key=f"btn_apply_import_{key_suffix}", use_container_width=True):
                        st.session_state["imported_custom_df"] = u_df
                        st.success("นำเข้าข้อมูลสำเร็จแล้ว!")
                        st.rerun()
            except Exception as ex:
                st.error(f"❌ อ่านไฟล์ไม่สำเร็จ: {ex}")
                
        if "imported_custom_df" in st.session_state and st.session_state["imported_custom_df"] is not None:
            st.info(f"📌 มีข้อมูลนำเข้าเพิ่มอยู่ {len(st.session_state['imported_custom_df']):,} รายการ")
            if st.button("🗑️ ล้างข้อมูลที่นำเข้า", key=f"btn_clear_import_{key_suffix}", use_container_width=True):
                del st.session_state["imported_custom_df"]
                st.rerun()

    # Right: Export File
    with col_exp:
        st.markdown("###### 📤 ส่งออกข้อมูลในตาราง (Export Data)")
        if df_to_export is not None and not df_to_export.empty:
            n_rows = len(df_to_export)
            st.caption(f"📊 ข้อมูลพร้อมส่งออกทั้งหมด **{n_rows:,}** รายการ")
            
            c_exp1, c_exp2 = st.columns(2)
            with c_exp1:
                st.download_button(
                    label="📄 ส่งออก CSV (.csv) ⚡",
                    data=convert_df_to_csv(df_to_export),
                    file_name=f"{filename_prefix}.csv",
                    mime="text/csv",
                    use_container_width=True,
                    key=f"btn_export_csv_{key_suffix}",
                    help="ดาวน์โหลดทันที (เสี้ยววินาที) รองรับภาษาไทย UTF-8 เปิดใน Microsoft Excel ได้โดยตรง"
                )
            with c_exp2:
                excel_key = f"excel_data_{key_suffix}"
                excel_rows_key = f"excel_rows_{key_suffix}"
                
                # Check if Excel was already prepared for this exact row count
                if st.session_state.get(excel_rows_key) == n_rows and excel_key in st.session_state:
                    st.download_button(
                        label="📊 ดาวน์โหลด Excel (.xlsx)",
                        data=st.session_state[excel_key],
                        file_name=f"{filename_prefix}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True,
                        key=f"btn_export_excel_{key_suffix}"
                    )
                else:
                    if st.button("📊 สร้างไฟล์ Excel (.xlsx)", key=f"btn_prep_excel_{key_suffix}", use_container_width=True, help="คลิกเพื่อเริ่มแปลงข้อมูลเป็นไฟล์ Excel (.xlsx)"):
                        with st.spinner(f"⏳ กำลังแปลงข้อมูล {n_rows:,} รายการเป็นไฟล์ Excel..."):
                            excel_bytes = convert_df_to_excel(df_to_export)
                            st.session_state[excel_key] = excel_bytes
                            st.session_state[excel_rows_key] = n_rows
                            st.rerun()
                    if n_rows > 10000:
                        st.caption("💡 แนะนำ **CSV** สำหรับไฟล์ขนาดใหญ่ จะดาวน์โหลดได้ทันที")
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
        
    if match_type and str(match_type).strip() != '' and str(match_type).lower() != 'nan':
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
st.set_page_config(
    page_title="All Asset NPA Dashboard",
    page_icon="📊",
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

if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

if not st.session_state['logged_in']:
    # Inject CSS for a beautiful login interface (use st.markdown with unsafe_allow_html for global DOM injection)
    login_css = """<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
<style>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=Sarabun:wght@300;400;500;600;700&display=swap');

html, body, .stApp {
    font-family: 'Outfit', 'Sarabun', sans-serif;
    background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 50%, #e2e8f0 100%) !important;
    height: 100vh !important;
    overflow: hidden !important;
}

div[data-testid="stAppViewContainer"] {
    background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 50%, #e2e8f0 100%) !important;
}

div[data-testid="stForm"] {
    background: #ffffff !important;
    border: 1px solid #e2e8f0 !important;
    border-radius: 24px !important;
    padding: 40px !important;
    box-shadow: 0 20px 45px rgba(15, 23, 42, 0.08), 0 1px 3px rgba(15, 23, 42, 0.04) !important;
    max-width: 440px !important;
    margin: 12vh auto auto auto !important;
}

div[data-testid="stForm"] div[data-baseweb="input"],
div[data-testid="stForm"] div[data-baseweb="base-input"],
div[data-testid="stTextInput"] div[data-baseweb="input"],
div[data-testid="stTextInput"] div[data-baseweb="base-input"],
.stTextInput div[data-baseweb="input"],
.stTextInput div[data-baseweb="base-input"] {
    border-radius: 12px !important;
    border: 1.5px solid #cbd5e1 !important;
    background-color: #f8fafc !important;
    background: #f8fafc !important;
    box-shadow: inset 0 1px 2px rgba(0, 0, 0, 0.04) !important;
    transition: all 0.25s ease !important;
}

div[data-testid="stForm"] div[data-baseweb="input"] > div,
div[data-testid="stTextInput"] div[data-baseweb="input"] > div,
div[data-testid="stForm"] div[data-baseweb="base-input"] > div {
    background-color: transparent !important;
    background: transparent !important;
    border: none !important;
}

div[data-testid="stForm"] div[data-baseweb="input"]:focus-within,
div[data-testid="stForm"] div[data-baseweb="base-input"]:focus-within,
div[data-testid="stTextInput"] div[data-baseweb="input"]:focus-within {
    border-color: #3b82f6 !important;
    box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.2) !important;
    background-color: #ffffff !important;
    background: #ffffff !important;
}

div[data-testid="stForm"] input,
div[data-testid="stForm"] input[type="password"],
div[data-testid="stForm"] input[type="text"],
div[data-testid="stTextInput"] input,
.stTextInput input {
    background-color: transparent !important;
    background: transparent !important;
    color: #0f172a !important;
    -webkit-text-fill-color: #0f172a !important;
    -webkit-opacity: 1 !important;
    opacity: 1 !important;
    caret-color: #2563eb !important;
    border: none !important;
    height: 52px !important;
    font-size: 1.25rem !important;
    letter-spacing: 3px !important;
    text-align: center !important;
    width: 100% !important;
    font-weight: 700 !important;
}

div[data-testid="stForm"] input::placeholder,
div[data-testid="stTextInput"] input::placeholder {
    color: #94a3b8 !important;
    -webkit-text-fill-color: #94a3b8 !important;
    letter-spacing: normal !important;
    font-size: 0.95rem !important;
    font-weight: 400 !important;
}

div[data-testid="stForm"] div[data-testid="stCheckbox"] label span {
    color: #475569 !important;
    font-size: 0.88rem !important;
}

div[data-testid="stFormSubmitButton"] button {
    background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%) !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: 12px !important;
    font-weight: 600 !important;
    font-size: 1.1rem !important;
    height: 50px !important;
    width: 100% !important;
    box-shadow: 0 8px 20px rgba(37, 99, 235, 0.25) !important;
    transition: all 0.3s ease !important;
    margin-top: 15px !important;
}

div[data-testid="stFormSubmitButton"] button:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 12px 25px rgba(37, 99, 235, 0.4) !important;
    background: linear-gradient(135deg, #1d4ed8 0%, #1e40af 100%) !important;
    color: #ffffff !important;
}

div[data-testid="stFormSubmitButton"] button:active {
    transform: translateY(0) !important;
}

section[data-testid="stSidebar"], header, footer {
    display: none !important;
    visibility: hidden !important;
}
</style>"""
    st.html(login_css)
    
    logo_path = Path("assets/logo.png")
    if logo_path.exists():
        with open(logo_path, "rb") as img_f:
            logo_b64 = base64.b64encode(img_f.read()).decode("utf-8")
        logo_html = f'<img src="data:image/png;base64,{logo_b64}" style="width: 130px; height: 130px; object-fit: contain; margin-bottom: 16px; filter: drop-shadow(0 8px 24px rgba(37, 99, 235, 0.2));">'
    else:
        logo_html = '<div style="display: inline-flex; align-items: center; justify-content: center; width: 90px; height: 90px; background: #eff6ff; border-radius: 50%; margin-bottom: 20px; border: 1px solid #bfdbfe;"><i class="fa-solid fa-lock" style="font-size: 2.5rem; color: #2563eb;"></i></div>'

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
                    st.rerun()
                else:
                    err_html = """<div style="background-color: #fef2f2; color: #dc2626; border: 1px solid #fecaca; border-radius: 10px; padding: 12px; margin-top: 15px; font-size: 0.9rem; text-align: center; font-weight: 500;">
<i class="fa-solid fa-triangle-exclamation"></i> รหัสผ่านไม่ถูกต้อง กรุณาลองใหม่อีกครั้ง
</div>"""
                    st.html(err_html)
    st.stop()


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
        "BAM", "SAM", "KBANK", "SCB", "KTB", "GHB", "GSB",
        "Chayo555", "NaYoo", "Baania", "ZmyHome", "Taladnudbaan", "จุดอ้างอิง"
    ]
    
    atlas_width = len(companies) * icon_size
    atlas_height = icon_size
    
    try:
        from PIL import Image, ImageDraw
        import io, base64
        
        atlas = Image.new("RGBA", (atlas_width, atlas_height), (0, 0, 0, 0))
        
        alias_map = {
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
            'taladnudbaan': 'taladnudbaan.png',
            'led': 'led.png'
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
                
                comp_key = name.lower()
                fname = alias_map.get(comp_key, f"{comp_key}.png")
                p = os.path.join("assets", "logos", fname)
                
                if os.path.exists(p) and not fname.endswith(".svg"):
                    try:
                        logo = Image.open(p).convert("RGBA")
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
    """Generates optimized base64 dictionary of all 11 company logos for Leaflet pins with healthy margin."""
    global _LEAFLET_LOGO_CACHE
    if _LEAFLET_LOGO_CACHE:
        return _LEAFLET_LOGO_CACHE
        
    alias_map = {
        'bam': 'bam.png',
        'sam': 'sam.png',
        'kbank': 'kbank.png',
        'scb': 'scb.png',
        'ktb': 'ktb.png',
        'ghb': 'ghb.png',
        'gsb': 'gsb.png',
        'chayo555': 'chayo555.png',
        'nayoo': 'nayoo.png',
        'baania': 'baania.png',
        'zmyhome': 'zmyhome.png',
        'taladnudbaan': 'taladnudbaan.png',
        'led': 'led.png'
    }
    
    companies = ['BAM', 'SAM', 'KBANK', 'SCB', 'KTB', 'GHB', 'GSB', 'Chayo555', 'NaYoo', 'Baania', 'ZmyHome', 'Taladnudbaan', 'LED']
    logo_dict = {}
    
    from PIL import Image
    import io, base64
    
    for c in companies:
        comp_key = c.lower()
        fname = alias_map.get(comp_key, f"{comp_key}.png")
        p = os.path.join("assets", "logos", fname)
        
        if os.path.exists(p):
            try:
                im = Image.open(p).convert("RGBA")
                # Tight crop + center in square canvas
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
                logo_dict[c] = f"data:image/png;base64,{b64}"
                logo_dict[c.lower()] = logo_dict[c]
                logo_dict[c.upper()] = logo_dict[c]
            except Exception:
                pass
                
    _LEAFLET_LOGO_CACHE = logo_dict
    return logo_dict

def render_tab3_radius_leaflet_map_html(inp_lat, inp_lng, search_radius_km, nearby_props, is_dark_mode=False):
    """Renders complete Leaflet map HTML with genuine company logo markers, rich property detail cards, and controls."""
    import json
    
    tiles_url = "https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png" if not is_dark_mode else "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
    logo_dict = get_leaflet_logo_dict()
    
    props_json = json.dumps(nearby_props, ensure_ascii=False)
    logos_json = json.dumps(logo_dict, ensure_ascii=False)
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
        <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700;800&family=Sarabun:wght@300;400;500;600;700;800&display=swap');
            html, body, #map {{
                width: 100%;
                height: 100%;
                margin: 0;
                padding: 0;
                font-family: 'Sarabun', 'Outfit', -apple-system, BlinkMacSystemFont, sans-serif;
                background: {'#0f172a' if is_dark_mode else '#f8fafc'};
                border-radius: 14px;
                overflow: hidden;
            }}
            .logo-marker-pin {{
                display: flex;
                justify-content: center;
                align-items: center;
                width: 34px;
                height: 34px;
                background: #ffffff;
                border-radius: 50%;
                border: 2px solid #ffffff;
                box-shadow: 0 3px 10px rgba(0, 0, 0, 0.25);
                transition: transform 0.2s ease, box-shadow 0.2s ease;
                cursor: pointer;
                overflow: hidden;
                box-sizing: border-box;
                padding: 0;
            }}
            .logo-marker-pin:hover {{
                transform: scale(1.3);
                box-shadow: 0 6px 20px rgba(0, 0, 0, 0.4);
                z-index: 1000 !important;
            }}
            .logo-marker-pin img {{
                width: 18px;
                height: 18px;
                max-width: 18px;
                max-height: 18px;
                object-fit: contain;
                display: block;
                margin: 0 auto;
                transform: translateY(-1px);
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
                background: rgba(15, 23, 42, 0.98) !important;
                color: #ffffff !important;
                border-radius: 14px !important;
                border: 1px solid rgba(255, 255, 255, 0.2) !important;
                box-shadow: 0 14px 36px rgba(0, 0, 0, 0.5) !important;
                backdrop-filter: blur(12px) !important;
                padding: 4px !important;
            }}
            .leaflet-popup-tip {{
                background: rgba(15, 23, 42, 0.98) !important;
            }}
            .leaflet-popup-content {{
                margin: 10px 14px !important;
                line-height: 1.45 !important;
            }}
            .leaflet-tooltip {{
                background: rgba(15, 23, 42, 0.96) !important;
                color: #ffffff !important;
                border-radius: 8px !important;
                border: 1px solid rgba(255, 255, 255, 0.2) !important;
                box-shadow: 0 6px 18px rgba(0,0,0,0.35) !important;
                padding: 6px 10px !important;
                font-size: 12px !important;
            }}
            .leaflet-tooltip-top:before {{
                border-top-color: rgba(15, 23, 42, 0.96) !important;
            }}
            .prop-badge {{
                display: inline-block;
                padding: 2px 7px;
                border-radius: 6px;
                font-size: 11px;
                font-weight: 700;
                letter-spacing: 0.02em;
            }}
            .prop-badge-co {{
                background: rgba(99, 102, 241, 0.25);
                color: #a5b4fc;
                border: 1px solid rgba(99, 102, 241, 0.4);
            }}
            .prop-badge-sale {{
                background: rgba(16, 185, 129, 0.2);
                color: #6ee7b7;
                border: 1px solid rgba(16, 185, 129, 0.35);
            }}
            .prop-badge-dist {{
                background: rgba(244, 63, 94, 0.2);
                color: #fda4af;
                border: 1px solid rgba(244, 63, 94, 0.35);
            }}
        </style>
    </head>
    <body>
        <div id="map"></div>
        <script>
            var map = L.map('map', {{
                zoomControl: true,
                attributionControl: false
            }}).setView([{inp_lat}, {inp_lng}], 13);

            L.tileLayer('{tiles_url}', {{
                maxZoom: 19
            }}).addTo(map);

            var logos = {logos_json};
            var properties = {props_json};

            // 1. Search Radius Buffer Circle
            var radiusCircle = L.circle([{inp_lat}, {inp_lng}], {{
                radius: {search_radius_km * 1000},
                color: '#6366f1',
                fillColor: '#6366f1',
                fillOpacity: 0.14,
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
            refMarker.bindPopup('<div style="font-size:14px; font-weight:800; color:#ef4444; margin-bottom:3px;">🎯 จุดอ้างอิงของคุณ</div><div style="font-size:12px; color:#94a3b8;">📍 จุดศูนย์กลางการค้นหารัศมี ({search_radius_km} กม.)</div><div style="font-size:11px; color:#cbd5e1; margin-top:3px;">🌐 พิกัด: {inp_lat:.5f}, {inp_lng:.5f}</div>');
            refMarker.bindTooltip('🎯 จุดอ้างอิง ({search_radius_km} กม.)', {{ direction: 'top', offset: [0, -22] }});

            // 3. Company Logo Pins for each property found
            properties.forEach(function(p) {{
                if (!p.lat || !p.lon) return;
                var comp = p.company || 'BAM';
                var logoUrl = logos[comp] || logos[comp.toLowerCase()] || '';
                
                var logoHtml = logoUrl ? '<img src="' + logoUrl + '" alt="' + comp + '" />' : '<span style="font-weight:800; font-size:11px; color:#0f172a;">' + comp.substring(0,3) + '</span>';
                
                var customIcon = L.divIcon({{
                    className: 'custom-logo-icon',
                    html: '<div class="logo-marker-pin">' + logoHtml + '</div>',
                    iconSize: [34, 34],
                    iconAnchor: [17, 17],
                    popupAnchor: [0, -17]
                }});
                var locStr = [p.subdist, p.district, p.province].filter(Boolean).join(', ');

                var popupContent = '<div style="font-size: 13px; padding: 2px; min-width: 230px;">' +
                    '<div style="font-weight: 800; font-size: 14px; color: #38bdf8; margin-bottom: 4px;">' + p.name + '</div>' +
                    '<div style="color: #94a3b8; font-size: 11.5px; margin-bottom: 6px;">🔑 รหัสทรัพย์: <b style="color: #ffffff;">' + (p.code || '-') + '</b></div>' +
                    '<div style="display:flex; gap:8px; flex-wrap:wrap; margin-bottom:5px;">' +
                    '  <span style="background:rgba(167,139,250,0.15); color:#a78bfa; padding:2px 6px; border-radius:4px; font-size:11px; font-weight:600;">🏢 ' + comp + '</span>' +
                    '  <span style="background:rgba(252,211,77,0.15); color:#fcd34d; padding:2px 6px; border-radius:4px; font-size:11px; font-weight:600;">🏠 ' + (p.type || '-') + '</span>' +
                    '</div>' +
                    '<div style="background: rgba(16, 185, 129, 0.1); border: 1px solid rgba(16, 185, 129, 0.25); border-radius: 6px; padding: 5px 8px; margin-bottom: 6px;">' +
                    '  <div style="display:flex; justify-content:space-between; align-items:center;">' +
                    '    <div><span style="font-size:10px; color:#a7f3d0;">ราคา</span><br/><b style="font-size:14px; color:#34d399;">' + p.price + '</b></div>' +
                    '    <div style="text-align:right;"><span style="font-size:10px; color:#fca5a5;">ระยะห่าง</span><br/><b style="font-size:13px; color:#f43f5e;">' + p.dist + '</b></div>' +
                    '  </div>' +
                    '</div>' +
                    '<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 3px 8px; font-size: 11px; color:#cbd5e1; margin-bottom: 5px;">' +
                    '   <div>📐 เนื้อที่: <b>' + (p.land_area || '-') + '</b>' + (p.price_per_wah ? '<br/><span style="color:#38bdf8; font-size:10px;">(' + p.price_per_wah + ')</span>' : '') + '</div>' +
                    '   <div>🏢 ใช้สอย: <b>' + (p.usable_area || '-') + '</b>' + (p.price_per_sqm ? '<br/><span style="color:#38bdf8; font-size:10px;">(' + p.price_per_sqm + ')</span>' : '') + '</div>' +
                    '</div>' +
                    (locStr ? '<div style="font-size: 11px; color: #94a3b8; margin-bottom: 5px;">📍 <span style="color: #e2e8f0;">' + locStr + '</span></div>' : '') +
                    (p.link && p.link !== '-' && p.link !== '' ? '<div style="margin-top: 4px; text-align: right;"><a href="' + p.link + '" target="_blank" style="display: inline-block; background: #3b82f6; color: white; padding: 3px 8px; border-radius: 6px; text-decoration: none; font-size: 11px; font-weight: 600;">🔗 ดูประกาศ ↗</a></div>' : '') +
                    '</div>';

                var tooltipContent = '<div style="font-size:12px; line-height:1.4;">' +
                    '<b style="color:#38bdf8;">' + p.name + '</b><br/>' +
                    '🏢 ' + comp + ' | 🏠 ' + (p.type || '-') + '<br/>' +
                    '💰 <b style="color:#34d399;">' + p.price + '</b> | 📏 ' + p.dist +
                    (locStr ? '<br/><span style="color:#94a3b8;">📍 ' + locStr + '</span>' : '') +
                    '</div>';

                var marker = L.marker([p.lat, p.lon], {{ icon: customIcon }}).addTo(map);
                marker.bindPopup(popupContent);
                marker.bindTooltip(tooltipContent, {{ direction: 'top', offset: [0, -17] }});
            }});

            // Auto-fit view to radius circle with padding
            var group = new L.featureGroup([radiusCircle]);
            map.fitBounds(group.getBounds(), {{ padding: [30, 30] }});
        </script>
    </body>
    </html>
    """
    return html

def get_data_mtime():
    p = Path("all_assets.parquet")
    if p.exists():
        return p.stat().st_mtime
    return 0

# Cached function to load data – strictly parquet only for maximum speed
@st.cache_data(ttl=3600, show_spinner="กำลังโหลดฐานข้อมูลทรัพย์สิน (Parquet)...")
def load_properties_data(data_version=0):
    parquet_file = Path("all_assets.parquet")
    
    if not parquet_file.exists():
        st.error("❌ ไม่พบไฟล์ข้อมูล 'all_assets.parquet' กรุณารันสคริปต์ convert_csv_to_parquet.py เพื่อสร้างไฟล์")
        return None
        
    def ensure_derived_cols(df):
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
            df['ประเภททรัพย์'] = df['ประเภททรัพย์'].astype(str).str.strip().replace(prop_type_map)
            
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
            sale_map = {
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
            df['ประเภทการขาย'] = df['ประเภทการขาย'].astype(str).str.strip().replace(sale_map)

        if 'ชื่อประกาศ' not in df.columns:
            if 'ชื่อโครงการ' in df.columns:
                df['ชื่อประกาศ'] = df['ชื่อโครงการ'].astype(object).fillna('ไม่มีชื่อ').astype(str)
            else:
                df['ชื่อประกาศ'] = df['รหัสทรัพย์'].astype(object).fillna('ทรัพย์สิน NPA').astype(str)
        else:
            df['ชื่อประกาศ'] = df['ชื่อประกาศ'].astype(object).fillna('ไม่มีชื่อ').astype(str)

        if 'ลิงก์' not in df.columns:
            df['ลิงก์'] = ""
        else:
            df['ลิงก์'] = df['ลิงก์'].astype(object).fillna("").astype(str)

        if 'ราคา' in df.columns:
            df['ราคา'] = pd.to_numeric(df['ราคา'], errors='coerce')
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
            df['ภาค'] = df['จังหวัด'].apply(get_region_by_province)

        return df

    try:
        df = pd.read_parquet(parquet_file)
        # Exclude Livinginsider
        if 'บริษัท' in df.columns:
            df = df[df['บริษัท'] != 'Livinginsider'].copy()
        df = ensure_derived_cols(df)
        df.attrs['source'] = 'all_assets.parquet'
        return df
    except Exception as e:
        st.error(f"❌ เกิดข้อผิดพลาดในการโหลดไฟล์ Parquet: {e}")
        return None

def get_base_map_html():
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
    if df_raw is not None and not df_raw.empty:
        df_raw = pd.concat([df_raw, imp_df], ignore_index=True)
    else:
        df_raw = imp_df

# ----------------- SIDEBAR -----------------
with st.sidebar:
    col_side_title, col_side_theme = st.columns([0.72, 0.28])
    with col_side_title:
        logo_path = Path("assets/logo.png")
        if logo_path.exists():
            with open(logo_path, "rb") as f:
                side_logo_b64 = base64.b64encode(f.read()).decode("utf-8")
            st.markdown(f'''
            <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 2px;">
                <img src="data:image/png;base64,{side_logo_b64}" style="width: 58px; height: 58px; object-fit: contain; filter: drop-shadow(0 4px 12px rgba(37, 99, 235, 0.25));">
                <div>
                    <div style="font-size: 1.35rem; font-weight: 800; color: #2563eb; line-height: 1.1; letter-spacing: -0.5px;">All Asset</div>
                    <div style="font-size: 0.68rem; font-weight: 700; color: #64748b; letter-spacing: 0.8px;">NPA DASHBOARD</div>
                </div>
            </div>
            ''', unsafe_allow_html=True)
        else:
            st.markdown('<h3 style="color: #2563eb; margin: 0; padding-top: 4px;"><i class="fa fa-home"></i> All Asset</h3>', unsafe_allow_html=True)
    with col_side_theme:
        is_dark_mode = st.toggle("🌙 มืด", value=False, key="app_theme_mode", help="สลับระหว่างโหมดมืด (Dark Mode) และโหมดสว่าง (Light Mode)")
    
    if df_raw is not None and not df_raw.empty:
        src_name = getattr(df_raw, 'attrs', {}).get('source', 'all_assets.parquet')
        month_year_str, exact_date_str = get_dataset_month_year(df_raw)
        st.markdown(f"""
        <div style="background: rgba(99, 102, 241, 0.08); border: 1px solid rgba(99, 102, 241, 0.2); border-radius: 8px; padding: 6px 10px; margin-top: 5px; margin-bottom: 8px; font-size: 0.8rem; color: #6366f1; font-weight: 600;">
            <i class="fa fa-database"></i> แหล่งข้อมูล: <code>{src_name}</code><br/>
            <span style="font-size: 0.75rem; color: #475569; font-weight: normal;">📊 ข้อมูลพร้อมใช้งาน: <b>{len(df_raw):,}</b> รายการ</span><br/>
            <span style="font-size: 0.75rem; color: #2563eb; font-weight: 600;"><i class="fa fa-calendar-check"></i> ข้อมูลประจำเดือน: <b>{month_year_str}</b></span><br/>
            <span style="font-size: 0.72rem; color: #64748b; font-weight: normal;">(ดึงข้อมูล: <b>{exact_date_str}</b>)</span>
        </div>
        """, unsafe_allow_html=True)
        
    if st.button("🔄 รีโหลดฐานข้อมูล (Clear Cache)", use_container_width=True, help="กดเมื่อต้องการให้แอปอ่านไฟล์ข้อมูลใหม่ล่าสุดทันที"):
        st.cache_data.clear()
        st.session_state.pop('data_loaded_once', None)
        st.rerun()
        
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
    
    st.markdown("### <i class='fa fa-filter'></i> ตัวกรองข้อมูลทรัพย์สิน", unsafe_allow_html=True)
    
    if df_raw is not None and not df_raw.empty:
        search_query = ""
        
        # Company Filter (Pills) with dynamic list from data (Prioritize SAM, BAM, Chayo555 first)
        co_counts = df_raw['บริษัท'].value_counts()
        raw_comps = [str(c) for c in df_raw['บริษัท'].dropna().unique() if str(c).strip() not in ['', 'nan', 'None']]
        COMPANY_PRIORITY = ["SAM", "BAM", "Chayo555", "Chayo", "Baania", "NaYoo", "Taladnudbaan", "ZmyHome", "KBANK", "GHB", "SCB", "KTB"]
        companies_list = sorted(
            raw_comps,
            key=lambda c: (COMPANY_PRIORITY.index(c) if c in COMPANY_PRIORITY else 999, c)
        )
        if not companies_list:
            companies_list = ["SAM", "BAM", "Chayo555", "Baania", "NaYoo", "Taladnudbaan", "ZmyHome", "KBANK", "GHB", "SCB", "KTB"]
        
        # Ensure session state automatically includes all available companies
        if "filter_companies" not in st.session_state or not st.session_state["filter_companies"]:
            st.session_state["filter_companies"] = companies_list
        else:
            curr_sel = list(st.session_state["filter_companies"])
            missing_new = [c for c in companies_list if c not in curr_sel]
            if missing_new and len(curr_sel) >= len(companies_list) - len(missing_new):
                st.session_state["filter_companies"] = [c for c in companies_list if c in curr_sel or c in missing_new]
            else:
                sanitize_session_state("filter_companies", companies_list)
        selected_companies = st.pills(
            "บริษัททรัพย์สิน", 
            options=companies_list, 
            format_func=lambda x: f"{x} ({co_counts.get(x, 0):,})",
            selection_mode="multi", 
            default=companies_list,
            key="filter_companies"
        )
        if not selected_companies:
            selected_companies = companies_list
        
        # Property Type Filter
        if selected_companies:
            df_by_company = df_raw[df_raw['บริษัท'].isin(selected_companies)]
        else:
            df_by_company = df_raw
            
        # Group property types into prominent common pills and rare (เพิ่มเติม)
        PROMINENT_TYPES = [
            "บ้านเดี่ยว", "ห้องชุดพักอาศัย", "ทาวน์เฮ้าส์", "ที่ดินเปล่า",
            "อาคารพาณิชย์", "วิลล่า", "โรงงาน/โกดัง", "บ้านแฝด",
            "อพาร์ทเมนท์", "อาคารสำนักงาน", "โรงแรม/รีสอร์ท"
        ]
        type_counts = df_by_company['ประเภททรัพย์'].value_counts()
        common_types = [t for t in PROMINENT_TYPES if t in type_counts]
        for t in type_counts.index:
            if t not in common_types and type_counts[t] >= 80 and t != "อื่นๆ":
                common_types.append(t)
                
        rare_types = [t for t in type_counts.index if t not in common_types]
        
        display_type_keys = list(common_types)
        if len(rare_types) > 0:
            display_type_keys.append("เพิ่มเติม")
            
        sanitize_session_state("filter_types", display_type_keys)
        rare_count_sum = sum(type_counts[t] for t in rare_types)
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
            rare_options = [f"{t} ({type_counts[t]:,})" for t in rare_types_sorted]
            sanitize_session_state("selected_rare_types", rare_options)
            st.multiselect(
                "เลือกประเภททรัพย์สินเพิ่มเติม",
                options=rare_options,
                default=[],
                key="selected_rare_types"
            )
        
        # Sale Type Filter (ประเภทการขาย) - แสดงทุกแบบที่มีในฐานข้อมูลแบบไดนามิก
        sale_type_series = df_by_company['ประเภทการขาย'].dropna().astype(str).str.strip()
        sale_type_counts = sale_type_series[~sale_type_series.isin(["", "nan", "None"])].value_counts()
        available_sale_types = sale_type_counts.index.tolist()
        
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
        region_series = df_by_company['ภาค'].dropna().astype(str).str.strip() if 'ภาค' in df_by_company.columns else pd.Series(dtype=str)
        region_counts = region_series.value_counts()
        all_ordered_regions = ["ภาคกลาง", "ภาคเหนือ", "ภาคตะวันออกเฉียงเหนือ", "ภาคตะวันออก", "ภาคตะวันตก", "ภาคใต้"]
        available_regions = [r for r in all_ordered_regions if r in region_counts]
        for r in region_counts.index:
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
            provinces_pool = (
                df_by_company[df_by_company['ภาค'].isin(selected_regions)]['จังหวัด']
                .dropna()
                .unique()
                .tolist()
            )
        else:
            provinces_pool = (
                df_by_company['จังหวัด']
                .dropna()
                .unique()
                .tolist()
            )
        unique_provinces = sorted(provinces_pool)
        # Clean up province lists, removing "ไม่ระบุ" or blank
        if "ไม่ระบุ" in unique_provinces:
            unique_provinces.remove("ไม่ระบุ")
            unique_provinces.append("ไม่ระบุ")
        sanitize_session_state("selected_provinces", unique_provinces)
        selected_provinces = st.multiselect("จังหวัด", options=unique_provinces, default=[], key="selected_provinces", placeholder="เลือกจังหวัด...")
        
        # District Filter (dynamically populate from selected provinces or regions)
        if selected_provinces:
            filtered_provinces_df = df_by_company[df_by_company['จังหวัด'].isin(selected_provinces)]
        elif selected_regions:
            filtered_provinces_df = df_by_company[df_by_company['ภาค'].isin(selected_regions)]
        else:
            filtered_provinces_df = df_by_company
            
        dist_df = filtered_provinces_df[['อำเภอ', 'จังหวัด']].drop_duplicates().dropna()
        dist_df = dist_df[dist_df['อำเภอ'].astype(str).str.strip() != ""]
        unique_districts_formatted = (dist_df['อำเภอ'].astype(str) + " (" + dist_df['จังหวัด'].astype(str) + ")").tolist()
        unique_districts_formatted.sort()
        selected_districts_formatted = st.multiselect("อำเภอ / เขต", options=unique_districts_formatted, default=[], placeholder="เลือกอำเภอ / เขต...")
        
        # Parse selected districts into tuples for subdistrict option filtering
        selected_districts_tuples = []
        for d_f in selected_districts_formatted:
            if " (" in d_f:
                parts = d_f.split(" (")
                d_name = parts[0].strip()
                p_name = parts[1].replace(")", "").strip()
                selected_districts_tuples.append((d_name, p_name))
        
        # Subdistrict Filter (cascaded to prevent sending 17,000+ items to browser DOM)
        if selected_districts_tuples:
            filtered_districts_df = filtered_provinces_df[filtered_provinces_df.set_index(['อำเภอ', 'จังหวัด']).index.isin(selected_districts_tuples)]
            sub_df = filtered_districts_df[['ตำบล', 'อำเภอ', 'จังหวัด']].drop_duplicates().dropna()
            sub_df = sub_df[sub_df['ตำบล'].astype(str).str.strip() != ""]
            unique_subdistricts_formatted = (sub_df['ตำบล'].astype(str) + " (" + sub_df['อำเภอ'].astype(str) + ", " + sub_df['จังหวัด'].astype(str) + ")").tolist()
            unique_subdistricts_formatted.sort()
            selected_subdistricts_formatted = st.multiselect("ตำบล / แขวง", options=unique_subdistricts_formatted, default=[])
        elif selected_provinces:
            sub_df = filtered_provinces_df[['ตำบล', 'อำเภอ', 'จังหวัด']].drop_duplicates().dropna()
            sub_df = sub_df[sub_df['ตำบล'].astype(str).str.strip() != ""]
            unique_subdistricts_formatted = (sub_df['ตำบล'].astype(str) + " (" + sub_df['อำเภอ'].astype(str) + ", " + sub_df['จังหวัด'].astype(str) + ")").tolist()
            unique_subdistricts_formatted.sort()
            selected_subdistricts_formatted = st.multiselect("ตำบล / แขวง", options=unique_subdistricts_formatted, default=[], placeholder="เลือกตำบลในจังหวัดที่เลือก...")
        else:
            selected_subdistricts_formatted = st.multiselect(
                "ตำบล / แขวง", 
                options=[], 
                default=[], 
                placeholder="💡 เลือกจังหวัดหรืออำเภอก่อนเพื่อค้นหาตำบล"
            )
        
        # Price Filter - อิงราคาจริงที่มีในฐานข้อมูล
        valid_prices = df_by_company['ราคา'].dropna()
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
                "⚡ กดเลือกช่วงราคาด่วน",
                options=price_presets,
                default="ทั้งหมด",
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

# Construct root CSS custom properties based on theme toggle selection (default is Light Theme)
if is_dark_mode:
    root_vars = """
    --app-color-scheme: dark;
    --card-bg: #1e293b;
    --card-border: #334155;
    --card-text: #f8fafc;
    --card-subtext: #94a3b8;
    --sidebar-bg: #0f172a;
    --sidebar-border: #1e293b;
    --tag-bg: #334155;
    --tag-border: #475569;
    --tag-text: #f8fafc;
    --pill-bg: #334155;
    --pill-border: #475569;
    --pill-text: #f8fafc;
    --input-bg: #1e293b;
    --input-border: #475569;
    --input-text: #f8fafc;
    --hover-bg: #334155;
    --tab-bg: #0f172a;
    --page-bg: #0f172a;
    """
    plotly_template = "plotly_dark"
    mapbox_style = "carto-darkmatter"
else:
    root_vars = """
    --app-color-scheme: light;
    --card-bg: #ffffff;
    --card-border: #e2e8f0;
    --card-text: #0f172a;
    --card-subtext: #475569;
    --sidebar-bg: #f8fafc;
    --sidebar-border: #e2e8f0;
    --tag-bg: #f1f5f9;
    --tag-border: #cbd5e1;
    --tag-text: #0f172a;
    --pill-bg: #f1f5f9;
    --pill-border: #cbd5e1;
    --pill-text: #1e293b;
    --input-bg: #ffffff;
    --input-border: #cbd5e1;
    --input-text: #0f172a;
    --hover-bg: #e2e8f0;
    --tab-bg: #ffffff;
    --page-bg: #ffffff;
    """
    plotly_template = "plotly_white"
    mapbox_style = "carto-positron"

def style_plotly_fig(fig):
    bg = "#1e293b" if is_dark_mode else "#ffffff"
    font_c = "#f8fafc" if is_dark_mode else "#0f172a"
    tmpl = "plotly_dark" if is_dark_mode else "plotly_white"
    map_st = "carto-darkmatter" if is_dark_mode else "carto-positron"
    fig.update_layout(
        template=tmpl,
        paper_bgcolor=bg,
        plot_bgcolor=bg,
        font=dict(color=font_c, family="Outfit, Sarabun, sans-serif"),
        title_font=dict(color=font_c, family="Outfit, Sarabun, sans-serif"),
        legend=dict(font=dict(color=font_c))
    )
    try:
        fig.update_map(style=map_st)
    except Exception:
        pass
    if hasattr(fig, 'update_annotations'):
        fig.update_annotations(font=dict(color=font_c, family="Outfit, Sarabun, sans-serif"))
    return fig

# Global CSS Inject for modern UI aesthetics and theme-adaptive styling
css_style = """<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
<style>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=Sarabun:wght@300;400;500;600;700&display=swap');

:root {
    ROOT_VARS_PLACEHOLDER
}

.floating-card {
    background: var(--card-bg) !important;
    backdrop-filter: blur(12px) !important;
    -webkit-backdrop-filter: blur(12px) !important;
    border: 1px solid var(--card-border) !important;
    border-radius: 14px !important;
    padding: 12px 18px !important;
    box-shadow: 0 10px 30px rgba(15, 23, 42, 0.05) !important;
    flex: 1;
    transition: transform 0.2s ease, background-color 0.2s ease, border-color 0.2s ease;
}

.floating-card:hover {
    transform: translateY(-2px);
    background: var(--card-bg) !important;
    border-color: rgba(99, 102, 241, 0.4) !important;
    box-shadow: 0 12px 30px rgba(99, 102, 241, 0.15), 0 2px 10px rgba(6, 182, 212, 0.1) !important;
}

.floating-card-title {
    font-size: 0.72rem;
    color: var(--card-subtext) !important;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 4px;
}

.floating-card-value {
    font-size: 1.45rem;
    font-weight: 800;
    background: linear-gradient(135deg, #4f46e5 0%, #06b6d4 100%); 
    -webkit-background-clip: text; 
    -webkit-text-fill-color: transparent;
}

.floating-card-sub {
    font-size: 0.68rem;
    color: var(--card-subtext) !important;
    margin-top: 2px;
    font-weight: 500;
}



html, body, [data-testid="stSidebar"], .stApp {
    font-family: 'Outfit', 'Sarabun', sans-serif;
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
    padding-bottom: 40px !important;
    padding-left: 20px !important;
    padding-right: 20px !important;
    max-width: 100% !important;
    position: relative !important;
}

.main {
    position: relative !important;
}

/* Sidebar styling using dynamic theme colors */
section[data-testid="stSidebar"] {
    background-color: var(--sidebar-bg) !important;
    border-right: 1px solid var(--sidebar-border) !important;
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
    border-color: #6366f1 !important;
    background-color: var(--hover-bg) !important;
}
div[data-testid="stPills"] button:hover *,
div[data-testid="stPills"] button:hover p,
div[data-testid="stPills"] button:hover span,
div[data-testid="stPills"] [data-testid="stPillsItem"]:hover *,
div[data-testid="stPills"] [data-testid="stPillsItem"]:hover p,
div[data-testid="stPills"] [data-testid="stPillsItem"]:hover span {
    color: #6366f1 !important;
    -webkit-text-fill-color: #6366f1 !important;
}

/* Style selected pill buttons with explicit indigo background and white text */
div[data-testid="stPills"] button[aria-checked="true"],
div[data-testid="stPills"] button[aria-pressed="true"],
div[data-testid="stPills"] button[data-selected="true"],
div[data-testid="stPills"] button[aria-selected="true"],
div[data-testid="stPills"] [data-testid="stPillsItem"][aria-checked="true"],
div[data-testid="stPills"] [data-testid="stPillsItem"][data-selected="true"] {
    background-color: #6366f1 !important;
    border-color: #6366f1 !important;
    box-shadow: 0 4px 12px rgba(99, 102, 241, 0.3) !important;
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

/* Metrics panel styling with high-tech glassmorphic hover glows */
.metric-card {
    background: var(--card-bg) !important;
    border: 1px solid var(--card-border) !important;
    border-radius: 16px;
    padding: 24px;
    text-align: center;
    box-shadow: 0 4px 20px rgba(15, 23, 42, 0.02);
    transition: transform 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
}
.metric-card:hover {
    transform: translateY(-3px);
    border-color: rgba(99, 102, 241, 0.3) !important;
    box-shadow: 0 12px 30px rgba(99, 102, 241, 0.12), 0 2px 10px rgba(6, 182, 212, 0.08) !important;
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
    background: linear-gradient(135deg, #4f46e5 0%, #06b6d4 100%); 
    -webkit-background-clip: text; 
    -webkit-text-fill-color: transparent;
}
.metric-sub {
    font-size: 0.78rem;
    color: var(--card-subtext) !important;
    margin-top: 6px;
    font-weight: 500;
}

/* Style the tab container to sit at the top and fit height */
div[data-baseweb="tab-list"], div[data-testid="stTabList"] {
    margin-top: 0px !important;
    padding-top: 5px !important;
    padding-bottom: 5px !important;
    padding-left: 20px !important;
    background-color: var(--page-bg) !important;
    border-bottom: 1px solid var(--card-border) !important;
    z-index: 1000 !important;
}

button[data-baseweb="tab"] p, button[data-testid="stTab"] p {
    color: var(--card-subtext) !important;
    font-weight: 600;
    font-size: 0.95rem;
}
button[data-baseweb="tab"][aria-selected="true"], button[data-testid="stTab"][aria-selected="true"] {
    border-bottom-color: #6366f1 !important;
}
button[data-baseweb="tab"][aria-selected="true"] p, button[data-testid="stTab"][aria-selected="true"] p {
    color: #6366f1 !important;
}

/* Segmented Control Styling */
div[data-testid="stSegmentedControl"] {
    background: var(--card-bg) !important;
    border: 1px solid var(--card-border) !important;
    border-radius: 12px !important;
    padding: 3px !important;
    box-shadow: 0 1px 4px rgba(0,0,0,0.04) !important;
}
div[data-testid="stSegmentedControl"] button {
    border-radius: 9px !important;
    font-weight: 600 !important;
    font-size: 0.86rem !important;
    transition: all 0.2s ease !important;
}
div[data-testid="stSegmentedControl"] button[aria-checked="true"] {
    background: #2563eb !important;
    color: #ffffff !important;
    box-shadow: 0 2px 8px rgba(37, 99, 235, 0.3) !important;
}

/* Tab Panel content area styling */
div[data-baseweb="tab-panel"], div[data-testid="stTabPanel"] {
    position: relative !important;
    padding-top: 15px !important;
    padding-left: 0px !important;
    padding-right: 0px !important;
}

.floating-kpi-container {
    position: relative !important;
    margin: 15px 20px 5px 20px !important;
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
    district_tuples = []
    for d_f in selected_districts_formatted:
        if " (" in d_f:
            parts = d_f.split(" (")
            d_name = parts[0].strip()
            p_name = parts[1].replace(")", "").strip()
            district_tuples.append((d_name, p_name))
    if district_tuples:
        df_filtered = df_filtered[df_filtered.set_index(['อำเภอ', 'จังหวัด']).index.isin(district_tuples)]

# 6. Subdistricts
if selected_subdistricts_formatted:
    subdistrict_trios = []
    for s_f in selected_subdistricts_formatted:
        if " (" in s_f:
            parts = s_f.split(" (")
            s_name = parts[0].strip()
            parent_parts = parts[1].replace(")", "").split(",")
            d_name = parent_parts[0].strip()
            p_name = parent_parts[1].strip()
            subdistrict_trios.append((s_name, d_name, p_name))
    if subdistrict_trios:
        df_filtered = df_filtered[df_filtered.set_index(['ตำบล', 'อำเภอ', 'จังหวัด']).index.isin(subdistrict_trios)]

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
    if val_baht >= 1e6:
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
<div style="display: flex; justify-content: space-between; align-items: center; margin: 15px 20px 8px 20px; flex-wrap: wrap; gap: 8px;">
    <div style="font-size: 1.05rem; font-weight: 700; color: var(--card-text);"><i class="fa fa-chart-pie" style="color: #2563eb;"></i> สรุปข้อมูลภาพรวม (Summary Overview)</div>
    <div style="display: inline-flex; align-items: center; gap: 6px; background: rgba(37, 99, 235, 0.08); border: 1px solid rgba(37, 99, 235, 0.25); padding: 4px 14px; border-radius: 16px; font-size: 0.84rem; font-weight: 600; color: #2563eb;">
        <i class="fa fa-calendar-check"></i> ข้อมูลประจำเดือน: <b>{month_year_str}</b> <span style="font-size:0.75rem; color:#64748b; font-weight:normal;">(ดึงข้อมูล: {exact_date_str})</span>
    </div>
</div>
<div class="floating-kpi-container" style="margin-bottom: 20px;">
    <div class="floating-card">
        <div class="floating-card-title"><i class="fa fa-list" style="color: #6366f1;"></i> ทรัพย์สินที่พบ</div>
        <div class="floating-card-value">{filtered_count_str}</div>
        <div class="floating-card-sub">{summary_text}</div>
    </div>
    <div class="floating-card">
        <div class="floating-card-title"><i class="fa fa-wallet" style="color: #3b82f6;"></i> มูลค่ารวมทรัพย์สิน</div>
        <div class="floating-card-value">{total_value_str}</div>
        <div class="floating-card-sub">มูลค่ารวมตามตัวกรอง</div>
    </div>
    <div class="floating-card">
        <div class="floating-card-title"><i class="fa fa-arrow-down" style="color: #10b981;"></i> ราคาต่ำสุด (Min)</div>
        <div class="floating-card-value">{min_price_str}</div>
        <div class="floating-card-sub">ราคาเริ่มต้นต่ำสุด</div>
    </div>
    <div class="floating-card">
        <div class="floating-card-title"><i class="fa fa-tags" style="color: #06b6d4;"></i> ราคากลาง (Median)</div>
        <div class="floating-card-value">{median_price_str}</div>
        <div class="floating-card-sub">ค่ามัธยฐานของกลุ่ม</div>
    </div>
    <div class="floating-card">
        <div class="floating-card-title"><i class="fa fa-calculator" style="color: #8b5cf6;"></i> ราคาเฉลี่ย (Mean)</div>
        <div class="floating-card-value">{mean_price_str}</div>
        <div class="floating-card-sub">ค่าเฉลี่ยเลขคณิต</div>
    </div>
    <div class="floating-card">
        <div class="floating-card-title"><i class="fa fa-arrow-up" style="color: #f59e0b;"></i> ราคาสูงสุด (Max)</div>
        <div class="floating-card-value">{max_price_str}</div>
        <div class="floating-card-sub">มูลค่าสูงสุดในกลุ่ม</div>
    </div>
    <div class="floating-card">
        <div class="floating-card-title"><i class="fa fa-chart-line" style="color: #ec4899;"></i> ส่วนเบี่ยงเบน (SD)</div>
        <div class="floating-card-value">{sd_price_str}</div>
        <div class="floating-card-sub">การกระจายตัวของราคา</div>
    </div>
</div>
"""

st.markdown(floating_kpi_html, unsafe_allow_html=True)

# ----------------- TABS CREATION -----------------
tab1, tab2, tab3, tab4 = st.tabs([
    "🔮 ภาพรวม & แผนที่ (Bubble & Map)", 
    "📈 สถิติ & วิเคราะห์ (Analytics)", 
    "🔍 เปรียบเทียบตำแหน่ง (Comparison)",
    "📋 รายการทรัพย์สิน (Property Listing)"
])

# ----- TAB 1: BUBBLE & MAP -----
with tab1:
    with st.container(key="tab_map"):
        c_mode1, c_mode2 = st.columns([0.52, 0.48])
        with c_mode1:
            t1_view = st.segmented_control(
                "รูปแบบมุมมองการแสดงผล:",
                options=["🔮 แผนภาพวงกลมบับเบิ้ล (Bubble View)", "🗺️ แผนที่พิกัดทรัพย์สิน (Interactive Map)"],
                default="🔮 แผนภาพวงกลมบับเบิ้ล (Bubble View)",
                key="tab1_main_view_mode"
            )
            if not t1_view:
                t1_view = "🔮 แผนภาพวงกลมบับเบิ้ล (Bubble View)"
                
        if "บับเบิ้ล" in t1_view:
            with c_mode2:
                bubble_metric = st.segmented_control(
                    "เกณฑ์เปรียบเทียบขนาดวงกลม:",
                    options=["📊 สัดส่วนจำนวนทรัพย์สิน", "💰 สัดส่วนมูลค่ารวม"],
                    default="📊 สัดส่วนจำนวนทรัพย์สิน",
                    key="tab1_bubble_metric_radio"
                )
                if not bubble_metric:
                    bubble_metric = "📊 สัดส่วนจำนวนทรัพย์สิน"
            
            # Render 3D Glossy Bubble Chart matching AMC NPA Monitor style
            bubble_html = generate_3d_glossy_bubble_chart_html(
                df_filtered, 
                bubble_metric=bubble_metric, 
                is_dark_mode=is_dark_mode
            )
            
            try:
                import streamlit.components.v1 as stc
                stc.html(bubble_html, height=640)
            except Exception:
                st.html(bubble_html)
                
        else:
            with c_mode2:
                map_color_mode = st.segmented_control(
                    "เกณฑ์จำแนกสีจุดพิกัดบนแผนที่:",
                    options=["🏢 จำแนกตามบริษัท (By Company)", "🏠 จำแนกตามประเภททรัพย์ (By Property Type)"],
                    default="🏢 จำแนกตามบริษัท (By Company)",
                    key="tab1_map_color_mode"
                )
                if not map_color_mode:
                    map_color_mode = "🏢 จำแนกตามบริษัท (By Company)"

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
                # Step 2: Format prices (40%)
                progress_bar.progress(40, text="กำลังจัดรูปแบบราคาและชื่อประกาศ (40%)...")
                prices = pd.to_numeric(map_data['ราคา'], errors='coerce')
                map_data['ราคาขาย'] = prices.apply(lambda p: f"฿{p:,.0f} บาท" if pd.notna(p) and p > 0 else "ไม่ระบุ")
                
            if map_data.empty:
                progress_bar.empty()
                st.warning("⚠️ ไม่พบพิกัดตำแหน่ง ละติจูด/ลองจิจูด ในรายการทรัพย์สินที่คุณเลือกค้นหา")
            else:
                title_col = 'ชื่อประกาศ' if 'ชื่อประกาศ' in map_data.columns else ('ชื่อโครงการ' if 'ชื่อโครงการ' in map_data.columns else 'รหัสทรัพย์')
                titles = [str(x)[:30] for x in map_data[title_col].fillna('ไม่มีชื่อ').astype(str)]
                ids = [str(x)[:15] for x in map_data['รหัสทรัพย์'].fillna('-').astype(str)]
                provs = [str(x) for x in map_data['จังหวัด'].fillna('-').astype(str)]
                types = [str(x) for x in map_data['ประเภททรัพย์'].fillna('-').astype(str)]
                companies = [str(x) for x in map_data['บริษัท'].fillna('-').astype(str)]
                prices = [str(x) for x in map_data['ราคาขาย'].astype(str)]

                r_vals, g_vals, b_vals = [], [], []
                
                # Step 3: Color mapping (60%)
                if "ประเภททรัพย์" in map_color_mode:
                    progress_bar.progress(60, text="กำลังจัดเตรียมสีตามประเภททรัพย์สิน (60%)...")
                    PROP_TYPE_COLORS = {
                        "บ้านเดี่ยว": [37, 99, 235],       # Royal Blue (#2563eb)
                        "ห้องชุดพักอาศัย": [139, 92, 246], # Purple (#8b5cf6)
                        "ทาวน์เฮ้าส์": [245, 158, 11],     # Amber (#f59e0b)
                        "ที่ดินเปล่า": [16, 185, 129],          # Emerald (#10b981)
                        "อาคารพาณิชย์": [244, 63, 94],     # Rose/Coral (#f43f5e)
                        "วิลล่า": [236, 72, 153],          # Pink (#ec4899)
                        "โรงงาน/โกดัง": [6, 182, 212],     # Cyan (#06b6d4)
                        "บ้านแฝด": [99, 102, 241],         # Indigo (#6366f1)
                        "อพาร์ทเมนท์": [168, 85, 247],     # Violet (#a855f7)
                        "อาคารสำนักงาน": [100, 116, 139],  # Slate (#64748b)
                        "โรงแรม/รีสอร์ท": [234, 179, 8],   # Gold (#eab308)
                    }
                    DEFAULT_PROP_COLOR = [148, 163, 184]
                    
                    for ptype in map_data['ประเภททรัพย์']:
                        color = PROP_TYPE_COLORS.get(ptype, DEFAULT_PROP_COLOR)
                        r_vals.append(color[0])
                        g_vals.append(color[1])
                        b_vals.append(color[2])
                        
                    # Dynamic Legend for Property Types
                    type_counts = map_data['ประเภททรัพย์'].value_counts()
                    legend_items_html = ['<div style="font-weight: 600; font-size: 11px; text-transform: uppercase; color: #64748b; margin-bottom: 4px; letter-spacing: 0.5px;">ประเภททรัพย์สิน</div>']
                    for p_name, p_rgb in PROP_TYPE_COLORS.items():
                        c_cnt = type_counts.get(p_name, 0)
                        if c_cnt > 0:
                            hex_c = f"rgb({p_rgb[0]},{p_rgb[1]},{p_rgb[2]})"
                            legend_items_html.append(f'<div class="legend-item"><span class="legend-color" style="background:{hex_c};"></span>{p_name} ({c_cnt:,})</div>')
                            
                    other_cnt = sum(cnt for t, cnt in type_counts.items() if t not in PROP_TYPE_COLORS)
                    if other_cnt > 0:
                        legend_items_html.append(f'<div class="legend-item"><span class="legend-color" style="background:#94a3b8;"></span>อื่นๆ ({other_cnt:,})</div>')
                        
                    legend_content = "\n".join(legend_items_html)
                else:
                    progress_bar.progress(60, text="กำลังจัดเตรียมสีตามบริษัทคู่แข่ง (60%)...")
                    COMPANY_COLORS = {
                        "SAM": [16, 185, 129],
                        "BAM": [59, 130, 246],
                        "Chayo555": [249, 115, 22],
                        "Baania": [245, 158, 11],
                        "NaYoo": [139, 92, 246],
                        "Taladnudbaan": [6, 182, 212],
                        "ZmyHome": [236, 72, 153],
                        "KBANK": [5, 150, 105],
                        "GHB": [202, 138, 4],
                        "SCB": [126, 34, 206],
                        "KTB": [2, 132, 199],
                        "GSB": [235, 25, 133]
                    }
                    DEFAULT_COLOR = [148, 163, 184]
                    
                    for company in map_data['บริษัท']:
                        color = COMPANY_COLORS.get(company, DEFAULT_COLOR)
                        r_vals.append(color[0])
                        g_vals.append(color[1])
                        b_vals.append(color[2])
                        
                    # Dynamic Legend for Companies
                    co_counts = map_data['บริษัท'].value_counts()
                    legend_items_html = ['<div style="font-weight: 600; font-size: 11px; text-transform: uppercase; color: #64748b; margin-bottom: 4px; letter-spacing: 0.5px;">บริษัททรัพย์สิน</div>']
                    for co_name, co_rgb in COMPANY_COLORS.items():
                        c_cnt = co_counts.get(co_name, 0)
                        if c_cnt > 0:
                            hex_c = f"rgb({co_rgb[0]},{co_rgb[1]},{co_rgb[2]})"
                            legend_items_html.append(f'<div class="legend-item"><span class="legend-color" style="background:{hex_c};"></span>{co_name} ({c_cnt:,})</div>')
                    
                    other_co_cnt = sum(cnt for co, cnt in co_counts.items() if co not in COMPANY_COLORS)
                    if other_co_cnt > 0:
                        legend_items_html.append(f'<div class="legend-item"><span class="legend-color" style="background:#94a3b8;"></span>อื่นๆ ({other_co_cnt:,})</div>')
                        
                    legend_content = "\n".join(legend_items_html)
                    
                # Step 4: CSV conversion & Base64 encoding (80%)
                progress_bar.progress(80, text="กำลังแปลงข้อมูลเป็น Base64 Payload (80%)...")
                csv_df = pd.DataFrame({
                    'lon': map_data['ลองจิจูด'].values.astype('float32'),
                    'lat': map_data['ละติจูด'].values.astype('float32'),
                    'r': np.array(r_vals, dtype='uint8'),
                    'g': np.array(g_vals, dtype='uint8'),
                    'b': np.array(b_vals, dtype='uint8'),
                    '_title': titles,
                    '_id': ids,
                    '_prov': provs,
                    '_type': types,
                    '_company': companies,
                    '_price_str': prices,
                })
                
                csv_str = csv_df.to_csv(index=False)
                csv_base64 = base64.b64encode(csv_str.encode('utf-8')).decode('utf-8')
                
                # Step 5: Render map template (90%)
                progress_bar.progress(90, text="กำลังสร้างแผนที่ความละเอียดสูง Deck.gl (90%)...")
                base_tmpl = get_base_map_html()
                html_content = base_tmpl.replace("CSV_BASE64_PLACEHOLDER", csv_base64)
                html_content = html_content.replace("LEGEND_ITEMS_PLACEHOLDER", legend_content)
                
                body_theme_class = "dark-theme" if is_dark_mode else ""
                html_content = html_content.replace("BODY_CLASS_PLACEHOLDER", body_theme_class)
                
                # Step 6: Finish (100%)
                progress_bar.progress(100, text="เรนเดอร์แผนที่สำเร็จแล้ว (100%)")
                progress_bar.empty()
                
                map_rendered = False
                try:
                    import streamlit.components.v1 as stc
                    stc.html(html_content, height=680)
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
                    st.error("❌ ไม่สามารถแสดงแผนที่ได้ กรุณาลองรีเฟรชหน้าเว็บ")

# ----- TAB 2: ANALYTICS -----
with tab2:
    st.markdown("### 📈 วิเคราะห์เชิงลึกและเปรียบเทียบสถิติของคู่แข่ง")
    
    if df_filtered.empty:
        st.warning("⚠️ ไม่มีข้อมูลสำหรับจัดทำแผนภูมิวิเคราะห์สถิติ")
    else:
        # Create sub-tabs inside Tab 2
        sub_tab1, sub_tab2, sub_tab3 = st.tabs([
            "📊 ภาพรวมตลาด (Market Overview)",
            "🏢 สัดส่วนสินค้าคู่แข่ง (Asset Type Focus)",
            "🏛️ การกระจายตัวพอร์ตโฟลิโอ SAM (SAM Portfolio)"
        ])
        
        with sub_tab1:
            col_c1, col_c2 = st.columns(2)
            
            # 1. Total Assets by Company
            with col_c1:
                comp_counts = df_filtered['บริษัท'].value_counts().reset_index()
                comp_counts.columns = ['บริษัท', 'จำนวนทรัพย์สิน']
                fig_comp = px.bar(
                    comp_counts,
                    x='บริษัท',
                    y='จำนวนทรัพย์สิน',
                    color='บริษัท',
                    title='จำนวนรายการทรัพย์สินเปรียบเทียบแต่ละบริษัท',
                    color_discrete_map={"SAM": "#10b981", "BAM": "#3b82f6", "Chayo555": "#f97316", "Baania": "#f59e0b", "NaYoo": "#8b5cf6", "Taladnudbaan": "#06b6d4", "ZmyHome": "#ec4899", "KBANK": "#059669", "GHB": "#ca8a04", "SCB": "#7e22ce", "KTB": "#0284c7", "GSB": "#eb1985"},
                    template=plotly_template
                )
                fig_comp.update_layout(title_font=dict(size=14, family="Outfit"))
                st.plotly_chart(style_plotly_fig(fig_comp), width="stretch", theme=None)
                
            # 2. Distribution of Property Type
            with col_c2:
                type_counts = df_filtered['ประเภททรัพย์'].value_counts().head(8).reset_index()
                type_counts.columns = ['ประเภททรัพย์', 'จำนวนประกาศ']
                fig_type = px.pie(
                    type_counts,
                    names='ประเภททรัพย์',
                    values='จำนวนประกาศ',
                    hole=0.4,
                    title='สัดส่วนประเภททรัพย์หลัก',
                    color_discrete_sequence=px.colors.qualitative.Pastel,
                    template=plotly_template
                )
                fig_type.update_layout(title_font=dict(size=14, family="Outfit"))
                st.plotly_chart(style_plotly_fig(fig_type), width="stretch", theme=None)
                
            st.markdown("---")
            col_c3, col_c4 = st.columns(2)
            
            # 3. Median Price by Company
            with col_c3:
                median_price_comp = df_filtered.groupby('บริษัท')['ราคา'].median().reset_index()
                median_price_comp.columns = ['บริษัท', 'ราคากลาง Median (บาท)']
                fig_avg_p = px.bar(
                    median_price_comp,
                    x='บริษัท',
                    y='ราคากลาง Median (บาท)',
                    color='บริษัท',
                    title='ราคากลาง (Median) จำแนกตามบริษัททรัพย์สิน',
                    color_discrete_map={"SAM": "#10b981", "BAM": "#3b82f6", "Chayo555": "#f97316", "Baania": "#f59e0b", "NaYoo": "#8b5cf6", "Taladnudbaan": "#06b6d4", "ZmyHome": "#ec4899", "KBANK": "#059669", "GHB": "#ca8a04", "SCB": "#7e22ce", "KTB": "#0284c7", "GSB": "#eb1985"},
                    template=plotly_template
                )
                fig_avg_p.update_layout(title_font=dict(size=14, family="Outfit"))
                st.plotly_chart(style_plotly_fig(fig_avg_p), width="stretch", theme=None)
                
            # 4. Top 10 Provinces
            with col_c4:
                top_prov = df_filtered['จังหวัด'].value_counts().head(10).reset_index()
                top_prov.columns = ['จังหวัด', 'จำนวนทรัพย์']
                fig_prov = px.bar(
                    top_prov,
                    x='จำนวนทรัพย์',
                    y='จังหวัด',
                    orientation='h',
                    color='จำนวนทรัพย์',
                    title='10 อันดับจังหวัดที่มีทรัพย์สินเยอะที่สุด',
                    color_continuous_scale="Viridis",
                    template=plotly_template
                )
                fig_prov.update_layout(yaxis=dict(autorange="reversed"), title_font=dict(size=14, family="Outfit"), coloraxis_showscale=False)
                st.plotly_chart(style_plotly_fig(fig_prov), width="stretch", theme=None)
                
            st.markdown("---")
            col_c5, col_c6 = st.columns(2)
            
            # 5. Price Distribution (Capped at 25 Million Baht)
            with col_c5:
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
                    "ที่ดินเปล่า": "#56B4E9",
                    "บ้านเดี่ยว": "#CC79A7", 
                    "ห้องชุดพักอาศัย": "#E69F00",
                    "คอนโด": "#E69F00", 
                    "ทาวน์เฮ้าส์": "#107c41"
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
                fig_price_dist.update_layout(
                    title_font=dict(size=14, family="Outfit"), 
                    yaxis_title="จำนวนรายการ",
                    xaxis_title="ราคาเริ่มต้น (บาท)",
                    height=520,
                    margin=dict(l=60, r=40, t=50, b=90)
                )
                st.plotly_chart(style_plotly_fig(fig_price_dist), width="stretch", theme=None)
                
            # 6. Price vs. Land Area (Sq.Wah) - Exclude Condos/ห้องชุด
            with col_c6:
                def map_type_for_land_scatter(t):
                    t_str = str(t).strip()
                    if 'คอนโด' in t_str or 'ห้องชุด' in t_str:
                        return np.nan  # ไม่เอาห้องชุด
                    elif 'ที่ดิน' in t_str:
                        return 'ที่ดินเปล่า'
                    elif 'บ้านเดี่ยว' in t_str or 'บ้านแฝด' in t_str or 'พูลวิลล่า' in t_str or 'บ้าน' in t_str:
                        return 'บ้านเดี่ยว'
                    elif 'ทาวน์โฮม' in t_str or 'ทาวน์เฮ้าส์' in t_str or 'ทาวน์เฮาส์' in t_str:
                        return 'ทาวน์เฮ้าส์'
                    elif 'อาคารพาณิชย์' in t_str or 'ตึกแถว' in t_str:
                        return 'อาคารพาณิชย์'
                    return np.nan

                df_land_scatter = df_filtered[
                    (df_filtered['พื้นที่_ตารางวา'].notna()) & 
                    (df_filtered['พื้นที่_ตารางวา'] > 0) & 
                    (df_filtered['พื้นที่_ตารางวา'] <= 1000) & 
                    (df_filtered['ราคา'].notna()) & 
                    (df_filtered['ราคา'] > 0) & 
                    (df_filtered['ราคา'] <= 60000000)
                ].copy()
                
                df_land_scatter['ประเภททรัพย์ '] = df_land_scatter['ประเภททรัพย์'].apply(map_type_for_land_scatter)
                df_land_scatter = df_land_scatter[df_land_scatter['ประเภททรัพย์ '].notna()]
                
                # Optimize by subsetting and sampling to 10k points to prevent scatter plot lag
                df_scatter_data = df_land_scatter[['พื้นที่_ตารางวา', 'ราคา', 'ประเภททรัพย์ ', 'ชื่อประกาศ', 'จังหวัด', 'อำเภอ']]
                if len(df_scatter_data) > 10000:
                    df_scatter_data = df_scatter_data.sample(n=10000, random_state=42)
                
                color_map_scatter = {
                    "บ้านเดี่ยว": "#3182bd", 
                    "ทาวน์เฮ้าส์": "#ef3b2c",
                    "ที่ดินเปล่า": "#56B4E9",
                    "อาคารพาณิชย์": "#a855f7"
                }
                
                fig_price_vs_area = px.scatter(
                    df_scatter_data,
                    x='พื้นที่_ตารางวา',
                    y='ราคา',
                    color='ประเภททรัพย์ ',
                    hover_data=['ชื่อประกาศ', 'จังหวัด', 'อำเภอ'],
                    title='ราคาเริ่มต้น เทียบกับ เนื้อที่ (ตร.ว.)',
                    labels={'พื้นที่_ตารางวา': 'เนื้อที่ (ตร.ว.)', 'ราคา': 'ราคาเริ่มต้น (บาท)', 'ประเภททรัพย์ ': 'ประเภททรัพย์'},
                    color_discrete_map=color_map_scatter,
                    template=plotly_template
                )
                fig_price_vs_area.update_layout(
                    title_font=dict(size=14, family="Outfit"),
                    xaxis_title="เนื้อที่ (ตร.ว.)",
                    yaxis_title="ราคาเริ่มต้น (บาท)",
                    height=520,
                    margin=dict(l=60, r=40, t=50, b=90)
                )
                fig_price_vs_area.update_traces(
                    marker=dict(
                        size=12,
                        opacity=0.75,
                        line=dict(width=1, color='white')
                    )
                )
                st.plotly_chart(style_plotly_fig(fig_price_vs_area), width="stretch", theme=None)
                
        with sub_tab2:
            st.markdown("#### 🏢 สัดส่วนประเภททรัพย์สินคู่แข่งเชิงลึก (Asset Type Focus)")
            st.write("เปรียบเทียบสัดส่วนพอร์ตสินค้าของแต่ละบริษัทเพื่อดูความเชี่ยวชาญเฉพาะทางในแต่ละประเภททรัพย์สิน")
            
            focus_metric = st.radio(
                "เลือกเกณฑ์การวิเคราะห์สัดส่วนพอร์ตสินค้า", 
                ["👥 จำนวนทรัพย์สิน (Asset Count)", "💰 มูลค่าทรัพย์สินรวม (Total Value)"], 
                horizontal=True, 
                key="focus_metric_type"
            )
            
            is_val_metric = (focus_metric == "💰 มูลค่าทรัพย์สินรวม (Total Value)")
            
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
                
            # Sort with SAM, BAM, Chayo555 / Chayo prioritized in the top row (3 columns)
            PREFERRED_COMPANY_ORDER = ["SAM", "BAM", "Chayo555", "Chayo", "Chayo NPA", "Baania", "NaYoo", "Taladnudbaan", "ZmyHome", "KBANK", "GHB", "SCB", "KTB"]
            all_comps = list(comp_type_df['บริษัท'].unique())
            companies = sorted(
                all_comps, 
                key=lambda c: (PREFERRED_COMPANY_ORDER.index(c) if c in PREFERRED_COMPANY_ORDER else 999, c)
            )
            
            if len(companies) > 0:
                from plotly.subplots import make_subplots
                import plotly.graph_objects as go
                
                n_cols = min(len(companies), 3)
                n_rows = (len(companies) + n_cols - 1) // n_cols
                
                fig_asset_focus = make_subplots(
                    rows=n_rows, cols=n_cols,
                    specs=[[{'type': 'pie'}] * n_cols for _ in range(n_rows)],
                    subplot_titles=[f"{c}" for c in companies],
                )
                
                colors = px.colors.qualitative.Pastel
                # Top property types that are considered "important"
                TOP_TYPES = ['บ้านเดี่ยว', 'ห้องชุดพักอาศัย', 'ทาวน์เฮ้าส์', 'ที่ดินเปล่า', 'อาคารพาณิชย์', 'โรงงาน/โกดัง', 'บ้านแฝด']
                other_color = '#d1d5db'
                color_map = {t: colors[i % len(colors)] for i, t in enumerate(TOP_TYPES)}
                color_map['อื่นๆ'] = other_color
                
                MIN_PCT = 3.0  # Group types below this % into อื่นๆ
                
                for idx, company in enumerate(companies):
                    row = idx // n_cols + 1
                    col = idx % n_cols + 1
                    cdf = comp_type_df[comp_type_df['บริษัท'] == company].sort_values(value_col, ascending=False)
                    total = cdf[value_col].sum()
                    
                    if total <= 0:
                        continue
                        
                    # Split into major vs minor
                    cdf = cdf.copy()
                    cdf['pct'] = cdf[value_col] / total * 100
                    major = cdf[cdf['pct'] >= MIN_PCT]
                    minor = cdf[cdf['pct'] < MIN_PCT]
                    
                    # Build final data with อื่นๆ
                    labels = major['ประเภททรัพย์'].tolist()
                    values = major[value_col].tolist()
                    pie_colors = [color_map.get(t, colors[hash(t) % len(colors)]) for t in labels]
                    
                    if not minor.empty:
                        labels.append('อื่นๆ')
                        values.append(minor[value_col].sum())
                        pie_colors.append(other_color)
                    
                    # Only show label+percent for major items, hide text for อื่นๆ
                    text_labels = [f"{l}" for l in major['ประเภททรัพย์']] + ([''] if not minor.empty else [])
                    
                    fig_asset_focus.add_trace(
                        go.Pie(
                            labels=labels,
                            values=values,
                            name=company,
                            marker=dict(colors=pie_colors),
                            textinfo='label+percent',
                            textposition='auto',
                            text=text_labels,
                            insidetextorientation='auto',
                            hovertemplate=hover_tmpl,
                        ),
                        row=row, col=col
                    )
                
                fig_asset_focus.update_layout(
                    title=dict(text='สัดส่วนประเภททรัพย์สินแยกตามแต่ละบริษัท', font=dict(size=14, family="Outfit")),
                    height=420 * n_rows,
                    template=plotly_template,
                    showlegend=False,
                )
                st.plotly_chart(style_plotly_fig(fig_asset_focus), width="stretch", theme=None)

        # -----------------------------------------------------------------
        # SUB-TAB 3: การกระจายตัวพอร์ตโฟลิโอ SAM (SAM Portfolio Deep Dive)
        # -----------------------------------------------------------------
        with sub_tab3:
            st.markdown("#### 📊 การกระจายตัวเชิงลึกของพอร์ตโฟลิโอ SAM")
            st.caption("วิเคราะห์การกระจายตัวตามช่วงราคา และการกระจายราคาของ 6 ประเภททรัพย์หลักของ SAM")

            sam_df_tab2 = df_filtered[df_filtered['บริษัท'] == 'SAM'].copy() if not df_filtered.empty else pd.DataFrame()
            if sam_df_tab2.empty and df_raw is not None:
                sam_df_tab2 = df_raw[df_raw['บริษัท'] == 'SAM'].copy()

            if sam_df_tab2.empty:
                st.warning("⚠️ ไม่พบข้อมูลทรัพย์สินของ SAM ในตัวกรองปัจจุบัน")
            else:
                PRICE_TIER_ORDER = [
                    "< 1 ล้านบาท",
                    "1 - 3 ล้านบาท",
                    "3 - 5 ล้านบาท",
                    "5 - 10 ล้านบาท",
                    "10 - 20 ล้านบาท",
                    "> 20 ล้านบาท"
                ]
                def get_price_tier(price):
                    if pd.isna(price) or price <= 0:
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

                sam_df_tab2['Price_Tier'] = sam_df_tab2['ราคา'].apply(get_price_tier)

                col_s1, col_s2 = st.columns(2)
                with col_s1:
                    tier_df = sam_df_tab2.groupby('Price_Tier', observed=False).agg(
                        count=('รหัสทรัพย์', 'count') if 'รหัสทรัพย์' in sam_df_tab2.columns else ('ราคา', 'count'),
                        total_val=('ราคา', 'sum')
                    ).reindex(PRICE_TIER_ORDER).reset_index()
                    tier_df['count'] = tier_df['count'].fillna(0)
                    tier_df['val_million'] = tier_df['total_val'].fillna(0) / 1e6

                    fig_tier = go.Figure()
                    fig_tier.add_trace(go.Bar(
                        x=tier_df['Price_Tier'],
                        y=tier_df['count'],
                        name='จำนวนทรัพย์ (รายการ)',
                        marker_color='#10b981',
                        yaxis='y',
                        text=tier_df['count'].astype(int),
                        textposition='auto'
                    ))
                    fig_tier.add_trace(go.Scatter(
                        x=tier_df['Price_Tier'],
                        y=tier_df['val_million'],
                        name='มูลค่ารวม (ล้านบาท)',
                        marker_color='#3b82f6',
                        mode='lines+markers+text',
                        text=[f"฿{v:,.0f}M" for v in tier_df['val_million']],
                        textposition='top center',
                        yaxis='y2',
                        line=dict(width=3, color='#3b82f6')
                    ))
                    fig_tier.update_layout(
                        title=dict(text='🏷️ การกระจายตัวตามช่วงราคา SAM (Price Tier Pyramid)', font=dict(size=14, family="Outfit")),
                        yaxis=dict(title='จำนวนทรัพย์ (รายการ)', showgrid=False),
                        yaxis2=dict(title='มูลค่ารวม (ล้านบาท)', overlaying='y', side='right', showgrid=False),
                        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                        height=450,
                        margin=dict(t=40, b=10, l=10, r=10),
                        template=plotly_template
                    )
                    st.plotly_chart(style_plotly_fig(fig_tier), width="stretch", theme=None)

                with col_s2:
                    top_types = sam_df_tab2['ประเภททรัพย์'].value_counts().head(6).index.tolist()
                    box_data = sam_df_tab2[sam_df_tab2['ประเภททรัพย์'].isin(top_types) & (sam_df_tab2['ราคา'] > 0)].copy()
                    box_data['val_million'] = box_data['ราคา'] / 1e6
                    
                    fig_box = px.box(
                        box_data,
                        x='ประเภททรัพย์',
                        y='val_million',
                        color='ประเภททรัพย์',
                        title='📦 การกระจายราคาของ 6 ประเภททรัพย์หลัก SAM (Box Plot - ล้านบาท)',
                        template=plotly_template,
                        points=False
                    )
                    fig_box.update_layout(
                        title_font=dict(size=14, family="Outfit"),
                        height=450, 
                        showlegend=False, 
                        yaxis_type="log",
                        yaxis_title="ราคา (ล้านบาท - สเกล Log)",
                        margin=dict(t=40, b=10, l=10, r=10)
                    )
                    st.plotly_chart(style_plotly_fig(fig_box), width="stretch", theme=None)

# ----- TAB 3: COMPARISON -----
with tab3:
    comp_sub_tab1, comp_sub_tab2 = st.tabs([
        "📍 เปรียบเทียบตามรัศมีทำเล (Radius Location Analysis)",
        "🏘️ เปรียบเทียบในโครงการเดียวกัน (Same-Project Comparison)"
    ])

    with comp_sub_tab1:
        st.markdown("### 🔍 เปรียบเทียบทำเลของทรัพย์สิน (Asset Location Comparison)")
        st.write("นำเข้าพิกัดที่คุณต้องการเพื่อค้นหาทรัพย์สิน NPA ของทุกบริษัทที่อยู่ใกล้เคียงในรัศมีที่กำหนด")

        st.markdown("---")

        inp_col1, inp_col2 = st.columns(2)
        with inp_col1:
            st.markdown("##### 📍 ส่วนที่ 1: กำหนดพิกัดที่ต้องการค้นหา")

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

            # Intercept map clicks BEFORE st.number_input is called so widget state syncs cleanly
            map_picker_state = st.session_state.get("manual_sec1_clean_map_picker", {})
            map_pts = map_picker_state.get("selection", {}).get("points", []) if map_picker_state else []
            if map_pts:
                clk_lat = float(map_pts[0].get("lat", 13.7651))
                clk_lng = float(map_pts[0].get("lon", 100.5383))
                if clk_lat != st.session_state.get("prev_clk_lat") or clk_lng != st.session_state.get("prev_clk_lng"):
                    st.session_state["prev_clk_lat"] = clk_lat
                    st.session_state["prev_clk_lng"] = clk_lng
                    st.session_state["manual_map_clicked_lat"] = clk_lat
                    st.session_state["manual_map_clicked_lng"] = clk_lng
                    st.session_state["comp_manual_lat"] = clk_lat
                    st.session_state["comp_manual_lng"] = clk_lng

            st.markdown(f"""
            <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px; margin-top: 4px;">
                <span style="font-size: 0.88rem; font-weight: 700; color: {'#94a3b8' if is_dark_mode else '#475569'};">
                    🎯 วิธีการกำหนดจุดอ้างอิง (Reference Point Method)
                </span>
            </div>
            """, unsafe_allow_html=True)

            ref_method = st.segmented_control(
                "วิธีการกำหนดจุดอ้างอิง",
                options=[
                    "📌 ระบุพิกัดด้วยตัวเอง (Manual Coordinates)",
                    "🏠 เลือกจากรายการทรัพย์สินในระบบ (Choose from Asset)"
                ],
                default="📌 ระบุพิกัดด้วยตัวเอง (Manual Coordinates)",
                label_visibility="collapsed",
                key="comp_ref_method"
            )
            if not ref_method:
                ref_method = "📌 ระบุพิกัดด้วยตัวเอง (Manual Coordinates)"

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
            if "เลือกจากรายการทรัพย์สินในระบบ" in ref_method:
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
                                area_items.append(f"🌾 <b>เนื้อที่:</b> {inp_land_area:,.1f} ตร.ว.{u_land_str}")
                            if pd.notna(inp_use_area) and inp_use_area > 0:
                                u_sqm_str = f" <span style='color:#64748b; font-size:0.8rem;'>(฿{inp_price/inp_use_area:,.0f}/ตร.ม.)</span>" if inp_price > 0 else ""
                                area_items.append(f"🏢 <b>พื้นที่ใช้สอย:</b> {inp_use_area:,.1f} ตร.ม.{u_sqm_str}")
                            if not area_items:
                                area_items.append("📐 <b>เนื้อที่ / พื้นที่ใช้สอย:</b> ไม่ระบุ")
                            area_html = "</div><div>".join(area_items)

                            # Specs
                            specs = []
                            bed = selected_asset.get('ห้องนอน')
                            bath = selected_asset.get('ห้องน้ำ')
                            park = selected_asset.get('ที่จอดรถ')
                            if pd.notna(bed) and str(bed).strip() not in ['', 'nan', '-']:
                                specs.append(f"🛏️ {int(float(bed)) if str(bed).replace('.','',1).isdigit() else bed} ห้องนอน")
                            if pd.notna(bath) and str(bath).strip() not in ['', 'nan', '-']:
                                specs.append(f"🚿 {int(float(bath)) if str(bath).replace('.','',1).isdigit() else bath} ห้องน้ำ")
                            if pd.notna(park) and str(park).strip() not in ['', 'nan', '-']:
                                specs.append(f"🚗 {int(float(park)) if str(park).replace('.','',1).isdigit() else park} ที่จอดรถ")
                            spec_div = f"<div>🚪 <b>ฟังก์ชันอาคาร:</b> {' | '.join(specs)}</div>" if specs else ""

                            # Sale type & date
                            sale_type_val = str(selected_asset.get('ประเภทการขาย', 'ขาย')).strip()
                            sale_div = f"<div>🏷️ <b>ประเภทการขาย:</b> {sale_type_val}</div>" if sale_type_val not in ['', 'nan', 'None'] else ""
                            date_val = str(selected_asset.get('วันประกาศ', selected_asset.get('วันที่ดึงข้อมูล', ''))).strip()
                            date_div = f"<div>📅 <b>ข้อมูล ณ วันที่:</b> {date_val}</div>" if date_val not in ['', 'nan', 'None'] else ""
                            proj_div = f"<div>🏗️ <b>ชื่อโครงการ:</b> {proj_name}</div>" if has_proj else ""

                            # Link info
                            asset_url = str(selected_asset.get('ลิงก์', '')).strip()
                            if asset_url.startswith('http'):
                                link_html = f"<a href='{asset_url}' target='_blank' style='color:#2563eb; text-decoration:underline; font-weight:600;'>คลิกดูรายละเอียดบนเว็บต้นทาง ↗</a>"
                            else:
                                link_html = "<span style='color:#94a3b8;'>ไม่มีลิงก์ต้นทาง</span>"

                            card_html = f"""<div style="background: rgba(59, 130, 246, 0.04); border: 1px solid rgba(59, 130, 246, 0.25); border-radius: 12px; padding: 16px 20px; margin: 12px 0 16px 0; font-family: 'Sarabun', sans-serif;">
<div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid rgba(59, 130, 246, 0.15); padding-bottom: 8px; margin-bottom: 12px; flex-wrap: wrap; gap: 8px;">
<div style="font-size: 1.02rem; font-weight: 700; color: #1e3a8a;">🏠 รายละเอียดทรัพย์อ้างอิงที่เลือก</div>
<div>
<span style="background: #3b82f6; color: #ffffff; font-size: 0.8rem; font-weight: 600; padding: 3px 10px; border-radius: 12px;">{selected_asset['บริษัท']}</span>
<span style="background: rgba(59, 130, 246, 0.12); color: #1d4ed8; font-size: 0.8rem; font-weight: 600; padding: 3px 8px; border-radius: 6px; margin-left: 4px;">{selected_asset['รหัสทรัพย์']}</span>
</div>
</div>
<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 8px 20px; font-size: 0.88rem; line-height: 1.6; color: var(--card-text, #334155);">
<div>🏷️ <b>ชื่อประกาศ:</b> {selected_asset['ชื่อประกาศ']}</div>
{proj_div}
<div>🏘️ <b>ประเภททรัพย์:</b> <span style="font-weight: 600; color: #2563eb;">{inp_type}</span></div>
<div>💰 <b>ราคาขาย:</b> <span style="font-size: 1.05rem; font-weight: 800; color: #059669;">{price_str}</span></div>
{sale_div}
<div>📍 <b>ทำเล:</b> {loc_str}</div>
<div>🗺️ <b>พิกัด:</b> <code>{inp_lat:.6f}, {inp_lng:.6f}</code></div>
<div>{area_html}</div>
{spec_div}
{date_div}
</div>
<div style="margin-top: 10px; padding-top: 8px; border-top: 1px dashed rgba(59, 130, 246, 0.2); font-size: 0.85rem;">
🔗 <b>ลิงก์ประกาศ:</b> {link_html}
</div>
</div>"""
                            st.html(card_html)
                        else:
                            st.warning("⚠️ เกิดข้อผิดพลาดในการดึงข้อมูลรายการที่เลือก")
                    else:
                        st.warning("⚠️ กรุณาเลือกรายการทรัพย์สินอ้างอิง")
            else:
                # If they choose manual coordinates, render manual input widgets + interactive map picker
                st.markdown("👇 **ระบุพิกัดเอง หรือกดคลิกเลือกหมุดบนแผนที่ด้านล่างเพื่อเลือกพิกัดได้ทันที:**")
                
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
            st.markdown("##### ⚙️ ส่วนที่ 2: เงื่อนไขการค้นหา")
            search_radius = st.slider("รัศมีการค้นหา (กิโลเมตร)", min_value=0.5, max_value=10.0, value=5.0, step=0.5)

            # Company Filter for Comparison (Pills)
            all_comp_list = sorted([str(c) for c in df_raw['บริษัท'].dropna().unique()]) if df_raw is not None else ["Baania", "BAM", "SAM", "DDproperty", "Taladnudbaan", "ZmyHome"]
            compare_companies = st.pills(
                "บริษัททรัพย์สิน (เปรียบเทียบ)",
                options=all_comp_list,
                selection_mode="multi",
                default=all_comp_list,
                key="comp_companies"
            )

            # Property Type Scope Filter for Comparison (Segmented Control)
            st.markdown(f"""
            <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px; margin-top: 10px;">
                <span style="font-size: 0.88rem; font-weight: 700; color: {'#94a3b8' if is_dark_mode else '#475569'};">
                    🏷️ ขอบเขตประเภททรัพย์สิน (Property Type Matching)
                </span>
            </div>
            """, unsafe_allow_html=True)

            type_options = [
                f"🎯 เฉพาะประเภทเดียวกัน ({inp_type})",
                "🌐 ทุกประเภททรัพย์สิน"
            ]
            type_scope = st.segmented_control(
                "ขอบเขตประเภททรัพย์สิน",
                options=type_options,
                default=type_options[0],
                label_visibility="collapsed",
                key=f"comp_type_scope_{inp_type}"
            )
            filter_by_type = (type_scope is None or "เฉพาะประเภทเดียวกัน" in type_scope)

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
            st.caption(f"💰 ราคาต่ำสุด: **฿{min_price_val:,.0f}** | สูงสุด: **฿{max_price_val:,.0f}** (ครอบคลุมทุกกลุ่มเป็นค่า Default)")

        # Clean Empty Map Picker rendered FULL-WIDTH spanning both columns
        if "ระบุพิกัดด้วยตัวเอง" in ref_method:
            st.markdown("<br/>", unsafe_allow_html=True)
            st.markdown("🗺️ **คลิกตำแหน่งบนแผนที่เปล่าด้านล่าง (พอกดคลิกตรงไหน ระบบจะใช้จุดนั้นเป็นจุดอ้างอิงทันที):**")
            
            ref_pin_lat = st.session_state.get("manual_map_clicked_lat", inp_lat if inp_lat != 0 else 13.7651)
            ref_pin_lng = st.session_state.get("manual_map_clicked_lng", inp_lng if inp_lng != 0 else 100.5383)

            # Use cached multi-scale interactive grid generator for instant rendering
            all_grid_lats, all_grid_lngs = get_thailand_clean_grid(round(ref_pin_lat, 4), round(ref_pin_lng, 4))

            fig_picker = go.Figure()

            # Add invisible grid trace with 40px hitbox size & transparent color for clean map look
            fig_picker.add_trace(go.Scattermap(
                lat=all_grid_lats,
                lon=all_grid_lngs,
                mode='markers',
                marker=dict(size=40, color='rgba(0, 0, 0, 0.001)', opacity=0.05),
                hovertemplate="🌐 พิกัดตำแหน่งเมาส์ขณะนี้:<br>• ละติจูด (Lat): %{lat:.6f}<br>• ลองจิจูด (Lng): %{lon:.6f}<extra></extra>",
                name="จุดพิกัดในไทย"
            ))

            # Add reference red pin trace
            fig_picker.add_trace(go.Scattermap(
                lat=[ref_pin_lat],
                lon=[ref_pin_lng],
                mode='markers',
                marker=dict(size=24, color='#ef4444', opacity=1.0),
                hovertemplate=f"📍 จุดอ้างอิงของคุณ<br>• ละติจูด (Lat): {ref_pin_lat:.6f}<br>• ลองจิจูด (Lng): {ref_pin_lng:.6f}<extra></extra>",
                name="จุดอ้างอิง"
            ))

            fig_picker.update_layout(
                map=dict(
                    style=mapbox_style,
                    center=dict(lat=ref_pin_lat, lon=ref_pin_lng),
                    zoom=10
                ),
                margin={"r": 0, "t": 0, "l": 0, "b": 0},
                paper_bgcolor="rgba(0,0,0,0)",
                showlegend=False,
                height=420,
                template=plotly_template
            )
            
            picker_event = st.plotly_chart(
                style_plotly_fig(fig_picker),
                width="stretch",
                theme=None,
                on_select="rerun",
                selection_mode="points",
                key="manual_sec1_clean_map_picker"
            )
            
            pts = picker_event.get("selection", {}).get("points", []) if picker_event else []
            if pts:
                c_lat = float(pts[0].get("lat", ref_pin_lat))
                c_lng = float(pts[0].get("lon", ref_pin_lng))
                if c_lat != st.session_state.get("prev_clk_lat") or c_lng != st.session_state.get("prev_clk_lng"):
                    st.session_state["prev_clk_lat"] = c_lat
                    st.session_state["prev_clk_lng"] = c_lng
                    st.session_state["manual_map_clicked_lat"] = c_lat
                    st.session_state["manual_map_clicked_lng"] = c_lng
                    st.session_state["comp_manual_lat"] = c_lat
                    st.session_state["comp_manual_lng"] = c_lng
                    st.rerun()

        st.markdown("<br/>", unsafe_allow_html=True)
        run_comp_btn = st.button("🚀 เริ่มเปรียบเทียบทำเล", type="primary", use_container_width=True, key="btn_run_comp_radius")

        if run_comp_btn:
            st.session_state["has_run_comp"] = True

        # Only display comparison results if the user has clicked the button
        if st.session_state.get("has_run_comp", False):
            if inp_lat != 0.0 and inp_lng != 0.0:
                m_type = inp_type if filter_by_type else None
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
                    st.warning(f"❌ ไม่พบทรัพย์สิน NPA ตามเงื่อนไขตัวกรองในรัศมี {search_radius:.1f} กิโลเมตร รอบจุดพิกัด ({inp_lat:.4f}, {inp_lng:.4f})")
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
                            <span style="font-size: 1.8rem;">🎯</span>
                            <div>
                                <div style="font-size: 1.15rem; font-weight: 800; letter-spacing: 0.02em;">
                                    พบทรัพย์ NPA ทั้งหมด <span style="font-size: 1.45rem; text-decoration: underline; text-underline-offset: 4px; color: #fef08a;">{len(nearby_df):,}</span> รายการ ในรัศมี <span style="font-size: 1.35rem; color: #fef08a;">{search_radius:.1f}</span> กิโลเมตร!
                                </div>
                                <div style="font-size: 0.85rem; opacity: 0.95; margin-top: 3px;">
                                    📍 <b>จุดอ้างอิง:</b> {inp_name} (พิกัด {inp_lat:.4f}, {inp_lng:.4f})
                                </div>
                            </div>
                        </div>
                        <div style="background: rgba(255,255,255,0.22); backdrop-filter: blur(8px); padding: 6px 16px; border-radius: 20px; font-weight: 700; font-size: 0.88rem; white-space: nowrap;">
                            🏠 {inp_type if filter_by_type else 'ทุกประเภททรัพย์'}
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
                        if not filter_by_type and 'nearby_df' in locals() and not nearby_df.empty:
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

                        st.markdown(f"#### 📊 ผลการวิเคราะห์ราคากลางต่อหน่วย (Median Analysis) เฉพาะประเภททรัพย์: **{inp_type}**")

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
                                <div>💰 <b>ราคารวม:</b> ฿{inp_price:,.0f}</div>
                                <div>🏠 <b>ทรัพย์สิน:</b> {inp_type} ({float(inp_use_area):,.1f} ตร.ม.)</div>
                                <div style='color: #64748b; font-size: 0.76rem; margin-top: 2px;'>📐 คำนวณจากพื้นที่ใช้สอย (ตารางเมตร)</div>
                            </div>
                            """
                        elif not is_condo_ref and has_land:
                            ref_u_p = inp_price / float(inp_land_area)
                            ref_val_html = f"฿{ref_u_p:,.0f} <span style='font-size:0.85rem; font-weight:normal; color:#475569;'>/ตร.ว.</span>"
                            sqm_sub = f" | ใช้สอย {float(inp_use_area):,.1f} ตร.ม." if has_sqm else ""
                            ref_sub_html = f"""
                            <div style='margin-top: 6px; line-height: 1.55; font-size: 0.82rem; color: #475569;'>
                                <div>💰 <b>ราคารวม:</b> ฿{inp_price:,.0f}</div>
                                <div>🏠 <b>ทรัพย์สิน:</b> {inp_type} ({float(inp_land_area):,.1f} ตร.ว{sqm_sub})</div>
                                <div style='color: #64748b; font-size: 0.76rem; margin-top: 2px;'>📐 คำนวณจากเนื้อที่ (ตารางวา)</div>
                            </div>
                            """
                        elif has_sqm:
                            ref_u_p = inp_price / float(inp_use_area)
                            ref_val_html = f"฿{ref_u_p:,.0f} <span style='font-size:0.85rem; font-weight:normal; color:#475569;'>/ตร.ม.</span>"
                            ref_sub_html = f"""
                            <div style='margin-top: 6px; line-height: 1.55; font-size: 0.82rem; color: #475569;'>
                                <div>💰 <b>ราคารวม:</b> ฿{inp_price:,.0f}</div>
                                <div>🏠 <b>ทรัพย์สิน:</b> {inp_type} (พื้นที่ใช้สอย {float(inp_use_area):,.1f} ตร.ม.)</div>
                                <div style='color: #64748b; font-size: 0.76rem; margin-top: 2px;'>📐 คำนวณจากพื้นที่ใช้สอย (ตารางเมตร)</div>
                            </div>
                            """
                        else:
                            ref_val_html = f"฿{inp_price:,.0f}"
                            ref_sub_html = f"""
                            <div style='margin-top: 6px; line-height: 1.55; font-size: 0.82rem; color: #475569;'>
                                <div>🏠 <b>ทรัพย์สิน:</b> {inp_type}</div>
                                <div style='color: #94a3b8; font-size: 0.76rem;'>⚠️ ไม่ระบุขนาดพื้นที่</div>
                            </div>
                            """

                        ref_html = f"""
                        <div class="metric-card">
                            <div class="metric-title"><i class="fa fa-map-marker" style="color: #ef4444;"></i> พิกัดอ้างอิงของคุณ</div>
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
                                <div>📊 <b>ช่วงราคา:</b> ฿{min_u_sel:,.0f} - ฿{max_u_sel:,.0f} /{unit_lbl_sel}</div>
                                <div>📦 <b>จำนวน:</b> {count_u_sel:,} รายการในรัศมี {search_radius:.1f} กม.</div>
                                <div style='color: #64748b; font-size: 0.76rem; margin-top: 2px;'>📐 {area_source_label}</div>
                            </div>
                            """
                        else:
                            unit_val_html = "ไม่มีข้อมูล"
                            unit_sub_html = f"<div style='color: #94a3b8; font-size: 0.8rem; margin-top: 6px;'>ไม่พบข้อมูลพื้นที่ของ {inp_type} ในรัศมี {search_radius:.1f} กม.</div>"

                        unit_html = f"""
                        <div class="metric-card" style="background: rgba(59, 130, 246, 0.04); border: 1px solid rgba(59, 130, 246, 0.2);">
                            <div class="metric-title"><i class="fa fa-tag" style="color: #3b82f6;"></i> ราคากลางต่อหน่วย (Median ในรัศมี {search_radius:.1f} กม.) - {inp_type}</div>
                            <div class="metric-value" style="color: #2563eb;">{unit_val_html}</div>
                            <div class="metric-sub">{unit_sub_html}</div>
                        </div>
                        """
                        m_col2.markdown(unit_html, unsafe_allow_html=True)

                        # Col 3: Raw Land Price per Sq.Wah (Median)
                        if has_raw_land:
                            rl_val_html = f"฿{median_raw_land:,.0f} <span style='font-size:0.85rem; font-weight:normal; color:#475569;'>/ตร.ว.</span>"
                            rl_sub_html = f"""
                            <div style='margin-top: 6px; line-height: 1.55; font-size: 0.82rem; color: #334155;'>
                                <div>📊 <b>ช่วงราคา:</b> ฿{min_raw_land:,.0f} - ฿{max_raw_land:,.0f} /ตร.ว.</div>
                                <div>📦 <b>จำนวน:</b> {count_raw_land:,} รายการในรัศมี {search_radius:.1f} กม.</div>
                                <div style='color: #64748b; font-size: 0.76rem; margin-top: 2px;'>📐 คำนวณจากเนื้อที่ (ตารางวา)</div>
                            </div>
                            """
                        else:
                            rl_val_html = "ไม่มีข้อมูล"
                            rl_sub_html = f"<div style='color: #94a3b8; font-size: 0.8rem; margin-top: 6px;'>ไม่พบรายการที่ดินเปล่าในรัศมี {search_radius:.1f} กม.</div>"

                        rl_html = f"""
                        <div class="metric-card" style="background: rgba(16, 185, 129, 0.04); border: 1px solid rgba(16, 185, 129, 0.2);">
                            <div class="metric-title"><i class="fa fa-tree" style="color: #10b981;"></i> ราคากลางที่ดินเปล่า (Median ในรัศมี {search_radius:.1f} กม.)</div>
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

                    st.markdown("##### 🗺️ แผนที่ตำแหน่งจุดอ้างอิงเทียบกับตำแหน่งทรัพย์ NPA ที่พบ (คลิกที่หมุดเพื่อดูเฉพาะทรัพย์สินนั้นในตาราง)")
                    
                    geo_info_msg = f"📍 **มีพิกัดปักหมุดบนแผนที่ได้:** **{valid_geo_count:,}** รายการ (คิดเป็น **{pct_geo:.1f}%**)"
                    if dup_geo_count > 0:
                        geo_info_msg += f" | 🏢 **พิกัดซ้ำกัน (เช่น คอนโด/โครงการเดียวกัน):** **{dup_geo_count:,}** รายการ (ปักรวม **{unique_geo_count:,}** ตำแหน่งหมุดบนแผนที่)"
                    if missing_geo_count > 0:
                        geo_info_msg += f" | ⚠️ **ไม่มีข้อมูลพิกัดในระบบ:** **{missing_geo_count:,}** รายการ ({pct_missing:.1f}% - แสดงเฉพาะในตารางข้อมูล)"
                    
                    st.caption(f"{geo_info_msg} จากทรัพย์ NPA ทั้งหมด {total_found:,} รายการที่พบในทำเล")

                    # 1. Render Interactive Leaflet Radius Map with Company Logo Badges & Comprehensive Metadata
                    nearby_list_for_map = []
                    for _, r in map_nearby_df.iterrows():
                        if pd.notna(r.get('ละติจูด')) and pd.notna(r.get('ลองจิจูด')):
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
                            
                            # Building Specs
                            bed_val = f"{r['ห้องนอน']} นอน" if pd.notna(r.get('ห้องนอน')) and str(r.get('ห้องนอน')) not in ['nan', 'None', '', '0'] else ""
                            bath_val = f"{r['ห้องน้ำ']} น้ำ" if pd.notna(r.get('ห้องน้ำ')) and str(r.get('ห้องน้ำ')) not in ['nan', 'None', '', '0'] else ""
                            park_val = f"{r['ที่จอดรถ']} จอด" if pd.notna(r.get('ที่จอดรถ')) and str(r.get('ที่จอดรถ')) not in ['nan', 'None', '', '0'] else ""
                            
                            link_val = str(r.get('ลิงก์', ''))
                            subdist_val = str(r.get('ตำบล', ''))
                            dist_name_val = str(r.get('อำเภอ', ''))
                            prov_val = str(r.get('จังหวัด', ''))
                            gps_str = f"{float(r['ละติจูด']):.5f}, {float(r['ลองจิจูด']):.5f}"
                            
                            nearby_list_for_map.append({
                                "lat": float(r["ละติจูด"]),
                                "lon": float(r["ลองจิจูด"]),
                                "name": str(r.get('ชื่อประกาศ', 'ทรัพย์สิน NPA')),
                                "project": project_val,
                                "code": asset_code,
                                "price": formatted_price,
                                "type": prop_type_val,
                                "sale_type": sale_type_val,
                                "dist": dist_km_val,
                                "company": company_name_val,
                                "land_area": land_area_val,
                                "usable_area": usable_area_val,
                                "price_per_wah": price_per_wah_str,
                                "price_per_sqm": price_per_sqm_str,
                                "unit_price": u_price_val,
                                "bed": bed_val,
                                "bath": bath_val,
                                "parking": park_val,
                                "link": link_val,
                                "subdist": subdist_val,
                                "district": dist_name_val,
                                "province": prov_val,
                                "gps": gps_str
                            })
                    # Deduplicate: keep only 1 marker per exact same (lat, lon)
                    seen_coords = set()
                    deduped_list = []
                    for item in nearby_list_for_map:
                        coord_key = (item.get("lat"), item.get("lon"))
                        if coord_key not in seen_coords:
                            seen_coords.add(coord_key)
                            deduped_list.append(item)

                    leaflet_html = render_tab3_radius_leaflet_map_html(
                        float(inp_lat), float(inp_lng), float(search_radius), deduped_list, is_dark_mode=is_dark_mode
                    )
                    st.components.v1.html(leaflet_html, height=640, scrolling=False)

                    # 2. Table of Nearby NPA Properties
                    st.markdown(f"##### 📋 รายการทรัพย์สิน NPA ที่พบในรัศมีค้นหาทั้งหมด {len(nearby_df):,} รายการ (พร้อมราคาต่อตารางวา / ตารางเมตร)")

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

                    # Standard Column Ordering: Price and Areas front and center!
                    cols_nearby_order = [
                        "บริษัท", "รหัสทรัพย์", "ชื่อโครงการ", "ประเภททรัพย์", "ประเภทการขาย", 
                        "ราคาขาย (บาท)", "เนื้อที่ (ไร่-งาน-ตร.ว.)", "ราคา/ตร.ว. (บาท)", "พื้นที่ใช้สอย (ตร.ม.)", "ราคา/ตร.ม. (บาท)",
                        "ระยะทาง (กม.)", "ตำบล", "อำเภอ", "จังหวัด", "ชื่อประกาศ", "ลิงก์", 
                        "ห้องนอน", "ห้องน้ำ", "ที่จอดรถ", "ID", "ละติจูด", "ลองจิจูด", "วันที่ดึงข้อมูล", "วันประกาศ"
                    ]
                    cols_present = [c for c in cols_nearby_order if c in nearby_show.columns]
                    # Also include any other columns in nearby_show that weren't in the explicit list (excluding helper columns)
                    extra_cols = [c for c in nearby_show.columns if c not in cols_present and c not in ['ราคา', 'ขนาดพื้นที่', 'ฐานพื้นที่คำนวณ', 'หน่วยวัด', 'ราคาต่อหน่วย', 'ราคาต่อหน่วย (แสดงผล)', 'พื้นที่_ตารางวา', 'เนื้อที่ (ตร.ว.)', 'sqwah_calc']]
                    nearby_show = nearby_show[cols_present + extra_cols]

                    st.dataframe(
                        nearby_show,
                        use_container_width=True,
                        column_config={
                            "ราคาขาย (บาท)": st.column_config.NumberColumn("ราคาขาย (บาท)", format="฿%,d"),
                            "เนื้อที่ (ไร่-งาน-ตร.ว.)": st.column_config.TextColumn("เนื้อที่ (ไร่-งาน-ตร.ว.)"),
                            "ราคา/ตร.ว. (บาท)": st.column_config.NumberColumn("ราคา/ตร.ว. (บาท)", format="฿%,d"),
                            "พื้นที่ใช้สอย (ตร.ม.)": st.column_config.NumberColumn("พื้นที่ใช้สอย (ตร.ม.)", format="%.1f"),
                            "ราคา/ตร.ม. (บาท)": st.column_config.NumberColumn("ราคา/ตร.ม. (บาท)", format="฿%,d"),
                            "ระยะทาง (กม.)": st.column_config.NumberColumn("ระยะทาง (กม.)", format="%.2f กม."),
                            "ละติจูด": st.column_config.NumberColumn(format="%.6f"),
                            "ลองจิจูด": st.column_config.NumberColumn(format="%.6f"),
                            "ลิงก์": st.column_config.LinkColumn("ลิงก์ประกาศ", display_text="🔗 เปิดดูทรัพย์")
                        }
                    )
                    render_import_export_section(nearby_show, filename_prefix="npa_radius_search", key_suffix="radius_tab3")

    with comp_sub_tab2:
        render_same_project_comparison(
            df_all_source=df_raw,
            is_dark_mode=is_dark_mode,
            plotly_template=plotly_template,
            style_plotly_fig=style_plotly_fig,
            key_prefix="tab3_same_proj"
        )

# ----- TAB 4: PROPERTY LISTING -----
with tab4:
    st.markdown(f"### 📋 รายการทรัพย์สินที่ค้นพบ ({len(df_filtered):,} รายการ)")
    
    if df_filtered.empty:
        st.warning("⚠️ ไม่พบข้อมูลตามเงื่อนไข")
    else:
        # Search Box to filter Tab 4 Property Listing table
        tab4_search_query = st.text_input(
            "🔍 ค้นหา ชื่อโครงการ / รหัสทรัพย์ / ชื่อประกาศ",
            value="",
            placeholder="พิมพ์ชื่อโครงการ, รหัสทรัพย์, หรือชื่อประกาศเพื่อกรองข้อมูลในตาราง...",
            key="tab4_property_listing_search"
        )

        df_table_source = df_filtered.copy()
        if tab4_search_query:
            q_tab4 = tab4_search_query.strip().lower()
            cond_title = df_table_source['ชื่อประกาศ'].astype(str).str.lower().str.contains(q_tab4, na=False) if 'ชื่อประกาศ' in df_table_source.columns else False
            cond_code = df_table_source['รหัสทรัพย์'].astype(str).str.lower().str.contains(q_tab4, na=False) if 'รหัสทรัพย์' in df_table_source.columns else False
            cond_proj = df_table_source['ชื่อโครงการ'].astype(str).str.lower().str.contains(q_tab4, na=False) if 'ชื่อโครงการ' in df_table_source.columns else False
            df_table_source = df_table_source[cond_title | cond_code | cond_proj]

        # Show top 5,000 rows in the interactive table for performance
        display_limit = 5000
        if len(df_table_source) > display_limit:
            st.info(f"💡 แสดงผลตารางเฉพาะ {display_limit:,} รายการแรก จากที่ค้นพบ {len(df_table_source):,} รายการ เพื่อลดการใช้ข้อมูลหน้าเว็บและช่วยให้โหลดรวดเร็ว")
            df_table = df_table_source.head(display_limit)
        else:
            df_table = df_table_source
            
        df_table_show = df_table.copy()
        
        # Prepare clean numeric columns
        if 'ราคา' in df_table_show.columns:
            df_table_show['ราคาขาย (บาท)'] = pd.to_numeric(df_table_show['ราคา'], errors='coerce')
        
        sqwah_t4 = df_table_show['เนื้อที่ (ตร.ว.)'].apply(to_float_sqwah) if 'เนื้อที่ (ตร.ว.)' in df_table_show.columns else pd.Series(np.nan, index=df_table_show.index)
        if 'พื้นที่_ตารางวา' in df_table_show.columns:
            sqwah_t4 = sqwah_t4.fillna(df_table_show['พื้นที่_ตารางวา'].apply(to_float_sqwah))
        df_table_show['sqwah_calc'] = sqwah_t4
        
        df_table_show['เนื้อที่ (ไร่-งาน-ตร.ว.)'] = df_table_show['เนื้อที่ (ตร.ว.)'].apply(format_to_rai_ngan_wah) if 'เนื้อที่ (ตร.ว.)' in df_table_show.columns else df_table_show['sqwah_calc'].apply(format_to_rai_ngan_wah)
            
        if 'พื้นที่ใช้สอย (ตร.ม.)' in df_table_show.columns:
            df_table_show['พื้นที่ใช้สอย (ตร.ม.)'] = df_table_show['พื้นที่ใช้สอย (ตร.ม.)'].apply(to_float_sqm)

        # 1. ราคา/ตร.ว. (บาท) = ราคาขาย / sqwah_calc
        df_table_show['ราคา/ตร.ว. (บาท)'] = df_table_show.apply(
            lambda r: round(r['ราคาขาย (บาท)'] / r['sqwah_calc']) if (pd.notna(r.get('ราคาขาย (บาท)')) and pd.notna(r.get('sqwah_calc')) and float(r.get('sqwah_calc', 0)) > 0 and float(r.get('ราคาขาย (บาท)', 0)) > 0) else np.nan,
            axis=1
        )
        
        # 2. ราคา/ตร.ม. (บาท) = ราคาขาย / พื้นที่ใช้สอย (ตร.ม.)
        df_table_show['ราคา/ตร.ม. (บาท)'] = df_table_show.apply(
            lambda r: round(r['ราคาขาย (บาท)'] / r['พื้นที่ใช้สอย (ตร.ม.)']) if (pd.notna(r.get('ราคาขาย (บาท)')) and pd.notna(r.get('พื้นที่ใช้สอย (ตร.ม.)')) and float(r.get('พื้นที่ใช้สอย (ตร.ม.)', 0)) > 0 and float(r.get('ราคาขาย (บาท)', 0)) > 0) else np.nan,
            axis=1
        )

        for num_col in ['ละติจูด', 'ลองจิจูด']:
            if num_col in df_table_show.columns:
                df_table_show[num_col] = pd.to_numeric(df_table_show[num_col], errors='coerce')

        cols_table_raw = [
            "บริษัท", "รหัสทรัพย์", "ชื่อโครงการ", "ประเภททรัพย์", "ประเภทการขาย", 
            "ราคาขาย (บาท)", "เนื้อที่ (ไร่-งาน-ตร.ว.)", "ราคา/ตร.ว. (บาท)", "พื้นที่ใช้สอย (ตร.ม.)", "ราคา/ตร.ม. (บาท)",
            "ตำบล", "อำเภอ", "จังหวัด", "ชื่อประกาศ", "ลิงก์", 
            "ห้องนอน", "ห้องน้ำ", "ที่จอดรถ", "ID", "ละติจูด", "ลองจิจูด", "วันที่ดึงข้อมูล", "วันประกาศ"
        ]
        cols_present = [c for c in cols_table_raw if c in df_table_show.columns]
        extra_cols = [c for c in df_table_show.columns if c not in cols_present and c not in ['ราคา', 'พื้นที่_ตารางวา', 'เนื้อที่ (ตร.ว.)', 'sqwah_calc']]
        df_table_show = df_table_show[cols_present + extra_cols]

        st.dataframe(
            df_table_show,
            width="stretch",
            column_config={
                "ราคาขาย (บาท)": st.column_config.NumberColumn("ราคาขาย (บาท)", format="฿%,d"),
                "เนื้อที่ (ไร่-งาน-ตร.ว.)": st.column_config.TextColumn("เนื้อที่ (ไร่-งาน-ตร.ว.)"),
                "ราคา/ตร.ว. (บาท)": st.column_config.NumberColumn("ราคา/ตร.ว. (บาท)", format="฿%,d"),
                "พื้นที่ใช้สอย (ตร.ม.)": st.column_config.NumberColumn("พื้นที่ใช้สอย (ตร.ม.)", format="%.1f"),
                "ราคา/ตร.ม. (บาท)": st.column_config.NumberColumn("ราคา/ตร.ม. (บาท)", format="฿%,d"),
                "ละติจูด": st.column_config.NumberColumn(format="%.6f"),
                "ลองจิจูด": st.column_config.NumberColumn(format="%.6f"),
                "ลิงก์": st.column_config.LinkColumn("ลิงก์ประกาศ", display_text="🔗 เปิดดูทรัพย์")
            }
        )
        render_import_export_section(df_table_source, filename_prefix="npa_property_listing", key_suffix="tab4")
