# -*- coding: utf-8 -*-
"""
clean_sam_project.py
สคริปต์รัน Clean และจัดมาตรฐานชื่อโครงการของ SAM (และทุกค่าย) ประจำ All Asset NPA Dashboard
ใช้งาน:
    python clean_sam_project.py
    python clean_sam_project.py --input "CSV_Output/2026_09/SAM_NPA_New_2026_09.csv"
"""

import os
import sys

# Add Py Scraper to sys.path
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_SCRAPER_DIR = os.path.join(_BASE_DIR, "Py Scraper")
if _SCRAPER_DIR not in sys.path:
    sys.path.insert(0, _SCRAPER_DIR)

from clean_project_util import (
    clean_sam_project_name,
    is_same_project,
    clean_csv_project_names,
    main
)

if __name__ == "__main__":
    main()
