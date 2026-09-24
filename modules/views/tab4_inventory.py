import re
import numpy as np
import pandas as pd
import streamlit as st

from modules.config.constants import is_true_centroid
from modules.services.data_cleaner import to_float_sqwah, to_float_sqm, format_to_rai_ngan_wah
from modules.services.export_service import render_import_export_section

@st.cache_data(ttl=3600, show_spinner=False)
def get_tab4_search_options(df_filtered):
    """Build fast, memory-safe dropdown options for Tab 4 across all companies."""
    # 1. Projects specifically from SAM properties
    sam_projs = []
    if 'บริษัท' in df_filtered.columns and 'ชื่อโครงการ' in df_filtered.columns:
        sam_df = df_filtered[df_filtered['บริษัท'].astype(str).str.strip().str.upper() == 'SAM']
        projs = sam_df['ชื่อโครงการ'].dropna().astype(str).str.strip()
        projs = projs[~projs.isin(['-', '', 'nan', 'None', 'ไม่ระบุ', 'undefined', 'โครงการไม่มีชื่อ', 'null'])]
        sam_projs = sorted(projs.unique().tolist())
    elif 'ชื่อโครงการ' in df_filtered.columns:
        projs = df_filtered['ชื่อโครงการ'].dropna().astype(str).str.strip()
        projs = projs[~projs.isin(['-', '', 'nan', 'None', 'ไม่ระบุ', 'undefined', 'โครงการไม่มีชื่อ', 'null'])]
        sam_projs = sorted(projs.value_counts().head(2000).index.tolist())

    # 2. Comprehensive asset codes across all 14 companies (safe ~35k size for browser)
    code_list = []
    if 'บริษัท' in df_filtered.columns and 'รหัสทรัพย์' in df_filtered.columns:
        # Full 100% of SAM, KTB, SCB, GSB, Chayo555
        for comp in ['SAM', 'KTB', 'SCB', 'GSB', 'Chayo555']:
            sub = df_filtered[df_filtered['บริษัท'] == comp]['รหัสทรัพย์'].dropna().astype(str).str.strip()
            code_list.extend(sub.unique().tolist())
        # Balanced quotas for others
        quotas = {
            'BAM': 4000, 'KBANK': 3000, 'GHB': 3000, 'LED': 4000,
            'Baania': 1000, 'NaYoo': 1000, 'Livinginsider': 1500,
            'DDproperty': 1500, 'ZmyHome': 1000
        }
        for comp, q in quotas.items():
            sub = df_filtered[df_filtered['บริษัท'] == comp]['รหัสทรัพย์'].dropna().astype(str).str.strip()
            code_list.extend(sub.head(q).unique().tolist())
    elif 'รหัสทรัพย์' in df_filtered.columns:
        sub = df_filtered['รหัสทรัพย์'].dropna().astype(str).str.strip()
        code_list = sub.head(25000).unique().tolist()

    clean_codes = sorted(list(set(c for c in code_list if c and c not in ['-', '', 'nan', 'None', 'null', 'undefined'])))
    return sam_projs, clean_codes

def render_tab4_inventory_view(df_filtered, is_dark_mode):
    """
    Renders Tab 4: Property Listing / Inventory Explorer:
    - Searchable multi-select dropdowns (รหัสทรัพย์, ชื่อโครงการ)
    - Row limit controller
    - Smart quick sort presets (Min/Max price, cheapest sqm/sqw, latest update, largest area)
    - Formatted columns with LandsMaps link, coordinates precision, and currency formatting
    - CSV/Excel export section
    """
    if df_filtered is None or df_filtered.empty:
        st.warning("ไม่พบข้อมูลตามเงื่อนไข")
        return

    st.markdown(f"### <i class='fa-solid fa-table-list' style='color:#059669; margin-right:8px;'></i>รายการทรัพย์สินที่ค้นพบ ({len(df_filtered):,} รายการ)", unsafe_allow_html=True)
    
    # Preload options (SAM projects & all-company asset codes)
    proj_options, code_options = get_tab4_search_options(df_filtered)

    col_code, col_proj, col_limit = st.columns([1.8, 2.2, 0.8], gap="medium")
    with col_code:
        st.markdown(
            f"<div style='font-size:0.875rem; font-weight:600; margin-bottom:4px; color:{'#f8fafc' if is_dark_mode else '#0f172a'}; display:flex; align-items:center; gap:6px;'>"
            f"<i class='fa-solid fa-barcode' style='color:#059669;'></i><span>รหัสทรัพย์ (Dropdown ทุกบริษัท)</span>"
            f"</div>",
            unsafe_allow_html=True
        )
        selected_codes = st.multiselect(
            "รหัสทรัพย์",
            options=code_options,
            default=[],
            placeholder="พิมพ์เพื่อค้นหา หรือเลือกจาก Dropdown...",
            label_visibility="collapsed",
            key="tab4_multiselect_code"
        )

    with col_proj:
        st.markdown(
            f"<div style='font-size:0.875rem; font-weight:600; margin-bottom:4px; color:{'#f8fafc' if is_dark_mode else '#0f172a'}; display:flex; align-items:center; gap:6px;'>"
            f"<i class='fa-solid fa-city' style='color:#059669;'></i><span>ชื่อโครงการ (SAM)</span>"
            f"</div>",
            unsafe_allow_html=True
        )
        selected_projs = st.multiselect(
            "ชื่อโครงการ",
            options=proj_options,
            default=[],
            placeholder="พิมพ์หรือเลือกโครงการของ SAM...",
            label_visibility="collapsed",
            key="tab4_multiselect_proj"
        )

    with col_limit:
        display_limit = st.number_input(
            "แสดงผล (แถว)",
            icon=":material/format_list_numbered:",
            min_value=0,
            max_value=100000,
            value=0,
            step=50,
            key="tab4_direct_row_limit",
            help="กำหนดจำนวนแถวที่ต้องการแสดงในตาราง (ค่าเริ่มต้นคือ 0 เพื่อความรวดเร็ว)"
        )
        display_limit = int(display_limit)

    # Quick Sort & Filter Presets
    quick_presets = [
        "ค่าเริ่มต้น", 
        "ยอดเข้าชมสูงสุด (Top 100)",
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

    has_active_search = bool(selected_codes or selected_projs)

    # Fast Tab 4 Data Pipeline
    if display_limit == 0 and not has_active_search and selected_quick_sort == "ค่าเริ่มต้น":
        df_table = df_filtered.head(0)
        df_table_source = df_table
        active_sort_label = ""
    else:
        df_table_source = df_filtered

        # 1. Filter by Asset Codes (selected from Dropdown)
        if selected_codes:
            code_set = set(selected_codes)
            mask_code = pd.Series(False, index=df_table_source.index)
            if 'รหัสทรัพย์' in df_table_source.columns:
                mask_code = mask_code | df_table_source['รหัสทรัพย์'].astype(str).str.strip().isin(code_set)
            if 'ID' in df_table_source.columns:
                mask_code = mask_code | df_table_source['ID'].astype(str).str.strip().isin(code_set)
            df_table_source = df_table_source[mask_code]

        # 2. Filter by Projects (from SAM projects dropdown)
        if selected_projs:
            proj_set = set(selected_projs)
            if 'ชื่อโครงการ' in df_table_source.columns:
                mask_proj = df_table_source['ชื่อโครงการ'].astype(str).str.strip().isin(proj_set)
                df_table_source = df_table_source[mask_proj]

        # Apply Quick Sort logic
        active_sort_label = ""
        if selected_quick_sort == "ยอดเข้าชมสูงสุด (Top 100)":
            if 'ยอดเข้าชม' in df_table_source.columns:
                p_mask = df_table_source['ยอดเข้าชม'].notna() & (pd.to_numeric(df_table_source['ยอดเข้าชม'], errors='coerce') > 0)
                df_table_source = df_table_source[p_mask].sort_values(by='ยอดเข้าชม', ascending=False)
            active_sort_label = "ยอดเข้าชมสูงสุด (ยอดวิวมากไปน้อย)"
        elif selected_quick_sort == "ราคาต่ำสุด (Top 100)":
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

        # Slice the requested number of rows
        if display_limit > 0:
            df_table = df_table_source.head(display_limit)
        elif has_active_search or selected_quick_sort != "ค่าเริ่มต้น":
            df_table = df_table_source.head(100)
        else:
            df_table = df_table_source.head(0)

    # Status summary card
    status_bg = '#1e293b' if is_dark_mode else '#f8fafc'
    status_border = '#334155' if is_dark_mode else '#e2e8f0'
    status_text_color = '#cbd5e1' if is_dark_mode else '#475569'

    if display_limit == 0 and not has_active_search and selected_quick_sort == "ค่าเริ่มต้น":
        st.markdown(
            f"""<div style="background:{status_bg}; border:1px solid {status_border}; border-radius:8px; padding:6px 12px; margin: 8px 0 10px 0; font-size:0.83rem; color:{status_text_color}; display:flex; align-items:center; gap:8px;">
                <i class="fa-solid fa-circle-info" style="color:#059669;"></i>
                <span>ปัจจุบันแสดงเฉพาะ <b>หัวข้อคอลัมน์</b> เพื่อความเร็วสูงสุด (พิมพ์รหัสทรัพย์ หรือชื่อโครงการด้านบน เพื่อเริ่มค้นหา)</span>
            </div>""",
            unsafe_allow_html=True
        )
    elif has_active_search:
        filter_parts = []
        if selected_codes:
            filter_parts.append(f"รหัสทรัพย์ที่เลือก {len(selected_codes):,} รายการ")
        if selected_projs:
            filter_parts.append(f"โครงการที่เลือก {len(selected_projs):,} โครงการ (SAM)")

        filter_desc = " และ ".join(filter_parts) if filter_parts else "ตัวเลือกที่ระบุ"
        st.markdown(
            f"""<div style="background:{status_bg}; border:1px solid {status_border}; border-radius:8px; padding:6px 12px; margin: 8px 0 10px 0; font-size:0.83rem; color:{status_text_color}; display:flex; align-items:center; gap:8px;">
                <i class="fa-solid fa-filter" style="color:#059669;"></i>
                <span>พบข้อมูลตรงตามเงื่อนไข ({filter_desc}) <b>{len(df_table_source):,}</b> รายการ (แสดง <b>{len(df_table):,}</b> รายการแรกในตาราง)</span>
            </div>""",
            unsafe_allow_html=True
        )
    else:
        sort_info_str = f" | จัดเรียง: <b>{active_sort_label}</b>" if active_sort_label else ""
        total_matches = len(df_table_source) if len(df_table_source) > 0 else len(df_filtered)
        st.markdown(
            f"""<div style="background:{status_bg}; border:1px solid {status_border}; border-radius:8px; padding:6px 12px; margin: 8px 0 10px 0; font-size:0.83rem; color:{status_text_color}; display:flex; align-items:center; gap:8px;">
                <i class="fa-solid fa-table" style="color:#059669;"></i>
                <span>แสดงข้อมูล <b>{len(df_table):,}</b> รายการ จากที่พบทั้งหมด <b>{total_matches:,}</b> รายการ{sort_info_str}</span>
            </div>""",
            unsafe_allow_html=True
        )
        
    df_table_show = df_table.copy()
    
    # Prepare clean numeric columns on sliced subset only
    if not df_table_show.empty:
        df_table_show['รูปแปลงที่ดิน'] = df_table_show['บริษัท'].apply(
            lambda c: "https://landsmaps.dol.go.th/" if str(c).strip().upper() == "LED" else None
        )
        df_table_show['ความแม่นยำพิกัด'] = df_table_show.apply(
            lambda r: "กึ่งกลางตำบล" if is_true_centroid(r.get('is_centroid'), r.get('บริษัท')) else "พิกัดแปลงจริง",
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
        "ห้องนอน", "ห้องน้ำ", "ที่จอดรถ", "ชั้น", "วันประกาศ", "ยอดเข้าชม", "ยอดคลิก"
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
            "ยอดเข้าชม": st.column_config.NumberColumn("ยอดเข้าชม (วิว)", format="%,d"),
            "ยอดคลิก": st.column_config.NumberColumn("ยอดคลิก", format="%,d"),
            "ละติจูด": st.column_config.NumberColumn(format="%.6f"),
            "ลองจิจูด": st.column_config.NumberColumn(format="%.6f"),
            "ความแม่นยำพิกัด": st.column_config.TextColumn("ความแม่นยำพิกัด", help="ระบุว่าเป็นพิกัดแปลงจริงจากประกาศ หรือพิกัดจุดกึ่งกลางตำบล/อำเภอ"),
            "ชั้น": st.column_config.TextColumn("ชั้น", help="ชั้นที่ตั้งของทรัพย์สิน หรือจำนวนชั้นของอาคาร"),
            "ลิงก์": st.column_config.LinkColumn("ลิงก์ประกาศ", display_text="เปิดดูทรัพย์"),
            "รูปแปลงที่ดิน": st.column_config.LinkColumn("รูปแปลงที่ดิน (LED)", display_text="LandsMaps", help="คลิกเพื่อเปิดระบบค้นหารูปแปลงที่ดิน กรมที่ดิน (เฉพาะกรมบังคับคดี)")
        }
    )
    render_import_export_section(df_table_source if not df_table_source.empty else df_filtered, filename_prefix="npa_property_listing", key_suffix="tab4")
