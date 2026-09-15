# -*- coding: utf-8 -*-
"""
data_completeness.py
Module for Data Completeness Audit & Scraper Health (ความครบถ้วนของข้อมูลและสถานะการดึงข้อมูล).
- Left side: Company Card Strip (ดึงได้ xx / หน้าเว็บ xx, วันที่ดึงข้อมูล, % สี)
- Right side: Field Completeness Heatmap cells (GPS, ราคา, อำเภอ, ตำบล, พื้นที่, ลิงก์, ประเภท, รหัส)
- Top Summary: Total Scraped/Web, Coverage %, Total GPS, Centroid GPS count, Total Companies
"""

import os
import re
import datetime
import textwrap
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

import streamlit as st
import pandas as pd
import numpy as np

# ==============================================================================
# CONSTANTS & BRAND STYLES
# ==============================================================================
COMPANY_COLORS = {
    "LED": "#0891b2",
    "SAM": "#10b981",
    "BAM": "#3b82f6",
    "Chayo555": "#f97316",
    "Chayo": "#f97316",
    "Chayo NPA": "#f97316",
    "GHB": "#ca8a04",
    "KBANK": "#059669",
    "KTB": "#0284c7",
    "SCB": "#7e22ce",
    "GSB": "#eb1985",
    "DDproperty": "#a855f7",
    "Livinginsider": "#14b8a6",
    "NaYoo": "#8b5cf6",
    "ZmyHome": "#ec4899",
    "Baania": "#f59e0b",
    "ไฟล์นำเข้า": "#64748b"
}

DEFAULT_COLOR = "#059669"

# Verified benchmark of total properties announced on official websites/portals
# SAM: เดิมกำหนดไว้ 5,500 จากการประมาณการพอร์ตโฟลิโอเบื้องต้น
# ล่าสุดอัปเดตเป็น 4,968 รายการ ตามจำนวนประกาศจริงบนหน้าเว็บ sam.or.th
WEB_ANNOUNCED_BENCHMARKS = {
    "LED": 105004,          # กรมบังคับคดี (e-Auction & Bidreg)
    "Livinginsider": 143664, # Livinginsider ค้นหาอสังหาฯ รวม
    "DDproperty": 114000,   # DDproperty รวมประกาศขาย
    "ZmyHome": 32515,       # ZmyHome ทรัพย์สินทั้งหมด
    "GHB": 31264,           # ธนาคารอาคารสงเคราะห์ (ธอส.)
    "BAM": 18614,           # บมจ.บริหารสินทรัพย์ กรุงเทพพาณิชย์
    "KBANK": 14774,         # ธนาคารกสิกรไทย ทรัพย์รอการขาย
    "Baania": 10000,        # Baania ทรัพย์ทั้งหมด (ElasticSearch Window)
    "NaYoo": 8136,          # ขอนแก่นน่าอยู่ / น่าอยู่ทั่วไทย
    "SAM": 4968,            # บมจ.บริหารสินทรัพย์สุขุมวิท (sam.or.th ล่าสุด 4,968 รายการ)
    "GSB": 4456,            # ธนาคารออมสิน ทรัพย์รอการขาย
    "SCB": 4108,            # ธนาคารไทยพาณิชย์ ทรัพย์รอการขาย
    "KTB": 2312,            # ธนาคารกรุงไทย NPA
    "Chayo555": 320,        # บมจ.ชโย กรุ๊ป NPA
    "Chayo": 320,
    "Chayo NPA": 320,
}

THAI_SHORT_MONTHS = ['ม.ค.', 'ก.พ.', 'มี.ค.', 'เม.ย.', 'พ.ค.', 'มิ.ย.', 'ก.ค.', 'ส.ค.', 'ก.ย.', 'ต.ค.', 'พ.ย.', 'ธ.ค.']


def render_html_block(html_content: str):
    """Renders HTML cleanly without markdown indentation issues."""
    clean_html = textwrap.dedent(html_content).strip()
    if hasattr(st, "html"):
        st.html(clean_html)
    else:
        st.markdown(clean_html, unsafe_allow_html=True)


def format_thai_date(dt: Any, include_time: bool = True) -> str:
    """Format datetime object into Thai Buddhist Era string with optional time."""
    if not dt or pd.isna(dt):
        return "ไม่ระบุวันที่"
    if not isinstance(dt, (datetime.datetime, datetime.date, pd.Timestamp)):
        try:
            dt = pd.to_datetime(dt)
        except Exception:
            return str(dt)
    thai_year = dt.year + 543 if dt.year < 2500 else dt.year
    month_name = THAI_SHORT_MONTHS[dt.month - 1]
    if include_time and hasattr(dt, 'strftime') and hasattr(dt, 'hour') and (dt.hour != 0 or dt.minute != 0):
        return f"{dt.day} {month_name} {thai_year} ({dt.strftime('%H:%M น.')})"
    return f"{dt.day} {month_name} {thai_year}"


def parse_date_safely(date_series: Any) -> pd.Series:
    """Parse dates in mixed formats cleanly and fast."""
    if date_series is None:
        return pd.Series(dtype='datetime64[ns]')
    if isinstance(date_series, (list, np.ndarray, set)):
        clean_series = pd.Series(list(date_series)).dropna().astype(str).str.strip()
    else:
        clean_series = pd.Series(date_series.dropna().unique()).astype(str).str.strip()
    clean_series = clean_series[~clean_series.isin(['', 'nan', 'None', '-', 'NaT'])]
    if clean_series.empty:
        return pd.Series(dtype='datetime64[ns]')

    try:
        is_iso = clean_series.str.match(r'^\d{4}[-/]\d{1,2}[-/]\d{1,2}')
        res = pd.Series(index=clean_series.index, dtype='datetime64[ns]')
        if is_iso.any():
            res.loc[is_iso] = pd.to_datetime(clean_series[is_iso], format='mixed', dayfirst=False, errors='coerce')
        if (~is_iso).any():
            res.loc[~is_iso] = pd.to_datetime(clean_series[~is_iso], format='mixed', dayfirst=True, errors='coerce')
        return res.dropna()
    except Exception:
        try:
            return pd.to_datetime(clean_series, format='mixed', errors='coerce').dropna()
        except Exception:
            return pd.Series(dtype='datetime64[ns]')


def get_heat_style(pct: float, is_dark_mode: bool = False) -> Tuple[str, str]:
    """Returns (background_color, text_color) for a heatmap cell based on fill rate."""
    if pct >= 95.0:
        return "#059669", "#ffffff"  # เขียวเข้ม
    elif pct >= 80.0:
        return "#10b981", "#ffffff"  # เขียวสด
    elif pct >= 60.0:
        return "#eab308", "#0f172a" if not is_dark_mode else "#ffffff"  # เหลือง
    elif pct >= 35.0:
        return "#f97316", "#ffffff"  # ส้ม
    elif pct > 0.0:
        return "#ef4444", "#ffffff"  # แดง
    else:
        bg = "rgba(239, 68, 68, 0.15)" if not is_dark_mode else "rgba(239, 68, 68, 0.25)"
        return bg, "#ef4444"  # แดงจาง (0%)


# ==============================================================================
# COMPUTATION ENGINE: DATA COMPLETENESS & SCRAPER HEALTH
# ==============================================================================
@st.cache_data(ttl=1800, show_spinner=False)
def compute_data_completeness_table(_df: Optional[pd.DataFrame], base_csv_dir: str = "CSV_Output") -> pd.DataFrame:
    """
    Computes data counts, scraper yield, completeness matrix,
    and extraction dates per company. Clean, vectorized, and highly efficient.
    """
    if _df is None or _df.empty or 'บริษัท' not in _df.columns:
        return pd.DataFrame()

    # Find physical file mtime as fallback
    csv_path = Path(base_csv_dir)
    csv_files_map = {}
    if csv_path.exists() and csv_path.is_dir():
        for f in csv_path.rglob("*.csv"):
            f_name_lower = f.name.lower()
            if "all_assets" in f_name_lower or "backup" in f_name_lower:
                continue
            mtime = datetime.datetime.fromtimestamp(f.stat().st_mtime)
            for co in COMPANY_COLORS.keys():
                if co.lower() in f_name_lower:
                    if co not in csv_files_map or mtime > csv_files_map[co]:
                        csv_files_map[co] = mtime

    now = datetime.datetime.now()
    records = []
    excluded_companies = {'Taladnudbaan', 'ตลาดนัด', 'taladnudbaan', 'nan', 'None', ''}

    # Detect Columns
    has_date_col = 'วันที่ดึงข้อมูล' in _df.columns
    has_price_col = 'ราคา' in _df.columns or 'ราคาขาย (บาท)' in _df.columns
    price_col_name = 'ราคา' if 'ราคา' in _df.columns else ('ราคาขาย (บาท)' if 'ราคาขาย (บาท)' in _df.columns else None)
    has_subdist_col = 'ตำบล' in _df.columns
    has_dist_col = 'อำเภอ' in _df.columns
    has_prov_col = 'จังหวัด' in _df.columns
    has_lat_col = 'ละติจูด' in _df.columns
    has_lon_col = 'ลองจิจูด' in _df.columns
    has_link_col = 'ลิงก์' in _df.columns
    has_land_area = 'เนื้อที่ (ตร.ว.)' in _df.columns or 'เนื้อที่ (ไร่-งาน-ตร.ว.)' in _df.columns
    has_usable_area = 'พื้นที่ใช้สอย (ตร.ม.)' in _df.columns
    has_ptype_col = 'ประเภททรัพย์' in _df.columns
    has_code_col = 'รหัสทรัพย์' in _df.columns or 'ID' in _df.columns
    code_col_name = 'รหัสทรัพย์' if 'รหัสทรัพย์' in _df.columns else ('ID' if 'ID' in _df.columns else None)

    for comp, group in _df.groupby('บริษัท'):
        comp_str = str(comp).strip()
        if not comp_str or comp_str in excluded_companies:
            continue

        count = len(group)
        if count == 0:
            continue

        # 1. Extraction Date (วันดึงข้อมูล)
        latest_dt = None
        earliest_dt = None
        days_ago = None
        date_span_str = "ไม่ระบุวันที่"

        if has_date_col:
            dts = parse_date_safely(group['วันที่ดึงข้อมูล'])
            if not dts.empty:
                latest_dt = dts.max()
                earliest_dt = dts.min()
                days_ago = (now - latest_dt).days
                if earliest_dt.date() == latest_dt.date():
                    date_span_str = format_thai_date(latest_dt, include_time=True)
                else:
                    date_span_str = f"{format_thai_date(earliest_dt, include_time=False)} - {format_thai_date(latest_dt, include_time=False)}"

        # Fallback to file mtime if no column date
        if latest_dt is None and comp_str in csv_files_map:
            latest_dt = csv_files_map[comp_str]
            days_ago = (now - latest_dt).days
            date_span_str = format_thai_date(latest_dt, include_time=True)

        # 2. Key completeness factors for Heatmap
        gps_pct = 0.0
        if has_lat_col and has_lon_col:
            lat = pd.to_numeric(group['ละติจูด'], errors='coerce')
            lon = pd.to_numeric(group['ลองจิจูด'], errors='coerce')
            gps_valid = lat.notna() & lon.notna() & (lat != 0) & (lon != 0)
            gps_pct = round((gps_valid.sum() / count) * 100, 1)

        price_pct = 0.0
        if price_col_name:
            p_val = pd.to_numeric(group[price_col_name].astype(str).str.replace(',', ''), errors='coerce')
            price_valid = p_val.notna() & (p_val > 0)
            price_pct = round((price_valid.sum() / count) * 100, 1)

        loc_pct = 0.0
        if has_prov_col and has_dist_col:
            prov_clean = group['จังหวัด'].fillna('').astype(str).str.strip()
            dist_clean = group['อำเภอ'].fillna('').astype(str).str.strip()
            loc_valid = ~prov_clean.isin(['', '-', 'ไม่ระบุ', 'nan', 'None']) & ~dist_clean.isin(['', '-', 'ไม่ระบุ', 'nan', 'None'])
            loc_pct = round((loc_valid.sum() / count) * 100, 1)

        subdist_pct = 0.0
        if has_subdist_col:
            subdist_clean = group['ตำบล'].fillna('').astype(str).str.strip()
            subdist_valid = ~subdist_clean.isin(['', '-', 'ไม่ระบุ', 'nan', 'None'])
            subdist_pct = round((subdist_valid.sum() / count) * 100, 1)

        area_pct = 0.0
        area_valid = pd.Series(False, index=group.index)
        if has_land_area:
            land_col = 'เนื้อที่ (ตร.ว.)' if 'เนื้อที่ (ตร.ว.)' in group.columns else 'เนื้อที่ (ไร่-งาน-ตร.ว.)'
            l_val = pd.to_numeric(group[land_col].astype(str).str.replace(',', ''), errors='coerce')
            area_valid = area_valid | (l_val.notna() & (l_val > 0))
        if has_usable_area:
            u_val = pd.to_numeric(group['พื้นที่ใช้สอย (ตร.ม.)'].astype(str).str.replace(',', ''), errors='coerce')
            area_valid = area_valid | (u_val.notna() & (u_val > 0))
        area_pct = round((area_valid.sum() / count) * 100, 1)

        link_pct = 0.0
        if has_link_col:
            links = group['ลิงก์'].fillna('').astype(str).str.strip()
            link_valid = links.str.startswith('http')
            link_pct = round((link_valid.sum() / count) * 100, 1)

        ptype_pct = 0.0
        if has_ptype_col:
            pt_clean = group['ประเภททรัพย์'].fillna('').astype(str).str.strip()
            pt_valid = ~pt_clean.isin(['', '-', 'ไม่ระบุ', 'nan', 'None'])
            ptype_pct = round((pt_valid.sum() / count) * 100, 1)

        code_pct = 0.0
        if code_col_name:
            c_clean = group[code_col_name].fillna('').astype(str).str.strip()
            c_valid = ~c_clean.isin(['', '-', 'ไม่ระบุ', 'nan', 'None'])
            code_pct = round((c_valid.sum() / count) * 100, 1)

        # 3. Web Announced Benchmark & Scrape Yield (ดึงข้อมูลได้ vs ประกาศหน้าเว็บ)
        web_announced = WEB_ANNOUNCED_BENCHMARKS.get(comp_str, count)
        if count > web_announced:
            web_announced = count
        yield_pct = round((count / web_announced) * 100, 1) if web_announced > 0 else 100.0
        yield_pct = min(100.0, yield_pct)

        records.append({
            "บริษัท": comp_str,
            "วันที่ดึงข้อมูลล่าสุด": date_span_str,
            "จำนวนที่ดึงได้ (รายการ)": count,
            "ประกาศหน้าเว็บ (รายการ)": web_announced,
            "ดึงได้ / หน้าเว็บ": f"{count:,} / {web_announced:,}",
            "สัดส่วนการดึงข้อมูล (%)": yield_pct,
            "มีพิกัด GPS (%)": gps_pct,
            "มีราคาขาย (%)": price_pct,
            "มีอำเภอ/จังหวัด (%)": loc_pct,
            "มีตำบล (%)": subdist_pct,
            "มีขนาดพื้นที่ (%)": area_pct,
            "มีลิงก์ (%)": link_pct,
            "มีประเภททรัพย์ (%)": ptype_pct,
            "มีรหัสทรัพย์ (%)": code_pct,
            "_latest_dt": latest_dt,
            "_days_ago": days_ago if days_ago is not None else 999
        })

    result_df = pd.DataFrame(records)
    if not result_df.empty:
        result_df = result_df.sort_values(by="จำนวนที่ดึงได้ (รายการ)", ascending=False).reset_index(drop=True)

    return result_df


# ==============================================================================
# MAIN RENDER FUNCTION FOR TAB 5 (CARD + DIRECT HEATMAP MATRIX)
# ==============================================================================
def render_data_completeness(
    df_raw: Optional[pd.DataFrame],
    is_dark_mode: bool = False,
    plotly_template: str = "plotly_white",
    style_plotly_fig=None
):
    """
    Renders clean, compact company cards paired directly with a matching heatmap matrix row-by-row:
    - Left side: Company Card Strip (ดึงได้ xx / หน้าเว็บ xx, วันที่ดึงข้อมูล, % สี)
    - Right side: Field Completeness Heatmap cells (GPS, ราคา, อำเภอ, ตำบล, พื้นที่, ลิงก์, ประเภท, รหัส)
    - Top Summary: Total Scraped vs Web, Overall Coverage %, Total with GPS, Centroid GPS count
    """
    if df_raw is None or df_raw.empty:
        st.info("ไม่พบข้อมูลทรัพย์สินในระบบ กรุณาตรวจสอบไฟล์ all_assets.parquet หรือ CSV_Output")
        return

    # 1. Compute Data Completeness Table
    completeness_df = compute_data_completeness_table(df_raw, "CSV_Output")

    if completeness_df.empty:
        st.warning("ไม่สามารถวิเคราะห์ความครบถ้วนของข้อมูลได้")
        return

    # 2. Key Summary Numbers
    total_scraped = int(completeness_df["จำนวนที่ดึงได้ (รายการ)"].sum())
    total_web = int(completeness_df["ประกาศหน้าเว็บ (รายการ)"].sum())
    overall_yield = round((total_scraped / total_web) * 100, 1) if total_web > 0 else 100.0
    total_comps = len(completeness_df)

    # 3. Compute Coordinates & Centroids Totals
    total_with_gps = 0
    total_centroid = 0
    total_real_gps = 0

    if 'ละติจูด' in df_raw.columns and 'ลองจิจูด' in df_raw.columns:
        lat = pd.to_numeric(df_raw['ละติจูด'], errors='coerce')
        lon = pd.to_numeric(df_raw['ลองจิจูด'], errors='coerce')
        gps_mask = lat.notna() & lon.notna() & (lat != 0) & (lon != 0)
        total_with_gps = int(gps_mask.sum())

        # Centroid detection (LED is always subdistrict centroid; others check is_centroid column)
        is_c_col = df_raw['is_centroid'] if 'is_centroid' in df_raw.columns else pd.Series(False, index=df_raw.index)
        comp_col = df_raw['บริษัท'].astype(str).str.strip().str.upper() if 'บริษัท' in df_raw.columns else pd.Series('', index=df_raw.index)

        is_c_bool = (
            (comp_col == 'LED') |
            is_c_col.astype(str).str.strip().str.lower().isin(['true', '1', 'yes', 't']) |
            (is_c_col == True)
        )
        centroid_mask = gps_mask & is_c_bool
        total_centroid = int(centroid_mask.sum())
        total_real_gps = max(0, total_with_gps - total_centroid)

    pct_gps_total = round((total_with_gps / total_scraped) * 100, 1) if total_scraped > 0 else 0.0
    pct_centroid = round((total_centroid / total_with_gps) * 100, 1) if total_with_gps > 0 else 0.0

    # CSS Theme Variables
    card_bg = "#1e293b" if is_dark_mode else "#ffffff"
    card_border = "#334155" if is_dark_mode else "#e2e8f0"
    text_color = "#f8fafc" if is_dark_mode else "#0f172a"
    sub_color = "#94a3b8" if is_dark_mode else "#64748b"

    # Color for overall yield
    if overall_yield >= 95:
        overall_color = "#10b981"
    elif overall_yield >= 75:
        overall_color = "#f59e0b"
    else:
        overall_color = "#ef4444"

    # Inject Card + Heatmap Grid Styles
    render_html_block(f"""
<style>
.comp-audit-summary-bar {{
    background: {card_bg};
    border: 1px solid {card_border};
    border-radius: 10px;
    padding: 12px 18px;
    margin-bottom: 12px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 14px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.03);
}}
.company-row-wrap {{
    background: {card_bg};
    border: 1px solid {card_border};
    border-radius: 8px;
    padding: 8px 14px;
    margin-bottom: 6px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 14px;
    transition: all 0.15s ease-in-out;
}}
.company-row-wrap:hover {{
    border-color: #0284c7;
    box-shadow: 0 3px 8px rgba(0,0,0,0.05);
}}
.card-left-section {{
    flex: 0 0 360px;
    display: flex;
    flex-direction: column;
    gap: 2px;
}}
.card-title-row {{
    display: flex;
    justify-content: space-between;
    align-items: center;
}}
.company-brand {{
    display: flex;
    align-items: center;
    gap: 8px;
}}
.brand-bar {{
    width: 4px;
    height: 16px;
    border-radius: 2px;
    display: inline-block;
}}
.company-name {{
    font-size: 0.98rem;
    font-weight: 800;
    color: {text_color};
}}
.yield-badge {{
    font-size: 1.05rem;
    font-weight: 800;
    letter-spacing: -0.2px;
}}
.card-scraped-row {{
    font-size: 0.8rem;
    color: {sub_color};
}}
.card-scraped-row b {{
    color: {text_color};
}}
.card-date-row {{
    font-size: 0.72rem;
    color: {sub_color};
    display: flex;
    align-items: center;
    gap: 5px;
}}
.heatmap-right-section {{
    flex: 1;
    display: grid;
    grid-template-columns: repeat(8, 1fr);
    gap: 6px;
    align-items: center;
}}
.heat-cell {{
    height: 34px;
    border-radius: 5px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.8rem;
    font-weight: 700;
    cursor: default;
    transition: transform 0.1s ease;
}}
.heat-cell:hover {{
    transform: scale(1.06);
}}
.grid-header-row {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 6px 14px;
    margin-bottom: 4px;
    font-size: 0.75rem;
    font-weight: 700;
    color: {sub_color};
    text-transform: uppercase;
    letter-spacing: 0.3px;
}}
.header-left-title {{
    flex: 0 0 360px;
}}
.header-right-heatmaps {{
    flex: 1;
    display: grid;
    grid-template-columns: repeat(8, 1fr);
    gap: 6px;
    text-align: center;
}}
.heat-header-col {{
    text-align: center;
    font-size: 0.74rem;
}}
</style>
""")

    # 4. Top Summary Banner (With Total Scraped, GPS total & Centroid count)
    render_html_block(f"""
<div class="comp-audit-summary-bar">
    <div style="display: flex; align-items: center; gap: 12px;">
        <div style="font-size: 1.25rem; color: #0284c7;"><i class="fa-solid fa-server"></i></div>
        <div>
            <div style="font-size: 0.72rem; font-weight: 700; color: {sub_color}; text-transform: uppercase;">สรุปข้อมูลภาพรวม</div>
            <div style="font-size: 1.12rem; font-weight: 800; color: {text_color};">
                ดึงข้อมูลได้ <span style="color:#0284c7;">{total_scraped:,}</span> / ประกาศหน้าเว็บ <span style="color:{sub_color};">{total_web:,}</span> รายการ
            </div>
        </div>
    </div>
    <div style="display: flex; align-items: center; gap: 14px; flex-wrap: wrap;">
        <div style="text-align: right;">
            <div style="font-size: 0.7rem; color: {sub_color};">ความครอบคลุม</div>
            <div style="font-size: 1.1rem; font-weight: 800; color: {overall_color};">{overall_yield:.1f}%</div>
        </div>
        <div style="height: 22px; width: 1px; background: {card_border};"></div>
        <div style="text-align: right;">
            <div style="font-size: 0.7rem; color: {sub_color};"><i class="fa-solid fa-location-dot" style="color:#059669; margin-right:3px;"></i>มีพิกัดทั้งหมด</div>
            <div style="font-size: 1.05rem; font-weight: 800; color: #059669;">{total_with_gps:,} <span style="font-size:0.75rem; font-weight:600; color:{sub_color};">({pct_gps_total}%)</span></div>
        </div>
        <div style="height: 22px; width: 1px; background: {card_border};"></div>
        <div style="text-align: right;">
            <div style="font-size: 0.7rem; color: {sub_color};"><i class="fa-solid fa-triangle-exclamation" style="color:#b45309; margin-right:3px;"></i>พิกัดกึ่งกลาง</div>
            <div style="font-size: 1.05rem; font-weight: 800; color: #b45309;">{total_centroid:,} <span style="font-size:0.75rem; font-weight:600; color:{sub_color};">({pct_centroid}%)</span></div>
        </div>
        <div style="height: 22px; width: 1px; background: {card_border};"></div>
        <div style="text-align: right;">
            <div style="font-size: 0.7rem; color: {sub_color};">บริษัททั้งหมด</div>
            <div style="font-size: 1.05rem; font-weight: 800; color: {text_color};">{total_comps} แห่ง</div>
        </div>
    </div>
</div>
""")

    # 5. Search and Sort Filter Controls
    ctrl_col1, ctrl_col2 = st.columns([1.6, 1])
    with ctrl_col1:
        search_kw = st.text_input(
            "ค้นหาบริษัท:",
            placeholder="ค้นหาชื่อบริษัท เช่น LED, BAM, SAM, GHB...",
            label_visibility="collapsed"
        ).strip().lower()
    with ctrl_col2:
        sort_by = st.selectbox(
            "เรียงลำดับ:",
            options=[
                "จำนวนทรัพย์ (มาก ➔ น้อย)",
                "อัตราดึงสำเร็จ (Yield %)",
                "วันที่ดึงข้อมูลล่าสุด",
                "ชื่อบริษัท (A-Z)"
            ],
            index=0,
            label_visibility="collapsed"
        )

    # Filter & Sort Data
    display_df = completeness_df.copy()
    if search_kw:
        display_df = display_df[display_df["บริษัท"].str.lower().str.contains(search_kw)]

    if sort_by == "อัตราดึงสำเร็จ (Yield %)":
        display_df = display_df.sort_values(by="สัดส่วนการดึงข้อมูล (%)", ascending=False)
    elif sort_by == "วันที่ดึงข้อมูลล่าสุด":
        display_df = display_df.sort_values(by="_days_ago", ascending=True)
    elif sort_by == "ชื่อบริษัท (A-Z)":
        display_df = display_df.sort_values(by="บริษัท", ascending=True)
    else:
        display_df = display_df.sort_values(by="จำนวนที่ดึงได้ (รายการ)", ascending=False)

    if display_df.empty:
        st.warning("ไม่พบบริษัทที่ตรงกับคำค้นหา")
        return

    # 6. Header Row (Alined perfectly with cards and heatmap columns)
    render_html_block(f"""
<div class="grid-header-row">
    <div class="header-left-title">การ์ดข้อมูลบริษัท (ดึงได้ / ประกาศหน้าเว็บ)</div>
    <div class="header-right-heatmaps">
        <div class="heat-header-col"><i class="fa-solid fa-location-dot" style="margin-right:3px;"></i>GPS</div>
        <div class="heat-header-col"><i class="fa-solid fa-tag" style="margin-right:3px;"></i>ราคา</div>
        <div class="heat-header-col"><i class="fa-solid fa-city" style="margin-right:3px;"></i>อำเภอ</div>
        <div class="heat-header-col"><i class="fa-solid fa-map-pin" style="margin-right:3px;"></i>ตำบล</div>
        <div class="heat-header-col"><i class="fa-solid fa-ruler-combined" style="margin-right:3px;"></i>พื้นที่</div>
        <div class="heat-header-col"><i class="fa-solid fa-arrow-up-right-from-square" style="margin-right:3px;"></i>ลิงก์</div>
        <div class="heat-header-col"><i class="fa-solid fa-house-chimney" style="margin-right:3px;"></i>ประเภท</div>
        <div class="heat-header-col"><i class="fa-solid fa-hashtag" style="margin-right:3px;"></i>รหัส</div>
    </div>
</div>
""")

    # 7. Render Synchronized Rows (Company Card on Left, Heatmap Cells on Right)
    for _, row in display_df.reset_index(drop=True).iterrows():
        comp_name = row["บริษัท"]
        brand_color = COMPANY_COLORS.get(comp_name, DEFAULT_COLOR)
        scraped_val = row["จำนวนที่ดึงได้ (รายการ)"]
        web_val = row["ประกาศหน้าเว็บ (รายการ)"]
        yield_pct = row["สัดส่วนการดึงข้อมูล (%)"]
        date_str = row["วันที่ดึงข้อมูลล่าสุด"]

        # Color token according to yield percentage
        if yield_pct >= 95:
            pct_color = "#10b981"  # เขียว
        elif yield_pct >= 75:
            pct_color = "#f59e0b"  # ส้ม/เหลือง
        else:
            pct_color = "#ef4444"  # แดง

        # Field completeness percentages
        gps_pct = row["มีพิกัด GPS (%)"]
        price_pct = row["มีราคาขาย (%)"]
        loc_pct = row["มีอำเภอ/จังหวัด (%)"]
        subdist_pct = row["มีตำบล (%)"]
        area_pct = row["มีขนาดพื้นที่ (%)"]
        link_pct = row["มีลิงก์ (%)"]
        ptype_pct = row["มีประเภททรัพย์ (%)"]
        code_pct = row["มีรหัสทรัพย์ (%)"]

        # Cell styles
        c_gps_bg, c_gps_tx = get_heat_style(gps_pct, is_dark_mode)
        c_price_bg, c_price_tx = get_heat_style(price_pct, is_dark_mode)
        c_loc_bg, c_loc_tx = get_heat_style(loc_pct, is_dark_mode)
        c_subdist_bg, c_subdist_tx = get_heat_style(subdist_pct, is_dark_mode)
        c_area_bg, c_area_tx = get_heat_style(area_pct, is_dark_mode)
        c_link_bg, c_link_tx = get_heat_style(link_pct, is_dark_mode)
        c_ptype_bg, c_ptype_tx = get_heat_style(ptype_pct, is_dark_mode)
        c_code_bg, c_code_tx = get_heat_style(code_pct, is_dark_mode)

        render_html_block(f"""
<div class="company-row-wrap">
    <div class="card-left-section">
        <div class="card-title-row">
            <div class="company-brand">
                <span class="brand-bar" style="background-color: {brand_color};"></span>
                <span class="company-name">{comp_name}</span>
            </div>
            <span class="yield-badge" style="color: {pct_color};">{yield_pct:.1f}%</span>
        </div>
        <div class="card-scraped-row">
            <span>ดึงได้ <b>{scraped_val:,}</b> / หน้าเว็บ <b>{web_val:,}</b> รายการ</span>
        </div>
        <div class="card-date-row">
            <i class="fa-regular fa-clock" style="color: #0284c7; font-size: 0.72rem;"></i>
            <span>{date_str}</span>
        </div>
    </div>

    <div class="heatmap-right-section">
        <div class="heat-cell" style="background-color: {c_gps_bg}; color: {c_gps_tx};" title="{comp_name} - มีพิกัด GPS: {gps_pct:.1f}%">
            {gps_pct:.0f}%
        </div>
        <div class="heat-cell" style="background-color: {c_price_bg}; color: {c_price_tx};" title="{comp_name} - มีราคาขาย: {price_pct:.1f}%">
            {price_pct:.0f}%
        </div>
        <div class="heat-cell" style="background-color: {c_loc_bg}; color: {c_loc_tx};" title="{comp_name} - มีอำเภอ/จว: {loc_pct:.1f}%">
            {loc_pct:.0f}%
        </div>
        <div class="heat-cell" style="background-color: {c_subdist_bg}; color: {c_subdist_tx};" title="{comp_name} - มีตำบล: {subdist_pct:.1f}%">
            {subdist_pct:.0f}%
        </div>
        <div class="heat-cell" style="background-color: {c_area_bg}; color: {c_area_tx};" title="{comp_name} - มีขนาดพื้นที่: {area_pct:.1f}%">
            {area_pct:.0f}%
        </div>
        <div class="heat-cell" style="background-color: {c_link_bg}; color: {c_link_tx};" title="{comp_name} - มีลิงก์: {link_pct:.1f}%">
            {link_pct:.0f}%
        </div>
        <div class="heat-cell" style="background-color: {c_ptype_bg}; color: {c_ptype_tx};" title="{comp_name} - มีประเภททรัพย์: {ptype_pct:.1f}%">
            {ptype_pct:.0f}%
        </div>
        <div class="heat-cell" style="background-color: {c_code_bg}; color: {c_code_tx};" title="{comp_name} - มีรหัสทรัพย์: {code_pct:.1f}%">
            {code_pct:.0f}%
        </div>
    </div>
</div>
""")


# Alias for backward compatibility
render_monthly_comparison = render_data_completeness
