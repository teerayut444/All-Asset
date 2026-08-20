# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pydeck as pdk
import base64
import os
from pathlib import Path
import io
import urllib.request
import re
import ssl
import math
import json
from PIL import Image

# SSL context for image fetching
_ssl_ctx = ssl.create_default_context()
_ssl_ctx.check_hostname = False
_ssl_ctx.verify_mode = ssl.CERT_NONE

# ==============================================================================
# CONSTANTS & CONFIGURATIONS
# ==============================================================================
SAM_BRAND_GREEN = "#10b981"
SAM_BRAND_NAVY = "#1e3a8a"
SAM_ACCENT_BLUE = "#3b82f6"
SAM_AMBER = "#f59e0b"
SAM_ROSE = "#f43f5e"
SAM_PURPLE = "#8b5cf6"
SAM_CYAN = "#06b6d4"

COMPANY_COLORS = {
    "SAM": "#10b981",
    "BAM": "#3b82f6",
    "Chayo555": "#f97316",
    "Baania": "#f59e0b",
    "NaYoo": "#8b5cf6",
    "Taladnudbaan": "#06b6d4",
    "ZmyHome": "#ec4899",
    "KBANK": "#059669",
    "GHB": "#ca8a04",
    "SCB": "#7e22ce",
    "KTB": "#0284c7"
}

ASSET_CLASS_MAP = {
    # Residential (ที่อยู่อาศัย)
    "บ้านเดี่ยว": "🏠 ที่อยู่อาศัย (Residential)",
    "ทาวน์เฮ้าส์": "🏠 ที่อยู่อาศัย (Residential)",
    "ห้องชุดพักอาศัย": "🏠 ที่อยู่อาศัย (Residential)",
    "บ้านแฝด": "🏠 ที่อยู่อาศัย (Residential)",
    
    # Land (ที่ดิน)
    "ที่ดินเปล่า": "🌾 ที่ดินเปล่า (Land Plots)",
    
    # Commercial (พาณิชยกรรม)
    "อาคารพาณิชย์": "🏢 อาคารและพาณิชยกรรม (Commercial)",
    "ห้องชุดพาณิชยกรรม/สำนักงาน": "🏢 อาคารและพาณิชยกรรม (Commercial)",
    "อพาร์ทเมนท์": "🏢 อาคารและพาณิชยกรรม (Commercial)",
    "อาคารสำนักงาน": "🏢 อาคารและพาณิชยกรรม (Commercial)",
    "โชว์รูม": "🏢 อาคารและพาณิชยกรรม (Commercial)",
    "โฮมออฟฟิศ": "🏢 อาคารและพาณิชยกรรม (Commercial)",
    
    # Industrial & Mega Commercial (อุตสาหกรรม & โครงการพิเศษ)
    "โรงงาน/โกดัง": "🏭 อุตสาหกรรมและโครงการพิเศษ (Industrial & Mega)",
    "โรงแรม/รีสอร์ท": "🏭 อุตสาหกรรมและโครงการพิเศษ (Industrial & Mega)",
    "ปั๊มน้ำมัน": "🏭 อุตสาหกรรมและโครงการพิเศษ (Industrial & Mega)",
    "โรงพยาบาล": "🏭 อุตสาหกรรมและโครงการพิเศษ (Industrial & Mega)",
    "สวนน้ำ": "🏭 อุตสาหกรรมและโครงการพิเศษ (Industrial & Mega)",
    "ศูนย์จำหน่ายสินค้า": "🏭 อุตสาหกรรมและโครงการพิเศษ (Industrial & Mega)",
    "ห้างสรรพสินค้า": "🏭 อุตสาหกรรมและโครงการพิเศษ (Industrial & Mega)",
    "โรงภาพยนต์": "🏭 อุตสาหกรรมและโครงการพิเศษ (Industrial & Mega)",
    "ฟาร์มเลี้ยงสัตว์": "🏭 อุตสาหกรรมและโครงการพิเศษ (Industrial & Mega)",
    "โครงการที่พักอาศัย/พาณิชยกรรม": "🏭 อุตสาหกรรมและโครงการพิเศษ (Industrial & Mega)",
    
    # Others
    "สังหาริมทรัพย์": "📦 อื่นๆ & สังหาริมทรัพย์ (Others)",
    "อสังหาริมทรัพย์อื่นๆ": "📦 อื่นๆ & สังหาริมทรัพย์ (Others)",
    "อื่นๆ": "📦 อื่นๆ & สังหาริมทรัพย์ (Others)"
}

PRICE_TIER_ORDER = [
    "< 1 ล้านบาท",
    "1 - 3 ล้านบาท",
    "3 - 5 ล้านบาท",
    "5 - 10 ล้านบาท",
    "10 - 20 ล้านบาท",
    "> 20 ล้านบาท"
]

def classify_price_tier(price):
    if pd.isna(price) or price <= 0:
        return "ไม่ระบุราคา"
    if price < 1_000_000:
        return "< 1 ล้านบาท"
    elif price < 3_000_000:
        return "1 - 3 ล้านบาท"
    elif price < 5_000_000:
        return "3 - 5 ล้านบาท"
    elif price < 10_000_000:
        return "5 - 10 ล้านบาท"
    elif price < 20_000_000:
        return "10 - 20 ล้านบาท"
    else:
        return "> 20 ล้านบาท"

def classify_economic_zone(prov):
    p = str(prov).strip()
    if p in ['ชลบุรี', 'ระยอง', 'ฉะเชิงเทรา']:
        return "⚡ เขตเศรษฐกิจพิเศษ (EEC)"
    elif p in ['กรุงเทพมหานคร', 'นนทบุรี', 'ปทุมธานี', 'สมุทรปราการ', 'สมุทรสาคร', 'นครปฐม']:
        return "🌆 กรุงเทพฯ และปริมณฑล (BKK & Metro)"
    elif p in ['เชียงใหม่', 'เชียงราย', 'ลำปาง', 'พิษณุโลก', 'น่าน', 'แพร่', 'พะเยา', 'แม่ฮ่องสอน', 'ลำพูน', 'สุโขทัย', 'อุตรดิตถ์', 'ตาก', 'กำแพงเพชร', 'พิจิตร', 'เพชรบูรณ์', 'นครสวรรค์', 'อุทัยธานี']:
        return "🏞️ ภาคเหนือ (Northern)"
    elif p in ['นครราชสีมา', 'ขอนแก่น', 'อุดรธานี', 'อุบลราชธานี', 'บุรีรัมย์', 'ร้อยเอ็ด', 'สุรินทร์', 'ศรีสะเกษ', 'มหาสารคาม', 'ชัยภูมิ', 'กาฬสินธุ์', 'สกลนคร', 'นครพนม', 'มุกดาหาร', 'ยโสธร', 'อำนาจเจริญ', 'หนองคาย', 'เลย', 'หนองบัวลำภู', 'บึงกาฬ']:
        return "🌾 ภาคตะวันออกเฉียงเหนือ (Northeast)"
    elif p in ['ภูเก็ต', 'สุราษฎร์ธานี', 'สงขลา', 'นครศรีธรรมราช', 'กระบี่', 'พังงา', 'ตรัง', 'ชุมพร', 'ระนอง', 'พัทลุง', 'สตูล', 'ปัตตานี', 'ยะลา', 'นราธิวาส']:
        return "🏖️ ภาคใต้ (Southern)"
    else:
        return "🏛️ ภาคกลาง & ตะวันตก (Central & West)"

def format_price_short(val):
    if pd.isna(val) or val is None:
        return "รอประกาศราคา"
    try:
        val_f = float(val)
        if val_f <= 0:
            return "รอประกาศราคา"
        if val_f >= 1e9:
            return f"฿{val_f / 1e9:,.2f}B"
        elif val_f >= 1e6:
            return f"฿{val_f / 1e6:,.2f}M"
        elif val_f >= 1e3:
            return f"฿{val_f / 1e3:,.1f}K"
        else:
            return f"฿{val_f:,.0f}"
    except (ValueError, TypeError):
        return "รอประกาศราคา"

def format_rai_ngan_wah(sqwah):
    if pd.isna(sqwah) or sqwah <= 0:
        return "-"
    r = int(sqwah // 400)
    rem = sqwah % 400
    g = int(rem // 100)
    w = rem % 100
    parts = []
    if r > 0:
        parts.append(f"{r} ไร่")
    if g > 0:
        parts.append(f"{g} งาน")
    if w > 0 or not parts:
        parts.append(f"{w:g} วา")
    return " ".join(parts)

@st.cache_data(ttl=86400, show_spinner=False)
def fetch_sam_asset_images(asset_id, asset_link):
    """
    Fetches real property photo URLs for a SAM asset from sam.or.th with caching.
    """
    if not asset_link or pd.isna(asset_link) or str(asset_link).strip() in ['', '#', 'nan', 'None']:
        return []
    try:
        req = urllib.request.Request(
            str(asset_link).strip(), 
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
        )
        with urllib.request.urlopen(req, timeout=4, context=_ssl_ctx) as response:
            html = response.read().decode('utf-8', errors='ignore')
            
            # Match images under site/images/npa/{asset_id}/
            pattern = r'https://(?:npa|www)\.sam\.or\.th/site/images/npa/' + str(asset_id) + r'/[^"\'\s>]+'
            found = re.findall(pattern, html)
            
            # Fallback to og:image if not found
            if not found:
                og_imgs = re.findall(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', html)
                found.extend(og_imgs)
                
            unique_imgs = []
            for img in found:
                clean_img = img.strip().replace(' ', '%20')
                if clean_img not in unique_imgs and any(clean_img.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.webp']):
                    unique_imgs.append(clean_img)
            return unique_imgs
    except Exception:
        return []


# ==============================================================================
# SAME-PROJECT LEAFLET MAP RENDERER
# ==============================================================================
def render_same_project_leaflet_map_html(proj_units, proj_name, is_dark_mode=False):
    """Renders an interactive Leaflet map showing all units in the selected project with company logo pins."""
    if proj_units is None or proj_units.empty:
        return None
        
    valid_units = proj_units[proj_units['ละติจูด'].notna() & proj_units['ลองจิจูด'].notna()].copy()
    if valid_units.empty:
        return None

    # Load logo dictionary with tight crop & centering
    alias_map = {
        'bam': 'bam.png',
        'sam': 'SAM.png',
        'kbank': 'kbank.png',
        'scb': 'scb.png',
        'ktb': 'KTB.png',
        'ghb': 'ghb.png',
        'chayo': 'Chayo555.png',
        'chayo555': 'Chayo555.png',
        'nayoo': 'nayoo.png',
        'baania': 'baania.png',
        'zmyhome': 'zmyhome.png',
        'taladnudbaan': 'taladnudbaan.png',
        'led': 'LED.png'
    }
    companies = ['BAM', 'SAM', 'KBANK', 'SCB', 'KTB', 'GHB', 'GSB', 'Chayo555', 'NaYoo', 'Baania', 'ZmyHome', 'Taladnudbaan', 'LED']
    logo_dict = {}
    for c in companies:
        comp_key = c.lower()
        fname = alias_map.get(comp_key, f"{comp_key}.png")
        p = os.path.join("assets", "logos", fname)
        if os.path.exists(p):
            try:
                im = Image.open(p).convert("RGBA")
                bbox = im.getbbox()
                if bbox:
                    im = im.crop(bbox)
                max_side = max(im.width, im.height)
                square = Image.new("RGBA", (max_side, max_side), (0, 0, 0, 0))
                ox = (max_side - im.width) // 2
                oy = (max_side - im.height) // 2
                square.paste(im, (ox, oy), im)
                square = square.resize((64, 64), Image.Resampling.LANCZOS)
                buf = io.BytesIO()
                square.save(buf, format="PNG", optimize=True)
                b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
                logo_dict[c] = f"data:image/png;base64,{b64}"
                logo_dict[c.lower()] = logo_dict[c]
                logo_dict[c.upper()] = logo_dict[c]
            except Exception:
                pass

    props_list = []
    for _, r in valid_units.iterrows():
        try:
            lat = float(r['ละติจูด'])
            lon = float(r['ลองจิจูด'])
            if math.isnan(lat) or math.isnan(lon) or (lat == 0 and lon == 0):
                continue
            
            p_val = float(r.get('ราคา', 0))
            p_str = f"฿{p_val:,.0f}" if p_val > 0 else "ไม่ระบุราคา"
            
            land_w = r.get('พื้นที่_ตารางวา')
            land_str = f"{float(land_w):,.1f} ตร.ว." if pd.notna(land_w) and float(land_w) > 0 else "-"
            
            use_m = r.get('พื้นที่ใช้สอย (ตร.ม.)')
            use_str = f"{float(use_m):,.1f} ตร.ม." if pd.notna(use_m) and float(use_m) > 0 else "-"
            
            props_list.append({
                "lat": lat,
                "lon": lon,
                "company": str(r.get('บริษัท', 'SAM')),
                "code": str(r.get('รหัสทรัพย์', '-')),
                "name": str(r.get('ชื่อประกาศ', proj_name)),
                "type": str(r.get('ประเภททรัพย์', '-')),
                "price": p_str,
                "land_area": land_str,
                "usable_area": use_str,
                "link": str(r.get('ลิงก์', '')),
                "subdist": str(r.get('ตำบล', '')),
                "district": str(r.get('อำเภอ', '')),
                "province": str(r.get('จังหวัด', ''))
            })
        except Exception:
            continue

    if not props_list:
        return None

    # Deduplicate exact same coordinates for markers to prevent overlap lag
    seen_coords = set()
    deduped_props = []
    for item in props_list:
        coord_key = (item.get("lat"), item.get("lon"))
        if coord_key not in seen_coords:
            seen_coords.add(coord_key)
            deduped_props.append(item)

    tiles_url = "https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png" if not is_dark_mode else "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
    props_json = json.dumps(deduped_props, ensure_ascii=False)
    logos_json = json.dumps(logo_dict, ensure_ascii=False)
    proj_title_escaped = str(proj_name).replace("'", "\\'")

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
        <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
        <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;600;700;800&family=Sarabun:wght@400;500;600;700&display=swap" rel="stylesheet">
        <style>
            html, body, #same-proj-map {{
                height: 100%;
                width: 100%;
                margin: 0;
                padding: 0;
                font-family: 'Sarabun', 'Outfit', -apple-system, BlinkMacSystemFont, sans-serif;
                background: {'#0f172a' if is_dark_mode else '#f8fafc'};
                border-radius: 12px;
                overflow: hidden;
            }}
            .logo-marker-pin {{
                display: flex;
                justify-content: center;
                align-items: center;
                width: 34px;
                height: 34px;
                background: #ffffff;
                border-radius: 50%;
                border: 2px solid #ffffff;
                box-shadow: 0 3px 10px rgba(0, 0, 0, 0.25);
                transition: transform 0.2s ease, box-shadow 0.2s ease;
                cursor: pointer;
                overflow: hidden;
                box-sizing: border-box;
                padding: 0;
            }}
            .logo-marker-pin:hover {{
                transform: scale(1.3);
                box-shadow: 0 6px 20px rgba(0, 0, 0, 0.4);
                z-index: 1000 !important;
            }}
            .logo-marker-pin img {{
                width: 18px;
                height: 18px;
                max-width: 18px;
                max-height: 18px;
                object-fit: contain;
                display: block;
                margin: 0 auto;
                transform: translateY(-1px);
            }}
            .leaflet-popup-content-wrapper {{
                background: {'#1e293b' if is_dark_mode else '#ffffff'} !important;
                color: {'#f8fafc' if is_dark_mode else '#0f172a'} !important;
                border-radius: 12px !important;
                box-shadow: 0 10px 25px rgba(0,0,0,0.3) !important;
                border: 1px solid {'rgba(255,255,255,0.1)' if is_dark_mode else 'rgba(0,0,0,0.08)'} !important;
                padding: 4px !important;
            }}
            .leaflet-popup-tip {{
                background: {'#1e293b' if is_dark_mode else '#ffffff'} !important;
            }}
            .leaflet-tooltip {{
                background: {'rgba(15, 23, 42, 0.92)' if is_dark_mode else 'rgba(255, 255, 255, 0.95)'} !important;
                color: {'#f8fafc' if is_dark_mode else '#0f172a'} !important;
                border: 1px solid {'rgba(255,255,255,0.15)' if is_dark_mode else 'rgba(0,0,0,0.1)'} !important;
                border-radius: 8px !important;
                box-shadow: 0 4px 15px rgba(0,0,0,0.2) !important;
                font-family: 'Sarabun', sans-serif !important;
                padding: 6px 10px !important;
            }}
        </style>
    </head>
    <body>
        <div id="same-proj-map"></div>
        <script>
            var map = L.map('same-proj-map', {{
                zoomControl: true,
                attributionControl: false
            }});

            L.tileLayer('{tiles_url}', {{
                maxZoom: 19,
                subdomains: 'abcd'
            }}).addTo(map);

            var properties = {props_json};
            var logos = {logos_json};
            var markers = [];

            properties.forEach(function(p) {{
                if (!p.lat || !p.lon) return;
                var comp = p.company || 'SAM';
                var logoUrl = logos[comp] || logos[comp.toLowerCase()] || '';
                
                var logoHtml = logoUrl ? '<img src="' + logoUrl + '" alt="' + comp + '" />' : '<span style="font-weight:800; font-size:11px; color:#0f172a;">' + comp.substring(0,3) + '</span>';
                
                var customIcon = L.divIcon({{
                    className: 'custom-logo-icon',
                    html: '<div class="logo-marker-pin">' + logoHtml + '</div>',
                    iconSize: [34, 34],
                    iconAnchor: [17, 17],
                    popupAnchor: [0, -17]
                }});

                var locStr = [p.subdist, p.district, p.province].filter(Boolean).join(', ');

                var popupContent = '<div style="font-size: 13px; padding: 2px; min-width: 230px;">' +
                    '<div style="font-weight: 800; font-size: 14px; color: #38bdf8; margin-bottom: 4px;">🏢 {proj_title_escaped}</div>' +
                    '<div style="color: #94a3b8; font-size: 11.5px; margin-bottom: 6px;">🔑 รหัสทรัพย์: <b style="color: #ffffff;">' + (p.code || '-') + '</b></div>' +
                    '<div style="display:flex; gap:8px; flex-wrap:wrap; margin-bottom:5px;">' +
                    '  <span style="background:rgba(167,139,250,0.15); color:#a78bfa; padding:2px 6px; border-radius:4px; font-size:11px; font-weight:600;">🏢 ' + comp + '</span>' +
                    '  <span style="background:rgba(252,211,77,0.15); color:#fcd34d; padding:2px 6px; border-radius:4px; font-size:11px; font-weight:600;">🏠 ' + (p.type || '-') + '</span>' +
                    '</div>' +
                    '<div style="background: rgba(16, 185, 129, 0.1); border: 1px solid rgba(16, 185, 129, 0.25); border-radius: 6px; padding: 5px 8px; margin-bottom: 6px;">' +
                    '  <span style="font-size:10px; color:#a7f3d0;">ราคาเสนอขาย</span><br/><b style="font-size:14px; color:#34d399;">' + p.price + '</b>' +
                    '</div>' +
                    '<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 3px 8px; font-size: 11px; color:#cbd5e1; margin-bottom: 5px;">' +
                    '   <div>📐 เนื้อที่: <b>' + (p.land_area || '-') + '</b></div>' +
                    '   <div>🏢 ใช้สอย: <b>' + (p.usable_area || '-') + '</b></div>' +
                    '</div>' +
                    (locStr ? '<div style="font-size: 11px; color: #94a3b8; margin-bottom: 5px;">📍 <span style="color: #e2e8f0;">' + locStr + '</span></div>' : '') +
                    (p.link && p.link !== '-' && p.link !== '' ? '<div style="margin-top: 4px; text-align: right;"><a href="' + p.link + '" target="_blank" style="display: inline-block; background: #3b82f6; color: white; padding: 3px 8px; border-radius: 6px; text-decoration: none; font-size: 11px; font-weight: 600;">🔗 ดูประกาศ ↗</a></div>' : '') +
                    '</div>';

                var tooltipContent = '<div style="font-size:12px; line-height:1.4;">' +
                    '<b style="color:#38bdf8;">🏢 {proj_title_escaped}</b><br/>' +
                    '🔑 [' + comp + '] ' + (p.code || '-') + ' | 🏠 ' + (p.type || '-') + '<br/>' +
                    '💰 <b style="color:#34d399;">' + p.price + '</b>' +
                    (locStr ? '<br/><span style="color:#94a3b8;">📍 ' + locStr + '</span>' : '') +
                    '</div>';

                var marker = L.marker([p.lat, p.lon], {{ icon: customIcon }}).addTo(map);
                marker.bindPopup(popupContent);
                marker.bindTooltip(tooltipContent, {{ direction: 'top', offset: [0, -17] }});
                markers.push(marker);
            }});

            if (markers.length > 0) {{
                var group = new L.featureGroup(markers);
                map.fitBounds(group.getBounds(), {{ padding: [40, 40], maxZoom: 16 }});
            }} else {{
                map.setView([13.7563, 100.5018], 10);
            }}
        </script>
    </body>
    </html>
    """
    return html


# ==============================================================================
# SAME-PROJECT COMPARISON RENDERER (SHARED FUNCTION)
# ==============================================================================
def render_same_project_comparison(df_all_source, is_dark_mode=False, plotly_template="plotly_white", style_plotly_fig=None, default_company_filter=None, key_prefix="same_proj"):
    """
    Renders a comprehensive Same-Project Comparison module.
    Allows comparing all units within a specific project across SAM or all companies.
    """
    if df_all_source is None or df_all_source.empty:
        st.warning("⚠️ ไม่มีข้อมูลสำหรับการเปรียบเทียบในโครงการ")
        return

    st.markdown("### 🏘️ เปรียบเทียบทรัพย์ในโครงการเดียวกัน (Same-Project Comparison)")
    st.write("ค้นหาและเปรียบเทียบยูนิตทั้งหมดที่ตั้งอยู่ในโครงการ/หมู่บ้าน/คอนโดเดียวกัน ทั้งราคา ขนาด และความคุ้มค่าเทียบระหว่างสถาบัน")

    # Clean projects
    df_p = df_all_source[df_all_source['ชื่อโครงการ'].notna()].copy()
    df_p['proj_clean'] = df_p['ชื่อโครงการ'].astype(str).str.strip()
    df_p = df_p[~df_p['proj_clean'].isin(['', 'nan', 'None', '-', 'ไม่มีชื่อ', 'ทรัพย์สิน NPA', '#NAME?'])]

    if default_company_filter:
        df_p_filtered_comp = df_p[df_p['บริษัท'] == default_company_filter]
        valid_proj_list = df_p_filtered_comp['proj_clean'].unique().tolist()
        df_p = df_p[df_p['proj_clean'].isin(valid_proj_list)]

    if df_p.empty:
        st.warning("⚠️ ไม่พบข้อมูลโครงการที่มีชื่อระบุชัดเจน")
        return

    # Filter Bar for selecting project
    col_f1, col_f2, col_f3 = st.columns([0.3, 0.3, 0.4])
    
    with col_f1:
        prov_list = ["ทั้งหมด (ทุกจังหวัด)"] + sorted(df_p['จังหวัด'].dropna().unique().tolist())
        sel_prov = st.selectbox("กรองตามจังหวัด:", options=prov_list, index=0, key=f"{key_prefix}_sel_prov")
        
    with col_f2:
        type_list = ["ทั้งหมด (ทุกประเภท)"] + sorted(df_p['ประเภททรัพย์'].dropna().unique().tolist())
        sel_type = st.selectbox("กรองตามประเภททรัพย์:", options=type_list, index=0, key=f"{key_prefix}_sel_type")

    # Apply filters to find available projects
    df_avail = df_p.copy()
    if sel_prov != "ทั้งหมด (ทุกจังหวัด)":
        df_avail = df_avail[df_avail['จังหวัด'] == sel_prov]
    if sel_type != "ทั้งหมด (ทุกประเภท)":
        df_avail = df_avail[df_avail['ประเภททรัพย์'] == sel_type]

    # Group projects with count and company info
    proj_counts = df_avail.groupby('proj_clean').agg(
        count=('ID', 'count'),
        companies=('บริษัท', lambda x: ', '.join(sorted(x.unique()))),
        province=('จังหวัด', 'first')
    ).sort_values('count', ascending=False)

    if proj_counts.empty:
        st.info("💡 ไม่พบโครงการที่ตรงกับเงื่อนไขจังหวัดหรือประเภททรัพย์ที่เลือก")
        return

    # Build options formatted nicely
    proj_options = proj_counts.index.tolist()
    proj_labels = {
        p: f"{p} ({proj_counts.loc[p, 'count']} ยูนิต - [{proj_counts.loc[p, 'companies']}] - จ.{proj_counts.loc[p, 'province']})"
        for p in proj_options
    }

    with col_f3:
        selected_proj = st.selectbox(
            "🏢 เลือกโครงการที่ต้องการเปรียบเทียบ:",
            options=proj_options,
            format_func=lambda x: proj_labels.get(x, x),
            index=0,
            key=f"{key_prefix}_selected_proj"
        )

    if not selected_proj:
        st.info("กรุณาเลือกโครงการด้านบน")
        return

    # Get all units in the selected project from the full dataset
    proj_units = df_all_source[df_all_source['ชื่อโครงการ'].astype(str).str.strip() == selected_proj].copy()
    
    if proj_units.empty:
        st.warning(f"⚠️ ไม่พบข้อมูลยูนิตในโครงการ '{selected_proj}'")
        return

    # Ensure price numeric
    proj_units['ราคา'] = pd.to_numeric(proj_units['ราคา'], errors='coerce')
    if 'พื้นที่_ตารางวา' in proj_units.columns:
        proj_units['พื้นที่_ตารางวา'] = pd.to_numeric(proj_units['พื้นที่_ตารางวา'], errors='coerce')
    if 'ราคาต่อตารางวา' not in proj_units.columns:
        if 'พื้นที่_ตารางวา' in proj_units.columns:
            proj_units['ราคาต่อตารางวา'] = np.where(
                (proj_units['พื้นที่_ตารางวา'] > 0) & (proj_units['ราคา'] > 0), 
                proj_units['ราคา'] / proj_units['พื้นที่_ตารางวา'], 
                np.nan
            )
        else:
            proj_units['ราคาต่อตารางวา'] = np.nan

    if 'พื้นที่ใช้สอย (ตร.ม.)' in proj_units.columns:
        proj_units['พื้นที่ใช้สอย (ตร.ม.)'] = pd.to_numeric(proj_units['พื้นที่ใช้สอย (ตร.ม.)'], errors='coerce')
    elif 'พื้นที่ใช้สอย' in proj_units.columns:
        proj_units['พื้นที่ใช้สอย (ตร.ม.)'] = pd.to_numeric(proj_units['พื้นที่ใช้สอย'], errors='coerce')

    if 'ราคาต่อตารางเมตร' not in proj_units.columns:
        if 'พื้นที่ใช้สอย (ตร.ม.)' in proj_units.columns:
            proj_units['ราคาต่อตารางเมตร'] = np.where(
                (proj_units['พื้นที่ใช้สอย (ตร.ม.)'] > 0) & (proj_units['ราคา'] > 0),
                proj_units['ราคา'] / proj_units['พื้นที่ใช้สอย (ตร.ม.)'],
                np.nan
            )
        else:
            proj_units['ราคาต่อตารางเมตร'] = np.nan

    valid_prices = proj_units['ราคา'].dropna()
    valid_prices = valid_prices[valid_prices > 0]
    
    n_units = len(proj_units)
    companies_present = sorted(proj_units['บริษัท'].dropna().unique().tolist())
    location_str = f"{proj_units['ตำบล'].dropna().iloc[0] if not proj_units['ตำบล'].dropna().empty else ''} {proj_units['อำเภอ'].dropna().iloc[0] if not proj_units['อำเภอ'].dropna().empty else ''} จ.{proj_units['จังหวัด'].dropna().iloc[0] if not proj_units['จังหวัด'].dropna().empty else ''}".strip()

    min_p = valid_prices.min() if not valid_prices.empty else 0
    med_p = valid_prices.median() if not valid_prices.empty else 0
    mean_p = valid_prices.mean() if not valid_prices.empty else 0
    max_p = valid_prices.max() if not valid_prices.empty else 0

    best_deal_unit = proj_units.loc[proj_units['ราคา'] == min_p].iloc[0] if not valid_prices.empty else None

    # Project Header Info Card
    st.markdown(f"""
    <div style="background: {'#1e293b' if is_dark_mode else '#f0fdf4'}; border: 1px solid {'#334155' if is_dark_mode else '#bbf7d0'}; border-radius: 14px; padding: 16px 20px; margin-top: 10px; margin-bottom: 18px;">
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px;">
            <div>
                <h3 style="margin: 0; color: {'#34d399' if is_dark_mode else '#15803d'}; font-size: 1.35rem; font-weight: 800;">
                    🏢 โครงการ: {selected_proj}
                </h3>
                <div style="color: {'#94a3b8' if is_dark_mode else '#475569'}; font-size: 0.85rem; margin-top: 3px;">
                    📍 ทำเล: <b>{location_str}</b> | พบทั้งหมด <b>{n_units:,}</b> ยูนิต จาก <b>{len(companies_present)}</b> สถาบัน ({', '.join(companies_present)})
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Metric Cards
    best_co = str(best_deal_unit['บริษัท']) if best_deal_unit is not None else "-"
    best_code = str(best_deal_unit['รหัสทรัพย์']) if best_deal_unit is not None else "-"
    
    st.markdown(f"""
    <div class="floating-kpi-container" style="margin-bottom: 20px;">
        <div class="floating-card">
            <div class="floating-card-title"><i class="fa fa-tag" style="color: #10b981;"></i> ราคาเริ่มต้นต่ำสุด (Best Entry)</div>
            <div class="floating-card-value">{format_price_short(min_p)}</div>
            <div class="floating-card-sub">โดย [{best_co}] รหัส: {best_code}</div>
        </div>
        <div class="floating-card">
            <div class="floating-card-title"><i class="fa fa-calculator" style="color: #3b82f6;"></i> ราคากลางโครงการ (Median)</div>
            <div class="floating-card-value">{format_price_short(med_p)}</div>
            <div class="floating-card-sub">ค่าเฉลี่ย: {format_price_short(mean_p)}</div>
        </div>
        <div class="floating-card">
            <div class="floating-card-title"><i class="fa fa-arrow-up-right-dots" style="color: #f59e0b;"></i> ราคาสูงสุดในโครงการ</div>
            <div class="floating-card-value">{format_price_short(max_p)}</div>
            <div class="floating-card-sub">ส่วนต่าง Max-Min: {format_price_short(max_p - min_p)}</div>
        </div>
        <div class="floating-card">
            <div class="floating-card-title"><i class="fa fa-building" style="color: #8b5cf6;"></i> สถาบันที่พบ</div>
            <div class="floating-card-value">{len(companies_present)} แห่ง</div>
            <div class="floating-card-sub">{', '.join(companies_present[:3])}</div>
        </div>
        <div class="floating-card">
            <div class="floating-card-title"><i class="fa fa-layer-group" style="color: #06b6d4;"></i> จำนวนยูนิตทั้งหมด</div>
            <div class="floating-card-value">{n_units:,}</div>
            <div class="floating-card-sub">พร้อมเปรียบเทียบทุกยูนิต</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Visual Charts
    c_chart1, c_chart2 = st.columns([0.55, 0.45])
    
    with c_chart1:
        proj_sorted = proj_units.sort_values('ราคา', ascending=True).copy()
        proj_sorted['label'] = proj_sorted.apply(
            lambda r: f"[{r['บริษัท']}] {str(r.get('รหัสทรัพย์', ''))[:10]}", axis=1
        )
        proj_sorted['price_million'] = proj_sorted['ราคา'] / 1e6
        
        fig_bar = px.bar(
            proj_sorted,
            x='label',
            y='price_million',
            color='บริษัท',
            title=f'📊 ราคาขายรายยูนิตในโครงการ {selected_proj} (เรียงจากถูกไปแพง)',
            color_discrete_map=COMPANY_COLORS,
            template=plotly_template
        )
        fig_bar.add_hline(
            y=med_p / 1e6, 
            line_dash="dash", 
            line_color="#f59e0b",
            annotation_text=f"ราคากลาง ฿{med_p/1e6:,.2f}M", 
            annotation_position="top right"
        )
        fig_bar.update_layout(
            height=400,
            xaxis_title="ยูนิตในโครงการ",
            yaxis_title="ราคาขาย (ล้านบาท)",
            margin=dict(t=40, b=10, l=10, r=10)
        )
        if style_plotly_fig:
            fig_bar = style_plotly_fig(fig_bar)
        st.plotly_chart(fig_bar, use_container_width=True, key=f"{key_prefix}_bar_chart")
        
    with c_chart2:
        if len(companies_present) > 1:
            co_counts = proj_units['บริษัท'].value_counts().reset_index()
            co_counts.columns = ['บริษัท', 'count']
            fig_co_pie = px.pie(
                co_counts,
                names='บริษัท',
                values='count',
                hole=0.45,
                title=f'🥧 สัดส่วนยูนิตแยกตามบริษัทใน {selected_proj}',
                color='บริษัท',
                color_discrete_map=COMPANY_COLORS,
                template=plotly_template
            )
            fig_co_pie.update_traces(textposition='inside', textinfo='percent+label')
            fig_co_pie.update_layout(height=400, margin=dict(t=40, b=10, l=10, r=10))
            if style_plotly_fig:
                fig_co_pie = style_plotly_fig(fig_co_pie)
            st.plotly_chart(fig_co_pie, use_container_width=True, key=f"{key_prefix}_co_pie")
        else:
            scatter_data = proj_units[(proj_units['พื้นที่_ตารางวา'] > 0) & (proj_units['ราคา'] > 0)].copy()
            if not scatter_data.empty:
                fig_scat = px.scatter(
                    scatter_data,
                    x='พื้นที่_ตารางวา',
                    y='ราคา',
                    color='ประเภททรัพย์',
                    hover_data=['รหัสทรัพย์', 'บริษัท'],
                    title=f'📐 ความสัมพันธ์ระหว่างขนาดที่ดิน (ตร.ว.) กับราคาขาย',
                    template=plotly_template
                )
                fig_scat.update_layout(height=400, margin=dict(t=40, b=10, l=10, r=10))
                if style_plotly_fig:
                    fig_scat = style_plotly_fig(fig_scat)
                st.plotly_chart(fig_scat, use_container_width=True, key=f"{key_prefix}_scatter_chart")
    # Map Section
    st.markdown("---")
    st.markdown(f"##### 🗺️ แผนที่พิกัดที่ตั้งโครงการและยูนิต ({selected_proj})")
    same_proj_map_html = render_same_project_leaflet_map_html(proj_units, selected_proj, is_dark_mode=is_dark_mode)
    if same_proj_map_html:
        st.components.v1.html(same_proj_map_html, height=480, scrolling=False)
    else:
        st.info("💡 ไม่พบข้อมูลพิกัดละติจูด/ลองจิจูดสำหรับแสดงแผนที่ของโครงการนี้")

    # Detailed Unit Table
    st.markdown("##### 📋 ตารางเปรียบเทียบรายละเอียดทุกยูนิตในโครงการ")
    
    table_units = proj_units.sort_values('ราคา', ascending=True).copy()
    table_units['ขนาดที่ดิน'] = table_units['พื้นที่_ตารางวา'].apply(format_rai_ngan_wah)
    table_units['ราคาขาย (บาท)'] = table_units['ราคา']
    
    if med_p > 0:
        table_units['เทียบราคากลาง (%)'] = table_units['ราคา'].apply(
            lambda p: f"{(p - med_p) / med_p * 100:+.1f}%" if pd.notna(p) and p > 0 else "-"
        )
    else:
        table_units['เทียบราคากลาง (%)'] = "-"

    cols_show = [
        'บริษัท', 'รหัสทรัพย์', 'ประเภททรัพย์', 'ราคาขาย (บาท)', 'เทียบราคากลาง (%)',
        'ขนาดที่ดิน', 'พื้นที่ใช้สอย (ตร.ม.)', 'ราคาต่อตารางวา', 'ราคาต่อตารางเมตร', 'ตำบล', 'อำเภอ', 'ลิงก์'
    ]
    cols_exist = [c for c in cols_show if c in table_units.columns]
    
    st.dataframe(
        table_units[cols_exist],
        use_container_width=True,
        column_config={
            "ราคาขาย (บาท)": st.column_config.NumberColumn("ราคาขาย (บาท)", format="฿%,d"),
            "ราคาต่อตารางวา": st.column_config.NumberColumn("ราคา/ตร.ว. (บาท)", format="฿%,d"),
            "ราคาต่อตารางเมตร": st.column_config.NumberColumn("ราคา/ตร.ม. (บาท)", format="฿%,d"),
            "พื้นที่ใช้สอย (ตร.ม.)": st.column_config.NumberColumn(format="%.1f"),
            "ลิงก์": st.column_config.LinkColumn("เปิดดูทรัพย์", display_text="🔗 ดูรายละเอียด")
        },
        height=380,
        key=f"{key_prefix}_units_table"
    )

    # Export Section
    c_exp1, c_exp2 = st.columns(2)
    with c_exp1:
        csv_proj = table_units.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            label=f"📄 ดาวน์โหลด CSV โครงการนี้ ({len(table_units):,} ยูนิต) ⚡",
            data=csv_proj,
            file_name=f"Project_Comparison_{selected_proj}_{pd.Timestamp.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            use_container_width=True,
            key=f"{key_prefix}_btn_csv"
        )
    with c_exp2:
        excel_buf = io.BytesIO()
        with pd.ExcelWriter(excel_buf, engine='openpyxl') as writer:
            table_units.to_excel(writer, index=False, sheet_name='Units')
        st.download_button(
            label=f"📊 ดาวน์โหลด Excel โครงการนี้ (.xlsx)",
            data=excel_buf.getvalue(),
            file_name=f"Project_Comparison_{selected_proj}_{pd.Timestamp.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            key=f"{key_prefix}_btn_excel"
        )


# ==============================================================================
# SINGLE SAM ASSET INSPECTOR & COMPARATIVE BENCHMARKS (WITH PHOTO GALLERY)
# ==============================================================================
def render_single_sam_asset_inspector(sam_all, df_raw, is_dark_mode=False, plotly_template="plotly_white", style_plotly_fig=None):
    """
    Detailed single SAM asset inspector with real property photo gallery,
    complete specs, district/province/market benchmarks, and nearby comps.
    """
    st.markdown("#### 🔎 เจาะลึกทรัพย์ SAM รายชิ้น & เปรียบเทียบตลาด (SAM Single Asset Deep Dive)")
    st.caption("เลือกรหัสทรัพย์ SAM เพื่อตรวจสอบข้อมูลเชิงลึกแบบ 360 องศา พร้อมรูปภาพจริงจาก SAM เทียบราคากลาง และค้นหาทรัพย์คู่แข่งโดยรอบ")

    # Filter Bar to find the asset
    f1, f2, f3 = st.columns([0.25, 0.25, 0.5])
    
    with f1:
        all_provs = ["ทั้งหมด (ทุกจังหวัด)"] + sorted(sam_all['จังหวัด'].dropna().unique().tolist())
        insp_prov = st.selectbox("กรองตามจังหวัด:", options=all_provs, index=0, key="insp_filter_prov")
        
    with f2:
        all_types = ["ทั้งหมด (ทุกประเภท)"] + sorted(sam_all['ประเภททรัพย์'].dropna().unique().tolist())
        insp_type = st.selectbox("กรองตามประเภททรัพย์:", options=all_types, index=0, key="insp_filter_type")

    sam_searchable = sam_all.copy()
    if insp_prov != "ทั้งหมด (ทุกจังหวัด)":
        sam_searchable = sam_searchable[sam_searchable['จังหวัด'] == insp_prov]
    if insp_type != "ทั้งหมด (ทุกประเภท)":
        sam_searchable = sam_searchable[sam_searchable['ประเภททรัพย์'] == insp_type]

    # Keyword search for asset code or project
    with f3:
        search_kw = st.text_input(
            "🔍 ค้นหารหัสทรัพย์ หรือชื่อโครงการ/ทำเล:",
            value="",
            placeholder="เช่น 3A1291, 4T0641, กฤษดานคร, ดอนเมือง...",
            key="insp_search_kw"
        )
        if search_kw:
            q = search_kw.strip().lower()
            m_code = sam_searchable['รหัสทรัพย์'].astype(str).str.lower().str.contains(q, na=False)
            m_proj = sam_searchable['ชื่อโครงการ'].astype(str).str.lower().str.contains(q, na=False)
            m_title = sam_searchable['ชื่อประกาศ'].astype(str).str.lower().str.contains(q, na=False)
            m_dist = sam_searchable['อำเภอ'].astype(str).str.lower().str.contains(q, na=False)
            sam_searchable = sam_searchable[m_code | m_proj | m_title | m_dist]

    if sam_searchable.empty:
        st.warning("⚠️ ไม่พบรายการทรัพย์สิน SAM ตามเงื่อนไขการค้นหา")
        return

    # Create clean, distinct labels for dropdown
    def _make_sam_dropdown_label(r):
        code = str(r.get('รหัสทรัพย์') or '').strip() or '-'
        ptype = str(r.get('ประเภททรัพย์') or '').strip()
        proj = str(r.get('ชื่อโครงการ') or '').strip()
        if proj.lower() in ['nan', 'none', 'null', '-', '']:
            proj = ''
        
        # Price formatting
        price_val = pd.to_numeric(r.get('ราคา'), errors='coerce')
        sale_type = str(r.get('ประเภทการขาย') or '').strip()
        if pd.isna(price_val) or price_val <= 0:
            price_str = "รอประกาศราคา" if 'รอประกาศราคา' in sale_type else "ไม่ระบุราคา"
        else:
            price_str = format_price_short(price_val)
            
        dist = str(r.get('อำเภอ') or '').strip()
        if dist.lower() in ['nan', 'none', 'null', '-', '']:
            dist = ''
        prov = str(r.get('จังหวัด') or '').strip()
        if prov.lower() in ['nan', 'none', 'null', '-', '']:
            prov = ''
            
        loc_str = f" (อ.{dist}, จ.{prov})" if dist and prov else (f" (จ.{prov})" if prov else "")
        
        if proj:
            return f"[{code}] {ptype} - {proj} - {price_str}{loc_str}"
        else:
            return f"[{code}] {ptype} - {price_str}{loc_str}"

    sam_searchable['dropdown_label'] = sam_searchable.apply(_make_sam_dropdown_label, axis=1)

    # Sort so active priced properties appear first, then sorted by price/code
    sam_searchable['is_priced'] = pd.to_numeric(sam_searchable['ราคา'], errors='coerce').fillna(0) > 0
    sam_searchable = sam_searchable.sort_values(by=['is_priced', 'รหัสทรัพย์'], ascending=[False, True])

    options_list = sam_searchable['รหัสทรัพย์'].tolist()
    labels_dict = dict(zip(sam_searchable['รหัสทรัพย์'], sam_searchable['dropdown_label']))

    selected_code = st.selectbox(
        "🏛️ เลือกทรัพย์สิน SAM ที่ต้องการเจาะลึก:",
        options=options_list,
        format_func=lambda x: labels_dict.get(x, str(x)),
        index=0,
        key="insp_selected_sam_code"
    )

    if not selected_code:
        return

    asset_row = sam_all[sam_all['รหัสทรัพย์'] == selected_code].iloc[0]
    
    # -------------------------------------------------------------------------
    # 1. ASSET PROFILE HEADER & SPECIFICATIONS
    # -------------------------------------------------------------------------
    asset_id = str(asset_row.get('ID', '-'))
    asset_code = str(asset_row.get('รหัสทรัพย์', '-'))
    raw_proj = str(asset_row.get('ชื่อโครงการ', '')).strip()
    raw_title = str(asset_row.get('ชื่อประกาศ', '')).strip()
    if raw_proj.lower() in ['nan', 'none', 'null', '-', '']:
        raw_proj = ''
    if raw_title.lower() in ['nan', 'none', 'null', '-', 'sam']:
        raw_title = ''
    asset_name = raw_proj or raw_title or f"ทรัพย์สิน SAM ({asset_code})"
    asset_type = str(asset_row.get('ประเภททรัพย์', '-'))
    asset_sale = str(asset_row.get('ประเภทการขาย', 'ขาย'))
    asset_price = float(asset_row.get('ราคา', 0)) if pd.notna(asset_row.get('ราคา')) else 0
    asset_sqw = float(asset_row.get('พื้นที่_ตารางวา', 0)) if pd.notna(asset_row.get('พื้นที่_ตารางวา')) else 0
    asset_sqm = float(asset_row.get('พื้นที่ใช้สอย (ตร.ม.)', 0)) if pd.notna(asset_row.get('พื้นที่ใช้สอย (ตร.ม.)')) else 0
    asset_prov = str(asset_row.get('จังหวัด', '-'))
    asset_dist = str(asset_row.get('อำเภอ', '-'))
    asset_subdist = str(asset_row.get('ตำบล', '-'))
    asset_link = str(asset_row.get('ลิงก์', ''))
    asset_lat = float(asset_row.get('ละติจูด', 0)) if pd.notna(asset_row.get('ละติจูด')) else None
    asset_lng = float(asset_row.get('ลองจิจูด', 0)) if pd.notna(asset_row.get('ลองจิจูด')) else None

    price_sqw = asset_price / asset_sqw if asset_sqw > 0 and asset_price > 0 else 0
    price_sqm = asset_price / asset_sqm if asset_sqm > 0 and asset_price > 0 else 0

    gmap_url = f"https://www.google.com/maps/search/?api=1&query={asset_lat},{asset_lng}" if asset_lat and asset_lng else "#"

    # Status tag color
    if "ประมูล" in asset_sale:
        sale_badge_color = "#f59e0b"
        sale_badge_text = "🔨 ทรัพย์ประมูล (Auction)"
    elif "รอประกาศราคา" in asset_sale or asset_price <= 0:
        sale_badge_color = "#94a3b8"
        sale_badge_text = "⚪ รอประกาศราคา"
    else:
        sale_badge_color = "#10b981"
        sale_badge_text = "🟢 ขายปกติ (Direct Sale)"

    # Header HTML Card
    header_html = f"""
    <div style="background: {'#1e293b' if is_dark_mode else '#ffffff'}; border: 1px solid {'#334155' if is_dark_mode else '#e2e8f0'}; border-left: 6px solid #10b981; border-radius: 14px; padding: 18px 20px; margin-top: 10px; margin-bottom: 16px; box-shadow: 0 4px 16px rgba(0,0,0,0.06);">
        <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 12px;">
            <div>
                <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 6px;">
                    <span style="background: #10b981; color: white; padding: 3px 10px; border-radius: 6px; font-weight: 800; font-size: 0.85rem;">🏛️ รหัสทรัพย์: {asset_code}</span>
                    <span style="background: {sale_badge_color}22; color: {sale_badge_color}; border: 1px solid {sale_badge_color}; padding: 3px 10px; border-radius: 6px; font-weight: 700; font-size: 0.82rem;">{sale_badge_text}</span>
                    <span style="background: #3b82f622; color: #3b82f6; border: 1px solid #3b82f6; padding: 3px 10px; border-radius: 6px; font-weight: 700; font-size: 0.82rem;">{asset_type}</span>
                </div>
                <h2 style="margin: 0; color: {'#f8fafc' if is_dark_mode else '#0f172a'}; font-size: 1.4rem; font-weight: 800;">
                    {asset_name}
                </h2>
                <p style="margin: 4px 0 0 0; color: {'#94a3b8' if is_dark_mode else '#64748b'}; font-size: 0.88rem;">
                    📍 ทำเล: <b>ต.{asset_subdist} อ.{asset_dist} จ.{asset_prov}</b> {f'| พิกัด GPS: {asset_lat:.5f}, {asset_lng:.5f}' if asset_lat else ''}
                </p>
            </div>
            <div style="display: flex; gap: 8px; flex-wrap: wrap;">
                {f'<a href="{asset_link}" target="_blank" style="background: #10b981; color: white; padding: 8px 16px; border-radius: 8px; text-decoration: none; font-weight: 700; font-size: 0.85rem; display: inline-flex; align-items: center; gap: 6px; box-shadow: 0 2px 8px rgba(16, 185, 129, 0.3);">🔗 เปิดเว็บ SAM</a>' if asset_link and asset_link != '#' else ''}
                {f'<a href="{gmap_url}" target="_blank" style="background: {"#334155" if is_dark_mode else "#f1f5f9"}; color: {"#38bdf8" if is_dark_mode else "#0284c7"}; border: 1px solid {"#475569" if is_dark_mode else "#cbd5e1"}; padding: 8px 16px; border-radius: 8px; text-decoration: none; font-weight: 700; font-size: 0.85rem; display: inline-flex; align-items: center; gap: 6px;">📍 ดูบน Google Maps</a>' if asset_lat else ''}
            </div>
        </div>
    </div>
    """
    st.markdown(header_html, unsafe_allow_html=True)

    # -------------------------------------------------------------------------
    # PHOTO GALLERY & CORE METRICS (2-COLUMN PRESENTATION)
    # -------------------------------------------------------------------------
    col_photo, col_specs = st.columns([0.48, 0.52])
    
    with col_photo:
        st.markdown("##### 📷 ภาพถ่ายทรัพย์สินจริงจาก SAM")
        with st.spinner("กำลังดึงภาพถ่ายทรัพย์สินจาก SAM..."):
            asset_photos = fetch_sam_asset_images(asset_id, asset_link)
        
        if asset_photos:
            st.image(
                asset_photos[0],
                use_container_width=True,
                caption=f"📷 ภาพถ่ายทรัพย์สินจริงจาก SAM (รหัส {asset_code})"
            )
        else:
            # Fallback when no photos found
            st.markdown(f"""
            <div style="background: {'#1e293b' if is_dark_mode else '#f8fafc'}; border: 2px dashed {'#334155' if is_dark_mode else '#cbd5e1'}; border-radius: 12px; padding: 40px 20px; text-align: center; margin-bottom: 10px;">
                <div style="font-size: 2.5rem; margin-bottom: 8px;">🏠</div>
                <div style="font-weight: 700; font-size: 1rem; color: {'#f8fafc' if is_dark_mode else '#1e293b'};">{asset_name}</div>
                <div style="font-size: 0.82rem; color: {'#94a3b8' if is_dark_mode else '#64748b'}; margin-top: 4px;">ประเภท: {asset_type} ({asset_sale})</div>
                <div style="margin-top: 14px;">
                    <a href="{asset_link}" target="_blank" style="background: #10b981; color: white; padding: 6px 14px; border-radius: 6px; text-decoration: none; font-weight: 700; font-size: 0.8rem;">🔗 เปิดดูรูปภาพและโฉนดบนเว็บ SAM</a>
                </div>
            </div>
            """, unsafe_allow_html=True)

    with col_specs:
        st.markdown("##### 🏷️ ข้อมูลราคาและรายละเอียดพื้นที่")
        
        m_row1_c1, m_row1_c2 = st.columns(2)
        with m_row1_c1:
            st.markdown(f"""
            <div class="floating-card" style="padding: 12px;">
                <div class="floating-card-title"><i class="fa fa-tag" style="color: #10b981;"></i> ราคาเสนอขาย</div>
                <div class="floating-card-value" style="font-size: 1.35rem; color: #10b981;">{format_price_short(asset_price)}</div>
                <div class="floating-card-sub">{f'฿{asset_price:,.0f}' if asset_price > 0 else 'รอประกาศ'}</div>
            </div>""", unsafe_allow_html=True)
        with m_row1_c2:
            st.markdown(f"""
            <div class="floating-card" style="padding: 12px;">
                <div class="floating-card-title"><i class="fa fa-vector-square" style="color: #3b82f6;"></i> ขนาดเนื้อที่ดิน</div>
                <div class="floating-card-value" style="font-size: 1.35rem;">{format_rai_ngan_wah(asset_sqw)}</div>
                <div class="floating-card-sub">{f'{asset_sqw:,.1f} ตารางวา' if asset_sqw > 0 else '-'}</div>
            </div>""", unsafe_allow_html=True)

        m_row2_c1, m_row2_c2 = st.columns(2)
        with m_row2_c1:
            st.markdown(f"""
            <div class="floating-card" style="padding: 12px;">
                <div class="floating-card-title"><i class="fa fa-ruler-combined" style="color: #f59e0b;"></i> ราคาเฉลี่ยต่อ ตร.ว.</div>
                <div class="floating-card-value" style="font-size: 1.35rem;">{f'฿{price_sqw:,.0f}' if price_sqw > 0 else '-'}</div>
                <div class="floating-card-sub">บาท / ตารางวา</div>
            </div>""", unsafe_allow_html=True)
        with m_row2_c2:
            st.markdown(f"""
            <div class="floating-card" style="padding: 12px;">
                <div class="floating-card-title"><i class="fa fa-house" style="color: #8b5cf6;"></i> พื้นที่ใช้สอย</div>
                <div class="floating-card-value" style="font-size: 1.35rem;">{f'{asset_sqm:,.1f} ตร.ม.' if asset_sqm > 0 else '-'}</div>
                <div class="floating-card-sub">{f'฿{price_sqm:,.0f}/ตร.ม.' if price_sqm > 0 else 'ไม่ระบุขนาด'}</div>
            </div>""", unsafe_allow_html=True)

        # Specifications details list
        bed_str = str(asset_row.get('ห้องนอน', '-')) if pd.notna(asset_row.get('ห้องนอน')) else '-'
        bath_str = str(asset_row.get('ห้องน้ำ', '-')) if pd.notna(asset_row.get('ห้องน้ำ')) else '-'
        park_str = str(asset_row.get('ที่จอดรถ', '-')) if pd.notna(asset_row.get('ที่จอดรถ')) else '-'
        
        st.markdown(f"""
        <div style="background: {'#1e293b' if is_dark_mode else '#f8fafc'}; border: 1px solid {'#334155' if is_dark_mode else '#e2e8f0'}; border-radius: 10px; padding: 10px 14px; margin-top: 10px; font-size: 0.84rem;">
            <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
                <span style="color: {'#94a3b8' if is_dark_mode else '#64748b'};">🛏️ ห้องนอน / 🚿 ห้องน้ำ:</span>
                <b>{bed_str} ห้องนอน / {bath_str} ห้องน้ำ</b>
            </div>
            <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
                <span style="color: {'#94a3b8' if is_dark_mode else '#64748b'};">🚗 ที่จอดรถ:</span>
                <b>{park_str} คัน</b>
            </div>
            <div style="display: flex; justify-content: space-between;">
                <span style="color: {'#94a3b8' if is_dark_mode else '#64748b'};">📅 วันที่อัปเดตข้อมูล:</span>
                <b>{str(asset_row.get('วันที่ดึงข้อมูล', '-'))}</b>
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br/>", unsafe_allow_html=True)

    # -------------------------------------------------------------------------
    # 2. UNIFIED MARKET & LAND VALUATION BENCHMARKS (Sq.Wah & Sq.M.)
    # -------------------------------------------------------------------------
    st.markdown(f"##### 📊 การเปรียบเทียบราคากลางและสถิติตลาด ({asset_type} & ที่ดินเปล่าในทำเลนี้)")
    st.caption("วิเคราะห์เปรียบเทียบราคาต่อตารางวา (จากเนื้อที่ดิน) และราคาต่อตารางเมตร (จากพื้นที่ใช้สอย) พร้อมเปรียบเทียบราคากลางที่ดินเปล่าในรัศมีรอบทรัพย์")

    # Land Radius Slider Bar
    c_land_slider, c_land_info = st.columns([0.42, 0.58])
    with c_land_slider:
        land_radius_km = st.slider(
            "📍 ปรับระยะรัศมีค้นหาที่ดินรอบทรัพย์นี้ (กิโลเมตร):",
            min_value=1,
            max_value=30,
            value=5,
            step=1,
            key="insp_land_radius_slider"
        )

    # Calculate Nearby Land within Radius
    if asset_lat and asset_lng:
        land_all = df_raw[
            (df_raw['ประเภททรัพย์'] == 'ที่ดินเปล่า') & 
            df_raw['ละติจูด'].notna() & 
            df_raw['ลองจิจูด'].notna() & 
            (df_raw['ราคา'] > 0)
        ].copy()
        
        R = 6371.0 # Earth radius in km
        dlat = np.radians(land_all['ละติจูด'] - asset_lat)
        dlon = np.radians(land_all['ลองจิจูด'] - asset_lng)
        a = np.sin(dlat / 2)**2 + np.cos(np.radians(asset_lat)) * np.cos(np.radians(land_all['ละติจูด'])) * np.sin(dlon / 2)**2
        c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))
        land_all['dist_km'] = R * c
        nearby_land = land_all[land_all['dist_km'] <= land_radius_km].copy()
    else:
        nearby_land = pd.DataFrame()

    nearby_land_cnt = len(nearby_land)
    nearby_land_med_p = nearby_land['ราคา'].median() if not nearby_land.empty else np.nan
    
    if not nearby_land.empty and 'พื้นที่_ตารางวา' in nearby_land.columns:
        nearby_land_sqw_valid = nearby_land[(nearby_land['พื้นที่_ตารางวา'] > 0) & (nearby_land['ราคา'] > 0)]
        nearby_land_med_sqw = (nearby_land_sqw_valid['ราคา'] / nearby_land_sqw_valid['พื้นที่_ตารางวา']).median() if not nearby_land_sqw_valid.empty else np.nan
    else:
        nearby_land_med_sqw = np.nan

    with c_land_info:
        if asset_lat and asset_lng:
            st.info(f"🎯 พบที่ดินเปล่าในรัศมี **{land_radius_km} กม.** ทั้งหมด **{nearby_land_cnt:,} แปลง** (ราคากลาง **{format_price_short(nearby_land_med_p)}** | **฿{nearby_land_med_sqw:,.0f}/ตร.ว.**)" if nearby_land_cnt > 0 else f"💡 ไม่พบแปลงที่ดินเปล่าในรัศมี {land_radius_km} กม. แนะนำให้เพิ่มรัศมีค้นหา")
        else:
            st.warning("⚠️ ทรัพย์สินนี้ไม่มีพิกัด GPS สำหรับค้นหาตามรัศมี ระบบจะอิงราคากลางระดับอำเภอ/จังหวัดแทน")

    # Calculate Property Type Benchmarks (Sq.W. and Sq.M.)
    col_sqm = 'พื้นที่ใช้สอย (ตร.ม.)' if 'พื้นที่ใช้สอย (ตร.ม.)' in df_raw.columns else ('พื้นที่ใช้สอย' if 'พื้นที่ใช้สอย' in df_raw.columns else None)

    # A. District ({asset_dist})
    dist_comps = df_raw[
        (df_raw['จังหวัด'] == asset_prov) & 
        (df_raw['อำเภอ'] == asset_dist) & 
        (df_raw['ประเภททรัพย์'] == asset_type) & 
        (df_raw['ราคา'] > 0)
    ].copy()
    dist_cnt = len(dist_comps)
    dist_med_sqw = (dist_comps[dist_comps['พื้นที่_ตารางวา'] > 0]['ราคา'] / dist_comps[dist_comps['พื้นที่_ตารางวา'] > 0]['พื้นที่_ตารางวา']).median() if not dist_comps.empty and 'พื้นที่_ตารางวา' in dist_comps.columns and (dist_comps['พื้นที่_ตารางวา'] > 0).any() else np.nan
    dist_med_sqm = (dist_comps[dist_comps[col_sqm] > 0]['ราคา'] / dist_comps[dist_comps[col_sqm] > 0][col_sqm]).median() if col_sqm and not dist_comps.empty and (dist_comps[col_sqm] > 0).any() else np.nan

    # B. Province ({asset_prov})
    prov_comps = df_raw[
        (df_raw['จังหวัด'] == asset_prov) & 
        (df_raw['ประเภททรัพย์'] == asset_type) & 
        (df_raw['ราคา'] > 0)
    ].copy()
    prov_cnt = len(prov_comps)
    prov_med_sqw = (prov_comps[prov_comps['พื้นที่_ตารางวา'] > 0]['ราคา'] / prov_comps[prov_comps['พื้นที่_ตารางวา'] > 0]['พื้นที่_ตารางวา']).median() if not prov_comps.empty and 'พื้นที่_ตารางวา' in prov_comps.columns and (prov_comps['พื้นที่_ตารางวา'] > 0).any() else np.nan
    prov_med_sqm = (prov_comps[prov_comps[col_sqm] > 0]['ราคา'] / prov_comps[prov_comps[col_sqm] > 0][col_sqm]).median() if col_sqm and not prov_comps.empty and (prov_comps[col_sqm] > 0).any() else np.nan

    # C. SAM Category ({asset_type})
    sam_cat_comps = sam_all[
        (sam_all['ประเภททรัพย์'] == asset_type) & 
        (sam_all['ราคา'] > 0)
    ].copy()
    sam_cat_cnt = len(sam_cat_comps)
    sam_cat_med_sqw = (sam_cat_comps[sam_cat_comps['พื้นที่_ตารางวา'] > 0]['ราคา'] / sam_cat_comps[sam_cat_comps['พื้นที่_ตารางวา'] > 0]['พื้นที่_ตารางวา']).median() if not sam_cat_comps.empty and 'พื้นที่_ตารางวา' in sam_cat_comps.columns and (sam_cat_comps['พื้นที่_ตารางวา'] > 0).any() else np.nan
    sam_cat_med_sqm = (sam_cat_comps[sam_cat_comps[col_sqm] > 0]['ราคา'] / sam_cat_comps[sam_cat_comps[col_sqm] > 0][col_sqm]).median() if col_sqm and not sam_cat_comps.empty and (sam_cat_comps[col_sqm] > 0).any() else np.nan

    # D. National Market ({asset_type})
    all_cat_comps = df_raw[
        (df_raw['ประเภททรัพย์'] == asset_type) & 
        (df_raw['ราคา'] > 0)
    ].copy()
    all_cat_cnt = len(all_cat_comps)
    all_cat_med_sqw = (all_cat_comps[all_cat_comps['พื้นที่_ตารางวา'] > 0]['ราคา'] / all_cat_comps[all_cat_comps['พื้นที่_ตารางวา'] > 0]['พื้นที่_ตารางวา']).median() if not all_cat_comps.empty and 'พื้นที่_ตารางวา' in all_cat_comps.columns and (all_cat_comps['พื้นที่_ตารางวา'] > 0).any() else np.nan
    all_cat_med_sqm = (all_cat_comps[all_cat_comps[col_sqm] > 0]['ราคา'] / all_cat_comps[all_cat_comps[col_sqm] > 0][col_sqm]).median() if col_sqm and not all_cat_comps.empty and (all_cat_comps[col_sqm] > 0).any() else np.nan

    # District & Province Land Medians
    land_dist_comps = df_raw[
        (df_raw['จังหวัด'] == asset_prov) & 
        (df_raw['อำเภอ'] == asset_dist) & 
        (df_raw['ประเภททรัพย์'] == 'ที่ดินเปล่า') & 
        (df_raw['ราคา'] > 0)
    ].copy()
    land_dist_med_sqw = (land_dist_comps[land_dist_comps['พื้นที่_ตารางวา'] > 0]['ราคา'] / land_dist_comps[land_dist_comps['พื้นที่_ตารางวา'] > 0]['พื้นที่_ตารางวา']).median() if not land_dist_comps.empty and (land_dist_comps['พื้นที่_ตารางวา'] > 0).any() else np.nan

    land_prov_comps = df_raw[
        (df_raw['จังหวัด'] == asset_prov) & 
        (df_raw['ประเภททรัพย์'] == 'ที่ดินเปล่า') & 
        (df_raw['ราคา'] > 0)
    ].copy()
    land_prov_med_sqw = (land_prov_comps[land_prov_comps['พื้นที่_ตารางวา'] > 0]['ราคา'] / land_prov_comps[land_prov_comps['พื้นที่_ตารางวา'] > 0]['พื้นที่_ตารางวา']).median() if not land_prov_comps.empty and (land_prov_comps['พื้นที่_ตารางวา'] > 0).any() else np.nan

    def calc_diff_badge(val, benchmark):
        if pd.isna(val) or pd.isna(benchmark) or benchmark <= 0 or val <= 0:
            return '<span style="color: #94a3b8;">-</span>'
        diff_pct = (val - benchmark) / benchmark * 100
        if diff_pct < -5:
            return f'<span style="color: #10b981; font-weight: 700;">🟢 ถูกกว่า {abs(diff_pct):.1f}%</span>'
        elif diff_pct > 5:
            return f'<span style="color: #ef4444; font-weight: 700;">🔴 สูงกว่า +{diff_pct:.1f}%</span>'
        else:
            return f'<span style="color: #3b82f6; font-weight: 700;">🔵 ใกล้เคียง ({diff_pct:+.1f}%)</span>'

    # Unified KPI Benchmark Cards
    b_col1, b_col2, b_col3, b_col4 = st.columns(4)
    
    with b_col1:
        sqw_card_badge = calc_diff_badge(price_sqw, nearby_land_med_sqw) if price_sqw > 0 else '<span style="color: #94a3b8;">-</span>'
        st.markdown(f"""
        <div style="background: {'#1e293b' if is_dark_mode else '#f0fdf4'}; border: 1px solid {'#334155' if is_dark_mode else '#bbf7d0'}; border-radius: 10px; padding: 14px; text-align: center;">
            <div style="font-size: 0.75rem; color: {'#34d399' if is_dark_mode else '#166534'}; font-weight: 600;">🌾 ราคากลางที่ดินเปล่า (รัศมี {land_radius_km} กม.)</div>
            <div style="font-size: 1.25rem; font-weight: 800; color: {'#34d399' if is_dark_mode else '#15803d'}; margin: 2px 0;">{f'฿{nearby_land_med_sqw:,.0f}/ตร.ว.' if pd.notna(nearby_land_med_sqw) else '-'}</div>
            <div style="font-size: 0.78rem;">{sqw_card_badge}</div>
            <div style="font-size: 0.7rem; color: #94a3b8; margin-top: 2px;">(จาก {nearby_land_cnt:,} แปลงที่ดินรอบทำเล)</div>
        </div>""", unsafe_allow_html=True)

    with b_col2:
        dist_badge = calc_diff_badge(price_sqw, dist_med_sqw) if price_sqw > 0 else (calc_diff_badge(price_sqm, dist_med_sqm) if price_sqm > 0 else '<span style="color: #94a3b8;">-</span>')
        st.markdown(f"""
        <div style="background: {'#1e293b' if is_dark_mode else '#f8fafc'}; border: 1px solid {'#334155' if is_dark_mode else '#e2e8f0'}; border-radius: 10px; padding: 14px; text-align: center;">
            <div style="font-size: 0.75rem; color: {'#94a3b8' if is_dark_mode else '#64748b'}; font-weight: 600;">🏘️ ราคากลาง {asset_type} อ.{asset_dist}</div>
            <div style="font-size: 1.15rem; font-weight: 800; color: {'#f8fafc' if is_dark_mode else '#0f172a'}; margin: 2px 0;">{f'฿{dist_med_sqw:,.0f}/ตร.ว.' if pd.notna(dist_med_sqw) else '-'}</div>
            <div style="font-size: 0.8rem; color: {'#38bdf8' if is_dark_mode else '#0284c7'}; font-weight: 700;">{f'฿{dist_med_sqm:,.0f}/ตร.ม.' if pd.notna(dist_med_sqm) else '-'}</div>
            <div style="font-size: 0.7rem; color: #94a3b8; margin-top: 2px;">{dist_badge} (จาก {dist_cnt:,} ทรัพย์)</div>
        </div>""", unsafe_allow_html=True)

    with b_col3:
        prov_badge = calc_diff_badge(price_sqw, prov_med_sqw) if price_sqw > 0 else (calc_diff_badge(price_sqm, prov_med_sqm) if price_sqm > 0 else '<span style="color: #94a3b8;">-</span>')
        st.markdown(f"""
        <div style="background: {'#1e293b' if is_dark_mode else '#f8fafc'}; border: 1px solid {'#334155' if is_dark_mode else '#e2e8f0'}; border-radius: 10px; padding: 14px; text-align: center;">
            <div style="font-size: 0.75rem; color: {'#94a3b8' if is_dark_mode else '#64748b'}; font-weight: 600;">📍 ราคากลาง {asset_type} จ.{asset_prov}</div>
            <div style="font-size: 1.15rem; font-weight: 800; color: {'#f8fafc' if is_dark_mode else '#0f172a'}; margin: 2px 0;">{f'฿{prov_med_sqw:,.0f}/ตร.ว.' if pd.notna(prov_med_sqw) else '-'}</div>
            <div style="font-size: 0.8rem; color: {'#38bdf8' if is_dark_mode else '#0284c7'}; font-weight: 700;">{f'฿{prov_med_sqm:,.0f}/ตร.ม.' if pd.notna(prov_med_sqm) else '-'}</div>
            <div style="font-size: 0.7rem; color: #94a3b8; margin-top: 2px;">{prov_badge} (จาก {prov_cnt:,} ทรัพย์)</div>
        </div>""", unsafe_allow_html=True)

    with b_col4:
        all_badge = calc_diff_badge(price_sqw, all_cat_med_sqw) if price_sqw > 0 else (calc_diff_badge(price_sqm, all_cat_med_sqm) if price_sqm > 0 else '<span style="color: #94a3b8;">-</span>')
        st.markdown(f"""
        <div style="background: {'#1e293b' if is_dark_mode else '#f8fafc'}; border: 1px solid {'#334155' if is_dark_mode else '#e2e8f0'}; border-radius: 10px; padding: 14px; text-align: center;">
            <div style="font-size: 0.75rem; color: {'#94a3b8' if is_dark_mode else '#64748b'}; font-weight: 600;">🌐 ราคากลางตลาดรวม ({asset_type})</div>
            <div style="font-size: 1.15rem; font-weight: 800; color: {'#f8fafc' if is_dark_mode else '#0f172a'}; margin: 2px 0;">{f'฿{all_cat_med_sqw:,.0f}/ตร.ว.' if pd.notna(all_cat_med_sqw) else '-'}</div>
            <div style="font-size: 0.8rem; color: {'#38bdf8' if is_dark_mode else '#0284c7'}; font-weight: 700;">{f'฿{all_cat_med_sqm:,.0f}/ตร.ม.' if pd.notna(all_cat_med_sqm) else '-'}</div>
            <div style="font-size: 0.7rem; color: #94a3b8; margin-top: 2px;">{all_badge} (จาก {all_cat_cnt:,} ทรัพย์)</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<br/>", unsafe_allow_html=True)

    # Dual Comparison Bar Charts: Sq.W. (Left) & Sq.M. (Right)
    c_chart_sqw, c_chart_sqm = st.columns(2)

    with c_chart_sqw:
        sqw_cats = []
        sqw_vals = []
        sqw_colors = []

        if price_sqw > 0:
            sqw_cats.append(f'🏛️ ทรัพย์ SAM นี้ ({asset_code})')
            sqw_vals.append(price_sqw)
            sqw_colors.append('#10b981')

        if pd.notna(nearby_land_med_sqw):
            sqw_cats.append(f'🌾 ที่ดินเปล่า (รัศมี {land_radius_km} กม.)')
            sqw_vals.append(nearby_land_med_sqw)
            sqw_colors.append('#059669')

        if pd.notna(land_dist_med_sqw):
            sqw_cats.append(f'🏘️ ที่ดินเปล่า อ.{asset_dist}')
            sqw_vals.append(land_dist_med_sqw)
            sqw_colors.append('#0d9488')

        if pd.notna(dist_med_sqw):
            sqw_cats.append(f'🏘️ {asset_type} อ.{asset_dist}')
            sqw_vals.append(dist_med_sqw)
            sqw_colors.append('#3b82f6')

        if pd.notna(prov_med_sqw):
            sqw_cats.append(f'📍 {asset_type} จ.{asset_prov}')
            sqw_vals.append(prov_med_sqw)
            sqw_colors.append('#06b6d4')

        if pd.notna(all_cat_med_sqw):
            sqw_cats.append(f'🌐 {asset_type} ตลาดรวม')
            sqw_vals.append(all_cat_med_sqw)
            sqw_colors.append('#f59e0b')

        if sqw_vals:
            fig_sqw_bench = go.Figure(go.Bar(
                x=sqw_vals,
                y=sqw_cats,
                orientation='h',
                marker_color=sqw_colors,
                text=[f"฿{v:,.0f}/ตร.ว." for v in sqw_vals],
                textposition='auto'
            ))
            fig_sqw_bench.update_layout(
                title=f'📐 ราคาต่อตารางวา (Price/Sq.Wah - จากเนื้อที่ดิน)',
                xaxis_title="บาท / ตร.ว.",
                height=320,
                margin=dict(t=40, b=10, l=10, r=10),
                template=plotly_template
            )
            if style_plotly_fig:
                fig_sqw_bench = style_plotly_fig(fig_sqw_bench)
            st.plotly_chart(fig_sqw_bench, use_container_width=True, key="insp_fig_sqw_bench")
        else:
            st.info("ไม่พบข้อมูลราคาต่อตารางวาสำหรับสร้างแผนภูมิ")

    with c_chart_sqm:
        sqm_cats = []
        sqm_vals = []
        sqm_colors = []

        if price_sqm > 0:
            sqm_cats.append(f'🏛️ ทรัพย์ SAM นี้ ({asset_code})')
            sqm_vals.append(price_sqm)
            sqm_colors.append('#10b981')

        if pd.notna(dist_med_sqm):
            sqm_cats.append(f'🏘️ {asset_type} อ.{asset_dist}')
            sqm_vals.append(dist_med_sqm)
            sqm_colors.append('#3b82f6')

        if pd.notna(prov_med_sqm):
            sqm_cats.append(f'📍 {asset_type} จ.{asset_prov}')
            sqm_vals.append(prov_med_sqm)
            sqm_colors.append('#06b6d4')

        if pd.notna(sam_cat_med_sqm):
            sqm_cats.append(f'🏛️ {asset_type} SAM ทั่วประเทศ')
            sqm_vals.append(sam_cat_med_sqm)
            sqm_colors.append('#8b5cf6')

        if pd.notna(all_cat_med_sqm):
            sqm_cats.append(f'🌐 {asset_type} ตลาดรวม')
            sqm_vals.append(all_cat_med_sqm)
            sqm_colors.append('#f59e0b')

        if sqm_vals:
            fig_sqm_bench = go.Figure(go.Bar(
                x=sqm_vals,
                y=sqm_cats,
                orientation='h',
                marker_color=sqm_colors,
                text=[f"฿{v:,.0f}/ตร.ม." for v in sqm_vals],
                textposition='auto'
            ))
            fig_sqm_bench.update_layout(
                title=f'🏢 ราคาต่อตารางเมตร (Price/Sq.M. - จากพื้นที่ใช้สอย)',
                xaxis_title="บาท / ตร.ม.",
                height=320,
                margin=dict(t=40, b=10, l=10, r=10),
                template=plotly_template
            )
            if style_plotly_fig:
                fig_sqm_bench = style_plotly_fig(fig_sqm_bench)
            st.plotly_chart(fig_sqm_bench, use_container_width=True, key="insp_fig_sqm_bench")
        else:
            st.info("ไม่พบข้อมูลพื้นที่ใช้สอยสำหรับคำนวณราคาต่อตารางเมตร")

    st.markdown("---")

    # -------------------------------------------------------------------------
    # 3. NEARBY COMPARABLE ASSETS (COMPS) WITH MINI-MAP & TABLE
    # -------------------------------------------------------------------------
    st.markdown("##### 📍 เปรียบเทียบกับทรัพย์สินคู่แข่งในบริเวณใกล้เคียง (Nearby Comparable Assets)")
    st.caption("ค้นหาและเปรียบเทียบทรัพย์ NPA ของทุกสถาบัน (BAM, GHB, KBANK, SCB, Chayo555 ฯลฯ) ที่ตั้งอยู่รอบตำแหน่งทรัพย์นี้")

    c_opt1, c_opt2, c_opt3 = st.columns([0.35, 0.35, 0.3])
    with c_opt1:
        radius_km = st.slider("เลือกรัศมีค้นหา (กิโลเมตร):", min_value=1, max_value=25, value=5, step=1, key="insp_radius_slider")
    with c_opt2:
        filter_same_type = st.checkbox("เฉพาะประเภททรัพย์เดียวกันเท่านั้น", value=True, key="insp_filter_same_type")
    with c_opt3:
        sort_by_dist = st.radio("เรียงลำดับผลลัพธ์:", options=["ใกล้สุดก่อน (Distance)", "ถูกสุดก่อน (Price)"], horizontal=True, key="insp_sort_radio")

    if asset_lat and asset_lng:
        # Calculate Haversine Distance
        valid_coords = df_raw[
            df_raw['ละติจูด'].notna() & 
            df_raw['ลองจิจูด'].notna() & 
            (df_raw['รหัสทรัพย์'] != asset_code)
        ].copy()

        R = 6371.0 # Earth radius in km
        dlat = np.radians(valid_coords['ละติจูด'] - asset_lat)
        dlon = np.radians(valid_coords['ลองจิจูด'] - asset_lng)
        a = np.sin(dlat / 2)**2 + np.cos(np.radians(asset_lat)) * np.cos(np.radians(valid_coords['ละติจูด'])) * np.sin(dlon / 2)**2
        c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))
        valid_coords['dist_km'] = R * c

        nearby_comps = valid_coords[valid_coords['dist_km'] <= radius_km].copy()
        if filter_same_type:
            nearby_comps = nearby_comps[nearby_comps['ประเภททรัพย์'] == asset_type]

        if "ใกล้สุด" in sort_by_dist:
            nearby_comps = nearby_comps.sort_values('dist_km', ascending=True)
        else:
            nearby_comps = nearby_comps.sort_values('ราคา', ascending=True)

        st.info(f"🎯 พบทรัพย์สินคู่แข่งในรัศมี **{radius_km} กม.** จำนวนทั้งหมด **{len(nearby_comps):,}** รายการ (ครอบคลุม {nearby_comps['บริษัท'].nunique()} สถาบัน)")

        # Mini Map showing SAM asset (Green Star) vs Nearby Comps (Colored circles)
        if not nearby_comps.empty:
            map_comps_data = nearby_comps[['ละติจูด', 'ลองจิจูด', 'บริษัท', 'รหัสทรัพย์', 'ประเภททรัพย์', 'ราคา', 'dist_km', 'ชื่อประกาศ', 'ชื่อโครงการ']].copy()
            map_comps_data['fill_color'] = map_comps_data['บริษัท'].map(lambda x: [
                int(COMPANY_COLORS.get(x, '#64748b')[1:3], 16),
                int(COMPANY_COLORS.get(x, '#64748b')[3:5], 16),
                int(COMPANY_COLORS.get(x, '#64748b')[5:7], 16),
                200
            ])
            map_comps_data['ราคา_fmt'] = map_comps_data['ราคา'].apply(lambda p: f"฿{p:,.0f}" if pd.notna(p) and p > 0 else "ไม่ระบุ")
            map_comps_data['dist_fmt'] = map_comps_data['dist_km'].apply(lambda d: f"{d:.2f} กม.")

            # Target SAM pin
            target_df = pd.DataFrame([{
                'ละติจูด': asset_lat,
                'ลองจิจูด': asset_lng,
                'fill_color': [16, 185, 129, 255],
                'บริษัท': 'SAM (ทรัพย์เป้าหมาย)',
                'รหัสทรัพย์': asset_code,
                'ประเภททรัพย์': asset_type,
                'ราคา_fmt': f"฿{asset_price:,.0f}",
                'dist_fmt': '0.00 กม. (จุดศูนย์กลาง)',
                'ชื่อประกาศ': asset_name
            }])

            layer_comps = pdk.Layer(
                "ScatterplotLayer",
                data=map_comps_data,
                get_position='[ลองจิจูด, ละติจูด]',
                get_fill_color='fill_color',
                get_radius=220,
                radius_min_pixels=5,
                radius_max_pixels=20,
                pickable=True,
                auto_highlight=True
            )

            layer_target = pdk.Layer(
                "ScatterplotLayer",
                data=target_df,
                get_position='[ลองจิจูด, ละติจูด]',
                get_fill_color='fill_color',
                get_line_color=[255, 255, 255, 255],
                line_width_min_pixels=3,
                get_radius=500,
                radius_min_pixels=10,
                radius_max_pixels=30,
                pickable=True
            )

            view_state_comp = pdk.ViewState(
                latitude=asset_lat,
                longitude=asset_lng,
                zoom=12.5,
                pitch=0
            )

            tooltip_comp = {
                "html": """
                <div style="background:#0f172a; color:#f8fafc; padding:8px 12px; border-radius:6px; font-family:Sarabun, sans-serif; font-size:12px; border:1px solid #38bdf8;">
                    <div style="font-weight:bold; color:#38bdf8;">[{บริษัท}] {รหัสทรัพย์}</div>
                    <div><b>ประเภท:</b> {ประเภททรัพย์}</div>
                    <div><b>ราคา:</b> <span style="color:#fbbf24; font-weight:bold;">{ราคา_fmt}</span></div>
                    <div><b>ระยะทาง:</b> {dist_fmt}</div>
                </div>
                """,
                "style": {"backgroundColor": "transparent", "color": "white"}
            }

            pdk_style = "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json" if is_dark_mode else "https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json"
            deck_comp = pdk.Deck(
                layers=[layer_comps, layer_target],
                initial_view_state=view_state_comp,
                tooltip=tooltip_comp,
                map_style=pdk_style
            )
            st.pydeck_chart(deck_comp, use_container_width=True, key="insp_nearby_deck_chart")

            # Nearby Comps Data Table
            table_comps = nearby_comps[[
                'บริษัท', 'รหัสทรัพย์', 'ประเภททรัพย์', 'ราคา', 'dist_km', 
                'พื้นที่_ตารางวา', 'ราคาต่อตารางวา', 'ชื่อโครงการ', 'ชื่อประกาศ', 'ตำบล', 'ลิงก์'
            ]].copy()

            table_comps['ราคาขาย (บาท)'] = table_comps['ราคา']
            table_comps['ระยะทาง (กม.)'] = table_comps['dist_km'].apply(lambda d: round(d, 2))
            table_comps['ขนาดที่ดิน'] = table_comps['พื้นที่_ตารางวา'].apply(format_rai_ngan_wah)

            if asset_price > 0:
                table_comps['เทียบราคา SAM (%)'] = table_comps['ราคา'].apply(
                    lambda p: f"{(p - asset_price) / asset_price * 100:+.1f}%" if pd.notna(p) and p > 0 else "-"
                )
            else:
                table_comps['เทียบราคา SAM (%)'] = "-"

            st.dataframe(
                table_comps[[
                    'บริษัท', 'รหัสทรัพย์', 'ประเภททรัพย์', 'ราคาขาย (บาท)', 'เทียบราคา SAM (%)', 
                    'ระยะทาง (กม.)', 'ขนาดที่ดิน', 'ราคาต่อตารางวา', 'ชื่อโครงการ', 'ตำบล', 'ลิงก์'
                ]],
                use_container_width=True,
                column_config={
                    "ราคาขาย (บาท)": st.column_config.NumberColumn("ราคาขาย (บาท)", format="฿%,d"),
                    "ราคาต่อตารางวา": st.column_config.NumberColumn("ราคา/ตร.ว.", format="฿%,d"),
                    "ระยะทาง (กม.)": st.column_config.NumberColumn("ระยะห่าง (กม.)", format="%.2f กม."),
                    "ลิงก์": st.column_config.LinkColumn("เปิดดูทรัพย์", display_text="🔗 ดูรายละเอียด")
                },
                height=350,
                key="insp_nearby_comps_table"
            )
        else:
            st.warning(f"⚠️ ไม่พบทรัพย์สินอื่นในรัศมี {radius_km} กม. ลองขยายรัศมีหรือปลดตัวกรองประเภททรัพย์")
    else:
        st.info("ℹ️ ทรัพย์สินนี้ไม่มีข้อมูลพิกัด GPS สำหรับค้นหาทรัพย์รอบข้าง")

    # -------------------------------------------------------------------------
    # 4. SAME-PROJECT COMPS (IF APPLICABLE)
    # -------------------------------------------------------------------------
    asset_proj_name = str(asset_row.get('ชื่อโครงการ', '')).strip()
    if asset_proj_name and asset_proj_name not in ['', 'nan', 'None', '-', 'ไม่มีชื่อ']:
        st.markdown(f"##### 🏢 ทรัพย์สินอื่นในโครงการเดียวกัน ({asset_proj_name})")
        same_proj_all = df_raw[df_raw['ชื่อโครงการ'].astype(str).str.strip() == asset_proj_name].copy()
        
        if len(same_proj_all) > 1:
            st.success(f"พบเพื่อนบ้านในโครงการเดียวกัน **{len(same_proj_all):,}** ยูนิต (จาก {same_proj_all['บริษัท'].nunique()} สถาบัน)")
            same_proj_show = same_proj_all.sort_values('ราคา', ascending=True).copy()
            same_proj_show['ราคาขาย (บาท)'] = same_proj_show['ราคา']
            same_proj_show['ขนาดที่ดิน'] = same_proj_show['พื้นที่_ตารางวา'].apply(format_rai_ngan_wah)

            st.dataframe(
                same_proj_show[['บริษัท', 'รหัสทรัพย์', 'ประเภททรัพย์', 'ราคาขาย (บาท)', 'ขนาดที่ดิน', 'พื้นที่ใช้สอย (ตร.ม.)', 'ตำบล', 'อำเภอ', 'ลิงก์']],
                use_container_width=True,
                column_config={
                    "ราคาขาย (บาท)": st.column_config.NumberColumn("ราคาขาย (บาท)", format="฿%,d"),
                    "ลิงก์": st.column_config.LinkColumn("เปิดดูทรัพย์", display_text="🔗 ดูรายละเอียด")
                },
                key="insp_same_proj_table"
            )
        else:
            st.caption(f"ℹ️ โครงการ '{asset_proj_name}' มีทรัพย์ของ SAM เพียงยูนิตเดียวในฐานข้อมูล")


# ==============================================================================
# MAIN RENDER FUNCTION FOR TAB SAM
# ==============================================================================
def render_sam_tab(df_raw, df_filtered, is_dark_mode=False, plotly_template="plotly_white", style_plotly_fig=None):
    """
    Renders the specialized, comprehensive SAM NPA Analysis Tab with 7 deep-dive subtabs.
    """
    if df_raw is None or df_raw.empty:
        st.warning("⚠️ ไม่มีข้อมูลในฐานข้อมูลสำหรับการวิเคราะห์ SAM")
        return

    # Extract all SAM data from raw dataset
    sam_all = df_raw[df_raw['บริษัท'].astype(str).str.upper().str.contains('SAM', na=False)].copy()
    if sam_all.empty:
        st.warning("⚠️ ไม่พบข้อมูลทรัพย์สินของบริษัท SAM ในฐานข้อมูล")
        return

    # Ensure price numeric
    if 'ราคา' in sam_all.columns:
        sam_all['ราคา'] = pd.to_numeric(sam_all['ราคา'], errors='coerce')
    if 'พื้นที่_ตารางวา' in sam_all.columns:
        sam_all['พื้นที่_ตารางวา'] = pd.to_numeric(sam_all['พื้นที่_ตารางวา'], errors='coerce')

    # Add enriched classification columns if not present
    if 'Asset_Class' not in sam_all.columns:
        sam_all['Asset_Class'] = sam_all['ประเภททรัพย์'].map(lambda x: ASSET_CLASS_MAP.get(str(x).strip(), "📦 อื่นๆ & สังหาริมทรัพย์ (Others)"))
    if 'Price_Tier' not in sam_all.columns:
        sam_all['Price_Tier'] = sam_all['ราคา'].apply(classify_price_tier)
    if 'Economic_Zone' not in sam_all.columns:
        sam_all['Economic_Zone'] = sam_all['จังหวัด'].apply(classify_economic_zone)
    if 'ราคาต่อตารางวา' not in sam_all.columns:
        if 'พื้นที่_ตารางวา' in sam_all.columns and 'ราคา' in sam_all.columns:
            sam_all['ราคาต่อตารางวา'] = np.where((sam_all['พื้นที่_ตารางวา'] > 0) & (sam_all['ราคา'] > 0), sam_all['ราคา'] / sam_all['พื้นที่_ตารางวา'], np.nan)
        else:
            sam_all['ราคาต่อตารางวา'] = np.nan

    # -------------------------------------------------------------------------
    # SAM HEADER & BRAND BANNER
    # -------------------------------------------------------------------------
    sam_logo_path = Path("assets/logos/SAM.png")
    sam_logo_b64 = ""
    if sam_logo_path.exists():
        with open(sam_logo_path, "rb") as img_f:
            sam_logo_b64 = base64.b64encode(img_f.read()).decode("utf-8")

    logo_img_tag = f'<img src="data:image/png;base64,{sam_logo_b64}" style="height: 52px; object-fit: contain; margin-right: 12px; filter: drop-shadow(0 4px 8px rgba(16, 185, 129, 0.25));">' if sam_logo_b64 else '🏛️'

    total_sam_units = len(sam_all)
    total_sam_val = sam_all['ราคา'].dropna().sum()
    mean_sam_price = sam_all['ราคา'].dropna().mean()
    median_sam_price = sam_all['ราคา'].dropna().median()
    auction_count = len(sam_all[sam_all['ประเภทการขาย'].astype(str).str.contains('ประมูล', na=False)])
    large_land_count = len(sam_all[(sam_all['ประเภททรัพย์'] == 'ที่ดินเปล่า') & (sam_all['พื้นที่_ตารางวา'] >= 4000)]) # >= 10 ไร่
    mega_assets_count = len(sam_all[sam_all['ราคา'] >= 50_000_000])

    header_html = f"""
    <div style="background: linear-gradient(135deg, {'#064e3b' if is_dark_mode else '#ecfdf5'} 0%, {'#0f172a' if is_dark_mode else '#f0fdf4'} 100%); 
                border: 1px solid {'#047857' if is_dark_mode else '#a7f3d0'}; 
                border-radius: 16px; padding: 18px 24px; margin-bottom: 20px; 
                box-shadow: 0 8px 24px rgba(16, 185, 129, 0.12);">
        <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 14px;">
            <div style="display: flex; align-items: center;">
                {logo_img_tag}
                <div>
                    <h2 style="margin: 0; color: {'#34d399' if is_dark_mode else '#065f46'}; font-size: 1.6rem; font-weight: 800; letter-spacing: -0.5px;">
                        วิเคราะห์ทรัพย์ SAM โดยเฉพาะ (SAM NPA Deep Dive)
                    </h2>
                    <p style="margin: 3px 0 0 0; color: {'#94a3b8' if is_dark_mode else '#047857'}; font-size: 0.88rem; font-weight: 500;">
                        บริษัท บริหารสินทรัพย์สุขุมวิท จำกัด (Sukhumvit Asset Management) | พอร์ตทรัพย์สิน NPA ครอบคลุมทั่วประเทศ
                    </p>
                </div>
            </div>
            <div style="display: flex; gap: 10px; flex-wrap: wrap;">
                <div style="background: {'rgba(16, 185, 129, 0.2)' if is_dark_mode else '#d1fae5'}; padding: 6px 14px; border-radius: 10px; border: 1px solid #10b981; text-align: center;">
                    <div style="font-size: 0.72rem; color: {'#a7f3d0' if is_dark_mode else '#065f46'}; font-weight: 600;">มูลค่ารวมพอร์ต SAM</div>
                    <div style="font-size: 1.15rem; font-weight: 800; color: {'#34d399' if is_dark_mode else '#047857'};">฿{total_sam_val/1e9:,.2f} พันล้าน</div>
                </div>
                <div style="background: {'rgba(59, 130, 246, 0.2)' if is_dark_mode else '#dbeafe'}; padding: 6px 14px; border-radius: 10px; border: 1px solid #3b82f6; text-align: center;">
                    <div style="font-size: 0.72rem; color: {'#bfdbfe' if is_dark_mode else '#1e40af'}; font-weight: 600;">จำนวนทรัพย์ทั้งหมด</div>
                    <div style="font-size: 1.15rem; font-weight: 800; color: {'#60a5fa' if is_dark_mode else '#1d4ed8'};">{total_sam_units:,} รายการ</div>
                </div>
            </div>
        </div>
    </div>
    """
    st.markdown(header_html, unsafe_allow_html=True)

    # -------------------------------------------------------------------------
    # SAM DEDICATED QUICK FILTERS
    # -------------------------------------------------------------------------
    with st.expander("🎯 แผงควบคุมตัวกรองเฉพาะทรัพย์ SAM (Filter SAM Portfolio)", expanded=False):
        f_col1, f_col2, f_col3, f_col4 = st.columns(4)
        
        with f_col1:
            all_classes = ["ทั้งหมด"] + sorted(sam_all['Asset_Class'].unique().tolist())
            sel_class = st.selectbox("กลุ่มประเภททรัพย์หลัก", options=all_classes, index=0, key="sam_filter_class")
            
        with f_col2:
            all_zones = ["ทั้งหมด"] + sorted(sam_all['Economic_Zone'].unique().tolist())
            sel_zone = st.selectbox("โซนเศรษฐกิจ / ภูมิภาค", options=all_zones, index=0, key="sam_filter_zone")
            
        with f_col3:
            all_sales = ["ทั้งหมด", "ขาย (ทั่วไป)", "ประมูล (Auction)", "รอประกาศราคา"]
            sel_sale = st.selectbox("รูปแบบการขาย", options=all_sales, index=0, key="sam_filter_sale")
            
        with f_col4:
            prov_options = sorted(sam_all['จังหวัด'].dropna().unique().tolist())
            sel_provs = st.multiselect("เลือกจังหวัดเฉพาะ", options=prov_options, default=[], key="sam_filter_provs")

    # Apply SAM filters to a working dataset for Tab SAM
    sam_filtered = sam_all.copy()
    if sel_class != "ทั้งหมด":
        sam_filtered = sam_filtered[sam_filtered['Asset_Class'] == sel_class]
    if sel_zone != "ทั้งหมด":
        sam_filtered = sam_filtered[sam_filtered['Economic_Zone'] == sel_zone]
    if sel_sale == "ขาย (ทั่วไป)":
        sam_filtered = sam_filtered[sam_filtered['ประเภทการขาย'].astype(str).str.contains('ขาย', na=False) & ~sam_filtered['ประเภทการขาย'].astype(str).str.contains('ประมูล', na=False)]
    elif sel_sale == "ประมูล (Auction)":
        sam_filtered = sam_filtered[sam_filtered['ประเภทการขาย'].astype(str).str.contains('ประมูล', na=False)]
    elif sel_sale == "รอประกาศราคา":
        sam_filtered = sam_filtered[sam_filtered['ประเภทการขาย'].astype(str).str.contains('รอประกาศราคา', na=False) | sam_filtered['ราคา'].isna()]
    if sel_provs:
        sam_filtered = sam_filtered[sam_filtered['จังหวัด'].isin(sel_provs)]

    # Floating KPI Metrics for active SAM selection
    kpi_val = sam_filtered['ราคา'].dropna().sum()
    kpi_count = len(sam_filtered)
    kpi_med = sam_filtered['ราคา'].dropna().median() if not sam_filtered['ราคา'].dropna().empty else 0
    kpi_mean = sam_filtered['ราคา'].dropna().mean() if not sam_filtered['ราคา'].dropna().empty else 0
    kpi_auction = len(sam_filtered[sam_filtered['ประเภทการขาย'].astype(str).str.contains('ประมูล', na=False)])
    kpi_large_land = len(sam_filtered[(sam_filtered['ประเภททรัพย์'] == 'ที่ดินเปล่า') & (sam_filtered['พื้นที่_ตารางวา'] >= 4000)])

    kpi_html = f"""
    <div class="floating-kpi-container" style="margin-bottom: 22px;">
        <div class="floating-card">
            <div class="floating-card-title"><i class="fa fa-layer-group" style="color: #10b981;"></i> ทรัพย์ SAM ที่เลือก</div>
            <div class="floating-card-value">{kpi_count:,}</div>
            <div class="floating-card-sub">จากทั้งหมด {total_sam_units:,} รายการ</div>
        </div>
        <div class="floating-card">
            <div class="floating-card-title"><i class="fa fa-coins" style="color: #059669;"></i> มูลค่ารวมทรัพย์</div>
            <div class="floating-card-value">{format_price_short(kpi_val)}</div>
            <div class="floating-card-sub">คิดเป็น {kpi_val/total_sam_val*100:.1f}% ของพอร์ต SAM</div>
        </div>
        <div class="floating-card">
            <div class="floating-card-title"><i class="fa fa-tags" style="color: #3b82f6;"></i> ราคากลาง (Median)</div>
            <div class="floating-card-value">{format_price_short(kpi_med)}</div>
            <div class="floating-card-sub">ค่าเฉลี่ย: {format_price_short(kpi_mean)}</div>
        </div>
        <div class="floating-card">
            <div class="floating-card-title"><i class="fa fa-gavel" style="color: #f59e0b;"></i> ทรัพย์ประมูล</div>
            <div class="floating-card-value">{kpi_auction:,}</div>
            <div class="floating-card-sub">ทรัพย์ที่เปิดเคาะราคา</div>
        </div>
        <div class="floating-card">
            <div class="floating-card-title"><i class="fa fa-mountain-sun" style="color: #8b5cf6;"></i> ที่ดินแปลงใหญ่ (≥10 ไร่)</div>
            <div class="floating-card-value">{kpi_large_land:,}</div>
            <div class="floating-card-sub">ศักยภาพพัฒนาโครงการ</div>
        </div>
    </div>
    """
    st.markdown(kpi_html, unsafe_allow_html=True)

    # -------------------------------------------------------------------------
    # 5 SPECIALIZED SUBTABS
    # -------------------------------------------------------------------------
    sam_sub2, sam_sub3, sam_sub_proj, sam_sub4, sam_sub5 = st.tabs([
        "🗺️ แผนที่ & ทำเลยุทธศาสตร์ (Geospatial & Zones)",
        "⚔️ เปรียบเทียบ SAM vs คู่แข่ง (Market Benchmarking)",
        "🏘️ เปรียบเทียบในโครงการเดียวกัน (Same-Project Benchmark)",
        "💎 ขุมทรัพย์การลงทุน & ทรัพย์เด่น (Investment Gems)",
        "🔍 ค้นหาทรัพย์ SAM เจาะลึก & ส่งออก (Explorer & Export)"
    ])

    # =========================================================================
    # SUB-TAB 2: ทำเลยุทธศาสตร์ & แผนที่ (GEOSPATIAL & ZONES)
    # =========================================================================
    with sam_sub2:
        st.markdown("#### 🗺️ ทำเลยุทธศาสตร์และแผนที่พิกัดทรัพย์สิน SAM")
        st.caption("เจาะลึก 3 โซนยุทธศาสตร์หลัก (EEC, BKK & Metro, ภูมิภาค) พร้อมพิกัด GPS แม่นยำ 100%")
        
        # Zone KPI summary pills
        z_agg = sam_all.groupby('Economic_Zone').agg(
            count=('รหัสทรัพย์', 'count'),
            total_val=('ราคา', 'sum'),
            median_val=('ราคา', 'median')
        ).reset_index()
        
        z_col1, z_col2, z_col3 = st.columns(3)
        with z_col1:
            eec_match = z_agg[z_agg['Economic_Zone'].str.contains('EEC', na=False)]
            eec_row = eec_match.iloc[0] if not eec_match.empty else None
            if eec_row is not None:
                st.markdown(f"""
                <div style="background: {'#1e293b' if is_dark_mode else '#f8fafc'}; border-left: 4px solid #f59e0b; padding: 12px 16px; border-radius: 8px; border-top: 1px solid {'#334155' if is_dark_mode else '#e2e8f0'}; border-right: 1px solid {'#334155' if is_dark_mode else '#e2e8f0'}; border-bottom: 1px solid {'#334155' if is_dark_mode else '#e2e8f0'};"><div style="font-size: 0.85rem; font-weight: 700; color: #f59e0b;">⚡ เขตพัฒนาพิเศษภาคตะวันออก (EEC)</div><div style="font-size: 1.3rem; font-weight: 800; color: {'#f8fafc' if is_dark_mode else '#0f172a'}; margin: 2px 0;">{eec_row['count']:,} รายการ (฿{eec_row['total_val']/1e9:,.2f}B)</div><div style="font-size: 0.75rem; color: {'#94a3b8' if is_dark_mode else '#64748b'};">ชลบุรี (391), ระยอง (302), ฉะเชิงเทรา (46)</div></div>""", unsafe_allow_html=True)
                
        with z_col2:
            bkk_match = z_agg[z_agg['Economic_Zone'].str.contains('BKK', na=False)]
            bkk_row = bkk_match.iloc[0] if not bkk_match.empty else None
            if bkk_row is not None:
                st.markdown(f"""
                <div style="background: {'#1e293b' if is_dark_mode else '#f8fafc'}; border-left: 4px solid #3b82f6; padding: 12px 16px; border-radius: 8px; border-top: 1px solid {'#334155' if is_dark_mode else '#e2e8f0'}; border-right: 1px solid {'#334155' if is_dark_mode else '#e2e8f0'}; border-bottom: 1px solid {'#334155' if is_dark_mode else '#e2e8f0'};"><div style="font-size: 0.85rem; font-weight: 700; color: #3b82f6;">🌆 กรุงเทพฯ และปริมณฑล (BKK & Metro)</div><div style="font-size: 1.3rem; font-weight: 800; color: {'#f8fafc' if is_dark_mode else '#0f172a'}; margin: 2px 0;">{bkk_row['count']:,} รายการ (฿{bkk_row['total_val']/1e9:,.2f}B)</div><div style="font-size: 0.75rem; color: {'#94a3b8' if is_dark_mode else '#64748b'};">กทม. (1,029), ปทุมธานี (365), สมุทรปราการ (256), นนทบุรี (245)</div></div>""", unsafe_allow_html=True)
                
        with z_col3:
            upcountry_cnt = total_sam_units - (eec_row['count'] if eec_row is not None else 0) - (bkk_row['count'] if bkk_row is not None else 0)
            upcountry_val = total_sam_val - (eec_row['total_val'] if eec_row is not None else 0) - (bkk_row['total_val'] if bkk_row is not None else 0)
            st.markdown(f"""
            <div style="background: {'#1e293b' if is_dark_mode else '#f8fafc'}; border-left: 4px solid #10b981; padding: 12px 16px; border-radius: 8px; border-top: 1px solid {'#334155' if is_dark_mode else '#e2e8f0'}; border-right: 1px solid {'#334155' if is_dark_mode else '#e2e8f0'}; border-bottom: 1px solid {'#334155' if is_dark_mode else '#e2e8f0'};"><div style="font-size: 0.85rem; font-weight: 700; color: #10b981;">🏞️ ภูมิภาคและต่างจังหวัด (Regional Hubs)</div><div style="font-size: 1.3rem; font-weight: 800; color: {'#f8fafc' if is_dark_mode else '#0f172a'}; margin: 2px 0;">{upcountry_cnt:,} รายการ (฿{upcountry_val/1e9:,.2f}B)</div><div style="font-size: 0.75rem; color: {'#94a3b8' if is_dark_mode else '#64748b'};">เชียงใหม่ (124), โคราช (85), สงขลา (82), สุราษฎร์ฯ (82)</div></div>""", unsafe_allow_html=True)

        st.markdown("<br/>", unsafe_allow_html=True)

        # Interactive Map Rendering for SAM
        map_mode_col1, map_mode_col2 = st.columns([0.6, 0.4])
        with map_mode_col1:
            sam_map_color = st.segmented_control(
                "🎨 เลือกการจำแนกสีจุดพิกัดบนแผนที่ SAM:",
                options=["🏠 จำแนกตามกลุ่มประเภททรัพย์", "🏷️ จำแนกตามช่วงราคา (Price Tier)", "🔨 จำแนกตามสถานะการขาย (ประมูล/ขาย)"],
                default="🏠 จำแนกตามกลุ่มประเภททรัพย์",
                key="sam_map_color_selector"
            )
            if not sam_map_color:
                sam_map_color = "🏠 จำแนกตามกลุ่มประเภททรัพย์"
                
        sam_map_data = sam_filtered[
            sam_filtered['ละติจูด'].notna() & sam_filtered['ลองจิจูด'].notna() &
            sam_filtered['ละติจูด'].between(5, 21) & sam_filtered['ลองจิจูด'].between(97, 106)
        ].copy()

        if not sam_map_data.empty:
            if "กลุ่มประเภททรัพย์" in sam_map_color:
                color_lookup = {
                    "🏠 ที่อยู่อาศัย (Residential)": [59, 130, 246, 200],
                    "🌾 ที่ดินเปล่า (Land Plots)": [16, 185, 129, 200],
                    "🏢 อาคารและพาณิชยกรรม (Commercial)": [245, 158, 11, 200],
                    "🏭 อุตสาหกรรมและโครงการพิเศษ (Industrial & Mega)": [239, 68, 68, 220],
                    "📦 อื่นๆ & สังหาริมทรัพย์ (Others)": [139, 92, 246, 180]
                }
                sam_map_data['fill_color'] = sam_map_data['Asset_Class'].map(lambda x: color_lookup.get(x, [16, 185, 129, 200]))
            elif "ช่วงราคา" in sam_map_color:
                tier_colors = {
                    "< 1 ล้านบาท": [16, 185, 129, 180],
                    "1 - 3 ล้านบาท": [6, 182, 212, 190],
                    "3 - 5 ล้านบาท": [59, 130, 246, 200],
                    "5 - 10 ล้านบาท": [245, 158, 11, 210],
                    "10 - 20 ล้านบาท": [249, 115, 22, 220],
                    "> 20 ล้านบาท": [239, 68, 68, 230],
                    "ไม่ระบุราคา": [148, 163, 184, 150]
                }
                sam_map_data['fill_color'] = sam_map_data['Price_Tier'].map(lambda x: tier_colors.get(x, [16, 185, 129, 200]))
            else:
                sale_colors = {
                    "ขาย": [16, 185, 129, 200],
                    "ประมูล": [239, 68, 68, 230],
                    "รอประกาศราคา": [245, 158, 11, 200]
                }
                sam_map_data['fill_color'] = sam_map_data['ประเภทการขาย'].map(lambda x: sale_colors.get(str(x).strip(), [16, 185, 129, 200]))

            sam_map_data['ราคา_fmt'] = sam_map_data['ราคา'].apply(lambda p: f"฿{p:,.0f}" if pd.notna(p) and p > 0 else "ไม่ระบุ")
            sam_map_data['ขนาด_fmt'] = sam_map_data['พื้นที่_ตารางวา'].apply(format_rai_ngan_wah)

            center_lat = float(sam_map_data['ละติจูด'].median()) if not sam_map_data.empty else 13.75
            center_lng = float(sam_map_data['ลองจิจูด'].median()) if not sam_map_data.empty else 100.5

            view_state = pdk.ViewState(
                latitude=center_lat,
                longitude=center_lng,
                zoom=5.8,
                pitch=20
            )

            layer = pdk.Layer(
                "ScatterplotLayer",
                data=sam_map_data[['ละติจูด', 'ลองจิจูด', 'fill_color', 'รหัสทรัพย์', 'ประเภททรัพย์', 'ราคา_fmt', 'จังหวัด', 'อำเภอ', 'ขนาด_fmt', 'ประเภทการขาย']],
                get_position='[ลองจิจูด, ละติจูด]',
                get_fill_color='fill_color',
                get_radius=1800,
                radius_min_pixels=4,
                radius_max_pixels=25,
                pickable=True,
                auto_highlight=True
            )

            tooltip = {
                "html": """
                <div style="background:#0f172a; color:#f8fafc; padding:10px 14px; border-radius:8px; font-family:Sarabun, sans-serif; font-size:12px; border:1px solid #10b981; box-shadow:0 4px 12px rgba(0,0,0,0.5);">
                    <div style="font-weight:bold; font-size:14px; color:#34d399; margin-bottom:4px;">🏛️ SAM: {รหัสทรัพย์}</div>
                    <div><b>ประเภท:</b> {ประเภททรัพย์} ({ประเภทการขาย})</div>
                    <div><b>ราคา:</b> <span style="color:#fbbf24; font-weight:bold;">{ราคา_fmt}</span></div>
                    <div><b>ทำเล:</b> {อำเภอ}, {จังหวัด}</div>
                    <div><b>ขนาดพื้นที่:</b> {ขนาด_fmt}</div>
                </div>
                """,
                "style": {"backgroundColor": "transparent", "color": "white"}
            }

            pdk_style = "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json" if is_dark_mode else "https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json"
            deck = pdk.Deck(
                layers=[layer],
                initial_view_state=view_state,
                tooltip=tooltip,
                map_style=pdk_style
            )
            st.pydeck_chart(deck, use_container_width=True)
        else:
            st.warning("⚠️ ไม่พบข้อมูลพิกัดสำหรับแสดงแผนที่")

        # Top 15 SAM Provinces Table & Bar Chart
        st.markdown("##### 📍 15 อันดับจังหวัดที่มีทรัพย์สิน SAM หนาแน่นที่สุด")
        top_prov_df = sam_all.groupby('จังหวัด').agg(
            count=('รหัสทรัพย์', 'count'),
            val_million=('ราคา', lambda x: x.sum() / 1e6),
            median_price=('ราคา', 'median')
        ).sort_values('count', ascending=False).head(15).reset_index()

        fig_prov_bar = px.bar(
            top_prov_df,
            x='จังหวัด',
            y='count',
            color='val_million',
            color_continuous_scale='Tealgrn',
            title='Top 15 จังหวัดของ SAM (จำนวนทรัพย์และมูลค่ารวม)',
            text='count',
            template=plotly_template
        )
        fig_prov_bar.update_layout(
            height=380, 
            yaxis_title="จำนวนทรัพย์ (รายการ)",
            margin=dict(t=40, b=10, l=10, r=10)
        )
        if style_plotly_fig:
            fig_prov_bar = style_plotly_fig(fig_prov_bar)
        st.plotly_chart(fig_prov_bar, use_container_width=True, key="sam_tab_prov_bar")

    # =========================================================================
    # SUB-TAB 3: เปรียบเทียบ SAM VS คู่แข่ง (MARKET BENCHMARKING)
    # =========================================================================
    with sam_sub3:
        st.markdown("#### ⚔️ การเปรียบเทียบขีดความสามารถในการแข่งขัน (SAM vs Competitors)")
        st.caption("เปรียบเทียบส่วนแบ่งตลาด (Market Share), ราคากลางต่อหน่วย, และราคาต่อตารางวา กับคู่แข่งทุกสถาบัน")
        
        b1, b2 = st.columns(2)
        with b1:
            comp_units = df_raw.groupby('บริษัท')['รหัสทรัพย์'].count().reset_index()
            comp_units.columns = ['บริษัท', 'count']
            fig_share_units = px.pie(
                comp_units,
                names='บริษัท',
                values='count',
                hole=0.4,
                title='🥧 ส่วนแบ่งตลาดตามจำนวนทรัพย์สิน (Units Market Share)',
                color='บริษัท',
                color_discrete_map=COMPANY_COLORS,
                template=plotly_template
            )
            fig_share_units.update_traces(textposition='inside', textinfo='percent+label')
            fig_share_units.update_layout(height=400, margin=dict(t=40, b=10, l=10, r=10))
            if style_plotly_fig:
                fig_share_units = style_plotly_fig(fig_share_units)
            st.plotly_chart(fig_share_units, use_container_width=True, key="sam_tab_share_units")
            
        with b2:
            comp_vals = df_raw.groupby('บริษัท')['ราคา'].sum().reset_index()
            comp_vals.columns = ['บริษัท', 'total_val']
            comp_vals['val_million'] = comp_vals['total_val'] / 1e6
            fig_share_val = px.pie(
                comp_vals,
                names='บริษัท',
                values='val_million',
                hole=0.4,
                title='💰 ส่วนแบ่งตลาดตามมูลค่ารวมของพอร์ต (Portfolio Value Share)',
                color='บริษัท',
                color_discrete_map=COMPANY_COLORS,
                template=plotly_template
            )
            fig_share_val.update_traces(textposition='inside', textinfo='percent+label')
            fig_share_val.update_layout(height=400, margin=dict(t=40, b=10, l=10, r=10))
            if style_plotly_fig:
                fig_share_val = style_plotly_fig(fig_share_val)
            st.plotly_chart(fig_share_val, use_container_width=True, key="sam_tab_share_val")

        st.markdown("---")

        # 2. Price Competitiveness Benchmark by Property Type
        st.markdown("##### 🏷️ เปรียบเทียบราคากลาง (Median Price) SAM vs สถาบันอื่น แยกตามประเภททรัพย์")
        top_types_benchmark = ["บ้านเดี่ยว", "ทาวน์เฮ้าส์", "ห้องชุดพักอาศัย", "ที่ดินเปล่า", "อาคารพาณิชย์", "โรงงาน/โกดัง"]
        df_bench = df_raw[df_raw['ประเภททรัพย์'].isin(top_types_benchmark) & (df_raw['ราคา'] > 0)].copy()
        
        bench_agg = df_bench.groupby(['ประเภททรัพย์', 'บริษัท'])['ราคา'].median().reset_index()
        bench_agg.columns = ['ประเภททรัพย์', 'บริษัท', 'median_price']
        bench_agg['price_million'] = bench_agg['median_price'] / 1e6
        
        major_amcs = ["SAM", "BAM", "KBANK", "GHB", "SCB", "KTB", "Chayo555"]
        bench_agg_major = bench_agg[bench_agg['บริษัท'].isin(major_amcs)]

        fig_bench_p = px.bar(
            bench_agg_major,
            x='ประเภททรัพย์',
            y='price_million',
            color='บริษัท',
            barmode='group',
            title='ราคากลาง (Median Price - ล้านบาท) เปรียบเทียบระหว่างสถาบัน NPA',
            color_discrete_map=COMPANY_COLORS,
            template=plotly_template
        )
        fig_bench_p.update_layout(height=420, yaxis_title="ราคากลาง (ล้านบาท)", margin=dict(t=40, b=10, l=10, r=10))
        if style_plotly_fig:
            fig_bench_p = style_plotly_fig(fig_bench_p)
        st.plotly_chart(fig_bench_p, use_container_width=True, key="sam_tab_bench_p")

        # 3. Price per Sq.Wah Benchmark (Land & House)
        st.markdown("##### 📐 เปรียบเทียบราคาต่อตารางวา (Price / Sq.Wah) ในจังหวัดหลัก")
        df_raw_sqw = df_raw.copy()
        if 'ราคาต่อตารางวา' not in df_raw_sqw.columns:
            if 'พื้นที่_ตารางวา' in df_raw_sqw.columns and 'ราคา' in df_raw_sqw.columns:
                df_raw_sqw['ราคาต่อตารางวา'] = np.where(
                    (df_raw_sqw['พื้นที่_ตารางวา'] > 0) & (df_raw_sqw['ราคา'] > 0), 
                    df_raw_sqw['ราคา'] / df_raw_sqw['พื้นที่_ตารางวา'], 
                    np.nan
                )
            else:
                df_raw_sqw['ราคาต่อตารางวา'] = np.nan

        top_provs_for_sqw = ["กรุงเทพมหานคร", "นนทบุรี", "ปทุมธานี", "สมุทรปราการ", "ชลบุรี", "ระยอง", "เชียงใหม่"]
        df_sqw = df_raw_sqw[
            df_raw_sqw['จังหวัด'].isin(top_provs_for_sqw) & 
            df_raw_sqw['ประเภททรัพย์'].isin(['บ้านเดี่ยว', 'ที่ดินเปล่า', 'ทาวน์เฮ้าส์']) &
            (df_raw_sqw['ราคาต่อตารางวา'] > 0) & (df_raw_sqw['ราคาต่อตารางวา'] < 500000)
        ].copy()
        
        if not df_sqw.empty:
            sqw_agg = df_sqw.groupby(['จังหวัด', 'บริษัท'])['ราคาต่อตารางวา'].median().reset_index()
            sqw_agg.columns = ['จังหวัด', 'บริษัท', 'price_per_sqw']
            sqw_agg_major = sqw_agg[sqw_agg['บริษัท'].isin(["SAM", "BAM", "KBANK", "GHB", "Taladnudbaan"])]

            fig_sqw = px.bar(
                sqw_agg_major,
                x='จังหวัด',
                y='price_per_sqw',
                color='บริษัท',
                barmode='group',
                title='ราคากลางต่อตารางวา (Median Price/Sq.Wah) ในหัวเมืองสำคัญ',
                color_discrete_map=COMPANY_COLORS,
                template=plotly_template
            )
            fig_sqw.update_layout(height=380, yaxis_title="บาท / ตารางวา", margin=dict(t=40, b=10, l=10, r=10))
            if style_plotly_fig:
                fig_sqw = style_plotly_fig(fig_sqw)
            st.plotly_chart(fig_sqw, use_container_width=True, key="sam_tab_sqw")

    # =========================================================================
    # SUB-TAB: เปรียบเทียบในโครงการเดียวกัน (SAME-PROJECT BENCHMARK)
    # =========================================================================
    with sam_sub_proj:
        render_same_project_comparison(
            df_all_source=df_raw,
            is_dark_mode=is_dark_mode,
            plotly_template=plotly_template,
            style_plotly_fig=style_plotly_fig,
            default_company_filter="SAM",
            key_prefix="sam_same_proj"
        )

    # =========================================================================
    # SUB-TAB 4: ขุมทรัพย์การลงทุน & ทรัพย์เด่น (INVESTMENT GEMS)
    # =========================================================================
    with sam_sub4:
        st.markdown("#### 💎 ขุมทรัพย์การลงทุนและคัดกรองทรัพย์ศักยภาพสูงของ SAM")
        st.caption("คัดสรรกลุ่มทรัพย์ที่โดดเด่นทั้งในแง่มูลค่า, โอกาสการพัฒนา, สภาพคล่อง, และทรัพย์ประมูล")

        gem_category = st.radio(
            "เลือกกลุ่มทรัพย์ศักยภาพที่ต้องการวิเคราะห์:",
            options=[
                "👑 10 อันดับ Mega Assets (ทรัพย์มูลค่าสูงสุด)",
                "🏭 โรงงาน & โครงการเชิงพาณิชย์ (Commercial & Industrial)",
                "🌾 ที่ดินแปลงยักษ์ศักยภาพสูง (Land Plots > 10 ไร่)",
                "🏷️ ทรัพย์สภาพคล่องสูงราคาเข้าถึงง่าย (< 2 ล้านบาท)",
                "🔨 ทรัพย์ประมูลน่าจับตา (SAM Auction Watchlist)"
            ],
            horizontal=True,
            key="sam_gem_cat_radio"
        )

        if "Mega Assets" in gem_category:
            st.markdown("##### 👑 10 อันดับทรัพย์สินมูลค่าสูงสุดของ SAM (Mega Commercial Assets)")
            top_mega = sam_all.nlargest(10, 'ราคา')[
                ['รหัสทรัพย์', 'ชื่อประกาศ', 'ประเภททรัพย์', 'ราคา', 'จังหวัด', 'อำเภอ', 'เนื้อที่ (ตร.ว.)', 'พื้นที่_ตารางวา', 'ลิงก์']
            ].copy()
            top_mega['ขนาดที่ดิน'] = top_mega['พื้นที่_ตารางวา'].apply(format_rai_ngan_wah)
            top_mega['ราคา (บาท)'] = top_mega['ราคา']
            
            st.dataframe(
                top_mega[['รหัสทรัพย์', 'ประเภททรัพย์', 'ชื่อประกาศ', 'ราคา (บาท)', 'ขนาดที่ดิน', 'อำเภอ', 'จังหวัด', 'ลิงก์']],
                use_container_width=True,
                column_config={
                    "ราคา (บาท)": st.column_config.NumberColumn("ราคาขาย (บาท)", format="฿%,d"),
                    "ลิงก์": st.column_config.LinkColumn("เปิดเว็บ SAM", display_text="🔗 ดูรายละเอียด")
                },
                key="sam_top_mega_table"
            )

        elif "โรงงาน & โครงการเชิงพาณิชย์" in gem_category:
            st.markdown("##### 🏭 ทรัพย์สินกลุ่มอุตสาหกรรม, โรงแรม, และโครงการพาณิชยกรรมขนาดใหญ่")
            comm_types = [
                'โรงงาน/โกดัง', 'โรงแรม/รีสอร์ท', 'ปั๊มน้ำมัน', 'โรงพยาบาล', 'สวนน้ำ', 
                'ศูนย์จำหน่ายสินค้า', 'ห้างสรรพสินค้า', 'อาคารสำนักงาน', 'โชว์รูม'
            ]
            comm_df = sam_all[sam_all['ประเภททรัพย์'].isin(comm_types)].copy()
            
            st.info(f"📊 พบทรัพย์สินเชิงพาณิชย์และอุตสาหกรรมรวม **{len(comm_df):,}** รายการ มูลค่ารวม **฿{comm_df['ราคา'].sum()/1e9:,.2f} พันล้านบาท**")
            
            c_comm1, c_comm2 = st.columns([0.45, 0.55])
            with c_comm1:
                comm_type_counts = comm_df['ประเภททรัพย์'].value_counts().reset_index()
                comm_type_counts.columns = ['prop_type', 'count']
                fig_comm_p = px.pie(
                    comm_type_counts,
                    names='prop_type',
                    values='count',
                    title='สัดส่วนทรัพย์เชิงพาณิชย์และโรงงาน',
                    hole=0.4,
                    template=plotly_template
                )
                if style_plotly_fig:
                    fig_comm_p = style_plotly_fig(fig_comm_p)
                st.plotly_chart(fig_comm_p, use_container_width=True, key="sam_tab_comm_p")
                
            with c_comm2:
                comm_show = comm_df[['รหัสทรัพย์', 'ประเภททรัพย์', 'ราคา', 'จังหวัด', 'อำเภอ', 'พื้นที่_ตารางวา', 'ลิงก์']].sort_values('ราคา', ascending=False)
                comm_show['ขนาด'] = comm_show['พื้นที่_ตารางวา'].apply(format_rai_ngan_wah)
                st.dataframe(
                    comm_show[['รหัสทรัพย์', 'ประเภททรัพย์', 'ราคา', 'ขนาด', 'อำเภอ', 'จังหวัด', 'ลิงก์']],
                    use_container_width=True,
                    column_config={
                        "ราคา": st.column_config.NumberColumn("ราคาขาย (บาท)", format="฿%,d"),
                        "ลิงก์": st.column_config.LinkColumn("เว็บ SAM", display_text="🔗 เปิดดู")
                    },
                    height=350,
                    key="sam_comm_table"
                )

        elif "ที่ดินแปลงยักษ์" in gem_category:
            st.markdown("##### 🌾 ที่ดินเปล่าแปลงใหญ่ (ขนาดตั้งแต่ 10 ไร่ขึ้นไป / ≥ 4,000 ตร.ว.)")
            large_land = sam_all[(sam_all['ประเภททรัพย์'] == 'ที่ดินเปล่า') & (sam_all['พื้นที่_ตารางวา'] >= 4000)].copy()
            large_land = large_land.sort_values('พื้นที่_ตารางวา', ascending=False)
            
            st.success(f"🌾 มีที่ดินเปล่าแปลงใหญ่รวม **{len(large_land):,}** แปลง ขนาดรวมกว่า **{large_land['พื้นที่_ตารางวา'].sum()/400:,.1f} ไร่**")
            
            large_land['ขนาด (ไร่-งาน-วา)'] = large_land['พื้นที่_ตารางวา'].apply(format_rai_ngan_wah)
            large_land['ราคา/ตร.ว. (บาท)'] = large_land['ราคาต่อตารางวา']
            
            st.dataframe(
                large_land[['รหัสทรัพย์', 'ราคา', 'ขนาด (ไร่-งาน-วา)', 'ราคา/ตร.ว. (บาท)', 'ตำบล', 'อำเภอ', 'จังหวัด', 'ลิงก์']],
                use_container_width=True,
                column_config={
                    "ราคา": st.column_config.NumberColumn("ราคารวม (บาท)", format="฿%,d"),
                    "ราคา/ตร.ว. (บาท)": st.column_config.NumberColumn("ราคา/ตร.ว.", format="฿%,d"),
                    "ลิงก์": st.column_config.LinkColumn("เว็บ SAM", display_text="🔗 ดูโฉนด/แปลงที่ดิน")
                },
                key="sam_large_land_table"
            )

        elif "ราคาเข้าถึงง่าย" in gem_category:
            st.markdown("##### 🏷️ ทรัพย์ที่อยู่อาศัยราคาไม่เกิน 2 ล้านบาท (Affordable & High-Liquidity)")
            aff_df = sam_all[
                sam_all['Asset_Class'].str.contains('Residential', na=False) & 
                (sam_all['ราคา'] > 0) & (sam_all['ราคา'] <= 2_000_000)
            ].copy().sort_values('ราคา', ascending=True)
            
            st.info(f"🏡 พบที่อยู่อาศัยราคาเข้าถึงง่าย **{len(aff_df):,}** รายการ (คอนโด {len(aff_df[aff_df['ประเภททรัพย์']=='ห้องชุดพักอาศัย']):,} ห้อง, ทาวน์เฮ้าส์ {len(aff_df[aff_df['ประเภททรัพย์']=='ทาวน์เฮ้าส์']):,} หลัง)")
            
            st.dataframe(
                aff_df[['รหัสทรัพย์', 'ประเภททรัพย์', 'ชื่อประกาศ', 'ราคา', 'ตำบล', 'อำเภอ', 'จังหวัด', 'ลิงก์']],
                use_container_width=True,
                column_config={
                    "ราคา": st.column_config.NumberColumn("ราคาขาย (บาท)", format="฿%,d"),
                    "ลิงก์": st.column_config.LinkColumn("เปิดเว็บ SAM", display_text="🔗 ดูรายละเอียด")
                },
                key="sam_aff_table"
            )

        else:
            st.markdown("##### 🔨 รายการทรัพย์ประมูลของ SAM (Auction Watchlist)")
            auc_df = sam_all[sam_all['ประเภทการขาย'].astype(str).str.contains('ประมูล', na=False)].copy().sort_values('ราคา', ascending=False)
            
            st.warning(f"🔨 มีทรัพย์สินที่ต้องเข้าประมูลทั้งหมด **{len(auc_df):,}** รายการ มูลค่ารวม **฿{auc_df['ราคา'].sum()/1e6:,.1f} ล้านบาท**")
            
            auc_df['ขนาด'] = auc_df['พื้นที่_ตารางวา'].apply(format_rai_ngan_wah)
            st.dataframe(
                auc_df[['รหัสทรัพย์', 'ประเภททรัพย์', 'ชื่อประกาศ', 'ราคา', 'ขนาด', 'อำเภอ', 'จังหวัด', 'ลิงก์']],
                use_container_width=True,
                column_config={
                    "ราคา": st.column_config.NumberColumn("ราคาเริ่มต้นประมูล (บาท)", format="฿%,d"),
                    "ลิงก์": st.column_config.LinkColumn("เว็บ SAM", display_text="🔗 เข้าร่วมประมูล")
                },
                key="sam_auc_table"
            )

    # =========================================================================
    # SUB-TAB 5: ค้นหาทรัพย์ SAM เจาะลึก & ส่งออก (EXPLORER & EXPORT)
    # =========================================================================
    with sam_sub5:
        st.markdown("#### 🔍 ระบบค้นหาทรัพย์ SAM เจาะลึก และส่งออกข้อมูล")
        st.caption("ค้นหาตามรหัสทรัพย์, ชื่อโครงการ, ทำเล พร้อมระบบ Export ไฟล์ Excel / CSV")

        # Live search bar for SAM
        sam_search_txt = st.text_input(
            "🔎 พิมพ์คำค้นหา (รหัสทรัพย์ เช่น 3A1291, ชื่อโครงการ, ตำบล, อำเภอ, จังหวัด):",
            value="",
            placeholder="เช่น 3A0424, บุรีรัมย์, คลองหลวง, บ้านเดี่ยว...",
            key="sam_explorer_search_input"
        )

        sam_res = sam_filtered.copy()
        if sam_search_txt:
            q = sam_search_txt.strip().lower()
            m1 = sam_res['รหัสทรัพย์'].astype(str).str.lower().str.contains(q, na=False)
            m2 = sam_res['ชื่อประกาศ'].astype(str).str.lower().str.contains(q, na=False)
            m3 = sam_res['ชื่อโครงการ'].astype(str).str.lower().str.contains(q, na=False)
            m4 = sam_res['จังหวัด'].astype(str).str.lower().str.contains(q, na=False)
            m5 = sam_res['อำเภอ'].astype(str).str.lower().str.contains(q, na=False)
            m6 = sam_res['ตำบล'].astype(str).str.lower().str.contains(q, na=False)
            m7 = sam_res['ประเภททรัพย์'].astype(str).str.lower().str.contains(q, na=False)
            sam_res = sam_res[m1 | m2 | m3 | m4 | m5 | m6 | m7]

        st.markdown(f"**ผลการค้นหา: พบ {len(sam_res):,} รายการ**")

        # Prepare rich display table
        sam_table_show = sam_res[[
            'รหัสทรัพย์', 'ประเภททรัพย์', 'ประเภทการขาย', 'ราคา', 
            'ตำบล', 'อำเภอ', 'จังหวัด', 'เนื้อที่ (ตร.ว.)', 'พื้นที่_ตารางวา', 
            'พื้นที่ใช้สอย (ตร.ม.)', 'ชื่อประกาศ', 'ลิงก์'
        ]].copy()

        sam_table_show['ราคาขาย (บาท)'] = sam_table_show['ราคา']
        sam_table_show['ขนาดที่ดิน'] = sam_table_show['พื้นที่_ตารางวา'].apply(format_rai_ngan_wah)

        cols_order = [
            'รหัสทรัพย์', 'ประเภททรัพย์', 'ประเภทการขาย', 'ราคาขาย (บาท)', 
            'ขนาดที่ดิน', 'พื้นที่ใช้สอย (ตร.ม.)', 'ตำบล', 'อำเภอ', 'จังหวัด', 
            'ชื่อประกาศ', 'ลิงก์'
        ]
        sam_table_show = sam_table_show[cols_order]

        st.dataframe(
            sam_table_show,
            use_container_width=True,
            column_config={
                "ราคาขาย (บาท)": st.column_config.NumberColumn("ราคาขาย (บาท)", format="฿%,d"),
                "พื้นที่ใช้สอย (ตร.ม.)": st.column_config.NumberColumn(format="%.1f"),
                "ลิงก์": st.column_config.LinkColumn("หน้าประกาศเว็บ SAM", display_text="🔗 เปิดดูทรัพย์")
            },
            height=450,
            key="sam_explorer_table"
        )

        # Export Section
        st.markdown("<br/>", unsafe_allow_html=True)
        st.markdown("##### 📥 ส่งออกข้อมูลทรัพย์ SAM (Export SAM NPA Data)")
        
        exp_col1, exp_col2 = st.columns(2)
        with exp_col1:
            csv_data = sam_res.to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                label=f"📄 ดาวน์โหลด CSV ({len(sam_res):,} รายการ) ⚡",
                data=csv_data,
                file_name=f"SAM_NPA_Analysis_{pd.Timestamp.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True,
                key="btn_download_sam_csv"
            )
            
        with exp_col2:
            excel_buffer = io.BytesIO()
            with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                sam_res.to_excel(writer, index=False, sheet_name='SAM_Assets')
            st.download_button(
                label=f"📊 ดาวน์โหลด Excel (.xlsx) ({len(sam_res):,} รายการ)",
                data=excel_buffer.getvalue(),
                file_name=f"SAM_NPA_Analysis_{pd.Timestamp.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                key="btn_download_sam_excel"
            )
