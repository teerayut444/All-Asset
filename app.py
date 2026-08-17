import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import sys
import re
import json
import math
import subprocess
import ast
import io
from pathlib import Path
import base64
import time

from dashboard_metrics import build_kpi_summary_text

def make_clean_dropdown_label(row, show_company=False):
    """Creates clean, non-redundant dropdown labels without truncated text or duplicate codes."""
    co = str(row.get('บริษัท', '')).strip()
    title = str(row.get('ชื่อประกาศ', '')).strip()
    code = str(row.get('รหัสทรัพย์', '')).strip()
    price = row.get('ราคา', 0)
    
    try:
        f_price = float(price)
        price_str = f"฿{f_price:,.0f}" if f_price > 0 else "ไม่ระบุราคา"
    except (ValueError, TypeError):
        price_str = "ไม่ระบุราคา"
        
    has_code = code and code not in ['nan', 'None', '-']
    has_code_in_title = has_code and (code in title)
    
    clean_title = title
    if len(clean_title) > 60:
        sp_idx = clean_title.rfind(' ', 0, 60)
        if sp_idx > 35:
            clean_title = clean_title[:sp_idx] + "..."
        else:
            clean_title = clean_title[:60] + "..."

    prefix = f"[{co}] " if show_company and co and co not in ['nan', 'None', '-'] else ""
    code_suffix = "" if (has_code_in_title or not has_code) else f" ({code})"
    
    return f"{prefix}{clean_title}{code_suffix} - {price_str}"

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
            c_exp1, c_exp2 = st.columns(2)
            with c_exp1:
                st.download_button(
                    label="📊 ส่งออก Excel (.xlsx)",
                    data=convert_df_to_excel(df_to_export),
                    file_name=f"{filename_prefix}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                    key=f"btn_export_excel_{key_suffix}"
                )
            with c_exp2:
                st.download_button(
                    label="📄 ส่งออก CSV (.csv)",
                    data=convert_df_to_csv(df_to_export),
                    file_name=f"{filename_prefix}.csv",
                    mime="text/csv",
                    use_container_width=True,
                    key=f"btn_export_csv_{key_suffix}"
                )
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
    c = 2.0 * np.arcsin(np.sqrt(a))
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
    """Cached lightweight Thailand grid generator for fast, low-memory map interaction."""
    # 1. Fine grid around reference pin (±0.04 deg ~4.4km, 12x12 = 144 pts)
    u_lat, u_lng = np.meshgrid(
        np.linspace(ref_lat - 0.04, ref_lat + 0.04, 12),
        np.linspace(ref_lng - 0.04, ref_lng + 0.04, 12)
    )
    # 2. Medium grid around reference pin (±0.4 deg ~44km, 8x8 = 64 pts)
    m_lat, m_lng = np.meshgrid(
        np.linspace(ref_lat - 0.4, ref_lat + 0.4, 8),
        np.linspace(ref_lng - 0.4, ref_lng + 0.4, 8)
    )
    # 3. Country-wide Thailand macro grid (14x14 = 196 pts)
    c_lat, c_lng = np.meshgrid(
        np.linspace(5.8, 20.2, 14),
        np.linspace(97.8, 105.2, 14)
    )

    all_lats = np.concatenate([u_lat.flatten(), m_lat.flatten(), c_lat.flatten()])
    all_lngs = np.concatenate([u_lng.flatten(), m_lng.flatten(), c_lng.flatten()])

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
    # Inject CSS for a beautiful login interface
    st.html("""
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=Sarabun:wght@300;400;500;600;700&display=swap');
    
    html, body, .stApp {
        font-family: 'Outfit', 'Sarabun', sans-serif;
        background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 50%, #311042 100%) !important;
        height: 100vh !important;
        overflow: hidden !important;
    }
    
    /* Login Page Wrapper */
    div[data-testid="stAppViewContainer"] {
        background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 50%, #311042 100%) !important;
    }
    
    /* Card form styling (strictly target the form wrapper to prevent recursive nested layouts) */
    div[data-testid="stForm"] {
        background: rgba(255, 255, 255, 0.05) !important;
        backdrop-filter: blur(20px) !important;
        -webkit-backdrop-filter: blur(20px) !important;
        border: 1px solid rgba(255, 255, 255, 0.12) !important;
        border-radius: 24px !important;
        padding: 40px !important;
        box-shadow: 0 20px 50px rgba(0, 0, 0, 0.4) !important;
        max-width: 440px !important;
        margin: 15vh auto auto auto !important;
    }
    
    /* Style the input wrapper to override default white background */
    div[data-testid="stForm"] div[data-baseweb="input"] {
        border-radius: 12px !important;
        border: 1px solid rgba(255, 255, 255, 0.15) !important;
        background-color: rgba(255, 255, 255, 0.07) !important;
        transition: all 0.3s ease !important;
    }
    
    div[data-testid="stForm"] div[data-baseweb="input"] > div {
        background-color: transparent !important;
        border: none !important;
    }
    
    div[data-testid="stForm"] div[data-baseweb="input"]:focus-within {
        border-color: #6366f1 !important;
        box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.2) !important;
        background-color: rgba(255, 255, 255, 0.1) !important;
    }
    
    /* Style the actual input element */
    input[type="password"] {
        background-color: transparent !important;
        color: #ffffff !important;
        -webkit-text-fill-color: #ffffff !important;
        border: none !important;
        height: 50px !important;
        font-size: 1.05rem !important;
        text-align: center !important;
        width: 100% !important;
    }
    
    /* Form Submit Button */
    div[data-testid="stFormSubmitButton"] button {
        background: linear-gradient(135deg, #6366f1 0%, #a855f7 100%) !important;
        color: #ffffff !important;
        border: none !important;
        border-radius: 12px !important;
        font-weight: 600 !important;
        font-size: 1.1rem !important;
        height: 50px !important;
        width: 100% !important;
        box-shadow: 0 8px 20px rgba(99, 102, 241, 0.3) !important;
        transition: all 0.3s ease !important;
        margin-top: 15px !important;
    }
    
    div[data-testid="stFormSubmitButton"] button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 12px 25px rgba(99, 102, 241, 0.5) !important;
        background: linear-gradient(135deg, #4f46e5 0%, #9333ea 100%) !important;
        color: #ffffff !important;
    }
    
    div[data-testid="stFormSubmitButton"] button:active {
        transform: translateY(0) !important;
    }
    
    /* Hide sidebar and headers/footers completely during login */
    section[data-testid="stSidebar"], header, footer {
        display: none !important;
        visibility: hidden !important;
    }
    </style>
    """)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("login_form", clear_on_submit=False):
            st.markdown("""
            <div style="text-align: center; margin-bottom: 25px;">
                <div style="display: inline-flex; align-items: center; justify-content: center; width: 80px; height: 80px; background: rgba(99, 102, 241, 0.1); border-radius: 50%; margin-bottom: 20px; border: 1px solid rgba(99, 102, 241, 0.2);">
                    <i class="fa-solid fa-lock" style="font-size: 2.2rem; color: #818cf8;"></i>
                </div>
                <h2 style="color: #ffffff; font-weight: 800; font-size: 2.2rem; margin: 0 0 8px 0; background: linear-gradient(135deg, #ffffff 0%, #cbd5e1 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">All Asset NPA</h2>
                <p style="color: #94a3b8; font-size: 0.95rem; margin: 0;">กรุณาใส่รหัสผ่านเพื่อเข้าใช้งานระบบ</p>
            </div>
            """, unsafe_allow_html=True)
            
            password = st.text_input("รหัสผ่าน (Password)", type="password", key="login_password", label_visibility="collapsed")
            
            submit = st.form_submit_button("เข้าสู่ระบบ")
            
            if submit:
                if check_password(password):
                    st.session_state['logged_in'] = True
                    st.rerun()
                else:
                    st.markdown("""
                    <div style="background-color: rgba(239, 68, 68, 0.15); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.2); border-radius: 10px; padding: 12px; margin-top: 15px; font-size: 0.9rem; text-align: center; font-weight: 500;">
                        <i class="fa-solid fa-triangle-exclamation"></i> รหัสผ่านไม่ถูกต้อง กรุณาลองใหม่อีกครั้ง
                    </div>
                    """, unsafe_allow_html=True)
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

# Cache static HTML & JS libraries once in memory to save 300MB+ RAM per rerun
@st.cache_data
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
    col_side_title, col_side_theme = st.columns([0.62, 0.38])
    with col_side_title:
        st.markdown('<h3 style="color: #6366f1; margin: 0; padding-top: 4px;"><i class="fa fa-home"></i> All Asset</h3>', unsafe_allow_html=True)
    with col_side_theme:
        is_dark_mode = st.toggle("🌙 มืด", value=False, key="app_theme_mode", help="สลับระหว่างโหมดมืด (Dark Mode) และโหมดสว่าง (Light Mode)")
    
    if df_raw is not None and not df_raw.empty:
        src_name = getattr(df_raw, 'attrs', {}).get('source', 'all_assets.parquet')
        st.markdown(f"""
        <div style="background: rgba(99, 102, 241, 0.08); border: 1px solid rgba(99, 102, 241, 0.2); border-radius: 8px; padding: 6px 10px; margin-top: 5px; margin-bottom: 8px; font-size: 0.8rem; color: #6366f1; font-weight: 600;">
            <i class="fa fa-database"></i> แหล่งข้อมูล: <code>{src_name}</code><br/>
            <span style="font-size: 0.75rem; color: #475569; font-weight: normal;">📊 ข้อมูลพร้อมใช้งาน: <b>{len(df_raw):,}</b> รายการ</span>
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
    plot_font_color = "#1f2937"
    plotly_template = "plotly_white"
    
    st.markdown("### <i class='fa fa-filter'></i> ตัวกรองข้อมูลทรัพย์สิน", unsafe_allow_html=True)
    
    if df_raw is not None and not df_raw.empty:
        search_query = ""
        
        # Company Filter (Pills) with stable keys and format_func
        co_counts = df_raw['บริษัท'].value_counts()
        companies_list = ["Baania", "BAM", "SAM", "DDproperty", "Taladnudbaan", "ZmyHome"]
        
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
            
        # Group property types into common and rare (เพิ่มเติม)
        type_counts = df_by_company['ประเภททรัพย์'].value_counts()
        top_n = 7
        common_types = type_counts.head(top_n).index.tolist()
        rare_types = type_counts.index[top_n:].tolist()
        
        display_type_keys = list(common_types)
        display_type_keys.sort()
        if len(rare_types) > 0:
            display_type_keys.append("เพิ่มเติม")
            
        sanitize_session_state("filter_types", display_type_keys)
        selected_types = st.pills(
            "ประเภททรัพย์สิน", 
            options=display_type_keys, 
            format_func=lambda x: f"เพิ่มเติม ({type_counts.iloc[top_n:].sum():,})" if x == "เพิ่มเติม" else f"{x} ({type_counts.get(x, 0):,})",
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
        
        # Sale Type Filter (ประเภทการขาย)
        sale_type_counts = df_by_company['ประเภทการขาย'].astype(str).str.strip().value_counts()
        sale_types_list = ["ขาย", "ขาย/เช่า", "เช่า", "ประมูล / ขายทอดตลาด", "ขายดาวน์ / รอประกาศ"]
        available_sale_types = [s for s in sale_types_list if sale_type_counts.get(s, 0) > 0]
        
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
        
        # Province Filter
        unique_provinces = (
            df_by_company['จังหวัด']
            .dropna()
            .unique()
            .tolist()
        )
        unique_provinces.sort()
        # Clean up province lists, removing "ไม่ระบุ" or blank
        if "ไม่ระบุ" in unique_provinces:
            unique_provinces.remove("ไม่ระบุ")
            unique_provinces.append("ไม่ระบุ")
        selected_provinces = st.multiselect("จังหวัด", options=unique_provinces, default=[])
        
        # District Filter (dynamically populate from selected provinces)
        if selected_provinces:
            filtered_provinces_df = df_by_company[df_by_company['จังหวัด'].isin(selected_provinces)]
            dist_df = filtered_provinces_df[['อำเภอ', 'จังหวัด']].drop_duplicates().dropna()
            dist_df = dist_df[dist_df['อำเภอ'].astype(str).str.strip() != ""]
            unique_districts_formatted = (dist_df['อำเภอ'].astype(str) + " (" + dist_df['จังหวัด'].astype(str) + ")").tolist()
            unique_districts_formatted.sort()
            selected_districts_formatted = st.multiselect("อำเภอ / เขต", options=unique_districts_formatted, default=[])
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
        
        # Price Filter
        valid_prices = df_by_company['ราคา'].dropna()
        valid_prices = valid_prices[(valid_prices > 0) & (valid_prices <= 1000000000)]
        if not valid_prices.empty:
            options = [
                0, 500000, 1000000, 1500000, 2000000, 2500000, 3000000, 3500000, 4000000, 4500000, 5000000,
                6000000, 7000000, 8000000, 9000000, 10000000, 12000000, 15000000, 20000000, 25000000, 30000000,
                40000000, 50000000, 75000000, 100000000, 150000000, 200000000, 300000000, 500000000, 1000000000
            ]
            
            price_range = st.select_slider(
                "ช่วงราคาขาย (บาท)",
                options=options,
                value=(options[0], options[-1]),
                format_func=lambda x: f"฿{x:,.0f}" if x < 1000000 else (f"฿{x/1000000:,.1f} ล้าน" if x % 1000000 != 0 else f"฿{x/1000000:,.0f} ล้าน")
            )
        else:
            options = [0, 1000000000]
            price_range = (0, 1000000000)
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

def style_plotly_fig(fig):
    bg = "#1e293b" if is_dark_mode else "#ffffff"
    font_c = "#f8fafc" if is_dark_mode else "#0f172a"
    tmpl = "plotly_dark" if is_dark_mode else "plotly_white"
    fig.update_layout(
        template=tmpl,
        paper_bgcolor=bg,
        plot_bgcolor=bg,
        font=dict(color=font_c, family="Outfit, Sarabun, sans-serif"),
        title_font=dict(color=font_c, family="Outfit, Sarabun, sans-serif"),
        legend=dict(font=dict(color=font_c))
    )
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
    display: flex;
    gap: 12px;
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
        top_n = 7
        rare_types = type_counts.index[top_n:].tolist()
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
    is_default_price_range = (price_range[0] == options[0] and price_range[1] == options[-1])
    if is_default_price_range:
        df_filtered = df_filtered[
            (df_filtered['ราคา'].isna()) | 
            ((df_filtered['ราคา'] >= price_range[0]) & (df_filtered['ราคา'] <= price_range[1]))
        ]
    else:
        df_filtered = df_filtered[
            (df_filtered['ราคา'].notna()) & 
            (df_filtered['ราคา'] >= price_range[0]) & 
            (df_filtered['ราคา'] <= price_range[1])
        ]

# ----------------- GLOBAL KPI METRICS COMPUTATION -----------------
total_count = len(df_raw) if df_raw is not None else 0
filtered_count = len(df_filtered)
valid_prices_filtered = df_filtered['ราคา'].dropna()

if not valid_prices_filtered.empty:
    total_value = valid_prices_filtered.sum() / 1e6
    median_price = valid_prices_filtered.median() / 1e6
    max_price = valid_prices_filtered.max() / 1e6
else:
    total_value = 0.0
    median_price = 0.0
    max_price = 0.0

total_count_str = f"{total_count:,.0f}"
filtered_count_str = f"{filtered_count:,.0f}"
total_value_str = f"฿{total_value:,.2f}M"
median_price_str = f"฿{median_price:,.2f}M"
max_price_str = f"฿{max_price:,.2f}M"

active_co_counts = df_filtered['บริษัท'].value_counts()
active_companies = selected_companies if selected_companies else ["Baania", "BAM", "SAM", "DDproperty", "Taladnudbaan", "ZmyHome"]
co_breakdown_items = [f"{co}: {active_co_counts.get(co, 0):,}" for co in active_companies if active_co_counts.get(co, 0) > 0]
co_breakdown_str = " | ".join(co_breakdown_items) if co_breakdown_items else "ไม่มีรายการในตัวกรองนี้"

summary_text = build_kpi_summary_text(total_count, filtered_count)

floating_kpi_html = f"""
<div class="floating-kpi-container" style="margin-bottom: 20px;">
    <div class="floating-card">
        <div class="floating-card-title"><i class="fa fa-list" style="color: #6366f1;"></i> ทรัพย์สินที่พบ</div>
        <div class="floating-card-value">{filtered_count_str}</div>
        <div class="floating-card-sub">{summary_text}</div>
    </div>
    <div class="floating-card">
        <div class="floating-card-title"><i class="fa fa-wallet" style="color: #06b6d4;"></i> มูลค่ารวมทรัพย์สิน</div>
        <div class="floating-card-value">{total_value_str}</div>
        <div class="floating-card-sub">เฉพาะตามตัวกรองแถบซ้าย (ล้านบาท)</div>
    </div>
    <div class="floating-card">
        <div class="floating-card-title"><i class="fa fa-tags" style="color: #10b981;"></i> ราคากลาง (Median)</div>
        <div class="floating-card-value">{median_price_str}</div>
        <div class="floating-card-sub">ค่ากลางล้านบาท / ทรัพย์สิน</div>
    </div>
    <div class="floating-card">
        <div class="floating-card-title"><i class="fa fa-arrow-up" style="color: #f59e0b;"></i> ราคาสูงสุด</div>
        <div class="floating-card-value">{max_price_str}</div>
        <div class="floating-card-sub">มูลค่าสูงสุดตามตัวกรองแถบซ้าย</div>
    </div>
</div>
"""

st.markdown(floating_kpi_html, unsafe_allow_html=True)

# ----------------- TABS CREATION -----------------
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🗺️ แผนที่พิกัดทรัพย์ (Map Grid)", 
    "📈 สถิติ & วิเคราะห์ (Analytics)", 
    "📋 รายการทรัพย์สิน (Property Listing)", 
    "🔍 เปรียบเทียบตำแหน่ง (Comparison)",
    "💎 ค้นหาของดีราคาถูก (Bargain Hunter)"
])

# ----- TAB 1: MAP GRID -----
with tab1:
    with st.container(key="tab_map"):
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
            prices = map_data['ราคา']
            map_data['ราคาขาย'] = np.where(
                prices.notna() & (prices > 0),
                '฿' + prices.map('{:,.0f}'.format) + ' บาท',
                'ไม่ระบุ'
            )
            
        if map_data.empty:
            progress_bar.empty()
            st.warning("⚠️ ไม่พบพิกัดตำแหน่ง ละติจูด/ลองจิจูด ในรายการทรัพย์สินที่คุณเลือกค้นหา")
        else:
            # Step 3: Color mapping (60%)
            progress_bar.progress(60, text="กำลังจัดเตรียมสีตามบริษัทคู่แข่ง (60%)...")
            title_col = 'ชื่อประกาศ' if 'ชื่อประกาศ' in map_data.columns else ('ชื่อโครงการ' if 'ชื่อโครงการ' in map_data.columns else 'รหัสทรัพย์')
            titles = map_data[title_col].astype(object).fillna('ไม่มีชื่อ').astype(str).str[:30].values
            ids = map_data['รหัสทรัพย์'].astype(object).fillna('-').astype(str).str[:15].values
            provs = map_data['จังหวัด'].astype(object).fillna('-').astype(str).values
            types = map_data['ประเภททรัพย์'].astype(object).fillna('-').astype(str).values
            companies = map_data['บริษัท'].astype(object).fillna('-').astype(str).values
            prices = map_data['ราคาขาย'].astype(str).values
            
            COMPANY_COLORS = {"Baania": [245, 158, 11], "BAM": [59, 130, 246], "SAM": [16, 185, 129], "DDproperty": [168, 85, 247], "Taladnudbaan": [6, 182, 212], "ZmyHome": [236, 72, 153]}
            DEFAULT_COLOR = [148, 163, 184]
            r_vals, g_vals, b_vals = [], [], []
            for company in map_data['บริษัท']:
                color = COMPANY_COLORS.get(company, DEFAULT_COLOR)
                r_vals.append(color[0])
                g_vals.append(color[1])
                b_vals.append(color[2])
                
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
            
            body_theme_class = "dark-theme" if is_dark_mode else ""
            html_content = html_content.replace("BODY_CLASS_PLACEHOLDER", body_theme_class)

            map_baania_count = len(map_data[map_data['บริษัท'] == 'Baania'])
            map_bam_count = len(map_data[map_data['บริษัท'] == 'BAM'])
            map_sam_count = len(map_data[map_data['บริษัท'] == 'SAM'])
            map_ddproperty_count = len(map_data[map_data['บริษัท'] == 'DDproperty'])
            map_taladnudbaan_count = len(map_data[map_data['บริษัท'] == 'Taladnudbaan'])
            map_zmyhome_count = len(map_data[map_data['บริษัท'] == 'ZmyHome'])

            html_content = html_content.replace("BAANIA_COUNT", f"{map_baania_count:,}")
            html_content = html_content.replace("BAM_COUNT", f"{map_bam_count:,}")
            html_content = html_content.replace("SAM_COUNT", f"{map_sam_count:,}")
            html_content = html_content.replace("DDPROPERTY_COUNT", f"{map_ddproperty_count:,}")
            html_content = html_content.replace("TALADNUDBAAN_COUNT", f"{map_taladnudbaan_count:,}")
            html_content = html_content.replace("ZMYHOME_COUNT", f"{map_zmyhome_count:,}")
            
            # Step 6: Finish (100%)
            progress_bar.progress(100, text="เรนเดอร์แผนที่สำเร็จแล้ว (100%)")
            time.sleep(0.1)
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
            "📐 ราคาต่อตารางเมตร (Price per Sq.M. Analysis)"
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
                    color_discrete_map={"Baania": "#f59e0b", "BAM": "#3b82f6", "SAM": "#10b981", "DDproperty": "#a855f7", "Taladnudbaan": "#06b6d4", "ZmyHome": "#ec4899"},
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
                    color_discrete_map={"Baania": "#f59e0b", "BAM": "#3b82f6", "SAM": "#10b981", "DDproperty": "#a855f7", "Taladnudbaan": "#06b6d4", "ZmyHome": "#ec4899"},
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
                fig_prov.update_layout(title_font=dict(size=14, family="Outfit"), coloraxis_showscale=False)
                st.plotly_chart(style_plotly_fig(fig_prov), width="stretch", theme=None)
                
            st.markdown("---")
            col_c5, col_c6 = st.columns(2)
            
            # 5. Price Distribution (Capped at 25 Million Baht)
            with col_c5:
                df_price_capped = df_filtered[(df_filtered['ราคา'].notna()) & (df_filtered['ราคา'] <= 25000000)].copy()
                
                # Simplify property type mapping for visualization
                def map_simplified_type(t):
                    t_str = str(t).strip()
                    if 'ที่ดินเปล่า' in t_str:
                        return 'ที่ดินเปล่า'
                    elif 'คอนโด' in t_str:
                        return 'คอนโด'
                    elif 'บ้านเดี่ยว' in t_str or 'บ้านแฝด' in t_str or 'พูลวิลล่า' in t_str or 'บ้าน' in t_str:
                        return 'บ้านเดี่ยว'
                    elif 'ทาวน์โฮม' in t_str or 'ทาวน์เฮ้าส์' in t_str or 'ทาวน์เฮาส์' in t_str:
                        return 'ทาวน์เฮ้าส์'
                    return np.nan
                
                df_price_capped['ประเภททรัพย์ '] = df_price_capped['ประเภททรัพย์'].apply(map_simplified_type)
                df_price_capped = df_price_capped[df_price_capped['ประเภททรัพย์ '].notna()]
                
                # Optimize by subsetting and sampling to 50k rows to prevent browser crash
                df_hist_data = df_price_capped[['ราคา', 'ประเภททรัพย์ ']]
                if len(df_hist_data) > 50000:
                    df_hist_data = df_hist_data.sample(n=50000, random_state=42)
                
                color_map_dist = {
                    "ที่ดินเปล่า": "#56B4E9", 
                    "บ้านเดี่ยว": "#CC79A7", 
                    "คอนโด": "#E69F00", 
                    "ทาวน์เฮ้าส์": "#107c41"
                }
                
                fig_price_dist = px.histogram(
                    df_hist_data,
                    x='ราคา',
                    color='ประเภททรัพย์ ',
                    nbins=40,
                    title='การกระจายตัวของราคาทรัพย์สิน (ไม่เกิน 25 ล้านบาท)',
                    labels={'ราคา': 'ราคาเริ่มต้น (บาท)', 'ประเภททรัพย์ ': 'ประเภททรัพย์'},
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
                
            # 6. Price vs. Usable Area (Sq.M.)
            with col_c6:
                df_usable_area = df_filtered[
                    (df_filtered['พื้นที่ใช้สอย (ตร.ม.)'].notna()) & 
                    (df_filtered['พื้นที่ใช้สอย (ตร.ม.)'] < 1500) & 
                    (df_filtered['ราคา'].notna()) & 
                    (df_filtered['ราคา'] <= 60000000)
                ].copy()
                
                df_usable_area['ประเภททรัพย์ '] = df_usable_area['ประเภททรัพย์'].apply(map_simplified_type)
                df_usable_area = df_usable_area[
                    df_usable_area['ประเภททรัพย์ '].notna() & 
                    (df_usable_area['ประเภททรัพย์ '] != 'ที่ดินเปล่า')
                ]
                
                # Optimize by subsetting and sampling to 10k points to prevent scatter plot lag
                df_scatter_data = df_usable_area[['พื้นที่ใช้สอย (ตร.ม.)', 'ราคา', 'ประเภททรัพย์ ', 'ชื่อประกาศ', 'จังหวัด', 'อำเภอ']]
                if len(df_scatter_data) > 10000:
                    df_scatter_data = df_scatter_data.sample(n=10000, random_state=42)
                
                color_map_scatter = {
                    "บ้านเดี่ยว": "#3182bd", 
                    "คอนโด": "#9ecae1", 
                    "ทาวน์เฮ้าส์": "#ef3b2c",
                }
                
                fig_price_vs_area = px.scatter(
                    df_scatter_data,
                    x='พื้นที่ใช้สอย (ตร.ม.)',
                    y='ราคา',
                    color='ประเภททรัพย์ ',
                    hover_data=['ชื่อประกาศ', 'จังหวัด', 'อำเภอ'],
                    title='ราคาเริ่มต้น เทียบกับ พื้นที่ใช้สอย (ตร.ม.)',
                    labels={'พื้นที่ใช้สอย (ตร.ม.)': 'พื้นที่ใช้สอย (ตร.ม.)', 'ราคา': 'ราคาเริ่มต้น (บาท)', 'ประเภททรัพย์ ': 'ประเภททรัพย์'},
                    color_discrete_map=color_map_scatter,
                    template=plotly_template
                )
                fig_price_vs_area.update_layout(
                    title_font=dict(size=14, family="Outfit"),
                    xaxis_title="พื้นที่ใช้สอย (ตร.ม.)",
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
                
            companies = sorted(comp_type_df['บริษัท'].unique())
            
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
                TOP_TYPES = ['บ้านเดี่ยว', 'คอนโด', 'ทาวน์เฮ้าส์', 'ที่ดินเปล่า', 'อาคารพาณิชย์', 'โรงงาน/โกดัง', 'บ้านแฝด']
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
            
        with sub_tab3:
            st.markdown("#### 📐 วิเคราะห์ราคาเฉลี่ยและราคากลางต่อตารางเมตร (Price per Sq.M. Insights)")
            st.write("เปรียบเทียบราคากลางต่อตารางเมตรแยกตามประเภททรัพย์สินและบริษัทคู่แข่ง (ตรงตามประเภททรัพย์สินที่เลือกทางแถบฝั่งซ้าย)")
            
            # Calculate fallback price per sq.m. (using sq.m. or 1 sq.wah = 4 sq.m.)
            sqm_calc = np.where(
                (df_filtered['ราคาต่อตารางเมตร'].notna()) & (df_filtered['ราคาต่อตารางเมตร'] > 0),
                df_filtered['ราคาต่อตารางเมตร'],
                np.where(
                    (df_filtered['พื้นที่_ตารางวา'] > 0) & (df_filtered['ราคา'] > 0),
                    df_filtered['ราคา'] / (df_filtered['พื้นที่_ตารางวา'] * 4.0),
                    np.nan
                )
            )
            df_filtered['ราคาต่อตารางเมตร_คำนวณ'] = sqm_calc

            # Filter properties with valid price per sq.m. and positive price
            area_df = df_filtered[
                (df_filtered['ราคาต่อตารางเมตร_คำนวณ'].notna()) & 
                (df_filtered['ราคาต่อตารางเมตร_คำนวณ'] > 0) & 
                (df_filtered['ราคาต่อตารางเมตร_คำนวณ'] < 5000000) # Exclude extreme outliers
            ].copy()
            
            if not area_df.empty:
                # Group directly by Company and exact Property Type (matching the sidebar selection)
                median_per_sqm = area_df.groupby(['บริษัท', 'ประเภททรัพย์'])['ราคาต่อตารางเมตร_คำนวณ'].median().reset_index()
                median_per_sqm.columns = ['บริษัท', 'ประเภททรัพย์', 'ราคากลางต่อ ตร.ม. (บาท)']
                
                fig_sqm = px.bar(
                    median_per_sqm,
                    x='ประเภททรัพย์',
                    y='ราคากลางต่อ ตร.ม. (บาท)',
                    color='บริษัท',
                    barmode='group',
                    title='เปรียบเทียบราคากลาง (Median) ต่อตารางเมตร เชื่อมโยงกับประเภททรัพย์สินฝั่งซ้าย',
                    color_discrete_map={"Baania": "#f59e0b", "BAM": "#3b82f6", "SAM": "#10b981", "DDproperty": "#a855f7", "Taladnudbaan": "#06b6d4", "ZmyHome": "#ec4899"},
                    template=plotly_template
                )
                fig_sqm.update_layout(
                    title_font=dict(size=14, family="Outfit"),
                    xaxis_title="ประเภททรัพย์สิน (จากแถบตัวกรองฝั่งซ้าย)",
                    yaxis_title="ราคากลางต่อ ตร.ม. (บาท)",
                    legend_title="บริษัท"
                )
                st.plotly_chart(style_plotly_fig(fig_sqm), width="stretch", theme=None)

                # Show Summary Pivot Table
                st.markdown("##### 📋 ตารางสรุปราคากลางต่อตารางเมตร (บาท/ตร.ม.) แยกตามประเภททรัพย์สินฝั่งซ้าย รายบริษัท")
                pivot_sqm = median_per_sqm.pivot(index='บริษัท', columns='ประเภททรัพย์', values='ราคากลางต่อ ตร.ม. (บาท)')
                st.dataframe(
                    pivot_sqm,
                    width="stretch",
                    column_config={
                        col: st.column_config.NumberColumn(format="%,d") for col in pivot_sqm.columns if pd.notna(col)
                    }
                )
            else:
                st.warning("⚠️ ไม่มีข้อมูลพื้นที่ใช้สอยหรือราคาทรัพย์สินสำหรับวิเคราะห์ราคาต่อตารางเมตร")

# ----- TAB 3: PROPERTY LISTING -----
with tab3:
    st.markdown(f"### 📋 รายการทรัพย์สินที่ค้นพบ ({total_count:,} รายการ)")
    
    if df_filtered.empty:
        st.warning("⚠️ ไม่พบข้อมูลตามเงื่อนไข")
    else:
        # Search Box to filter Tab 3 Property Listing table
        tab3_search_query = st.text_input(
            "🔍 ค้นหา ชื่อโครงการ / รหัสทรัพย์ / ชื่อประกาศ",
            value="",
            placeholder="พิมพ์ชื่อโครงการ, รหัสทรัพย์, หรือชื่อประกาศเพื่อกรองข้อมูลในตาราง...",
            key="tab3_property_listing_search"
        )

        df_table_source = df_filtered.copy()
        if tab3_search_query:
            q_tab3 = tab3_search_query.strip().lower()
            cond_title = df_table_source['ชื่อประกาศ'].astype(str).str.lower().str.contains(q_tab3, na=False)
            cond_code = df_table_source['รหัสทรัพย์'].astype(str).str.lower().str.contains(q_tab3, na=False)
            cond_proj = df_table_source['ชื่อโครงการ'].astype(str).str.lower().str.contains(q_tab3, na=False) if 'ชื่อโครงการ' in df_table_source.columns else False
            df_table_source = df_table_source[cond_title | cond_code | cond_proj]

        # Show top 5,000 rows in the interactive table for performance
        display_limit = 5000
        if len(df_table_source) > display_limit:
            st.info(f"💡 แสดงผลตารางเฉพาะ {display_limit:,} รายการแรก จากที่ค้นพบ {len(df_table_source):,} รายการ เพื่อลดการใช้ข้อมูลหน้าเว็บและช่วยให้โหลดรวดเร็ว")
            df_table = df_table_source.head(display_limit)
        else:
            df_table = df_table_source
            
        cols_table_raw = [
            "บริษัท", "รหัสทรัพย์", "ชื่อโครงการ", "ชื่อประกาศ", "ประเภททรัพย์", 
            "ประเภทการขาย", "ราคา", "จังหวัด", "อำเภอ", "ตำบล",
            "พื้นที่ (ไร่-งาน-วา)", "พื้นที่ใช้สอย (ตร.ม.)", "ห้องนอน", "ห้องน้ำ", "ที่จอดรถ", "วันที่ดึงข้อมูล"
        ]
        df_table_show = df_table[[c for c in cols_table_raw if c in df_table.columns]].copy()
        if 'ราคา' in df_table_show.columns:
            df_table_show['ราคาขาย (บาท)'] = pd.to_numeric(df_table_show['ราคา'], errors='coerce')
            df_table_show = df_table_show.drop(columns=['ราคา'])

        cols_table = [
            "บริษัท", "รหัสทรัพย์", "ชื่อโครงการ", "ชื่อประกาศ", "ประเภททรัพย์", 
            "ประเภทการขาย", "ราคาขาย (บาท)", "จังหวัด", "อำเภอ", "ตำบล",
            "พื้นที่ (ไร่-งาน-วา)", "พื้นที่ใช้สอย (ตร.ม.)", "ห้องนอน", "ห้องน้ำ", "ที่จอดรถ", "วันที่ดึงข้อมูล"
        ]
        df_table_show = df_table_show[[c for c in cols_table if c in df_table_show.columns]]

        st.dataframe(
            df_table_show,
            width="stretch",
            column_config={
                "ราคาขาย (บาท)": st.column_config.NumberColumn("ราคาขาย (บาท)", format="%,d"),
                "พื้นที่ใช้สอย (ตร.ม.)": st.column_config.NumberColumn(format="%.1f")
            }
        )

        render_import_export_section(df_table_source, filename_prefix="npa_property_listing", key_suffix="tab3")

# ----- TAB 4: COMPARISON -----
with tab4:
    comp_sub_tab1, comp_sub_tab2 = st.tabs([
        "📍 เปรียบเทียบตามรัศมีทำเล (Radius Location Analysis)",
        "⚔️ เปรียบเทียบแบบ 1 ต่อ 1 (1-on-1 Asset Comparison)"
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

            if "prev_ref_method" not in st.session_state:
                st.session_state["prev_ref_method"] = "📌 ระบุพิกัดด้วยตัวเอง (Manual Coordinates)"

            ref_method = st.radio(
                "วิธีการกำหนดจุดอ้างอิง",
                options=["📌 ระบุพิกัดด้วยตัวเอง (Manual Coordinates)", "🏠 เลือกจากรายการทรัพย์สินในระบบ (Choose from Asset)"],
                horizontal=True,
                key="comp_ref_method"
            )

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
                txt = str(r.get('พื้นที่ (ไร่-งาน-วา)', r.get('พื้นที่ดิน', ''))).strip()
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

            # Helper to calculate Median Price per Sq.Wah for a specific local area (Subdistrict/District/Province)
            def get_location_median_sqwah(df, prov, dist, subdist=None):
                if df is None or df.empty:
                    return np.nan, "ไม่มีข้อมูล"
                
                loc_df = pd.DataFrame()
                loc_label = ""
                # 1. Try exact Subdistrict first
                if subdist and pd.notna(subdist) and str(subdist).strip() not in ['', '-', 'nan']:
                    loc_df = df[(df['จังหวัด'] == prov) & (df['ตำบล'] == subdist)]
                    loc_label = f"ย่าน ต.{subdist} อ.{dist}"
                
                # 2. Fallback to District if < 3 properties
                if loc_df.empty or len(loc_df) < 3:
                    if dist and pd.notna(dist) and str(dist).strip() not in ['', '-', 'nan']:
                        loc_df = df[(df['จังหวัด'] == prov) & (df['อำเภอ'] == dist)]
                        loc_label = f"ย่าน อ.{dist} จ.{prov}"
                
                # 3. Fallback to Province
                if loc_df.empty or len(loc_df) < 3:
                    if prov and pd.notna(prov) and str(prov).strip() not in ['', '-', 'nan']:
                        loc_df = df[df['จังหวัด'] == prov]
                        loc_label = f"ย่าน จ.{prov}"
                        
                if loc_df.empty:
                    return np.nan, "ไม่มีข้อมูล"
                    
                if 'ราคาต่อตารางวา' in loc_df.columns:
                    valid_u = loc_df['ราคาต่อตารางวา'].dropna()
                    valid_u = valid_u[valid_u > 0]
                elif 'พื้นที่_ตารางวา' in loc_df.columns:
                    valid_mask = (loc_df['พื้นที่_ตารางวา'] > 0) & (loc_df['ราคา'] > 0)
                    valid_u = (loc_df.loc[valid_mask, 'ราคา'] / loc_df.loc[valid_mask, 'พื้นที่_ตารางวา']).dropna()
                else:
                    sqwah = loc_df.apply(parse_land_sqwah, axis=1)
                    valid_u = np.where((sqwah.notna()) & (sqwah > 0) & (loc_df['ราคา'] > 0), loc_df['ราคา'] / sqwah, np.nan)
                    valid_u = pd.Series(valid_u).dropna()
                    
                if valid_u.empty:
                    return np.nan, loc_label
                    
                return float(valid_u.median()), f"{loc_label} ({len(valid_u):,} รายการ)"

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
                    all_raw_types = sorted([str(t) for t in df_raw['ประเภททรัพย์'].dropna().unique()]) if df_raw is not None else []
                    valid_ref_types = ["ทั้งหมด"] + all_raw_types
                    sanitize_session_state("comp_sel_type", valid_ref_types, "ทั้งหมด")
                    sel_ref_type = st.selectbox(
                        "ประเภททรัพย์ (เลือกจุดอ้างอิง)",
                        options=valid_ref_types,
                        index=0,
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

                            area_lines = []
                            if pd.notna(inp_land_area) and inp_land_area > 0:
                                area_lines.append(f"- **เนื้อที่:** {inp_land_area:,.1f} ตารางวา")
                            if pd.notna(inp_use_area) and inp_use_area > 0:
                                area_lines.append(f"- **พื้นที่ใช้สอย:** {inp_use_area:,.1f} ตารางเมตร")
                            if not area_lines:
                                area_lines.append("- **เนื้อที่ / พื้นที่ใช้สอย:** ไม่ระบุ")
                            area_info_str = "\n".join(area_lines)

                            asset_url = str(selected_asset.get('ลิงก์', '')).strip()
                            link_str = f"- **ลิงก์ประกาศ:** [{asset_url}]({asset_url})" if asset_url.startswith('http') else "- **ลิงก์ประกาศ:** ไม่พบลิงก์"

                            st.info(f"""
                            🏠 **รายละเอียดทรัพย์อ้างอิงที่เลือก**:
                            - **ชื่อประกาศ:** {selected_asset['ชื่อประกาศ']}
                            - **รหัสทรัพย์:** {selected_asset['รหัสทรัพย์']} ({selected_asset['บริษัท']})
                            - **พิกัด:** {inp_lat:.6f}, {inp_lng:.6f}
                            - **ราคาขาย:** ฿{inp_price:,.0f} บาท
                            - **ประเภท:** {inp_type}
                            {area_info_str}
                            {link_str}
                            """)
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

                # Select Property Type first so area field adapts immediately
                prop_options = sorted([str(t) for t in df_raw['ประเภททรัพย์'].dropna().unique()]) if df_raw is not None and not df_raw.empty else ["บ้านเดี่ยว"]
                inp_type = st.selectbox("ประเภททรัพย์ของจุดอ้างอิง", options=prop_options, index=0, key="comp_manual_type")

                c_m1, c_m2 = st.columns(2)
                with c_m1:
                    inp_lat = st.number_input("ละติจูด (Latitude)", value=def_manual_lat, format="%.6f", key="comp_manual_lat")
                    inp_lng = st.number_input("ลองจิจูด (Longitude)", value=def_manual_lng, format="%.6f", key="comp_manual_lng")
                    inp_price = st.number_input("ราคาของจุดอ้างอิง (บาท)", min_value=0.0, value=5000000.0, step=100000.0, format="%.0f", key="comp_manual_price")
                with c_m2:
                    is_condo_ref = any(kw in str(inp_type).lower() for kw in ['คอนโด', 'ห้องชุด'])
                    default_land_w = 0.0 if is_condo_ref else 50.0
                    default_use_sqm = 35.0 if is_condo_ref else 150.0
                    
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

            # Price Range Filter for Comparison
            valid_prices = df_raw['ราคา'].dropna() if df_raw is not None else pd.Series()
            min_price_val = float(valid_prices.min()) if not valid_prices.empty else 0.0
            max_price_val = float(valid_prices.max()) if not valid_prices.empty else 100000000.0

            compare_price_range = st.slider(
                "ช่วงราคาขาย (บาท) (เปรียบเทียบ)",
                min_value=min_price_val,
                max_value=max_price_val,
                value=(min_price_val, max_price_val),
                format="%d",
                key="comp_price_slider"
            )

            filter_by_type = st.checkbox("กรองเฉพาะประเภททรัพย์สินที่เหมือนกับจุดอ้างอิง (ประเภทเดียวกัน)", value=True)

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
                    if not valid_prices.empty:
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
                            return np.nan, "-", "-", "-"
                            
                        if is_condo:
                            sqm = r.get('พื้นที่ใช้สอย (ตร.ม.)')
                            if pd.notna(sqm) and float(sqm) > 0:
                                u_price = float(price) / float(sqm)
                                return u_price, "ตร.ม.", f"{float(sqm):,.1f} ตร.ม.", "พื้นที่ใช้สอย"
                        else:
                            sqwah = r.get('พื้นที่_ตารางวา')
                            if pd.isna(sqwah) or float(sqwah or 0) <= 0:
                                sqwah = parse_land_sqwah(r)
                            if pd.notna(sqwah) and float(sqwah) > 0:
                                u_price = float(price) / float(sqwah)
                                return u_price, "วา", f"{float(sqwah):,.1f} วา", "พื้นที่ดิน"
                        return np.nan, "-", "-", "-"

                    unit_results = nearby_df.apply(get_unit_info, axis=1)
                    nearby_df['ราคาต่อหน่วย'] = [res[0] for res in unit_results]
                    nearby_df['หน่วยวัด'] = [res[1] for res in unit_results]
                    nearby_df['ขนาดพื้นที่'] = [res[2] for res in unit_results]
                    nearby_df['ฐานพื้นที่คำนวณ'] = [res[3] for res in unit_results]

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
                                    unit_lbl_sel = sel_type_df[sel_type_df['หน่วยวัด'] != '-']['หน่วยวัด'].mode()[0] if not sel_type_df[sel_type_df['หน่วยวัด'] != '-'].empty else "วา"
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
                            ref_val_html = f"฿{ref_u_p:,.0f} <span style='font-size:0.85rem; font-weight:normal; color:#475569;'>/วา</span>"
                            sqm_sub = f" | ใช้สอย {float(inp_use_area):,.1f} ตร.ม." if has_sqm else ""
                            ref_sub_html = f"""
                            <div style='margin-top: 6px; line-height: 1.55; font-size: 0.82rem; color: #475569;'>
                                <div>💰 <b>ราคารวม:</b> ฿{inp_price:,.0f}</div>
                                <div>🏠 <b>ทรัพย์สิน:</b> {inp_type} ({float(inp_land_area):,.1f} วา{sqm_sub})</div>
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
                            rl_val_html = f"฿{median_raw_land:,.0f} <span style='font-size:0.85rem; font-weight:normal; color:#475569;'>/วา</span>"
                            rl_sub_html = f"""
                            <div style='margin-top: 6px; line-height: 1.55; font-size: 0.82rem; color: #334155;'>
                                <div>📊 <b>ช่วงราคา:</b> ฿{min_raw_land:,.0f} - ฿{max_raw_land:,.0f} /วา</div>
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

                        st.markdown("<br/>", unsafe_allow_html=True)

                        # Summary info box focused on selected type vs raw land price (Median)
                        summary_bullets = []
                        if has_sel_u_stats:
                            area_src = "พื้นที่ใช้สอย (ตร.ม.)" if unit_lbl_sel == "บาท/ตร.ม." else "เนื้อที่ (ตารางวา)"
                            summary_bullets.append(f"- **ราคากลางต่อหน่วย (Median) เฉพาะ [{inp_type}]:** อยู่ที่ **฿{median_u_sel:,.0f} {unit_lbl_sel}** (คำนวณจาก{area_src} | ช่วงราคาตลาดระหว่าง ฿{min_u_sel:,.0f} ถึง ฿{max_u_sel:,.0f} {unit_lbl_sel})")

                        if has_raw_land:
                            summary_bullets.append(f"- **ราคากลางต่อตารางวา (Median) ที่ดินเปล่าในทำเล:** อยู่ที่ **฿{median_raw_land:,.0f} บาท/ตารางวา** (คำนวณจากเนื้อที่ | ช่วงราคาที่ดินเปล่าในทำเล ฿{min_raw_land:,.0f} ถึง ฿{max_raw_land:,.0f} บาท/วา จาก {count_raw_land:,} รายการ)")

                        # Local area median sqwah calculation for reference point location
                        ref_prov = nearby_df['จังหวัด'].iloc[0] if 'จังหวัด' in nearby_df.columns and not nearby_df['จังหวัด'].empty else None
                        ref_dist = nearby_df['อำเภอ'].iloc[0] if 'อำเภอ' in nearby_df.columns and not nearby_df['อำเภอ'].empty else None
                        ref_subdist = nearby_df['ตำบล'].iloc[0] if 'ตำบล' in nearby_df.columns and not nearby_df['ตำบล'].empty else None

                        loc_u_med, loc_u_lbl = get_location_median_sqwah(df_raw, ref_prov, ref_dist, ref_subdist)
                        if pd.notna(loc_u_med) and loc_u_med > 0:
                            summary_bullets.append(f"- **ราคากลางต่อตารางวา (Median ย่านทำเลของแถบนั้น):** อยู่ที่ **฿{loc_u_med:,.0f} บาท/ตารางวา** (อ้างอิง {loc_u_lbl})")

                        unit_text_str = "\n".join(summary_bullets) if summary_bullets else "- ไม่พบข้อมูลสำหรับการวิเคราะห์เปรียบเทียบในเงื่อนไขนี้"

                        st.info(f"""
                        💡 **บทวิเคราะห์ราคากลางต่อหน่วย (Median Analysis) เทียบกับฐานราคาที่ดินเปล่าในทำเล**:
                        {unit_text_str}
                        """)

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

                    map_points = []
                    # Reference point
                    map_points.append({
                        "ละติจูด": inp_lat,
                        "ลองจิจูด": inp_lng,
                        "ชื่อ": f"📍 จุดอ้างอิง: {inp_name}",
                        "รหัสทรัพย์": "จุดอ้างอิง",
                        "ราคา (บาท)": f"฿{inp_price:,.0f}",
                        "ประเภท": inp_type,
                        "ระยะทาง": "0.00 กม.",
                        "ขนาดพิกัด": 12,
                        "บริษัท": "จุดอ้างอิง"
                    })

                    # Found points (display up to top 400 nearest properties on interactive map to keep memory low)
                    plot_nearby_df = map_nearby_df.head(400) if len(map_nearby_df) > 400 else map_nearby_df
                    for _, r in plot_nearby_df.iterrows():
                        formatted_price = f"฿{r['ราคา']:,.0f}" if pd.notna(r['ราคา']) else "ไม่ระบุ"
                        asset_code = str(r.get('รหัสทรัพย์', '-'))
                        dist_km = f"{r['ระยะทาง (กม.)']:.2f}" if pd.notna(r.get('ระยะทาง (กม.)')) else "-"
                        prop_type = str(r.get('ประเภททรัพย์', '-'))
                        company_name = str(r.get('บริษัท', '-'))
                        map_points.append({
                            "ละติจูด": r["ละติจูด"],
                            "ลองจิจูด": r["ลองจิจูด"],
                            "ชื่อ": str(r['ชื่อประกาศ']),
                            "รหัสทรัพย์": asset_code,
                            "ราคา (บาท)": formatted_price,
                            "ประเภท": prop_type,
                            "ระยะทาง": f"{dist_km} กม.",
                            "ขนาดพิกัด": 8,
                            "บริษัท": company_name
                        })

                    map_compare_df = pd.DataFrame(map_points)
                    fig_compare = px.scatter_map(
                        map_compare_df,
                        lat="ละติจูด",
                        lon="ลองจิจูด",
                        color="บริษัท",
                        hover_name="ชื่อ",
                        custom_data=["บริษัท", "ราคา (บาท)", "ประเภท", "ระยะทาง", "รหัสทรัพย์"],
                        hover_data={
                            "รหัสทรัพย์": False,
                            "ราคา (บาท)": False,
                            "ประเภท": False,
                            "ระยะทาง": False,
                            "บริษัท": False,
                            "ละติจูด": False,
                            "ลองจิจูด": False
                        },
                        zoom=11.5,
                        height=620,
                        color_discrete_map={
                            "จุดอ้างอิง": "#ef4444",
                            "Baania": "#f59e0b",
                            "BAM": "#3b82f6",
                            "SAM": "#10b981",
                            "DDproperty": "#a855f7",
                            "Taladnudbaan": "#06b6d4",
                            "ZmyHome": "#ec4899"
                        },
                        template=plotly_template
                    )
                    fig_compare.update_traces(
                        hovertemplate=(
                            "<b>%{hovertext}</b><br>"
                            "━━━━━━━━━━━━━━━━━━━━<br>"
                            "🔑 รหัสทรัพย์: %{customdata[4]}<br>"
                            "🏢 บริษัท: %{customdata[0]}<br>"
                            "💰 ราคา: %{customdata[1]}<br>"
                            "🏠 ประเภท: %{customdata[2]}<br>"
                            "📏 ระยะทาง: %{customdata[3]}<br>"
                            "🌐 พิกัด: %{lat:.6f}, %{lon:.6f}"
                            "<extra></extra>"
                        ),
                        marker=dict(size=10, opacity=0.8)
                    )
                    # Override reference point to show simpler tooltip
                    fig_compare.update_traces(
                        selector=dict(name="จุดอ้างอิง"),
                        hovertemplate=(
                            "📍 จุดอ้างอิงของคุณ<br>"
                            "━━━━━━━━━━━━━━━━━━━━<br>"
                            "💰 ราคา: %{customdata[1]}<br>"
                            "🌐 พิกัด: %{lat:.6f}, %{lon:.6f}"
                            "<extra></extra>"
                        )
                    )
                    fig_compare.update_traces(
                        selector=dict(name="จุดอ้างอิง"),
                        marker=dict(size=24, opacity=1.0)
                    )
                    fig_compare.update_layout(
                        map_style=mapbox_style,
                        margin={"r": 0, "t": 0, "l": 0, "b": 0},
                        paper_bgcolor="rgba(0,0,0,0)",
                        hovermode='closest',
                        hoverlabel=dict(
                            bgcolor="rgba(15, 23, 42, 0.9)",
                            font_size=13,
                            font_color="white",
                            font_family="Sarabun, Outfit, sans-serif",
                            bordercolor="rgba(255, 255, 255, 0.1)"
                        )
                    )

                    # Interactive Plotly Chart with Point Click Event Selection
                    map_event = st.plotly_chart(
                        style_plotly_fig(fig_compare), 
                        width="stretch", 
                        theme=None, 
                        config={"scrollZoom": True},
                        on_select="rerun",
                        selection_mode="points",
                        key="tab1_radius_map_click"
                    )

                    # Extract exact clicked asset codes via customdata
                    selected_pts = map_event.get("selection", {}).get("points", []) if map_event else []
                    clicked_asset_codes = []
                    for pt in selected_pts:
                        c_data = pt.get("customdata", [])
                        if c_data and len(c_data) > 4:
                            code_val = str(c_data[4])
                            if code_val and code_val != "จุดอ้างอิง":
                                clicked_asset_codes.append(code_val)

                    # Filter copy helper display based on clicked asset codes
                    if clicked_asset_codes:
                        filtered_nearby_df = map_nearby_df[map_nearby_df['รหัสทรัพย์'].astype(str).isin(clicked_asset_codes)].copy()
                        if filtered_nearby_df.empty:
                            filtered_nearby_df = nearby_df.copy()
                            has_clicked_match = False
                        else:
                            has_clicked_match = True
                    else:
                        filtered_nearby_df = nearby_df.copy()
                        has_clicked_match = False

                    # Table ALWAYS displays ALL found properties in the area
                    st.markdown(f"##### 📋 รายการทรัพย์สิน NPA ที่พบในรัศมีค้นหาทั้งหมด {len(nearby_df):,} รายการ (พร้อมราคาต่อตารางวา / ตารางเมตร)")

                    nearby_show = nearby_df.sort_values("ระยะทาง (กม.)").copy()
                    nearby_show['ราคาขาย (บาท)'] = pd.to_numeric(nearby_show['ราคา'], errors='coerce')
                    nearby_show['ละติจูด'] = pd.to_numeric(nearby_show['ละติจูด'], errors='coerce')
                    nearby_show['ลองจิจูด'] = pd.to_numeric(nearby_show['ลองจิจูด'], errors='coerce')
                    if 'พื้นที่ใช้สอย (ตร.ม.)' in nearby_show.columns:
                        nearby_show['พื้นที่ใช้สอย (ตร.ม.)'] = pd.to_numeric(nearby_show['พื้นที่ใช้สอย (ตร.ม.)'], errors='coerce')
                    else:
                        nearby_show['พื้นที่ใช้สอย (ตร.ม.)'] = np.nan

                    cols_nearby = [
                        "บริษัท", "รหัสทรัพย์", "ประเภททรัพย์", "ราคาขาย (บาท)", 
                        "ขนาดพื้นที่", "พื้นที่ใช้สอย (ตร.ม.)", "ราคาต่อหน่วย (แสดงผล)",
                        "จังหวัด", "อำเภอ", "ตำบล", "ละติจูด", "ลองจิจูด", "ระยะทาง (กม.)", "ชื่อประกาศ", "ลิงก์"
                    ]
                    nearby_show = nearby_show[[c for c in cols_nearby if c in nearby_show.columns]]

                    st.dataframe(
                        nearby_show,
                        width="stretch",
                        column_config={
                            "ราคาขาย (บาท)": st.column_config.NumberColumn("ราคาขาย (บาท)", format="%,d"),
                            "พื้นที่ใช้สอย (ตร.ม.)": st.column_config.NumberColumn("พื้นที่ใช้สอย (ตร.ม.)", format="%.1f ตร.ม."),
                            "ละติจูด": st.column_config.NumberColumn("ละติจูด (Lat)", format="%.6f"),
                            "ลองจิจูด": st.column_config.NumberColumn("ลองจิจูด (Lng)", format="%.6f"),
                            "ระยะทาง (กม.)": st.column_config.NumberColumn("ระยะทาง (กม.)", format="%.2f กม."),
                            "ราคาต่อหน่วย (แสดงผล)": st.column_config.TextColumn("ราคาต่อหน่วย (บาท/วา หรือ บาท/ตร.ม.)")
                        }
                    )

                    render_import_export_section(nearby_show, filename_prefix=f"npa_location_comparison_{search_radius}km", key_suffix="tab4_radius")

                    # --- COPYABLE ASSET CODES HELPER (Displays clicked item in table format with code copy box) ---
                    expander_title = f"📋 ดูและคัดลอกรหัสทรัพย์สิน NPA ที่คลิกเลือกบนแผนที่ ({len(filtered_nearby_df):,} รายการ)" if has_clicked_match else f"📋 ดูและคัดลอกรหัสทรัพย์สิน NPA ทั้งหมดในแผนที่ ({len(filtered_nearby_df):,} รายการ)"
                    with st.expander(expander_title, expanded=True if has_clicked_match else False):
                        if has_clicked_match:
                            st.info(f"🎯 **ทรัพย์สินที่คุณคลิกเลือกบนแผนที่ ({len(filtered_nearby_df):,} รายการ):**")
                            
                            # 1. Show Company Name + Copy Asset Code Box perfectly aligned horizontally
                            for idx, (_, r) in enumerate(filtered_nearby_df.iterrows()):
                                asset_cd = str(r.get('รหัสทรัพย์', '-'))
                                co_nm = str(r.get('บริษัท', ''))
                                
                                c_co, c_lbl, c_code, _ = st.columns([1.3, 1.2, 2.2, 2.3], vertical_alignment="center")
                                with c_co:
                                    st.markdown(f"🏢 **บริษัท:** `{co_nm}`")
                                preset_lbl = "📌 **รหัสทรัพย์:**"
                                with c_lbl:
                                    st.markdown(preset_lbl)
                                with c_code:
                                    st.code(asset_cd, language="text")

                            # 2. Show 1-row Dataframe Table identical to main table format above
                            st.markdown("##### 📋 รายละเอียดทรัพย์สินที่เลือก (แสดงรูปแบบตาราง):")
                            sel_show = filtered_nearby_df.sort_values("ระยะทาง (กม.)").copy() if 'ระยะทาง (กม.)' in filtered_nearby_df.columns else filtered_nearby_df.copy()
                            sel_show['ราคาขาย (บาท)'] = pd.to_numeric(sel_show['ราคา'], errors='coerce')
                            sel_show['ละติจูด'] = pd.to_numeric(sel_show['ละติจูด'], errors='coerce')
                            sel_show['ลองจิจูด'] = pd.to_numeric(sel_show['ลองจิจูด'], errors='coerce')
                            if 'พื้นที่ใช้สอย (ตร.ม.)' in sel_show.columns:
                                sel_show['พื้นที่ใช้สอย (ตร.ม.)'] = pd.to_numeric(sel_show['พื้นที่ใช้สอย (ตร.ม.)'], errors='coerce')
                            else:
                                sel_show['พื้นที่ใช้สอย (ตร.ม.)'] = np.nan

                            cols_sel = [
                                "บริษัท", "รหัสทรัพย์", "ประเภททรัพย์", "ราคาขาย (บาท)", 
                                "ขนาดพื้นที่", "พื้นที่ใช้สอย (ตร.ม.)", "ราคาต่อหน่วย (แสดงผล)",
                                "จังหวัด", "อำเภอ", "ตำบล", "ละติจูด", "ลองจิจูด", "ระยะทาง (กม.)", "ชื่อประกาศ", "ลิงก์"
                            ]
                            sel_show = sel_show[[c for c in cols_sel if c in sel_show.columns]]

                            st.dataframe(
                                sel_show,
                                width="stretch",
                                height=110,
                                column_config={
                                    "ราคาขาย (บาท)": st.column_config.NumberColumn("ราคาขาย (บาท)", format="%,d"),
                                    "พื้นที่ใช้สอย (ตร.ม.)": st.column_config.NumberColumn("พื้นที่ใช้สอย (ตร.ม.)", format="%.1f ตร.ม."),
                                    "ละติจูด": st.column_config.NumberColumn("ละติจูด", format="%.6f"),
                                    "ลองจิจูด": st.column_config.NumberColumn("ลองจิจูด", format="%.6f"),
                                    "ระยะทาง (กม.)": st.column_config.NumberColumn("ระยะทาง (กม.)", format="%.2f กม."),
                                    "ราคาต่อหน่วย (แสดงผล)": st.column_config.TextColumn("ราคาต่อหน่วย (บาท/วา หรือ บาท/ตร.ม.)")
                                }
                            )

                        else:
                            st.markdown("กดปุ่มมุมขวาบนของกล่องโค้ด เพื่อคัดลอกรหัสทรัพย์สินไปใช้งานได้ทันที (หรือคลิกเลือกหมุดบนแผนที่เพื่อดูเฉพาะทรัพย์สินนั้น):")
                            code_lines = [str(r.get('รหัสทรัพย์', '')) for _, r in filtered_nearby_df.iterrows() if pd.notna(r.get('รหัสทรัพย์'))]
                            joined_codes = "\n".join(code_lines)
                            st.code(joined_codes, language="text")

                            st.markdown("##### 📌 รหัสทรัพย์สินแยกตามรายการ (กดปุ่มคัดลอกเฉพาะรหัสทรัพย์ได้ง่าย):")
                            copy_cols = st.columns(3)
                            for i, (_, r) in enumerate(filtered_nearby_df.iterrows()):
                                col_idx = i % 3
                                asset_cd = str(r.get('รหัสทรัพย์', '-'))
                                with copy_cols[col_idx]:
                                    st.code(asset_cd, language="text")
        else:
            st.info("💡 **คำแนะนำ:** กรุณากำหนดพิกัดอ้างอิงและเงื่อนไขค้นหาด้านบนให้เรียบร้อย แล้วกดปุ่ม **'🚀 เริ่มเปรียบเทียบทำเล'** ด้านบนเพื่อเริ่มต้นวิเคราะห์ข้อมูลเปรียบเทียบ")

    with comp_sub_tab2:
        st.markdown("### ⚔️ เปรียบเทียบแบบ 1 ต่อ 1 (1-on-1 Asset Comparison)")
        st.write("เลือกทรัพย์สิน 2 รายการที่คุณสนใจเพื่อเปรียบเทียบรายละเอียดและราคาขายแบบเคียงข้างกัน (สามารถเลือกผ่านแผนที่ทำเล หรือเลือกลิสต์รายชื่อได้)")
        
        if df_raw is None or df_raw.empty:
            st.warning("⚠️ ไม่มีข้อมูลทรัพย์สินให้ทำการเปรียบเทียบ")
            asset_a = None
            asset_b = None
        else:
            # Mode selection
            comp_mode = st.radio(
                "🎯 เลือกรูปแบบการค้นหาทรัพย์สินเปรียบเทียบ:",
                options=["🗺️ เลือกผ่านแผนที่ / รัศมีทำเล (Map & Radius Search)", "📋 เลือกจากรายการดร็อปดาวน์ (Dropdown Lists)"],
                horizontal=True,
                key="oneone_comp_mode"
            )
            st.markdown("<br/>", unsafe_allow_html=True)

            asset_a = st.session_state.get("oneone_asset_a_override", None)
            asset_b = st.session_state.get("oneone_asset_b_override", None)

            if comp_mode.startswith("🗺️"):
                # --- MODE 1: MAP & RADIUS SEARCH TABLE WITH CLICK SELECTION ---
                st.markdown("##### 📍 ขั้นตอนที่ 1: กำหนดรัศมีทำเล และคลิกเลือกหมุดบนแผนที่")
                
                m_col_left, m_col_right = st.columns([1, 2])
                with m_col_left:
                    map_prov = st.selectbox(
                        "จังหวัด",
                        options=["ทั้งหมด"] + sorted([str(p) for p in df_raw['จังหวัด'].dropna().unique()]),
                        key="oneone_map_prov"
                    )
                    df_map_subset = df_raw if map_prov == "ทั้งหมด" else df_raw[df_raw['จังหวัด'] == map_prov]

                    dist_opts = ["ทั้งหมด"] + sorted([str(d) for d in df_map_subset['อำเภอ'].dropna().unique()])
                    map_dist = st.selectbox("อำเภอ/เขต", options=dist_opts, key="oneone_map_dist")
                    if map_dist != "ทั้งหมด":
                        df_map_subset = df_map_subset[df_map_subset['อำเภอ'] == map_dist]

                    type_opts = ["ทั้งหมด"] + sorted([str(t) for t in df_map_subset['ประเภททรัพย์'].dropna().unique()])
                    map_type = st.selectbox("ประเภททรัพย์", options=type_opts, key="oneone_map_type")
                    if map_type != "ทั้งหมด":
                        df_map_subset = df_map_subset[df_map_subset['ประเภททรัพย์'] == map_type]

                    # Radius Slider
                    map_radius = st.slider(
                        "📏 รัศมีการค้นหาจากจุดอ้างอิงทำเล (กิโลเมตร)", 
                        min_value=0.5, 
                        max_value=30.0, 
                        value=5.0, 
                        step=0.5, 
                        key="oneone_map_radius"
                    )

                    # Calculate distance if reference coordinates exist
                    if 'inp_lat' in locals() and 'inp_lng' in locals() and pd.notna(inp_lat) and pd.notna(inp_lng):
                        df_map_subset = find_nearby_properties(inp_lat, inp_lng, df_map_subset, map_radius, match_type=None)
                        st.caption(f"📍 คำนวณระยะทางจากพิกัดอ้างอิงในรัศมี **{map_radius:.1f} กม.**")

                    search_kw = st.text_input("🔍 พิมพ์ชื่อโครงการ/ทำเลค้นหาเพิ่มเติม", value="", placeholder="เช่น บางบัวทอง, ลาดพร้าว...", key="oneone_map_kw")
                    if search_kw.strip():
                        q = search_kw.strip().lower()
                        df_map_subset = df_map_subset[
                            df_map_subset['ชื่อประกาศ'].astype(str).str.lower().str.contains(q, na=False) |
                            df_map_subset['รหัสทรัพย์'].astype(str).str.lower().str.contains(q, na=False) |
                            df_map_subset['ชื่อโครงการ'].astype(str).str.lower().str.contains(q, na=False)
                        ]

                with m_col_right:
                    # Show map of matching properties with click event enabled
                    valid_geo_df = df_map_subset[
                        df_map_subset['ละติจูด'].notna() & 
                        df_map_subset['ลองจิจูด'].notna() & 
                        (df_map_subset['ละติจูด'] != 0)
                    ].copy().reset_index(drop=True)

                    if not valid_geo_df.empty:
                        unique_sub2_geo = len(valid_geo_df.drop_duplicates(subset=['ละติจูด', 'ลองจิจูด']))
                        dup_sub2_geo = len(valid_geo_df) - unique_sub2_geo
                        if dup_sub2_geo > 0:
                            st.caption(f"📍 มีพิกัด **{len(valid_geo_df):,}** รายการ (🏢 ซ้ำกันที่โครงการ/คอนโดเดียวกัน **{dup_sub2_geo:,}** รายการ กระจาย **{unique_sub2_geo:,}** จุดหมุดบนแผนที่)")
                        valid_geo_df['formatted_price'] = valid_geo_df['ราคา'].apply(lambda p: f"฿{p:,.0f}" if pd.notna(p) else "ไม่ระบุ")
                        fig_picker = px.scatter_map(
                            valid_geo_df.head(500),
                            lat="ละติจูด",
                            lon="ลองจิจูด",
                            color="บริษัท",
                            hover_name="ชื่อประกาศ",
                            hover_data={"formatted_price": True, "ประเภททรัพย์": True, "บริษัท": True},
                            custom_data=["รหัสทรัพย์"],
                            zoom=10,
                            height=380,
                            color_discrete_map={
                                "Baania": "#f59e0b", "BAM": "#3b82f6", "SAM": "#10b981",
                                "DDproperty": "#a855f7",
                                "Taladnudbaan": "#06b6d4", "ZmyHome": "#ec4899"
                            },
                            template=plotly_template
                        )
                        fig_picker.update_layout(
                            map_style=mapbox_style,
                            margin={"r":0,"t":0,"l":0,"b":0},
                            paper_bgcolor="rgba(0,0,0,0)"
                        )
                        map_event = st.plotly_chart(
                            style_plotly_fig(fig_picker), 
                            use_container_width=True, 
                            theme=None, 
                            config={"scrollZoom": True},
                            on_select="rerun",
                            selection_mode="points",
                            key="oneone_map_plotly_click"
                        )
                    else:
                        map_event = None
                        st.info("🗺️ ไม่พบจุดพิกัดละติจูดบนแผนที่ในเงื่อนไขนี้ (แต่สามารถเลือกลิสต์ในตารางด้านล่างได้)")

                # Handle Click Event on Map Marker
                selected_points = map_event.get("selection", {}).get("points", []) if map_event else []
                
                if selected_points and not valid_geo_df.empty:
                    pt_custom = selected_points[0].get("customdata", [])
                    clicked_asset_code = str(pt_custom[0]) if pt_custom and len(pt_custom) > 0 else None
                    
                    clicked_row = None
                    if clicked_asset_code:
                        match_r = valid_geo_df[valid_geo_df['รหัสทรัพย์'].astype(str) == clicked_asset_code]
                        if not match_r.empty:
                            clicked_row = match_r.iloc[0]
                            
                    if clicked_row is None:
                        point_idx = selected_points[0].get("point_index", 0)
                        clicked_row = valid_geo_df.iloc[point_idx] if point_idx < len(valid_geo_df) else None
                    if clicked_row is not None:
                        st.markdown("##### 🎯 รายการที่คุณคลิกเลือกบนแผนที่ (1 รายการ):")
                        single_df = pd.DataFrame([clicked_row])
                        single_df['ราคาเสนอขาย'] = single_df['ราคา'].apply(lambda p: f"฿{p:,.0f}" if pd.notna(p) else "-")
                        t_cols = ['บริษัท', 'รหัสทรัพย์', 'ชื่อประกาศ', 'ประเภททรัพย์', 'ราคาเสนอขาย', 'ตำบล', 'อำเภอ', 'จังหวัด']
                        if 'ระยะทาง (กม.)' in single_df.columns:
                            t_cols.insert(5, 'ระยะทาง (กม.)')
                            single_df['ระยะทาง (กม.)'] = single_df['ระยะทาง (กม.)'].map('{:.2f}'.format)
                            
                        st.dataframe(single_df[t_cols], use_container_width=True, height=95)
                        
                        btn_c1, btn_c2 = st.columns(2)
                        with btn_c1:
                            if st.button("🔵 ตั้งเป็น Asset A (จากหมุดที่คลิก)", key=f"btn_clk_a_{clicked_row['รหัสทรัพย์']}"):
                                st.session_state["oneone_asset_a_override"] = clicked_row
                                st.rerun()
                        with btn_c2:
                            if st.button("💖 ตั้งเป็น Asset B (จากหมุดที่คลิก)", key=f"btn_clk_b_{clicked_row['รหัสทรัพย์']}"):
                                st.session_state["oneone_asset_b_override"] = clicked_row
                                st.rerun()
                        st.markdown("<hr/>", unsafe_allow_html=True)

                st.markdown("##### 📋 ตารางรายการทรัพย์สิน NPA ทั้งหมดในทำเลที่เลือก (พร้อมปุ่มเลือกเปรียบเทียบ)")
                st.caption(f"พบรายการทรัพย์สิน NPA รวม **{len(df_map_subset):,}** รายการในรัศมีทำเลที่เลือก:")

                if not df_map_subset.empty:
                    df_display_table = df_map_subset.copy()
                    df_display_table['ราคาเสนอขาย'] = df_display_table['ราคา'].apply(lambda p: f"฿{p:,.0f}" if pd.notna(p) else "-")
                    
                    # Columns to present in summary table
                    table_cols = ['บริษัท', 'รหัสทรัพย์', 'ชื่อประกาศ', 'ประเภททรัพย์', 'ราคาเสนอขาย', 'ตำบล', 'อำเภอ', 'จังหวัด']
                    if 'ระยะทาง (กม.)' in df_display_table.columns:
                        table_cols.insert(5, 'ระยะทาง (กม.)')
                        df_display_table['ระยะทาง (กม.)'] = df_display_table['ระยะทาง (กม.)'].map('{:.2f}'.format)
                    
                    st.dataframe(
                        df_display_table[table_cols].head(100),
                        use_container_width=True,
                        height=200
                    )

                    # Quick Selector Dropdowns right under Table
                    df_display_table['label'] = df_display_table.apply(lambda r: make_clean_dropdown_label(r, show_company=True), axis=1)
                    valid_labels = ["-- เลือกรายการ --"] + df_display_table['label'].tolist()

                    col_sel_a, col_sel_b = st.columns(2)
                    with col_sel_a:
                        sel_a_choice = st.selectbox("🔵 เลือกตั้งเป็นทรัพย์สินรายการที่ 1 (Asset A) จากตาราง", options=valid_labels, key="map_table_sel_a")
                        if sel_a_choice != "-- เลือกรายการ --":
                            match_row = df_display_table[df_display_table['label'] == sel_a_choice]
                            if not match_row.empty:
                                st.session_state["oneone_asset_a_override"] = match_row.iloc[0]

                    with col_sel_b:
                        sel_b_choice = st.selectbox("💖 เลือกตั้งเป็นทรัพย์สินรายการที่ 2 (Asset B) จากตาราง", options=valid_labels, key="map_table_sel_b")
                        if sel_b_choice != "-- เลือกรายการ --":
                            match_row = df_display_table[df_display_table['label'] == sel_b_choice]
                            if not match_row.empty:
                                st.session_state["oneone_asset_b_override"] = match_row.iloc[0]
                else:
                    st.warning("⚠️ ไม่พบทรัพย์สินตามเงื่อนไขรัศมีและทำเลที่กำหนด")

            else:
                # --- MODE 2: DROPDOWN SELECTORS ---
                col_comp_1, col_comp_2 = st.columns(2)
                
                # --- ASSET A SELECTOR ---
                with col_comp_1:
                    st.markdown("<h5 style='color: #3b82f6;'><i class='fa fa-home'></i> เลือกทรัพย์สินรายการที่ 1 (Asset A)</h5>", unsafe_allow_html=True)
                    comp_a_co = st.selectbox("เลือกบริษัท (รายการที่ 1)", options=sorted([str(c) for c in df_raw['บริษัท'].dropna().unique()]), index=0, key="oneone_co_a")
                    df_a_filtered = df_raw[df_raw['บริษัท'] == comp_a_co].copy()
                    types_a = sorted([str(t) for t in df_a_filtered['ประเภททรัพย์'].dropna().unique()]) if not df_a_filtered.empty else []
                    valid_types_a = ["ทั้งหมด"] + types_a
                    sanitize_session_state("oneone_type_a", valid_types_a, "ทั้งหมด")
                    comp_a_type = st.selectbox("เลือกประเภททรัพย์ (รายการที่ 1)", options=valid_types_a, index=0, key="oneone_type_a")
                    
                    df_a_subset = df_a_filtered.copy()
                    if comp_a_type != "ทั้งหมด":
                        df_a_subset = df_a_subset[df_a_subset['ประเภททรัพย์'] == comp_a_type]
                        
                    search_a = st.text_input("🔍 ค้นหารายการที่ 1", value="", placeholder="พิมพ์ชื่อโครงการ, รหัสทรัพย์...", key="oneone_search_a")
                    if search_a:
                        q = search_a.strip().lower()
                        df_a_subset = df_a_subset[
                            df_a_subset['ชื่อประกาศ'].astype(str).str.lower().str.contains(q, na=False) |
                            df_a_subset['รหัสทรัพย์'].astype(str).str.lower().str.contains(q, na=False) |
                            df_a_subset['ชื่อโครงการ'].astype(str).str.lower().str.contains(q, na=False)
                        ]
                        
                    if not df_a_subset.empty:
                        display_a = df_a_subset.head(100).copy()
                        display_a['label'] = display_a.apply(make_clean_dropdown_label, axis=1)
                        display_a = display_a.drop_duplicates(subset=['label'])
                        valid_labels_a = display_a['label'].tolist()
                        sanitize_session_state("oneone_sel_a", valid_labels_a)
                        sel_label_a = st.selectbox("ค้นหาและเลือกทรัพย์สินรายการที่ 1", options=valid_labels_a, index=0, key="oneone_sel_a")
                        match_a = display_a[display_a['label'] == sel_label_a] if sel_label_a else None
                        if match_a is not None and not match_a.empty:
                            asset_a = match_a.iloc[0]
                            st.session_state["oneone_asset_a_override"] = asset_a

                # --- ASSET B SELECTOR ---
                with col_comp_2:
                    st.markdown("<h5 style='color: #ec4899;'><i class='fa fa-home'></i> เลือกทรัพย์สินรายการที่ 2 (Asset B)</h5>", unsafe_allow_html=True)
                    companies_list = sorted([str(c) for c in df_raw['บริษัท'].dropna().unique()])
                    default_idx_b = 1 if len(companies_list) > 1 else 0
                    comp_b_co = st.selectbox("เลือกบริษัท (รายการที่ 2)", options=companies_list, index=default_idx_b, key="oneone_co_b")
                    df_b_filtered = df_raw[df_raw['บริษัท'] == comp_b_co].copy()
                    types_b = sorted([str(t) for t in df_b_filtered['ประเภททรัพย์'].dropna().unique()]) if not df_b_filtered.empty else []
                    valid_types_b = ["ทั้งหมด"] + types_b
                    sanitize_session_state("oneone_type_b", valid_types_b, "ทั้งหมด")
                    comp_b_type = st.selectbox("เลือกประเภททรัพย์ (รายการที่ 2)", options=valid_types_b, index=0, key="oneone_type_b")
                    
                    df_b_subset = df_b_filtered.copy()
                    if comp_b_type != "ทั้งหมด":
                        df_b_subset = df_b_subset[df_b_subset['ประเภททรัพย์'] == comp_b_type]
                        
                    search_b = st.text_input("🔍 ค้นหารายการที่ 2", value="", placeholder="พิมพ์ชื่อโครงการ, รหัสทรัพย์...", key="oneone_search_b")
                    if search_b:
                        q = search_b.strip().lower()
                        df_b_subset = df_b_subset[
                            df_b_subset['ชื่อประกาศ'].astype(str).str.lower().str.contains(q, na=False) |
                            df_b_subset['รหัสทรัพย์'].astype(str).str.lower().str.contains(q, na=False) |
                            df_b_subset['ชื่อโครงการ'].astype(str).str.lower().str.contains(q, na=False)
                        ]
                        
                    if not df_b_subset.empty:
                        display_b = df_b_subset.head(100).copy()
                        display_b['label'] = display_b.apply(make_clean_dropdown_label, axis=1)
                        display_b = display_b.drop_duplicates(subset=['label'])
                        valid_labels_b = display_b['label'].tolist()
                        sanitize_session_state("oneone_sel_b", valid_labels_b)
                        sel_label_b = st.selectbox("ค้นหาและเลือกทรัพย์สินรายการที่ 2", options=valid_labels_b, index=0, key="oneone_sel_b")
                        match_b = display_b[display_b['label'] == sel_label_b] if sel_label_b else None
                        if match_b is not None and not match_b.empty:
                            asset_b = match_b.iloc[0]
                            st.session_state["oneone_asset_b_override"] = asset_b

            # --- SLOT BANNER DISPLAY & SWAP CONTROL ---
            st.markdown("<br/>", unsafe_allow_html=True)
            slot_col1, slot_col2 = st.columns(2)
            with slot_col1:
                if asset_a is not None:
                    p_a_str = f"฿{asset_a['ราคา']:,.0f}" if pd.notna(asset_a['ราคา']) else "-"
                    st.success(f"🔵 **Asset A ที่เลือก:** {asset_a['ชื่อประกาศ'][:30]} ({asset_a['บริษัท']}) - **{p_a_str}**")
                else:
                    st.warning("🔵 **Asset A:** ยังไม่ได้เลือกรายการ")

            with slot_col2:
                if asset_b is not None:
                    p_b_str = f"฿{asset_b['ราคา']:,.0f}" if pd.notna(asset_b['ราคา']) else "-"
                    st.success(f"💖 **Asset B ที่เลือก:** {asset_b['ชื่อประกาศ'][:30]} ({asset_b['บริษัท']}) - **{p_b_str}**")
                else:
                    st.warning("💖 **Asset B:** ยังไม่ได้เลือกรายการ")

            ctrl_c1, ctrl_c2, ctrl_c3 = st.columns([1, 1, 2])
            with ctrl_c1:
                if st.button("🔄 สลับตำแหน่ง (A ↔ B)"):
                    st.session_state["oneone_asset_a_override"], st.session_state["oneone_asset_b_override"] = asset_b, asset_a
                    st.session_state.pop("oneone_sel_a", None)
                    st.session_state.pop("oneone_sel_b", None)
                    st.rerun()
            with ctrl_c2:
                if st.button("🗑️ ล้างรายการที่เลือก"):
                    st.session_state["oneone_asset_a_override"] = None
                    st.session_state["oneone_asset_b_override"] = None
                    st.session_state.pop("oneone_sel_a", None)
                    st.session_state.pop("oneone_sel_b", None)
                    st.rerun()

# --- COMPARISON OUTPUT ---
            if asset_a is not None and asset_b is not None:
                st.markdown("<br/><h4>📊 ผลการเปรียบเทียบแบบเคียงข้าง (Side-by-Side Comparison)</h4>", unsafe_allow_html=True)
                
                price_a = float(asset_a['ราคา']) if pd.notna(asset_a['ราคา']) else 0.0
                price_b = float(asset_b['ราคา']) if pd.notna(asset_b['ราคา']) else 0.0
                area_a = float(asset_a['พื้นที่ใช้สอย (ตร.ม.)']) if pd.notna(asset_a['พื้นที่ใช้สอย (ตร.ม.)']) else 0.0
                area_b = float(asset_b['พื้นที่ใช้สอย (ตร.ม.)']) if pd.notna(asset_b['พื้นที่ใช้สอย (ตร.ม.)']) else 0.0
                
                # --- UNIT PRICE CALCULATIONS FOR ASSET A & B ---
                is_condo_a = any(kw in str(asset_a.get('ประเภททรัพย์', '')).lower() for kw in ['คอนโด', 'ห้องชุด'])
                sqwah_a = parse_land_sqwah(asset_a)
                if is_condo_a:
                    u_price_a = price_a / area_a if area_a > 0 else np.nan
                    u_lbl_a = "บาท/ตร.ม."
                    base_lbl_a = "พื้นที่ใช้สอย"
                else:
                    u_price_a = price_a / sqwah_a if (pd.notna(sqwah_a) and sqwah_a > 0) else np.nan
                    u_lbl_a = "บาท/วา"
                    base_lbl_a = "พื้นที่ดิน"

                is_condo_b = any(kw in str(asset_b.get('ประเภททรัพย์', '')).lower() for kw in ['คอนโด', 'ห้องชุด'])
                sqwah_b = parse_land_sqwah(asset_b)
                if is_condo_b:
                    u_price_b = price_b / area_b if area_b > 0 else np.nan
                    u_lbl_b = "บาท/ตร.ม."
                    base_lbl_b = "พื้นที่ใช้สอย"
                else:
                    u_price_b = price_b / sqwah_b if (pd.notna(sqwah_b) and sqwah_b > 0) else np.nan
                    u_lbl_b = "บาท/วา"
                    base_lbl_b = "พื้นที่ดิน"

                sqm_a = float(u_price_a) if (pd.notna(u_price_a) and u_price_a > 0) else 0.0
                sqm_b = float(u_price_b) if (pd.notna(u_price_b) and u_price_b > 0) else 0.0

                # Local area median sqwah price calculation for Asset A & Asset B
                loc_u_med_a, loc_lbl_a = get_location_median_sqwah(df_raw, asset_a.get('จังหวัด'), asset_a.get('อำเภอ'), asset_a.get('ตำบล'))
                loc_u_med_b, loc_lbl_b = get_location_median_sqwah(df_raw, asset_b.get('จังหวัด'), asset_b.get('อำเภอ'), asset_b.get('ตำบล'))
                str_loc_med_a = f"฿{loc_u_med_a:,.0f} /วา ({loc_lbl_a})" if pd.notna(loc_u_med_a) and loc_u_med_a > 0 else "ไม่มีข้อมูล"
                str_loc_med_b = f"฿{loc_u_med_b:,.0f} /วา ({loc_lbl_b})" if pd.notna(loc_u_med_b) and loc_u_med_b > 0 else "ไม่มีข้อมูล"

                # Sq.Wah Unit Prices for Raw Land comparison
                u_sqwah_a = price_a / sqwah_a if (pd.notna(sqwah_a) and sqwah_a > 0) else np.nan
                u_sqwah_b = price_b / sqwah_b if (pd.notna(sqwah_b) and sqwah_b > 0) else np.nan

                # --- MARKET MEDIAN UNIT PRICES FROM DF_RAW ---
                # 1. Raw Land Median Unit Price (บาท/วา)
                raw_land_df_all = df_raw[
                    df_raw['ประเภททรัพย์'].astype(str).str.contains('ที่ดินเปล่า|ที่ดิน', regex=True, na=False) &
                    (df_raw['ราคา'] > 0)
                ].copy() if df_raw is not None else pd.DataFrame()

                if not raw_land_df_all.empty:
                    raw_land_df_all['sqwah'] = raw_land_df_all.apply(parse_land_sqwah, axis=1)
                    raw_land_df_all['u_price'] = np.where(
                        (raw_land_df_all['sqwah'].notna()) & (raw_land_df_all['sqwah'] > 0),
                        raw_land_df_all['ราคา'] / raw_land_df_all['sqwah'],
                        np.nan
                    )
                    rl_u_median = float(raw_land_df_all['u_price'].dropna().median()) if not raw_land_df_all['u_price'].dropna().empty else 0.0
                else:
                    rl_u_median = 0.0

                # 2. Median Unit Price for Property Type A
                type_a_df = df_raw[df_raw['ประเภททรัพย์'] == asset_a['ประเภททรัพย์']].copy() if df_raw is not None else pd.DataFrame()
                if not type_a_df.empty:
                    def calc_u(r):
                        p = r.get('ราคา')
                        if pd.isna(p) or float(p) <= 0: return np.nan
                        pt = str(r.get('ประเภททรัพย์', '')).lower()
                        if any(kw in pt for kw in ['คอนโด', 'ห้องชุด']):
                            s = r.get('พื้นที่ใช้สอย (ตร.ม.)')
                            return float(p)/float(s) if (pd.notna(s) and float(s)>0) else np.nan
                        else:
                            w = parse_land_sqwah(r)
                            return float(p)/float(w) if (pd.notna(w) and float(w)>0) else np.nan
                    type_a_u_median = float(type_a_df.apply(calc_u, axis=1).dropna().median()) if not type_a_df.empty else 0.0
                else:
                    type_a_u_median = 0.0

                # 3. Median Unit Price for Property Type B
                type_b_df = df_raw[df_raw['ประเภททรัพย์'] == asset_b['ประเภททรัพย์']].copy() if df_raw is not None else pd.DataFrame()
                if not type_b_df.empty:
                    type_b_u_median = float(type_b_df.apply(calc_u, axis=1).dropna().median()) if not type_b_df.empty else 0.0
                else:
                    type_b_u_median = 0.0

                lat_a = float(asset_a['ละติจูด']) if pd.notna(asset_a['ละติจูด']) else None
                lat_b = float(asset_b['ละติจูด']) if pd.notna(asset_b['ละติจูด']) else None
                lng_a = float(asset_a['ลองจิจูด']) if pd.notna(asset_a['ลองจิจูด']) else None
                lng_b = float(asset_b['ลองจิจูด']) if pd.notna(asset_b['ลองจิจูด']) else None
                
                dist_km = haversine_distance(lat_a, lng_a, lat_b, lng_b) if (lat_a and lng_a and lat_b and lng_b) else None
                
                # --- METRIC CARDS (4 COLUMNS) ---
                k_col1, k_col2, k_col3, k_col4 = st.columns(4)
                
                # Metric 1: Asset A Unit Price
                with k_col1:
                    if pd.notna(u_price_a) and u_price_a > 0:
                        val_str_a = f"฿{u_price_a:,.0f} /{u_lbl_a.replace('บาท/', '')}"
                        if type_a_u_median > 0:
                            diff_a = u_price_a - type_a_u_median
                            pct_a = (diff_a / type_a_u_median) * 100
                            sub_a = f"เทียบราคากลาง ({pct_a:+.1f}%)"
                        else:
                            sub_a = f"คำนวณจาก{base_lbl_a}"
                        st.metric(f"🏷️ ราคา/หน่วย (Asset A - {asset_a['บริษัท']})", val_str_a, sub_a)
                    else:
                        st.metric(f"🏷️ ราคา/หน่วย (Asset A)", "N/A", "ไม่มีข้อมูลขนาดพื้นที่")

                # Metric 2: Asset B Unit Price
                with k_col2:
                    if pd.notna(u_price_b) and u_price_b > 0:
                        val_str_b = f"฿{u_price_b:,.0f} /{u_lbl_b.replace('บาท/', '')}"
                        if type_b_u_median > 0:
                            diff_b = u_price_b - type_b_u_median
                            pct_b = (diff_b / type_b_u_median) * 100
                            sub_b = f"เทียบราคากลาง ({pct_b:+.1f}%)"
                        else:
                            sub_b = f"คำนวณจาก{base_lbl_b}"
                        st.metric(f"🏷️ ราคา/หน่วย (Asset B - {asset_b['บริษัท']})", val_str_b, sub_b)
                    else:
                        st.metric(f"🏷️ ราคา/หน่วย (Asset B)", "N/A", "ไม่มีข้อมูลขนาดพื้นที่")

                # Metric 3: Raw Land Median Comparison
                with k_col3:
                    if rl_u_median > 0:
                        st.metric("🌾 ราคากลางที่ดินเปล่า", f"฿{rl_u_median:,.0f} /วา", "ราคากลางในระบบ")
                    else:
                        st.metric("🌾 ราคากลางที่ดินเปล่า", "N/A", "ไม่มีข้อมูล")

                # Metric 4: Distance / Unit Price Deal Winner
                with k_col4:
                    if pd.notna(u_price_a) and pd.notna(u_price_b) and u_lbl_a == u_lbl_b:
                        if u_price_a < u_price_b:
                            diff_u = u_price_b - u_price_a
                            pct_u = (diff_u / u_price_b) * 100
                            st.metric("ดีลราคา/หน่วยประหยัดกว่า", f"Asset A ({asset_a['บริษัท']})", f"-฿{diff_u:,.0f} (-{pct_u:.1f}%)")
                        elif u_price_b < u_price_a:
                            diff_u = u_price_a - u_price_b
                            pct_u = (diff_u / u_price_a) * 100
                            st.metric("ดีลราคา/หน่วยประหยัดกว่า", f"Asset B ({asset_b['บริษัท']})", f"-฿{diff_u:,.0f} (-{pct_u:.1f}%)")
                        else:
                            st.metric("ดีลราคา/หน่วย", "ราคา/หน่วยเท่ากัน", "0%")
                    elif dist_km is not None:
                        st.metric("ระยะห่างระหว่างทรัพย์", f"{dist_km:.2f} กม.", "พิกัดแผนที่")
                    else:
                        st.metric("ระยะห่างระหว่างทรัพย์", "N/A", "ไม่มีพิกัด")
                
                st.markdown("<br/>", unsafe_allow_html=True)
                
                # HTML styling helper (adaptive text color via CSS variables)
                def get_val_styled(val, compare_val, is_price=False, is_area=False, reverse=False):
                    if pd.isna(val) or val == "" or val == 0:
                        return "<span style='color: var(--card-subtext);'>ไม่มีข้อมูล</span>"
                    if is_price:
                        formatted = f"฿{float(val):,.0f}"
                    elif is_area:
                        formatted = f"{float(val):,.1f} ตร.ม."
                    else:
                        formatted = str(val)
                    if compare_val is not None and pd.notna(compare_val) and compare_val != 0:
                        v_num = float(val)
                        c_num = float(compare_val)
                        if v_num < c_num:
                            color = "#10b981" if not reverse else "#ef4444"
                            return f"<span style='color:{color}; font-weight:700;'>{formatted}</span>"
                        elif v_num > c_num:
                            color = "#ef4444" if not reverse else "#10b981"
                            return f"<span style='color:{color}; font-weight:700;'>{formatted}</span>"
                    return f"<span style='color: var(--card-text);'>{formatted}</span>"
                
                # Format Unit Price Display strings
                str_u_a = f"฿{u_price_a:,.0f} /{u_lbl_a} ({base_lbl_a})" if pd.notna(u_price_a) else "-"
                str_u_b = f"฿{u_price_b:,.0f} /{u_lbl_b} ({base_lbl_b})" if pd.notna(u_price_b) else "-"

                str_med_type_a = f"฿{type_a_u_median:,.0f} /{u_lbl_a}" if type_a_u_median > 0 else "-"
                str_med_type_b = f"฿{type_b_u_median:,.0f} /{u_lbl_b}" if type_b_u_median > 0 else "-"

                str_rl_a = f"฿{u_sqwah_a:,.0f} /วา" if pd.notna(u_sqwah_a) else "-"
                str_rl_b = f"฿{u_sqwah_b:,.0f} /วา" if pd.notna(u_sqwah_b) else "-"
                str_rl_med = f"฿{rl_u_median:,.0f} /วา" if rl_u_median > 0 else "-"

                str_sqwah_a = f"{sqwah_a:,.1f} วา" if pd.notna(sqwah_a) and sqwah_a > 0 else (asset_a['พื้นที่ (ไร่-งาน-วา)'] if asset_a['พื้นที่ (ไร่-งาน-วา)'] else '-')
                str_sqwah_b = f"{sqwah_b:,.1f} วา" if pd.notna(sqwah_b) and sqwah_b > 0 else (asset_b['พื้นที่ (ไร่-งาน-วา)'] if asset_b['พื้นที่ (ไร่-งาน-วา)'] else '-')

                # Render the table (uses dynamic borders, backgrounds, and text colors)
                comp_table_html = f"""
                <div style="overflow-x: auto;">
                    <table style="width:100%; border-collapse: collapse; font-family: 'Sarabun', sans-serif; font-size: 0.9rem; margin-top: 15px; border: 1px solid var(--card-border); border-radius: 8px; color: var(--card-text);">
                        <thead>
                            <tr style="background-color: var(--sidebar-bg); border-bottom: 2px solid var(--card-border);">
                                <th style="padding: 12px; text-align: left; color: var(--card-subtext); width: 22%; border-right: 1px solid var(--card-border);">รายละเอียด</th>
                                <th style="padding: 12px; text-align: center; color: #3b82f6; width: 39%; font-weight: 700; border-right: 1px solid var(--card-border);">🏠 ทรัพย์สิน A ({asset_a['บริษัท']})</th>
                                <th style="padding: 12px; text-align: center; color: #ec4899; width: 39%; font-weight: 700;">🏠 ทรัพย์สิน B ({asset_b['บริษัท']})</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr style="border-bottom: 1px solid var(--card-border);">
                                <td style="padding: 10px; font-weight: 600; color: var(--card-subtext); border-right: 1px solid var(--card-border);">รหัสทรัพย์</td>
                                <td style="padding: 10px; text-align: center; color: var(--card-text); border-right: 1px solid var(--card-border);">{asset_a['รหัสทรัพย์']}</td>
                                <td style="padding: 10px; text-align: center; color: var(--card-text);">{asset_b['รหัสทรัพย์']}</td>
                            </tr>
                            <tr style="border-bottom: 1px solid var(--card-border);">
                                <td style="padding: 10px; font-weight: 600; color: var(--card-subtext); border-right: 1px solid var(--card-border);">ชื่อประกาศ / ชื่อโครงการ</td>
                                <td style="padding: 10px; text-align: center; color: var(--card-text); font-weight: 500; border-right: 1px solid var(--card-border);">{asset_a['ชื่อประกาศ']}</td>
                                <td style="padding: 10px; text-align: center; color: var(--card-text); font-weight: 500;">{asset_b['ชื่อประกาศ']}</td>
                            </tr>
                            <tr style="border-bottom: 1px solid var(--card-border);">
                                <td style="padding: 10px; font-weight: 600; color: var(--card-subtext); border-right: 1px solid var(--card-border);">ประเภททรัพย์</td>
                                <td style="padding: 10px; text-align: center; color: var(--card-text); border-right: 1px solid var(--card-border);">{asset_a['ประเภททรัพย์']}</td>
                                <td style="padding: 10px; text-align: center; color: var(--card-text);">{asset_b['ประเภททรัพย์']}</td>
                            </tr>
                            <tr style="border-bottom: 1px solid var(--card-border); background-color: var(--hover-bg);">
                                <td style="padding: 10px; font-weight: 600; color: var(--card-subtext); border-right: 1px solid var(--card-border);">ราคาเสนอขาย</td>
                                <td style="padding: 10px; text-align: center; font-size: 1.1rem; border-right: 1px solid var(--card-border);">{get_val_styled(price_a, price_b, is_price=True)}</td>
                                <td style="padding: 10px; text-align: center; font-size: 1.1rem;">{get_val_styled(price_b, price_a, is_price=True)}</td>
                            </tr>
                            <tr style="border-bottom: 1px solid var(--card-border);">
                                <td style="padding: 10px; font-weight: 600; color: var(--card-subtext); border-right: 1px solid var(--card-border);">ทำเลที่ตั้ง</td>
                                <td style="padding: 10px; text-align: center; color: var(--card-subtext); border-right: 1px solid var(--card-border);">{asset_a['ตำบล']} &raquo; {asset_a['อำเภอ']} &raquo; {asset_a['จังหวัด']}</td>
                                <td style="padding: 10px; text-align: center; color: var(--card-subtext);">{asset_b['ตำบล']} &raquo; {asset_b['อำเภอ']} &raquo; {asset_b['จังหวัด']}</td>
                            </tr>
                            <tr style="border-bottom: 1px solid var(--card-border);">
                                <td style="padding: 10px; font-weight: 600; color: var(--card-subtext); border-right: 1px solid var(--card-border);">พื้นที่ดิน (ตารางวา / ไร่-งาน-วา)</td>
                                <td style="padding: 10px; text-align: center; color: var(--card-text); border-right: 1px solid var(--card-border);">{str_sqwah_a}</td>
                                <td style="padding: 10px; text-align: center; color: var(--card-text);">{str_sqwah_b}</td>
                            </tr>
                            <tr style="border-bottom: 1px solid var(--card-border);">
                                <td style="padding: 10px; font-weight: 600; color: var(--card-subtext); border-right: 1px solid var(--card-border);">พื้นที่ใช้สอย (ตร.ม.)</td>
                                <td style="padding: 10px; text-align: center; border-right: 1px solid var(--card-border);">{get_val_styled(area_a, area_b, is_area=True, reverse=True)}</td>
                                <td style="padding: 10px; text-align: center;">{get_val_styled(area_b, area_a, is_area=True, reverse=True)}</td>
                            </tr>
                            <tr style="border-bottom: 1px solid var(--card-border); background-color: var(--hover-bg);">
                                <td style="padding: 10px; font-weight: 600; color: #3b82f6; border-right: 1px solid var(--card-border);">ราคาต่อหน่วย (คำนวณจากพื้นที่)</td>
                                <td style="padding: 10px; text-align: center; font-weight: 700; border-right: 1px solid var(--card-border);">{str_u_a}</td>
                                <td style="padding: 10px; text-align: center; font-weight: 700;">{str_u_b}</td>
                            </tr>
                            <tr style="border-bottom: 1px solid var(--card-border);">
                                <td style="padding: 10px; font-weight: 600; color: var(--card-subtext); border-right: 1px solid var(--card-border);">ราคากลางประเภททรัพย์สินในตลาด (Median)</td>
                                <td style="padding: 10px; text-align: center; color: var(--card-subtext); border-right: 1px solid var(--card-border);">{str_med_type_a}</td>
                                <td style="padding: 10px; text-align: center; color: var(--card-subtext);">{str_med_type_b}</td>
                            </tr>
                            <tr style="border-bottom: 1px solid var(--card-border);">
                                <td style="padding: 10px; font-weight: 600; color: #8b5cf6; border-right: 1px solid var(--card-border);">📍 ราคากลางต่อวาในทำเลย่านนั้น (Median ตามอำเภอ/ตำบล)</td>
                                <td style="padding: 10px; text-align: center; color: var(--card-text); border-right: 1px solid var(--card-border);">{str_loc_med_a}</td>
                                <td style="padding: 10px; text-align: center; color: var(--card-text);">{str_loc_med_b}</td>
                            </tr>
                            <tr style="border-bottom: 1px solid var(--card-border); background-color: var(--hover-bg);">
                                <td style="padding: 10px; font-weight: 600; color: #10b981; border-right: 1px solid var(--card-border);">🌾 เทียบราคาต่อวา กับราคากลางที่ดินเปล่า</td>
                                <td style="padding: 10px; text-align: center; color: var(--card-text); border-right: 1px solid var(--card-border);">{str_rl_a} (กลาง: {str_rl_med})</td>
                                <td style="padding: 10px; text-align: center; color: var(--card-text);">{str_rl_b} (กลาง: {str_rl_med})</td>
                            </tr>
                            <tr style="border-bottom: 1px solid var(--card-border);">
                                <td style="padding: 10px; font-weight: 600; color: var(--card-subtext); border-right: 1px solid var(--card-border);">รายละเอียดห้อง</td>
                                <td style="padding: 10px; text-align: center; color: var(--card-subtext); border-right: 1px solid var(--card-border);">🛏️ {asset_a.get('ห้องนอน', '-')} นอน | 🚿 {asset_a.get('ห้องน้ำ', '-')} น้ำ | 🚗 {asset_a.get('ที่จอดรถ', '-')} จอด</td>
                                <td style="padding: 10px; text-align: center; color: var(--card-subtext);">🛏️ {asset_b.get('ห้องนอน', '-')} นอน | 🚿 {asset_b.get('ห้องน้ำ', '-')} น้ำ | 🚗 {asset_b.get('ที่จอดรถ', '-')} จอด</td>
                            </tr>
                            <tr style="border-bottom: 1px solid var(--card-border);">
                                <td style="padding: 10px; font-weight: 600; color: var(--card-subtext); border-right: 1px solid var(--card-border);">ลิงก์รายละเอียด</td>
                                <td style="padding: 10px; text-align: center; border-right: 1px solid var(--card-border);">
                                    {f'<a href="{str(asset_a.get("ลิงก์", "") or "").strip()}" target="_blank" style="color: #3b82f6; text-decoration: none; font-weight: 600;"><i class="fa fa-external-link-alt"></i> เปิดหน้าประกาศ</a>' if str(asset_a.get('ลิงก์', '') or '').strip().startswith('http') else '<span style="color:#94a3b8;">ไม่มีลิงก์</span>'}
                                </td>
                                <td style="padding: 10px; text-align: center;">
                                    {f'<a href="{str(asset_b.get("ลิงก์", "") or "").strip()}" target="_blank" style="color: #ec4899; text-decoration: none; font-weight: 600;"><i class="fa fa-external-link-alt"></i> เปิดหน้าประกาศ</a>' if str(asset_b.get('ลิงก์', '') or '').strip().startswith('http') else '<span style="color:#94a3b8;">ไม่มีลิงก์</span>'}
                                </td>
                            </tr>
                        </tbody>
                    </table>
                </div>
                """
                st.markdown(comp_table_html, unsafe_allow_html=True)
                st.markdown("<br/>", unsafe_allow_html=True)
                

                
                # --- MAP DISPLAY FOR 1-ON-1 COMPARISON ---
                if (lat_a and lng_a) or (lat_b and lng_b):
                    st.markdown("<h4>🗺️ แผนที่เปรียบเทียบตำแหน่งทรัพย์สิน (Location Map)</h4>", unsafe_allow_html=True)
                    
                    map_points = []
                    if lat_a and lng_a:
                        map_points.append({
                            'lat': lat_a,
                            'lon': lng_a,
                            'ชื่อ': f"A: {asset_a['ชื่อประกาศ'][:30]}",
                            'บริษัท': f"A ({asset_a['บริษัท']})",
                            'ราคา': f"฿{price_a:,.0f}" if price_a > 0 else "ไม่ระบุราคา"
                        })
                    if lat_b and lng_b:
                        map_points.append({
                            'lat': lat_b,
                            'lon': lng_b,
                            'ชื่อ': f"B: {asset_b['ชื่อประกาศ'][:30]}",
                            'บริษัท': f"B ({asset_b['บริษัท']})",
                            'ราคา': f"฿{price_b:,.0f}" if price_b > 0 else "ไม่ระบุราคา"
                        })
                        
                    map_df = pd.DataFrame(map_points)
                    
                    fig_oneone_map = px.scatter_map(
                        map_df,
                        lat="lat",
                        lon="lon",
                        hover_name="ชื่อ",
                        hover_data={"บริษัท": True, "ราคา": True, "lat": False, "lon": False},
                        zoom=12 if (len(map_points) == 2 and dist_km and dist_km < 10) else 9,
                        height=400,
                        color="บริษัท",
                        color_discrete_map={
                            f"A ({asset_a['บริษัท']})": "#3b82f6",
                            f"B ({asset_b['บริษัท']})": "#ec4899"
                        },
                        template=plotly_template
                    )
                    
                    # Draw a line between A and B if both coordinates are available
                    if len(map_points) == 2:
                        import plotly.graph_objects as go
                        fig_oneone_map.add_trace(
                            go.Scattermap(
                                mode="lines+markers",
                                lon=[lng_a, lng_b],
                                lat=[lat_a, lat_b],
                                marker=dict(size=0), # Invisible markers on the line
                                line=dict(width=3, color="#6366f1"), # Indigo connection line
                                name="ระยะห่างทางกายภาพ",
                                hoverinfo="skip"
                            )
                        )
                        
                    fig_oneone_map.update_layout(
                        map_style=mapbox_style,
                        margin={"r": 0, "t": 0, "l": 0, "b": 0},
                        paper_bgcolor="rgba(0,0,0,0)",
                        hovermode='closest',
                        legend=dict(
                            yanchor="top",
                            y=0.99,
                            xanchor="left",
                            x=0.01,
                            bgcolor="rgba(255, 255, 255, 0.8)"
                        )
                    )
                    st.plotly_chart(style_plotly_fig(fig_oneone_map), use_container_width=True, theme=None, config={"scrollZoom": True})
                else:
                    st.warning("⚠️ ไม่มีพิกัดแผนที่ทั้งคู่ จึงไม่สามารถแสดงแผนที่เปรียบเทียบได้")
                
                # --- DYNAMIC COMPARATIVE INSIGHTS SECTION ---
                st.markdown("<br/><h3>📊 ผลวิเคราะห์เปรียบเทียบเชิงลึก (Comparative Insights)</h3>", unsafe_allow_html=True)
                
                # 1. Market Benchmarking against Province Medians
                st.markdown("##### 📍 1. การเปรียบเทียบราคาเสนอขายเทียบกับราคากลางในจังหวัด (Market Benchmarking)")
                
                prov_a = asset_a['จังหวัด']
                type_a = asset_a['ประเภททรัพย์']
                # Subset of same province & type
                df_market_a = df_raw[(df_raw['จังหวัด'] == prov_a) & (df_raw['ประเภททรัพย์'] == type_a) & (df_raw['ราคา'] > 0)] if df_raw is not None else pd.DataFrame()
                median_a = df_market_a['ราคา'].median() if not df_market_a.empty else 0.0
                
                prov_b = asset_b['จังหวัด']
                type_b = asset_b['ประเภททรัพย์']
                df_market_b = df_raw[(df_raw['จังหวัด'] == prov_b) & (df_raw['ประเภททรัพย์'] == type_b) & (df_raw['ราคา'] > 0)] if df_raw is not None else pd.DataFrame()
                median_b = df_market_b['ราคา'].median() if not df_market_b.empty else 0.0
                
                m_col1, m_col2 = st.columns(2)
                
                with m_col1:
                    st.markdown(f"**ทรัพย์สิน A ({asset_a['บริษัท']})**")
                    st.markdown(f"- ทำเล: **{prov_a}** | ประเภท: **{type_a}**")
                    if median_a > 0 and price_a > 0:
                        dev_a = ((price_a - median_a) / median_a) * 100
                        median_str = f"฿{median_a:,.0f}"
                        if dev_a < 0:
                            st.success(f"🟢 **ถูกกว่าราคากลางจังหวัด:** {abs(dev_a):.1f}% (ราคากลาง {median_str})")
                        elif dev_a > 0:
                            st.warning(f"🔴 **สูงกว่าราคากลางจังหวัด:** {dev_a:.1f}% (ราคากลาง {median_str})")
                        else:
                            st.info(f"🔵 **เท่ากับราคากลางจังหวัด** ({median_str})")
                    else:
                        st.write("- *ไม่มีข้อมูลเปรียบเทียบราคากลางจังหวัด*")
                        
                with m_col2:
                    st.markdown(f"**ทรัพย์สิน B ({asset_b['บริษัท']})**")
                    st.markdown(f"- ทำเล: **{prov_b}** | ประเภท: **{type_b}**")
                    if median_b > 0 and price_b > 0:
                        dev_b = ((price_b - median_b) / median_b) * 100
                        median_str = f"฿{median_b:,.0f}"
                        if dev_b < 0:
                            st.success(f"🟢 **ถูกกว่าราคากลางจังหวัด:** {abs(dev_b):.1f}% (ราคากลาง {median_str})")
                        elif dev_b > 0:
                            st.warning(f"🔴 **สูงกว่าราคากลางจังหวัด:** {dev_b:.1f}% (ราคากลาง {median_str})")
                        else:
                            st.info(f"🔵 **เท่ากับราคากลางจังหวัด** ({median_str})")
                    else:
                        st.write("- *ไม่มีข้อมูลเปรียบเทียบราคากลางจังหวัด*")
                
                # 2. Spec & Layout Comparison
                st.markdown("<br/>##### 📐 2. การเปรียบเทียบพื้นที่ใช้สอยและขนาดอาคาร (Functional Specification Difference)", unsafe_allow_html=True)
                
                spec_bullets = []
                
                # Area difference
                if area_a > 0 and area_b > 0:
                    if area_a > area_b:
                        diff = area_a - area_b
                        pct = (diff / area_b) * 100
                        spec_bullets.append(f"🟩 **พื้นที่ใช้สอย:** ทรัพย์สิน A กว้างขวางกว่า ทรัพย์สิน B อยู่ **{diff:.1f} ตร.ม. (+{pct:.1f}%)**")
                    elif area_b > area_a:
                        diff = area_b - area_a
                        pct = (diff / area_a) * 100
                        spec_bullets.append(f"🟪 **พื้นที่ใช้สอย:** ทรัพย์สิน B กว้างขวางกว่า ทรัพย์สิน A อยู่ **{diff:.1f} ตร.ม. (+{pct:.1f}%)**")
                    else:
                        spec_bullets.append("⬜ **พื้นที่ใช้สอย:** ทรัพย์สินทั้งสองมีขนาดพื้นที่ใช้สอยเท่ากัน")
                
                # Helper to parse values
                def parse_digits(val):
                    if pd.isna(val): return None
                    s = str(val).strip()
                    import re
                    match = re.search(r'\d+', s)
                    return int(match.group()) if match else None
                    
                beds_a = parse_digits(asset_a.get('ห้องนอน'))
                beds_b = parse_digits(asset_b.get('ห้องนอน'))
                baths_a = parse_digits(asset_a.get('ห้องน้ำ'))
                baths_b = parse_digits(asset_b.get('ห้องน้ำ'))
                park_a = parse_digits(asset_a.get('ที่จอดรถ'))
                park_b = parse_digits(asset_b.get('ที่จอดรถ'))
                
                # Bed diff
                if beds_a is not None and beds_b is not None:
                    if beds_a > beds_b:
                        spec_bullets.append(f"🛏️ **ห้องนอน:** ทรัพย์สิน A มีห้องนอนมากกว่า ทรัพย์สิน B อยู่ **+{beds_a - beds_b} ห้อง**")
                    elif beds_b > beds_a:
                        spec_bullets.append(f"🛏️ **ห้องนอน:** ทรัพย์สิน B มีห้องนอนมากกว่า ทรัพย์สิน A อยู่ **+{beds_b - beds_a} ห้อง**")
                        
                # Bath diff
                if baths_a is not None and baths_b is not None:
                    if baths_a > baths_b:
                        spec_bullets.append(f"🚿 **ห้องน้ำ:** ทรัพย์สิน A มีห้องน้ำมากกว่า ทรัพย์สิน B อยู่ **+{baths_a - baths_b} ห้อง**")
                    elif baths_b > baths_a:
                        spec_bullets.append(f"🚿 **ห้องน้ำ:** ทรัพย์สิน B มีห้องน้ำมากกว่า ทรัพย์สิน A อยู่ **+{baths_b - baths_a} ห้อง**")
                        
                # Parking diff
                if park_a is not None and park_b is not None:
                    if park_a > park_b:
                        spec_bullets.append(f"🚗 **ที่จอดรถ:** ทรัพย์สิน A มีพื้นที่จอดรถมากกว่า ทรัพย์สิน B อยู่ **+{park_a - park_b} คัน**")
                    elif park_b > park_a:
                        spec_bullets.append(f"🚗 **ที่จอดรถ:** ทรัพย์สิน B มีพื้นที่จอดรถมากกว่า ทรัพย์สิน A อยู่ **+{park_b - park_a} คัน**")
                        
                if spec_bullets:
                    for b in spec_bullets:
                        st.markdown(f"- {b}")
                else:
                    st.write("- *ไม่พบข้อมูลความแตกต่างเชิงรายละเอียดฟังก์ชัน (ห้องนอน/พื้นที่ใช้สอย)*")
                
                # 3. Overall Value Recommendation Summary
                st.markdown("<br/>##### 🏆 3. บทสรุปจุดเด่นของแต่ละรายการ (Value Proposition Summary)", unsafe_allow_html=True)
                
                box_col1, box_col2 = st.columns(2)
                
                # Points for A
                points_a = []
                if price_a > 0 and price_b > 0 and price_a < price_b:
                    points_a.append(f"💰 **ประหยัดงบลงทุนเริ่มต้นมากกว่า:** ราคาต่ำกว่าคู่แข่ง ฿{price_b - price_a:,.0f}")
                if sqm_a > 0 and sqm_b > 0 and sqm_a < sqm_b:
                    points_a.append(f"💎 **ราคาเฉลี่ยพื้นที่คุ้มค่ากว่า:** ราคาต่อตารางเมตรถูกกว่าคู่แข่ง {((sqm_b - sqm_a)/sqm_b)*100:.1f}%")
                if area_a > 0 and area_b > 0 and area_a > area_b:
                    points_a.append(f"📐 **เนื้อที่บ้านกว้างขวางกว่า:** พื้นที่ใช้สอยกว้างกว่าคู่แข่ง {area_a - area_b:.1f} ตร.ม.")
                if beds_a is not None and beds_b is not None and beds_a > beds_b:
                    points_a.append(f"🛏️ **สเปกห้องนอนมากกว่า:** รองรับสมาชิกครอบครัวขนาดใหญ่ได้ดีกว่า")
                if median_a > 0 and price_a > 0 and price_a < median_a:
                    points_a.append(f"📈 **ราคาตลาดยอดเยี่ยม:** เสนอขายถูกกว่าค่าเฉลี่ยกลางจังหวัด {prov_a}")
                    
                # Points for B
                points_b = []
                if price_b > 0 and price_a > 0 and price_b < price_a:
                    points_b.append(f"💰 **ประหยัดงบลงทุนเริ่มต้นมากกว่า:** ราคาต่ำกว่าคู่แข่ง ฿{price_a - price_b:,.0f}")
                if sqm_b > 0 and sqm_a > 0 and sqm_b < sqm_a:
                    points_b.append(f"💎 **ราคาเฉลี่ยพื้นที่คุ้มค่ากว่า:** ราคาต่อตารางเมตรถูกกว่าคู่แข่ง {((sqm_a - sqm_b)/sqm_a)*100:.1f}%")
                if area_b > 0 and area_a > 0 and area_b > area_a:
                    points_b.append(f"📐 **เนื้อที่บ้านกว้างขวางกว่า:** พื้นที่ใช้สอยกว้างกว่าคู่แข่ง {area_b - area_a:.1f} ตร.ม.")
                if beds_b is not None and beds_a is not None and beds_b > beds_a:
                    points_b.append(f"🛏️ **สเปกห้องนอนมากกว่า:** รองรับสมาชิกครอบครัวขนาดใหญ่ได้ดีกว่า")
                if median_b > 0 and price_b > 0 and price_b < median_b:
                    points_b.append(f"📈 **ราคาตลาดยอดเยี่ยม:** เสนอขายถูกกว่าค่าเฉลี่ยกลางจังหวัด {prov_b}")
                
                with box_col1:
                    st.markdown(f"<div style='border: 1px solid #3b82f6; border-radius: 8px; padding: 12px; height: 100%; background-color: rgba(59, 130, 246, 0.08); color: var(--card-text);'><strong>🌟 จุดเด่นของทรัพย์สิน A ({asset_a['บริษัท']})</strong></div>", unsafe_allow_html=True)
                    if points_a:
                        for p in points_a:
                            st.markdown(f"- {p}")
                    else:
                        st.markdown("- เหมาะสำหรับเปรียบเทียบในเชิงทำเลหรือมิติพิเศษอื่น ๆ")
                        
                with box_col2:
                    st.markdown(f"<div style='border: 1px solid #ec4899; border-radius: 8px; padding: 12px; height: 100%; background-color: rgba(236, 72, 153, 0.08); color: var(--card-text);'><strong>🌟 จุดเด่นของทรัพย์สิน B ({asset_b['บริษัท']})</strong></div>", unsafe_allow_html=True)
                    if points_b:
                        for p in points_b:
                            st.markdown(f"- {p}")
                    else:
                        st.markdown("- เหมาะสำหรับเปรียบเทียบในเชิงทำเลหรือมิติพิเศษอื่น ๆ")

# ----- TAB 5: BARGAIN HUNTER -----
with tab5:
    st.markdown("### 💎 ระบบค้นหาและคัดกรองทรัพย์ของดีราคาถูก (Bargain Hunter & Outliers)")
    st.write("คัดกรองและเปรียบเทียบหาทรัพย์สินที่มีราคาถูกกว่าราคาเฉลี่ยอย่างผิดปกติในทำเลที่คุณเลือก")
    
    st.markdown("---")
    
    if df_raw is None or df_raw.empty:
        st.warning("⚠️ ไม่มีข้อมูลทรัพย์สินให้ทำการวิเคราะห์")
    else:
        # Form for filtering location & property type for analysis
        col_b1, col_b2, col_b3 = st.columns(3)
        with col_b1:
            # Clean province list (excluding ไม่ระบุ)
            prov_list = sorted([str(p) for p in df_raw['จังหวัด'].dropna().unique() if str(p) not in ["ไม่ระบุ", "nan", "None", ""]])
            sel_b_prov = st.selectbox("เลือกจังหวัด (Province) (วิเคราะห์ส่วนลด)", options=prov_list if prov_list else ["ไม่มีข้อมูล"], index=0)
            
        with col_b2:
            # Filter districts by province
            dist_list = sorted([str(d) for d in df_raw[df_raw['จังหวัด'] == sel_b_prov]['อำเภอ'].dropna().unique() if str(d).strip() not in ["", "nan", "None"]])
            sel_b_dist = st.selectbox("เลือกอำเภอ/เขต (District) (วิเคราะห์ส่วนลด)", options=["ทั้งหมด"] + dist_list, index=0)
            
        with col_b3:
            # Filter property types by location
            loc_df = df_raw[df_raw['จังหวัด'] == sel_b_prov]
            if sel_b_dist != "ทั้งหมด":
                loc_df = loc_df[loc_df['อำเภอ'] == sel_b_dist]
            prop_types = sorted([str(t) for t in loc_df['ประเภททรัพย์'].dropna().unique() if str(t).strip() not in ["", "nan", "None"]])
            sel_b_type = st.selectbox("ประเภททรัพย์สิน (Property Type) (วิเคราะห์ส่วนลด)", options=prop_types if prop_types else ["ไม่มีข้อมูล"], index=0)
            
        # Perform analysis on this filtered dataset
        analysis_df = loc_df[loc_df['ประเภททรัพย์'] == sel_b_type].copy()
        
        # Decide unit to use dynamically based on data availability
        w_count = analysis_df['พื้นที่_ตารางวา'].notna().sum() if not analysis_df.empty else 0
        m_count = analysis_df['พื้นที่ใช้สอย (ตร.ม.)'].notna().sum() if not analysis_df.empty else 0
        
        if w_count >= m_count and w_count > 0:
            unit_col = 'ราคาต่อตารางวา'
            unit_label = 'ตารางวา'
            unit_short = 'ตร.ว.'
        else:
            unit_col = 'ราคาต่อตารางเมตร'
            unit_label = 'ตารางเมตร'
            unit_short = 'ตร.ม.'
        
        # Drop rows with no price, non-positive price, or no unit area
        analysis_df = analysis_df[
            analysis_df['ราคา'].notna() & 
            (analysis_df['ราคา'] > 0) & 
            analysis_df[unit_col].notna() &
            (analysis_df[unit_col] > 0)
        ]
        
        if analysis_df.empty or len(analysis_df) < 3:
            st.info("💡 มีข้อมูลไม่เพียงพอในการวิเคราะห์สถิติเชิงลึกในทำเลนี้ (ต้องการข้อมูลราคาและพื้นที่อย่างน้อย 3 รายการขึ้นไป)")
        else:
            # Outlier Filter Controls
            col_out1, col_out2 = st.columns([2, 2])
            with col_out1:
                enable_outlier_filter = st.checkbox(
                    "🛡️ กรองตัดราคาโดดผิดปกติ (Remove Extreme Outliers)", 
                    value=True, 
                    key="tab5_outlier_filter",
                    help="ตัดรายการที่ราคาต่อหน่วยสูงเกินจริงผิดปกติ (เช่น พิมพ์ราคาผิดหลักพันล้าน) เพื่อให้ Box Plot และสถิติแสดงผลได้อย่างสมดุลและถูกต้อง"
                )
            with col_out2:
                if enable_outlier_filter:
                    outlier_mode = st.selectbox(
                        "ระดับความเข้มงวดในการกรอง Outlier",
                        options=[
                            "ปานกลาง (Q3 + 3.0×IQR - ตัดเฉพาะราคาโดดผิดปกติรุนแรง)",
                            "เข้มงวด (Q3 + 1.5×IQR - ตัด Outlier ตามสถิติมาตรฐาน)",
                            "เพดานสูงสุด 500,000 บาท/หน่วย",
                            "เพดานสูงสุด 1,000,000 บาท/หน่วย"
                        ],
                        index=0,
                        key="tab5_outlier_mode"
                    )
                else:
                    outlier_mode = "ไม่กรอง"
                    
            plot_df = analysis_df.copy()
            removed_count = 0
            lower_limit_val = None
            upper_limit_val = None
            
            # Floor sanity threshold for realistic real estate price per unit
            floor_limit = 50.0 if unit_label == 'ตารางวา' else 500.0
            
            if enable_outlier_filter and len(analysis_df) >= 4:
                q1 = float(analysis_df[unit_col].quantile(0.25))
                q3 = float(analysis_df[unit_col].quantile(0.75))
                iqr = q3 - q1
                if "3.0×IQR" in outlier_mode:
                    lower_limit_val = max(floor_limit, q1 - (3.0 * iqr)) if iqr > 0 else floor_limit
                    upper_limit_val = q3 + (3.0 * iqr) if iqr > 0 else q3 * 3.0
                elif "1.5×IQR" in outlier_mode:
                    lower_limit_val = max(floor_limit * 2.0, q1 - (1.5 * iqr)) if iqr > 0 else floor_limit * 2.0
                    upper_limit_val = q3 + (1.5 * iqr) if iqr > 0 else q3 * 2.0
                elif "500,000" in outlier_mode:
                    lower_limit_val = floor_limit
                    upper_limit_val = 500000.0
                elif "1,000,000" in outlier_mode:
                    lower_limit_val = floor_limit
                    upper_limit_val = 1000000.0
                    
                if upper_limit_val is not None and lower_limit_val is not None:
                    plot_df = analysis_df[
                        (analysis_df[unit_col] >= lower_limit_val) & 
                        (analysis_df[unit_col] <= upper_limit_val)
                    ].copy()
                    removed_count = len(analysis_df) - len(plot_df)
                    if removed_count > 0:
                        st.caption(f"ℹ️ ระบบกรองตัดข้อมูลราคาโดดผิดปกติออก **{removed_count:,}** รายการ (คงเหลือวิเคราะห์ **{len(plot_df):,}** รายการ ในช่วงราคา **฿{lower_limit_val:,.0f} - ฿{upper_limit_val:,.0f}** / {unit_label})")

            # Calculate Statistics on clean data
            median_val = float(plot_df[unit_col].median()) if not plot_df.empty else 0.0
            mean_val = float(plot_df[unit_col].mean()) if not plot_df.empty else 0.0
            std_val = float(plot_df[unit_col].std()) if not plot_df.empty else 0.0
            min_val = float(plot_df[unit_col].min()) if not plot_df.empty else 0.0
            max_val = float(plot_df[unit_col].max()) if not plot_df.empty else 0.0
            
            # Display Statistics Cards
            s_col1, s_col2, s_col3, s_col4 = st.columns(4)
            s_col1.markdown(f"""
            <div class="metric-card">
                <div class="metric-title"><i class="fa fa-calculator"></i> ค่ากลางราคาต่อหน่วย</div>
                <div class="metric-value">฿{median_val:,.0f}</div>
                <div class="metric-sub">บาท / {unit_label} (Median)</div>
            </div>
            """, unsafe_allow_html=True)
            
            s_col2.markdown(f"""
            <div class="metric-card">
                <div class="metric-title"><i class="fa fa-arrow-down" style="color: #10b981;"></i> ราคาต่ำสุดต่อหน่วย</div>
                <div class="metric-value">฿{min_val:,.0f}</div>
                <div class="metric-sub">บาท / {unit_label} (Min)</div>
            </div>
            """, unsafe_allow_html=True)
            
            s_col3.markdown(f"""
            <div class="metric-card">
                <div class="metric-title"><i class="fa fa-arrow-up" style="color: #ef4444;"></i> ราคาสูงสุดต่อหน่วย</div>
                <div class="metric-value">฿{max_val:,.0f}</div>
                <div class="metric-sub">บาท / {unit_label} (Max)</div>
            </div>
            """, unsafe_allow_html=True)
            
            s_col4.markdown(f"""
            <div class="metric-card">
                <div class="metric-title"><i class="fa fa-list"></i> จำนวนทรัพย์วิเคราะห์</div>
                <div class="metric-value">{len(plot_df):,}</div>
                <div class="metric-sub">รายการในทำเลนี้</div>
            </div>
            """, unsafe_allow_html=True)
            
            st.markdown("<br/>", unsafe_allow_html=True)
            
            # Display Layout: Box Plot and AMC vs Portal average price
            col_graph1, col_graph2 = st.columns(2)
            
            with col_graph1:
                # Box Plot
                fig_box = px.box(
                    plot_df,
                    y=unit_col,
                    color='บริษัท',
                    points="outliers" if len(plot_df) > 150 else "all",
                    hover_data=['ชื่อประกาศ', 'รหัสทรัพย์', 'ราคา'] if 'ชื่อประกาศ' in plot_df.columns else ['รหัสทรัพย์', 'ราคา'],
                    title=f'แผนภูมิการกระจายตัวราคาต่อ{unit_label} (Box Plot)',
                    color_discrete_map={"Baania": "#f59e0b", "BAM": "#3b82f6", "SAM": "#10b981", "DDproperty": "#a855f7", "Taladnudbaan": "#06b6d4", "ZmyHome": "#ec4899"},
                    template=plotly_template
                )
                fig_box.update_layout(title_font=dict(size=14, family="Outfit"), yaxis_title=f"ราคา (บาท / {unit_label})")
                st.plotly_chart(style_plotly_fig(fig_box), use_container_width=True, theme=None)
                
            with col_graph2:
                # AMC vs Portal median price comparison
                amc_portal_group = plot_df.groupby('บริษัท')[unit_col].median().reset_index()
                fig_amc_vs_portal = px.bar(
                    amc_portal_group,
                    x='บริษัท',
                    y=unit_col,
                    color='บริษัท',
                    title=f'ราคากลาง (Median) ต่อ{unit_label} เปรียบเทียบ AMC vs พอร์ทัลทั่วไป',
                    color_discrete_map={"Baania": "#f59e0b", "BAM": "#3b82f6", "SAM": "#10b981", "DDproperty": "#a855f7", "Taladnudbaan": "#06b6d4", "ZmyHome": "#ec4899"},
                    template=plotly_template
                )
                fig_amc_vs_portal.update_layout(title_font=dict(size=14, family="Outfit"), yaxis_title=f"ราคากลาง (บาท / {unit_label})")
                st.plotly_chart(style_plotly_fig(fig_amc_vs_portal), use_container_width=True, theme=None)
                
            # Underpriced Assets Finder
            st.markdown("#### 💎 ทรัพย์สินที่ราคาต่อหน่วยคุ้มค่าที่สุด (ส่วนลดสูงสุดเทียบกับราคากลางทำเล)")
            st.write(f"แสดงรายการทรัพย์สินที่มีราคาต่อ{unit_label} ต่ำกว่าราคาเฉลี่ยกลาง (Median) ของพื้นที่ ซึ่งคิดเป็นดีลสุดคุ้มในการลงทุน")
            
            # Calculate discount from median
            plot_df['ส่วนต่างจากราคากลาง (%)'] = ((plot_df[unit_col] - median_val) / median_val) * 100.0
            
            # Sort by lowest unit price (or most negative deviation)
            bargain_df = plot_df.sort_values(by=unit_col)
            
            # Format and show columns
            name_col = 'ชื่อประกาศ' if 'ชื่อประกาศ' in bargain_df.columns else 'ชื่อโครงการ'
            link_col = 'ลิงก์' if 'ลิงก์' in bargain_df.columns else 'ลิงก์_สะอาด'
            
            display_cols = [c for c in [
                'บริษัท', 'รหัสทรัพย์', name_col, 'ราคา', unit_col, 'ส่วนต่างจากราคากลาง (%)', 
                'จังหวัด', 'อำเภอ', 'ตำบล', 'พื้นที่ (ไร่-งาน-วา)', 'พื้นที่ใช้สอย (ตร.ม.)', link_col
            ] if c in bargain_df.columns]
            
            bargain_display = bargain_df[display_cols].copy()
            
            if 'ราคา' in bargain_display.columns:
                bargain_display = bargain_display.rename(columns={'ราคา': 'ราคาเสนอขาย (บาท)'})
                bargain_display['ราคาเสนอขาย (บาท)'] = pd.to_numeric(bargain_display['ราคาเสนอขาย (บาท)'], errors='coerce')

            st.dataframe(
                bargain_display,
                use_container_width=True,
                column_config={
                    "ราคาเสนอขาย (บาท)": st.column_config.NumberColumn("ราคาเสนอขาย (บาท)", format="%,d"),
                    unit_col: st.column_config.NumberColumn(f"ราคา/หน่วย (บาท/{unit_short})", format="%,d"),
                    "ส่วนต่างจากราคากลาง (%)": st.column_config.NumberColumn("เทียบราคากลาง (%)", format="%+.1f%%"),
                    "พื้นที่ใช้สอย (ตร.ม.)": st.column_config.NumberColumn("พื้นที่ใช้สอย (ตร.ม.)", format="%.1f"),
                    link_col: st.column_config.LinkColumn("ลิงก์ประกาศ")
                }
            )

