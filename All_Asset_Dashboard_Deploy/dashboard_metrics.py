from __future__ import annotations

from typing import Optional

import pandas as pd


def build_kpi_summary_text(total_count: int, filtered_count: int) -> str:
    """Build a short KPI subtitle that explains both total and filtered counts."""
    total_str = f"{total_count:,.0f}"
    filtered_str = f"{filtered_count:,.0f}"
    return f"ทั้งหมดในฐานข้อมูล: {total_str} รายการ | ตามตัวกรองปัจจุบัน: {filtered_str} รายการ"


def build_kpi_metrics(df_raw: Optional[pd.DataFrame], df_filtered: Optional[pd.DataFrame]) -> dict:
    """Build KPI metrics for the dashboard using raw and filtered datasets."""
    total_count = int(len(df_raw)) if df_raw is not None else 0
    filtered_count = int(len(df_filtered)) if df_filtered is not None else 0

    if df_filtered is None or df_filtered.empty or "ราคา" not in df_filtered.columns:
        valid_prices_filtered = pd.Series(dtype=float)
    else:
        valid_prices_filtered = df_filtered["ราคา"].dropna()

    if not valid_prices_filtered.empty:
        total_value = valid_prices_filtered.sum() / 1e6
        avg_price = valid_prices_filtered.mean() / 1e6
        max_price = valid_prices_filtered.max() / 1e6
    else:
        total_value = 0.0
        avg_price = 0.0
        max_price = 0.0

    return {
        "total_count": total_count,
        "filtered_count": filtered_count,
        "total_value": total_value,
        "avg_price": avg_price,
        "max_price": max_price,
        "filter_applied": total_count > 0 and filtered_count != total_count,
        "summary_text": build_kpi_summary_text(total_count, filtered_count),
    }
