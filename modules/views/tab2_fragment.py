import json
import numpy as np
import pandas as pd
import streamlit as st

from modules.services.geo_service import find_nearby_properties
from modules.services.export_service import render_import_export_section
from modules.services.data_cleaner import to_float_sqwah, to_float_sqm, format_to_rai_ngan_wah
from modules.ui.kpi_header import format_price_kpi

fragment_decorator = getattr(st, "fragment", lambda f: f)

@fragment_decorator
def render_tab2_reference_analytics_fragment(
    df_raw,
    is_dark_mode,
    active_ref_lat,
    active_ref_lon,
    active_ref_prop,
    active_ref_radius,
    tab2_types=None
):
    """
    Renders the live reference analytics fragment below the Tab 2 Leaflet map:
    - Hidden sync bridge with Leaflet iframe (two-way state syncing)
    - Active filter status chip banner
    - Prominent comparison action button
    - Dynamic median price benchmark cards (Total assets, sqm median, target type median, pure land benchmark)
    - Detailed comparative dataframe with up/down delta badges
    - CSV/Excel export section
    """
    if active_ref_prop is not None and isinstance(active_ref_prop, pd.Series):
        active_ref_prop = active_ref_prop.to_dict()

    # Ensure Tab 2 reference analytics strictly operates on properties with valid coordinates (matching the 418,055 map pins)
    if df_raw is not None and not df_raw.empty and 'ละติจูด' in df_raw.columns and 'ลองจิจูด' in df_raw.columns:
        valid_coords_mask = (
            df_raw['ละติจูด'].notna() & df_raw['ลองจิจูด'].notna() &
            df_raw['ละติจูด'].between(5, 21) & df_raw['ลองจิจูด'].between(97, 106)
        )
        df_raw = df_raw[valid_coords_mask]

    # 0. Hidden synchronization bridge between map iframe and Streamlit
    st.markdown("""
    <style>
    /* Position sync button and bridge input offscreen while remaining active and clickable via JS */
    .st-key-btn_map_filter_sync,
    div[data-testid="stElementContainer"]:has(.st-key-btn_map_filter_sync),
    div[data-testid="stButton"]:has(.st-key-btn_map_filter_sync),
    .st-key-map_sync_bridge_payload,
    div[data-testid="stElementContainer"]:has(.st-key-map_sync_bridge_payload),
    div[data-testid="stTextInput"]:has(.st-key-map_sync_bridge_payload) {
        position: fixed !important;
        bottom: -9999px !important;
        right: -9999px !important;
        opacity: 0 !important;
        z-index: -9999 !important;
    }
    </style>
    <div id="map-sync-anchor" style="position:fixed; bottom:-9999px; right:-9999px;"></div>
    """, unsafe_allow_html=True)
    
    sync_bridge_val = st.text_input("map_sync_bridge", key="map_sync_bridge_payload", label_visibility="collapsed")
    sync_btn_clicked = st.button("sync_map_filter", key="btn_map_filter_sync")
    
    if sync_bridge_val or sync_btn_clicked:
        payload_obj = None
        if sync_bridge_val and str(sync_bridge_val).strip():
            try:
                payload_obj = json.loads(str(sync_bridge_val).strip())
            except Exception:
                pass

        if payload_obj and isinstance(payload_obj, dict):
            p_prov = str(payload_obj.get("prov", "")).strip()
            if p_prov and p_prov not in ["ALL", "__ALL__", "all", "-"]:
                st.session_state["tab2_filter_provinces"] = [p_prov]
                try:
                    st.query_params["map_prov"] = p_prov
                except Exception:
                    pass
            else:
                st.session_state["tab2_filter_provinces"] = []
                st.session_state["tab2_filter_districts"] = []
                st.session_state["tab2_filter_subdistricts"] = []
                st.session_state["tab2_search_prop_id"] = ""
                st.session_state.pop("tab2_ref_prop", None)
                for qk in ["map_prov", "map_dist", "map_subdist", "map_ref_id"]:
                    try:
                        st.query_params.pop(qk, None)
                    except Exception:
                        pass

            p_dist = str(payload_obj.get("dist", "")).strip()
            if st.session_state.get("tab2_filter_provinces") and p_dist and p_dist not in ["ALL", "__ALL__", "all", "-"]:
                st.session_state["tab2_filter_districts"] = [p_dist]
                try:
                    st.query_params["map_dist"] = p_dist
                except Exception:
                    pass
            else:
                st.session_state["tab2_filter_districts"] = []
                try:
                    st.query_params.pop("map_dist", None)
                except Exception:
                    pass

            p_subdist = str(payload_obj.get("subdist", "")).strip()
            if st.session_state.get("tab2_filter_provinces") and st.session_state.get("tab2_filter_districts") and p_subdist and p_subdist not in ["ALL", "__ALL__", "all", "-"]:
                st.session_state["tab2_filter_subdistricts"] = [p_subdist]
                try:
                    st.query_params["map_subdist"] = p_subdist
                except Exception:
                    pass
            else:
                st.session_state["tab2_filter_subdistricts"] = []
                try:
                    st.query_params.pop("map_subdist", None)
                except Exception:
                    pass

            p_proj = str(payload_obj.get("proj", "")).strip()
            if p_proj and p_proj not in ["ALL", "__ALL__", "all", "-"]:
                p_list = [x.strip() for x in p_proj.split(",") if x.strip()]
                st.session_state["tab2_filter_projects"] = p_list
                try:
                    st.query_params["map_proj"] = p_proj
                except Exception:
                    pass
            elif "proj" in payload_obj:
                st.session_state["tab2_filter_projects"] = []
                try:
                    st.query_params.pop("map_proj", None)
                except Exception:
                    pass

            p_id = str(payload_obj.get("id", "")).strip()
            if p_id:
                st.session_state["tab2_search_prop_id"] = p_id
                try:
                    st.query_params["map_ref_id"] = p_id
                except Exception:
                    pass
                if df_raw is not None and not df_raw.empty:
                    m = df_raw[df_raw['รหัสทรัพย์'].astype(str).str.strip().str.lower() == p_id.lower()]
                    if not m.empty:
                        active_ref_prop = m.iloc[0].to_dict()
                        st.session_state["tab2_ref_prop"] = active_ref_prop
                        prop_p = str(active_ref_prop.get('จังหวัด', '')).strip()
                        prop_d = str(active_ref_prop.get('อำเภอ', '')).strip()
                        prop_s = str(active_ref_prop.get('ตำบล', '')).strip()
                        if prop_p and prop_p not in ['-', 'ไม่มีข้อมูล', 'nan']:
                            st.session_state["tab2_filter_provinces"] = [prop_p]
                        if prop_d and prop_d not in ['-', 'ไม่มีข้อมูล', 'nan']:
                            st.session_state["tab2_filter_districts"] = [prop_d]
                        if prop_s and prop_s not in ['-', 'ไม่มีข้อมูล', 'nan']:
                            st.session_state["tab2_filter_subdistricts"] = [prop_s]
            elif "id" in payload_obj or not st.session_state.get("tab2_filter_provinces"):
                st.session_state["tab2_search_prop_id"] = ""
                st.session_state.pop("tab2_ref_prop", None)
                try:
                    st.query_params.pop("map_ref_id", None)
                except Exception:
                    pass

            p_lat = payload_obj.get("lat")
            p_lon = payload_obj.get("lon")
            if p_lat is not None and p_lon is not None and float(p_lat) > 0 and float(p_lon) > 0:
                try:
                    active_ref_lat = float(p_lat)
                    active_ref_lon = float(p_lon)
                    st.session_state["tab2_ref_lat"] = active_ref_lat
                    st.session_state["tab2_ref_lon"] = active_ref_lon
                    st.session_state["tab2_compared_lat"] = active_ref_lat
                    st.session_state["tab2_compared_lon"] = active_ref_lon
                    try:
                        st.query_params["map_ref_lat"] = f"{active_ref_lat:.6f}"
                        st.query_params["map_ref_lon"] = f"{active_ref_lon:.6f}"
                    except Exception:
                        pass
                except (ValueError, TypeError):
                    pass
            elif "lat" in payload_obj or "lon" in payload_obj:
                active_ref_lat = None
                active_ref_lon = None
                st.session_state.pop("tab2_ref_lat", None)
                st.session_state.pop("tab2_ref_lon", None)
                st.session_state.pop("tab2_compared_lat", None)
                st.session_state.pop("tab2_compared_lon", None)
                for qk in ["map_ref_lat", "map_ref_lon"]:
                    try:
                        st.query_params.pop(qk, None)
                    except Exception:
                        pass

            p_rad = payload_obj.get("radius")
            if p_rad:
                try:
                    active_ref_radius = float(p_rad)
                    st.session_state["tab2_ref_radius"] = active_ref_radius
                    try:
                        st.query_params["map_ref_radius"] = str(active_ref_radius)
                    except Exception:
                        pass
                except (ValueError, TypeError):
                    pass

            p_mode = payload_obj.get("mode")
            if p_mode:
                st.session_state["tab2_pin_mode"] = str(p_mode).strip()
                try:
                    st.query_params["map_pin_mode"] = str(p_mode).strip()
                except Exception:
                    pass

            if "cos" in payload_obj and isinstance(payload_obj["cos"], list):
                st.session_state["tab2_map_filter_cos"] = payload_obj["cos"]
            if "types" in payload_obj and isinstance(payload_obj["types"], list):
                st.session_state["tab2_map_filter_types"] = payload_obj["types"]
            if "min_p" in payload_obj:
                st.session_state["tab2_map_filter_min_p"] = float(payload_obj["min_p"] or 0)
            if "max_p" in payload_obj:
                st.session_state["tab2_map_filter_max_p"] = float(payload_obj["max_p"] or 0)
            if "min_sqw" in payload_obj:
                st.session_state["tab2_map_filter_min_sqw"] = float(payload_obj["min_sqw"] or 0)
            if "max_sqw" in payload_obj:
                st.session_state["tab2_map_filter_max_sqw"] = float(payload_obj["max_sqw"] or 0)
            if "min_sqm" in payload_obj:
                st.session_state["tab2_map_filter_min_sqm"] = float(payload_obj["min_sqm"] or 0)
            if "max_sqm" in payload_obj:
                st.session_state["tab2_map_filter_max_sqm"] = float(payload_obj["max_sqm"] or 0)

            if payload_obj.get("compare_active", True):
                st.session_state["tab2_compared_active"] = True

        else:
            q_prov = st.query_params.get("map_prov", None)
            if q_prov and str(q_prov).strip() not in ["ALL", "__ALL__", "all", "", "-"]:
                st.session_state["tab2_filter_provinces"] = [str(q_prov).strip()]
            elif q_prov in ["ALL", "__ALL__", "all", "-"]:
                st.session_state["tab2_filter_provinces"] = []
                st.session_state["tab2_filter_districts"] = []
                st.session_state["tab2_filter_subdistricts"] = []
                st.session_state["tab2_search_prop_id"] = ""
                st.session_state.pop("tab2_ref_prop", None)

            q_dist = st.query_params.get("map_dist", None)
            if st.session_state.get("tab2_filter_provinces") and q_dist and str(q_dist).strip() not in ["ALL", "__ALL__", "all", "", "-"]:
                st.session_state["tab2_filter_districts"] = [str(q_dist).strip()]
            elif q_dist in ["ALL", "__ALL__", "all", "-"]:
                st.session_state["tab2_filter_districts"] = []

            q_subdist = st.query_params.get("map_subdist", None)
            if st.session_state.get("tab2_filter_provinces") and st.session_state.get("tab2_filter_districts") and q_subdist and str(q_subdist).strip() not in ["ALL", "__ALL__", "all", "", "-"]:
                st.session_state["tab2_filter_subdistricts"] = [str(q_subdist).strip()]
            elif q_subdist in ["ALL", "__ALL__", "all", "-"]:
                st.session_state["tab2_filter_subdistricts"] = []

            q_lat = st.query_params.get("map_ref_lat")
            q_lon = st.query_params.get("map_ref_lon")
            if q_lat and q_lon:
                try:
                    active_ref_lat = float(q_lat)
                    active_ref_lon = float(q_lon)
                    st.session_state["tab2_ref_lat"] = active_ref_lat
                    st.session_state["tab2_ref_lon"] = active_ref_lon
                    st.session_state["tab2_compared_active"] = True
                except (ValueError, TypeError):
                    pass

            q_id = st.query_params.get("map_ref_id")
            if q_id and df_raw is not None and not df_raw.empty:
                clean_id = str(q_id).strip()
                st.session_state["tab2_search_prop_id"] = clean_id
                f_prop = df_raw[df_raw['รหัสทรัพย์'].astype(str).str.strip().str.lower() == clean_id.lower()]
                if not f_prop.empty:
                    prop_row = f_prop.iloc[0]
                    active_ref_prop = prop_row.to_dict()
                    st.session_state["tab2_ref_prop"] = active_ref_prop
                    r_prov = str(prop_row.get('จังหวัด', '')).strip()
                    r_dist = str(prop_row.get('อำเภอ', '')).strip()
                    r_subdist = str(prop_row.get('ตำบล', '')).strip()
                    if r_prov and r_prov not in ['-', 'ไม่มีข้อมูล', 'nan']:
                        st.session_state["tab2_filter_provinces"] = [r_prov]
                    if r_dist and r_dist not in ['-', 'ไม่มีข้อมูล', 'nan']:
                        st.session_state["tab2_filter_districts"] = [r_dist]
                    if r_subdist and r_subdist not in ['-', 'ไม่มีข้อมูล', 'nan']:
                        st.session_state["tab2_filter_subdistricts"] = [r_subdist]

            has_loc_synced = (
                (q_prov is not None and str(q_prov).strip() not in ["", "ALL", "__ALL__", "all"]) or
                (q_dist is not None and str(q_dist).strip() not in ["", "ALL", "__ALL__", "all"]) or
                (q_subdist is not None and str(q_subdist).strip() not in ["", "ALL", "__ALL__", "all"]) or
                bool(q_id)
            )
            if has_loc_synced:
                st.session_state["tab2_compared_active"] = True

    # 1. Recovery of reference coordinates & radius from query_params or session_state
    q_lat_check = st.query_params.get("map_ref_lat")
    if q_lat_check:
        try:
            if float(q_lat_check) > 0 and "map_ref_cleared" in st.query_params:
                del st.query_params["map_ref_cleared"]
        except (ValueError, TypeError):
            pass

    if st.query_params.get("map_ref_cleared") == "1":
        active_ref_lat = 0.0
        active_ref_lon = 0.0
        active_ref_prop = None
        st.session_state["tab2_ref_lat"] = 0.0
        st.session_state["tab2_ref_lon"] = 0.0
        st.session_state["tab2_ref_prop"] = None
        st.session_state["tab2_compared_active"] = False
        try:
            del st.query_params["map_ref_cleared"]
        except Exception:
            pass
    else:
        try:
            q_lat = st.query_params.get("map_ref_lat")
            q_lon = st.query_params.get("map_ref_lon")
            if q_lat and q_lon and float(q_lat) > 0 and float(q_lon) > 0:
                active_ref_lat = float(q_lat)
                active_ref_lon = float(q_lon)
                st.session_state["tab2_ref_lat"] = active_ref_lat
                st.session_state["tab2_ref_lon"] = active_ref_lon
            q_rad = st.query_params.get("map_ref_radius")
            if q_rad and float(q_rad) > 0:
                active_ref_radius = float(q_rad)
                st.session_state["tab2_ref_radius"] = active_ref_radius
        except (ValueError, TypeError):
            pass

    if not active_ref_lat or not active_ref_lon or float(active_ref_lat) <= 0 or float(active_ref_lon) <= 0:
        s_lat = float(st.session_state.get("tab2_ref_lat") or 0.0)
        s_lon = float(st.session_state.get("tab2_ref_lon") or 0.0)
        if s_lat > 0 and s_lon > 0:
            active_ref_lat = s_lat
            active_ref_lon = s_lon

    if not active_ref_radius or float(active_ref_radius) <= 0:
        active_ref_radius = float(st.session_state.get("tab2_ref_radius") or 5.0)

    # Auto-resolve active_ref_prop if present in query params or session state
    q_id = st.query_params.get("map_ref_id") or st.session_state.get("tab2_search_prop_id")
    if q_id and df_raw is not None and not df_raw.empty:
        clean_id = str(q_id).strip()
        if active_ref_prop is None or str(active_ref_prop.get('รหัสทรัพย์', '')).strip().lower() != clean_id.lower():
            found = df_raw[df_raw['รหัสทรัพย์'].astype(str).str.strip().str.lower() == clean_id.lower()]
            if not found.empty:
                active_ref_prop = found.iloc[0].to_dict()
                st.session_state["tab2_ref_prop"] = active_ref_prop
                st.session_state["tab2_search_prop_id"] = clean_id
    elif not q_id and not st.session_state.get("tab2_search_prop_id"):
        active_ref_prop = None
        st.session_state["tab2_search_prop_id"] = ""
        st.session_state.pop("tab2_ref_prop", None)

    # 2. Extract and resolve all current map filters
    q_prov = st.query_params.get("map_prov", None)
    if q_prov and str(q_prov).strip() not in ["ALL", "__ALL__", "all", "", "-"]:
        active_prov = [str(q_prov).strip()]
        st.session_state["tab2_filter_provinces"] = active_prov
    elif q_prov in ["ALL", "__ALL__", "all", "-"]:
        active_prov = []
        st.session_state["tab2_filter_provinces"] = []
    else:
        active_prov = st.session_state.get("tab2_filter_provinces", [])

    q_dist = st.query_params.get("map_dist", None)
    if active_prov and q_dist and str(q_dist).strip() not in ["ALL", "__ALL__", "all", "", "-"]:
        active_dist = [str(q_dist).strip()]
        st.session_state["tab2_filter_districts"] = active_dist
    elif q_dist in ["ALL", "__ALL__", "all", "-"]:
        active_dist = []
        st.session_state["tab2_filter_districts"] = []
    else:
        active_dist = st.session_state.get("tab2_filter_districts", []) if active_prov else []

    q_subdist = st.query_params.get("map_subdist", None)
    if active_prov and active_dist and q_subdist and str(q_subdist).strip() not in ["ALL", "__ALL__", "all", "", "-"]:
        active_subdist = [str(q_subdist).strip()]
        st.session_state["tab2_filter_subdistricts"] = active_subdist
    elif q_subdist in ["ALL", "__ALL__", "all", "-"]:
        active_subdist = []
        st.session_state["tab2_filter_subdistricts"] = []
    else:
        active_subdist = st.session_state.get("tab2_filter_subdistricts", []) if (active_prov and active_dist) else []

    q_proj = st.query_params.get("map_proj", None)
    if q_proj and str(q_proj).strip() not in ["ALL", "__ALL__", "all", ""]:
        active_proj = str(q_proj).strip()
    else:
        proj_list = st.session_state.get("tab2_filter_projects", [])
        active_proj = ",".join(proj_list) if proj_list else None

    raw_cos = st.query_params.get("map_filter_cos", "")
    map_cos = [c.strip() for c in raw_cos.split(",") if c.strip()] if raw_cos else st.session_state.get("tab2_map_filter_cos", [])

    raw_types = st.query_params.get("map_filter_types", "")
    map_types = [t.strip() for t in raw_types.split(",") if t.strip()] if raw_types else st.session_state.get("tab2_map_filter_types", [])

    try:
        map_min_p = float(st.query_params.get("map_filter_min_p", 0)) or float(st.session_state.get("tab2_map_filter_min_p", 0.0))
    except (ValueError, TypeError):
        map_min_p = float(st.session_state.get("tab2_map_filter_min_p", 0.0))

    try:
        map_max_p = float(st.query_params.get("map_filter_max_p", 0)) or float(st.session_state.get("tab2_map_filter_max_p", 0.0))
    except (ValueError, TypeError):
        map_max_p = float(st.session_state.get("tab2_map_filter_max_p", 0.0))

    try:
        map_min_sqw = float(st.query_params.get("map_filter_min_sqw", 0)) or float(st.session_state.get("tab2_map_filter_min_sqw", 0.0))
    except (ValueError, TypeError):
        map_min_sqw = float(st.session_state.get("tab2_map_filter_min_sqw", 0.0))

    try:
        map_max_sqw = float(st.query_params.get("map_filter_max_sqw", 0)) or float(st.session_state.get("tab2_map_filter_max_sqw", 0.0))
    except (ValueError, TypeError):
        map_max_sqw = float(st.session_state.get("tab2_map_filter_max_sqw", 0.0))

    try:
        map_min_sqm = float(st.query_params.get("map_filter_min_sqm", 0)) or float(st.session_state.get("tab2_map_filter_min_sqm", 0.0))
    except (ValueError, TypeError):
        map_min_sqm = float(st.session_state.get("tab2_map_filter_min_sqm", 0.0))

    try:
        map_max_sqm = float(st.query_params.get("map_filter_max_sqm", 0)) or float(st.session_state.get("tab2_map_filter_max_sqm", 0.0))
    except (ValueError, TypeError):
        map_max_sqm = float(st.session_state.get("tab2_map_filter_max_sqm", 0.0))

    pin_mode = st.session_state.get("tab2_pin_mode") or st.query_params.get("map_pin_mode", "radius")
    has_ref_point = bool(active_ref_lat and active_ref_lon and float(active_ref_lat) > 0 and float(active_ref_lon) > 0)
    has_loc_filter = bool(active_prov or active_dist or active_subdist or active_proj)

    # 3. Compute matching count and summary labels for Filter Status Bar
    status_df = df_raw.copy() if df_raw is not None else pd.DataFrame()
    if not status_df.empty:
        if has_ref_point and pin_mode == 'radius' and not active_proj:
            status_df = find_nearby_properties(active_ref_lat, active_ref_lon, status_df, active_ref_radius)
        elif active_proj and 'ชื่อโครงการ' in status_df.columns:
            p_list = [p.strip() for p in active_proj.split(",") if p.strip()]
            status_df = status_df[status_df['ชื่อโครงการ'].astype(str).str.strip().isin(p_list)]
        else:
            if active_prov and 'จังหวัด' in status_df.columns:
                status_df = status_df[status_df['จังหวัด'].astype(str).str.strip().isin(active_prov)]
            if active_dist and 'อำเภอ' in status_df.columns:
                clean_target_dists = [d.split(' (')[0].strip() for d in active_dist]
                status_df = status_df[status_df['อำเภอ'].astype(str).str.strip().isin(clean_target_dists)]
            if active_subdist and 'ตำบล' in status_df.columns:
                clean_target_subs = [s.split(' (')[0].strip() for s in active_subdist]
                status_df = status_df[status_df['ตำบล'].astype(str).str.strip().isin(clean_target_subs)]

        if map_cos and 'บริษัท' in status_df.columns:
            cos_to_keep = set(map_cos)
            if active_proj:
                cos_to_keep.add('SAM')
            status_df = status_df[status_df['บริษัท'].isin(cos_to_keep)]
        if map_types and 'ประเภททรัพย์' in status_df.columns:
            status_df = status_df[status_df['ประเภททรัพย์'].isin(map_types)]
        if map_min_p > 0 and 'ราคา' in status_df.columns:
            status_df = status_df[status_df['ราคา'] >= map_min_p]
        if map_max_p > 0 and 'ราคา' in status_df.columns:
            status_df = status_df[status_df['ราคา'] <= map_max_p]
        if map_min_sqw > 0:
            col_sqw = 'เนื้อที่ (ตร.ว.)' if 'เนื้อที่ (ตร.ว.)' in status_df.columns else ('พื้นที่_ตารางวา' if 'พื้นที่_ตารางวา' in status_df.columns else None)
            if col_sqw:
                status_df = status_df[status_df[col_sqw].apply(to_float_sqwah) >= map_min_sqw]
        if map_max_sqw > 0:
            col_sqw = 'เนื้อที่ (ตร.ว.)' if 'เนื้อที่ (ตร.ว.)' in status_df.columns else ('พื้นที่_ตารางวา' if 'พื้นที่_ตารางวา' in status_df.columns else None)
            if col_sqw:
                status_df = status_df[status_df[col_sqw].apply(to_float_sqwah) <= map_max_sqw]
        if map_min_sqm > 0 and 'พื้นที่ใช้สอย (ตร.ม.)' in status_df.columns:
            status_df = status_df[status_df['พื้นที่ใช้สอย (ตร.ม.)'].apply(to_float_sqm) >= map_min_sqm]
        if map_max_sqm > 0 and 'พื้นที่ใช้สอย (ตร.ม.)' in status_df.columns:
            status_df = status_df[status_df['พื้นที่ใช้สอย (ตร.ม.)'].apply(to_float_sqm) <= map_max_sqm]

    matched_count = len(status_df)

    # Human-readable labels
    if active_proj:
        loc_str = f"โครงการ: {active_proj}"
    elif has_ref_point and pin_mode == 'radius':
        if active_subdist:
            clean_s = active_subdist[0].split(' (')[0].strip()
            clean_d = active_dist[0].split(' (')[0].strip() if active_dist else "-"
            loc_str = f"จุดศูนย์กลาง: จ.{active_prov[0] if active_prov else '-'} > อ.{clean_d} > ต.{clean_s}"
        elif active_dist:
            clean_d = active_dist[0].split(' (')[0].strip()
            loc_str = f"จุดศูนย์กลาง: จ.{active_prov[0] if active_prov else '-'} > อ.{clean_d}"
        elif active_prov:
            loc_str = f"จุดศูนย์กลาง: จ.{active_prov[0]}"
        else:
            loc_str = "ตามพิกัดจุดอ้างอิง (ครอบคลุมตามรัศมี)"
    elif active_subdist:
        clean_s = active_subdist[0].split(' (')[0].strip()
        clean_d = active_dist[0].split(' (')[0].strip() if active_dist else "-"
        loc_str = f"จ.{active_prov[0] if active_prov else '-'} > อ.{clean_d} > ต.{clean_s}"
    elif active_dist:
        clean_d = active_dist[0].split(' (')[0].strip()
        loc_str = f"จ.{active_prov[0] if active_prov else '-'} > อ.{clean_d}"
    elif active_prov:
        loc_str = f"จ.{active_prov[0]}"
    else:
        loc_str = "ทุกทำเล (ทั่วประเทศ)"

    if has_ref_point:
        if active_ref_prop is not None:
            rad_str = f"{active_ref_radius:.1f} กม. รอบ [{active_ref_prop.get('บริษัท', '-')}] {active_ref_prop.get('รหัสทรัพย์', '')}"
        else:
            rad_str = f"{active_ref_radius:.1f} กม. ({active_ref_lat:.4f}, {active_ref_lon:.4f})"
    else:
        rad_str = f"รัศมี {active_ref_radius:.1f} กม. (ยังไม่ได้ปักหมุด)"

    cos_str = f"{', '.join(map_cos)} ({len(map_cos)} บริษัท)" if map_cos else "ทุกบริษัท"
    types_str = f"{', '.join(map_types)}" if map_types else "ทุกประเภททรัพย์"

    if map_min_p > 0 and map_max_p > 0:
        price_str = f"฿{format_price_kpi(map_min_p)} - ฿{format_price_kpi(map_max_p)}"
    elif map_min_p > 0:
        price_str = f">= ฿{format_price_kpi(map_min_p)}"
    elif map_max_p > 0:
        price_str = f"<= ฿{format_price_kpi(map_max_p)}"
    else:
        price_str = "ทุกช่วงราคา"

    area_parts = []
    if map_min_sqw > 0 or map_max_sqw > 0:
        area_parts.append(f"{map_min_sqw:,.0f}-{map_max_sqw:,.0f} ตร.ว." if map_max_sqw > 0 else f">= {map_min_sqw:,.0f} ตร.ว.")
    if map_min_sqm > 0 or map_max_sqm > 0:
        area_parts.append(f"{map_min_sqm:,.0f}-{map_max_sqm:,.0f} ตร.ม." if map_max_sqm > 0 else f">= {map_min_sqm:,.0f} ตร.ม.")
    area_str = " / ".join(area_parts) if area_parts else "ทุกขนาด (ทุก Plan)"

    mode_badge_lbl = "ตามรัศมี (Radius)" if (pin_mode == 'radius' and has_ref_point) else "ตามทำเล (Location)"

    # Theme colors for status card
    card_bg = "rgba(2, 44, 34, 0.45)" if is_dark_mode else "#f8fafc"
    card_border = "rgba(52, 211, 153, 0.35)" if is_dark_mode else "#e2e8f0"
    chip_bg = "rgba(2, 44, 34, 0.7)" if is_dark_mode else "#ffffff"
    chip_border = "rgba(52, 211, 153, 0.25)" if is_dark_mode else "#e2e8f0"
    text_c = "#f1f5f9" if is_dark_mode else "#1e293b"
    sub_c = "#94a3b8" if is_dark_mode else "#64748b"

    # --- RENDER FILTER STATUS BANNER (นอกแผนที่ ข้างใต้แผนที่) ---
    st.markdown(f"""
    <div id='ref-analytics-section' style='height: 0px; margin: 0px; padding: 0px; scroll-margin-top: 80px;'></div>
    <div id="map-active-filters-banner" style="background: {card_bg}; border: 1.5px solid {card_border}; border-radius: 14px; padding: 12px 16px; margin-top: -18px; margin-bottom: 12px; position: relative; z-index: 10; box-shadow: 0 4px 14px rgba(0,0,0,0.04);">
        <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px; margin-bottom: 10px; padding-bottom: 8px; border-bottom: 1px solid {chip_border};">
            <div style="display: flex; align-items: center; gap: 8px;">
                <span style="background: linear-gradient(135deg, #059669, #10b981); color: #ffffff; padding: 3px 10px; border-radius: 6px; font-size: 0.78rem; font-weight: 800; display: inline-flex; align-items: center; gap: 5px;">
                    <i class="fa-solid fa-sliders"></i> สถานะตัวกรองแผนที่ (Active Map Filters)
                </span>
                <span style="font-size: 0.82rem; font-weight: 700; color: #10b981;" id="active-filter-mode-val">
                    โหมด: <b>{mode_badge_lbl}</b>
                </span>
            </div>
            <div style="font-size: 0.82rem; font-weight: 700; color: #059669; background: rgba(16, 185, 129, 0.12); padding: 3px 10px; border-radius: 20px; display: inline-flex; align-items: center; gap: 5px;" id="active-filter-count-val">
                <i class="fa-solid fa-layer-group"></i> ทรัพย์ที่ตรงเงื่อนไข: <b>{matched_count:,}</b> รายการ
            </div>
        </div>
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 8px;">
            <div style="background: {chip_bg}; border: 1px solid {chip_border}; border-radius: 8px; padding: 7px 10px;">
                <div style="font-size: 0.70rem; font-weight: 700; color: {sub_c}; text-transform: uppercase;">
                    <i class="fa-solid fa-location-dot" style="color: #10b981; margin-right: 3px;"></i>ทำเล (Location)
                </div>
                <div id="active-filter-loc-val" style="font-size: 0.84rem; font-weight: 700; color: {text_c}; margin-top: 2px; word-break: break-word;">
                    {loc_str}
                </div>
            </div>
            <div style="background: {chip_bg}; border: 1px solid {chip_border}; border-radius: 8px; padding: 7px 10px;">
                <div style="font-size: 0.70rem; font-weight: 700; color: {sub_c}; text-transform: uppercase;">
                    <i class="fa-solid fa-bullseye" style="color: #06b6d4; margin-right: 3px;"></i>รัศมีตรวจ (Radius)
                </div>
                <div id="active-filter-rad-val" style="font-size: 0.84rem; font-weight: 700; color: {text_c}; margin-top: 2px;">
                    {rad_str}
                </div>
            </div>
            <div style="background: {chip_bg}; border: 1px solid {chip_border}; border-radius: 8px; padding: 7px 10px;">
                <div style="font-size: 0.70rem; font-weight: 700; color: {sub_c}; text-transform: uppercase;">
                    <i class="fa-solid fa-building" style="color: #3b82f6; margin-right: 3px;"></i>บริษัท (Company)
                </div>
                <div id="active-filter-co-val" style="font-size: 0.84rem; font-weight: 700; color: {text_c}; margin-top: 2px;">
                    {cos_str}
                </div>
            </div>
            <div style="background: {chip_bg}; border: 1px solid {chip_border}; border-radius: 8px; padding: 7px 10px;">
                <div style="font-size: 0.70rem; font-weight: 700; color: {sub_c}; text-transform: uppercase;">
                    <i class="fa-solid fa-house" style="color: #f59e0b; margin-right: 3px;"></i>ประเภททรัพย์ (Type)
                </div>
                <div id="active-filter-type-val" style="font-size: 0.84rem; font-weight: 700; color: {text_c}; margin-top: 2px;">
                    {types_str}
                </div>
            </div>
            <div style="background: {chip_bg}; border: 1px solid {chip_border}; border-radius: 8px; padding: 7px 10px;">
                <div style="font-size: 0.70rem; font-weight: 700; color: {sub_c}; text-transform: uppercase;">
                    <i class="fa-solid fa-tag" style="color: #10b981; margin-right: 3px;"></i>ราคา (Price)
                </div>
                <div id="active-filter-price-val" style="font-size: 0.84rem; font-weight: 700; color: {text_c}; margin-top: 2px;">
                    {price_str}
                </div>
            </div>
            <div style="background: {chip_bg}; border: 1px solid {chip_border}; border-radius: 8px; padding: 7px 10px;">
                <div style="font-size: 0.70rem; font-weight: 700; color: {sub_c}; text-transform: uppercase;">
                    <i class="fa-solid fa-ruler-combined" style="color: #8b5cf6; margin-right: 3px;"></i>ขนาด/Plan (Area)
                </div>
                <div id="active-filter-area-val" style="font-size: 0.84rem; font-weight: 700; color: {text_c}; margin-top: 2px;">
                    {area_str}
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 4. Track comparison state
    is_compared = st.session_state.get("tab2_compared_active", False)

    if not is_compared:
        # Comparison Button ALWAYS present and prominent above details!
        st.markdown("""
        <style>
        .st-key-tab2_hero_compare_container {
            display: flex !important;
            justify-content: center !important;
            align-items: center !important;
            margin-top: -6px !important;
            margin-bottom: 12px !important;
            position: relative !important;
            z-index: 100 !important;
        }
        .st-key-tab2_hero_compare_container div[data-testid="stButton"] {
            display: flex !important;
            justify-content: center !important;
            width: 100% !important;
        }
        .st-key-tab2_hero_compare_container button {
            background: linear-gradient(135deg, #059669 0%, #10b981 50%, #047857 100%) !important;
            color: #ffffff !important;
            font-size: 1.12rem !important;
            font-weight: 800 !important;
            font-family: 'Noto Sans Thai', 'Outfit', sans-serif !important;
            letter-spacing: 0.3px !important;
            padding: 12px 36px !important;
            min-height: 52px !important;
            max-width: 480px !important;
            width: 100% !important;
            border-radius: 50px !important;
            border: 1.5px solid rgba(255, 255, 255, 0.45) !important;
            box-shadow: 0 6px 20px rgba(16, 185, 129, 0.38), 0 2px 6px rgba(0, 0, 0, 0.1) !important;
            transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1) !important;
            cursor: pointer !important;
        }
        .st-key-tab2_hero_compare_container button:hover {
            transform: translateY(-2px) scale(1.02) !important;
            background: linear-gradient(135deg, #10b981 0%, #34d399 50%, #059669 100%) !important;
            box-shadow: 0 10px 28px rgba(16, 185, 129, 0.52), 0 4px 12px rgba(0, 0, 0, 0.15) !important;
            border-color: rgba(255, 255, 255, 0.8) !important;
            color: #ffffff !important;
        }
        .st-key-tab2_hero_compare_container button:active {
            transform: translateY(1px) scale(0.99) !important;
            box-shadow: 0 2px 10px rgba(16, 185, 129, 0.3) !important;
        }
        .st-key-tab2_hero_compare_container button p {
            font-size: 1.12rem !important;
            font-weight: 800 !important;
            color: #ffffff !important;
            margin: 0 !important;
            display: inline-flex !important;
            align-items: center !important;
            gap: 8px !important;
        }
        .st-key-tab2_hero_compare_container button span[data-testid="stIconMaterial"] {
            font-size: 1.35rem !important;
            color: #ffffff !important;
        }
        </style>
        """, unsafe_allow_html=True)
        with st.container(key="tab2_hero_compare_container"):
            col_b1, col_b2, col_b3 = st.columns([1, 1.8, 1])
            with col_b2:
                # Dynamic Compare Button Label
                if active_proj:
                    btn_compare_label = f"กดเปรียบเทียบตามโครงการ: {active_proj}"
                    btn_help_text = f"ประมวลผลการคำนวณราคากลางในโครงการ {active_proj}"
                elif has_ref_point and pin_mode == 'radius' and not has_loc_filter:
                    btn_compare_label = f"กดเปรียบเทียบรอบจุดอ้างอิง ({active_ref_radius:.1f} กม.)"
                    btn_help_text = f"ประมวลผลการคำนวณราคากลางรอบจุดอ้างอิงในรัศมี {active_ref_radius:.1f} กม."
                elif active_subdist:
                    clean_s = active_subdist[0].split(' (')[0].strip()
                    clean_d = active_dist[0].split(' (')[0].strip() if active_dist else ""
                    btn_compare_label = f"กดเปรียบเทียบตามทำเล: ต.{clean_s} อ.{clean_d}"
                    btn_help_text = f"ประมวลผลการคำนวณราคากลางและวิเคราะห์ทรัพย์สินในตำบล {clean_s}"
                elif active_dist:
                    clean_d = active_dist[0].split(' (')[0].strip()
                    btn_compare_label = f"กดเปรียบเทียบตามทำเล: อ.{clean_d} จ.{active_prov[0] if active_prov else ''}"
                    btn_help_text = f"ประมวลผลการคำนวณราคากลางและวิเคราะห์ทรัพย์สินในอำเภอ {clean_d}"
                elif active_prov:
                    btn_compare_label = f"กดเปรียบเทียบตามทำเล: จังหวัด {active_prov[0]}"
                    btn_help_text = f"ประมวลผลการคำนวณราคากลางและวิเคราะห์ทรัพย์สินในจังหวัด {active_prov[0]}"
                else:
                    btn_compare_label = "กดเปรียบเทียบสถิติและราคากลางทั้งหมด"
                    btn_help_text = "ประมวลผลการคำนวณราคากลางและวิเคราะห์ทรัพย์สินทั้งหมดตามตัวกรอง"

                btn_do_compare = st.button(
                    btn_compare_label,
                    icon=":material/compare_arrows:",
                    key="btn_do_ref_compare",
                    type="primary",
                    use_container_width=True,
                    help=btn_help_text
                )
                if btn_do_compare:
                    cur_lat = active_ref_lat or float(st.query_params.get("map_ref_lat", 0.0) or 0.0) or float(st.session_state.get("tab2_ref_lat", 0.0) or 0.0)
                    cur_lon = active_ref_lon or float(st.query_params.get("map_ref_lon", 0.0) or 0.0) or float(st.session_state.get("tab2_ref_lon", 0.0) or 0.0)
                    if cur_lat and cur_lon and cur_lat > 0 and cur_lon > 0:
                        active_ref_lat = cur_lat
                        active_ref_lon = cur_lon
                        st.session_state["tab2_ref_lat"] = cur_lat
                        st.session_state["tab2_ref_lon"] = cur_lon
                        st.session_state["tab2_compared_lat"] = cur_lat
                        st.session_state["tab2_compared_lon"] = cur_lon
                    st.session_state["tab2_compared_active"] = True
                    try:
                        st.rerun(scope="fragment")
                    except TypeError:
                        st.rerun()

    else:
        # 5. Calculation results (Cards & Table) with Live Filters
        # Determine comparison data scope
        if has_ref_point and (pin_mode == 'radius' or not has_loc_filter) and not active_proj:
            nearby_df = find_nearby_properties(active_ref_lat, active_ref_lon, df_raw, active_ref_radius)
            scope_header = f"ในรัศมี {active_ref_radius:.1f} กม. รอบจุดอ้างอิง"
        elif active_proj:
            nearby_df = df_raw.copy() if df_raw is not None else pd.DataFrame()
            scope_header = f"ในโครงการ {active_proj}"
        else:
            nearby_df = df_raw.copy() if df_raw is not None else pd.DataFrame()
            if active_subdist:
                clean_s = active_subdist[0].split(' (')[0].strip()
                clean_d = active_dist[0].split(' (')[0].strip() if active_dist else ""
                scope_header = f"ในทำเล ตำบล{clean_s} อำเภอ{clean_d} จังหวัด{active_prov[0] if active_prov else ''}"
            elif active_dist:
                clean_d = active_dist[0].split(' (')[0].strip()
                scope_header = f"ในทำเล อำเภอ{clean_d} จังหวัด{active_prov[0] if active_prov else ''}"
            elif active_prov:
                scope_header = f"ในทำเล จังหวัด{active_prov[0]}"
            else:
                scope_header = "ภาพรวมตามตัวกรองที่เลือก"

        def compute_vectorized_unit_info(df_target):
            if df_target is None or df_target.empty:
                return df_target
            df_res = df_target.copy()
            p_num = pd.to_numeric(df_res['ราคา'], errors='coerce')
            sqm_num = pd.to_numeric(df_res.get('พื้นที่ใช้สอย (ตร.ม.)', np.nan), errors='coerce')
            sqw_num = pd.to_numeric(df_res.get('พื้นที่_ตารางวา', np.nan), errors='coerce')
            if 'เนื้อที่ (ตร.ว.)' in df_res.columns:
                sqw_num = sqw_num.combine_first(pd.to_numeric(df_res['เนื้อที่ (ตร.ว.)'], errors='coerce'))
            
            p_type = df_res['ประเภททรัพย์'].astype(str).str.lower()
            is_condo = p_type.str.contains('คอนโด|ห้องชุด', regex=True, na=False)
            
            condo_rate = np.where(is_condo & (sqm_num > 0) & (p_num > 0), p_num / sqm_num, np.nan)
            land_rate = np.where((~is_condo) & (sqw_num > 0) & (p_num > 0), p_num / sqw_num, np.nan)
            unit_price = np.where(pd.notna(condo_rate), condo_rate, land_rate)
            
            df_res['ราคาต่อหน่วย'] = unit_price
            df_res['หน่วยวัด'] = np.where(is_condo, 'ตร.ม.', 'ตร.ว.')
            df_res['ประเภทพื้นที่'] = np.where(is_condo, 'พื้นที่ใช้สอย', 'เนื้อที่')
            return df_res

        if not nearby_df.empty:
            nearby_df = compute_vectorized_unit_info(nearby_df)

        # Target type determination
        target_type = None
        if active_ref_prop is not None:
            target_type = active_ref_prop.get('ประเภททรัพย์')
        elif tab2_types and len(tab2_types) == 1:
            target_type = tab2_types[0]
        elif map_types and len(map_types) == 1:
            target_type = map_types[0]

        # Header row with title
        st.markdown(
            f"<div id='median-section-header' style='font-size: 1.25rem; font-weight: 700; margin-bottom: 12px;'><i class='fa-solid fa-chart-simple' style='color:#059669; margin-right:6px;'></i>ผลการวิเคราะห์ราคากลางต่อหน่วย (Median Analysis) <span id='median-scope-header-text'>{scope_header}</span></div>",
            unsafe_allow_html=True
        )

        # Apply active in-map filters to nearby_df
        filtered_nearby = nearby_df.copy()
        active_cos = map_cos
        active_types = map_types

        if has_ref_point and (pin_mode == 'radius' or not has_loc_filter) and not active_proj:
            # In Radius mode, comparison scope is the geographic radius circle.
            pass
        elif active_proj and not filtered_nearby.empty and 'ชื่อโครงการ' in filtered_nearby.columns:
            p_list = [p.strip() for p in active_proj.split(",") if p.strip()]
            filtered_nearby = filtered_nearby[filtered_nearby['ชื่อโครงการ'].astype(str).str.strip().isin(p_list)]
        else:
            if active_prov and not filtered_nearby.empty and 'จังหวัด' in filtered_nearby.columns:
                filtered_nearby = filtered_nearby[filtered_nearby['จังหวัด'].astype(str).str.strip().isin(active_prov)]

            if active_dist and not filtered_nearby.empty and 'อำเภอ' in filtered_nearby.columns:
                clean_target_dists = [d.split(' (')[0].strip() for d in active_dist]
                filtered_nearby = filtered_nearby[filtered_nearby['อำเภอ'].astype(str).str.strip().isin(clean_target_dists)]

            if active_subdist and not filtered_nearby.empty and 'ตำบล' in filtered_nearby.columns:
                clean_target_subs = [s.split(' (')[0].strip() for s in active_subdist]
                filtered_nearby = filtered_nearby[filtered_nearby['ตำบล'].astype(str).str.strip().isin(clean_target_subs)]

        if active_cos and not filtered_nearby.empty and 'บริษัท' in filtered_nearby.columns:
            cos_to_keep = set(active_cos)
            if active_proj:
                cos_to_keep.add('SAM')
            filtered_nearby = filtered_nearby[filtered_nearby['บริษัท'].isin(cos_to_keep)]
        if active_types and not filtered_nearby.empty and 'ประเภททรัพย์' in filtered_nearby.columns:
            filtered_nearby = filtered_nearby[filtered_nearby['ประเภททรัพย์'].isin(active_types)]
        if map_min_p > 0 and not filtered_nearby.empty and 'ราคา' in filtered_nearby.columns:
            filtered_nearby = filtered_nearby[filtered_nearby['ราคา'] >= map_min_p]
        if map_max_p > 0 and not filtered_nearby.empty and 'ราคา' in filtered_nearby.columns:
            filtered_nearby = filtered_nearby[filtered_nearby['ราคา'] <= map_max_p]
        if map_min_sqw > 0 and not filtered_nearby.empty:
            sqw_s = pd.to_numeric(filtered_nearby.get('พื้นที่_ตารางวา', np.nan), errors='coerce')
            if 'เนื้อที่ (ตร.ว.)' in filtered_nearby.columns:
                sqw_s = sqw_s.combine_first(pd.to_numeric(filtered_nearby['เนื้อที่ (ตร.ว.)'], errors='coerce'))
            filtered_nearby = filtered_nearby[sqw_s >= map_min_sqw]
        if map_max_sqw > 0 and not filtered_nearby.empty:
            sqw_s = pd.to_numeric(filtered_nearby.get('พื้นที่_ตารางวา', np.nan), errors='coerce')
            if 'เนื้อที่ (ตร.ว.)' in filtered_nearby.columns:
                sqw_s = sqw_s.combine_first(pd.to_numeric(filtered_nearby['เนื้อที่ (ตร.ว.)'], errors='coerce'))
            filtered_nearby = filtered_nearby[sqw_s <= map_max_sqw]
        if map_min_sqm > 0 and not filtered_nearby.empty and 'พื้นที่ใช้สอย (ตร.ม.)' in filtered_nearby.columns:
            sqm_s = pd.to_numeric(filtered_nearby['พื้นที่ใช้สอย (ตร.ม.)'], errors='coerce')
            filtered_nearby = filtered_nearby[sqm_s >= map_min_sqm]
        if map_max_sqm > 0 and not filtered_nearby.empty and 'พื้นที่ใช้สอย (ตร.ม.)' in filtered_nearby.columns:
            sqm_s = pd.to_numeric(filtered_nearby['พื้นที่ใช้สอย (ตร.ม.)'], errors='coerce')
            filtered_nearby = filtered_nearby[sqm_s <= map_max_sqm]

        # -------------------------------------------------------------
        # 1. Dedicated Pure Land Calculation (Card 4 & Benchmark)
        # Sourced strictly according to Location level (Tambon/Amphoe/Province) or Radius (min 1.0 km)
        # -------------------------------------------------------------
        def _check_pure_land_mask(s_types):
            p = s_types.astype(str)
            return p.str.contains('ที่ดินเปล่า|ที่ดิน', regex=True, na=False) & \
                   ~p.str.contains('บ้าน|อาคาร|ทาวน์|คอนโด|ตึก|โรงงาน|พาณิชย์|หอพัก|สิ่งปลูกสร้าง|พร้อมสิ่งปลูกสร้าง', regex=True, na=False)

        is_radius_scope = bool(has_ref_point and (pin_mode == 'radius' or not has_loc_filter) and not active_proj)

        if is_radius_scope:
            # Pure land radius must be at least 1.0 km minimum
            land_radius = max(float(active_ref_radius), 1.0)
            source_icon = "fa-circle-dot"
            land_source_desc = f"ตามรัศมี {land_radius:.1f} กม. รอบจุดอ้างอิง"
            if abs(land_radius - float(active_ref_radius)) < 0.001 and not nearby_df.empty:
                land_raw = nearby_df.copy()
            else:
                land_raw = find_nearby_properties(active_ref_lat, active_ref_lon, df_raw, land_radius)
                land_raw = compute_vectorized_unit_info(land_raw)
        elif active_proj:
            source_icon = "fa-mountain-sun"
            p_list = [p.strip() for p in active_proj.split(",") if p.strip()]
            # 1. First check if the project itself contains pure land
            proj_df = df_raw[df_raw['ชื่อโครงการ'].astype(str).str.strip().isin(p_list)].copy() if (df_raw is not None and 'ชื่อโครงการ' in df_raw.columns) else pd.DataFrame()
            proj_df = compute_vectorized_unit_info(proj_df)
            proj_pure_land = proj_df[_check_pure_land_mask(proj_df['ประเภททรัพย์']) & (proj_df['ราคา'] > 0)] if not proj_df.empty else pd.DataFrame()

            if not proj_pure_land.empty:
                land_source_desc = f"ในโครงการ: {active_proj}"
                land_raw = proj_df
            else:
                # Project has no pure land (condo/village) -> Fetch pure land from nearby location of this project!
                land_raw = pd.DataFrame()

                # A. Try radius search around project coordinates if available
                proj_lats = pd.to_numeric(proj_df.get('ละติจูด', pd.Series(dtype=float)), errors='coerce').dropna()
                proj_lons = pd.to_numeric(proj_df.get('ลองจิจูด', pd.Series(dtype=float)), errors='coerce').dropna()
                valid_coord = not proj_lats.empty and not proj_lons.empty and (proj_lats.iloc[0] > 0) and (proj_lons.iloc[0] > 0)

                if valid_coord:
                    c_lat = float(proj_lats.median())
                    c_lon = float(proj_lons.median())
                    # Try 5 km radius first, expand to 10 km if needed
                    for r_dist in [5.0, 10.0]:
                        cand = find_nearby_properties(c_lat, c_lon, df_raw, r_dist)
                        cand = compute_vectorized_unit_info(cand)
                        cand_pure = cand[_check_pure_land_mask(cand['ประเภททรัพย์']) & (cand['ราคา'] > 0)] if not cand.empty else pd.DataFrame()
                        if len(cand_pure) >= 2:
                            land_raw = cand
                            land_source_desc = f"ที่ดินเปล่ารอบโครงการ (รัศมี {r_dist:.0f} กม.)"
                            break
                    if land_raw.empty and not cand_pure.empty:
                        land_raw = cand
                        land_source_desc = f"ที่ดินเปล่ารอบโครงการ (รัศมี 10 กม.)"

                # B. If still empty, fall back to District / Province of the project
                if land_raw.empty and not proj_df.empty and df_raw is not None:
                    proj_dists = [d.split(' (')[0].strip() for d in proj_df['อำเภอ'].dropna().astype(str).unique() if d not in ['-', 'ไม่มีข้อมูล', 'ไม่ระบุ']] if 'อำเภอ' in proj_df.columns else []
                    proj_provs = [p.strip() for p in proj_df['จังหวัด'].dropna().astype(str).unique() if p not in ['-', 'ไม่มีข้อมูล', 'ไม่ระบุ']] if 'จังหวัด' in proj_df.columns else []

                    if proj_dists and 'อำเภอ' in df_raw.columns:
                        cand = df_raw[df_raw['อำเภอ'].astype(str).str.strip().isin(proj_dists)].copy()
                        if proj_provs and 'จังหวัด' in cand.columns:
                            cand = cand[cand['จังหวัด'].astype(str).str.strip().isin(proj_provs)]
                        cand = compute_vectorized_unit_info(cand)
                        cand_pure = cand[_check_pure_land_mask(cand['ประเภททรัพย์']) & (cand['ราคา'] > 0)] if not cand.empty else pd.DataFrame()
                        if not cand_pure.empty:
                            land_raw = cand
                            d_lbl = proj_dists[0]
                            p_lbl = proj_provs[0] if proj_provs else ""
                            land_source_desc = f"ที่ดินเปล่ารอบโครงการ (อ.{d_lbl} จ.{p_lbl})"

                    if land_raw.empty and proj_provs and 'จังหวัด' in df_raw.columns:
                        cand = df_raw[df_raw['จังหวัด'].astype(str).str.strip().isin(proj_provs)].copy()
                        cand = compute_vectorized_unit_info(cand)
                        cand_pure = cand[_check_pure_land_mask(cand['ประเภททรัพย์']) & (cand['ราคา'] > 0)] if not cand.empty else pd.DataFrame()
                        if not cand_pure.empty:
                            land_raw = cand
                            land_source_desc = f"ที่ดินเปล่ารอบโครงการ (จ.{proj_provs[0]})"

                # C. Final fallback if nothing else matched
                if land_raw.empty:
                    land_raw = proj_df
                    land_source_desc = f"ตามโครงการ: {active_proj}"
        else:
            source_icon = "fa-location-dot"
            land_raw = df_raw.copy() if df_raw is not None else pd.DataFrame()
            if active_subdist and not land_raw.empty and 'ตำบล' in land_raw.columns:
                clean_target_subs = [s.split(' (')[0].strip() for s in active_subdist]
                land_raw = land_raw[land_raw['ตำบล'].astype(str).str.strip().isin(clean_target_subs)]
                if active_dist and 'อำเภอ' in land_raw.columns:
                    clean_target_dists = [d.split(' (')[0].strip() for d in active_dist]
                    land_raw = land_raw[land_raw['อำเภอ'].astype(str).str.strip().isin(clean_target_dists)]
                if active_prov and 'จังหวัด' in land_raw.columns:
                    land_raw = land_raw[land_raw['จังหวัด'].astype(str).str.strip().isin(active_prov)]
                clean_s_name = active_subdist[0].split(' (')[0].strip()
                clean_d_name = active_dist[0].split(' (')[0].strip() if active_dist else ""
                land_source_desc = f"ตามทำเล ต.{clean_s_name} อ.{clean_d_name}"
            elif active_dist and not land_raw.empty and 'อำเภอ' in land_raw.columns:
                clean_target_dists = [d.split(' (')[0].strip() for d in active_dist]
                land_raw = land_raw[land_raw['อำเภอ'].astype(str).str.strip().isin(clean_target_dists)]
                if active_prov and 'จังหวัด' in land_raw.columns:
                    land_raw = land_raw[land_raw['จังหวัด'].astype(str).str.strip().isin(active_prov)]
                clean_d_name = active_dist[0].split(' (')[0].strip()
                clean_p_name = active_prov[0] if active_prov else ""
                land_source_desc = f"ตามทำเล อ.{clean_d_name} จ.{clean_p_name}"
            elif active_prov and not land_raw.empty and 'จังหวัด' in land_raw.columns:
                land_raw = land_raw[land_raw['จังหวัด'].astype(str).str.strip().isin(active_prov)]
                clean_p_name = active_prov[0]
                land_source_desc = f"ตามทำเล จ.{clean_p_name}"
            else:
                land_source_desc = "ตามทำเล ภาพรวมทั่วประเทศ"
            land_raw = compute_vectorized_unit_info(land_raw)

        is_scope_pure_land = _check_pure_land_mask(land_raw['ประเภททรัพย์']) if not land_raw.empty else pd.Series(False, index=land_raw.index)
        land_pool_df = land_raw[is_scope_pure_land & (land_raw['ราคา'] > 0)].copy() if not land_raw.empty else pd.DataFrame()

        # If company filter active and matching land exists for that company, use company-specific land; otherwise use all land in scope
        if active_cos and not land_pool_df.empty and 'บริษัท' in land_pool_df.columns:
            co_land = land_pool_df[land_pool_df['บริษัท'].isin(active_cos)]
            if not co_land.empty:
                land_pool_df = co_land

        has_raw_land = False
        median_raw_land = min_raw_land = max_raw_land = 0.0
        count_raw_land = 0
        if not land_pool_df.empty:
            rl_u = land_pool_df['ราคาต่อหน่วย'].dropna()
            rl_u = rl_u[rl_u > 0]
            if not rl_u.empty:
                median_raw_land = float(rl_u.median())
                min_raw_land = float(rl_u.min())
                max_raw_land = float(rl_u.max())
                count_raw_land = len(rl_u)
                has_raw_land = True

        # Pure land mask for filtered_nearby
        is_fn_pure_land = _check_pure_land_mask(filtered_nearby['ประเภททรัพย์']) if not filtered_nearby.empty else pd.Series(False, index=filtered_nearby.index)

        # Check if the user explicitly selected pure land in the map filter
        user_filtered_pure_land = bool(active_types and all(('ที่ดิน' in t and not any(k in t for k in ['บ้าน', 'อาคาร', 'ทาวน์', 'คอนโด', 'ตึก', 'โรงงาน', 'พาณิชย์', 'หอพัก', 'สิ่งปลูกสร้าง'])) for t in active_types))

        # -------------------------------------------------------------
        # 2. Calculate Median for Target Type (Card 3)
        # -------------------------------------------------------------
        has_sel_u_stats = False
        median_u_sel = min_u_sel = max_u_sel = 0.0
        unit_lbl_sel = "ตร.ว."
        count_u_sel = 0
        
        if active_types:
            calc_type_df = filtered_nearby[filtered_nearby['ประเภททรัพย์'].isin(active_types)].copy() if not filtered_nearby.empty else pd.DataFrame()
            t_lbl = ", ".join(active_types)
        elif target_type:
            calc_type_df = filtered_nearby[filtered_nearby['ประเภททรัพย์'] == target_type].copy() if not filtered_nearby.empty else pd.DataFrame()
            t_lbl = target_type
        else:
            # If no filter selected, do NOT mix pure land into general buildings!
            calc_type_df = filtered_nearby[~is_fn_pure_land].copy() if not filtered_nearby.empty else pd.DataFrame()
            t_lbl = "ประเภททรัพย์เป้าหมาย"

        if not calc_type_df.empty:
            u_sel = calc_type_df['ราคาต่อหน่วย'].dropna()
            u_sel = u_sel[u_sel > 0]
            if not u_sel.empty:
                median_u_sel = float(u_sel.median())
                min_u_sel = float(u_sel.min())
                max_u_sel = float(u_sel.max())
                modes = calc_type_df[calc_type_df['หน่วยวัด'] != '-']['หน่วยวัด'].mode()
                unit_lbl_sel = modes[0] if not modes.empty else "ตร.ว."
                count_u_sel = len(u_sel)
                has_sel_u_stats = True

        # -------------------------------------------------------------
        # 3. Calculate Median for Sq. Wah
        # Separate pure land: do NOT combine pure land with houses/buildings unless user explicitly filtered pure land
        # -------------------------------------------------------------
        has_sqw_median = False
        median_sqw_val = 0.0
        count_sqw_val = 0
        min_sqw_val = max_sqw_val = 0.0

        if user_filtered_pure_land:
            sqw_calc_df = filtered_nearby[is_fn_pure_land].copy() if not filtered_nearby.empty else pd.DataFrame()
        elif active_types:
            sqw_calc_df = filtered_nearby.copy()
        else:
            # Default when no type filter selected in map: exclude pure land so it does not mix with houses/buildings!
            sqw_calc_df = filtered_nearby[~is_fn_pure_land].copy() if not filtered_nearby.empty else pd.DataFrame()

        if not sqw_calc_df.empty:
            sqw_vals = pd.to_numeric(sqw_calc_df.get('พื้นที่_ตารางวา', np.nan), errors='coerce')
            if 'เนื้อที่ (ตร.ว.)' in sqw_calc_df.columns:
                sqw_vals = sqw_vals.combine_first(pd.to_numeric(sqw_calc_df['เนื้อที่ (ตร.ว.)'], errors='coerce'))
            price_vals = pd.to_numeric(sqw_calc_df['ราคา'], errors='coerce')
            valid_mask_sqw = (sqw_vals > 0) & (price_vals > 0)
            sqw_rates = (price_vals[valid_mask_sqw] / sqw_vals[valid_mask_sqw]).dropna()
            sqw_rates = sqw_rates[sqw_rates > 0]
            if not sqw_rates.empty:
                median_sqw_val = float(sqw_rates.median())
                min_sqw_val = float(sqw_rates.min())
                max_sqw_val = float(sqw_rates.max())
                count_sqw_val = len(sqw_rates)
                has_sqw_median = True

        # Calculate Median for All Sq. Metre (พื้นที่ใช้สอย) in filtered_nearby
        has_sqm_median = False
        median_sqm_val = 0.0
        count_sqm_val = 0
        min_sqm_val = max_sqm_val = 0.0
        if not filtered_nearby.empty and 'พื้นที่ใช้สอย (ตร.ม.)' in filtered_nearby.columns:
            sqm_vals = pd.to_numeric(filtered_nearby['พื้นที่ใช้สอย (ตร.ม.)'], errors='coerce')
            price_vals = pd.to_numeric(filtered_nearby['ราคา'], errors='coerce')
            valid_mask_sqm = (sqm_vals > 0) & (price_vals > 0)
            sqm_rates = (price_vals[valid_mask_sqm] / sqm_vals[valid_mask_sqm]).dropna()
            sqm_rates = sqm_rates[sqm_rates > 0]
            if not sqm_rates.empty:
                median_sqm_val = float(sqm_rates.median())
                min_sqm_val = float(sqm_rates.min())
                max_sqm_val = float(sqm_rates.max())
                count_sqm_val = len(sqm_rates)
                has_sqm_median = True

        # Render 4 Metric Cards (Total Count, Target Type, Pure Land, Sq. Metre)
        card_c1, card_c2, card_c3, card_c4 = st.columns(4)
        total_nearby_cnt = len(filtered_nearby)

        # Card 1: Reference Info (Total Count as Primary Metric)
        if active_ref_prop is not None:
            p_co = active_ref_prop.get('บริษัท', '-')
            p_code = active_ref_prop.get('รหัสทรัพย์', '-')
            p_type_str = str(active_ref_prop.get('ประเภททรัพย์', '-'))
            sub_ref_info = f"<div id='median-card1-sub' style='color: #94a3b8; font-size: 0.74rem; margin-top: 2px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;'>[{p_co}] {p_code} &bull; {p_type_str}</div>"
        elif active_ref_lat and active_ref_lon:
            sub_ref_info = "<div id='median-card1-sub' style='color: #94a3b8; font-size: 0.74rem; margin-top: 2px;'>กำหนดจากพิกัดแผนที่</div>"
        else:
            sub_ref_info = f"<div id='median-card1-sub' style='color: #94a3b8; font-size: 0.74rem; margin-top: 2px;'>{scope_header}</div>"

        card1_loc_detail = f"{active_ref_lat:.5f}, {active_ref_lon:.5f} (รัศมี {active_ref_radius:.1f} กม.)" if (active_ref_lat and active_ref_lon) else scope_header
        card1_html = (
            f"<div class='metric-card' id='median-card-1' style='background: rgba(16, 185, 129, 0.04); border: 1px solid rgba(16, 185, 129, 0.25); border-radius: 12px; padding: 12px 14px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); min-height: 140px; display: flex; flex-direction: column; justify-content: space-between;'>"
            f"<div>"
            f"<div style='font-size: 0.78rem; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.4px;'><i class='fa-solid fa-layer-group' style='color: #10b981; margin-right:4px;'></i> จำนวนทรัพย์ทั้งหมด</div>"
            f"<div id='median-card1-val' style='font-size: 1.55rem; font-weight: 800; color: #059669; margin: 3px 0;'>{total_nearby_cnt:,} <span style='font-size:0.85rem; font-weight:600; color:#64748b;'>รายการ</span></div>"
            f"</div>"
            f"<div>"
            f"<div id='median-card1-loc' style='color: #64748b; font-size: 0.76rem;'><i class='fa-solid fa-location-dot' style='color:#10b981; font-size:0.72rem; margin-right:3px;'></i>{card1_loc_detail}</div>"
            f"{sub_ref_info}"
            f"</div>"
            f"</div>"
        )

        # Card 2: Median Sq. Metre (All Properties)
        if has_sqm_median:
            c3_main = f"฿{median_sqm_val:,.0f}"
            c3_unit = "/ตร.ม."
            c3_sub = f"ต่ำสุด ฿{min_sqm_val:,.0f} &bull; สูงสุด ฿{max_sqm_val:,.0f}"
            c3_badge = f"<span style='font-size:0.74rem; font-weight:600; color:#10b981;'>({count_sqm_val:,} แปลง)</span>"
        else:
            c3_main = "-"
            c3_unit = ""
            c3_sub = "ไม่มีข้อมูลพื้นที่ใช้สอย"
            c3_badge = ""

        card3_html = (
            f"<div class='metric-card' id='median-card-2' style='background: rgba(16, 185, 129, 0.04); border: 1px solid rgba(16, 185, 129, 0.25); border-radius: 12px; padding: 12px 14px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); min-height: 140px; display: flex; flex-direction: column; justify-content: space-between;'>"
            f"<div>"
            f"<div id='median-card2-title' style='font-size: 0.78rem; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.4px;'><i class='fa-solid fa-ruler-combined' style='color: #10b981; margin-right:4px;'></i> ราคากลาง / ตร.ม. <span id='median-card2-badge'>{c3_badge}</span></div>"
            f"<div id='median-card2-val' style='font-size: 1.55rem; font-weight: 800; color: #059669; margin: 3px 0;'>{c3_main} <span style='font-size:0.85rem; font-weight:600; color:#64748b;'>{c3_unit}</span></div>"
            f"</div>"
            f"<div id='median-card2-sub' style='color: #64748b; font-size: 0.76rem;'>{c3_sub}</div>"
            f"</div>"
        )

        # Card 3: Target Type
        if has_sel_u_stats:
            c4_main = f"฿{median_u_sel:,.0f}"
            c4_unit = f"/{unit_lbl_sel}"
            c4_sub = f"ต่ำสุด ฿{min_u_sel:,.0f} &bull; สูงสุด ฿{max_u_sel:,.0f}"
            c4_badge = f"<span style='font-size:0.74rem; font-weight:600; color:#10b981;'>({count_u_sel:,} แปลง)</span>"
        else:
            c4_main = "-"
            c4_unit = ""
            c4_sub = f"ไม่มีข้อมูลราคาสำหรับ {t_lbl}"
            c4_badge = ""

        card4_html = (
            f"<div class='metric-card' id='median-card-3' style='background: rgba(16, 185, 129, 0.04); border: 1px solid rgba(16, 185, 129, 0.25); border-radius: 12px; padding: 12px 14px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); min-height: 140px; display: flex; flex-direction: column; justify-content: space-between;'>"
            f"<div>"
            f"<div id='median-card3-title' style='font-size: 0.78rem; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.4px;'><i class='fa-solid fa-house' style='color: #10b981; margin-right:4px;'></i> ราคากลาง {t_lbl} <span id='median-card3-badge'>{c4_badge}</span></div>"
            f"<div id='median-card3-val' style='font-size: 1.55rem; font-weight: 800; color: #059669; margin: 3px 0;'>{c4_main} <span style='font-size:0.85rem; font-weight:600; color:#64748b;'>{c4_unit}</span></div>"
            f"</div>"
            f"<div id='median-card3-sub' style='color: #64748b; font-size: 0.76rem;'>{c4_sub}</div>"
            f"</div>"
        )

        # Card 4: Pure Land (Always separated and displayed with explicit source)
        if has_raw_land:
            c5_main = f"฿{median_raw_land:,.0f}"
            c5_unit = "/ตร.ว."
            c5_sub = f"ต่ำสุด ฿{min_raw_land:,.0f} &bull; สูงสุด ฿{max_raw_land:,.0f}"
            c5_badge = f"<span style='font-size:0.74rem; font-weight:600; color:#10b981;'>({count_raw_land:,} แปลง)</span>"
        else:
            c5_main = "-"
            c5_unit = ""
            c5_sub = "ไม่พบข้อมูลที่ดินเปล่าในขอบเขตนี้"
            c5_badge = ""

        card5_html = (
            f"<div class='metric-card' id='median-card-4' style='background: rgba(16, 185, 129, 0.04); border: 1px solid rgba(16, 185, 129, 0.25); border-radius: 12px; padding: 12px 14px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); min-height: 140px; display: flex; flex-direction: column; justify-content: space-between;'>"
            f"<div>"
            f"<div id='median-card4-title' style='font-size: 0.78rem; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.4px;'><i class='fa-solid fa-mountain-sun' style='color: #10b981; margin-right:4px;'></i> ราคากลางที่ดินเปล่า <span id='median-card4-badge'>{c5_badge}</span></div>"
            f"<div id='median-card4-val' style='font-size: 1.55rem; font-weight: 800; color: #059669; margin: 3px 0;'>{c5_main} <span style='font-size:0.85rem; font-weight:600; color:#64748b;'>{c5_unit}</span></div>"
            f"</div>"
            f"<div>"
            f"<div id='median-card4-source' style='color: #059669; font-size: 0.76rem; font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;' title='{land_source_desc}'><i class='fa-solid {source_icon}' style='font-size:0.72rem; margin-right:3px;'></i>{land_source_desc}</div>"
            f"<div id='median-card4-sub' style='color: #64748b; font-size: 0.74rem; margin-top: 1px;'>{c5_sub}</div>"
            f"</div>"
            f"</div>"
        )

        with card_c1:
            st.html(card1_html)
        with card_c2:
            st.html(card4_html)
        with card_c3:
            st.html(card5_html)
        with card_c4:
            st.html(card3_html)

        # Nearby Assets Table (Direct display with icon instead of expander)
        filter_summary_str = f" [กรอง: {', '.join(active_cos)}]" if active_cos else ""
        if not filtered_nearby.empty:
            st.markdown(
                f"<div style='margin-top: 22px; margin-bottom: 12px; font-weight: 700; font-size: 1.06rem; display: flex; align-items: center; justify-content: space-between;'>"
                f"<span><i class='fa-solid fa-table-list' style='color:#059669; margin-right:8px;'></i>"
                f"<span id='median-table-title'>รายการทรัพย์สิน ({len(filtered_nearby):,} รายการ {scope_header}{filter_summary_str})</span></span>"
                f"<span style='font-size: 0.8rem; font-weight: 600; color: #059669; background: rgba(16, 185, 129, 0.1); padding: 4px 12px; border-radius: 20px; border: 1.2px solid rgba(16, 185, 129, 0.3);'>"
                f"<i class='fa-solid fa-layer-group' style='margin-right:5px;'></i>ตารางเปรียบเทียบข้อมูลทรัพย์</span>"
                f"</div>",
                unsafe_allow_html=True
            )
            # Build detailed analysis dataframe for display
            show_df = pd.DataFrame(index=filtered_nearby.index)
            
            # 1. บริษัท, รหัสทรัพย์, ประเภททรัพย์
            for col in ['บริษัท', 'รหัสทรัพย์', 'ประเภททรัพย์']:
                if col in filtered_nearby.columns:
                    show_df[col] = filtered_nearby[col]
            
            # 2. ราคา (บาท)
            price_num = pd.to_numeric(filtered_nearby['ราคา'], errors='coerce') if 'ราคา' in filtered_nearby.columns else pd.Series(np.nan, index=filtered_nearby.index)
            show_df['ราคา (บาท)'] = price_num
            
            # 3. เนื้อที่ (ไร่-งาน-ตร.ว.) - รูปแบบ 0-0-0
            col_sqw_name = 'พื้นที่_ตารางวา' if 'พื้นที่_ตารางวา' in filtered_nearby.columns else ('เนื้อที่ (ตร.ว.)' if 'เนื้อที่ (ตร.ว.)' in filtered_nearby.columns else None)
            sqw_vals = filtered_nearby[col_sqw_name].apply(to_float_sqwah) if col_sqw_name else pd.Series(np.nan, index=filtered_nearby.index)
            if 'พื้นที่_ตารางวา' in filtered_nearby.columns and col_sqw_name != 'พื้นที่_ตารางวา':
                sqw_vals = sqw_vals.fillna(filtered_nearby['พื้นที่_ตารางวา'].apply(to_float_sqwah))

            if 'เนื้อที่ (ตร.ว.)' in filtered_nearby.columns:
                formatted_sqw = filtered_nearby['เนื้อที่ (ตร.ว.)'].apply(format_to_rai_ngan_wah)
                formatted_sqw = formatted_sqw.where(formatted_sqw != "-", sqw_vals.apply(format_to_rai_ngan_wah))
            else:
                formatted_sqw = sqw_vals.apply(format_to_rai_ngan_wah)
            show_df['เนื้อที่ (ไร่-งาน-ตร.ว.)'] = formatted_sqw

            # 4. ราคาต่อตร.ว. (บาท)
            if 'ราคาต่อตารางวา' in filtered_nearby.columns:
                calc_p_sqw = pd.to_numeric(filtered_nearby['ราคาต่อตารางวา'], errors='coerce')
                fallback_sqw = np.where((price_num > 0) & (sqw_vals > 0), price_num / sqw_vals, np.nan)
                calc_p_sqw = np.where(calc_p_sqw > 0, calc_p_sqw, fallback_sqw)
            else:
                calc_p_sqw = np.where((price_num > 0) & (sqw_vals > 0), price_num / sqw_vals, np.nan)
            show_df['ราคาต่อตร.ว. (บาท)'] = calc_p_sqw

            # 5. เทียบราคากลางต่อ ตร.ว. (คำนวณราคากลางแยกตามประเภททรัพย์ของแต่ละแถว)
            def _fmt_diff_pct(val, med):
                if pd.isna(val) or val <= 0 or pd.isna(med) or med <= 0:
                    return "-"
                diff = ((val - med) / med) * 100.0
                if diff > 0:
                    return f"↑ +{diff:.1f}%"
                elif diff < 0:
                    return f"↓ {diff:.1f}%"
                else:
                    return "0.0%"

            # Calculate sqm and per-sqm rates
            sqm_vals = filtered_nearby['พื้นที่ใช้สอย (ตร.ม.)'].apply(to_float_sqm) if 'พื้นที่ใช้สอย (ตร.ม.)' in filtered_nearby.columns else pd.Series(np.nan, index=filtered_nearby.index)

            if 'ราคาต่อตารางเมตร' in filtered_nearby.columns:
                calc_p_sqm = pd.to_numeric(filtered_nearby['ราคาต่อตารางเมตร'], errors='coerce')
                fallback_sqm = np.where((price_num > 0) & (sqm_vals > 0), price_num / sqm_vals, np.nan)
                calc_p_sqm = np.where(calc_p_sqm > 0, calc_p_sqm, fallback_sqm)
            else:
                calc_p_sqm = np.where((price_num > 0) & (sqm_vals > 0), price_num / sqm_vals, np.nan)

            # Calculate per-type medians for sqw and sqm across active properties in filtered_nearby
            type_sqw_medians = {}
            type_sqm_medians = {}
            p_types_series = filtered_nearby['ประเภททรัพย์'].astype(str).str.strip() if 'ประเภททรัพย์' in filtered_nearby.columns else pd.Series([], dtype=str)
            if not filtered_nearby.empty and not p_types_series.empty:
                sqw_calc_rates = pd.Series(calc_p_sqw, index=filtered_nearby.index)
                for pt, sub_idx in filtered_nearby.groupby(p_types_series).groups.items():
                    sub_rates = sqw_calc_rates.loc[sub_idx].dropna()
                    sub_rates = sub_rates[sub_rates > 0]
                    if not sub_rates.empty:
                        type_sqw_medians[pt] = float(sub_rates.median())

                sqm_calc_rates = pd.Series(calc_p_sqm, index=filtered_nearby.index)
                for pt, sub_idx in filtered_nearby.groupby(p_types_series).groups.items():
                    sub_rates = sqm_calc_rates.loc[sub_idx].dropna()
                    sub_rates = sub_rates[sub_rates > 0]
                    if not sub_rates.empty:
                        type_sqm_medians[pt] = float(sub_rates.median())

            # 5. เทียบราคากลางต่อ ตร.ว. (เทียบกับราคากลางต่อ ตร.ว. ตามประเภททรัพย์นั้นๆ ในพื้นที่)
            def _get_target_med_sqw(idx, p_type_str):
                pt_clean = str(p_type_str).strip()
                if any(k in pt_clean for k in ['คอนโด', 'ห้องชุด', 'อาคารชุด']):
                    return None
                if pt_clean in type_sqw_medians:
                    return type_sqw_medians[pt_clean]
                if idx in is_fn_pure_land.index and is_fn_pure_land.loc[idx] and median_raw_land > 0:
                    return median_raw_land
                return median_sqw_val if median_sqw_val > 0 else None

            show_df['เทียบราคากลางต่อ ตร.ว.'] = [
                _fmt_diff_pct(v, _get_target_med_sqw(idx, p_t))
                for idx, v, p_t in zip(show_df.index, calc_p_sqw, p_types_series)
            ]

            # 6. เทียบราคากับ ตร.ว. ของที่ดินเปล่า (Benchmark เทียบมูลค่าที่ดินเปล่าในพื้นที่)
            show_df['เทียบราคากับ ตร.ว. ของที่ดินเปล่า'] = [
                _fmt_diff_pct(v, median_raw_land) if not any(k in str(p_t) for k in ['คอนโด', 'ห้องชุด', 'อาคารชุด']) else "-"
                for v, p_t in zip(calc_p_sqw, p_types_series)
            ]

            # 7. พื้นที่ใช้สอย (ตร.ม.) - ย้ายมาต่อจากกลุ่มเทียบราคากลางต่อ ตร.ว.
            show_df['พื้นที่ใช้สอย (ตร.ม.)'] = sqm_vals

            # 8. ราคาต่อตร.ม. (บาท)
            show_df['ราคาต่อตร.ม. (บาท)'] = calc_p_sqm

            # 9. เทียบราคากลางต่อ ตร.ม. (เทียบกับราคากลาง ตร.ม. ตามประเภททรัพย์นั้นๆ ในพื้นที่)
            def _get_target_med_sqm(p_type_str):
                pt_clean = str(p_type_str).strip()
                if pt_clean in type_sqm_medians:
                    return type_sqm_medians[pt_clean]
                return median_sqm_val if median_sqm_val > 0 else None

            show_df['เทียบราคากลางต่อ ตร.ม.'] = [
                _fmt_diff_pct(v, _get_target_med_sqm(p_t))
                for v, p_t in zip(calc_p_sqm, p_types_series)
            ]

            # 10. ระยะทาง (กม.) (ถ้ามีการค้นหาตามพิกัดรัศมี)
            if 'ระยะทาง (กม.)' in filtered_nearby.columns:
                show_df['ระยะทาง (กม.)'] = pd.to_numeric(filtered_nearby['ระยะทาง (กม.)'], errors='coerce')
                show_df = show_df.sort_values(by='ระยะทาง (กม.)', ascending=True)

            # 11. ตำบล, อำเภอ, จังหวัด
            for loc_c in ['ตำบล', 'อำเภอ', 'จังหวัด']:
                if loc_c in filtered_nearby.columns:
                    show_df[loc_c] = filtered_nearby[loc_c]

            # 11.5 ยอดเข้าชม
            if 'ยอดเข้าชม' in filtered_nearby.columns:
                show_df['ยอดเข้าชม'] = pd.to_numeric(filtered_nearby['ยอดเข้าชม'], errors='coerce')

            # 12. เปิดลิงก์
            if 'ลิงก์' in filtered_nearby.columns:
                show_df['เปิดลิงก์'] = filtered_nearby['ลิงก์']

            table_col_config = {
                "ราคา (บาท)": st.column_config.NumberColumn("ราคา (บาท)", format="฿%,d"),
                "ยอดเข้าชม": st.column_config.NumberColumn("ยอดเข้าชม (วิว)", format="%,d"),
                "เนื้อที่ (ไร่-งาน-ตร.ว.)": st.column_config.TextColumn(
                    "เนื้อที่ (ไร่-งาน-ตร.ว.)",
                    help="ขนาดเนื้อที่ดินในรูปแบบ ไร่-งาน-ตารางวา (0-0-0)"
                ),
                "เนื้อที่ (ตร.ว.)": st.column_config.TextColumn(
                    "เนื้อที่ (ไร่-งาน-ตร.ว.)",
                    help="ขนาดเนื้อที่ดินในรูปแบบ ไร่-งาน-ตารางวา (0-0-0)"
                ),
                "ราคาต่อตร.ว. (บาท)": st.column_config.NumberColumn("ราคาต่อตร.ว. (บาท)", format="฿%,d"),
                "เทียบราคากลางต่อ ตร.ว.": st.column_config.TextColumn(
                    "เทียบราคากลางต่อ ตร.ว.",
                    help="เทียบกับราคากลางต่อ ตร.ว. ตามประเภททรัพย์นั้นๆ ในพื้นที่ (ค่าบวก = สูงกว่าราคากลางประเภทนั้น, ค่าลบ = ถูกกว่าราคากลางประเภทนั้น)"
                ),
                "เทียบราคากับ ตร.ว. ของที่ดินเปล่า": st.column_config.TextColumn(
                    "เทียบราคากับ ตร.ว. ของที่ดินเปล่า",
                    help=f"เทียบกับราคากลาง ตร.ว. ของที่ดินเปล่าแท้ๆ ในพื้นที่ (฿{median_raw_land:,.0f}/ตร.ว.) เพื่อดูส่วนต่างจากราคาที่ดินดิบ" if median_raw_land > 0 else "เทียบราคากลางที่ดินเปล่า"
                ),
                "พื้นที่ใช้สอย (ตร.ม.)": st.column_config.NumberColumn("พื้นที่ใช้สอย (ตร.ม.)", format="%,.1f"),
                "ราคาต่อตร.ม. (บาท)": st.column_config.NumberColumn("ราคาต่อตร.ม. (บาท)", format="฿%,d"),
                "เทียบราคากลางต่อ ตร.ม.": st.column_config.TextColumn(
                    "เทียบราคากลางต่อ ตร.ม.",
                    help="เทียบกับราคากลางต่อ ตร.ม. ตามประเภททรัพย์นั้นๆ ในพื้นที่ (ค่าบวก = สูงกว่าราคากลางประเภทนั้น, ค่าลบ = ถูกกว่าราคากลางประเภทนั้น)"
                ),
                "ระยะทาง (กม.)": st.column_config.NumberColumn("ระยะทาง (กม.)", format="%.2f กม."),
                "เปิดลิงก์": st.column_config.LinkColumn("เปิดลิงก์", display_text="เปิดดูทรัพย์"),
            }

            def highlight_diff_cells(val):
                s = str(val).strip()
                if s in ["-", "", "nan", "None", "0.0%"]:
                    return ""
                if s.startswith("↑") or s.startswith("▲"):
                    return "color: #047857; font-weight: 700; background-color: rgba(16, 185, 129, 0.12); border: 1.5px solid rgba(16, 185, 129, 0.4); border-radius: 6px;"
                elif s.startswith("↓") or s.startswith("▼"):
                    return "color: #b91c1c; font-weight: 700; background-color: rgba(239, 68, 68, 0.12); border: 1.5px solid rgba(239, 68, 68, 0.4); border-radius: 6px;"
                return ""

            diff_target_cols = [c for c in ['เทียบราคากลางต่อ ตร.ว.', 'เทียบราคากับ ตร.ว. ของที่ดินเปล่า', 'เทียบราคากลางต่อ ตร.ม.'] if c in show_df.columns]
            
            # Pandas Styler has a cell rendering cap (default 262,144 cells).
            # When viewing large datasets (e.g. nationwide or thousands of rows), render show_df
            # directly via Arrow to maintain ultra-fast virtualized scrolling and avoid Styler memory exceptions.
            df_to_render = show_df
            if diff_target_cols and show_df.size <= 200_000:
                try:
                    df_to_render = show_df.style.map(highlight_diff_cells, subset=diff_target_cols)
                except Exception:
                    df_to_render = show_df

            try:
                st.dataframe(df_to_render, use_container_width=True, height=380, column_config=table_col_config)
            except Exception:
                st.dataframe(show_df, use_container_width=True, height=380, column_config=table_col_config)
            # ── Import / Export (same style as Tab 1) ──
            render_import_export_section(show_df, filename_prefix=f"comparison_{scope_header.replace(' ', '_')}", key_suffix="tab2_compare")
        else:
            st.info(f"ไม่พบรายการทรัพย์สินที่ตรงตามเงื่อนไขตัวกรอง {scope_header}")
