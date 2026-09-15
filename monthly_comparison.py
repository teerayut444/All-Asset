# -*- coding: utf-8 -*-
"""
monthly_comparison.py
[Backward Compatibility Alias]
This file has been renamed to data_completeness.py to better reflect its true purpose:
Data Completeness Audit & Scraper Health (ความครบถ้วนของข้อมูลและสถานะการดึงข้อมูล).
"""

from data_completeness import (
    render_data_completeness,
    render_monthly_comparison,
    compute_data_completeness_table,
    COMPANY_COLORS,
    WEB_ANNOUNCED_BENCHMARKS
)

__all__ = [
    "render_data_completeness",
    "render_monthly_comparison",
    "compute_data_completeness_table",
    "COMPANY_COLORS",
    "WEB_ANNOUNCED_BENCHMARKS"
]
