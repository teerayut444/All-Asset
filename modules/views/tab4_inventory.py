import re
import numpy as np
import pandas as pd
import streamlit as st

from modules.config.constants import is_true_centroid
from modules.services.data_cleaner import to_float_sqwah, to_float_sqm, format_to_rai_ngan_wah
from modules.services.export_service import render_import_export_section

fragment_decorator = getattr(st, "fragment", lambda f: f)

# Project normalization patterns & Brand tags (aligned with Tab 2 Map)
_PROJECT_BRAND_MAP = {
    'ไอดิโอ': 'ไอดีโอ',
    'ideo': 'ไอดีโอ',
    'lumpini': 'ลุมพินี',
    'lpn': 'ลุมพินี',
    'pruksa': 'พฤกษา',
    'ps': 'พฤกษา',
    'supalai': 'ศุภาลัย',
    'aspire': 'แอสปาย',
    'dcondo': 'ดีคอนโด',
    'the base': 'เดอะเบส',
    'thebase': 'เดอะเบส',
    'เดอะ เบส': 'เดอะเบส',
    'เดอะเบส': 'เดอะเบส',
    'life': 'ไลฟ์',
    'rhythm': 'ริทึ่ม',
    'knightsbridge': 'ไนท์บริดจ์',
    'plum': 'พลัม',
    'casa': 'คาซ่า',
    'centric': 'เซ็นทริค',
    'condolette': 'คอนโดเลต',
    'u delight': 'ยูดีไลท์',
    'udelight': 'ยูดีไลท์',
    'chapter one': 'แชปเตอร์วัน',
    'chapterone': 'แชปเตอร์วัน',
    'regent': 'รีเจ้นท์',
    'noble': 'โนเบิล',
    'parkland': 'พาร์คแลนด์',
    'ashton': 'แอชตัน',
    'เอลลิโอ': 'เอลิโอ',
    'elio': 'เอลิโอ',
    'unio': 'ยูนิโอ',
    'modiz': 'โมดิซ',
    'atmoz': 'แอทโมซ',
    'kave': 'เคฟ',
}

_BRAND_TAG_PATTERNS = [
    (re.compile(r'ไอดีโอ|ไอดิโอ|ideo', re.I), 'IDEO / ไอดิโอ'),
    (re.compile(r'ลุมพินี|lumpini|lpn', re.I), 'LPN / Lumpini'),
    (re.compile(r'พฤกษา|pruksa|ps\b', re.I), 'Pruksa / PS'),
    (re.compile(r'ศุภาลัย|supalai', re.I), 'Supalai'),
    (re.compile(r'แอสปาย|aspire', re.I), 'Aspire'),
    (re.compile(r'ดีคอนโด|dcondo', re.I), 'Dcondo'),
    (re.compile(r'เดอะ\s*เบส|the\s*base', re.I), 'The Base'),
    (re.compile(r'ไลฟ์|life\b', re.I), 'Life'),
    (re.compile(r'ริทึ่ม|rhythm', re.I), 'Rhythm'),
    (re.compile(r'ไนท์บริดจ์|knightsbridge', re.I), 'Knightsbridge'),
    (re.compile(r'พลัม|plum', re.I), 'Plum'),
    (re.compile(r'คาซ่า|casa', re.I), 'Casa'),
    (re.compile(r'เซ็นทริค|centric', re.I), 'Centric'),
    (re.compile(r'คอนโดเลต|condolette', re.I), 'Condolette'),
    (re.compile(r'ยูดีไลท์|u\s*delight|udelight', re.I), 'U Delight'),
    (re.compile(r'แชปเตอร์วัน|chapter\s*one', re.I), 'Chapter One'),
    (re.compile(r'รีเจ้นท์|regent', re.I), 'Regent'),
    (re.compile(r'โนเบิล|noble', re.I), 'Noble'),
    (re.compile(r'พาร์คแลนด์|parkland', re.I), 'Parkland'),
    (re.compile(r'แอชตัน|ashton', re.I), 'Ashton'),
    (re.compile(r'เอลิโอ|เอลลิโอ|elio', re.I), 'Elio'),
    (re.compile(r'ยูนิโอ|unio', re.I), 'Unio'),
    (re.compile(r'โมดิซ|modiz', re.I), 'Modiz'),
    (re.compile(r'แอทโมซ|atmoz', re.I), 'Atmoz'),
    (re.compile(r'เคฟ|kave', re.I), 'Kave'),
]

_PREFIX_PAT = re.compile(
    r'^(คอนโด\s*โครงการ|โครงการ\s*คอนโด|โครงการ\s*หมู่บ้าน|อาคารชุด|คอนโดมิเนียม|มีเนียม|โครงการ|หมู่บ้าน|คอนโด|บ้านเดี่ยว|บ้านแฝด|บ้าน|ทาวน์โฮม|ทาวน์เฮ้าส์|ขายคอนโด)\s*',
    re.I
)
_SUFFIX_PAT = re.compile(
    r'(\[.*?\]|\(.*?\)|,\s*(กรุงเทพมหานคร|กรุงเทพฯ|กรุงเทพ|นนทบุรี|ปทุมธานี|สมุทรปราการ|ชลบุรี|เชียงใหม่|ระยอง|ภูเก็ต).*$|ชั้น\s*\d+.*$|\b(ติด|ใกล้)\s*(bts|mrt).*$)',
    re.I
)
_SPACE_CLEAN = re.compile(r'[\s\-_/.,:;()\[\]{}]+')

def normalize_project_name(s):
    """Normalizes project names to link variations (e.g. ไอดิโอ <-> ไอดีโอ <-> IDEO) like in Tab 2."""
    if not s or pd.isna(s):
        return ''
    txt = str(s).strip()
    if ' : ' in txt:
        parts = txt.split(' : ')
        txt = parts[1] if len(parts) > 1 else parts[0]
    while True:
        nt = _PREFIX_PAT.sub('', txt).strip()
        if nt == txt:
            break
        txt = nt
    txt = _SUFFIX_PAT.sub('', txt).strip()
    txt_lower = txt.lower()
    for b_from, b_to in _PROJECT_BRAND_MAP.items():
        txt_lower = re.sub(r'\b' + re.escape(b_from) + r'\b', b_to, txt_lower)
        txt_lower = txt_lower.replace(b_from, b_to)
    res = _SPACE_CLEAN.sub('', txt_lower)
    if res in ['บ้าน', 'คอนโด', 'ที่ดิน', 'ทาวน์โฮม', 'อาคารพาณิชย์', '']:
        return ''
    return res

def get_brand_search_tag(raw_name):
    """Returns alias search tag (e.g. IDEO / ไอดิโอ, LPN / Lumpini) to ensure instant search in Streamlit dropdown."""
    name_str = str(raw_name).strip()
    for pat, tag in _BRAND_TAG_PATTERNS:
        if pat.search(name_str):
            return tag
    return ""

@st.cache_data(ttl=3600, show_spinner=False)
def get_tab4_search_options(_df_filtered):
    """Build fast, memory-safe dropdown options for Tab 4 (SAM projects with competitor stats & SAM asset codes)."""
    sam_projs = []
    sam_codes = []
    proj_options = []
    proj_label_to_raw = {}
    proj_label_to_norm = {}

    if _df_filtered is None or _df_filtered.empty:
        return proj_options, sam_codes, proj_label_to_raw, proj_label_to_norm

    # 1. Extract SAM asset codes & raw project names
    if 'บริษัท' in _df_filtered.columns:
        sam_df = _df_filtered[_df_filtered['บริษัท'].astype(str).str.strip().str.upper() == 'SAM']
        if 'รหัสทรัพย์' in sam_df.columns:
            codes = sam_df['รหัสทรัพย์'].dropna().astype(str).str.strip()
            codes = codes[~codes.isin(['-', '', 'nan', 'None', 'ไม่ระบุ', 'undefined', 'null'])]
            sam_codes = sorted(codes.unique().tolist())
        if 'ชื่อโครงการ' in sam_df.columns:
            projs = sam_df['ชื่อโครงการ'].dropna().astype(str).str.strip()
            projs = projs[~projs.isin(['-', '', 'nan', 'None', 'ไม่ระบุ', 'undefined', 'โครงการไม่มีชื่อ', 'null'])]
            sam_projs = sorted(projs.unique().tolist())

    # 2. Normalize and compute Same-Project Competitor Statistics
    if 'ชื่อโครงการ' in _df_filtered.columns and sam_projs:
        raw_to_norm = {p: normalize_project_name(p) for p in sam_projs}
        all_sam_norm_keys = set(k for k in raw_to_norm.values() if k)

        # Build normalized keys across all projects in the dataset
        all_unique_projs = _df_filtered['ชื่อโครงการ'].dropna().astype(str).str.strip().unique()
        all_norm_map = {p: normalize_project_name(p) for p in all_unique_projs if p}

        # Vectorized lookup on subset
        df_sub = _df_filtered[['ชื่อโครงการ', 'บริษัท']].dropna().copy()
        df_sub['norm_k'] = df_sub['ชื่อโครงการ'].astype(str).str.strip().map(all_norm_map)
        matched = df_sub[df_sub['norm_k'].isin(all_sam_norm_keys)]

        sam_counts = matched[matched['บริษัท'].astype(str).str.strip().str.upper() == 'SAM'].groupby('norm_k').size()
        comp_df = matched[matched['บริษัท'].astype(str).str.strip().str.upper() != 'SAM']
        comp_counts = comp_df.groupby('norm_k').size()
        comp_companies = comp_df.groupby('norm_k')['บริษัท'].nunique()

        # Build formatted dropdown labels
        items = []
        for p in sam_projs:
            k = raw_to_norm.get(p, '')
            sc = int(sam_counts.get(k, 0)) if k else 0
            cc = int(comp_counts.get(k, 0)) if k else 0
            cj = int(comp_companies.get(k, 0)) if k else 0
            tag = get_brand_search_tag(p)
            tag_suffix = f"  [{tag}]" if tag else ""

            if cc > 0:
                label = f"{p}  ➔  SAM: {sc:,}  |  คู่แข่ง: {cj} เจ้า ({cc:,} ทรัพย์){tag_suffix}"
            else:
                label = f"{p}  ➔  SAM: {sc:,}  |  ไม่มีคู่แข่ง{tag_suffix}"

            items.append((label, cc, sc, p, k))
            proj_label_to_raw[label] = p
            proj_label_to_norm[label] = k

        # Sort: Projects with competitor comparisons first (most competitor assets first), then most SAM assets, then Thai alphabet
        items.sort(key=lambda x: (1 if x[1] > 0 else 0, x[1], x[2]), reverse=True)
        proj_options = [x[0] for x in items]

    return proj_options, sam_codes, proj_label_to_raw, proj_label_to_norm

@fragment_decorator
def render_tab4_inventory_view(df_filtered, is_dark_mode):
    """
    Renders Tab 4: Property Listing / Inventory Explorer:
    - Searchable multi-select dropdowns (รหัสทรัพย์, โครงการเดียวกับ SAM)
    - Row limit controller
    - Smart quick sort presets (Min/Max price, cheapest sqm/sqw, latest update, largest area)
    - Formatted columns with LandsMaps link, coordinates precision, and currency formatting
    - CSV/Excel export section
    """
    if df_filtered is None or df_filtered.empty:
        st.warning("ไม่พบข้อมูลตามเงื่อนไข")
        return

    st.markdown(f"### <i class='fa-solid fa-table-list' style='color:#059669; margin-right:8px;'></i>รายการทรัพย์สินที่ค้นพบ ({len(df_filtered):,} รายการ)", unsafe_allow_html=True)
    
    # Preload options (SAM projects with competitor stats & SAM asset codes)
    proj_options, code_options, proj_label_to_raw, proj_label_to_norm = get_tab4_search_options(df_filtered)

    col_code, col_proj, col_limit = st.columns([1.8, 2.2, 0.8], gap="medium")
    with col_code:
        st.markdown(
            f"<div style='font-size:0.875rem; font-weight:600; margin-bottom:4px; color:{'#f8fafc' if is_dark_mode else '#0f172a'}; display:flex; align-items:center; gap:6px;'>"
            f"<i class='fa-solid fa-barcode' style='color:#059669;'></i><span>รหัสทรัพย์ (SAM)</span>"
            f"</div>",
            unsafe_allow_html=True
        )
        selected_codes = st.multiselect(
            "รหัสทรัพย์",
            options=code_options,
            default=[],
            placeholder="พิมพ์หรือเลือกค้นหารหัสทรัพย์ของ SAM...",
            label_visibility="collapsed",
            key="tab4_multiselect_code"
        )

    with col_proj:
        st.markdown(
            f"<div style='font-size:0.875rem; font-weight:600; margin-bottom:4px; color:{'#f8fafc' if is_dark_mode else '#0f172a'}; display:flex; align-items:center; gap:6px;'>"
            f"<i class='fa-solid fa-city' style='color:#059669;'></i><span>โครงการเดียวกับ SAM</span>"
            f"</div>",
            unsafe_allow_html=True
        )
        selected_projs = st.multiselect(
            "โครงการเดียวกับ SAM",
            options=proj_options,
            default=[],
            placeholder="เลือกหรือพิมพ์ค้นหาโครงการเดียวกับ SAM...",
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

        # 2. Filter by Projects (Same-project matching including name variations as in Tab 2)
        if selected_projs:
            selected_raw_names = set(proj_label_to_raw.get(l, l) for l in selected_projs)
            selected_norm_keys = {proj_label_to_norm.get(l, normalize_project_name(l)) for l in selected_projs}
            selected_norm_keys = {k for k in selected_norm_keys if k}

            if 'ชื่อโครงการ' in df_table_source.columns:
                proj_col_clean = df_table_source['ชื่อโครงการ'].astype(str).str.strip()
                # 1. Exact raw name match
                mask_raw = proj_col_clean.isin(selected_raw_names)
                # 2. Normalized name match (e.g. ไอดิโอ, ไอดีโอ, IDEO)
                norm_series = proj_col_clean.map(lambda s: normalize_project_name(s))
                mask_norm = norm_series.isin(selected_norm_keys) if selected_norm_keys else pd.Series(False, index=df_table_source.index)
                df_table_source = df_table_source[mask_raw | mask_norm]

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
            filter_parts.append(f"รหัสทรัพย์ที่เลือก {len(selected_codes):,} รายการ (SAM)")
        if selected_projs:
            filter_parts.append(f"โครงการเดียวกับ SAM {len(selected_projs):,} โครงการ")

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
    if not df_table_source.empty:
        render_import_export_section(df_table_source, filename_prefix="npa_property_listing", key_suffix="tab4")
