# -*- coding: utf-8 -*-
"""
monthly_comparison.py
Module for Monthly & Snapshot Comparison, Scraper Health Audit, and Inflow/Outflow Tracking.
Designed for All Asset NPA Dashboard.
"""

import os
import io
import re
import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

# ==============================================================================
# CONSTANTS & THEMES
# ==============================================================================
COMPANY_COLORS = {
    "LED": "#0891b2",
    "SAM": "#10b981",
    "BAM": "#3b82f6",
    "Chayo555": "#f97316",
    "Chayo": "#f97316",
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

DEFAULT_COLOR = "#94a3b8"

THAI_FULL_MONTHS = [
    'มกราคม', 'กุมภาพันธ์', 'มีนาคม', 'เมษายน', 'พฤษภาคม', 'มิถุนายน',
    'กรกฎาคม', 'สิงหาคม', 'กันยายน', 'ตุลาคม', 'พฤศจิกายน', 'ธันวาคม'
]
THAI_SHORT_MONTHS = ['ม.ค.', 'ก.พ.', 'มี.ค.', 'เม.ย.', 'พ.ค.', 'มิ.ย.', 'ก.ค.', 'ส.ค.', 'ก.ย.', 'ต.ค.', 'พ.ย.', 'ธ.ค.']

def format_thai_date(dt: datetime.datetime, include_time: bool = False) -> str:
    """Format datetime object into Thai Buddhist Era string."""
    if not dt or pd.isna(dt):
        return "-"
    thai_year = dt.year + 543 if dt.year < 2500 else dt.year
    month_name = THAI_SHORT_MONTHS[dt.month - 1]
    if include_time:
        return f"{dt.day} {month_name} {thai_year} ({dt.strftime('%H:%M น.')})"
    return f"{dt.day} {month_name} {thai_year}"

def parse_date_safely(date_series: pd.Series) -> pd.Series:
    """Parse dates in mixed formats cleanly (ISO YYYY-MM-DD vs Thai/Slash DD/MM/YYYY)."""
    clean_series = date_series.dropna().astype(str).str.strip()
    clean_series = clean_series[~clean_series.isin(['', 'nan', 'None', '-'])]
    if clean_series.empty:
        return pd.Series(dtype='datetime64[ns]')
    
    try:
        # Distinguish ISO YYYY-MM-DD from Slash DD/MM/YYYY to avoid swapping month and day
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

# ==============================================================================
# DATA DISCOVERY & SCRAPER HEALTH AUDIT
# ==============================================================================
@st.cache_data(ttl=600)
def scan_available_snapshots(base_csv_dir: str = "CSV_Output") -> List[Dict[str, Any]]:
    """
    Scans CSV_Output directory for monthly folders and snapshots.
    Returns list of dicts with label, folder_path, and snapshot_type.
    """
    snapshots = []
    base_path = Path(base_csv_dir)
    
    # Check default root Parquet file
    parquet_path = Path("all_assets.parquet")
    if parquet_path.exists():
        mtime = datetime.datetime.fromtimestamp(parquet_path.stat().st_mtime)
        snapshots.append({
            "id": "current_active_parquet",
            "label": f"ฐานข้อมูลปัจจุบัน (all_assets.parquet - {format_thai_date(mtime, True)})",
            "type": "parquet",
            "path": str(parquet_path),
            "mtime": mtime
        })
        
    if base_path.exists() and base_path.is_dir():
        # Scan subdirectories inside CSV_Output
        for sub_dir in sorted(base_path.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
            if sub_dir.is_dir():
                mtime = datetime.datetime.fromtimestamp(sub_dir.stat().st_mtime)
                name = sub_dir.name
                
                # Check if there is an all_assets_monthly_*.csv inside
                all_assets_csvs = list(sub_dir.glob("all_assets_monthly_*.csv"))
                if not all_assets_csvs:
                    all_assets_csvs = list(sub_dir.glob("*.csv"))
                    
                label_display = name
                # Clean up folder name into readable Thai text
                if " - Copy " in name:
                    parts = name.split(" - Copy ")
                    ym = parts[0]
                    raw_date = parts[1]
                    label_display = f"สำรองข้อมูล {ym} (Snapshot {raw_date})"
                elif re.match(r'^\d{4}_\d{1,2}_\d{1,2}$', name):
                    y, m, d = name.split('_')
                    try:
                        th_year = int(y) + 543 if int(y) < 2500 else int(y)
                        th_month = THAI_SHORT_MONTHS[int(m) - 1]
                        label_display = f"ชุดข้อมูลวันที่ {int(d)} {th_month} {th_year} ({name})"
                    except Exception:
                        label_display = f"ชุดข้อมูลวันที่ {name}"
                elif re.match(r'^\d{4}_\d{1,2}$', name):
                    y, m = name.split('_')
                    try:
                        th_year = int(y) + 543 if int(y) < 2500 else int(y)
                        th_month = THAI_FULL_MONTHS[int(m) - 1]
                        label_display = f"ชุดข้อมูลประจำเดือน {th_month} {th_year} ({name})"
                    except Exception:
                        label_display = f"ชุดข้อมูลประจำเดือน {name}"
                else:
                    label_display = f"โฟลเดอร์ {name}"
                    
                snapshots.append({
                    "id": f"folder_{sub_dir.name}",
                    "label": f"{label_display} (อัปเดต: {format_thai_date(mtime)})",
                    "type": "folder",
                    "path": str(sub_dir),
                    "mtime": mtime
                })
                
    return snapshots

def get_company_scraping_metadata(df: Optional[pd.DataFrame], csv_dir: str = "CSV_Output/2026_08") -> pd.DataFrame:
    """
    Extracts scraping audit details per company:
    - Latest extraction date (วันที่ดึงข้อมูลล่าสุด)
    - Date range (ช่วงวันที่ดึงข้อมูล: Min - Max)
    - Total asset count
    - Freshness status (🟢 สดใหม่ / 🟡 ปานกลาง / 🔴 ควรดึงใหม่)
    - Data completeness score (% GPS, % Price, % Area)
    - Corresponding CSV file name and size
    """
    records = []
    
    if df is None or df.empty or 'บริษัท' not in df.columns:
        return pd.DataFrame()
        
    # Also check physical CSV files in the folder
    csv_path = Path(csv_dir)
    csv_files_map = {}
    if csv_path.exists() and csv_path.is_dir():
        for f in csv_path.glob("*.csv"):
            f_name_lower = f.name.lower()
            size_mb = f.stat().st_size / (1024 * 1024)
            mtime = datetime.datetime.fromtimestamp(f.stat().st_mtime)
            for co in COMPANY_COLORS.keys():
                if co.lower() in f_name_lower and not f_name_lower.startswith("all_assets"):
                    csv_files_map[co] = {
                        "filename": f.name,
                        "size_mb": size_mb,
                        "mtime": mtime
                    }
                    
    now = datetime.datetime.now()
    
    for comp, group in df.groupby('บริษัท'):
        comp_str = str(comp).strip()
        if not comp_str or comp_str in ['nan', 'None', 'Taladnudbaan', 'ตลาดนัด']:
            continue
            
        count = len(group)
        
        # 1. Scrape dates
        latest_dt = None
        earliest_dt = None
        date_span_str = "-"
        days_ago = None
        
        if 'วันที่ดึงข้อมูล' in group.columns:
            dts = parse_date_safely(group['วันที่ดึงข้อมูล'])
            if not dts.empty:
                latest_dt = dts.max()
                earliest_dt = dts.min()
                days_ago = (now - latest_dt).days
                if earliest_dt.date() == latest_dt.date():
                    date_span_str = format_thai_date(latest_dt)
                else:
                    date_span_str = f"{format_thai_date(earliest_dt)} - {format_thai_date(latest_dt)}"
                    
        # Fallback to file mtime if no extraction date column is present
        file_info = csv_files_map.get(comp_str)
        if latest_dt is None and file_info:
            latest_dt = file_info["mtime"]
            days_ago = (now - latest_dt).days
            date_span_str = format_thai_date(latest_dt)
            
        # 2. Freshness Status badge
        if days_ago is not None:
            if days_ago <= 7:
                freshness_badge = "🟢 สดใหม่ล่าสุด"
                freshness_status = "Fresh"
            elif days_ago <= 15:
                freshness_badge = f"🟡 ปานกลาง ({days_ago} วันก่อน)"
                freshness_status = "Moderate"
            else:
                freshness_badge = f"🔴 ควรดึงใหม่ ({days_ago} วันก่อน)"
                freshness_status = "Stale"
        else:
            freshness_badge = "⚪ ไม่ระบุวันที่"
            freshness_status = "Unknown"
            
        # 3. Data Completeness Metrics
        # GPS coverage
        gps_count = group['ละติจูด'].notna() & group['ลองจิจูด'].notna() & (group['ละติจูด'] != 0) & (group['ลองจิจูด'] != 0)
        gps_pct = (gps_count.sum() / count * 100) if count > 0 else 0.0
        
        # Price coverage
        price_valid = group['ราคา'].notna() & (group['ราคา'] > 0)
        price_pct = (price_valid.sum() / count * 100) if count > 0 else 0.0
        
        # Area coverage (Land or Usable Area)
        has_land = group['เนื้อที่ (ตร.ว.)'].notna() if 'เนื้อที่ (ตร.ว.)' in group.columns else pd.Series(False, index=group.index)
        has_usable = group['พื้นที่ใช้สอย (ตร.ม.)'].notna() if 'พื้นที่ใช้สอย (ตร.ม.)' in group.columns else pd.Series(False, index=group.index)
        area_valid = has_land | has_usable
        area_pct = (area_valid.sum() / count * 100) if count > 0 else 0.0
        
        # Total portfolio value
        total_val_mb = (group.loc[price_valid, 'ราคา'].sum() / 1e6) if price_valid.any() else 0.0
        med_price = group.loc[price_valid, 'ราคา'].median() if price_valid.any() else 0.0
        
        records.append({
            "บริษัท": comp_str,
            "จำนวนทรัพย์ (รายการ)": count,
            "มูลค่ารวม (ล้านบาท)": round(total_val_mb, 1),
            "ราคากลาง (บาท)": round(med_price) if not np.isnan(med_price) else 0,
            "วันที่ดึงข้อมูลล่าสุด": format_thai_date(latest_dt) if latest_dt else "-",
            "ช่วงเวลาที่เก็บข้อมูล": date_span_str,
            "สถานะความสดใหม่": freshness_badge,
            "ความสมบูรณ์พิกัด GPS (%)": round(gps_pct, 1),
            "มีระบุราคา (%)": round(price_pct, 1),
            "มีระบุขนาดพื้นที่ (%)": round(area_pct, 1),
            "ไฟล์ต้นทาง": file_info["filename"] if file_info else "-",
            "ขนาดไฟล์": f"{file_info['size_mb']:.2f} MB" if file_info else "-",
            "_days_ago": days_ago if days_ago is not None else 999,
            "_latest_dt": latest_dt
        })
        
    audit_df = pd.DataFrame(records)
    if not audit_df.empty:
        # Sort by active asset count descending
        audit_df = audit_df.sort_values(by="จำนวนทรัพย์ (รายการ)", ascending=False).reset_index(drop=True)
    return audit_df

# ==============================================================================
# DATASET LOADER FOR HISTORICAL SNAPSHOTS
# ==============================================================================
@st.cache_data(ttl=600)
def load_snapshot_dataset(snapshot_item: Dict[str, Any]) -> Optional[pd.DataFrame]:
    """Load and normalize DataFrame from snapshot descriptor."""
    if not snapshot_item:
        return None
        
    stype = snapshot_item.get("type")
    spath = snapshot_item.get("path")
    
    EXCLUDED_COMPANIES = ['Taladnudbaan', 'ตลาดนัด', 'taladnudbaan']
    
    try:
        if stype == "parquet" and os.path.exists(spath):
            df = pd.read_parquet(spath)
            if 'บริษัท' in df.columns:
                df = df[~df['บริษัท'].isin(EXCLUDED_COMPANIES)].copy()
            return df
            
        elif stype == "folder" and os.path.exists(spath):
            folder_p = Path(spath)
            # Find master monthly csv
            master_csv = list(folder_p.glob("all_assets_monthly_*.csv"))
            if master_csv and master_csv[0].exists():
                df = pd.read_csv(master_csv[0], low_memory=False)
            else:
                # Concatenate all company csv files in folder
                all_csvs = list(folder_p.glob("*_NPA_*.csv"))
                if not all_csvs:
                    all_csvs = list(folder_p.glob("*.csv"))
                dfs = []
                for cf in all_csvs:
                    f_name_lower = cf.name.lower()
                    if "backup" in f_name_lower or "all_assets" in f_name_lower or "taladnud" in f_name_lower:
                        continue
                    try:
                        temp_df = pd.read_csv(cf, low_memory=False)
                        dfs.append(temp_df)
                    except Exception:
                        pass
                if dfs:
                    df = pd.concat(dfs, ignore_index=True)
                else:
                    return None
                    
            if 'บริษัท' in df.columns:
                df = df[~df['บริษัท'].isin(EXCLUDED_COMPANIES)].copy()
                
            # Clean numeric columns
            if 'ราคา' in df.columns:
                df['ราคา'] = pd.to_numeric(df['ราคา'].astype(str).str.replace(',', ''), errors='coerce')
            for c in ['ละติจูด', 'ลองจิจูด']:
                if c in df.columns:
                    df[c] = pd.to_numeric(df[c].astype(str).str.replace(',', ''), errors='coerce')
            return df
    except Exception as e:
        st.error(f"เกิดข้อผิดพลาดในการโหลด Snapshot: {e}")
        return None
    return None

# ==============================================================================
# CORE MONTH-OVER-MONTH COMPUTATION ENGINE
# ==============================================================================
def compute_mom_comparison(df_base: pd.DataFrame, df_target: pd.DataFrame) -> Dict[str, Any]:
    """
    Computes comprehensive comparison metrics between base (earlier) and target (later) datasets:
    1. Overall KPI Deltas (Count, Market Value, Median Price, Mean Price)
    2. Company-by-Company Matrix (Baseline vs Target, Abs Delta, % Growth)
    3. Property Type Shifts
    4. Inflow & Outflow Tracking:
       - New Listings (เข้าใหม่)
       - Delisted / Sold (ปิดการขาย/หายไป)
       - Price Adjustments (ปรับราคาขึ้น/ลง)
    """
    if df_base is None or df_base.empty or df_target is None or df_target.empty:
        return {}
        
    def make_asset_key(df_in: pd.DataFrame) -> pd.Series:
        comp = df_in['บริษัท'].fillna('').astype(str).str.strip().str.upper()
        code = df_in['รหัสทรัพย์'].fillna('').astype(str).str.strip()
        invalid_set = {'', 'nan', '-', 'None'}
        
        # Fallback to ID or Title if code is missing/blank
        if 'ID' in df_in.columns:
            id_col = df_in['ID'].fillna('').astype(str).str.strip()
            mask_code_invalid = code.isin(invalid_set)
            code = code.where(~mask_code_invalid, id_col)
            
        title = df_in['ชื่อประกาศ'].fillna('').astype(str).str.strip() if 'ชื่อประกาศ' in df_in.columns else pd.Series('', index=df_in.index)
        mask_still_invalid = code.isin(invalid_set)
        code = code.where(~mask_still_invalid, title)
        return comp + "___" + code
        
    df_base_clean = df_base.copy()
    df_target_clean = df_target.copy()
    
    df_base_clean['_match_key'] = make_asset_key(df_base_clean)
    df_target_clean['_match_key'] = make_asset_key(df_target_clean)
    
    # 1. Total KPI Deltas
    base_count = len(df_base_clean)
    target_count = len(df_target_clean)
    delta_count = target_count - base_count
    pct_count_growth = (delta_count / base_count * 100) if base_count > 0 else 0.0
    
    base_prices = df_base_clean['ราคา'].dropna()
    base_prices = base_prices[base_prices > 0]
    target_prices = df_target_clean['ราคา'].dropna()
    target_prices = target_prices[target_prices > 0]
    
    base_val_mb = base_prices.sum() / 1e6 if not base_prices.empty else 0.0
    target_val_mb = target_prices.sum() / 1e6 if not target_prices.empty else 0.0
    delta_val_mb = target_val_mb - base_val_mb
    pct_val_growth = (delta_val_mb / base_val_mb * 100) if base_val_mb > 0 else 0.0
    
    base_median_price = base_prices.median() if not base_prices.empty else 0.0
    target_median_price = target_prices.median() if not target_prices.empty else 0.0
    delta_median_price = target_median_price - base_median_price
    pct_median_growth = (delta_median_price / base_median_price * 100) if base_median_price > 0 else 0.0
    
    base_mean_price = base_prices.mean() if not base_prices.empty else 0.0
    target_mean_price = target_prices.mean() if not target_prices.empty else 0.0
    delta_mean_price = target_mean_price - base_mean_price
    
    # 2. Company-by-Company Matrix
    comp_base = df_base_clean.groupby('บริษัท').agg(
        count_base=('ราคา', 'count'),
        val_mb_base=('ราคา', lambda x: x[x > 0].sum() / 1e6),
        median_base=('ราคา', lambda x: x[x > 0].median() if not x[x > 0].empty else 0.0)
    ).reset_index()
    
    comp_target = df_target_clean.groupby('บริษัท').agg(
        count_target=('ราคา', 'count'),
        val_mb_target=('ราคา', lambda x: x[x > 0].sum() / 1e6),
        median_target=('ราคา', lambda x: x[x > 0].median() if not x[x > 0].empty else 0.0)
    ).reset_index()
    
    comp_matrix = pd.merge(comp_base, comp_target, on='บริษัท', how='outer').fillna(0)
    comp_matrix['delta_count'] = comp_matrix['count_target'] - comp_matrix['count_base']
    comp_matrix['pct_growth'] = comp_matrix.apply(
        lambda r: (r['delta_count'] / r['count_base'] * 100) if r['count_base'] > 0 else (100.0 if r['count_target'] > 0 else 0.0),
        axis=1
    )
    comp_matrix['delta_val_mb'] = comp_matrix['val_mb_target'] - comp_matrix['val_mb_base']
    comp_matrix['pct_val_growth'] = comp_matrix.apply(
        lambda r: (r['delta_val_mb'] / r['val_mb_base'] * 100) if r['val_mb_base'] > 0 else (100.0 if r['val_mb_target'] > 0 else 0.0),
        axis=1
    )
    comp_matrix = comp_matrix.sort_values(by='count_target', ascending=False).reset_index(drop=True)
    
    # 3. Property Type Shifts
    ptype_base = df_base_clean['ประเภททรัพย์'].value_counts().reset_index()
    ptype_base.columns = ['ประเภททรัพย์', 'base_count']
    ptype_target = df_target_clean['ประเภททรัพย์'].value_counts().reset_index()
    ptype_target.columns = ['ประเภททรัพย์', 'target_count']
    ptype_matrix = pd.merge(ptype_base, ptype_target, on='ประเภททรัพย์', how='outer').fillna(0)
    ptype_matrix['delta_count'] = ptype_matrix['target_count'] - ptype_matrix['base_count']
    ptype_matrix['pct_growth'] = ptype_matrix.apply(
        lambda r: (r['delta_count'] / r['base_count'] * 100) if r['base_count'] > 0 else 100.0,
        axis=1
    )
    ptype_matrix = ptype_matrix.sort_values(by='target_count', ascending=False).reset_index(drop=True)
    
    # 4. Inflow & Outflow Tracking
    base_keys_set = set(df_base_clean['_match_key'])
    target_keys_set = set(df_target_clean['_match_key'])
    
    # New Arrivals (In Target but not in Base)
    new_keys = target_keys_set - base_keys_set
    df_new_arrivals = df_target_clean[df_target_clean['_match_key'].isin(new_keys)].copy()
    
    # Delisted / Sold (In Base but not in Target)
    delisted_keys = base_keys_set - target_keys_set
    df_delisted = df_base_clean[df_base_clean['_match_key'].isin(delisted_keys)].copy()
    
    # Existing in both -> Check Price Adjustments
    common_keys = base_keys_set.intersection(target_keys_set)
    df_base_common = df_base_clean[df_base_clean['_match_key'].isin(common_keys)].drop_duplicates(subset=['_match_key'])
    df_target_common = df_target_clean[df_target_clean['_match_key'].isin(common_keys)].drop_duplicates(subset=['_match_key'])
    
    merged_common = pd.merge(
        df_target_common,
        df_base_common[['_match_key', 'ราคา']],
        on='_match_key',
        suffixes=('', '_ก่อนหน้า')
    )
    
    price_changed_mask = (
        merged_common['ราคา'].notna() & 
        merged_common['ราคา_ก่อนหน้า'].notna() & 
        (merged_common['ราคา'] > 0) & 
        (merged_common['ราคา_ก่อนหน้า'] > 0) & 
        (merged_common['ราคา'] != merged_common['ราคา_ก่อนหน้า'])
    )
    
    df_price_changed = merged_common[price_changed_mask].copy()
    if not df_price_changed.empty:
        df_price_changed['ส่วนต่างราคา (บาท)'] = df_price_changed['ราคา'] - df_price_changed['ราคา_ก่อนหน้า']
        df_price_changed['% เปลี่ยนแปลงราคา'] = (df_price_changed['ส่วนต่างราคา (บาท)'] / df_price_changed['ราคา_ก่อนหน้า']) * 100.0
        df_price_changed['สถานะการปรับราคา'] = np.where(
            df_price_changed['ส่วนต่างราคา (บาท)'] < 0, "🔻 ลดราคา (Price Drop)", "🔺 ปรับราคาขึ้น (Price Hike)"
        )
    
    return {
        "kpi": {
            "base_count": base_count,
            "target_count": target_count,
            "delta_count": delta_count,
            "pct_count_growth": pct_count_growth,
            "base_val_mb": base_val_mb,
            "target_val_mb": target_val_mb,
            "delta_val_mb": delta_val_mb,
            "pct_val_growth": pct_val_growth,
            "base_median_price": base_median_price,
            "target_median_price": target_median_price,
            "delta_median_price": delta_median_price,
            "pct_median_growth": pct_median_growth,
            "base_mean_price": base_mean_price,
            "target_mean_price": target_mean_price,
            "delta_mean_price": delta_mean_price
        },
        "comp_matrix": comp_matrix,
        "ptype_matrix": ptype_matrix,
        "df_new_arrivals": df_new_arrivals,
        "df_delisted": df_delisted,
        "df_price_changed": df_price_changed
    }

# ==============================================================================
# UI EXPORT HELPER
# ==============================================================================
def render_download_buttons(df: pd.DataFrame, filename_prefix: str, key_suffix: str):
    """Renders download buttons for CSV and Excel."""
    if df is None or df.empty:
        st.info("ไม่มีข้อมูลสำหรับดาวน์โหลด")
        return
        
    c1, c2 = st.columns(2)
    with c1:
        csv_data = df.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            label="📄 ดาวน์โหลด CSV (.csv) ⚡",
            data=csv_data,
            file_name=f"{filename_prefix}.csv",
            mime="text/csv",
            use_container_width=True,
            key=f"dl_csv_{key_suffix}"
        )
    with c2:
        excel_buffer = io.BytesIO()
        with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Comparison')
        st.download_button(
            label="📊 ดาวน์โหลด Excel (.xlsx)",
            data=excel_buffer.getvalue(),
            file_name=f"{filename_prefix}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            key=f"dl_excel_{key_suffix}"
        )

# ==============================================================================
# COMPANY SUMMARY CARDS GENERATION & UI
# ==============================================================================
def extract_company_date_str(df_comp: Optional[pd.DataFrame]) -> str:
    """Extract readable Thai date span string from company dataframe."""
    if df_comp is None or df_comp.empty:
        return "-"
    if 'วันที่ดึงข้อมูล' in df_comp.columns:
        dts = parse_date_safely(df_comp['วันที่ดึงข้อมูล'])
        if not dts.empty:
            max_dt = dts.max()
            min_dt = dts.min()
            if min_dt.date() == max_dt.date():
                return format_thai_date(max_dt)
            else:
                return f"{format_thai_date(min_dt)} - {format_thai_date(max_dt)}"
    return "-"

def build_company_card_metrics(df_base: Optional[pd.DataFrame], df_target: Optional[pd.DataFrame], mom_result: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Builds rich metrics for individual company comparison cards.
    """
    if df_target is None or df_target.empty:
        return []
        
    df_new = mom_result.get("df_new_arrivals", pd.DataFrame())
    df_del = mom_result.get("df_delisted", pd.DataFrame())
    df_price = mom_result.get("df_price_changed", pd.DataFrame())
    
    t_comps = set(df_target['บริษัท'].dropna().unique()) if 'บริษัท' in df_target.columns else set()
    b_comps = set(df_base['บริษัท'].dropna().unique()) if (df_base is not None and not df_base.empty and 'บริษัท' in df_base.columns) else set()
    all_comps = sorted(list(t_comps.union(b_comps)))
    
    COMPANY_PRIORITY = ["LED", "SAM", "BAM", "Chayo555", "Chayo", "GHB", "KBANK", "KTB", "SCB", "GSB", "DDproperty", "Livinginsider", "NaYoo", "ZmyHome", "Baania"]
    sorted_comps = sorted(
        all_comps,
        key=lambda c: (COMPANY_PRIORITY.index(c) if c in COMPANY_PRIORITY else 999, c)
    )
    
    card_metrics = []
    
    for comp in sorted_comps:
        comp_str = str(comp).strip()
        if not comp_str or comp_str in ['nan', 'None', 'Taladnudbaan', 'ตลาดนัด']:
            continue
            
        t_sub = df_target[df_target['บริษัท'] == comp_str] if 'บริษัท' in df_target.columns else pd.DataFrame()
        b_sub = df_base[df_base['บริษัท'] == comp_str] if (df_base is not None and not df_base.empty and 'บริษัท' in df_base.columns) else pd.DataFrame()
        
        target_count = len(t_sub)
        base_count = len(b_sub)
        
        # Scraped dates
        target_date_str = extract_company_date_str(t_sub)
        base_date_str = extract_company_date_str(b_sub)
        
        # Prices
        t_prices = t_sub['ราคา'].dropna() if 'ราคา' in t_sub.columns else pd.Series(dtype=float)
        t_prices = t_prices[t_prices > 0]
        b_prices = b_sub['ราคา'].dropna() if 'ราคา' in b_sub.columns else pd.Series(dtype=float)
        b_prices = b_prices[b_prices > 0]
        
        target_val_mb = (t_prices.sum() / 1e6) if not t_prices.empty else 0.0
        base_val_mb = (b_prices.sum() / 1e6) if not b_prices.empty else 0.0
        delta_val_mb = target_val_mb - base_val_mb
        
        target_median = t_prices.median() if not t_prices.empty else 0.0
        base_median = b_prices.median() if not b_prices.empty else 0.0
        delta_median = target_median - base_median
        
        # Inflow / Outflow
        comp_new = df_new[df_new['บริษัท'] == comp_str] if (df_new is not None and not df_new.empty and 'บริษัท' in df_new.columns) else pd.DataFrame()
        new_count = len(comp_new)
        new_val_mb = (comp_new['ราคา'].dropna().sum() / 1e6) if (not comp_new.empty and 'ราคา' in comp_new.columns) else 0.0
        
        comp_del = df_del[df_del['บริษัท'] == comp_str] if (df_del is not None and not df_del.empty and 'บริษัท' in df_del.columns) else pd.DataFrame()
        del_count = len(comp_del)
        del_val_mb = (comp_del['ราคา'].dropna().sum() / 1e6) if (not comp_del.empty and 'ราคา' in comp_del.columns) else 0.0
        
        net_delta = target_count - base_count
        pct_growth = (net_delta / base_count * 100.0) if base_count > 0 else (100.0 if target_count > 0 else 0.0)
        
        # Top Growing Property Types
        t_ptypes = t_sub['ประเภททรัพย์'].value_counts() if (not t_sub.empty and 'ประเภททรัพย์' in t_sub.columns) else pd.Series(dtype=int)
        b_ptypes = b_sub['ประเภททรัพย์'].value_counts() if (not b_sub.empty and 'ประเภททรัพย์' in b_sub.columns) else pd.Series(dtype=int)
        
        diff_types = []
        for pt, cnt in t_ptypes.items():
            b_cnt = b_ptypes.get(pt, 0)
            diff_pt = cnt - b_cnt
            if diff_pt > 0:
                diff_types.append((pt, diff_pt))
        diff_types.sort(key=lambda x: x[1], reverse=True)
        
        if diff_types:
            growing_types_str = ", ".join([f"{pt} (+{d:,})" for pt, d in diff_types[:2]])
        elif not t_ptypes.empty:
            top_pt = t_ptypes.index[0]
            growing_types_str = f"{top_pt} ({t_ptypes.iloc[0]:,} รายการ)"
        else:
            growing_types_str = "-"
            
        # Price Adjustments
        comp_price = df_price[df_price['บริษัท'] == comp_str] if (df_price is not None and not df_price.empty and 'บริษัท' in df_price.columns) else pd.DataFrame()
        price_drops = (comp_price['ส่วนต่างราคา (บาท)'] < 0).sum() if not comp_price.empty else 0
        price_hikes = (comp_price['ส่วนต่างราคา (บาท)'] > 0).sum() if not comp_price.empty else 0
        
        card_metrics.append({
            "company": comp_str,
            "color": COMPANY_COLORS.get(comp_str, DEFAULT_COLOR),
            "target_count": target_count,
            "target_date_str": target_date_str,
            "target_val_mb": target_val_mb,
            "target_median": target_median,
            "base_count": base_count,
            "base_date_str": base_date_str,
            "base_val_mb": base_val_mb,
            "base_median": base_median,
            "new_count": new_count,
            "new_val_mb": new_val_mb,
            "del_count": del_count,
            "del_val_mb": del_val_mb,
            "net_delta": net_delta,
            "pct_growth": pct_growth,
            "delta_val_mb": delta_val_mb,
            "delta_median": delta_median,
            "growing_types_str": growing_types_str,
            "price_drops": price_drops,
            "price_hikes": price_hikes
        })
        
    return card_metrics

def render_company_summary_cards(
    company_metrics: List[Dict[str, Any]], 
    is_dark_mode: bool = False,
    sort_opt: str = "ลำดับมาตรฐาน"
):
    """
    Renders responsive grid cards comparing each company's MoM statistics.
    """
    if not company_metrics:
        st.info("ไม่มีข้อมูลการ์ดรายบริษัท")
        return
        
    card_bg = "#1e293b" if is_dark_mode else "#ffffff"
    card_border = "#334155" if is_dark_mode else "#e2e8f0"
    text_color = "#f8fafc" if is_dark_mode else "#1e293b"
    subtext_color = "#94a3b8" if is_dark_mode else "#64748b"
    
    # Priority company order: LED (Top) -> SAM -> BAM -> Chayo -> Financial Institutions -> Platforms
    company_order_priority = [
        "LED", "SAM", "BAM", "CHAYO555", "CHAYO", "CHAYO NPA",
        "GHB", "KBANK", "KTB", "SCB", "GSB", "BAY", "TTB", "CIMB",
        "DDPROPERTY", "LIVINGINSIDER", "NAYOO", "ZMYHOME", "BAANIA"
    ]
    
    def get_comp_rank(comp_name: str) -> int:
        c_upper = str(comp_name).strip().upper()
        for idx, name in enumerate(company_order_priority):
            if name == c_upper or name in c_upper or c_upper in name:
                return idx
            if c_upper == "LED" or "บังคับคดี" in c_upper:
                return 0
        return 999
        
    filtered_cards = list(company_metrics)
        
    # Apply sorting
    if "ลำดับมาตรฐาน" in sort_opt:
        filtered_cards = sorted(filtered_cards, key=lambda c: (get_comp_rank(c['company']), -c['target_count']))
    elif "เข้าใหม่" in sort_opt:
        filtered_cards = sorted(filtered_cards, key=lambda c: c['new_count'], reverse=True)
    elif "ปิดการขาย" in sort_opt or "หายไป" in sort_opt:
        filtered_cards = sorted(filtered_cards, key=lambda c: c['del_count'], reverse=True)
    elif "อัตราการเติบโต" in sort_opt:
        filtered_cards = sorted(filtered_cards, key=lambda c: c['pct_growth'], reverse=True)
    elif "มูลค่าพอร์ต" in sort_opt:
        filtered_cards = sorted(filtered_cards, key=lambda c: c['target_val_mb'], reverse=True)
    elif "จำนวนทรัพย์" in sort_opt:
        filtered_cards = sorted(filtered_cards, key=lambda c: c['target_count'], reverse=True)
    else: # Default LED, SAM, BAM, Chayo, Banks
        filtered_cards = sorted(filtered_cards, key=lambda c: (get_comp_rank(c['company']), -c['target_count']))
        
    # Render each company as 1 horizontal row with 4 distinct smart boxes
    for card in filtered_cards:
        _render_company_horizontal_row(card, card_bg, card_border, text_color, subtext_color, is_dark_mode)

def _render_company_horizontal_row(card: Dict[str, Any], card_bg: str, card_border: str, text_color: str, subtext_color: str, is_dark_mode: bool):
    """Renders 1 company as a horizontal row with 4 distinct professional executive boxes side-by-side."""
    color = card['color']
    comp = card['company']
    
    # Growth badge
    net_d = card['net_delta']
    pct_g = card['pct_growth']
    if net_d > 0:
        growth_badge = f"+{pct_g:.1f}% (+{net_d:,})"
        growth_bg = "rgba(16, 185, 129, 0.12)"
        growth_color = "#059669" if not is_dark_mode else "#10b981"
    elif net_d < 0:
        growth_badge = f"{pct_g:.1f}% ({net_d:,})"
        growth_bg = "rgba(239, 68, 68, 0.12)"
        growth_color = "#dc2626" if not is_dark_mode else "#ef4444"
    else:
        growth_badge = "0.0% (คงที่)"
        growth_bg = "rgba(148, 163, 184, 0.12)"
        growth_color = "#64748b" if not is_dark_mode else "#94a3b8"
        
    net_color = "#059669" if net_d >= 0 else "#dc2626"
    if is_dark_mode:
        net_color = "#10b981" if net_d >= 0 else "#ef4444"
    net_sign = "+" if net_d >= 0 else ""
    
    # Value delta
    d_val = card['delta_val_mb']
    val_sign = "+" if d_val >= 0 else ""
    val_color = "#059669" if d_val >= 0 else "#dc2626"
    if is_dark_mode:
        val_color = "#10b981" if d_val >= 0 else "#ef4444"
    
    # Price adjustment text
    p_drops = card['price_drops']
    p_hikes = card['price_hikes']
    if p_drops > 0 or p_hikes > 0:
        drop_c = "#dc2626" if not is_dark_mode else "#ef4444"
        hike_c = "#059669" if not is_dark_mode else "#10b981"
        price_adj_str = f"<span style='color:{drop_c}; font-weight:600;'>ลดลง {p_drops:,}</span> <span style='color:{subtext_color};'>/</span> <span style='color:{hike_c}; font-weight:600;'>ปรับขึ้น {p_hikes:,}</span>"
    else:
        price_adj_str = f"<span style='color:{subtext_color};'>ไม่มีปรับราคา</span>"
        
    col1, col2, col3, col4 = st.columns([1.1, 0.95, 1.3, 1.65])
    
    # กล่องที่ 1: ข้อมูลปัจจุบัน
    with col1:
        st.markdown(f"""
        <div class="audit-metric-card" style="border-left: 4px solid {color}; padding: 12px 16px; margin-bottom: 8px; height: 100%;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                <span style="font-weight: 700; color: {text_color}; font-size: 0.95rem; letter-spacing: -0.2px;">{comp}</span>
                <span style="font-size: 0.72rem; padding: 2px 7px; border-radius: 4px; font-weight: 600; background: {growth_bg}; color: {growth_color};">{growth_badge}</span>
            </div>
            <div style="font-size: 1.35rem; font-weight: 800; color: {text_color}; line-height: 1.2;">
                {card['target_count']:,} <span style="font-size: 0.8rem; font-weight: 500; color: {subtext_color};">ทรัพย์</span>
            </div>
            <div style="font-size: 0.74rem; color: {subtext_color}; margin-top: 5px;">
                วันที่ดึง: <span style="color:{text_color}; font-weight: 600;">{card['target_date_str']}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
    # กล่องที่ 2: เดือนที่แล้ว
    with col2:
        st.markdown(f"""
        <div class="audit-metric-card" style="padding: 12px 16px; margin-bottom: 8px; height: 100%;">
            <div style="font-size: 0.74rem; font-weight: 600; letter-spacing: 0.3px; color: {subtext_color}; margin-bottom: 4px;">
                เดือนที่แล้ว
            </div>
            <div style="font-size: 1.35rem; font-weight: 800; color: {subtext_color}; line-height: 1.2;">
                {card['base_count']:,} <span style="font-size: 0.8rem; font-weight: 500;">ทรัพย์</span>
            </div>
            <div style="font-size: 0.74rem; color: {subtext_color}; margin-top: 5px;">
                วันที่ดึง: <span style="color:{subtext_color}; font-weight: 600;">{card['base_date_str']}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
    # กล่องที่ 3: ทรัพย์หมุนเวียน (เข้าใหม่ / ขายได้ / สุทธิ)
    with col3:
        st.markdown(f"""
        <div class="audit-metric-card" style="padding: 12px 16px; margin-bottom: 8px; height: 100%;">
            <div style="font-size: 0.74rem; font-weight: 600; letter-spacing: 0.3px; color: {subtext_color}; margin-bottom: 4px;">
                การหมุนเวียนทรัพย์สิน
            </div>
            <div style="font-size: 0.8rem; line-height: 1.5;">
                <div style="display: flex; justify-content: space-between;">
                    <span style="color:{subtext_color};">เพิ่มขึ้นมา:</span>
                    <span style="font-weight: 600; color:{'#059669' if not is_dark_mode else '#10b981'};">+{card['new_count']:,} <span style="font-size:0.7rem; color:{subtext_color}; font-weight:normal;">(฿{card['new_val_mb']:,.1f}M)</span></span>
                </div>
                <div style="display: flex; justify-content: space-between;">
                    <span style="color:{subtext_color};">ขายได้:</span>
                    <span style="font-weight: 600; color:{'#dc2626' if not is_dark_mode else '#ef4444'};">-{card['del_count']:,} <span style="font-size:0.7rem; color:{subtext_color}; font-weight:normal;">(฿{card['del_val_mb']:,.1f}M)</span></span>
                </div>
                <div style="display: flex; justify-content: space-between; margin-top: 2px; padding-top: 2px; border-top: 1px dashed {card_border};">
                    <span style="color:{subtext_color}; font-weight: 500;">สุทธิ:</span>
                    <span style="font-size: 0.8rem; color: {net_color}; font-weight: 700;">{net_sign}{net_d:,} ทรัพย์ ({net_sign}{pct_g:.1f}%)</span>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
    # กล่องที่ 4: ประเภทที่เพิ่ม & มูลค่า
    with col4:
        st.markdown(f"""
        <div class="audit-metric-card" style="padding: 12px 16px; margin-bottom: 8px; height: 100%;">
            <div style="font-size: 0.74rem; font-weight: 600; letter-spacing: 0.3px; color: {subtext_color}; margin-bottom: 4px;">
                ประเภท & มูลค่าที่เพิ่ม
            </div>
            <div style="font-size: 0.78rem; line-height: 1.5; color: {text_color};">
                <div style="white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" title="{card['growing_types_str']}">
                    <span style="color:{subtext_color};">ประเภทที่เพิ่ม:</span> <span style="color:#2563eb; font-weight:600;">{card['growing_types_str']}</span>
                </div>
                <div style="margin-top: 1px;">
                    <span style="color:{subtext_color};">มูลค่าพอร์ต:</span> <span style="font-weight:700;">฿{card['target_val_mb']:,.0f}M</span> <span style="color:{val_color}; font-size:0.74rem; font-weight:600;">({val_sign}฿{abs(d_val):,.0f}M)</span>
                    <span style="color:{subtext_color}; margin: 0 4px;">|</span>
                    <span style="color:{subtext_color};">ราคากลาง:</span> <span style="font-weight:600;">฿{card['target_median']:,.0f}</span>
                </div>
                <div style="margin-top: 1px;">
                    <span style="color:{subtext_color};">ปรับราคา:</span> {price_adj_str}
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

# ==============================================================================
# MAIN RENDER FUNCTION FOR STREAMLIT TAB
# ==============================================================================
def render_monthly_comparison(
    df_raw: Optional[pd.DataFrame],
    is_dark_mode: bool = False,
    plotly_template: str = "plotly_white",
    style_plotly_fig = None
):
    """
    Renders the complete Monthly Comparison & Scraper Health Audit Tab in Streamlit.
    """
    # -------------------------------------------------------------------------
    # CSS Custom Card Styles
    # -------------------------------------------------------------------------
    card_bg = "#1e293b" if is_dark_mode else "#ffffff"
    card_border = "#334155" if is_dark_mode else "#e2e8f0"
    text_color = "#f8fafc" if is_dark_mode else "#1e293b"
    subtext_color = "#94a3b8" if is_dark_mode else "#64748b"
    
    st.markdown(f"""
    <style>
    .audit-metric-card {{
        background: {card_bg};
        border: 1px solid {card_border};
        border-radius: 10px;
        box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.04), 0 1px 2px -1px rgba(0, 0, 0, 0.02);
        transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }}
    .audit-metric-card:hover {{
        border-color: #cbd5e1;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.06), 0 2px 4px -2px rgba(0, 0, 0, 0.03);
    }}
    .audit-card-title {{
        font-size: 0.8rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        color: {subtext_color};
        margin-bottom: 4px;
        display: flex;
        align-items: center;
        gap: 6px;
    }}
    .audit-card-value {{
        font-size: 1.45rem;
        font-weight: 800;
        color: {text_color};
        line-height: 1.2;
    }}
    .audit-card-sub {{
        font-size: 0.75rem;
        color: {subtext_color};
        margin-top: 4px;
    }}
    .freshness-tag-fresh {{
        background: rgba(16, 185, 129, 0.15);
        color: #10b981;
        font-weight: 700;
        padding: 4px 8px;
        border-radius: 6px;
        font-size: 0.78rem;
    }}
    .freshness-tag-mod {{
        background: rgba(245, 158, 11, 0.15);
        color: #f59e0b;
        font-weight: 700;
        padding: 4px 8px;
        border-radius: 6px;
        font-size: 0.78rem;
    }}
    .freshness-tag-stale {{
        background: rgba(239, 68, 68, 0.15);
        color: #ef4444;
        font-weight: 700;
        padding: 4px 8px;
        border-radius: 6px;
        font-size: 0.78rem;
    }}
    </style>
    """, unsafe_allow_html=True)
    
    # -------------------------------------------------------------------------
    # SECTION 1: PERIOD SELECTION & SORT CONTROLS
    # -------------------------------------------------------------------------
    available_snapshots = scan_available_snapshots("CSV_Output")
    if not available_snapshots:
        st.warning("⚠️ ยังไม่พบชุดข้อมูลสำหรับเปรียบเทียบในระบบ กรุณาตรวจสอบโฟลเดอร์ CSV_Output")
        return

    snapshot_labels = [s["label"] for s in available_snapshots]
    
    col_target, col_base, col_sort = st.columns([0.38, 0.38, 0.24])
    with col_target:
        selected_target_label = st.selectbox(
            "📅 ชุดข้อมูลปัจจุบัน (Target Period)",
            options=snapshot_labels,
            index=0,
            key="mom_target_snapshot_selector",
            help="เลือกชุดข้อมูลหรืองวดเวลาล่าสุดที่ต้องการนำมาวิเคราะห์"
        )
        target_snapshot = available_snapshots[snapshot_labels.index(selected_target_label)]
        
    with col_base:
        base_idx = 1 if len(available_snapshots) > 1 else 0
        selected_base_label = st.selectbox(
            "🗓️ ชุดข้อมูลเปรียบเทียบ (Baseline Period)",
            options=snapshot_labels,
            index=base_idx,
            key="mom_base_snapshot_selector",
            help="เลือกชุดข้อมูลหรืองวดเวลาก่อนหน้าที่ต้องการใช้เป็นฐานเปรียบเทียบ"
        )
        base_snapshot = available_snapshots[snapshot_labels.index(selected_base_label)]
        
    with col_sort:
        sort_opt = st.selectbox(
            "🔽 จัดเรียงตาม",
            options=[
                "ลำดับมาตรฐาน (LED, SAM, BAM, Chayo...)",
                "จำนวนทรัพย์ปัจจุบันสูงสุด",
                "ทรัพย์เข้าใหม่สูงสุด",
                "ปิดการขาย/หายไปสูงสุด",
                "อัตราการเติบโตสูงสุด (%)",
                "มูลค่าพอร์ตสูงสุด"
            ],
            index=0,
            key="mom_card_sort_opt"
        )
        
    df_base_loaded = load_snapshot_dataset(base_snapshot)
    df_target_loaded = load_snapshot_dataset(target_snapshot)
        
    # Fallback to current raw dataframe if target is same as parquet
    if df_target_loaded is None and df_raw is not None:
        df_target_loaded = df_raw
    if df_base_loaded is None and df_raw is not None:
        df_base_loaded = df_raw

    if df_base_loaded is None or df_target_loaded is None or df_base_loaded.empty or df_target_loaded.empty:
        st.warning("⚠️ ยังไม่สามารถโหลดชุดข้อมูลเพื่อเปรียบเทียบได้ กรุณาตรวจสอบไฟล์ในโฟลเดอร์ CSV_Output")
        return

    # Compute Comparison
    mom_result = compute_mom_comparison(df_base_loaded, df_target_loaded)
    company_card_metrics = build_company_card_metrics(df_base_loaded, df_target_loaded, mom_result)

    # -------------------------------------------------------------------------
    # SECTION 2: COMPANY MOM COMPARISON SUMMARY CARDS
    # -------------------------------------------------------------------------
    render_company_summary_cards(company_card_metrics, is_dark_mode=is_dark_mode, sort_opt=sort_opt)

