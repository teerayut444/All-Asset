import os
import time
import base64
import streamlit as st

from modules.services.data_loader import (
    load_properties_data,
    get_data_mtime,
    get_precomputed_map_payload,
    precompute_full_map_html,
    get_sam_project_options
)
from modules.services.geo_service import (
    load_raw_districts_geojson,
    load_raw_subdistricts_geojson,
    get_map_icon_atlas_and_mapping,
    get_leaflet_logo_dict
)
from bubble_chart import generate_3d_glossy_bubble_chart_html

def update_welcome_progress(placeholder, pct, status_text):
    """Renders a sleek luxury tech progress bar with live percentage on the welcome screen."""
    placeholder.html(f"""
    <div style="width: 290px; margin: 10px auto 6px auto; text-align: center; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Noto Sans Thai', 'Outfit', sans-serif;">
        <div style="display: flex; justify-content: space-between; font-size: 0.76rem; font-weight: 700; color: #064e3b; margin-bottom: 6px; letter-spacing: 0.2px;">
            <span style="color: {'#059669' if pct >= 100 else '#475569'}; font-weight: {'700' if pct >= 100 else '600'};">{status_text}</span>
            <span style="color: #059669; font-weight: 800;">{pct}%</span>
        </div>
        <div style="width: 100%; height: 6px; background: rgba(16, 185, 129, 0.14); border-radius: 9999px; overflow: hidden; box-shadow: inset 0 1px 2px rgba(0,0,0,0.06);">
            <div style="width: {pct}%; height: 100%; background: linear-gradient(90deg, #10b981 0%, #059669 100%); border-radius: 9999px; transition: width 0.3s ease;"></div>
        </div>
    </div>
    """)

def render_welcome_screen():
    """Renders elegant light luxury Welcome Portal with big 3D levitating icon, slow float, live loading progress %, and always-clickable enter button."""
    app_icon_b64 = ""
    icon_paths = [
        os.path.join("logo", "app_icon.png"),
        os.path.join("logo", "logo.png"),
        os.path.join("assets", "logo.png")
    ]
    for p in icon_paths:
        if os.path.exists(p):
            try:
                with open(p, "rb") as f_icon:
                    app_icon_b64 = base64.b64encode(f_icon.read()).decode("utf-8")
                if app_icon_b64:
                    break
            except Exception:
                pass

    st.html(f"""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@800;900&family=Outfit:wght@600;700;800;900&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
<style>
header[data-testid="stHeader"] {{
    background: transparent !important;
}}
section[data-testid="stSidebar"] {{
    display: none !important;
}}

html, body {{
    height: 100vh !important;
    overflow: hidden !important;
}}

div[data-testid="stAppViewBlockContainer"],
.main .block-container,
.block-container {{
    padding: 0 !important;
    max-width: 100% !important;
    height: 100vh !important;
    min-height: 100vh !important;
    display: flex !important;
    flex-direction: column !important;
    align-items: center !important;
    justify-content: center !important;
    overflow: hidden !important;
    margin: 0 auto !important;
}}

div[data-testid="stVerticalBlock"] {{
    display: flex !important;
    flex-direction: column !important;
    align-items: center !important;
    justify-content: center !important;
    width: 100% !important;
    gap: 0 !important;
}}

body, .stApp {{
    background: radial-gradient(circle at 50% 40%, #ffffff 0%, #f4fbf7 38%, #e8f7f0 70%, #dcf3e9 100%) !important;
    min-height: 100vh !important;
}}

.portal-stage-light {{
    position: relative;
    width: 320px;
    height: 310px;
    margin: 0 auto;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
}}

.portal-house-img {{
    width: 300px;
    height: 300px;
    object-fit: contain;
    filter: drop-shadow(0 24px 40px rgba(6, 78, 59, 0.18));
    animation: floatLevitate 7s ease-in-out infinite;
    user-select: none;
    -webkit-user-drag: none;
}}

.portal-ground-shadow {{
    width: 230px;
    height: 24px;
    background: radial-gradient(ellipse at center, rgba(16, 185, 129, 0.42) 0%, rgba(5, 150, 105, 0.14) 50%, transparent 75%);
    border-radius: 50%;
    margin-top: 14px;
    animation: shadowPulse 7s ease-in-out infinite;
}}

@keyframes floatLevitate {{
    0%, 100% {{ transform: translateY(0px); }}
    50% {{ transform: translateY(-26px); }}
}}

@keyframes shadowPulse {{
    0%, 100% {{
        transform: scale(1.12);
        opacity: 0.9;
        filter: blur(5px);
    }}
    50% {{
        transform: scale(0.62);
        opacity: 0.22;
        filter: blur(9px);
    }}
}}

.nova-light-title {{
    font-family: 'Montserrat', 'Outfit', sans-serif;
    font-size: 5.2rem;
    font-weight: 900;
    letter-spacing: 16px;
    background: linear-gradient(180deg, #022c22 0%, #064e3b 38%, #047857 70%, #059669 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin: 18px 0 4px 16px;
    line-height: 1.05;
    text-align: center;
    filter: drop-shadow(0 6px 18px rgba(5, 150, 105, 0.3));
}}

.nova-light-sub {{
    font-family: 'Outfit', sans-serif;
    font-size: 0.90rem;
    font-weight: 700;
    color: #475569;
    letter-spacing: 6px;
    text-transform: uppercase;
    text-align: center;
    margin: 6px 0 10px 6px;
}}
</style>

<div style="display: flex; flex-direction: column; align-items: center; justify-content: center; width: 100%; text-align: center;">
    <div class="portal-stage-light">
        <img class="portal-house-img" src="data:image/png;base64,{app_icon_b64}" alt="NOVA House Icon" />
        <div class="portal-ground-shadow"></div>
    </div>
    <div class="nova-light-title">NOVA</div>
    <div class="nova-light-sub">NPA ASSET INTELLIGENCE</div>
</div>
""")

    progress_slot = st.empty()

    if st.session_state.get("preload_done", False):
        update_welcome_progress(progress_slot, 100, "✓ ระบบและแผนที่พร้อมใช้งาน")
        st.session_state["portal_entered"] = True
        time.sleep(0.4)
        st.rerun()
    else:
        update_welcome_progress(progress_slot, 20, "กำลังโหลดฐานข้อมูลทรัพย์สิน...")
        df_p = load_properties_data(get_data_mtime())
        
        update_welcome_progress(progress_slot, 45, "กำลังอ่านพิกัดและขอบเขตแผนที่...")
        load_raw_districts_geojson()
        load_raw_subdistricts_geojson()
        
        update_welcome_progress(progress_slot, 75, "กำลังประมวลผลแผนที่ 442,077 จุด...")
        get_precomputed_map_payload(get_data_mtime())
        precompute_full_map_html(get_data_mtime())
        
        update_welcome_progress(progress_slot, 90, "กำลังเตรียมสัญลักษณ์และหมุดแผนที่...")
        get_map_icon_atlas_and_mapping()
        get_leaflet_logo_dict()
        if df_p is not None and not df_p.empty:
            get_sam_project_options(df_p)
            
        update_welcome_progress(progress_slot, 98, "กำลังเตรียมกราฟ 3D และสถิติภาพรวม...")
        if df_p is not None and not df_p.empty and "cached_bubble_html_v2" not in st.session_state:
            try:
                st.session_state["cached_bubble_html_v2"] = generate_3d_glossy_bubble_chart_html(df_p)
            except Exception:
                pass
                
        update_welcome_progress(progress_slot, 100, "✓ ระบบและแผนที่พร้อมใช้งาน")
        st.session_state["preload_done"] = True
        st.session_state["portal_entered"] = True
        time.sleep(0.35)
        st.rerun()
