import os
import sys
from pathlib import Path
from PIL import Image
import pandas as pd
import streamlit as st

# Ensure project root is in sys.path
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if _BASE_DIR not in sys.path:
    sys.path.insert(0, _BASE_DIR)


# Core configuration & theme
from modules.config.theme import inject_global_theme_css

# Services
from modules.services.data_cleaner import ensure_derived_cols
from modules.services.data_loader import load_properties_data, get_data_mtime

# UI Components
from modules.ui.welcome_screen import render_welcome_screen
from modules.ui.sidebar import render_sidebar
from modules.ui.kpi_header import render_floating_kpi_cards

# Views
from modules.views.tab1_bubble import render_tab1_bubble_view
from modules.views.tab2_map import render_tab2_map_view
from modules.views.tab3_analytics import render_tab3_analytics_view
from modules.views.tab4_inventory import render_tab4_inventory_view

# ----------------- PAGE CONFIGURATION -----------------
_app_icon_file = os.path.join("logo", "app_icon.ico") if os.path.exists(os.path.join("logo", "app_icon.ico")) else os.path.join("assets", "app_icon.ico")
_app_page_icon = Image.open(_app_icon_file) if os.path.exists(_app_icon_file) else ":material/analytics:"

st.set_page_config(
    page_title="NOVA NPA Dashboard",
    page_icon=_app_page_icon,
    layout="wide",
    initial_sidebar_state="expanded"
)

# ----------------- PORTAL GATEWAY ENTRY CHECK -----------------
if "portal_entered" not in st.session_state:
    if st.query_params.get("portal") == "skip":
        st.session_state["portal_entered"] = True

if not st.session_state.get("portal_entered", False):
    render_welcome_screen()
    st.stop()

# ----------------- DATA LOADING & CACHING -----------------
data_mtime = get_data_mtime()
df_raw = load_properties_data(data_mtime)

# Merge user uploaded data if available (protect cache via explicit .copy())
if "imported_custom_df" in st.session_state and st.session_state["imported_custom_df"] is not None:
    imp_df = st.session_state["imported_custom_df"].copy()
    if 'บริษัท' not in imp_df.columns:
        imp_df['บริษัท'] = 'ไฟล์นำเข้า'
    imp_df = ensure_derived_cols(imp_df)
    if df_raw is not None and not df_raw.empty:
        df_raw = df_raw.copy()
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

if df_raw is None or df_raw.empty:
    st.markdown("""
    <div style="background-color: rgba(239, 68, 68, 0.08); border: 1px solid rgba(239, 68, 68, 0.2); border-radius: 12px; padding: 40px; text-align: center; margin-top: 50px; max-width: 800px; margin-left: auto; margin-right: auto; box-shadow: 0 10px 30px rgba(0,0,0,0.04);">
        <i class="fa-solid fa-triangle-exclamation" style="font-size: 4rem; color: #ef4444; margin-bottom: 20px;"></i>
        <h2 style="color: #ef4444; margin-bottom: 15px; font-weight: 700;">ไม่พบไฟล์ข้อมูล 'all_asset.parquet'</h2>
        <p style="color: #475569; font-size: 1rem;">กรุณารันคำสั่ง <code>python convert_csv_to_parquet.py</code> เพื่อแปลงไฟล์และเริ่มต้นใช้งานแดชบอร์ด</p>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

# ----------------- SIDEBAR & THEME SETUP -----------------
is_dark_mode = render_sidebar(df_raw)
inject_global_theme_css(is_dark_mode)

# ----------------- GLOBAL FLOATING KPI CARDS -----------------
render_floating_kpi_cards(df_raw, df_raw, is_dark_mode)

# ----------------- MAIN NAVIGATION TABS -----------------
with st.container(key="main_tabs_container"):
    tab1, tab2, tab3, tab4 = st.tabs([
        "ภาพรวม (Bubble Chart)",
        "แผนที่ (Interactive Map)",
        "สถิติ & วิเคราะห์",
        "รายการทรัพย์สิน",
    ], key="main_tabs")

# Tab 1: 3D Bubble Chart
with tab1:
    render_tab1_bubble_view(df_raw, is_dark_mode=is_dark_mode, has_active_filters=False)

# Tab 2: Interactive Deck.gl Map + Median Reference Analytics Fragment
with tab2:
    render_tab2_map_view(df_raw, df_raw, is_dark_mode=is_dark_mode)

# Tab 3: Competitor & Market Analytics
with tab3:
    render_tab3_analytics_view(df_raw, df_raw, is_dark_mode=is_dark_mode)

# Tab 4: Property Listing / Inventory Table
with tab4:
    render_tab4_inventory_view(df_raw, is_dark_mode=is_dark_mode)
