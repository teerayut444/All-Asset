import pandas as pd
import streamlit as st
from dashboard_metrics import build_kpi_summary_text

def format_price_kpi(val_baht):
    """Formats numeric Baht values to compact legible strings (e.g. ฿1.25M, ฿500K)."""
    if pd.isna(val_baht) or val_baht is None or val_baht <= 0:
        return "฿0"
    if val_baht >= 1e9:
        return f"฿{val_baht / 1e9:,.2f}B"
    elif val_baht >= 1e6:
        return f"฿{val_baht / 1e6:,.2f}M"
    elif val_baht >= 1e3:
        return f"฿{val_baht / 1e3:,.1f}K"
    else:
        return f"฿{val_baht:,.0f}"

def render_floating_kpi_cards(df_filtered, df_raw, is_dark_mode=False):
    """Computes and renders the floating KPI cards summary ribbon."""
    total_count = len(df_raw) if df_raw is not None else 0
    filtered_count = len(df_filtered) if df_filtered is not None else 0
    
    valid_prices = pd.Series(dtype=float)
    if df_filtered is not None and not df_filtered.empty and 'ราคา' in df_filtered.columns:
        valid_prices = df_filtered['ราคา'].dropna()
        valid_prices = valid_prices[valid_prices > 0]

    if not valid_prices.empty:
        total_value = valid_prices.sum()
        min_price = valid_prices.min()
        median_price = valid_prices.median()
        mean_price = valid_prices.mean()
        max_price = valid_prices.max()
        sd_price = valid_prices.std() if len(valid_prices) > 1 else 0.0
        
        total_value_str = format_price_kpi(total_value)
        min_price_str = format_price_kpi(min_price)
        median_price_str = format_price_kpi(median_price)
        mean_price_str = format_price_kpi(mean_price)
        max_price_str = format_price_kpi(max_price)
        sd_price_str = f"±{format_price_kpi(sd_price)}" if sd_price > 0 else "฿0"
    else:
        total_value_str = "฿0"
        min_price_str = "฿0"
        median_price_str = "฿0"
        mean_price_str = "฿0"
        max_price_str = "฿0"
        sd_price_str = "฿0"

    total_count_str = f"{total_count:,.0f}"
    filtered_count_str = f"{filtered_count:,.0f}"
    summary_text = build_kpi_summary_text(total_count, filtered_count)

    floating_kpi_html = f"""
    <div class="floating-kpi-container" style="margin-top: 10px; margin-bottom: 20px;">
        <div class="floating-card" id="kpi-card-count" data-default-val="{filtered_count_str}" data-default-sub="{summary_text}">
            <div class="floating-card-title"><i class="fa fa-list" style="color: #047857;"></i> ทรัพย์สินที่พบ <span class="kpi-scope-badge" style="display:none;"></span></div>
            <div class="floating-card-value">{filtered_count_str}</div>
            <div class="floating-card-sub">{summary_text}</div>
        </div>
        <div class="floating-card" id="kpi-card-total-val" data-default-val="{total_value_str}" data-default-sub="มูลค่ารวมตามตัวกรอง">
            <div class="floating-card-title"><i class="fa fa-wallet" style="color: #059669;"></i> มูลค่ารวมทรัพย์สิน <span class="kpi-scope-badge" style="display:none;"></span></div>
            <div class="floating-card-value">{total_value_str}</div>
            <div class="floating-card-sub">มูลค่ารวมตามตัวกรอง</div>
        </div>
        <div class="floating-card" id="kpi-card-min-price" data-default-val="{min_price_str}" data-default-sub="ราคาเริ่มต้นต่ำสุด">
            <div class="floating-card-title"><i class="fa fa-arrow-down" style="color: #10b981;"></i> ราคาต่ำสุด (Min) <span class="kpi-scope-badge" style="display:none;"></span></div>
            <div class="floating-card-value">{min_price_str}</div>
            <div class="floating-card-sub">ราคาเริ่มต้นต่ำสุด</div>
        </div>
        <div class="floating-card" id="kpi-card-median-price" data-default-val="{median_price_str}" data-default-sub="ค่ามัธยฐานของกลุ่ม">
            <div class="floating-card-title"><i class="fa fa-tags" style="color: #047857;"></i> ราคากลาง (Median) <span class="kpi-scope-badge" style="display:none;"></span></div>
            <div class="floating-card-value">{median_price_str}</div>
            <div class="floating-card-sub">ค่ามัธยฐานของกลุ่ม</div>
        </div>
        <div class="floating-card" id="kpi-card-mean-price" data-default-val="{mean_price_str}" data-default-sub="ค่าเฉลี่ยเลขคณิต">
            <div class="floating-card-title"><i class="fa fa-calculator" style="color: #059669;"></i> ราคาเฉลี่ย (Mean) <span class="kpi-scope-badge" style="display:none;"></span></div>
            <div class="floating-card-value">{mean_price_str}</div>
            <div class="floating-card-sub">ค่าเฉลี่ยเลขคณิต</div>
        </div>
        <div class="floating-card" id="kpi-card-max-price" data-default-val="{max_price_str}" data-default-sub="มูลค่าสูงสุดในกลุ่ม">
            <div class="floating-card-title"><i class="fa fa-arrow-up" style="color: #10b981;"></i> ราคาสูงสุด (Max) <span class="kpi-scope-badge" style="display:none;"></span></div>
            <div class="floating-card-value">{max_price_str}</div>
            <div class="floating-card-sub">มูลค่าสูงสุดในกลุ่ม</div>
        </div>
        <div class="floating-card" id="kpi-card-sd-price" data-default-val="{sd_price_str}" data-default-sub="การกระจายตัวของราคา">
            <div class="floating-card-title"><i class="fa fa-chart-line" style="color: #047857;"></i> ส่วนเบี่ยงเบน (SD) <span class="kpi-scope-badge" style="display:none;"></span></div>
            <div class="floating-card-value">{sd_price_str}</div>
            <div class="floating-card-sub">การกระจายตัวของราคา</div>
        </div>
    </div>
    """
    st.markdown(floating_kpi_html, unsafe_allow_html=True)
