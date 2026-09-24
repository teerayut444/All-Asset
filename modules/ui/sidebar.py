import os
import base64
import datetime
import pandas as pd
import streamlit as st
import user_logger
from modules.services.data_cleaner import get_dataset_month_year

def render_sidebar(df_raw):
    """Renders the top sidebar: Logo, Theme toggle, Data source summary, Clear cache, and Admin Visitor Logs."""
    with st.sidebar:
        col_side_title, col_side_theme = st.columns([0.72, 0.28])
        with col_side_title:
            sb_logo_path = os.path.join("logo", "logo.png") if os.path.exists(os.path.join("logo", "logo.png")) else os.path.join("assets", "logo.png")
            if os.path.exists(sb_logo_path):
                with open(sb_logo_path, "rb") as f_logo:
                    sb_logo_b64 = base64.b64encode(f_logo.read()).decode("utf-8")
                sb_logo_img = f'<div style="width: 40px; height: 40px; min-width: 40px; display: flex; align-items: center; justify-content: center;"><img src="data:image/png;base64,{sb_logo_b64}" style="width: 100%; height: 100%; object-fit: contain; filter: drop-shadow(0 2px 6px rgba(0,0,0,0.3));"></div>'
            else:
                sb_logo_img = '<i class="fa-solid fa-city" style="margin-right:6px; font-size:1.25rem; color:#34d399;"></i>'
                
            st.markdown(f'''
            <div style="display: flex; align-items: center; gap: 9px; margin-bottom: 2px; padding-top: 2px;">
                {sb_logo_img}
                <div style="display: flex; flex-direction: column;">
                    <div style="font-size: 1.35rem; font-weight: 800; color: #ffffff; line-height: 1.1; letter-spacing: -0.5px;">NOVA</div>
                    <div style="font-size: 0.68rem; font-weight: 700; color: #a7f3d0; letter-spacing: 0.8px;">NPA DASHBOARD</div>
                </div>
            </div>
            ''', unsafe_allow_html=True)
            
        with col_side_theme:
            col_t1, col_t2 = st.columns([0.65, 0.35])
            with col_t1:
                is_dark_mode = st.toggle("โหมดมืด", value=False, key="app_theme_mode", label_visibility="collapsed", help="สลับระหว่างโหมดมืดและโหมดสว่าง (Dark / Light Mode)")
            with col_t2:
                st.markdown(f'''<div style="padding-top: 6px; font-size: 1.15rem; color: {'#34d399' if is_dark_mode else '#6ee7b7'};"><i class="fa-solid fa-moon"></i></div>''', unsafe_allow_html=True)
        
        if df_raw is not None and not df_raw.empty:
            src_name = getattr(df_raw, 'attrs', {}).get('source', 'all_assets.parquet')
            _, exact_date_str = get_dataset_month_year(df_raw)
            st.markdown(f"""
            <div style="background: rgba(255, 255, 255, 0.08); border: 1px solid rgba(110, 231, 183, 0.25); border-radius: 8px; padding: 7px 10px; margin-top: 5px; margin-bottom: 8px; font-size: 0.8rem; color: #f0fdf4; font-weight: 600;">
                <i class="fa fa-database" style="color:#34d399;"></i> แหล่งข้อมูล: <code style="background:rgba(0,0,0,0.25); color:#a7f3d0; padding:1px 5px; border-radius:4px;">{src_name}</code><br/>
                <span style="font-size: 0.75rem; color: #6ee7b7; font-weight: 600;"><i class="fa fa-calendar-check" style="margin-right: 3px; color:#34d399;"></i> ดึงข้อมูล: <b style="color:#ffffff;">{exact_date_str}</b></span>
            </div>
            """, unsafe_allow_html=True)
            
        btn_clear_cache_clicked = st.button("รีโหลดแคช", icon=":material/refresh:", key="btn_clear_cache_main", use_container_width=True, help="ล้างแคชและรีเฟรชหน้าเว็บใหม่ล่าสุดทันที")

        if btn_clear_cache_clicked:
            st.cache_data.clear()
            st.cache_resource.clear()
            try:
                st.query_params.clear()
            except Exception:
                pass
            for k in list(st.session_state.keys()):
                st.session_state.pop(k, None)
            
            overlay_bg = "rgba(15, 23, 42, 0.94)" if is_dark_mode else "rgba(255, 255, 255, 0.94)"
            overlay_title = "#34d399" if is_dark_mode else "#064e3b"
            overlay_desc = "#94a3b8" if is_dark_mode else "#047857"
            
            st.html(f"""
            <div style="position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; background: {overlay_bg}; backdrop-filter: blur(6px); z-index: 99999999; display: flex; flex-direction: column; align-items: center; justify-content: center; font-family: 'Noto Sans Thai', 'Inter', sans-serif;">
                <div style="width: 52px; height: 52px; border: 4px solid rgba(16, 185, 129, 0.2); border-top: 4px solid #10b981; border-radius: 50%; animation: spinClear 0.75s linear infinite; margin-bottom: 18px;"></div>
                <h3 style="color: {overlay_title}; font-weight: 800; font-size: 1.35rem; margin: 0 0 8px 0; letter-spacing: -0.3px;">กำลังล้างแคชและรีเซ็ตหน้าเว็บ...</h3>
                <p style="color: {overlay_desc}; font-size: 0.92rem; margin: 0; font-weight: 500;">ระบบกำลังล้างพิกัดเก่าและอ่านข้อมูลใหม่ล่าสุด กรุณารอสักครู่</p>
            </div>
            <style>
            @keyframes spinClear {{ from {{ transform: rotate(0deg); }} to {{ transform: rotate(360deg); }} }}
            </style>
            <script>
            setTimeout(function() {{
                var cleanUrl = window.location.origin + window.location.pathname;
                try {{
                    if (window.parent && window.parent !== window) {{
                        window.parent.location.href = window.parent.location.origin + window.parent.location.pathname;
                        return;
                    }}
                }} catch(err) {{}}
                window.location.href = cleanUrl;
            }}, 350);
            </script>
            """, unsafe_allow_javascript=True)
            st.stop()

        # Log visitor
        if "_visitor_logged" not in st.session_state:
            try:
                user_logger.log_visit()
                st.session_state["_visitor_logged"] = True
            except Exception:
                st.session_state["_visitor_logged"] = True

        # Visitor Access Logs (Admin Only)
        st.html("""<style>
        section[data-testid="stSidebar"] [data-testid="stExpander"] {
            background: transparent !important;
            border: none !important;
            box-shadow: none !important;
            padding: 0 !important;
            margin-bottom: 10px !important;
        }
        section[data-testid="stSidebar"] [data-testid="stExpander"] > details {
            background-color: rgba(2, 44, 34, 0.85) !important;
            background: rgba(2, 44, 34, 0.85) !important;
            border: 1px solid rgba(52, 211, 153, 0.35) !important;
            border-radius: 10px !important;
            overflow: hidden !important;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2) !important;
            padding: 0 !important;
            margin: 0 !important;
        }
        section[data-testid="stSidebar"] [data-testid="stExpander"] > details > summary {
            background-color: transparent !important;
            color: #ffffff !important;
            border: none !important;
            padding: 9px 12px !important;
            margin: 0 !important;
            display: flex !important;
            align-items: center !important;
            cursor: pointer !important;
        }
        section[data-testid="stSidebar"] [data-testid="stExpander"] > details > summary:hover {
            background-color: rgba(16, 185, 129, 0.15) !important;
        }
        section[data-testid="stSidebar"] [data-testid="stExpander"] > details[open] > summary {
            border-bottom: 1px solid rgba(52, 211, 153, 0.25) !important;
        }
        section[data-testid="stSidebar"] [data-testid="stExpander"] > details > summary p,
        section[data-testid="stSidebar"] [data-testid="stExpander"] > details > summary span,
        section[data-testid="stSidebar"] [data-testid="stExpander"] > details > summary div {
            color: #ffffff !important;
            -webkit-text-fill-color: #ffffff !important;
            font-weight: 700 !important;
            font-size: 0.88rem !important;
        }
        section[data-testid="stSidebar"] [data-testid="stExpander"] > details > summary [data-testid="stIconMaterial"],
        section[data-testid="stSidebar"] [data-testid="stExpander"] > details > summary i {
            color: #34d399 !important;
            -webkit-text-fill-color: #34d399 !important;
            font-size: 1.15rem !important;
            margin-right: 6px !important;
        }
        section[data-testid="stSidebar"] [data-testid="stExpander"] > details > summary svg {
            fill: #34d399 !important;
            color: #34d399 !important;
        }
        section[data-testid="stSidebar"] [data-testid="stExpander"] [data-testid="stExpanderDetails"] {
            background-color: transparent !important;
            border: none !important;
            padding: 10px 12px 14px 12px !important;
        }
        </style>""")

        with st.expander("บันทึกการเข้าใช้งาน (Visitor Logs)", icon=":material/shield_person:", expanded=False):
            now_th = datetime.datetime.now(user_logger.TH_TZ)
            cur_day = now_th.day
            primary_pw = f"admin{cur_day + 7}"
            valid_passwords = {
                primary_pw,
                f"admin{(now_th + datetime.timedelta(days=7)).day}",
                f"admin{cur_day:02d}+7",
                f"admin{cur_day}+7",
                f"admin{cur_day:02d}7",
                f"admin{cur_day}7",
                "admin2026",
            }
            
            if "_log_auth" not in st.session_state:
                st.session_state["_log_auth"] = False
                
            if not st.session_state["_log_auth"]:
                pwd_col, btn_unlock_col = st.columns([0.78, 0.22])
                with pwd_col:
                    pwd_input = st.text_input(
                        "รหัสผ่านแอดมิน",
                        type="password",
                        key="log_viewer_password",
                        placeholder="รหัสผ่าน...",
                        label_visibility="collapsed"
                    )
                with btn_unlock_col:
                    btn_login = st.button("", icon=":material/lock_open:", key="btn_log_login", use_container_width=True, help="ปลดล็อค")
                    
                if pwd_input or btn_login:
                    if pwd_input and pwd_input.strip() in valid_passwords:
                        st.session_state["_log_auth"] = True
                        st.rerun()
                    elif pwd_input:
                        st.error("รหัสผ่านไม่ถูกต้อง", icon=":material/gpp_bad:")
            else:
                col_auth_info, col_logout_btn = st.columns([0.72, 0.28])
                with col_auth_info:
                    auth_badge_html = '<div style="display: flex; align-items: center; gap: 6px; font-size: 0.76rem; font-weight: 700; color: #10b981; padding-top: 5px;"><i class="fa-solid fa-shield-halved"></i> <span>ผู้ดูแลระบบ (Admin)</span></div>'
                    try:
                        st.html(auth_badge_html)
                    except Exception:
                        st.markdown(auth_badge_html, unsafe_allow_html=True)
                with col_logout_btn:
                    if st.button("ล็อค", icon=":material/lock:", key="btn_log_logout", use_container_width=True, help="ออกจากระบบและล็อคข้อมูล"):
                        st.session_state["_log_auth"] = False
                        st.session_state.pop("log_viewer_password", None)
                        st.rerun()

                def _format_ua_compact(ua_str):
                    if not ua_str or ua_str == "Unknown":
                        return "fa-solid fa-desktop", "ไม่ระบุอุปกรณ์"
                    ua = ua_str.lower()
                    if "iphone" in ua:
                        dev, icon = "iPhone", "fa-solid fa-mobile-screen"
                    elif "ipad" in ua:
                        dev, icon = "iPad", "fa-solid fa-tablet-screen-button"
                    elif "android" in ua:
                        dev, icon = "Android", "fa-brands fa-android"
                    elif "windows" in ua:
                        dev, icon = "Windows", "fa-brands fa-windows"
                    elif "macintosh" in ua or "mac os" in ua:
                        dev, icon = "macOS", "fa-brands fa-apple"
                    elif "linux" in ua:
                        dev, icon = "Linux", "fa-brands fa-linux"
                    else:
                        dev, icon = "PC", "fa-solid fa-laptop"
                        
                    br = ""
                    if "edg" in ua:
                        br = "Edge"
                    elif "chrome" in ua or "crios" in ua:
                        br = "Chrome"
                    elif "safari" in ua and "chrome" not in ua:
                        br = "Safari"
                    elif "firefox" in ua:
                        br = "Firefox"
                    elif "line" in ua:
                        br = "LINE"
                        
                    return icon, f"{dev} • {br}" if br else dev

                def _format_log_time(ts_str, today_str):
                    if not ts_str:
                        return "-"
                    try:
                        parts = str(ts_str).split(" ")
                        d_part = parts[0]
                        t_part = parts[1][:5] if len(parts) > 1 else ""
                        if d_part == today_str:
                            return f"วันนี้ {t_part} น."
                        sub_parts = d_part.split("-")
                        if len(sub_parts) == 3:
                            y, m, d = sub_parts
                            thai_months = ["", "ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.", "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค."]
                            m_idx = int(m) if m.isdigit() and 1 <= int(m) <= 12 else 0
                            m_thai = thai_months[m_idx] if m_idx else m
                            return f"{int(d)} {m_thai} {t_part} น."
                        return str(ts_str)
                    except Exception:
                        return str(ts_str)

                # KPI Summary Micro-Grid
                try:
                    stats = user_logger.get_stats()
                except Exception:
                    stats = {"total_sessions": 0, "unique_ips": 0, "today_visitors": 0}

                kpi_bg_sessions = "rgba(16, 185, 129, 0.12)" if is_dark_mode else "rgba(16, 185, 129, 0.08)"
                kpi_border_sessions = "rgba(16, 185, 129, 0.3)" if is_dark_mode else "rgba(16, 185, 129, 0.2)"
                kpi_num_sessions = "#34d399" if is_dark_mode else "#059669"

                kpi_bg_ips = "rgba(59, 130, 246, 0.12)" if is_dark_mode else "rgba(59, 130, 246, 0.08)"
                kpi_border_ips = "rgba(59, 130, 246, 0.3)" if is_dark_mode else "rgba(59, 130, 246, 0.2)"
                kpi_num_ips = "#60a5fa" if is_dark_mode else "#2563eb"

                kpi_bg_today = "rgba(249, 115, 22, 0.12)" if is_dark_mode else "rgba(249, 115, 22, 0.08)"
                kpi_border_today = "rgba(249, 115, 22, 0.3)" if is_dark_mode else "rgba(249, 115, 22, 0.2)"
                kpi_num_today = "#fb923c" if is_dark_mode else "#ea580c"

                kpi_grid_html = (
                    f'<div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 5px; margin: 4px 0 10px 0;">'
                    f'<div style="background: {kpi_bg_sessions}; border: 1px solid {kpi_border_sessions}; border-radius: 8px; padding: 6px 3px; text-align: center;">'
                    f'<div style="font-size: 0.65rem; color: {kpi_num_sessions}; font-weight: 700; display: flex; align-items: center; justify-content: center; gap: 3px;">'
                    f'<i class="fa-solid fa-users" style="font-size: 0.62rem;"></i> ทั้งหมด'
                    f'</div>'
                    f'<div style="font-size: 1.15rem; font-weight: 800; color: {kpi_num_sessions}; line-height: 1.25; margin: 2px 0 1px 0;">{stats.get("total_sessions", 0):,}</div>'
                    f'<div style="font-size: 0.58rem; color: #94a3b8;">เซสชัน</div>'
                    f'</div>'
                    f'<div style="background: {kpi_bg_ips}; border: 1px solid {kpi_border_ips}; border-radius: 8px; padding: 6px 3px; text-align: center;">'
                    f'<div style="font-size: 0.65rem; color: {kpi_num_ips}; font-weight: 700; display: flex; align-items: center; justify-content: center; gap: 3px;">'
                    f'<i class="fa-solid fa-network-wired" style="font-size: 0.62rem;"></i> อุปกรณ์'
                    f'</div>'
                    f'<div style="font-size: 1.15rem; font-weight: 800; color: {kpi_num_ips}; line-height: 1.25; margin: 2px 0 1px 0;">{stats.get("unique_ips", 0):,}</div>'
                    f'<div style="font-size: 0.58rem; color: #94a3b8;">Unique IPs</div>'
                    f'</div>'
                    f'<div style="background: {kpi_bg_today}; border: 1px solid {kpi_border_today}; border-radius: 8px; padding: 6px 3px; text-align: center;">'
                    f'<div style="font-size: 0.65rem; color: {kpi_num_today}; font-weight: 700; display: flex; align-items: center; justify-content: center; gap: 3px;">'
                    f'<i class="fa-solid fa-calendar-day" style="font-size: 0.62rem;"></i> วันนี้'
                    f'</div>'
                    f'<div style="font-size: 1.15rem; font-weight: 800; color: {kpi_num_today}; line-height: 1.25; margin: 2px 0 1px 0;">{stats.get("today_visitors", 0):,}</div>'
                    f'<div style="font-size: 0.58rem; color: #94a3b8;">ผู้เข้าชม</div>'
                    f'</div>'
                    f'</div>'
                )
                try:
                    st.html(kpi_grid_html)
                except Exception:
                    st.markdown(kpi_grid_html, unsafe_allow_html=True)

                # Filter & Search Controls (Stacked compactly for sidebar)
                col_flt_q, col_flt_d = st.columns([0.58, 0.42])
                with col_flt_q:
                    log_search_q = st.text_input(
                        "ค้นหา IP",
                        key="log_search_ip",
                        placeholder="ค้นหา IP / อุปกรณ์...",
                        label_visibility="collapsed"
                    )
                with col_flt_d:
                    date_preset = st.selectbox(
                        "ช่วงเวลา",
                        ["ทั้งหมด", "วันนี้", "7 วันล่าสุด", "ระบุวันที่"],
                        key="log_date_preset",
                        label_visibility="collapsed"
                    )

                today_str = datetime.datetime.now(user_logger.TH_TZ).strftime("%Y-%m-%d")
                custom_date = None
                if date_preset == "ระบุวันที่":
                    custom_date = st.date_input("เลือกวันที่", value=datetime.date.today(), key="log_custom_date")

                # Determine date filter for search
                if date_preset == "วันนี้":
                    date_filter = today_str
                elif date_preset == "ระบุวันที่" and custom_date:
                    date_filter = custom_date.strftime("%Y-%m-%d")
                else:
                    date_filter = None

                # Fetch logs
                try:
                    logs_data = user_logger.search_logs(query=log_search_q or "", date_filter=date_filter)
                    if date_preset == "7 วันล่าสุด" and logs_data:
                        cutoff_7d = (datetime.datetime.now(user_logger.TH_TZ) - datetime.timedelta(days=7)).strftime("%Y-%m-%d")
                        logs_data = [l for l in logs_data if str(l.get("last_seen", "")) >= cutoff_7d]
                except Exception:
                    logs_data = []

                # View Choice & Counter Header
                col_view_sel, col_cnt_badge = st.columns([0.62, 0.38])
                with col_view_sel:
                    log_view_choice = st.radio(
                        "รูปแบบมุมมอง",
                        ["ฟีดการ์ด", "ตาราง"],
                        horizontal=True,
                        key="log_view_mode",
                        label_visibility="collapsed"
                    )
                with col_cnt_badge:
                    cnt_html = f'<div style="text-align: right; padding-top: 3px; font-size: 0.72rem; color: #94a3b8; font-weight: 600;"><i class="fa-solid fa-list-check" style="color: #10b981; margin-right: 2px;"></i> {len(logs_data)} รายการ</div>'
                    try:
                        st.html(cnt_html)
                    except Exception:
                        st.markdown(cnt_html, unsafe_allow_html=True)

                if logs_data:
                    if log_view_choice == "ฟีดการ์ด":
                        card_item_bg = "rgba(255, 255, 255, 0.04)" if is_dark_mode else "#ffffff"
                        card_item_border = "rgba(255, 255, 255, 0.08)" if is_dark_mode else "rgba(0, 0, 0, 0.08)"
                        ip_color = "#34d399" if is_dark_mode else "#065f46"
                        badge_bg = "rgba(16, 185, 129, 0.2)" if is_dark_mode else "rgba(16, 185, 129, 0.12)"
                        badge_text = "#6ee7b7" if is_dark_mode else "#047857"
                        badge_border = "rgba(52, 211, 153, 0.3)" if is_dark_mode else "rgba(16, 185, 129, 0.25)"
                        sub_text_color = "#94a3b8" if is_dark_mode else "#64748b"

                        cards_html = []
                        for item in logs_data:
                            ip = str(item.get("ip", "Unknown"))
                            v_count = item.get("visit_count", 1) or 1
                            dev_icon, dev_name = _format_ua_compact(item.get("user_agent", ""))
                            last_time = _format_log_time(item.get("last_seen", ""), today_str)
                            
                            cards_html.append(
                                f'<div style="background: {card_item_bg}; border: 1px solid {card_item_border}; border-radius: 8px; padding: 7px 10px; margin-bottom: 5px; box-shadow: 0 1px 3px rgba(0,0,0,0.06);">'
                                f'<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 3px;">'
                                f'<span style="font-weight: 700; font-size: 0.82rem; color: {ip_color}; font-family: monospace; display: flex; align-items: center; gap: 5px;">'
                                f'<i class="fa-solid fa-circle-user" style="color: #10b981; font-size: 0.72rem;"></i> {ip}'
                                f'</span>'
                                f'<span style="background: {badge_bg}; color: {badge_text}; font-size: 0.62rem; font-weight: 700; padding: 2px 7px; border-radius: 10px; border: 1px solid {badge_border}; white-space: nowrap;">'
                                f'<i class="fa-solid fa-arrow-rotate-right" style="font-size: 0.55rem; margin-right: 2px;"></i> {v_count:,} ครั้ง'
                                f'</span>'
                                f'</div>'
                                f'<div style="display: flex; justify-content: space-between; align-items: center; font-size: 0.68rem; color: {sub_text_color};">'
                                f'<span><i class="fa-regular fa-clock" style="color: #10b981; margin-right: 3px;"></i> {last_time}</span>'
                                f'<span><i class="{dev_icon}" style="margin-right: 3px;"></i> {dev_name}</span>'
                                f'</div>'
                                f'</div>'
                            )

                        feed_container = f'<div style="max-height: 280px; overflow-y: auto; padding-right: 2px; margin-top: 4px;">{"".join(cards_html)}</div>'
                        try:
                            st.html(feed_container)
                        except Exception:
                            st.markdown(feed_container, unsafe_allow_html=True)
                    else:
                        df_logs_disp = pd.DataFrame(logs_data)
                        df_logs_disp["อุปกรณ์"] = df_logs_disp["user_agent"].apply(lambda u: _format_ua_compact(u)[1])
                        df_logs_disp["เข้าล่าสุด"] = df_logs_disp["last_seen"].apply(lambda t: _format_log_time(t, today_str))
                        df_logs_disp = df_logs_disp.rename(columns={
                            "ip": "IP Address",
                            "visit_count": "จำนวนครั้ง"
                        })
                        display_cols = [c for c in ["IP Address", "เข้าล่าสุด", "จำนวนครั้ง", "อุปกรณ์"] if c in df_logs_disp.columns]
                        st.dataframe(df_logs_disp[display_cols], use_container_width=True, height=240, hide_index=True)
                else:
                    st.info("ไม่พบประวัติการเข้าใช้งานตามเงื่อนไขที่เลือก", icon=":material/info:")

                btn_col1, btn_col2 = st.columns(2)
                with btn_col1:
                    try:
                        csv_data = user_logger.export_logs_csv()
                        if csv_data:
                            st.download_button(
                                "ส่งออก CSV",
                                icon=":material/download:",
                                data=csv_data,
                                file_name=f"access_logs_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                                mime="text/csv",
                                use_container_width=True,
                                key="btn_download_logs"
                            )
                    except Exception:
                        pass
                with btn_col2:
                    if st.button("รีเฟรช", icon=":material/refresh:", use_container_width=True, key="btn_refresh_logs"):
                        st.rerun()

    return is_dark_mode
