import os
import json
import base64
import gzip
import numpy as np
import pandas as pd
import streamlit as st
import streamlit.components.v1 as stc

from modules.services.geo_service import (
    get_boundary_geojson_features,
    get_map_icon_atlas_and_mapping,
    get_leaflet_logo_dict
)
from modules.services.data_loader import (
    precompute_full_map_html,
    get_data_mtime,
    get_precomputed_map_payload,
    get_base_map_html,
    get_sam_project_options
)
from modules.views.tab2_fragment import render_tab2_reference_analytics_fragment

def render_tab2_map_view(df_raw, df_filtered, is_dark_mode):
    """
    Renders Tab 2: Interactive Leaflet Map with Deck.gl point visualization,
    in-map controls, search sync, boundary layers, and reference analytics fragment.
    """
    with st.container(key="tab_map"):
        # TOP IN-PAGE FILTERS & REFERENCE POINT PICKER (FontAwesome Icons)
        st.markdown('<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">', unsafe_allow_html=True)

        tab2_regions = []
        tab2_provs = st.session_state.get("tab2_filter_provinces", [])
        tab2_dists = st.session_state.get("tab2_filter_districts", [])
        tab2_subdists = st.session_state.get("tab2_filter_subdistricts", [])
        tab2_types = []

        # Resolve active reference point
        active_ref_prop = st.session_state.get("tab2_ref_prop")
        active_ref_lat = None
        active_ref_lon = None
        try:
            active_ref_radius = float(st.query_params.get("map_ref_radius", 5.0))
        except (ValueError, TypeError):
            active_ref_radius = 5.0

        # Check if reference property ID came from map search, click, or query params
        q_id = st.query_params.get("map_ref_id")
        search_prop_id = q_id or st.session_state.get("tab2_search_prop_id", "")

        if search_prop_id and search_prop_id.strip():
            clean_id = search_prop_id.strip()
            if active_ref_prop is None or str(active_ref_prop.get('รหัสทรัพย์', '')).strip().lower() != clean_id.lower():
                if df_raw is not None and not df_raw.empty:
                    match_df = df_raw[df_raw['รหัสทรัพย์'].astype(str).str.strip().str.lower() == clean_id.lower()]
                    if not match_df.empty:
                        r0 = match_df.iloc[0]
                        if pd.notna(r0.get('ละติจูด')) and pd.notna(r0.get('ลองจิจูด')) and float(r0['ละติจูด']) > 0 and float(r0['ลองจิจูด']) > 0:
                            active_ref_prop = r0.to_dict()
                            active_ref_lat = float(r0['ละติจูด'])
                            active_ref_lon = float(r0['ลองจิจูด'])
                            st.session_state["tab2_ref_lat"] = active_ref_lat
                            st.session_state["tab2_ref_lon"] = active_ref_lon
                            st.session_state["tab2_ref_prop"] = active_ref_prop
                            st.session_state["tab2_search_prop_id"] = clean_id
                            p_prov = str(r0.get('จังหวัด', '')).strip()
                            p_dist = str(r0.get('อำเภอ', '')).strip()
                            p_subdist = str(r0.get('ตำบล', '')).strip()
                            if p_prov and p_prov not in ['-', 'ไม่มีข้อมูล', 'nan']:
                                st.session_state["tab2_filter_provinces"] = [p_prov]
                                st.query_params["map_prov"] = p_prov
                            if p_dist and p_dist not in ['-', 'ไม่มีข้อมูล', 'nan']:
                                st.session_state["tab2_filter_districts"] = [p_dist]
                                st.query_params["map_dist"] = p_dist
                            if p_subdist and p_subdist not in ['-', 'ไม่มีข้อมูล', 'nan']:
                                st.session_state["tab2_filter_subdistricts"] = [p_subdist]
                                st.query_params["map_subdist"] = p_subdist
            else:
                active_ref_lat = float(active_ref_prop.get('ละติจูด', 0))
                active_ref_lon = float(active_ref_prop.get('ลองจิจูด', 0))

        if active_ref_lat is None:
            q_lat = st.query_params.get("map_ref_lat")
            q_lon = st.query_params.get("map_ref_lon")
            if q_lat and q_lon:
                try:
                    active_ref_lat = float(q_lat)
                    active_ref_lon = float(q_lon)
                    if active_ref_prop is not None:
                        p_lat = float(active_ref_prop.get('ละติจูด', 0))
                        p_lon = float(active_ref_prop.get('ลองจิจูด', 0))
                        if abs(p_lat - active_ref_lat) > 0.0005 or abs(p_lon - active_ref_lon) > 0.0005:
                            active_ref_prop = None
                            st.session_state["tab2_ref_prop"] = None
                            st.session_state["tab2_search_prop_id"] = ""
                            st.session_state["tab2_input_prop_id"] = ""
                except ValueError:
                    pass
            elif st.session_state.get("tab2_ref_lat") and st.session_state.get("tab2_ref_lon"):
                active_ref_lat = float(st.session_state["tab2_ref_lat"])
                active_ref_lon = float(st.session_state["tab2_ref_lon"])

        # 3. MAP DATA (Keep full dataset in map so client-side in-map filters and dropdowns work in real-time)
        tab2_filtered = df_filtered.copy() if df_filtered is not None else pd.DataFrame()
        if tab2_regions and not tab2_filtered.empty and 'ภาค' in tab2_filtered.columns:
            tab2_filtered = tab2_filtered[tab2_filtered['ภาค'].isin(tab2_regions)]

        effective_provs = st.session_state.get("tab2_filter_provinces", []) or st.session_state.get("selected_provinces", [])
        effective_dists = st.session_state.get("tab2_filter_districts", []) or st.session_state.get("selected_districts_formatted", [])
        effective_subdists = st.session_state.get("tab2_filter_subdistricts", []) or st.session_state.get("selected_subdistricts_formatted", [])
        current_prov_str = effective_provs[0] if (effective_provs and len(effective_provs) > 0) else ""

        # Map Rendering (Deck.gl OpenStreetMap Map with dynamic marker mode, compass, and slider)
        is_nationwide_default = (
            not tab2_regions and
            (len(tab2_filtered) == len(df_raw) if (df_raw is not None and not df_raw.empty) else True)
        )

        # INSTANT PATH: Use fully pre-assembled HTML from welcome screen preload (0ms data prep)
        _instant_rendered = False
        if is_nationwide_default and "cached_map_html_base" not in st.session_state:
            precompute_full_map_html(get_data_mtime())

        if (is_nationwide_default and
            "cached_map_html_base" in st.session_state and
            st.session_state.get("cached_map_data_len", 0) > 0):

            _instant_html = st.session_state["cached_map_html_base"]
            _body_cls = "dark-theme" if is_dark_mode else ""
            _instant_html = _instant_html.replace("BODY_CLASS_PLACEHOLDER", _body_cls)
            _instant_html = _instant_html.replace("INIT_REF_LAT_PLACEHOLDER", str(active_ref_lat) if active_ref_lat else "")
            _instant_html = _instant_html.replace("INIT_REF_LON_PLACEHOLDER", str(active_ref_lon) if active_ref_lon else "")
            _instant_html = _instant_html.replace("INIT_RADIUS_PLACEHOLDER", str(active_ref_radius) if active_ref_radius else "5.0")
            _instant_html = _instant_html.replace("INIT_REF_ID_PLACEHOLDER", str(st.session_state.get("tab2_search_prop_id") or st.query_params.get("map_ref_id") or search_prop_id or "").strip())
            
            boundary_obj = get_boundary_geojson_features(effective_provs, effective_dists, effective_subdists) if effective_provs else None
            boundary_json = json.dumps(boundary_obj, ensure_ascii=False) if boundary_obj else "null"
            _instant_html = _instant_html.replace("BOUNDARY_GEOJSON_PLACEHOLDER", boundary_json)
            _instant_html = _instant_html.replace("CURRENT_PROV_PLACEHOLDER", current_prov_str)

            try:
                stc.html(_instant_html, height=870)
                _instant_rendered = True
            except Exception:
                pass
            if not _instant_rendered:
                try:
                    st.html(_instant_html, unsafe_allow_javascript=True)
                    _instant_rendered = True
                except Exception:
                    pass
            if not _instant_rendered:
                st.error("ไม่สามารถแสดงแผนที่ได้ กรุณาลองรีเฟรชหน้าเว็บ")
                _instant_rendered = True

        # FALLBACK PATH: Full computation for filtered views or when cache is not ready
        if not _instant_rendered:
            progress_bar = None
            if is_nationwide_default:
                csv_base64, lookup_b64, legend_content, map_data_full_len = get_precomputed_map_payload(get_data_mtime())
                map_data_empty = (map_data_full_len == 0)
            else:
                progress_bar = st.progress(0, text="กำลังเตรียมข้อมูลแผนที่...")
                progress_bar.progress(20, text="กำลังกรองจุดพิกัดในประเทศไทย (20%)...")

                map_data = tab2_filtered[
                    tab2_filtered['ละติจูด'].notna() & tab2_filtered['ลองจิจูด'].notna() &
                    tab2_filtered['ละติจูด'].between(5, 21) & tab2_filtered['ลองจิจูด'].between(97, 106)
                ].copy()

                map_data_full_len = len(map_data)
                map_data_empty = map_data.empty

                if not map_data_empty:
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

                    title_col = 'ชื่อประกาศ' if 'ชื่อประกาศ' in map_data.columns else ('ชื่อโครงการ' if 'ชื่อโครงการ' in map_data.columns else 'รหัสทรัพย์')
                    titles = map_data[title_col].fillna('ไม่มีชื่อ').astype(str).str.strip().str[:80].tolist()
                    ids = map_data['รหัสทรัพย์'].fillna('-').astype(str).str.strip().tolist()
                    prices_list = map_data['ราคาขาย'].astype(str).tolist()

                    # Centroid flag: is_centroid column OR LED company
                    led_mask = map_data['บริษัท'].fillna('').astype(str).str.upper().str.strip() == 'LED'
                    if 'is_centroid' in map_data.columns:
                        centroid_mask = (map_data['is_centroid'].fillna(False).astype(bool)) | led_mask
                    else:
                        centroid_mask = led_mask

                    centroid_flags = centroid_mask.astype('uint8').tolist()
                    centroid_per_company = map_data.loc[centroid_mask, 'บริษัท'].fillna('-').value_counts().to_dict()
                    centroid_per_type = map_data.loc[centroid_mask, 'ประเภททรัพย์'].fillna('-').value_counts().to_dict()

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

                    if 'ลิงก์' in map_data.columns:
                        _lnk = map_data['ลิงก์'].fillna('').astype(str).str.strip()
                        links = _lnk.where(~_lnk.isin(['', 'nan', 'None', '-']), '').tolist()
                    else:
                        links = [''] * len(map_data)

                    progress_bar.progress(80, text="กำลังบีบอัด GZIP และแปลงเป็น Base64 (80%)...")
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
                    _prj_col = map_data['โครงการ'].fillna('-').astype(str).str.strip() if 'โครงการ' in map_data.columns else (
                        map_data['ชื่อโครงการ'].fillna('-').astype(str).str.strip() if 'ชื่อโครงการ' in map_data.columns else pd.Series(['-'] * len(map_data), index=map_data.index)
                    )
                    _prj_col = _prj_col.replace({'': '-', 'nan': '-', 'None': '-', 'null': '-', 'undefined': '-'})
                    _prj_cat = pd.Categorical(_prj_col)

                    sam_projs_list, _ = get_sam_project_options(df_raw) if df_raw is not None and not df_raw.empty else ([], {})
                    lookup_obj = {
                        'co': _co_cat.categories.tolist(),
                        'ty': _ty_cat.categories.tolist(),
                        'pv': _pv_cat.categories.tolist(),
                        'st': _st_cat.categories.tolist(),
                        'rg': _rg_cat.categories.tolist(),
                        'dt': _dt_cat.categories.tolist(),
                        'subdt': _subdt_cat.categories.tolist(),
                        'prj': _prj_cat.categories.tolist(),
                        'sam_prj': sam_projs_list,
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
                        '_prji':  _prj_cat.codes.astype('int32'),
                        '_p':     _prices_num.fillna(0).astype('float32').values,
                        '_up':    _unit_prices.astype('float32'),
                        '_sqw':   np.nan_to_num(_sqw_calc, nan=0.0).round(1).astype('float32'),
                        '_sqm':   np.nan_to_num(_sqm_calc, nan=0.0).round(1).astype('float32'),
                        '_puw':   np.nan_to_num(_p_wah_calc, nan=0.0).round(0).astype('float32'),
                        '_pum':   np.nan_to_num(_p_sqm_calc, nan=0.0).round(0).astype('float32'),
                        '_price_str': prices_list,
                        '_link':     links,
                        '_centroid': centroid_flags,
                        '_deed':     deeds,
                    })
                    csv_base64 = base64.b64encode(
                        gzip.compress(
                            csv_df.to_csv(index=False).encode('utf-8'),
                            compresslevel=1
                        )
                    ).decode('utf-8')

            if map_data_empty:
                if progress_bar:
                    progress_bar.empty()
                st.warning("ไม่พบพิกัดตำแหน่ง ละติจูด/ลองจิจูด ในรายการทรัพย์สินที่คุณเลือกค้นหา")
            else:
                _tmpl_path = "static/map_template.html"
                _tmpl_mtime = os.path.getmtime(_tmpl_path) if os.path.exists(_tmpl_path) else None
                base_tmpl = get_base_map_html(_tmpl_mtime)

                atlas_uri, icon_mapping = get_map_icon_atlas_and_mapping(128)
                icon_mapping_json = json.dumps(icon_mapping, ensure_ascii=False)

                html_content = base_tmpl.replace("CSV_BASE64_PLACEHOLDER", csv_base64)
                html_content = html_content.replace("LOOKUP_BASE64_PLACEHOLDER", lookup_b64)
                html_content = html_content.replace("LEGEND_ITEMS_PLACEHOLDER", legend_content)
                body_theme_class = "dark-theme" if is_dark_mode else ""
                html_content = html_content.replace("BODY_CLASS_PLACEHOLDER", body_theme_class)
                html_content = html_content.replace("ATLAS_BASE64_PLACEHOLDER", atlas_uri)
                html_content = html_content.replace("ICON_MAPPING_PLACEHOLDER", icon_mapping_json)
                html_content = html_content.replace("INIT_REF_LAT_PLACEHOLDER", str(active_ref_lat) if active_ref_lat else "")
                html_content = html_content.replace("INIT_REF_LON_PLACEHOLDER", str(active_ref_lon) if active_ref_lon else "")
                html_content = html_content.replace("INIT_RADIUS_PLACEHOLDER", str(active_ref_radius) if active_ref_radius else "5.0")
                html_content = html_content.replace("INIT_REF_ID_PLACEHOLDER", str(st.session_state.get("tab2_search_prop_id") or st.query_params.get("map_ref_id") or search_prop_id or "").strip())

                effective_provs = tab2_provs if tab2_provs else (st.session_state.get("tab2_filter_provinces", []) or st.session_state.get("selected_provinces", []))
                effective_dists = tab2_dists if tab2_dists else (st.session_state.get("tab2_filter_districts", []) or st.session_state.get("selected_districts_formatted", []))
                effective_subdists = tab2_subdists if tab2_subdists else (st.session_state.get("tab2_filter_subdistricts", []) or st.session_state.get("selected_subdistricts_formatted", []))

                boundary_obj = get_boundary_geojson_features(effective_provs, effective_dists, effective_subdists)
                boundary_json = json.dumps(boundary_obj, ensure_ascii=False) if boundary_obj else "null"
                html_content = html_content.replace("BOUNDARY_GEOJSON_PLACEHOLDER", boundary_json)

                all_provinces_list = sorted(list({
                    str(p).strip().strip(" ,;.-'\"")
                    for p in df_raw['จังหวัด'].dropna().unique()
                    if str(p).strip().strip(" ,;.-'\"") and str(p).strip().strip(" ,;.-'\"") not in ['-', 'ไม่มีข้อมูล', 'nan', 'None']
                })) if df_raw is not None and not df_raw.empty else []
                all_provinces_json = json.dumps(all_provinces_list, ensure_ascii=False)
                current_prov_str = effective_provs[0] if (effective_provs and len(effective_provs) > 0) else ""
                html_content = html_content.replace("ALL_PROVINCES_PLACEHOLDER", all_provinces_json)
                html_content = html_content.replace("CURRENT_PROV_PLACEHOLDER", current_prov_str)

                company_logos_dict = get_leaflet_logo_dict(72)
                company_logos_json = json.dumps(company_logos_dict, ensure_ascii=False)
                html_content = html_content.replace("COMPANY_LOGOS_PLACEHOLDER", company_logos_json)

                if progress_bar:
                    progress_bar.progress(100, text="เรนเดอร์แผนที่สำเร็จแล้ว (100%)")
                    progress_bar.empty()

                map_rendered = False
                try:
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

        # ----------------- BELOW MAP: ANALYTICS CARDS & NEARBY ASSET LISTING -----------------
        # Filter for properties with valid map coordinates (pins) to keep counts 100% consistent
        df_map_valid = df_raw[
            df_raw['ละติจูด'].notna() & df_raw['ลองจิจูด'].notna() &
            df_raw['ละติจูด'].between(5, 21) & df_raw['ลองจิจูด'].between(97, 106)
        ] if df_raw is not None and not df_raw.empty else df_raw

        render_tab2_reference_analytics_fragment(
            df_raw=df_map_valid,
            is_dark_mode=is_dark_mode,
            active_ref_lat=active_ref_lat,
            active_ref_lon=active_ref_lon,
            active_ref_prop=active_ref_prop,
            active_ref_radius=active_ref_radius,
            tab2_types=tab2_types
        )
