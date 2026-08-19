import os
import sys
import glob
import time
import io
import json
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from datetime import datetime

# Local screenshot service
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)
from screenshot_service import capture_url_sync, CACHE_DIR

# ---------------------------------------------------------
# Page Configuration & Styling
# ---------------------------------------------------------
st.set_page_config(
    page_title="ระบบตรวจสอบความถูกต้องข้อมูล & เปรียบเทียบหน้าเว็บจริง (Data QA)",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

CUSTOM_CSS = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Sarabun:wght@300;400;500;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Sarabun', sans-serif;
    }
    
    .metric-card {
        background: linear-gradient(135deg, #ffffff 0%, #f8f9fa 100%);
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 16px 20px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.03);
        margin-bottom: 12px;
    }
    
    .metric-title {
        font-size: 0.85rem;
        color: #64748b;
        font-weight: 500;
        margin-bottom: 4px;
    }
    
    .metric-val {
        font-size: 1.7rem;
        font-weight: 700;
        color: #1e293b;
    }
    
    .metric-sub {
        font-size: 0.8rem;
        color: #10b981;
        font-weight: 500;
    }
    
    .qa-box {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
        margin-bottom: 16px;
    }
    
    .field-badge-ok {
        background-color: #dcfce7;
        color: #166534;
        padding: 2px 8px;
        border-radius: 6px;
        font-size: 0.8rem;
        font-weight: 600;
    }
    
    .field-badge-missing {
        background-color: #fee2e2;
        color: #991b1b;
        padding: 2px 8px;
        border-radius: 6px;
        font-size: 0.8rem;
        font-weight: 600;
    }
    
    .badge-company {
        background-color: #3b82f6;
        color: #ffffff;
        padding: 4px 10px;
        border-radius: 8px;
        font-weight: 600;
        font-size: 0.85rem;
    }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# ---------------------------------------------------------
# Constants & File Paths
# ---------------------------------------------------------
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
CSV_DIR = os.path.join(PROJECT_ROOT, "Monthly all new", "CSV_Output")
QA_LOG_FILE = os.path.join(CURRENT_DIR, "cache", "qa_verification_log.json")
os.makedirs(os.path.dirname(QA_LOG_FILE), exist_ok=True)

STANDARD_COLUMNS = [
    "บริษัท", "ID", "รหัสทรัพย์", "ชื่อโครงการ", "ประเภททรัพย์", "ประเภทการขาย", "ราคา",
    "ตำบล", "อำเภอ", "จังหวัด", "ละติจูด", "ลองจิจูด", "ชื่อประกาศ", "ลิงก์",
    "เนื้อที่ (ตร.ว.)", "พื้นที่ใช้สอย (ตร.ม.)", "วันที่ดึงข้อมูล",
    "ห้องนอน", "ห้องน้ำ", "ที่จอดรถ", "วันประกาศ", "บริษัทเจ้าของทรัพย์"
]

COLUMN_CATEGORIES = {
    "ข้อมูลหลัก (Core)": ["บริษัท", "ID", "รหัสทรัพย์", "ชื่อโครงการ", "ชื่อประกาศ", "ลิงก์"],
    "ราคาและประเภท (Pricing & Type)": ["ราคา", "ประเภททรัพย์", "ประเภทการขาย", "บริษัทเจ้าของทรัพย์"],
    "ตำแหน่งที่ตั้ง (Location)": ["ตำบล", "อำเภอ", "จังหวัด", "ละติจูด", "ลองจิจูด"],
    "สเปกและพื้นที่ (Specs & Area)": ["เนื้อที่ (ตร.ว.)", "พื้นที่ใช้สอย (ตร.ม.)", "ห้องนอน", "ห้องน้ำ", "ที่จอดรถ"],
    "วันที่ (Dates)": ["วันที่ดึงข้อมูล", "วันประกาศ"]
}

# ---------------------------------------------------------
# Helper Functions & Data Loading
# ---------------------------------------------------------
def is_value_missing(val):
    """Check if a cell value is missing, empty, None, or dash."""
    if val is None or pd.isna(val):
        return True
    s = str(val).strip()
    if s in ["-", "nan", "None", "null", "NaN", "undefined"]:
        return True
    return len(s) == 0

@st.cache_data(ttl=600)
def load_all_company_data():
    """Load all company CSV files and calculate data completeness metrics."""
    if not os.path.exists(CSV_DIR):
        return {}, pd.DataFrame(columns=STANDARD_COLUMNS)
        
    csv_files = glob.glob(os.path.join(CSV_DIR, "*.csv"))
    # Exclude all-merged files and backup files
    csv_files = [
        f for f in csv_files 
        if not os.path.basename(f).lower().startswith("all") 
        and not "all_assets" in os.path.basename(f).lower() 
        and not "_backup" in os.path.basename(f).lower() 
        and not "merge" in os.path.basename(f).lower()
    ]
    
    company_dfs = {}
    combined_list = []
    
    for file_path in sorted(csv_files):
        try:
            filename = os.path.basename(file_path)
            company_name = filename.split('_')[0]
            
            df = pd.read_csv(file_path, encoding="utf-8-sig", dtype=str)
            for col in STANDARD_COLUMNS:
                if col not in df.columns:
                    df[col] = ""
            df = df[STANDARD_COLUMNS]
            df["_source_file"] = filename
            df["_file_company"] = company_name
            
            if "บริษัท" not in df.columns or df["บริษัท"].isna().all() or (df["บริษัท"].str.strip() == "").all():
                df["บริษัท"] = company_name
            else:
                df["บริษัท"] = df["บริษัท"].fillna(company_name)
                
            company_dfs[company_name] = df
            combined_list.append(df)
        except Exception as e:
            st.error(f"เกิดข้อผิดพลาดในการโหลดไฟล์ {file_path}: {e}")
            
    combined_df = pd.concat(combined_list, ignore_index=True) if combined_list else pd.DataFrame(columns=STANDARD_COLUMNS)
    return company_dfs, combined_df

def compute_completeness_matrix(company_dfs):
    """Compute field-by-field completeness percentage for each company."""
    rows = []
    for company, df in company_dfs.items():
        total_rows = len(df)
        if total_rows == 0:
            continue
            
        for col in STANDARD_COLUMNS:
            series = df[col] if col in df.columns else pd.Series([""] * total_rows)
            filled_mask = ~series.apply(is_value_missing)
            filled_count = int(filled_mask.sum())
            missing_count = total_rows - filled_count
            pct = (filled_count / total_rows * 100) if total_rows > 0 else 0.0
            
            category = "อื่นๆ"
            for cat_name, cat_cols in COLUMN_CATEGORIES.items():
                if col in cat_cols:
                    category = cat_name
                    break
                    
            rows.append({
                "บริษัท": company,
                "หมวดหมู่": category,
                "คอลัมน์": col,
                "จำนวนทั้งหมด": total_rows,
                "มีข้อมูล (Filled)": filled_count,
                "ไม่มีข้อมูล (Missing)": missing_count,
                "ความครบถ้วน (%)": round(pct, 2)
            })
            
    return pd.DataFrame(rows)

def load_qa_results():
    """Load human verification records from JSON cache."""
    if os.path.exists(QA_LOG_FILE):
        try:
            with open(QA_LOG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_qa_result(item_key, data):
    """Save human verification status to JSON cache."""
    results = load_qa_results()
    results[item_key] = {
        **data,
        "verified_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    with open(QA_LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

# ---------------------------------------------------------
# Sidebar Navigation
# ---------------------------------------------------------
st.sidebar.markdown("## 🔍 Data Quality & QA Portal")
st.sidebar.caption("ระบบตรวจสอบความถูกต้อง & เปรียบเทียบภาพหน้าเว็บจริง")

company_dfs, all_df = load_all_company_data()

if st.sidebar.button("🔄 โหลดข้อมูลใหม่ (Reload Data)", use_container_width=True):
    st.cache_data.clear()
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.markdown("### 📁 ข้อมูลที่ตรวจพบ")
for co, df in company_dfs.items():
    st.sidebar.write(f"• **{co}**: {len(df):,} รายการ")

st.sidebar.markdown("---")
view_mode = st.sidebar.radio(
    "เลือกหน้าการทำงาน:",
    [
        "📊 1. ภาพรวมความครบถ้วนของข้อมูล (Completeness Matrix)",
        "🔍 2. สุ่มตรวจ & เทียบภาพหน้าเว็บจริง (Live Visual QA)",
        "📑 3. รายงานสรุปผลการตรวจ (Verification Report)"
    ]
)

# ---------------------------------------------------------
# PAGE 1: COMPLETENESS AUDIT DASHBOARD
# ---------------------------------------------------------
if view_mode.startswith("📊"):
    st.markdown("## 📊 รายงานความครบถ้วนของข้อมูลแต่ละบริษัท (Data Completeness Audit)")
    st.markdown("ตรวจสอบอัตราความสมบูรณ์ (% Fill Rate) ของข้อมูลในแต่ละคอลัมน์ของทุกบริษัท เพื่อหาจุดบกพร่องของ Scraper")
    
    if all_df.empty:
        st.warning("⚠️ ไม่พบไฟล์ข้อมูล CSV ในโฟลเดอร์ `Monthly all new/CSV_Output`")
        st.stop()
        
    comp_df = compute_completeness_matrix(company_dfs)
    
    total_assets = len(all_df)
    total_companies = len(company_dfs)
    avg_completeness = comp_df["ความครบถ้วน (%)"].mean()
    perfect_fields = comp_df[comp_df["ความครบถ้วน (%)"] >= 99.0]["คอลัมน์"].nunique()
    
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.html(f"""
        <div class="metric-card">
            <div class="metric-title">📦 จำนวนทรัพย์ทั้งหมด</div>
            <div class="metric-val">{total_assets:,.0f}</div>
            <div class="metric-sub">จาก {total_companies} บริษัท</div>
        </div>
        """)
    with c2:
        st.html(f"""
        <div class="metric-card">
            <div class="metric-title">📈 ความครบถ้วนเฉลี่ยรวม</div>
            <div class="metric-val">{avg_completeness:.1f}%</div>
            <div class="metric-sub">ทุกคอลัมน์มาตรฐาน</div>
        </div>
        """)
    with c3:
        st.html(f"""
        <div class="metric-card">
            <div class="metric-title">🏢 จำนวนบริษัทที่นำเข้า</div>
            <div class="metric-val">{total_companies}</div>
            <div class="metric-sub">BAM, SAM, DD, LI, ฯลฯ</div>
        </div>
        """)
    with c4:
        st.html(f"""
        <div class="metric-card">
            <div class="metric-title">✨ คอลัมน์ที่สมบูรณ์สูง (≥99%)</div>
            <div class="metric-val">{perfect_fields} / {len(STANDARD_COLUMNS)}</div>
            <div class="metric-sub">ช่องข้อมูลหลัก</div>
        </div>
        """)
        
    st.markdown("---")
    
    # Visual Analytics
    col_chart1, col_chart2 = st.columns([1, 1])
    
    with col_chart1:
        st.subheader("🏆 คะแนนความครบถ้วนรวมเฉลี่ย แยกตามบริษัท")
        company_scores = comp_df.groupby("บริษัท")["ความครบถ้วน (%)"].mean().reset_index()
        company_scores = company_scores.sort_values(by="ความครบถ้วน (%)", ascending=False)
        
        fig_bar = px.bar(
            company_scores,
            x="ความครบถ้วน (%)",
            y="บริษัท",
            orientation="h",
            text="ความครบถ้วน (%)",
            color="ความครบถ้วน (%)",
            color_continuous_scale=["#ef4444", "#f59e0b", "#10b981"],
            range_color=[40, 100]
        )
        fig_bar.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
        fig_bar.update_layout(
            margin=dict(l=10, r=30, t=10, b=10),
            height=320,
            xaxis=dict(range=[0, 110], title="ความครบถ้วน (%)"),
            yaxis=dict(title="")
        )
        st.plotly_chart(fig_bar, use_container_width=True)

    with col_chart2:
        st.subheader("🎯 ความครบถ้วนของข้อมูลสำคัญ (Key Fields Health)")
        key_cols = ["ราคา", "ลิงก์", "ประเภททรัพย์", "จังหวัด", "ละติจูด", "เนื้อที่ (ตร.ว.)"]
        key_comp = comp_df[comp_df["คอลัมน์"].isin(key_cols)].groupby("คอลัมน์")["ความครบถ้วน (%)"].mean().reset_index()
        key_comp = key_comp.sort_values(by="ความครบถ้วน (%)", ascending=True)
        
        fig_key = px.bar(
            key_comp,
            x="ความครบถ้วน (%)",
            y="คอลัมน์",
            orientation="h",
            text="ความครบถ้วน (%)",
            color="ความครบถ้วน (%)",
            color_continuous_scale=["#f87171", "#fbbf24", "#34d399"],
            range_color=[50, 100]
        )
        fig_key.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
        fig_key.update_layout(
            margin=dict(l=10, r=30, t=10, b=10),
            height=320,
            xaxis=dict(range=[0, 110], title="ความครบถ้วนเฉลี่ย (%)"),
            yaxis=dict(title="")
        )
        st.plotly_chart(fig_key, use_container_width=True)

    # Completeness Heatmap
    st.subheader("🔥 Heatmap ตรวจสอบความครบถ้วนแยกตามคอลัมน์ (Completeness Heatmap)")
    
    pivot_df = comp_df.pivot(index="บริษัท", columns="คอลัมน์", values="ความครบถ้วน (%)")
    pivot_df = pivot_df[[c for c in STANDARD_COLUMNS if c in pivot_df.columns]]
    
    fig_heat = px.imshow(
        pivot_df,
        labels=dict(x="คอลัมน์ข้อมูล", y="บริษัท", color="ความครบถ้วน (%)"),
        x=pivot_df.columns,
        y=pivot_df.index,
        color_continuous_scale=["#ef4444", "#fef08a", "#10b981"],
        aspect="auto",
        text_auto=".0f"
    )
    fig_heat.update_layout(
        height=380,
        margin=dict(l=10, r=10, t=10, b=10),
        xaxis_tickangle=-45
    )
    st.plotly_chart(fig_heat, use_container_width=True)
    
    # Detailed Data Table
    st.subheader("📋 ตารางแจกแจงความสมบูรณ์รายคอลัมน์ (Field Details)")
    
    f_col1, f_col2, f_col3 = st.columns([1, 1, 1])
    with f_col1:
        sel_company = st.selectbox("กรองตามบริษัท:", ["ทั้งหมด (All)"] + list(company_dfs.keys()))
    with f_col2:
        sel_category = st.selectbox("กรองตามหมวดหมู่:", ["ทั้งหมด (All)"] + list(COLUMN_CATEGORIES.keys()))
    with f_col3:
        search_col = st.text_input("ค้นหาชื่อคอลัมน์:", placeholder="เช่น ราคา, ละติจูด...")
        
    filtered_comp = comp_df.copy()
    if sel_company != "ทั้งหมด (All)":
        filtered_comp = filtered_comp[filtered_comp["บริษัท"] == sel_company]
    if sel_category != "ทั้งหมด (All)":
        filtered_comp = filtered_comp[filtered_comp["หมวดหมู่"] == sel_category]
    if search_col.strip():
        filtered_comp = filtered_comp[filtered_comp["คอลัมน์"].str.contains(search_col.strip(), case=False, na=False)]
        
    def color_pct(val):
        if val >= 90:
            return 'background-color: #d1fae5; color: #065f46; font-weight: bold;'
        elif val >= 50:
            return 'background-color: #fef3c7; color: #92400e; font-weight: bold;'
        else:
            return 'background-color: #fee2e2; color: #991b1b; font-weight: bold;'

    styled_df = filtered_comp.style.map(color_pct, subset=['ความครบถ้วน (%)']).format({
        "จำนวนทั้งหมด": "{:,.0f}",
        "มีข้อมูล (Filled)": "{:,.0f}",
        "ไม่มีข้อมูล (Missing)": "{:,.0f}",
        "ความครบถ้วน (%)": "{:.2f}%"
    })
    
    st.dataframe(styled_df, use_container_width=True, height=400)
    
    # Drill-down Explorer
    with st.expander("🔎 ตรวจสอบรายการที่มีข้อมูลแหว่ง (Missing Records Inspector)"):
        st.markdown("เลือกบริษัทและคอลัมน์ที่ต้องการดูรายการข้อมูลที่ว่างอยู่:")
        d_c1, d_c2 = st.columns(2)
        with d_c1:
            inspect_co = st.selectbox("เลือกบริษัท:", list(company_dfs.keys()), key="inspect_co")
        with d_c2:
            inspect_col = st.selectbox("เลือกคอลัมน์ที่ต้องการตรวจ:", STANDARD_COLUMNS, key="inspect_col")
            
        if inspect_co in company_dfs:
            target_df = company_dfs[inspect_co]
            if inspect_col in target_df.columns:
                missing_mask = target_df[inspect_col].apply(is_value_missing)
                missing_df = target_df[missing_mask]
                st.write(f"พบรายการที่ช่อง **{inspect_col}** ว่างอยู่จำนวน **{len(missing_df):,}** รายการ (จากทั้งหมด {len(target_df):,} รายการ)")
                if not missing_df.empty:
                    preview_cols = ["ID", "รหัสทรัพย์", "ชื่อประกาศ", "ราคา", "จังหวัด", "ลิงก์", inspect_col]
                    preview_cols = [c for c in preview_cols if c in missing_df.columns]
                    st.dataframe(missing_df[preview_cols].head(50), use_container_width=True)

# ---------------------------------------------------------
# PAGE 2: RANDOM SAMPLING & LIVE VISUAL QA
# ---------------------------------------------------------
elif view_mode.startswith("🔍"):
    st.markdown("## 🔍 สุ่มตรวจข้อมูล & เปรียบเทียบหน้าเว็บจริง (Live Visual QA)")
    st.markdown("สุ่มรายการทรัพย์จากไฟล์ข้อมูล แคปภาพหน้าเว็บจริงแบบ Real-time ด้วย Playwright และนำมาเทียบกับข้อมูล Scraped Data เพื่อให้คนตรวจสอบความถูกต้อง")

    if all_df.empty:
        st.warning("⚠️ ไม่พบไฟล์ข้อมูล CSV ในระบบ")
        st.stop()

    if "qa_samples" not in st.session_state:
        st.session_state.qa_samples = []
    if "current_qa_index" not in st.session_state:
        st.session_state.current_qa_index = 0
    if "screenshot_cache" not in st.session_state:
        st.session_state.screenshot_cache = {}

    tab_mode_sample, tab_mode_search = st.tabs([
        "🎲 สุ่มตรวจตัวอย่าง (Random Sampling)",
        "🔎 ค้นหาทรัพย์เจาะจง (Search Specific Property)"
    ])

    btn_sample = False
    with tab_mode_sample:
        cfg_c1, cfg_c2, cfg_c3, cfg_c4 = st.columns([1.5, 1.3, 1.5, 1.4])
        
        with cfg_c1:
            sample_target_co = st.selectbox(
                "บริษัทที่ต้องการสุ่ม:",
                ["ทุกบริษัท (ครบทั้ง 7 บริษัท)"] + list(company_dfs.keys()),
                key="sel_target_co"
            )
        with cfg_c2:
            if sample_target_co.startswith("ทุกบริษัท"):
                samples_per_co = st.number_input("จำนวนที่สุ่ม (ต่อบริษัท):", min_value=1, max_value=20, value=1, step=1, key="num_samples_co")
                st.caption(f"📊 รวมทั้งหมด: **{samples_per_co * len(company_dfs)} รายการ** ({samples_per_co} × {len(company_dfs)} บริษัท)")
            else:
                samples_per_co = st.number_input("จำนวนที่สุ่ม (รายการ):", min_value=1, max_value=50, value=5, step=1, key="num_samples_single")
        with cfg_c3:
            sample_strategy = st.selectbox(
                "รูปแบบการสุ่ม:",
                [
                    "⚖️ สุ่มตัวแทนครบทุกบริษัท (Balanced per Company)",
                    "⚠️ สุ่มเน้นรายการที่ข้อมูลแหว่ง (Missing Fields Focus)",
                    "🎲 สุ่มทั่วไปทั้งหมด (Random Pool)"
                ],
                key="sel_strategy"
            )
        with cfg_c4:
            st.write("")
            st.write("")
            btn_sample = st.button("🎲 สุ่มตัวอย่างใหม่ (Generate Sample)", type="primary", use_container_width=True, key="btn_sample_trigger")

    with tab_mode_search:
        st.markdown("##### 🔎 ค้นหาทรัพย์จากฐานข้อมูล (ID, รหัสทรัพย์, ชื่อโครงการ, ชื่อประกาศ หรือ URL):")
        srch_c1, srch_c2, srch_c3, srch_c4 = st.columns([2.5, 1.3, 1, 1.2])
        with srch_c1:
            search_query = st.text_input("คำค้นหา:", placeholder="เช่น 63711, RCAM660022, คอนโด, พระราม 9 หรือ URL...", key="prop_search_query")
        with srch_c2:
            search_co = st.selectbox("บริษัท:", ["ทุกบริษัท"] + list(company_dfs.keys()), key="prop_search_co")
        with srch_c3:
            search_limit = st.number_input("จำกัดผลลัพธ์:", min_value=1, max_value=100, value=10, step=5, key="prop_search_limit")
        with srch_c4:
            st.write("")
            st.write("")
            btn_search = st.button("🔎 ค้นหาทรัพย์", type="primary", use_container_width=True, key="btn_search_trigger")
            
        if btn_search:
            if not search_query.strip():
                st.warning("⚠️ กรุณากรอกคำค้นหา (เช่น ID หรือ รหัสทรัพย์ หรือชื่อโครงการ)")
            else:
                target_df = all_df if search_co == "ทุกบริษัท" else company_dfs.get(search_co, pd.DataFrame())
                if not target_df.empty:
                    q_clean = search_query.strip().lower()
                    searchable_cols = [c for c in ["ID", "รหัสทรัพย์", "ชื่อโครงการ", "ชื่อประกาศ", "ลิงก์", "จังหวัด", "อำเภอ"] if c in target_df.columns]
                    
                    mask = pd.Series(False, index=target_df.index)
                    for col in searchable_cols:
                        mask = mask | target_df[col].astype(str).str.lower().str.contains(q_clean, na=False, regex=False)
                        
                    matched_df = target_df[mask]
                    
                    if not matched_df.empty:
                        # Prioritize items with valid links
                        if "ลิงก์" in matched_df.columns:
                            valid_matched = matched_df[~matched_df["ลิงก์"].apply(is_value_missing) & matched_df["ลิงก์"].astype(str).str.startswith("http")]
                            pool_to_use = valid_matched if not valid_matched.empty else matched_df
                        else:
                            pool_to_use = matched_df
                            
                        results_list = pool_to_use.head(search_limit).to_dict('records')
                        st.session_state.qa_samples = results_list
                        st.session_state.current_qa_index = 0
                        st.success(f"🎉 พบทั้งหมด **{len(matched_df):,} รายการ** (นำ {len(results_list)} รายการเข้าสู่หน้าตรวจเทียบเรียบร้อยแล้ว!)")
                        st.rerun()
                    else:
                        st.warning(f"❌ ไม่พบรายการทรัพย์ที่ตรงกับคำค้นหา '{search_query}' ในบริษัทที่เลือก")
                else:
                    st.warning("⚠️ ไม่มีข้อมูลสำหรับค้นหา")

    def get_valid_url_df(df_in):
        if "ลิงก์" not in df_in.columns:
            return pd.DataFrame()
        return df_in[~df_in["ลิงก์"].apply(is_value_missing) & df_in["ลิงก์"].str.startswith("http")]

    if btn_sample or len(st.session_state.qa_samples) == 0:
        samples = []
        if sample_target_co.startswith("ทุกบริษัท"):
            if sample_strategy.startswith("⚠️"):
                # Missing fields focus per company
                for co_name, df_co in company_dfs.items():
                    valid_df = get_valid_url_df(df_co)
                    if not valid_df.empty:
                        missing_score = valid_df[STANDARD_COLUMNS].apply(lambda row: sum(is_value_missing(v) for v in row), axis=1)
                        missing_pool = valid_df[missing_score >= 2]
                        pool = missing_pool if len(missing_pool) >= samples_per_co else valid_df
                        n = min(len(pool), samples_per_co)
                        sampled = pool.sample(n=n, random_state=int(time.time() * 1000) % 100000)
                        samples.extend(sampled.to_dict('records'))
            elif sample_strategy.startswith("🎲"):
                # Total random pool
                valid_df = get_valid_url_df(all_df)
                total_needed = samples_per_co * len(company_dfs)
                if not valid_df.empty:
                    sampled = valid_df.sample(n=min(len(valid_df), total_needed), random_state=int(time.time() * 1000) % 100000)
                    samples.extend(sampled.to_dict('records'))
            else:
                # Default: Balanced per company (guarantee all 7 companies)
                for co_name, df_co in company_dfs.items():
                    valid_df = get_valid_url_df(df_co)
                    if not valid_df.empty:
                        n = min(len(valid_df), samples_per_co)
                        sampled = valid_df.sample(n=n, random_state=int(time.time() * 1000) % 100000)
                        samples.extend(sampled.to_dict('records'))
        else:
            df_co = company_dfs.get(sample_target_co, pd.DataFrame())
            valid_df = get_valid_url_df(df_co)
            if not valid_df.empty:
                sampled = valid_df.sample(n=min(len(valid_df), samples_per_co), random_state=int(time.time() * 1000) % 100000)
                samples.extend(sampled.to_dict('records'))

        st.session_state.qa_samples = samples
        st.session_state.current_qa_index = 0
        st.rerun()

    samples = st.session_state.qa_samples
    if not samples:
        st.info("กรุณากดปุ่ม **สุ่มตัวอย่างใหม่** หรือใช้ **ช่องค้นหาทรัพย์** เพื่อเริ่มต้นตรวจสอบ")
        st.stop()

    st.markdown("---")
    
    # Navigation & Batch Capture
    nav_c1, nav_c2, nav_c3, nav_c4 = st.columns([1.5, 1, 1, 2])
    with nav_c1:
        st.markdown(f"### 📋 รายการพร้อมตรวจ: **{len(samples)} รายการ**")
    with nav_c2:
        if st.button("⬅️ ก่อนหน้า (Previous)", use_container_width=True, disabled=(st.session_state.current_qa_index == 0)):
            st.session_state.current_qa_index = max(0, st.session_state.current_qa_index - 1)
            st.rerun()
    with nav_c3:
        if st.button("ถัดไป (Next) ➡️", use_container_width=True, disabled=(st.session_state.current_qa_index >= len(samples) - 1)):
            st.session_state.current_qa_index = min(len(samples) - 1, st.session_state.current_qa_index + 1)
            st.rerun()
    with nav_c4:
        btn_batch_capture = st.button("📸 แคปหน้าเว็บทั้งหมดทุกรายการทันที", use_container_width=True)

    if btn_batch_capture:
        progress_bar = st.progress(0, text="กำลังเริ่มแคปภาพหน้าเว็บ...")
        for idx, item in enumerate(samples):
            url = str(item.get("ลิงก์", "")).strip()
            prop_id = str(item.get("ID", item.get("รหัสทรัพย์", idx))).strip()
            progress_bar.progress((idx + 1) / len(samples), text=f"กำลังแคปภาพ ({idx+1}/{len(samples)}): {item.get('บริษัท', '')} - {prop_id}...")
            res = capture_url_sync(url, property_id=prop_id)
            st.session_state.screenshot_cache[url] = res
        progress_bar.empty()
        st.success("✅ แคปภาพหน้าเว็บทุกรายการเรียบร้อยแล้ว!")
        st.rerun()

    item_labels = [
        f"[{i+1}/{len(samples)}] {s.get('บริษัท', '')} | {s.get('รหัสทรัพย์', s.get('ID', '-'))} | {str(s.get('ชื่อประกาศ', ''))[:40]}"
        for i, s in enumerate(samples)
    ]
    selected_item_idx = st.selectbox(
        "เลือกรายการที่ต้องการดู:",
        options=list(range(len(samples))),
        format_func=lambda x: item_labels[x],
        index=st.session_state.current_qa_index
    )
    if selected_item_idx != st.session_state.current_qa_index:
        st.session_state.current_qa_index = selected_item_idx
        st.rerun()

    cur_item = samples[st.session_state.current_qa_index]
    cur_url = str(cur_item.get("ลิงก์", "")).strip()
    cur_id = str(cur_item.get("ID", cur_item.get("รหัสทรัพย์", ""))).strip()
    cur_company = str(cur_item.get("บริษัท", "")).strip()
    item_key = f"{cur_company}_{cur_id}_{hash(cur_url)}"

    saved_qa_records = load_qa_results()
    existing_qa = saved_qa_records.get(item_key, {})

    st.markdown("---")
    col_left, col_right = st.columns([1, 1.1])
    
    # Left: Data Card
    with col_left:
        st.html(f"""
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
            <span class="badge-company">{cur_company}</span>
            <span style="color: #64748b; font-size: 0.9rem;">ID: <b>{cur_id}</b> | รหัสทรัพย์: <b>{cur_item.get('รหัสทรัพย์', '-')}</b></span>
        </div>
        """)
        
        st.markdown(f"#### 🏷️ {cur_item.get('ชื่อประกาศ', 'ไม่ระบุชื่อประกาศ')}")
        
        price_val = cur_item.get("ราคา", "")
        price_display = f"฿{float(price_val):,.0f}" if price_val and str(price_val).replace('.','',1).isdigit() else str(price_val)
        if is_value_missing(price_val):
            price_display = '<span class="field-badge-missing">⚠️ ไม่มีราคา</span>'
            
        st.html(f"""
        <div style="background: #f1f5f9; padding: 12px 16px; border-radius: 8px; margin: 10px 0;">
            <div style="font-size: 0.85rem; color: #475569;">ราคาตั้งขาย / ทรัพย์</div>
            <div style="font-size: 1.5rem; font-weight: 700; color: #0f172a;">{price_display}</div>
        </div>
        """)

        st.markdown("##### 📋 ตรวจสอบค่าในแต่ละช่อง (Field Comparison):")
        
        def render_field_row(label, val, is_url=False):
            missing = is_value_missing(val)
            status_badge = '<span class="field-badge-ok">✓ มีข้อมูล</span>' if not missing else '<span class="field-badge-missing">✕ ข้อมูลว่าง</span>'
            if missing:
                display_text = '<i style="color: #94a3b8;">(ไม่มีข้อมูล)</i>'
            elif is_url:
                url_str = str(val).strip()
                display_text = f'<a href="{url_str}" target="_blank" style="color: #0284c7; text-decoration: underline; word-break: break-all; font-size: 0.82rem;">{url_str}</a>'
            else:
                display_text = str(val)
            return f"""<tr><td style="padding: 6px 10px; font-weight: 600; width: 32%; color: #334155; border-bottom: 1px solid #f1f5f9; vertical-align: top;">{label}</td><td style="padding: 6px 10px; color: #1e293b; border-bottom: 1px solid #f1f5f9; word-break: break-word;">{display_text}</td><td style="padding: 6px 10px; text-align: right; width: 22%; border-bottom: 1px solid #f1f5f9; vertical-align: top;">{status_badge}</td></tr>"""

        table_rows = [
            render_field_row("ลิงก์ (URL)", cur_item.get("ลิงก์"), is_url=True),
            render_field_row("ID", cur_item.get("ID")),
            render_field_row("รหัสทรัพย์", cur_item.get("รหัสทรัพย์")),
            render_field_row("ชื่อโครงการ", cur_item.get("ชื่อโครงการ")),
            render_field_row("ประเภททรัพย์", cur_item.get("ประเภททรัพย์")),
            render_field_row("ประเภทการขาย", cur_item.get("ประเภทการขาย")),
            render_field_row("จังหวัด", cur_item.get("จังหวัด")),
            render_field_row("อำเภอ / เขต", cur_item.get("อำเภอ")),
            render_field_row("ตำบล / แขวง", cur_item.get("ตำบล")),
            render_field_row("ละติจูด (Lat)", cur_item.get("ละติจูด")),
            render_field_row("ลองจิจูด (Long)", cur_item.get("ลองจิจูด")),
            render_field_row("เนื้อที่ (ตร.ว.)", cur_item.get("เนื้อที่ (ตร.ว.)")),
            render_field_row("พื้นที่ใช้สอย (ตร.ม.)", cur_item.get("พื้นที่ใช้สอย (ตร.ม.)")),
            render_field_row("ห้องนอน", cur_item.get("ห้องนอน")),
            render_field_row("ห้องน้ำ", cur_item.get("ห้องน้ำ")),
            render_field_row("ที่จอดรถ", cur_item.get("ที่จอดรถ")),
            render_field_row("วันประกาศ", cur_item.get("วันประกาศ")),
            render_field_row("วันที่ดึงข้อมูล", cur_item.get("วันที่ดึงข้อมูล")),
            render_field_row("บริษัทเจ้าของทรัพย์", cur_item.get("บริษัทเจ้าของทรัพย์"))
        ]
        
        table_html = f"""<table style="width: 100%; border-collapse: collapse; font-size: 0.88rem; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; overflow: hidden;"><thead><tr style="background: #f8fafc; color: #475569; text-align: left; font-size: 0.8rem;"><th style="padding: 8px 10px;">ชื่อช่องข้อมูล</th><th style="padding: 8px 10px;">ค่าที่ Scrape ได้</th><th style="padding: 8px 10px; text-align: right;">สถานะ</th></tr></thead><tbody>{''.join(table_rows)}</tbody></table>"""
        st.html(table_html)
        
        st.html(f"""
        <div style="margin-top: 12px;">
            <a href="{cur_url}" target="_blank" style="display: inline-block; background: #0284c7; color: #ffffff; padding: 8px 18px; border-radius: 8px; text-decoration: none; font-weight: 600; font-size: 0.88rem;">🌐 เปิดดูหน้าเว็บจริง (Open URL in New Tab)</a>
        </div>
        """)

    # Right: Screenshot & Form
    with col_right:
        st.markdown("#### 📸 ภาพหน้าเว็บจริง (Live Webpage Screenshot)")
        
        btn_recapture = st.button("🔄 แคปภาพใหม่อีกครั้ง (Re-capture)", key=f"re_{item_key}", use_container_width=True)
        screenshot_res = st.session_state.screenshot_cache.get(cur_url)
        
        if btn_recapture or screenshot_res is None:
            with st.spinner("กำลังแคปภาพหน้าเว็บจาก URL..."):
                screenshot_res = capture_url_sync(cur_url, property_id=cur_id, force_refresh=btn_recapture)
                st.session_state.screenshot_cache[cur_url] = screenshot_res

        if screenshot_res and screenshot_res.get("success") and screenshot_res.get("path") and os.path.exists(screenshot_res.get("path")):
            img_path = screenshot_res["path"]
            if screenshot_res.get("is_cloudflare"):
                st.warning("🛡️ **เว็บไซต์นี้ (DDproperty) มีระบบ Cloudflare ป้องกันบอทอัตโนมัติ (Anti-Bot Verification)**\n\n👉 ระบบแคปภาพเบื้องหลังจึงติดหน้าตรวจสอบความปลอดภัย กรุณาคลิกปุ่ม **[🌐 เปิดดูหน้าเว็บจริง (Open URL in New Tab)]** ทางด้านซ้ายมือ เพื่อเปิดดูหน้าประกาศบนเบราว์เซอร์จริงได้ทันทีครับ")
            st.image(img_path, caption=f"ภาพหน้าเว็บ {cur_company} (บันทึกเมื่อ: {'แคชไว้' if screenshot_res.get('cached') else 'ล่าสุด'})", use_container_width=True)
        else:
            err_msg = screenshot_res.get("error", "ไม่สามารถเปิดหน้าเว็บได้") if screenshot_res else "ยังไม่ได้แคปภาพ"
            st.error(f"❌ เกิดข้อผิดพลาดในการเปิดหน้าเว็บ: {err_msg}")
            st.info("💡 สามารถคลิกปุ่ม **เปิดดูหน้าเว็บจริง (Open URL)** ในคอลัมน์ด้านซ้ายเพื่อเปิดดูโดยตรงได้ครับ")

        st.markdown("---")
        st.markdown("### ✍️ แบบฟอร์มบันทึกผลการตรวจสอบโดยคน (Human QA)")
        
        status_options = [
            "✅ ข้อมูลถูกต้องตรงกับหน้าเว็บ (Match)",
            "⚠️ ข้อมูลบางส่วนไม่ตรง (Partial Discrepancy)",
            "❌ ข้อมูลผิดพลาดมาก/ไม่ตรง (Significant Error)",
            "🚫 ลิงก์เสีย / หน้าเว็บปิดประกาศ (404/Removed)"
        ]
        
        default_status_idx = 0
        if existing_qa.get("status"):
            for idx, opt in enumerate(status_options):
                if opt.startswith(existing_qa["status"][:2]):
                    default_status_idx = idx
                    break

        qa_status = st.radio("ผลการประเมิน:", status_options, index=default_status_idx, key=f"qa_stat_{item_key}")
        
        qa_issues = st.multiselect(
            "ข้อผิดพลาดที่พบ (ถ้ามี):",
            [
                "ราคาไม่ตรงกับหน้าเว็บ",
                "เนื้อที่ / ขนาดพื้นที่ไม่ตรง",
                "ทำเล / จังหวัด / ตำบลไม่ตรง",
                "ประเภททรัพย์ไม่ตรง",
                "รูปภาพ / โครงสร้างหน้าเว็บเปลี่ยน",
                "ข้อมูลบนเว็บมีแต่ Scraper ดึงไม่มา",
                "หน้าเว็บลบประกาศแล้ว (Inactive/404)"
            ],
            default=existing_qa.get("issues", []),
            key=f"qa_issue_{item_key}"
        )
        
        qa_note = st.text_area(
            "บันทึกข้อคิดเห็น / คำอธิบายเพิ่มเติม:",
            value=existing_qa.get("note", ""),
            placeholder="ระบุรายละเอียด เช่น หน้าเว็บระบุ 2 ห้องนอน แต่ใน CSV เป็นค่าว่าง...",
            key=f"qa_note_{item_key}"
        )
        
        if st.button("💾 บันทึกผลการตรวจรายการนี้", type="primary", use_container_width=True, key=f"save_qa_{item_key}"):
            save_qa_result(item_key, {
                "company": cur_company,
                "property_id": cur_id,
                "asset_code": cur_item.get("รหัสทรัพย์", ""),
                "title": cur_item.get("ชื่อประกาศ", ""),
                "price": cur_item.get("ราคา", ""),
                "url": cur_url,
                "status": qa_status,
                "issues": qa_issues,
                "note": qa_note
            })
            st.success("✅ บันทึกผลการตรวจสอบเรียบร้อยแล้ว!")
            time.sleep(0.5)
            st.rerun()

        if existing_qa:
            st.caption(f"🕒 ตรวจสอบล่าสุดเมื่อ: {existing_qa.get('verified_at', '-')}")

# ---------------------------------------------------------
# PAGE 3: QA VERIFICATION REPORT & EXPORT
# ---------------------------------------------------------
elif view_mode.startswith("📑"):
    st.markdown("## 📑 รายงานสรุปผลการตรวจสอบโดยคน (Human QA Report)")
    st.markdown("แสดงรายการทรัพย์ทั้งหมดที่ได้รับการตรวจประเมิน พร้อมสรุปปัญหาที่พบ และสามารถ Export เป็นไฟล์ Excel / CSV ได้")

    qa_records = load_qa_results()
    
    if not qa_records:
        st.info("ℹ️ ยังไม่มีรายการที่ได้รับการบันทึกผลการตรวจ กรุณาไปที่แท็บ **'🔍 สุ่มตรวจ & เทียบภาพหน้าเว็บจริง'** เพื่อเริ่มตรวจข้อมูล")
        st.stop()
        
    records_list = list(qa_records.values())
    report_df = pd.DataFrame(records_list)
    
    total_reviewed = len(report_df)
    match_count = sum(1 for r in records_list if "✅" in r.get("status", ""))
    discrepancy_count = sum(1 for r in records_list if "⚠️" in r.get("status", "") or "❌" in r.get("status", ""))
    broken_count = sum(1 for r in records_list if "🚫" in r.get("status", ""))
    
    rc1, rc2, rc3, rc4 = st.columns(4)
    with rc1:
        st.html(f"""
        <div class="metric-card">
            <div class="metric-title">📝 ตรวจแล้วทั้งหมด</div>
            <div class="metric-val">{total_reviewed}</div>
            <div class="metric-sub">รายการ</div>
        </div>
        """)
    with rc2:
        st.html(f"""
        <div class="metric-card">
            <div class="metric-title">✅ ข้อมูลถูกต้องตรงกัน</div>
            <div class="metric-val">{match_count}</div>
            <div class="metric-sub">{match_count/max(1,total_reviewed)*100:.1f}%</div>
        </div>
        """)
    with rc3:
        st.html(f"""
        <div class="metric-card">
            <div class="metric-title">⚠️ พบข้อมูลไม่ตรง</div>
            <div class="metric-val">{discrepancy_count}</div>
            <div class="metric-sub">{discrepancy_count/max(1,total_reviewed)*100:.1f}%</div>
        </div>
        """)
    with rc4:
        st.html(f"""
        <div class="metric-card">
            <div class="metric-title">🚫 ลิงก์เสีย / ปิดประกาศ</div>
            <div class="metric-val">{broken_count}</div>
            <div class="metric-sub">{broken_count/max(1,total_reviewed)*100:.1f}%</div>
        </div>
        """)

    st.markdown("---")
    st.subheader("📋 ตารางรายการผลการตรวจสอบ")
    
    display_report = report_df.copy()
    if "issues" in display_report.columns:
        display_report["issues"] = display_report["issues"].apply(lambda x: ", ".join(x) if isinstance(x, list) else str(x))
        
    display_report = display_report.rename(columns={
        "company": "บริษัท",
        "property_id": "ID",
        "asset_code": "รหัสทรัพย์",
        "title": "ชื่อประกาศ",
        "price": "ราคา",
        "url": "ลิงก์",
        "status": "ผลการตรวจ",
        "issues": "ปัญหาที่พบ",
        "note": "หมายเหตุ",
        "verified_at": "เวลาที่ตรวจ"
    })
    
    st.dataframe(display_report, use_container_width=True)
    
    exp_c1, exp_c2 = st.columns(2)
    with exp_c1:
        excel_buffer = io.BytesIO()
        with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
            display_report.to_excel(writer, index=False, sheet_name='QA_Report')
        st.download_button(
            label="📥 ดาวน์โหลดรายงานเป็น Excel (.xlsx)",
            data=excel_buffer.getvalue(),
            file_name=f"qa_verification_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
        
    with exp_c2:
        csv_data = display_report.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            label="📥 ดาวน์โหลดรายงานเป็น CSV (.csv)",
            data=csv_data,
            file_name=f"qa_verification_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            use_container_width=True
        )
