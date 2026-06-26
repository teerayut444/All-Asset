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

# Haversine distance calculation (km)
def haversine_distance(lat1, lon1, lat2, lon2):
    R = 6371  # Earth radius in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def find_nearby_properties(input_lat, input_lon, df_all, radius_km, match_type=None, company=None):
    """Find properties within radius_km of the given coordinates."""
    results = []
    for _, row in df_all.iterrows():
        lat = row.get('ละติจูด')
        lon = row.get('ลองจิจูด')
        if pd.isna(lat) or pd.isna(lon):
            continue
        # Filter by company
        if company and row.get('บริษัท') != company:
            continue
        # Filter by property type
        if match_type and str(match_type).strip() != '' and str(match_type).lower() != 'nan':
            if str(row.get('ประเภททรัพย์', '')).strip() != str(match_type).strip():
                continue
        dist = haversine_distance(input_lat, input_lon, float(lat), float(lon))
        if dist <= radius_km:
            result_row = row.to_dict()
            result_row['ระยะทาง (กม.)'] = round(dist, 2)
            results.append(result_row)
    return pd.DataFrame(results)

# Configure Streamlit page layout
st.set_page_config(
    page_title="All Asset NPA Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

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

# Cached function to load data from excel
@st.cache_data(ttl=60)
def load_properties_data():
    excel_file = Path("all_assets.xlsx")
    if not excel_file.exists():
        return None
        
    try:
        # Load excel file
        df = pd.read_excel(excel_file)
        
        # Replace undefined values with NaN
        df = df.replace(["$undefined", "undefined", "nan", "NaN", "NAN"], np.nan)
        
        # Clean coordinates
        df['ละติจูด'] = pd.to_numeric(df['ละติจูด'], errors='coerce')
        df['ลองจิจูด'] = pd.to_numeric(df['ลองจิจูด'], errors='coerce')
        
        # Clean prices
        df['ราคา'] = pd.to_numeric(df['ราคา'], errors='coerce')
        
        # Fill NaN values in essential text columns
        df['รหัสทรัพย์'] = df['รหัสทรัพย์'].fillna("-").astype(str).str.strip()
        df['ประเภททรัพย์'] = df['ประเภททรัพย์'].fillna("อื่นๆ").astype(str).str.strip()
        df['จังหวัด'] = df['จังหวัด'].fillna("ไม่ระบุ").astype(str).str.strip()
        df['ตำบล'] = df['ตำบล'].fillna("").astype(str).str.strip()
        df['อำเภอ'] = df['อำเภอ'].fillna("").astype(str).str.strip()
        df['ชื่อโครงการ'] = df['ชื่อโครงการ'].fillna("").astype(str).str.strip()
        df['ประเภทการขาย'] = df['ประเภทการขาย'].fillna("").astype(str).str.strip()
        df['พื้นที่ (ไร่-งาน-วา)'] = df['พื้นที่ (ไร่-งาน-วา)'].fillna("").astype(str).str.strip()
        df['วันที่ดึงข้อมูล'] = df['วันที่ดึงข้อมูล'].fillna("").astype(str).str.strip()
        
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
        
        # จัดกลุ่มประเภททรัพย์สินให้เรียบง่ายและเป็นระบบ
        def simplify_type(val):
            v = str(val).strip()
            if any(k in v for k in ["คอนโด", "Condo", "ห้องชุด", "อพาร์ทเม้นท์", "Apartment"]):
                return "คอนโดมิเนียม"
            if any(k in v for k in ["บ้าน", "ทาวน์", "Town", "อาคารแฝด", "ตึกแถว", "โฮม"]):
                return "บ้านเดี่ยว / ทาวน์โฮม"
            if any(k in v for k in ["ที่ดิน", "เกษตร", "สวน", "ไร่"]):
                return "ที่ดินเปล่า / การเกษตร"
            if any(k in v for k in ["สำนักงาน", "Office", "โรงแรม", "รีสอร์ท", "พาณิชย์", "อาคารพาณิชย์"]):
                return "พาณิชย์ / สำนักงาน"
            if any(k in v for k in ["โรงงาน", "โกดัง", "คลังสินค้า", "Factory", "Warehouse"]):
                return "โรงงาน / โกดัง"
            return "อื่นๆ"
            
        df['ประเภททรัพย์_กลุ่ม'] = df['ประเภททรัพย์'].apply(simplify_type)
        
        # Clean titles dynamically
        df['ชื่อประกาศ_สะอาด'] = df['ชื่อประกาศ'].apply(get_clean_title)
        df['ลิงก์_สะอาด'] = df['ลิงก์'].apply(get_clean_link)
        
        return df
    except Exception as e:
        st.error(f"เกิดข้อผิดพลาดในการโหลดไฟล์ Excel: {e}")
        return None
        
    try:
        # Load excel file
        df = pd.read_excel(excel_file)
        
        # Replace undefined values with NaN
        df = df.replace(["$undefined", "undefined", "nan", "NaN", "NAN"], np.nan)
        
        # Clean coordinates
        df['ละติจูด'] = pd.to_numeric(df['ละติจูด'], errors='coerce')
        df['ลองจิจูด'] = pd.to_numeric(df['ลองจิจูด'], errors='coerce')
        
        # Clean prices
        df['ราคา'] = pd.to_numeric(df['ราคา'], errors='coerce')
        
        # Fill NaN values in essential text columns
        df['รหัสทรัพย์'] = df['รหัสทรัพย์'].fillna("-").astype(str)
        df['ประเภททรัพย์'] = df['ประเภททรัพย์'].fillna("อื่นๆ").astype(str)
        df['จังหวัด'] = df['จังหวัด'].fillna("ไม่ระบุ").astype(str)
        df['ตำบล'] = df['ตำบล'].fillna("").astype(str)
        df['อำเภอ'] = df['อำเภอ'].fillna("").astype(str)
        df['ชื่อโครงการ'] = df['ชื่อโครงการ'].fillna("").astype(str)
        df['ประเภทการขาย'] = df['ประเภทการขาย'].fillna("").astype(str)
        df['พื้นที่ (ไร่-งาน-วา)'] = df['พื้นที่ (ไร่-งาน-วา)'].fillna("").astype(str)
        df['วันที่ดึงข้อมูล'] = df['วันที่ดึงข้อมูล'].fillna("").astype(str)
        
        # Clean titles dynamically
        df['ชื่อประกาศ_สะอาด'] = df['ชื่อประกาศ'].apply(get_clean_title)
        df['ลิงก์_สะอาด'] = df['ลิงก์'].apply(get_clean_link)
        
        return df
    except Exception as e:
        st.error(f"เกิดข้อผิดพลาดในการโหลดไฟล์ Excel: {e}")
        return None

# Load the properties data
df_raw = load_properties_data()

# ----------------- SIDEBAR -----------------
with st.sidebar:
    st.markdown('<h2 style="color: #6366f1;"><i class="fa fa-home"></i> All Asset NPA</h2>', unsafe_allow_html=True)
    st.markdown("---")
    
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
        
        # Company Filter (Formal Checkboxes)
        st.markdown("<p style='font-weight: 600; margin-top: 10px; margin-bottom: 2px; color: #0f172a;'>บริษัททรัพย์สิน</p>", unsafe_allow_html=True)
        c_baania = st.checkbox("Baania", value=True, key="filter_baania")
        c_bam = st.checkbox("BAM", value=True, key="filter_bam")
        c_zmyhome = st.checkbox("ZmyHome", value=True, key="filter_zmyhome")
        
        selected_companies = []
        if c_baania: selected_companies.append("Baania")
        if c_bam: selected_companies.append("BAM")
        if c_zmyhome: selected_companies.append("ZmyHome")
        
        if not selected_companies:
            selected_companies = ["Baania", "BAM", "ZmyHome"]
        
        # Property Type Filter
        if selected_companies:
            df_by_company = df_raw[df_raw['บริษัท'].isin(selected_companies)]
        else:
            df_by_company = df_raw
            
        unique_types = sorted(df_by_company['ประเภททรัพย์_กลุ่ม'].unique().tolist())
        selected_types = st.pills(
            "ประเภททรัพย์สิน", 
            options=unique_types, 
            selection_mode="multi", 
            default=None
        )
        
        # Province Filter
        unique_provinces = sorted(df_by_company['จังหวัด'].unique().tolist())
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
        unique_districts_formatted = sorted([
            f"{row['อำเภอ']} ({row['จังหวัด']})" 
            for _, row in dist_df.iterrows()
        ])
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
        unique_subdistricts_formatted = sorted([
            f"{row['ตำบล']} ({row['อำเภอ']}, {row['จังหวัด']})"
            for _, row in sub_df.iterrows()
        ])
        selected_subdistricts_formatted = st.multiselect("ตำบล / แขวง", options=unique_subdistricts_formatted, default=[])
        
        # Price Filter
        valid_prices = df_by_company['ราคา'].dropna()
        if not valid_prices.empty:
            min_price_val = float(valid_prices.min())
            max_price_val = float(valid_prices.max())
            
            price_range = st.slider(
                "ช่วงราคาขาย (บาท)",
                min_value=min_price_val,
                max_value=max_price_val,
                value=(min_price_val, max_price_val),
                format="%d"
            )
        else:
            price_range = (0.0, 1000000000.0)
    else:
        st.warning("ไม่มีตัวกรองข้อมูลเนื่องจากยังไม่มีไฟล์ข้อมูล all_assets.xlsx")

# Global CSS Inject for modern UI aesthetics and light theme enforcement
st.html("""<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
<style>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=Sarabun:wght@300;400;500;600;700&display=swap');

html, body, [data-testid="stSidebar"], .stApp {
    font-family: 'Outfit', 'Sarabun', sans-serif;
}

/* Force the main app to fit exactly within the viewport and hide main scrollbars */
html, body, .stApp, div[data-testid="stAppViewContainer"] {
    overflow: hidden !important;
    height: 100vh !important;
}

body, .stApp {
    background-color: #ffffff !important;
    color: #0f172a !important;
}

/* Make right panel container borderless and full-screen under the header */
div[data-testid="stAppViewBlockContainer"],
.main .block-container,
.block-container {
    padding-top: 55px !important; /* To prevent header from covering the tabs! */
    padding-bottom: 0px !important;
    padding-left: 0px !important;
    padding-right: 0px !important;
    margin-top: 0px !important;
    margin-bottom: 0px !important;
    margin-left: 0px !important;
    margin-right: 0px !important;
    max-width: 100% !important;
    height: calc(100vh - 55px) !important;
    position: relative !important;
    overflow: hidden !important; /* Prevent page scrolling */
}

.main {
    position: relative !important;
}

/* Sidebar styling */
section[data-testid="stSidebar"] {
    background-color: #f8fafc !important;
    border-right: 1px solid #e2e8f0 !important;
}

header[data-testid="stHeader"] {
    background-color: #ffffff !important;
    border-bottom: 1px solid #e2e8f0 !important;
    height: 55px !important;
}

/* Force light theme colors on all input widgets in sidebar */
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] span,
section[data-testid="stSidebar"] h1,
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3 {
    color: #0f172a !important;
}

/* BaseWeb Select dropdowns and input boxes */
section[data-testid="stSidebar"] div[data-baseweb="select"] > div {
    background-color: #ffffff !important;
    border: 1px solid #cbd5e1 !important;
    border-radius: 8px !important;
}

section[data-testid="stSidebar"] div[data-baseweb="select"] div,
section[data-testid="stSidebar"] div[data-baseweb="select"] span,
section[data-testid="stSidebar"] div[data-baseweb="select"] input {
    color: #0f172a !important;
    -webkit-text-fill-color: #0f172a !important;
}

/* Multiselect selected items (chips/tags) override */
span[data-baseweb="tag"] {
    background-color: #f1f5f9 !important;
    border: 1px solid #cbd5e1 !important;
    border-radius: 6px !important;
}

span[data-baseweb="tag"] span {
    color: #0f172a !important;
    background-color: transparent !important;
}

span[data-baseweb="tag"] svg {
    fill: #64748b !important;
}

/* Dropdown listbox items (when expanding dropdown) */
div[role="listbox"], ul[role="listbox"], div[data-baseweb="menu"] {
    background-color: #ffffff !important;
    border: 1px solid #e2e8f0 !important;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08) !important;
}

div[role="listbox"] div, ul[role="listbox"] li, div[data-baseweb="menu"] div {
    background-color: #ffffff !important;
    color: #0f172a !important;
}

div[role="option"]:hover, li[role="option"]:hover, div[data-baseweb="menu"] div:hover {
    background-color: #f1f5f9 !important;
    color: #0f172a !important;
}

/* Text Input styling */
div[data-testid="stTextInput"] input {
    background-color: #ffffff !important;
    color: #0f172a !important;
    border: 1px solid #cbd5e1 !important;
    border-radius: 8px !important;
}

div[data-testid="stTextInput"] label p {
    color: #0f172a !important;
}

/* Slider values styling */
div[data-testid="stSlider"] div,
div[data-testid="stSlider"] span,
div[data-testid="stSlider"] p {
    color: #0f172a !important;
}

/* Toggle (Checkbox/Switch) label styling */
div[data-testid="stCheckbox"] label span,
div[data-testid="stCheckbox"] label p,
div[data-testid="stToggle"] label span,
div[data-testid="stToggle"] label p {
    color: #0f172a !important;
}

/* Custom st.pills styling to look ultra premium with selection state support */
div[data-testid="stPills"] {
    gap: 8px !important;
    padding-top: 4px !important;
}
div[data-testid="stPills"] button {
    background-color: #ffffff !important;
    color: #475569 !important;
    border: 1px solid #cbd5e1 !important;
    border-radius: 20px !important;
    padding: 4px 14px !important;
    font-size: 0.82rem !important;
    font-weight: 500 !important;
    transition: all 0.2s ease !important;
}
div[data-testid="stPills"] button:hover {
    border-color: #6366f1 !important;
    color: #6366f1 !important;
    background-color: #f5f3ff !important;
}
/* Style all possible states of a selected pill button in Streamlit */
div[data-testid="stPills"] button[aria-checked="true"],
div[data-testid="stPills"] button[aria-pressed="true"],
div[data-testid="stPills"] button[data-selected="true"],
div[data-testid="stPills"] button[aria-selected="true"] {
    background-color: #6366f1 !important;
    color: #ffffff !important;
    border-color: #6366f1 !important;
    box-shadow: 0 4px 12px rgba(99, 102, 241, 0.2) !important;
}

/* Metrics panel styling with high-tech glassmorphic hover glows */
.metric-card {
    background: #ffffff !important;
    border: 1px solid #e2e8f0 !important;
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
    background: rgba(255, 255, 255, 0.98) !important;
}
.metric-title {
    font-size: 0.85rem;
    color: #64748b !important;
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
    color: #64748b !important;
    margin-top: 6px;
    font-weight: 500;
}

/* Style the tab container to sit at the top and fit height */
div[data-baseweb="tab-list"] {
    margin-top: 0px !important;
    padding-top: 5px !important;
    padding-bottom: 5px !important;
    padding-left: 20px !important;
    background-color: #ffffff !important;
    border-bottom: 1px solid #e2e8f0 !important;
    z-index: 1000 !important;
}

button[data-baseweb="tab"] p {
    color: #64748b !important;
    font-weight: 600;
    font-size: 0.95rem;
}
button[data-baseweb="tab"][aria-selected="true"] {
    border-bottom-color: #6366f1 !important;
}
button[data-baseweb="tab"][aria-selected="true"] p {
    color: #6366f1 !important;
}

/* Tab Panel content area should fill the remaining height and scroll independently */
div[data-baseweb="tab-panel"] {
    position: relative !important;
    height: calc(100vh - 100px) !important;
    overflow-y: auto !important; /* Independent vertical scrollbar for other tabs */
    padding-top: 0px !important;
    padding-left: 0px !important;
    padding-right: 0px !important;
}

/* Map tab panel (first tab) should not have scrollbars at all */
div[data-baseweb="tab-panel"]:has(.st-key-tab_map) {
    overflow: hidden !important;
}

.st-key-tab_map {
    overflow: hidden !important;
    height: 100% !important;
    display: flex !important;
    flex-direction: column !important;
}

.floating-kpi-container {
    position: relative !important; /* Made KPI cards static instead of floating over map */
    margin: 15px 20px 5px 20px !important;
    z-index: 999;
    display: flex;
    gap: 12px;
}

.floating-card {
    background: rgba(255, 255, 255, 0.85) !important;
    backdrop-filter: blur(12px) !important;
    -webkit-backdrop-filter: blur(12px) !important;
    border: 1px solid rgba(226, 232, 240, 0.8) !important;
    border-radius: 14px !important;
    padding: 12px 18px !important;
    box-shadow: 0 10px 30px rgba(15, 23, 42, 0.05) !important;
    flex: 1;
    transition: transform 0.2s ease, background-color 0.2s ease, border-color 0.2s ease;
}

.floating-card:hover {
    transform: translateY(-2px);
    background: rgba(255, 255, 255, 0.95) !important;
    border-color: rgba(99, 102, 241, 0.4) !important;
    box-shadow: 0 12px 30px rgba(99, 102, 241, 0.15), 0 2px 10px rgba(6, 182, 212, 0.1) !important;
}

.floating-card-title {
    font-size: 0.72rem;
    color: #64748b !important;
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
    color: #64748b !important;
    margin-top: 2px;
    font-weight: 500;
}

/* Map chart container styling specifically in map tab to sit below static KPI cards */
div[data-baseweb="tab-panel"]:has(.floating-kpi-container) .stPlotlyChart, 
div[data-baseweb="tab-panel"]:has(.floating-kpi-container) .stPlotlyChart > div, 
div[data-baseweb="tab-panel"]:has(.floating-kpi-container) .stPlotlyChart .js-plotly-plot, 
div[data-baseweb="tab-panel"]:has(.floating-kpi-container) .stPlotlyChart .plotly {
    margin-top: 0px !important;
    padding-top: 0px !important;
    height: calc(100vh - 215px) !important;
    width: 100% !important;
}

#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
</style>""")

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
        df_filtered['ชื่อประกาศ_สะอาด'].str.contains(search_pattern, case=False, na=False) |
        df_filtered['รหัสทรัพย์'].str.contains(search_pattern, case=False, na=False) |
        df_filtered['ชื่อโครงการ'].str.contains(search_pattern, case=False, na=False) |
        df_filtered['จังหวัด'].str.contains(search_pattern, case=False, na=False)
    ]

# 2. Company
if selected_companies:
    df_filtered = df_filtered[df_filtered['บริษัท'].isin(selected_companies)]

# 3. Property Types
if selected_types:
    df_filtered = df_filtered[df_filtered['ประเภททรัพย์_กลุ่ม'].isin(selected_types)]

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

# 7. Price Range
if not valid_prices.empty:
    df_filtered = df_filtered[
        (df_filtered['ราคา'].isna()) | 
        ((df_filtered['ราคา'] >= price_range[0]) & (df_filtered['ราคา'] <= price_range[1]))
    ]

# ----------------- KPI METRICS RENDERING -----------------
total_count = len(df_filtered)
total_value = df_filtered['ราคา'].sum() / 1e6  # Convert to Million Baht
avg_price = df_filtered['ราคา'].mean() / 1e6 if total_count > 0 else 0  # Million Baht

# Count by company in filtered set
baania_count = len(df_filtered[df_filtered['บริษัท'] == 'Baania'])
bam_count = len(df_filtered[df_filtered['บริษัท'] == 'BAM'])
zmyhome_count = len(df_filtered[df_filtered['บริษัท'] == 'ZmyHome'])

# ----------------- TABS CREATION -----------------
tab1, tab2, tab3, tab4 = st.tabs([
    "🗺️ แผนที่พิกัดทรัพย์ (Map Grid)", 
    "📈 สถิติ & วิเคราะห์ (Analytics)", 
    "📋 รายการทรัพย์สิน (Property Listing)", 
    "🔍 เปรียบเทียบตำแหน่ง (Comparison)"
])

# ----- TAB 1: MAP GRID -----
with tab1:
    with st.container(key="tab_map"):
        # Filter rows with coordinates
        map_data = df_filtered[df_filtered['ละติจูด'].notna() & df_filtered['ลองจิจูด'].notna()].copy()
        
        if map_data.empty:
            st.warning("⚠️ ไม่พบพิกัดตำแหน่ง ละติจูด/ลองจิจูด ในรายการทรัพย์สินที่คุณเลือกค้นหา")
        else:
            # Glassmorphic Floating KPI UI Overlay (positioned absolute over the map)
            total_count_str = f"{total_count:,.0f}"
            total_value_str = f"฿{total_value:,.2f}M"
            avg_price_str = f"฿{avg_price:,.2f}M"
            
            # Max price display
            valid_prices_filtered = df_filtered['ราคา'].dropna()
            max_price = valid_prices_filtered.max() / 1e6 if not valid_prices_filtered.empty else 0
            max_price_str = f"฿{max_price:,.2f}M"
            
            floating_kpi_html = f"""
            <div class="floating-kpi-container">
                <div class="floating-card">
                    <div class="floating-card-title"><i class="fa fa-list" style="color: #6366f1;"></i> ทรัพย์สินที่พบ</div>
                    <div class="floating-card-value">{total_count_str}</div>
                    <div class="floating-card-sub">Baania: {baania_count:,} | BAM: {bam_count:,} | ZmyHome: {zmyhome_count:,}</div>
                </div>
                <div class="floating-card">
                    <div class="floating-card-title"><i class="fa fa-wallet" style="color: #06b6d4;"></i> มูลค่ารวมทรัพย์สิน</div>
                    <div class="floating-card-value">{total_value_str}</div>
                    <div class="floating-card-sub">เฉพาะที่ระบุราคา (ล้านบาท)</div>
                </div>
                <div class="floating-card">
                    <div class="floating-card-title"><i class="fa fa-tags" style="color: #10b981;"></i> ราคาเฉลี่ย</div>
                    <div class="floating-card-value">{avg_price_str}</div>
                    <div class="floating-card-sub">ล้านบาท / ทรัพย์สิน</div>
                </div>
                <div class="floating-card">
                    <div class="floating-card-title"><i class="fa fa-arrow-up" style="color: #f59e0b;"></i> ราคาสูงสุด</div>
                    <div class="floating-card-value">{max_price_str}</div>
                    <div class="floating-card-sub">มูลค่าสูงสุดในผลตัวกรอง</div>
                </div>
            </div>
            """
            st.markdown(floating_kpi_html, unsafe_allow_html=True)
            
            # Create map
            fig_map = px.scatter_mapbox(
                map_data,
                lat="ละติจูด",
                lon="ลองจิจูด",
                color="บริษัท",
                hover_name="ชื่อประกาศ_สะอาด",
                hover_data={
                    "รหัสทรัพย์": True,
                    "ราคา": ":,.0f",
                    "จังหวัด": True,
                    "ประเภททรัพย์": True,
                    "บริษัท": False,
                    "ละติจูด": False,
                    "ลองจิจูด": False
                },
                zoom=5.5,
                height=750,
                color_discrete_map={"Baania": "#f59e0b", "BAM": "#3b82f6", "ZmyHome": "#ec4899"},
                template=plotly_template
            )
            
            fig_map.update_layout(
                mapbox_style=mapbox_style,
                margin={"r": 0, "t": 0, "l": 0, "b": 0},
                paper_bgcolor="rgba(0,0,0,0)",
                legend=dict(
                    yanchor="top",
                    y=0.99,
                    xanchor="left",
                    x=0.01,
                    bgcolor="rgba(255, 255, 255, 0.9)",
                    bordercolor="rgba(0, 0, 0, 0.08)",
                    borderwidth=1,
                    font=dict(color="#1f2937", size=12)
                )
            )
            st.plotly_chart(fig_map, use_container_width=True, theme=None, config={"scrollZoom": True})

# ----- TAB 2: ANALYTICS -----
with tab2:
    st.markdown("### 📈 แผนภูมิเปรียบเทียบข้อมูลสถิติของ 3 บริษัท")
    
    if df_filtered.empty:
        st.warning("⚠️ ไม่มีข้อมูลสำหรับจัดทำแผนภูมิวิเคราะห์สถิติ")
    else:
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
                color_discrete_map={"Baania": "#f59e0b", "BAM": "#3b82f6", "ZmyHome": "#ec4899"},
                template=plotly_template
            )
            fig_comp.update_layout(title_font=dict(size=15, family="Outfit"))
            st.plotly_chart(fig_comp, use_container_width=True)
            
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
            fig_type.update_layout(title_font=dict(size=15, family="Outfit"))
            st.plotly_chart(fig_type, use_container_width=True)
            
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
                color_discrete_map={"Baania": "#f59e0b", "BAM": "#3b82f6", "ZmyHome": "#ec4899"},
                template=plotly_template
            )
            fig_avg_p.update_layout(title_font=dict(size=15, family="Outfit"))
            st.plotly_chart(fig_avg_p, use_container_width=True)
            
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
            fig_prov.update_layout(title_font=dict(size=15, family="Outfit"), coloraxis_showscale=False)
            st.plotly_chart(fig_prov, use_container_width=True)

# ----- TAB 3: PROPERTY LISTING -----
with tab3:
    st.markdown(f"### 📋 รายการทรัพยสินที่ค้นพบ ({total_count:,} รายการ)")
    
    if df_filtered.empty:
        st.warning("⚠️ ไม่พบข้อมูลตามเงื่อนไข")
    else:
        # Dataframe
        st.dataframe(
            df_filtered[[
                "บริษัท", "รหัสทรัพย์", "ชื่อโครงการ", "ชื่อประกาศ_สะอาด", "ประเภททรัพย์", 
                "ประเภทการขาย", "ราคา", "จังหวัด", "อำเภอ", "ตำบล",
                "พื้นที่ (ไร่-งาน-วา)", "พื้นที่ใช้สอย (ตร.ม.)", "ห้องนอน", "ห้องน้ำ", "ที่จอดรถ", "วันที่ดึงข้อมูล"
            ]],
            use_container_width=True,
            column_config={
                "ราคา": st.column_config.NumberColumn("ราคาขาย (บาท)", format="%d"),
                "พื้นที่ใช้สอย (ตร.ม.)": st.column_config.NumberColumn(format="%.1f")
            }
        )
        
        st.markdown("<br/><h4>💡 การแสดงผลแบบการ์ดรายละเอียดทรัพย์สิน (Card view)</h4>", unsafe_allow_html=True)
        
        # Pagination
        cards_per_page = 9
        total_pages = (total_count - 1) // cards_per_page + 1
        
        # Navigation
        nav_c1, nav_c2, nav_c3 = st.columns([2, 1, 2])
        with nav_c2:
            card_page = st.selectbox(
                "หน้าที่",
                options=list(range(1, total_pages + 1)),
                index=0,
                format_func=lambda x: f"หน้า {x} / {total_pages}"
            )
            
        start_idx = (card_page - 1) * cards_per_page
        end_idx = min(start_idx + cards_per_page, total_count)
        page_df = df_filtered.iloc[start_idx:end_idx]
        
        # Grid
        grid_cols = st.columns(3)
        for idx, (_, row) in enumerate(page_df.iterrows()):
            col_pos = idx % 3
            with grid_cols[col_pos]:
                comp = row.get("บริษัท")
                color_theme = "#f59e0b" if comp == "Baania" else ("#3b82f6" if comp == "BAM" else "#ec4899")
                
                # Image block
                image_tag = f'<div style="height: 150px; background-color: #f8fafc; border-bottom: 2px solid {color_theme}; border-radius: 8px 8px 0 0; display: flex; align-items: center; justify-content: center; color: #94a3b8;"><i class="fa fa-building" style="font-size: 2.8rem; color: {color_theme};"></i></div>'
                
                # Pricing
                price_val = row.get("ราคา", 0)

                price_display = f"฿{price_val:,.0f} บาท" if pd.notnull(price_val) and price_val > 0 else "ไม่ทราบราคา"
                
                # Details list
                details_list = []
                b_space = row.get("พื้นที่ใช้สอย (ตร.ม.)")
                if pd.notnull(b_space) and str(b_space).strip() != "" and str(b_space).strip() != "nan":
                    details_list.append(f'{format_num_val(b_space)} ตร.ม.')
                l_desc = row.get("พื้นที่ (ไร่-งาน-วา)")
                if l_desc and str(l_desc).strip() != "" and str(l_desc).strip() != "nan" and str(l_desc).strip() != "0-0-0":
                    details_list.append(f'ที่ดิน: {l_desc}')
                details_line = " | ".join(details_list)
                
                # Rooms
                room_list = []
                bed = row.get("ห้องนอน")
                bath = row.get("ห้องน้ำ")
                park = row.get("ที่จอดรถ")
                if pd.notnull(bed) and str(bed).strip() != "" and str(bed).strip() != "nan":
                    room_list.append(f'<i class="fa fa-bed"></i> {format_num_val(bed)} นอน')
                if pd.notnull(bath) and str(bath).strip() != "" and str(bath).strip() != "nan":
                    room_list.append(f'<i class="fa fa-bath"></i> {format_num_val(bath)} น้ำ')
                if pd.notnull(park) and str(park).strip() != "" and str(park).strip() != "nan":
                    room_list.append(f'<i class="fa fa-car"></i> {format_num_val(park)} จอด')
                room_line = "  ".join(room_list) if room_list else ""
                
                # Badge company
                comp_badge = f'<span style="background-color: {color_theme}; color: #ffffff; padding: 2px 8px; border-radius: 4px; font-size: 0.72rem; font-weight: 700; margin-right: 5px;">{comp}</span>'
                
                # HTML Card
                card_html = f"""
                <div style="background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; margin-bottom: 12px; box-shadow: 0 4px 12px rgba(15,23,42,0.02); overflow: hidden; display: flex; flex-direction: column;">
                    {image_tag}
                    <div style="padding: 16px; flex-grow: 1; display: flex; flex-direction: column; justify-content: space-between; min-height: 240px;">
                        <div>
                            <div>
                                {comp_badge}
                                <span style="background-color: #f1f5f9; color: #475569; padding: 2px 6px; border-radius: 4px; font-size: 0.7rem; font-weight: 700;">{row.get("ประเภททรัพย์", "")}</span>
                                <span style="color: #94a3b8; font-size: 0.7rem; float: right;">ID: {row.get("รหัสทรัพย์", "")}</span>
                            </div>
                            <h4 style="margin: 12px 0 6px 0; font-size: 0.95rem; color: #1e293b; line-height: 1.4; font-weight: 700; min-height: 2.8em; overflow: hidden; text-overflow: ellipsis; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;">{row.get("ชื่อประกาศ_สะอาด")}</h4>
                            <p style="color: #64748b; font-size: 0.78rem; margin-bottom: 5px;"><i class="fa fa-map-marker" style="margin-right: 4px; color: {color_theme};"></i>{row.get("จังหวัด")} &raquo; {row.get("อำเภอ")} &raquo; {row.get("ตำบล")}</p>
                            <p style="color: #334155; font-size: 0.78rem; margin-bottom: 4px; font-weight: 600;">{details_line}</p>
                            <div style="color: #64748b; font-size: 0.75rem; margin-bottom: 8px;">{room_line}</div>
                        </div>
                        <div>
                            <div style="margin-top: 10px; margin-bottom: 6px;"><span style="color: {color_theme}; font-weight: 800; font-size: 1.25rem;">{price_display}</span></div>
                            <div style="color: #94a3b8; font-size: 0.65rem;"><i class="fa fa-clock"></i> ดึงข้อมูล: {row.get("วันที่ดึงข้อมูล")}</div>
                        </div>
                    </div>
                </div>
                """
                st.markdown(card_html, unsafe_allow_html=True)
                
                # Link Button
                link_url = row.get("ลิงก์_สะอาด") or row.get("ลิงก์")
                if link_url and isinstance(link_url, str) and link_url.startswith("http"):
                    st.link_button(f"🌐 ไปยังเว็บไซต์ของ {comp}", url=link_url, use_container_width=True)
                else:
                    st.button(f"ไม่มีลิงก์ต้นทาง", disabled=True, use_container_width=True)
                    
                st.markdown("<div style='margin-bottom: 20px;'></div>", unsafe_allow_html=True)

# ----- TAB 4: COMPARISON -----
with tab4:
    st.markdown("### 🔍 เปรียบเทียบทำเลของทรัพย์สิน (Asset Location Comparison)")
    st.write("นำเข้าพิกัดที่คุณต้องการเพื่อค้นหาทรัพย์สิน NPA ของทุกบริษัทที่อยู่ใกล้เคียงในรัศมีที่กำหนด")
    
    st.markdown("---")
    
    inp_col1, inp_col2 = st.columns(2)
    with inp_col1:
        st.markdown("##### 📍 ส่วนที่ 1: กำหนดพิกัดที่ต้องการค้นหา")
        inp_name = st.text_input("ชื่อสถานที่/จุดอ้างอิง", value="จุดศูนย์กลางกรุงเทพฯ (อนุสาวรีย์ชัยฯ)")
        inp_lat = st.number_input("ละติจูด (Latitude)", value=13.7651, format="%.6f")
        inp_lng = st.number_input("ลองจิจูด (Longitude)", value=100.5383, format="%.6f")
        
    with inp_col2:
        st.markdown("##### ⚙️ ส่วนที่ 2: เงื่อนไขการค้นหา")
        search_radius = st.slider("รัศมีการค้นหา (กิโลเมตร)", min_value=0.5, max_value=50.0, value=5.0, step=0.5)
        filter_by_type = st.checkbox("กรองประเภททรัพย์สินให้เหมือนกัน", value=False)
        selected_compare_type = st.selectbox(
            "ประเภททรัพย์สินที่ต้องการค้นหา (หากกรองประเภททรัพย์)",
            options=sorted(df_raw['ประเภททรัพย์'].unique().tolist())
        )
        
    st.markdown("<br/>", unsafe_allow_html=True)
    
    if st.button("🔍 เริ่มการวิเคราะห์เปรียบเทียบพิกัด", type="primary"):
        with st.spinner("กำลังค้นหาทำเลและทรัพย์ที่อยู่รอบๆ..."):
            m_type = selected_compare_type if filter_by_type else None
            nearby_df = find_nearby_properties(inp_lat, inp_lng, df_raw, search_radius, match_type=m_type)
            
            if nearby_df.empty:
                st.warning(f"❌ ไม่พบทรัพย์สิน NPA ในรัศมี {search_radius} กิโลเมตร รอบจุดพิกัด ({inp_lat}, {inp_lng})")
            else:
                st.success(f"พบทรัพย์ NPA ทั้งหมด {len(nearby_df)} รายการ ในรัศมี {search_radius} กิโลเมตร!")
                
                # Show Table
                st.dataframe(
                    nearby_df[[
                        "บริษัท", "รหัสทรัพย์", "ชื่อประกาศ_สะอาด", "ประเภททรัพย์", "ราคา", 
                        "จังหวัด", "อำเภอ", "ตำบล", "ระยะทาง (กม.)", "ลิงก์_สะอาด"
                    ]].sort_values("ระยะทาง (กม.)"),
                    use_container_width=True,
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
                    "ประเภท": "จุดอ้างอิงของคุณ",
                    "ขนาดพิกัด": 12,
                    "บริษัท": "จุดอ้างอิง"
                })
                
                # Found points
                for _, r in nearby_df.iterrows():
                    map_points.append({
                        "ละติจูด": r["ละติจูด"],
                        "ลองจิจูด": r["ลองจิจูด"],
                        "ชื่อ": r["ชื่อประกาศ_สะอาด"],
                        "ประเภท": f"ทรัพย์ NPA ({r['บริษัท']})",
                        "ขนาดพิกัด": 8,
                        "บริษัท": r["บริษัท"]
                    })
                    
                map_compare_df = pd.DataFrame(map_points)
                fig_compare = px.scatter_mapbox(
                    map_compare_df,
                    lat="ละติจูด",
                    lon="ลองจิจูด",
                    color="บริษัท",
                    hover_name="ชื่อ",
                    zoom=11.5,
                    height=750,
                    color_discrete_map={
                        "จุดอ้างอิง": "#ef4444",
                        "Baania": "#f59e0b",
                        "BAM": "#3b82f6",
                        "ZmyHome": "#ec4899"
                    },
                    template=plotly_template
                )
                fig_compare.update_layout(
                    mapbox_style=mapbox_style,
                    margin={"r": 0, "t": 0, "l": 0, "b": 0},
                    paper_bgcolor="rgba(0,0,0,0)"
                )
                st.plotly_chart(fig_compare, use_container_width=True, theme=None, config={"scrollZoom": True})

