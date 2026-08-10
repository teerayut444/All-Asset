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
from pathlib import Path
import base64

from dashboard_metrics import build_kpi_summary_text

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

def find_nearby_properties(input_lat, input_lon, df_all, radius_km, match_type=None, company=None):
    """Find properties within radius_km of the given coordinates (memory-optimized & vectorized)."""
    if df_all is None or df_all.empty:
        return pd.DataFrame()
    empty_res = df_all.head(0).copy()
    if input_lat is None or input_lon is None or pd.isna(input_lat) or pd.isna(input_lon):
        return empty_res
        
    # Build mask without full dataframe copy
    mask = df_all['ละติจูด'].notna() & df_all['ลองจิจูด'].notna() & df_all['ละติจูด'].between(5, 21) & df_all['ลองจิจูด'].between(97, 106)
    
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

# Cached function to load data – prefer parquet for speed, fallback to excel
@st.cache_data(ttl=3600)
def load_properties_data():
    excel_file = Path("all_assets.xlsx")
    parquet_file = Path("all_assets.parquet")
    
    # If both files don't exist, return None
    if not excel_file.exists() and not parquet_file.exists():
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
            if 'พื้นที่ (ไร่-งาน-วา)' in df.columns:
                df['พื้นที่_ตารางวา'] = df['พื้นที่ (ไร่-งาน-วา)'].apply(parse_area_to_sqwah)
            else:
                df['พื้นที่_ตารางวา'] = np.nan
        else:
            df['พื้นที่_ตารางวา'] = pd.to_numeric(df['พื้นที่_ตารางวา'], errors='coerce')

        if 'พื้นที่ใช้สอย (ตร.ม.)' not in df.columns:
            df['พื้นที่ใช้สอย (ตร.ม.)'] = np.nan
        else:
            df['พื้นที่ใช้สอย (ตร.ม.)'] = pd.to_numeric(df['พื้นที่ใช้สอย (ตร.ม.)'], errors='coerce')

        if 'ราคาต่อตารางวา' not in df.columns:
            df['ราคาต่อตารางวา'] = np.where((df['พื้นที่_ตารางวา'] > 0) & (df['ราคา'] > 0), df['ราคา'] / df['พื้นที่_ตารางวา'], np.nan)
        else:
            df['ราคาต่อตารางวา'] = pd.to_numeric(df['ราคาต่อตารางวา'], errors='coerce')

        if 'ราคาต่อตารางเมตร' not in df.columns:
            df['ราคาต่อตารางเมตร'] = np.where((df['พื้นที่ใช้สอย (ตร.ม.)'] > 0) & (df['ราคา'] > 0), df['ราคา'] / df['พื้นที่ใช้สอย (ตร.ม.)'], np.nan)
        else:
            df['ราคาต่อตารางเมตร'] = pd.to_numeric(df['ราคาต่อตารางเมตร'], errors='coerce')

        return df

    # Always prefer parquet when it exists (10-50x faster than Excel)
    if parquet_file.exists():
        try:
            df = pd.read_parquet(parquet_file)
            return ensure_derived_cols(df)
        except Exception as e:
            if not excel_file.exists():
                st.error(f"เกิดข้อผิดพลาดในการโหลดไฟล์ Parquet และไม่พบไฟล์ Excel: {e}")
                return None
                
    try:
        # Load excel file
        df = pd.read_excel(excel_file)
        
        # Replace undefined values with NaN
        df = df.replace(["$undefined", "undefined", "nan", "NaN", "NAN"], np.nan)
        
        # Clean coordinates
        df['ละติจูด'] = pd.to_numeric(df['ละติจูด'], errors='coerce')
        df['ลองจิจูด'] = pd.to_numeric(df['ลองจิจูด'], errors='coerce')
        
        # Clean coordinates outside Thailand boundary
        invalid_coords = ~(df['ละติจูด'].between(5, 21) & df['ลองจิจูด'].between(97, 106))
        df.loc[invalid_coords, 'ละติจูด'] = np.nan
        df.loc[invalid_coords, 'ลองจิจูด'] = np.nan
        
        # Clean prices
        df['ราคา'] = pd.to_numeric(df['ราคา'], errors='coerce')
        
        # Fill NaN values in essential text columns (cast to object first to prevent Categorical fillna errors)
        df['รหัสทรัพย์'] = df['รหัสทรัพย์'].astype(object).fillna("-").astype(str).str.strip()
        df['ประเภททรัพย์'] = df['ประเภททรัพย์'].astype(object).fillna("อื่นๆ").astype(str).str.strip()
        df['จังหวัด'] = df['จังหวัด'].astype(object).fillna("ไม่ระบุ").astype(str).str.strip()
        df['ตำบล'] = df['ตำบล'].astype(object).fillna("").astype(str).str.strip()
        df['อำเภอ'] = df['อำเภอ'].astype(object).fillna("").astype(str).str.strip()
        df['ชื่อโครงการ'] = df['ชื่อโครงการ'].astype(object).fillna("").astype(str).str.strip()
        df['ประเภทการขาย'] = df['ประเภทการขาย'].astype(object).fillna("").astype(str).str.strip()
        df['พื้นที่ (ไร่-งาน-วา)'] = df['พื้นที่ (ไร่-งาน-วา)'].astype(object).fillna("").astype(str).str.strip()
        df['วันที่ดึงข้อมูล'] = df['วันที่ดึงข้อมูล'].astype(object).fillna("").astype(str).str.strip()
        
        # ทำความสะอาดข้อมูลจังหวัด ป้องกันอำเภอ/ตำบลเบียดเข้ามาปะปน
        THAI_PROVINCES = {
            "กรุงเทพมหานคร", "กระบี่", "กาญจนบุรี", "กาฬสินธุ์", "กำแพงเพชร", "ขอนแก่น", "จันทบุรี", "ฉะเชิงเทรา", "ชลบุรี", "ชัยนาท", 
            "ชัยภูมิ", "ชุมพร", "เชียงราย", "เชียงใหม่", "ตรัง", "ตราด", "ตาก", "นครนายก", "นครปฐม", "นครพนม", "นครราชสีมา", 
            "นครศรีธรรมราช", "นครสวรรค์", "นนทบุรี", "นราธิวาส", "น่าน", "บึงกาฬ", "บุรีรัมย์", "ปทุมธานี", "ประจวบคีรีขันธ์", 
            "ปราจีนบุรี", "ปัตตานี", "พระนครศรีอยุธยา", "พะเยา", "พังงา", "พัทลุง", "พิจิตร", "พิษณุโลก", "เพชรบุรี", "เพชรบูรณ์", 
            "แพร่", "ภูเก็ต", "มหาสารคาม", "มุกดาหาร", "แม่ฮ่องสอน", "ยโสธร", "ยะลา", "ร้อยเอ็ด", "ระนอง", "ระยอง", 
            "ราชบุรี", "ลพบุรี", "ลำปาง", "ลำพูน", "เลย", "ศรีสะเกษ", "สกลนคร", "สงขลา", "สตูล", "สมุทรปราการ", "สมุทรสงคราม", 
            "สมุทรสาคร", "สระแก้ว", "สระบุรี", "สิงห์บุรี", "สุโขทัย", "สุพรรณบุรี", "สุราษฎร์ธานี", "สุรินทร์", "หนองคาย", 
            "หนองบัวลำภู", "อ่างทอง", "อุดรธานี", "อุทัยธานี", "อุตรดิตถ์", "อุบลราชธานี", "อำนาจเจริญ"
        }
        
        PROVINCE_MAPPING = {
            "PATHUM THANI": "ปทุมธานี",
            "NAKHON SAWAN": "นครสวรรค์",
            "กรุงเทพ": "กรุงเทพมหานคร",
            "กรุงเทพฯ": "กรุงเทพมหานคร",
            "ปทุม": "ปทุมธานี",
            "อยุธยา": "พระนครศรีอยุธยา",
            "โคราช": "นครราชสีมา",
        }
        
        DISTRICT_TO_PROVINCE = {
            "บางบัวทอง": "นนทบุรี", "บางใหญ่": "นนทบุรี", "ปากเกร็ด": "นนทบุรี", "เมืองนนทบุรี": "นนทบุรี", 
            "บางกรวย": "นนทบุรี", "บางศรีเมือง": "นนทบุรี", "ไทรม้า": "นนทบุรี", "บางรักพัฒนา": "นนทบุรี",
            "บางรักน้อย": "นนทบุรี", "เสาธงหิน": "นนทบุรี", "ท่าอิฐ": "นนทบุรี", "คลองเกลือ": "นนทบุรี",
            "ธัญบุรี": "ปทุมธานี", "คลองหลวง": "ปทุมธานี", "ลำลูกกา": "ปทุมธานี", "สามโคก": "ปทุมธานี", 
            "ลาดหลุมแก้ว": "ปทุมธานี", "เมืองปทุมธานี": "ปทุมธานี", "คลองสอง": "ปทุมธานี", "คลองหนึ่ง": "ปทุมธานี",
            "คลองสาม": "ปทุมธานี", "คลองสี่": "ปทุมธานี", "คลองห้า": "ปทุมธานี", "คลองหก": "ปทุมธานี",
            "ประชาธิปัตย์": "ปทุมธานี", "คูคต": "ปทุมธานี", "ลาดสวาย": "ปทุมธานี", "บึงยี่โถ": "ปทุมธานี",
            "บางพลี": "สมุทรปราการ", "พระประแดง": "สมุทรปราการ", "บางบ่อ": "สมุทรปราการ", "บางเสาธง": "สมุทรปราการ", 
            "พระสมุทรเจดีย์": "สมุทรปราการ", "เมืองสมุทรปราการ": "สมุทรปราการ", "ราชาเทวะ": "สมุทรปราการ",
            "บางพลีใหญ่": "สมุทรปราการ", "สำโรง": "สมุทรปราการ", "สำโรงเหนือ": "สมุทรปราการ", "บางเมือง": "สมุทรปราการ",
            "ลาดพร้าว": "กรุงเทพมหานคร", "บางกะปิ": "กรุงเทพมหานคร", "มีนบุรี": "กรุงเทพมหานคร", "ประเวศ": "กรุงเทพมหานคร", 
            "จอมทอง": "กรุงเทพมหานคร", "สายไหม": "กรุงเทพมหานคร", "ทวีวัฒนา": "กรุงเทพมหานคร", "สวนหลวง": "กรุงเทพมหานคร", 
            "ห้วยขวาง": "กรุงเทพมหานคร", "คลองสามวา": "กรุงเทพมหานคร", "คันนายาว": "กรุงเทพมหานคร", "ตลิ่งชัน": "กรุงเทพมหานคร", 
            "บางแค": "กรุงเทพมหานคร", "บางบอน": "กรุงเทพมหานคร", "บางนา": "กรุงเทพมหานคร", "ลาดกระบัง": "กรุงเทพมหานคร", 
            "บึงกุ่ม": "กรุงเทพมหานคร", "สะพานสูง": "กรุงเทพมหานคร", "ดอนเมือง": "กรุงเทพมหานคร", "หลักสี่": "กรุงเทพมหานคร", 
            "พญาไท": "กรุงเทพมหานคร", "ดินแดง": "กรุงเทพมหานคร", "ปทุมวัน": "กรุงเทพมหานคร", "คลองถนน": "กรุงเทพมหานคร",
            "จรเข้บัว": "กรุงเทพมหานคร", "คลองเจ้าคุณสิงห์": "กรุงเทพมหานคร", "บางมด": "กรุงเทพมหานคร", "สีกัน": "กรุงเทพมหานคร",
            "ทุ่งสองห้อง": "กรุงเทพมหานคร", "ทุ่งครุ": "กรุงเทพมหานคร", "บางนาเหนือ": "กรุงเทพมหานคร", "บางนาใต้": "กรุงเทพมหานคร",
            "บางบอนเหนือ": "กรุงเทพมหานคร", "หัวหมาก": "กรุงเทพมหานคร", "แสมดำ": "กรุงเทพมหานคร", "คลองเตย": "กรุงเทพมหานคร",
            "ศรีราชา": "ชลบุรี", "บางละมุง": "ชลบุรี", "เมืองชลบุรี": "ชลบุรี", "พานทอง": "ชลบุรี", 
            "พนัสนิคม": "ชลบุรี", "บ้านบึง": "ชลบุรี", "สัตหีบ": "ชลบุรี", "พัทยา": "ชลบุรี",
            "หนองปรือ": "ชลบุรี", "ตะเคียนเตี้ย": "ชลบุรี", "ทุ่งสุขลา": "ชลบุรี", "แสนสุข": "ชลบุรี",
            "สามพราน": "นครปฐม", "นครชัยศรี": "นครปฐม", "พุทธมณฑล": "นครปฐม", "เมืองนครปฐม": "นครปฐม",
            "ศาลายา": "นครปฐม", "กระทุ่มล้ม": "นครปฐม", "อ้อมใหญ่": "นครปฐม", "ยายชา": "นครปฐม",
            "กระทุ่มแบน": "สมุทรสาคร", "เมืองสมุทรสาคร": "สมุทรสาคร", "บ้านแพ้ว": "สมุทรสาคร", "อ้อมน้อย": "สมุทรสาคร",
            "มหาชัย": "สมุทรสาคร", "ท่าทราย": "สมุทรสาคร", "พันท้ายนรสิงห์": "สมุทรสาคร", "บางโทรัด": "สมุทรสาคร",
            "ชะอำ": "เพชรบุรี", "หัวหิน": "ประจวบคีรีขันธ์", "ปราณบุรี": "ประจวบคีรีขันธ์", "ทับสะแก": "ประจวบคีรีขันธ์",
        }
        
        def clean_prov_row(row):
            p = str(row.get("จังหวัด", "")).strip()
            d = str(row.get("อำเภอ", "")).strip()
            s = str(row.get("ตำบล", "")).strip()
            
            if p in PROVINCE_MAPPING:
                p = PROVINCE_MAPPING[p]
            if p.startswith("จ."):
                p = p[2:].strip()
            elif p.startswith("จังหวัด"):
                p = p[7:].strip()
                
            if p in DISTRICT_TO_PROVINCE:
                p = DISTRICT_TO_PROVINCE[p]
            elif d in DISTRICT_TO_PROVINCE:
                p = DISTRICT_TO_PROVINCE[d]
            elif s in DISTRICT_TO_PROVINCE:
                p = DISTRICT_TO_PROVINCE[s]
                
            if p in THAI_PROVINCES:
                return p
            return "ไม่ระบุ"
            
        df['จังหวัด'] = df.apply(clean_prov_row, axis=1)
        
        def clean_sale_type_val(val):
            v = str(val).strip()
            v_lower = v.lower()
            if not v or v_lower in ["nan", "none", "undefined", "$undefined", "-"]:
                return "ไม่ระบุ"
            if v_lower in ["for-sale", "for_sale", "sale", "ขาย", "ขายปกติ", "ซื้อตรง"]:
                return "ขาย"
            if v_lower in ["sale-rent", "sale/rent", "sale_rent", "ขายและเช่า", "ขาย/เช่า", "ขาย/ ให้เช่า", "ขาย / เช่า", "ขาย / ให้เช่า"]:
                return "ขาย/เช่า"
            if v_lower in ["rent", "for-rent", "for_rent", "เช่า", "ให้เช่า", "เซ้ง"]:
                return "เช่า"
            if v_lower in ["auction", "ประมูล", "ขายทอดตลาด"]:
                return "ประมูล / ขายทอดตลาด"
            if v_lower in ["down-payment", "ขายดาวน์", "รอประกาศราคา"]:
                return "ขายดาวน์ / รอประกาศ"
            return v

        df['ประเภทการขาย'] = df['ประเภทการขาย'].apply(clean_sale_type_val)
        
        # Clean titles and links
        df['ชื่อประกาศ'] = df['ชื่อประกาศ'].astype(object).fillna('ไม่มีชื่อ').astype(str)
        df['ลิงก์'] = df['ลิงก์'].astype(object).fillna('').astype(str)
        
        # Derived fields
        df['พื้นที่_ตารางวา'] = df['พื้นที่ (ไร่-งาน-วา)'].apply(parse_area_to_sqwah)
        df['พื้นที่ใช้สอย (ตร.ม.)'] = pd.to_numeric(df['พื้นที่ใช้สอย (ตร.ม.)'], errors='coerce')
        
        # Unit price calculation
        df['ราคาต่อตารางวา'] = np.where(df['พื้นที่_ตารางวา'] > 0, df['ราคา'] / df['พื้นที่_ตารางวา'], np.nan)
        df['ราคาต่อตารางเมตร'] = np.where(df['พื้นที่ใช้สอย (ตร.ม.)'] > 0, df['ราคา'] / df['พื้นที่ใช้สอย (ตร.ม.)'], np.nan)
        
        # Drop unused raw columns to save 50%+ memory (250MB RAM savings)
        df = df.drop(columns=['ID', 'ชื่อประกาศ', 'ลิงก์'], errors='ignore')
        
        # Optimize types for RAM conservation on Streamlit Cloud
        cat_cols = ['บริษัท', 'ประเภททรัพย์', 'ประเภทการขาย', 'จังหวัด', 'อำเภอ', 'ห้องนอน', 'ห้องน้ำ', 'ที่จอดรถ']
        for col in cat_cols:
            if col in df.columns:
                df[col] = df[col].astype('category')
                
        float_cols = ['ละติจูด', 'ลองจิจูด', 'พื้นที่ใช้สอย (ตร.ม.)', 'พื้นที่_ตารางวา', 'ราคาต่อตารางวา', 'ราคาต่อตารางเมตร']
        for col in float_cols:
            if col in df.columns:
                df[col] = df[col].astype('float32')
        
        # Save to Parquet for caching (using ZSTD to compress under 100MB)
        df.to_parquet(parquet_file, index=False, compression='zstd')
        
        return df
    except Exception as e:
        st.error(f"เกิดข้อผิดพลาดในการโหลดไฟล์ Excel: {e}")
        return None

# Cache static HTML & JS libraries once in memory to save 300MB+ RAM per rerun
@st.cache_data
def get_base_map_html():
    try:
        with open("static/map_template.html", "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return ""

# Load the properties data
df_raw = load_properties_data()

# ----------------- SIDEBAR -----------------
with st.sidebar:
    col_side_title, col_side_theme = st.columns([0.62, 0.38])
    with col_side_title:
        st.markdown('<h3 style="color: #6366f1; margin: 0; padding-top: 4px;"><i class="fa fa-home"></i> All Asset</h3>', unsafe_allow_html=True)
    with col_side_theme:
        is_dark_mode = st.toggle("🌙 มืด", value=False, key="app_theme_mode", help="สลับระหว่างโหมดมืด (Dark Mode) และโหมดสว่าง (Light Mode)")
    st.markdown("---")
    
    max_map_points = 100000
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
        # Search Box
        search_query = st.text_input("ค้นหา ชื่อโครงการ/รหัสทรัพย์/ชื่อประกาศ", value="")
        
        # Company Filter (Pills) with stable keys and format_func
        co_counts = df_raw['บริษัท'].value_counts()
        companies_list = ["Baania", "BAM", "SAM", "Livinginsider", "DDproperty", "Taladnudbaan", "ZmyHome"]
        
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
        else:
            filtered_provinces_df = df_by_company
            
        # Get unique pairs of (อำเภอ, จังหวัด) to display parent province in parentheses
        dist_df = filtered_provinces_df[['อำเภอ', 'จังหวัด']].drop_duplicates().dropna()
        dist_df = dist_df[dist_df['อำเภอ'].str.strip() != ""]
        unique_districts_formatted = [
            f"{row['อำเภอ']} ({row['จังหวัด']})" 
            for _, row in dist_df.iterrows()
        ]
        unique_districts_formatted.sort()
        selected_districts_formatted = st.multiselect("อำเภอ / เขต", options=unique_districts_formatted, default=[])
        
        # Parse selected districts into tuples for subdistrict option filtering
        selected_districts_tuples = []
        for d_f in selected_districts_formatted:
            if " (" in d_f:
                parts = d_f.split(" (")
                d_name = parts[0].strip()
                p_name = parts[1].replace(")", "").strip()
                selected_districts_tuples.append((d_name, p_name))
        
        # Subdistrict Filter (dynamically populate from selected districts)
        if selected_districts_tuples:
            filtered_districts_df = filtered_provinces_df[filtered_provinces_df.set_index(['อำเภอ', 'จังหวัด']).index.isin(selected_districts_tuples)]
        else:
            filtered_districts_df = filtered_provinces_df
            
        # Get unique trios of (ตำบล, อำเภอ, จังหวัด) to display parent district & province in parentheses
        sub_df = filtered_districts_df[['ตำบล', 'อำเภอ', 'จังหวัด']].drop_duplicates().dropna()
        sub_df = sub_df[sub_df['ตำบล'].str.strip() != ""]
        unique_subdistricts_formatted = [
            f"{row['ตำบล']} ({row['อำเภอ']}, {row['จังหวัด']})"
            for _, row in sub_df.iterrows()
        ]
        unique_subdistricts_formatted.sort()
        selected_subdistricts_formatted = st.multiselect("ตำบล / แขวง", options=unique_subdistricts_formatted, default=[])
        
        # Price Filter
        valid_prices = df_by_company['ราคา'].dropna()
        if not valid_prices.empty:
            min_price_val = float(valid_prices.min())
            max_price_val = float(valid_prices.max())
            
            # Generate dynamic options list for select_slider with commas
            min_val = int(min_price_val)
            max_val = int(max_price_val)
            options = [min_val]
            
            if max_val - min_val > 10000000: # > 10M
                # 1. 100k steps up to 10M
                for v in range(max(100000, (min_val // 100000) * 100000), min(10000000, max_val), 100000):
                    if v > min_val:
                        options.append(v)
                # 2. 1M steps up to 50M
                for v in range(10000000, min(50000000, max_val), 1000000):
                    if v > options[-1]:
                        options.append(v)
                # 3. 5M steps up to 200M
                for v in range(50000000, min(200000000, max_val), 5000000):
                    if v > options[-1]:
                        options.append(v)
                # 4. 20M steps up to max_val
                for v in range(200000000, max_val, 20000000):
                    if v > options[-1]:
                        options.append(v)
            else:
                step = max(1, (max_val - min_val) // 100)
                for v in range(min_val + step, max_val, step):
                    options.append(v)
                    
            if max_val > options[-1]:
                options.append(max_val)
                
            options = sorted(list(set(options)))
            
            price_range = st.select_slider(
                "ช่วงราคาขาย (บาท)",
                options=options,
                value=(options[0], options[-1]),
                format_func=lambda x: f"฿{x:,.0f}"
            )
            
            # Map points setting slider
            st.markdown("#### ⚙️ ตั้งค่าการแสดงผลแผนที่")
            mapbox_style = "open-street-map"
            
            max_limit = int(len(df_raw)) if df_raw is not None else 600329
            max_map_points = st.slider(
                "จำนวนจุดสูงสุดบนแผนที่",
                min_value=1,
                max_value=min( max_val, max_limit),
                value=min(100000, max_limit),
                step=50000,
                help="หากจุดพิกัดจริงมีมากกว่าค่าที่เลือกไว้ ระบบจะสุ่มเลือกตัวอย่างมาวาดตามสัดส่วนเพื่อรักษาความลื่นไหลและป้องกันเบราว์เซอร์ค้าง"
            )
            st.markdown(f"📍 ขีดจำกัดบนแผนที่ขณะนี้: **{max_map_points:,}** จุด")
            if max_map_points > 200000:
                st.warning("⚠️ การแสดงผลจุดเกิน 200,000 จุด อาจส่งผลให้เบราว์เซอร์ทำงานหนักและหน่วงได้ในบางเครื่อง")
        else:
            price_range = (0.0, 1000000000.0)
            max_map_points = 100000
            mapbox_style = "open-street-map"
            map_is_dark = False
    else:
        st.warning("ไม่มีตัวกรองข้อมูลเนื่องจากยังไม่มีไฟล์ข้อมูล all_assets.xlsx")

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
    position: relative !important; /* Made KPI cards static instead of floating over map */
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

/* Map chart height override removed to prevent Plotly mouse hover coordinate mismatch */

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
        <h2 style="color: #ef4444; margin-bottom: 15px; font-weight: 700;">ไม่พบไฟล์ข้อมูล 'all_assets.xlsx'</h2>
        <p style="color: #0f172a; font-size: 1.1rem; line-height: 1.6; margin-bottom: 15px;">ระบบจำเป็นต้องใช้ไฟล์ข้อมูลรวมทรัพย์สินสำหรับการแสดงผลแผนที่และแดชบอร์ด</p>
        <div style="text-align: left; background: #ffffff; padding: 25px; border-radius: 10px; border: 1px solid #e2e8f0; margin-top: 25px;">
            <p style="font-weight: 700; color: #1e293b; margin-bottom: 10px; font-size: 1.05rem;"><i class="fa fa-terminal" style="color: #6366f1; margin-right: 6px;"></i> วิธีการสั่งรันตัวดึงข้อมูลภายนอก (Scraper):</p>
            <ol style="color: #475569; font-size: 0.95rem; margin-left: 20px; line-height: 1.8; font-weight: 500;">
                <li>เปิดหน้าต่าง Terminal (PowerShell หรือ Command Prompt) ในโฟลเดอร์ของแอปพลิเคชันนี้</li>
                <li>พิมพ์คำสั่งรันระบบดึงข้อมูล: <code style="background-color: #f1f5f9; padding: 3px 8px; border-radius: 4px; font-family: monospace; color: #0f172a; font-weight: 700;">python run_all_scrapers.py</code></li>
                <li>หรือดับเบิ้ลคลิกสคริปต์รันดึงข้อมูลเพื่อเริ่มต้นประมวลผล</li>
                <li>เมื่อโปรแกรมเสร็จสิ้น ไฟล์ <code style="background-color: #f1f5f9; padding: 3px 6px; border-radius: 4px; font-family: monospace; color: #0f172a; font-weight: 700;">all_assets.xlsx</code> จะปรากฏขึ้นโดยอัตโนมัติ ให้ทำการกด Refresh หน้าแดชบอร์ดนี้ใหม่</li>
            </ol>
        </div>
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
        # Get rare types dynamically based on selected companies
        if selected_companies:
            df_by_company = df_raw[df_raw['บริษัท'].isin(selected_companies)]
        else:
            df_by_company = df_raw
        type_counts = df_by_company['ประเภททรัพย์'].value_counts()
        top_n = 7
        rare_types = type_counts.index[top_n:].tolist()
        
        # Check if the user selected specific rare types in the dynamically shown multiselect
        selected_rare = st.session_state.get("selected_rare_types", [])
        selected_rare_clean = [t.rsplit(" (", 1)[0] for t in selected_rare] if selected_rare else []
        
        if selected_rare_clean:
            # Only filter for selected rare types + selected main types
            actual_selected_types = [t for t in selected_types if t != "เพิ่มเติม"] + selected_rare_clean
        else:
            # If no specific rare type is chosen, include all rare types as fallback
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
        # Include all items when full default range is selected (including unstated prices)
        df_filtered = df_filtered[
            (df_filtered['ราคา'].isna()) | 
            ((df_filtered['ราคา'] >= price_range[0]) & (df_filtered['ราคา'] <= price_range[1]))
        ]
    else:
        # Strictly filter properties within user-selected price range
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
    total_value = valid_prices_filtered.sum() / 1e6  # Convert to Million Baht
    avg_price = valid_prices_filtered.mean() / 1e6   # Million Baht
    max_price = valid_prices_filtered.max() / 1e6    # Million Baht
else:
    total_value = 0.0
    avg_price = 0.0
    max_price = 0.0

total_count_str = f"{total_count:,.0f}"
filtered_count_str = f"{filtered_count:,.0f}"
total_value_str = f"฿{total_value:,.2f}M"
avg_price_str = f"฿{avg_price:,.2f}M"
max_price_str = f"฿{max_price:,.2f}M"

# Dynamic breakdown of company counts strictly matching df_filtered
active_co_counts = df_filtered['บริษัท'].value_counts()
active_companies = selected_companies if selected_companies else ["Baania", "BAM", "SAM", "Livinginsider", "DDproperty", "Taladnudbaan", "ZmyHome"]
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
        <div class="floating-card-title"><i class="fa fa-tags" style="color: #10b981;"></i> ราคาเฉลี่ย</div>
        <div class="floating-card-value">{avg_price_str}</div>
        <div class="floating-card-sub">ล้านบาท / ทรัพย์สิน</div>
    </div>
    <div class="floating-card">
        <div class="floating-card-title"><i class="fa fa-arrow-up" style="color: #f59e0b;"></i> ราคาสูงสุด</div>
        <div class="floating-card-value">{max_price_str}</div>
        <div class="floating-card-sub">มูลค่าสูงสุดตามตัวกรองแถบซ้าย</div>
    </div>
</div>
"""

# Render KPI Cards globally right before tabs
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
        # Setup progress bar for map rendering process
        progress_bar = st.progress(0, text="กำลังเตรียมข้อมูลแผนที่...")
        
        # Step 1: Filter rows with coordinates (20%)
        progress_bar.progress(20, text="กำลังกรองจุดพิกัดในประเทศไทย (20%)...")
        map_data = df_filtered[
            df_filtered['ละติจูด'].notna() & df_filtered['ลองจิจูด'].notna() &
            df_filtered['ละติจูด'].between(5, 21) & df_filtered['ลองจิจูด'].between(97, 106)
        ].copy()
        
        # Step 2: Cap map points at safe limit (40%)
        progress_bar.progress(40, text="กำลังจัดการข้อมูลพิกัดความหนาแน่นสูง (40%)...")
        MAP_MAX_POINTS = max_map_points
        map_data_full_len = len(map_data)
        map_sampled = False
        if map_data_full_len > MAP_MAX_POINTS:
            map_sampled = True
            map_data = map_data.sample(n=MAP_MAX_POINTS, random_state=42)
            
        # Step 3: Pre-format price column (60%)
        progress_bar.progress(60, text="กำลังจัดรูปแบบราคาทรัพย์สิน (60%)...")
        if not map_data.empty:
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
            # Step 4: Pre-compile hover tooltips (80%)
            progress_bar.progress(80, text="กำลังทำดัชนีและป้ายข้อมูลพิกัด (80%)...")
            

            
            # Direct standalone HTML rendering with base64 embedded CSV data
            # This runs 100% locally and remotely, bypassing relative paths, CORS, and sandboxing 404 issues!
            
            # Build dataset for embedding
            title_col = 'ชื่อประกาศ_สะอาด' if 'ชื่อประกาศ_สะอาด' in map_data.columns else ('ชื่อโครงการ' if 'ชื่อโครงการ' in map_data.columns else 'รหัสทรัพย์')
            titles = map_data[title_col].astype(object).fillna('ไม่มีชื่อ').astype(str).str[:30].values
            ids = map_data['รหัสทรัพย์'].astype(object).fillna('-').astype(str).str[:15].values
            provs = map_data['จังหวัด'].astype(object).fillna('-').astype(str).values
            types = map_data['ประเภททรัพย์'].astype(object).fillna('-').astype(str).values
            companies = map_data['บริษัท'].astype(object).fillna('-').astype(str).values
            prices = map_data['ราคาขาย'].astype(str).values
            
            # Colors
            COMPANY_COLORS = {"Baania": [245, 158, 11], "BAM": [59, 130, 246], "SAM": [16, 185, 129], "Livinginsider": [132, 204, 22], "DDproperty": [168, 85, 247], "Taladnudbaan": [6, 182, 212], "ZmyHome": [236, 72, 153]}
            DEFAULT_COLOR = [148, 163, 184]
            r_vals, g_vals, b_vals = [], [], []
            for company in map_data['บริษัท']:
                color = COMPANY_COLORS.get(company, DEFAULT_COLOR)
                r_vals.append(color[0])
                g_vals.append(color[1])
                b_vals.append(color[2])
                
            # Create a very compact pandas dataframe
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
            
            # Step 5: Preparing map layer (90%)
            progress_bar.progress(90, text="กำลังเตรียมการเข้ารหัสข้อมูลพิกัด (90%)...")
            
            # Convert CSV to base64
            csv_str = csv_df.to_csv(index=False)
            csv_base64 = base64.b64encode(csv_str.encode('utf-8')).decode('utf-8')
            
            # Use pre-cached base HTML template (prevents duplicate reading of 3MB JS libraries)
            base_tmpl = get_base_map_html()
            html_content = base_tmpl.replace("CSV_BASE64_PLACEHOLDER", csv_base64)
            
            # Inject body theme class for map legend overlay styling
            body_theme_class = "dark-theme" if is_dark_mode else ""
            html_content = html_content.replace("BODY_CLASS_PLACEHOLDER", body_theme_class)

            # Calculate counts for map legend from the actual map_data (reflects coordinate filters and sampling)
            map_baania_count = len(map_data[map_data['บริษัท'] == 'Baania'])
            map_bam_count = len(map_data[map_data['บริษัท'] == 'BAM'])
            map_sam_count = len(map_data[map_data['บริษัท'] == 'SAM'])
            map_livinginsider_count = len(map_data[map_data['บริษัท'] == 'Livinginsider'])
            map_ddproperty_count = len(map_data[map_data['บริษัท'] == 'DDproperty'])
            map_taladnudbaan_count = len(map_data[map_data['บริษัท'] == 'Taladnudbaan'])
            map_zmyhome_count = len(map_data[map_data['บริษัท'] == 'ZmyHome'])

            html_content = html_content.replace("BAANIA_COUNT", f"{map_baania_count:,}")
            html_content = html_content.replace("BAM_COUNT", f"{map_bam_count:,}")
            html_content = html_content.replace("SAM_COUNT", f"{map_sam_count:,}")
            html_content = html_content.replace("LIVINGINSIDER_COUNT", f"{map_livinginsider_count:,}")
            html_content = html_content.replace("DDPROPERTY_COUNT", f"{map_ddproperty_count:,}")
            html_content = html_content.replace("TALADNUDBAAN_COUNT", f"{map_taladnudbaan_count:,}")
            html_content = html_content.replace("ZMYHOME_COUNT", f"{map_zmyhome_count:,}")
            
            # Finished (100%)
            progress_bar.progress(100, text="โหลดเสร็จสมบูรณ์! (100%)")
            

            
            # Render the interactive map (deck.gl requires JavaScript + iframe isolation)
            # Try multiple methods in priority order for Streamlit version compatibility
            map_rendered = False
            
            # Method 1: st.components.v1.html (deprecated but still functional)
            if not map_rendered:
                try:
                    import streamlit.components.v1 as stc
                    stc.html(html_content, height=680)
                    map_rendered = True
                except Exception:
                    pass
            
            # Method 2: st.html with unsafe_allow_javascript (newer Streamlit)
            if not map_rendered:
                try:
                    st.html(html_content, unsafe_allow_javascript=True)
                    map_rendered = True
                except Exception:
                    pass
            
            if not map_rendered:
                st.error("❌ ไม่สามารถแสดงแผนที่ได้ กรุณาลองรีเฟรชหน้าเว็บ")
            
            # Clear progress bar
            progress_bar.empty()
        st.markdown("<div style='margin-bottom: 20px;'></div>", unsafe_allow_html=True)
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
                    color_discrete_map={"Baania": "#f59e0b", "BAM": "#3b82f6", "SAM": "#10b981", "Livinginsider": "#84cc16", "DDproperty": "#a855f7", "Taladnudbaan": "#06b6d4", "ZmyHome": "#ec4899"},
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
            
            # 3. Average Price by Company
            with col_c3:
                avg_price_comp = df_filtered.groupby('บริษัท')['ราคา'].mean().reset_index()
                avg_price_comp.columns = ['บริษัท', 'ราคาเฉลี่ย (บาท)']
                fig_avg_p = px.bar(
                    avg_price_comp,
                    x='บริษัท',
                    y='ราคาเฉลี่ย (บาท)',
                    color='บริษัท',
                    title='ราคาประเมิน/ตั้งขายเฉลี่ยรายบริษัท',
                    color_discrete_map={"Baania": "#f59e0b", "BAM": "#3b82f6", "SAM": "#10b981", "Livinginsider": "#84cc16", "DDproperty": "#a855f7", "Taladnudbaan": "#06b6d4", "ZmyHome": "#ec4899"},
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
                    text_labels = [f"{l}" for l in labels[:-1]] + ([''] if not minor.empty else [])
                    
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
            st.markdown("#### 📐 วิเคราะห์ราคาเฉลี่ยต่อตารางเมตร (Price per Sq.M. Insights)")
            st.write("เปรียบเทียบราคาเฉลี่ยต่อตารางเมตรสำหรับทรัพย์สินประเภทสิ่งปลูกสร้าง (คอนโด, บ้านเดี่ยว, ทาวน์โฮม, อาคารพาณิชย์) แยกตามแบรนด์คู่แข่ง เพื่อดูความคุ้มค่าเชิงเปรียบเทียบ")
            
            # Filter properties with valid price per sq.m. and positive price
            area_df = df_filtered[
                (df_filtered['ราคาต่อตารางเมตร'].notna()) & 
                (df_filtered['ราคาต่อตารางเมตร'] > 0) & 
                (df_filtered['ราคาต่อตารางเมตร'] < 1000000) # Exclude extreme outliers
            ].copy()
            
            # Map property types to major categories for visualization
            def map_major_type(t):
                t_str = str(t).strip()
                if 'ที่ดินเปล่า' in t_str:
                    return 'ที่ดินเปล่า'
                elif 'คอนโด' in t_str:
                    return 'คอนโด'
                elif 'บ้านเดี่ยว' in t_str or 'บ้านแฝด' in t_str or 'บ้าน' in t_str:
                    return 'บ้านเดี่ยว'
                elif 'ทาวน์โฮม' in t_str or 'ทาวน์เฮ้าส์' in t_str or 'ทาวน์เฮาส์' in t_str:
                    return 'ทาวน์โฮม'
                elif 'อาคารพาณิชย์' in t_str or 'ตึกแถว' in t_str:
                    return 'อาคารพาณิชย์'
                return None
                
            if not area_df.empty:
                area_df['กลุ่มประเภททรัพย์'] = area_df['ประเภททรัพย์'].apply(map_major_type)
                area_df = area_df[area_df['กลุ่มประเภททรัพย์'].notna()]
                
                if not area_df.empty:
                    # Calculate mean price per sq.m. grouped by Company and Property Type Group
                    avg_per_sqm = area_df.groupby(['บริษัท', 'กลุ่มประเภททรัพย์'])['ราคาต่อตารางเมตร'].mean().reset_index()
                    avg_per_sqm.columns = ['บริษัท', 'ประเภททรัพย์', 'ราคาเฉลี่ยต่อ ตร.ม. (บาท)']
                    
                    fig_sqm = px.bar(
                        avg_per_sqm,
                        x='ประเภททรัพย์',
                        y='ราคาเฉลี่ยต่อ ตร.ม. (บาท)',
                        color='บริษัท',
                        barmode='group',
                        title='เปรียบเทียบราคาเฉลี่ยต่อตารางเมตร แยกตามแบรนด์และประเภททรัพย์สิน',
                        color_discrete_map={"Baania": "#f59e0b", "BAM": "#3b82f6", "SAM": "#10b981", "Livinginsider": "#84cc16", "DDproperty": "#a855f7", "Taladnudbaan": "#06b6d4", "ZmyHome": "#ec4899"},
                        template=plotly_template
                    )
                    fig_sqm.update_layout(
                        title_font=dict(size=14, family="Outfit"),
                        xaxis_title="ประเภททรัพย์สิน",
                        yaxis_title="ราคาเฉลี่ยต่อ ตร.ม. (บาท)",
                        legend_title="บริษัท"
                    )
                    st.plotly_chart(style_plotly_fig(fig_sqm), width="stretch", theme=None)
                else:
                    st.warning("⚠️ ไม่มีข้อมูลประเภททรัพย์สินหลักที่มีข้อมูลราคาต่อตารางเมตร")
            else:
                st.warning("⚠️ ไม่มีข้อมูลพื้นที่ใช้สอยหรือราคาทรัพย์สินสำหรับวิเคราะห์ราคาต่อตารางเมตร")

# ----- TAB 3: PROPERTY LISTING -----
with tab3:
    st.markdown(f"### 📋 รายการทรัพยสินที่ค้นพบ ({total_count:,} รายการ)")
    
    if df_filtered.empty:
        st.warning("⚠️ ไม่พบข้อมูลตามเงื่อนไข")
    else:
        # Show top 5,000 rows in the interactive table for performance
        display_limit = 5000
        if len(df_filtered) > display_limit:
            st.info(f"💡 แสดงผลตารางเฉพาะ {display_limit:,} รายการแรก เพื่อลดการใช้ข้อมูลหน้าเว็บและช่วยให้โหลดรวดเร็ว (กรุณาใช้แถบตัวกรองที่คอลัมน์ซ้ายเพื่อบีบขอบเขตข้อมูลเพิ่มเติม)")
            df_table = df_filtered.head(display_limit)
        else:
            df_table = df_filtered
            
        st.dataframe(
            df_table[[
                "บริษัท", "รหัสทรัพย์", "ชื่อโครงการ", "ชื่อประกาศ", "ประเภททรัพย์", 
                "ประเภทการขาย", "ราคา", "จังหวัด", "อำเภอ", "ตำบล",
                "พื้นที่ (ไร่-งาน-วา)", "พื้นที่ใช้สอย (ตร.ม.)", "ห้องนอน", "ห้องน้ำ", "ที่จอดรถ", "วันที่ดึงข้อมูล"
            ]],
            width="stretch",
            column_config={
                "ราคา": st.column_config.NumberColumn("ราคาขาย (บาท)", format="%d"),
                "พื้นที่ใช้สอย (ตร.ม.)": st.column_config.NumberColumn(format="%.1f")
            }
        )

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

            if "prev_ref_method" not in st.session_state:
                st.session_state["prev_ref_method"] = "📌 ระบุพิกัดด้วยตัวเอง (Manual Coordinates)"

            ref_method = st.radio(
                "วิธีการกำหนดจุดอ้างอิง",
                options=["📌 ระบุพิกัดด้วยตัวเอง (Manual Coordinates)", "🏠 เลือกจากรายการทรัพย์สินในระบบ (Choose from Asset)"],
                horizontal=True,
                key="comp_ref_method"
            )

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
                    sel_ref_company = st.selectbox(
                        "บริษัททรัพย์สิน (เลือกจุดอ้างอิง)",
                        options=sorted([str(c) for c in df_raw['บริษัท'].dropna().unique()]) if df_raw is not None else ["BAM"],
                        index=0,
                        key="comp_sel_company"
                    )
                with col_sel2:
                    ref_comp_df = df_raw[df_raw['บริษัท'] == sel_ref_company] if df_raw is not None else pd.DataFrame()
                    ref_comp_types = sorted([str(t) for t in ref_comp_df['ประเภททรัพย์'].dropna().unique()]) if not ref_comp_df.empty else []
                    valid_ref_types = ["ทั้งหมด"] + ref_comp_types
                    sanitize_session_state("comp_sel_type", valid_ref_types, "ทั้งหมด")
                    sel_ref_type = st.selectbox(
                        "ประเภททรัพย์ (เลือกจุดอ้างอิง)",
                        options=valid_ref_types,
                        index=0,
                        key="comp_sel_type"
                    )

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
                    # Add text input to search/filter the listings
                    ref_search_query = st.text_input(
                        "🔍 พิมพ์คำค้นหาเพื่อกรองรายชื่อทรัพย์สิน (ชื่อโครงการ, รหัสทรัพย์, ทำเล)",
                        value="",
                        placeholder="พิมพ์ชื่อโครงการ, รหัสทรัพย์, หรือทำเล เช่น แสนสิริ, BAM-1020, นนทบุรี...",
                        key="comp_ref_search"
                    )

                    # Apply filter if query is not empty
                    if ref_search_query:
                        q = ref_search_query.strip().lower()
                        ref_assets_df = ref_assets_df[
                            ref_assets_df['ชื่อประกาศ'].astype(str).str.lower().str.contains(q, na=False) |
                            ref_assets_df['รหัสทรัพย์'].astype(str).str.lower().str.contains(q, na=False) |
                            ref_assets_df['ชื่อโครงการ'].astype(str).str.lower().str.contains(q, na=False)
                        ]

                    if not ref_assets_df.empty:
                        # Force a copy to avoid SettingWithCopyWarning or copy-on-write errors in pandas 2.0+
                        ref_assets_df = ref_assets_df.copy()

                        # Create labels for selectbox: "ชื่อประกาศ (รหัสทรัพย์) - ฿ราคา"
                        ref_assets_df['label'] = (
                            ref_assets_df['ชื่อประกาศ'].astype(str).str[:35] + " (" + 
                            ref_assets_df['รหัสทรัพย์'].astype(str) + ") - ฿" + 
                            ref_assets_df['ราคา'].map('{:,.0f}'.format)
                        )

                        # Drop duplicate labels to avoid DuplicateOption errors in Streamlit selectbox
                        ref_assets_df = ref_assets_df.drop_duplicates(subset=['label'])

                        # Limit options to top 100 to prevent WebSocket message limit crashes!
                        total_matches = len(ref_assets_df)
                        display_df = ref_assets_df.head(100)

                        st.write(f"แสดงผล {len(display_df)} รายการแรก จากที่ค้นพบทั้งหมด {total_matches:,} รายการ (ใช้กล่องค้นหาเพื่อกรองเพิ่มได้)")

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
                                inp_type = selected_asset['ประเภททรัพย์']

                                st.info(f"""
                                🏠 **รายละเอียดทรัพย์อ้างอิงที่เลือก**:
                                - **ชื่อประกาศ:** {selected_asset['ชื่อประกาศ']}
                                - **รหัสทรัพย์:** {selected_asset['รหัสทรัพย์']} ({selected_asset['บริษัท']})
                                - **พิกัด:** {inp_lat:.6f}, {inp_lng:.6f}
                                - **ราคาขาย:** ฿{inp_price:,.0f} บาท
                                - **ประเภท:** {inp_type}
                                """)
                            else:
                                st.warning("⚠️ เกิดข้อผิดพลาดในการดึงข้อมูลรายการที่เลือก")
                        else:
                            st.warning("⚠️ กรุณาพิมพ์คำค้นหาเพื่อเลือกทรัพย์สินอ้างอิง")
                    else:
                        st.warning("⚠️ ไม่พบรายการทรัพย์สินที่ตรงกับคำค้นหาของคุณในเงื่อนไขนี้")
                else:
                    st.warning("⚠️ ไม่พบรายการทรัพย์สินที่มีพิกัดละติจูด/ลองจิจูดครบถ้วนในเงื่อนไขที่เลือก")

            else:
                # If they choose manual coordinates, render manual input widgets
                inp_name = st.text_input("ชื่อสถานที่/จุดอ้างอิง", value="จุดศูนย์กลางกรุงเทพฯ (อนุสาวรีย์ชัยฯ)", key="comp_manual_name")
                inp_lat = st.number_input("ละติจูด (Latitude)", value=13.7651, format="%.6f", key="comp_manual_lat")
                inp_lng = st.number_input("ลองจิจูด (Longitude)", value=100.5383, format="%.6f", key="comp_manual_lng")
                inp_price = st.number_input("ราคาของจุดอ้างอิง (บาท)", min_value=0.0, value=5000000.0, step=100000.0, format="%.0f", key="comp_manual_price")

                prop_options = sorted([str(t) for t in df_raw['ประเภททรัพย์'].dropna().unique()]) if df_raw is not None and not df_raw.empty else ["บ้านเดี่ยว"]
                inp_type = st.selectbox(
                    "ประเภททรัพย์ของจุดอ้างอิง",
                    options=prop_options,
                    index=0,
                    key="comp_manual_type"
                )

        with inp_col2:
            st.markdown("##### ⚙️ ส่วนที่ 2: เงื่อนไขการค้นหา")
            search_radius = st.slider("รัศมีการค้นหา (กิโลเมตร)", min_value=0.5, max_value=10.0, value=5.0, step=0.5)

            # Company Filter for Comparison (Pills)
            all_comp_list = sorted([str(c) for c in df_raw['บริษัท'].dropna().unique()]) if df_raw is not None else ["Baania", "BAM", "SAM", "Livinginsider", "DDproperty", "Taladnudbaan", "ZmyHome"]
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

        st.markdown("<br/>", unsafe_allow_html=True)

        # Auto-run radius analysis whenever valid coordinates exist
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
                st.warning(f"❌ ไม่พบทรัพย์สิน NPA ตามเงื่อนไขตัวกรองในรัศมี {search_radius} กิโลเมตร รอบจุดพิกัด ({inp_lat}, {inp_lng})")
            else:
                st.success(f"พบทรัพย์ NPA ทั้งหมด {len(nearby_df):,} รายการ ในรัศมี {search_radius} กิโลเมตร!")

                # ----------------- PRICE COMPARISON ANALYSIS -----------------
                prices = nearby_df['ราคา'].dropna()
                if not prices.empty:
                    min_price = float(prices.min())
                    max_price = float(prices.max())
                    avg_price = float(prices.mean())
                    range_diff = max_price - min_price

                    st.markdown("#### 📊 ผลการวิเคราะห์ราคาเปรียบเทียบทำเล")

                    # Columns for metrics
                    m_col1, m_col2, m_col3, m_col4 = st.columns(4)

                    # Col 1: Reference Point
                    ref_html = f"""
                    <div class="metric-card">
                        <div class="metric-title"><i class="fa fa-map-marker" style="color: #ef4444;"></i> พิกัดอ้างอิงของคุณ</div>
                        <div class="metric-value">฿{inp_price:,.0f}</div>
                        <div class="metric-sub">{inp_type}</div>
                    </div>
                    """
                    m_col1.markdown(ref_html, unsafe_allow_html=True)

                    # Helper function to generate sub text for diff
                    def get_diff_sub_html(val, ref_val):
                        if ref_val <= 0:
                            return '<div class="metric-sub">ไม่ได้กำหนดราคาอ้างอิง</div>'
                        diff = val - ref_val
                        pct = (diff / ref_val) * 100
                        if diff < 0:
                            return f'<div class="metric-sub"><span style="color: #10b981; font-weight: 600;"><i class="fa fa-arrow-down"></i> ถูกกว่า {pct:+.1f}%</span> (ต่าง ฿{abs(diff):,.0f})</div>'
                        elif diff > 0:
                            return f'<div class="metric-sub"><span style="color: #ef4444; font-weight: 600;"><i class="fa fa-arrow-up"></i> แพงกว่า {pct:+.1f}%</span> (ต่าง ฿{abs(diff):,.0f})</div>'
                        else:
                            return '<div class="metric-sub"><span style="color: #64748b; font-weight: 600;">ราคาเท่ากัน</span></div>'

                    # Col 2: Min Price
                    min_sub = get_diff_sub_html(min_price, inp_price)
                    min_html = f"""
                    <div class="metric-card">
                        <div class="metric-title"><i class="fa fa-arrow-down" style="color: #10b981;"></i> ราคาต่ำสุดในพื้นที่</div>
                        <div class="metric-value">฿{min_price:,.0f}</div>
                        {min_sub}
                    </div>
                    """
                    m_col2.markdown(min_html, unsafe_allow_html=True)

                    # Col 3: Max Price
                    max_sub = get_diff_sub_html(max_price, inp_price)
                    max_html = f"""
                    <div class="metric-card">
                        <div class="metric-title"><i class="fa fa-arrow-up" style="color: #ef4444;"></i> ราคาสูงสุดในพื้นที่</div>
                        <div class="metric-value">฿{max_price:,.0f}</div>
                        {max_sub}
                    </div>
                    """
                    m_col3.markdown(max_html, unsafe_allow_html=True)

                    # Col 4: Avg Price
                    avg_sub = get_diff_sub_html(avg_price, inp_price)
                    avg_html = f"""
                    <div class="metric-card">
                        <div class="metric-title"><i class="fa fa-calculator" style="color: #3b82f6;"></i> ราคาเฉลี่ยในพื้นที่</div>
                        <div class="metric-value">฿{avg_price:,.0f}</div>
                        {avg_sub}
                    </div>
                    """
                    m_col4.markdown(avg_html, unsafe_allow_html=True)

                    st.markdown("<br/>", unsafe_allow_html=True)

                    # Summary info box
                    comp_word = "ถูกกว่า" if avg_price < inp_price else ("แพงกว่า" if avg_price > inp_price else "เท่ากับ")
                    diff_avg = abs(avg_price - inp_price)
                    diff_avg_pct = (diff_avg / inp_price * 100) if inp_price > 0 else 0

                    st.info(f"""
                    💡 **บทวิเคราะห์ด้านราคาและส่วนต่างทำเล**:
                    - ทรัพย์สิน NPA ในทำเลนี้มีราคาระหว่าง **฿{min_price:,.0f}** ถึง **฿{max_price:,.0f}** บาท
                    - **ส่วนต่างของช่วงราคา (ราคาสูงสุด - ต่ำสุด)** อยู่ที่ **฿{range_diff:,.0f}** บาท
                    - ราคาเฉลี่ยของทรัพย์สิน NPA รอบๆ คือ **฿{avg_price:,.0f}** บาท ซึ่ง **{comp_word}** จุดอ้างอิงของคุณอยู่ **฿{diff_avg:,.0f}** บาท (คิดเป็น {diff_avg_pct:.1f}%)
                    """)

                st.markdown("##### 📋 รายการทรัพย์สิน NPA ที่พบในรัศมีค้นหา")

                # Show Table
                st.dataframe(
                    nearby_df[[
                        "บริษัท", "รหัสทรัพย์", "ชื่อประกาศ", "ประเภททรัพย์", "ราคา", 
                        "จังหวัด", "อำเภอ", "ตำบล", "ระยะทาง (กม.)", "ลิงก์"
                    ]].sort_values("ระยะทาง (กม.)"),
                    width="stretch",
                    column_config={
                        "ราคา": st.column_config.NumberColumn("ราคาขาย (บาท)", format="%d"),
                        "ระยะทาง (กม.)": st.column_config.NumberColumn("ระยะทาง (กม.)", format="%.2f")
                    }
                )

                # Show map
                st.markdown("##### 🗺️ แผนที่ตำแหน่งจุดอ้างอิงเทียบกับตำแหน่งทรัพย์ NPA ที่พบ")

                map_points = []
                # Reference point
                map_points.append({
                    "ละติจูด": inp_lat,
                    "ลองจิจูด": inp_lng,
                    "ชื่อ": f"📍 จุดอ้างอิง: {inp_name}",
                    "ราคา (บาท)": f"฿{inp_price:,.0f}",
                    "ประเภท": "จุดอ้างอิงของคุณ",
                    "ขนาดพิกัด": 12,
                    "บริษัท": "จุดอ้างอิง"
                })

                # Found points (display all properties found within radius)
                map_nearby_df = nearby_df.sort_values("ระยะทาง (กม.)")
                for _, r in map_nearby_df.iterrows():
                    formatted_price = f"฿{r['ราคา']:,.0f}" if pd.notna(r['ราคา']) else "ไม่ระบุ"
                    map_points.append({
                        "ละติจูด": r["ละติจูด"],
                        "ลองจิจูด": r["ลองจิจูด"],
                        "ชื่อ": f"{r['ชื่อประกาศ']} ({formatted_price})",
                        "ราคา (บาท)": formatted_price,
                        "ประเภท": f"ทรัพย์ NPA ({r['บริษัท']})",
                        "ขนาดพิกัด": 8,
                        "บริษัท": r["บริษัท"]
                    })

                map_compare_df = pd.DataFrame(map_points)
                fig_compare = px.scatter_map(
                    map_compare_df,
                    lat="ละติจูด",
                    lon="ลองจิจูด",
                    color="บริษัท",
                    hover_name="ชื่อ",
                    hover_data={
                        "ราคา (บาท)": True,
                        "บริษัท": True,
                        "ละติจูด": False,
                        "ลองจิจูด": False
                    },
                    zoom=11.5,
                    height=680,
                    color_discrete_map={
                        "จุดอ้างอิง": "#ef4444",
                        "Baania": "#f59e0b",
                        "BAM": "#3b82f6",
                        "SAM": "#10b981",
                        "Livinginsider": "#84cc16",
                        "DDproperty": "#a855f7",
                        "Taladnudbaan": "#06b6d4",
                        "ZmyHome": "#ec4899"
                    },
                    template=plotly_template
                )
                # Set base marker styling for all points, then override the reference point to make it prominent
                fig_compare.update_traces(marker=dict(size=10, opacity=0.8))
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
                st.plotly_chart(style_plotly_fig(fig_compare), width="stretch", theme=None, config={"scrollZoom": True})

    with comp_sub_tab2:
        st.markdown("### ⚔️ เปรียบเทียบแบบ 1 ต่อ 1 (1-on-1 Asset Comparison)")
        st.write("เลือกทรัพย์สิน 2 รายการที่คุณสนใจเพื่อเปรียบเทียบรายละเอียดและราคาขายแบบเคียงข้างกัน")
        

        
        if df_raw is None or df_raw.empty:
            st.warning("⚠️ ไม่มีข้อมูลทรัพย์สินให้ทำการเปรียบเทียบ")
        else:
            col_comp_1, col_comp_2 = st.columns(2)
            
            # --- ASSET A SELECTOR ---
            with col_comp_1:
                st.markdown("<h5 style='color: #3b82f6;'><i class='fa fa-home'></i> ทรัพย์สินรายการที่ 1 (Asset A)</h5>", unsafe_allow_html=True)
                comp_a_co = st.selectbox(
                    "เลือกบริษัท (รายการที่ 1)",
                    options=sorted([str(c) for c in df_raw['บริษัท'].dropna().unique()]),
                    index=0,
                    key="oneone_co_a"
                )
                df_a_filtered = df_raw[df_raw['บริษัท'] == comp_a_co].copy()
                types_a = sorted([str(t) for t in df_a_filtered['ประเภททรัพย์'].dropna().unique()]) if not df_a_filtered.empty else []
                valid_types_a = ["ทั้งหมด"] + types_a
                sanitize_session_state("oneone_type_a", valid_types_a, "ทั้งหมด")
                comp_a_type = st.selectbox(
                    "เลือกประเภททรัพย์ (รายการที่ 1)",
                    options=valid_types_a,
                    index=0,
                    key="oneone_type_a"
                )
                
                df_a_subset = df_a_filtered.copy()
                if comp_a_type != "ทั้งหมด":
                    df_a_subset = df_a_subset[df_a_subset['ประเภททรัพย์'] == comp_a_type]
                    
                search_a = st.text_input(
                    "🔍 ค้นหารายการที่ 1 (ชื่อโครงการ, รหัสทรัพย์, ทำเล)",
                    value="",
                    placeholder="พิมพ์ชื่อโครงการ, รหัสทรัพย์, ทำเล...",
                    key="oneone_search_a"
                )
                
                if search_a:
                    q = search_a.strip().lower()
                    df_a_subset = df_a_subset[
                        df_a_subset['ชื่อประกาศ'].astype(str).str.lower().str.contains(q, na=False) |
                        df_a_subset['รหัสทรัพย์'].astype(str).str.lower().str.contains(q, na=False) |
                        df_a_subset['ชื่อโครงการ'].astype(str).str.lower().str.contains(q, na=False)
                    ]
                    
                if not df_a_subset.empty:
                    df_a_subset = df_a_subset.copy()
                    df_a_subset['label'] = (
                        df_a_subset['ชื่อประกาศ'].astype(str).str[:35] + " (" + 
                        df_a_subset['รหัสทรัพย์'].astype(str) + ") - ฿" + 
                        df_a_subset['ราคา'].map('{:,.0f}'.format)
                    )
                    df_a_subset = df_a_subset.drop_duplicates(subset=['label'])
                    display_a = df_a_subset.head(100)
                    
                    st.write(f"พบที่ตรงกัน {len(df_a_subset):,} รายการ แสดงผล 100 รายการแรก")
                    valid_labels_a = display_a['label'].tolist()
                    sanitize_session_state("oneone_sel_a", valid_labels_a)
                    sel_label_a = st.selectbox(
                        "ค้นหาและเลือกทรัพย์สินรายการที่ 1",
                        options=valid_labels_a,
                        index=0,
                        key="oneone_sel_a"
                    )
                    match_a = display_a[display_a['label'] == sel_label_a] if sel_label_a else None
                    asset_a = match_a.iloc[0] if match_a is not None and not match_a.empty else None
                else:
                    st.warning("⚠️ ไม่พบทรัพย์สินตามเงื่อนไขค้นหา")
                    asset_a = None
                    
            # --- ASSET B SELECTOR ---
            with col_comp_2:
                st.markdown("<h5 style='color: #ec4899;'><i class='fa fa-home'></i> ทรัพย์สินรายการที่ 2 (Asset B)</h5>", unsafe_allow_html=True)
                companies_list = sorted([str(c) for c in df_raw['บริษัท'].dropna().unique()])
                default_idx_b = 1 if len(companies_list) > 1 else 0
                comp_b_co = st.selectbox(
                    "เลือกบริษัท (รายการที่ 2)",
                    options=companies_list,
                    index=default_idx_b,
                    key="oneone_co_b"
                )
                df_b_filtered = df_raw[df_raw['บริษัท'] == comp_b_co].copy()
                types_b = sorted([str(t) for t in df_b_filtered['ประเภททรัพย์'].dropna().unique()]) if not df_b_filtered.empty else []
                valid_types_b = ["ทั้งหมด"] + types_b
                sanitize_session_state("oneone_type_b", valid_types_b, "ทั้งหมด")
                comp_b_type = st.selectbox(
                    "เลือกประเภททรัพย์ (รายการที่ 2)",
                    options=valid_types_b,
                    index=0,
                    key="oneone_type_b"
                )
                
                df_b_subset = df_b_filtered.copy()
                if comp_b_type != "ทั้งหมด":
                    df_b_subset = df_b_subset[df_b_subset['ประเภททรัพย์'] == comp_b_type]
                    
                search_b = st.text_input(
                    "🔍 ค้นหารายการที่ 2 (ชื่อโครงการ, รหัสทรัพย์, ทำเล)",
                    value="",
                    placeholder="พิมพ์ชื่อโครงการ, รหัสทรัพย์, ทำเล...",
                    key="oneone_search_b"
                )
                
                if search_b:
                    q = search_b.strip().lower()
                    df_b_subset = df_b_subset[
                        df_b_subset['ชื่อประกาศ'].astype(str).str.lower().str.contains(q, na=False) |
                        df_b_subset['รหัสทรัพย์'].astype(str).str.lower().str.contains(q, na=False) |
                        df_b_subset['ชื่อโครงการ'].astype(str).str.lower().str.contains(q, na=False)
                    ]
                    
                if not df_b_subset.empty:
                    df_b_subset = df_b_subset.copy()
                    df_b_subset['label'] = (
                        df_b_subset['ชื่อประกาศ'].astype(str).str[:35] + " (" + 
                        df_b_subset['รหัสทรัพย์'].astype(str) + ") - ฿" + 
                        df_b_subset['ราคา'].map('{:,.0f}'.format)
                    )
                    df_b_subset = df_b_subset.drop_duplicates(subset=['label'])
                    display_b = df_b_subset.head(100)
                    
                    st.write(f"พบที่ตรงกัน {len(df_b_subset):,} รายการ แสดงผล 100 รายการแรก")
                    valid_labels_b = display_b['label'].tolist()
                    sanitize_session_state("oneone_sel_b", valid_labels_b)
                    sel_label_b = st.selectbox(
                        "ค้นหาและเลือกทรัพย์สินรายการที่ 2",
                        options=valid_labels_b,
                        index=0,
                        key="oneone_sel_b"
                    )
                    match_b = display_b[display_b['label'] == sel_label_b] if sel_label_b else None
                    asset_b = match_b.iloc[0] if match_b is not None and not match_b.empty else None
                else:
                    st.warning("⚠️ ไม่พบทรัพย์สินตามเงื่อนไขค้นหา")
                    asset_b = None
            
            # --- COMPARISON OUTPUT ---
            if asset_a is not None and asset_b is not None:
                st.markdown("<br/><h4>📊 ผลการเปรียบเทียบแบบเคียงข้าง (Side-by-Side Comparison)</h4>", unsafe_allow_html=True)
                
                price_a = float(asset_a['ราคา']) if pd.notna(asset_a['ราคา']) else 0.0
                price_b = float(asset_b['ราคา']) if pd.notna(asset_b['ราคา']) else 0.0
                area_a = float(asset_a['พื้นที่ใช้สอย (ตร.ม.)']) if pd.notna(asset_a['พื้นที่ใช้สอย (ตร.ม.)']) else 0.0
                area_b = float(asset_b['พื้นที่ใช้สอย (ตร.ม.)']) if pd.notna(asset_b['พื้นที่ใช้สอย (ตร.ม.)']) else 0.0
                sqm_a = float(asset_a['ราคาต่อตารางเมตร']) if pd.notna(asset_a['ราคาต่อตารางเมตร']) else 0.0
                sqm_b = float(asset_b['ราคาต่อตารางเมตร']) if pd.notna(asset_b['ราคาต่อตารางเมตร']) else 0.0
                
                lat_a = float(asset_a['ละติจูด']) if pd.notna(asset_a['ละติจูด']) else None
                lat_b = float(asset_b['ละติจูด']) if pd.notna(asset_b['ละติจูด']) else None
                lng_a = float(asset_a['ลองจิจูด']) if pd.notna(asset_a['ลองจิจูด']) else None
                lng_b = float(asset_b['ลองจิจูด']) if pd.notna(asset_b['ลองจิจูด']) else None
                
                dist_km = haversine_distance(lat_a, lng_a, lat_b, lng_b) if (lat_a and lng_a and lat_b and lng_b) else None
                
                k_col1, k_col2, k_col3 = st.columns(3)
                
                # Metric 1: Price Deal
                with k_col1:
                    if price_a > 0 and price_b > 0:
                        if price_a < price_b:
                            diff = price_b - price_a
                            pct = (diff / price_b) * 100
                            st.metric("ดีลราคาประหยัดกว่า", f"{asset_a['บริษัท']}", f"-฿{diff:,.0f} (-{pct:.1f}%)")
                        elif price_b < price_a:
                            diff = price_a - price_b
                            pct = (diff / price_a) * 100
                            st.metric("ดีลราคาประหยัดกว่า", f"{asset_b['บริษัท']}", f"-฿{diff:,.0f} (-{pct:.1f}%)")
                        else:
                            st.metric("ดีลราคาประหยัดกว่า", "ราคาเท่ากัน", "0%")
                    else:
                        st.metric("ดีลราคาประหยัดกว่า", "N/A", "ไม่มีข้อมูลราคา")
                        
                # Metric 2: Price per Sq.M. Deal
                with k_col2:
                    if sqm_a > 0 and sqm_b > 0:
                        if sqm_a < sqm_b:
                            diff = sqm_b - sqm_a
                            pct = (diff / sqm_b) * 100
                            st.metric("ราคา ตร.ม. ประหยัดกว่า", f"{asset_a['บริษัท']}", f"-฿{diff:,.0f}/ตร.ม. (-{pct:.1f}%)")
                        elif sqm_b < sqm_a:
                            diff = sqm_a - sqm_b
                            pct = (diff / sqm_a) * 100
                            st.metric("ราคา ตร.ม. ประหยัดกว่า", f"{asset_b['บริษัท']}", f"-฿{diff:,.0f}/ตร.ม. (-{pct:.1f}%)")
                        else:
                            st.metric("ราคา ตร.ม.", "เฉลี่ยเท่ากัน", "0%")
                    else:
                        st.metric("ราคา ตร.ม.", "N/A", "ไม่มีข้อมูล")
                        
                # Metric 3: Distance
                with k_col3:
                    if dist_km is not None:
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
                
                # Render the table (uses dynamic borders, backgrounds, and text colors)
                comp_table_html = f"""
                <div style="overflow-x: auto;">
                    <table style="width:100%; border-collapse: collapse; font-family: 'Sarabun', sans-serif; font-size: 0.9rem; margin-top: 15px; border: 1px solid var(--card-border); border-radius: 8px; color: var(--card-text);">
                        <thead>
                            <tr style="background-color: var(--sidebar-bg); border-bottom: 2px solid var(--card-border);">
                                <th style="padding: 12px; text-align: left; color: var(--card-subtext); width: 20%; border-right: 1px solid var(--card-border);">รายละเอียด</th>
                                <th style="padding: 12px; text-align: center; color: #3b82f6; width: 40%; font-weight: 700; border-right: 1px solid var(--card-border);">🏠 ทรัพย์สิน A ({asset_a['บริษัท']})</th>
                                <th style="padding: 12px; text-align: center; color: #ec4899; width: 40%; font-weight: 700;">🏠 ทรัพย์สิน B ({asset_b['บริษัท']})</th>
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
                                <td style="padding: 10px; font-weight: 600; color: var(--card-subtext); border-right: 1px solid var(--card-border);">พื้นที่ดิน (ไร่-งาน-วา)</td>
                                <td style="padding: 10px; text-align: center; color: var(--card-subtext); border-right: 1px solid var(--card-border);">{asset_a['พื้นที่ (ไร่-งาน-วา)'] if asset_a['พื้นที่ (ไร่-งาน-วา)'] else '-'}</td>
                                <td style="padding: 10px; text-align: center; color: var(--card-subtext);">{asset_b['พื้นที่ (ไร่-งาน-วา)'] if asset_b['พื้นที่ (ไร่-งาน-วา)'] else '-'}</td>
                            </tr>
                            <tr style="border-bottom: 1px solid var(--card-border);">
                                <td style="padding: 10px; font-weight: 600; color: var(--card-subtext); border-right: 1px solid var(--card-border);">พื้นที่ใช้สอย (ตร.ม.)</td>
                                <td style="padding: 10px; text-align: center; border-right: 1px solid var(--card-border);">{get_val_styled(area_a, area_b, is_area=True, reverse=True)}</td>
                                <td style="padding: 10px; text-align: center;">{get_val_styled(area_b, area_a, is_area=True, reverse=True)}</td>
                            </tr>
                            <tr style="border-bottom: 1px solid var(--card-border); background-color: var(--hover-bg);">
                                <td style="padding: 10px; font-weight: 600; color: var(--card-subtext); border-right: 1px solid var(--card-border);">ราคาเฉลี่ยต่อ ตร.ม.</td>
                                <td style="padding: 10px; text-align: center; border-right: 1px solid var(--card-border);">{get_val_styled(sqm_a, sqm_b, is_price=True)}</td>
                                <td style="padding: 10px; text-align: center;">{get_val_styled(sqm_b, sqm_a, is_price=True)}</td>
                            </tr>
                            <tr style="border-bottom: 1px solid var(--card-border);">
                                <td style="padding: 10px; font-weight: 600; color: var(--card-subtext); border-right: 1px solid var(--card-border);">รายละเอียดห้อง</td>
                                <td style="padding: 10px; text-align: center; color: var(--card-subtext); border-right: 1px solid var(--card-border);">🛏️ {asset_a.get('ห้องนอน', '-')} นอน | 🚿 {asset_a.get('ห้องน้ำ', '-')} น้ำ | 🚗 {asset_a.get('ที่จอดรถ', '-')} จอด</td>
                                <td style="padding: 10px; text-align: center; color: var(--card-subtext);">🛏️ {asset_b.get('ห้องนอน', '-')} นอน | 🚿 {asset_b.get('ห้องน้ำ', '-')} น้ำ | 🚗 {asset_b.get('ที่จอดรถ', '-')} จอด</td>
                            </tr>
                            <tr style="border-bottom: 1px solid var(--card-border);">
                                <td style="padding: 10px; font-weight: 600; color: var(--card-subtext); border-right: 1px solid var(--card-border);">ลิงก์รายละเอียด</td>
                                <td style="padding: 10px; text-align: center; border-right: 1px solid var(--card-border);">
                                    {'<a href="' + asset_a['ลิงก์'] + '" target="_blank" style="color: #3b82f6; text-decoration: none; font-weight: 600;"><i class="fa fa-external-link-alt"></i> เปิดหน้าประกาศ</a>' if asset_a['ลิงก์'].startswith('http') else '<span style="color:#94a3b8;">ไม่มีลิงก์</span>'}
                                </td>
                                <td style="padding: 10px; text-align: center;">
                                    {'<a href="' + asset_b['ลิงก์'] + '" target="_blank" style="color: #ec4899; text-decoration: none; font-weight: 600;"><i class="fa fa-external-link-alt"></i> เปิดหน้าประกาศ</a>' if asset_b['ลิงก์'].startswith('http') else '<span style="color:#94a3b8;">ไม่มีลิงก์</span>'}
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
                    
                    fig_oneone_map = px.scatter_mapbox(
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
                            go.Scattermapbox(
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
                        mapbox_style=mapbox_style,
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
            # Calculate Statistics
            median_val = float(analysis_df[unit_col].median())
            mean_val = float(analysis_df[unit_col].mean())
            std_val = float(analysis_df[unit_col].std())
            min_val = float(analysis_df[unit_col].min())
            max_val = float(analysis_df[unit_col].max())
            
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
                <div class="metric-value">{len(analysis_df)}</div>
                <div class="metric-sub">รายการในทำเลนี้</div>
            </div>
            """, unsafe_allow_html=True)
            
            st.markdown("<br/>", unsafe_allow_html=True)
            
            # Display Layout: Box Plot and AMC vs Portal average price
            col_graph1, col_graph2 = st.columns(2)
            
            with col_graph1:
                # Box Plot
                fig_box = px.box(
                    analysis_df,
                    y=unit_col,
                    color='บริษัท',
                    points="all",
                    hover_data=['ชื่อประกาศ_สะอาด', 'รหัสทรัพย์', 'ราคา'],
                    title=f'แผนภูมิการกระจายตัวราคาต่อ{unit_label} (Box Plot)',
                    color_discrete_map={"Baania": "#f59e0b", "BAM": "#3b82f6", "SAM": "#10b981", "Livinginsider": "#84cc16", "DDproperty": "#a855f7", "Taladnudbaan": "#06b6d4", "ZmyHome": "#ec4899"},
                    template=plotly_template
                )
                fig_box.update_layout(title_font=dict(size=14, family="Outfit"), yaxis_title=f"ราคา (บาท / {unit_label})")
                st.plotly_chart(style_plotly_fig(fig_box), width="stretch", theme=None)
                
            with col_graph2:
                # AMC vs Portal average price comparison
                amc_portal_group = analysis_df.groupby('บริษัท')[unit_col].mean().reset_index()
                fig_amc_vs_portal = px.bar(
                    amc_portal_group,
                    x='บริษัท',
                    y=unit_col,
                    color='บริษัท',
                    title=f'ราคาเฉลี่ยต่อ{unit_label} เปรียบเทียบ AMC vs พอร์ทัลทั่วไป',
                    color_discrete_map={"Baania": "#f59e0b", "BAM": "#3b82f6", "SAM": "#10b981", "Livinginsider": "#84cc16", "DDproperty": "#a855f7", "Taladnudbaan": "#06b6d4", "ZmyHome": "#ec4899"},
                    template=plotly_template
                )
                fig_amc_vs_portal.update_layout(title_font=dict(size=14, family="Outfit"), yaxis_title=f"ราคาเฉลี่ย (บาท / {unit_label})")
                st.plotly_chart(style_plotly_fig(fig_amc_vs_portal), width="stretch", theme=None)
                
            # Underpriced Assets Finder
            st.markdown("#### 💎 ทรัพย์สินที่ราคาต่อหน่วยคุ้มค่าที่สุด (ส่วนลดสูงสุดเทียบกับราคากลางทำเล)")
            st.write(f"แสดงรายการทรัพย์สินที่มีราคาต่อ{unit_label} ต่ำกว่าราคาเฉลี่ยกลาง (Median) ของพื้นที่ ซึ่งคิดเป็นดีลสุดคุ้มในการลงทุน")
            
            # Calculate discount from median
            analysis_df['ส่วนต่างจากราคากลาง (%)'] = ((analysis_df[unit_col] - median_val) / median_val) * 100.0
            
            # Sort by lowest unit price (or most negative deviation)
            bargain_df = analysis_df.sort_values(by=unit_col)
            
            # Format and show columns
            bargain_display = bargain_df[[
                'บริษัท', 'รหัสทรัพย์', 'ชื่อประกาศ_สะอาด', 'ราคา', unit_col, 'ส่วนต่างจากราคากลาง (%)', 
                'จังหวัด', 'อำเภอ', 'ตำบล', 'พื้นที่ (ไร่-งาน-วา)', 'พื้นที่ใช้สอย (ตร.ม.)', 'ลิงก์_สะอาด'
            ]].copy()
            
            st.dataframe(
                bargain_display,
                width="stretch",
                column_config={
                    "ราคา": st.column_config.NumberColumn("ราคาเสนอขาย (บาท)", format="%d"),
                    unit_col: st.column_config.NumberColumn(f"ราคา/หน่วย (บาท/{unit_short})", format="%.0f"),
                    "ส่วนต่างจากราคากลาง (%)": st.column_config.NumberColumn("เทียบราคากลาง (%)", format="%+.1f%%"),
                    "พื้นที่ใช้สอย (ตร.ม.)": st.column_config.NumberColumn("พื้นที่ใช้สอย (ตร.ม.)", format="%.1f"),
                    "ลิงก์_สะอาด": st.column_config.LinkColumn("ลิงก์ประกาศ")
                }
            )

