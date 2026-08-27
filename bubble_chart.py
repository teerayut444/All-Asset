import os
import math
import base64
import pandas as pd
import numpy as np

def format_price_thai(val):
    if pd.isna(val) or val == 0:
        return "฿0 บาท"
    if val >= 1_000_000_000:
        return f"฿{val / 1_000_000_000:,.2f} พันล้าน"
    elif val >= 1_000_000:
        return f"฿{val / 1_000_000:,.1f} ล้าน"
    elif val >= 1_000:
        return f"฿{val / 1_000:,.0f} พัน"
    return f"฿{val:,.0f} บาท"

def get_company_logo_data_uri(comp_id):
    """Loads base64 Data URI of official original logo from assets/logos/ fresh from disk."""
    target = comp_id.lower()
    
    # Priority order for file extensions
    for ext in ['.png', '.svg', '.webp', '.jpg', '.jpeg']:
        for fname in [f"{target}{ext}", f"{target.upper()}{ext}", f"{target.capitalize()}{ext}"]:
            p = os.path.join('assets', 'logos', fname)
            if os.path.exists(p):
                try:
                    mime = 'image/svg+xml' if ext == '.svg' else f"image/{ext.replace('.', '')}"
                    with open(p, 'rb') as f:
                        b64 = base64.b64encode(f.read()).decode('utf-8')
                    return f'data:{mime};base64,{b64}'
                except Exception:
                    pass
                
    fallback = "data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjQiIGhlaWdodD0iMjQiIHZpZXdCb3g9IjAgMCAyNCAyNCIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48Y2lyY2xlIGN4PSIxMiIgY3k9IjEyIiIgcj0iMTAiIGZpbGw9IiM2NDc0OGIiLz48L3N2Zz4="
    return fallback

def generate_3d_glossy_bubble_chart_html(df_filtered, bubble_metric="สัดส่วนตามจำนวนทรัพย์สิน (Asset Count)", is_dark_mode=False):
    """
    Generates an interactive, responsive 3D Glossy Bubble Chart HTML component
    strictly divided into 4 distinct sectors across a 1680px canvas:
    1. บริษัทบริหารสินทรัพย์ (Asset Management Companies / AMC)
    2. สถาบันการเงิน / ธนาคาร (Financial Institutions / Banks)
    3. เว็บไซต์ / แพลตฟอร์มอสังหาริมทรัพย์ (Portals & Marketplaces)
    4. หน่วยงานภาครัฐ / ขายทอดตลาด (Government & Public Auction / LED)
    """
    companies_meta = [
        # ================= SECTOR 1: GOVERNMENT (หน่วยงานภาครัฐ / ทอดตลาด) =================
        {
            "id": "led",
            "name": "LED",
            "label": "LED กรมบังคับคดี",
            "sector": "gov",
            "base_cx": 185, "base_cy": 365,
            "scraped_grad": "led-scraped",
            "float_dur": "7.0s",
            "color_hex": "#0891b2"
        },

        # ================= SECTOR 2: AMC (บริษัทบริหารสินทรัพย์) =================
        {
            "id": "sam",
            "name": "SAM",
            "label": "SAM NPA",
            "sector": "amc",
            "base_cx": 495, "base_cy": 250,
            "scraped_grad": "sam-scraped",
            "float_dur": "8.2s",
            "color_hex": "#10b981"
        },
        {
            "id": "bam",
            "name": "BAM",
            "label": "BAM NPA",
            "sector": "amc",
            "base_cx": 495, "base_cy": 485,
            "scraped_grad": "bam-scraped",
            "float_dur": "6.0s",
            "color_hex": "#3b82f6"
        },
        {
            "id": "chayo555",
            "name": "Chayo555",
            "label": "Chayo555 NPA",
            "sector": "amc",
            "base_cx": 645, "base_cy": 365,
            "scraped_grad": "chayo555-scraped",
            "float_dur": "7.5s",
            "color_hex": "#f97316"
        },

        # ================= SECTOR 3: BANKS (สถาบันการเงิน / ธนาคาร) =================
        {
            "id": "kbank",
            "name": "KBANK",
            "label": "KBANK NPA",
            "sector": "bank",
            "base_cx": 885, "base_cy": 240,
            "scraped_grad": "kbank-scraped",
            "float_dur": "7.2s",
            "color_hex": "#059669"
        },
        {
            "id": "gsb",
            "name": "GSB",
            "label": "GSB NPA",
            "sector": "bank",
            "base_cx": 1135, "base_cy": 240,
            "scraped_grad": "gsb-scraped",
            "float_dur": "7.4s",
            "color_hex": "#eb1985"
        },
        {
            "id": "ghb",
            "name": "GHB",
            "label": "GHB NPA",
            "sector": "bank",
            "base_cx": 1010, "base_cy": 365,
            "scraped_grad": "ghb-scraped",
            "float_dur": "6.8s",
            "color_hex": "#ca8a04"
        },
        {
            "id": "scb",
            "name": "SCB",
            "label": "SCB NPA",
            "sector": "bank",
            "base_cx": 885, "base_cy": 490,
            "scraped_grad": "scb-scraped",
            "float_dur": "7.0s",
            "color_hex": "#7e22ce"
        },
        {
            "id": "ktb",
            "name": "KTB",
            "label": "KTB NPA",
            "sector": "bank",
            "base_cx": 1135, "base_cy": 490,
            "scraped_grad": "ktb-scraped",
            "float_dur": "6.2s",
            "color_hex": "#0284c7"
        },

        # ================= SECTOR 4: PORTALS (เว็บไซต์ / แพลตฟอร์ม) =================
        {
            "id": "zmyhome",
            "name": "ZmyHome",
            "label": "ZmyHome NPA",
            "sector": "portal",
            "base_cx": 1360, "base_cy": 220,
            "scraped_grad": "zmyhome-scraped",
            "float_dur": "8.0s",
            "color_hex": "#ec4899"
        },
        {
            "id": "baania",
            "name": "Baania",
            "label": "Baania NPA",
            "sector": "portal",
            "base_cx": 1360, "base_cy": 480,
            "scraped_grad": "baania-scraped",
            "float_dur": "7.5s",
            "color_hex": "#f59e0b"
        },
        {
            "id": "nayoo",
            "name": "NaYoo",
            "label": "NaYoo NPA",
            "sector": "portal",
            "base_cx": 1560, "base_cy": 220,
            "scraped_grad": "nayoo-scraped",
            "float_dur": "6.5s",
            "color_hex": "#8b5cf6"
        },
        {
            "id": "ddproperty",
            "name": "DDproperty",
            "label": "DDproperty",
            "sector": "portal",
            "base_cx": 1560, "base_cy": 480,
            "scraped_grad": "ddproperty-scraped",
            "float_dur": "7.2s",
            "color_hex": "#a855f7"
        },
        {
            "id": "livinginsider",
            "name": "Livinginsider",
            "label": "Livinginsider",
            "sector": "portal",
            "base_cx": 1460, "base_cy": 350,
            "scraped_grad": "livinginsider-scraped",
            "float_dur": "6.8s",
            "color_hex": "#14b8a6"
        }
    ]

    total_market_count = len(df_filtered) if df_filtered is not None else 0
    valid_prices = df_filtered['ราคา'].dropna() if df_filtered is not None and not df_filtered.empty else pd.Series()
    total_market_val = valid_prices.sum() if not valid_prices.empty else 0.0

    is_count_metric = ("จำนวน" in str(bubble_metric))

    # Calculate 4 sector-level aggregates with Government on the leftmost position
    sector_meta = {
        "gov": {
            "title": "หน่วยงานภาครัฐ",
            "subtitle": "Government & Public Auction",
            "icon": "⚖️",
            "color": "#0891b2",
            "glow": "rgba(8, 145, 178, 0.25)",
            "bg_border": "rgba(8, 145, 178, 0.35)",
            "bg_tint": "rgba(8, 145, 178, 0.04)" if not is_dark_mode else "rgba(8, 145, 178, 0.08)",
            "x": 20, "y": 75, "w": 330, "h": 580,
            "count": 0, "val": 0.0
        },
        "amc": {
            "title": "บริษัทบริหารสินทรัพย์",
            "subtitle": "Asset Management (AMC)",
            "icon": "🏢",
            "color": "#10b981",
            "glow": "rgba(16, 185, 129, 0.25)",
            "bg_border": "rgba(16, 185, 129, 0.35)",
            "bg_tint": "rgba(16, 185, 129, 0.04)" if not is_dark_mode else "rgba(16, 185, 129, 0.08)",
            "x": 370, "y": 75, "w": 380, "h": 580,
            "count": 0, "val": 0.0
        },
        "bank": {
            "title": "สถาบันการเงิน",
            "subtitle": "Banks & Financial Institutions",
            "icon": "🏦",
            "color": "#3b82f6",
            "glow": "rgba(59, 130, 246, 0.25)",
            "bg_border": "rgba(59, 130, 246, 0.35)",
            "bg_tint": "rgba(59, 130, 246, 0.04)" if not is_dark_mode else "rgba(59, 130, 246, 0.08)",
            "x": 770, "y": 75, "w": 480, "h": 580,
            "count": 0, "val": 0.0
        },
        "portal": {
            "title": "เว็บไซต์สื่อกลาง",
            "subtitle": "Portals & Marketplaces",
            "icon": "🌐",
            "color": "#8b5cf6",
            "glow": "rgba(139, 92, 246, 0.25)",
            "bg_border": "rgba(139, 92, 246, 0.35)",
            "bg_tint": "rgba(139, 92, 246, 0.04)" if not is_dark_mode else "rgba(139, 92, 246, 0.08)",
            "x": 1270, "y": 75, "w": 390, "h": 580,
            "count": 0, "val": 0.0
        }
    }

    # Aggregate company stats
    comp_stats = {}
    for comp in companies_meta:
        comp_name = comp["name"]
        comp_df = df_filtered[df_filtered['บริษัท'] == comp_name] if df_filtered is not None and not df_filtered.empty else pd.DataFrame()
        c_count = len(comp_df)
        c_prices = comp_df['ราคา'].dropna() if not comp_df.empty else pd.Series()
        c_val = c_prices.sum() if not c_prices.empty else 0.0
        
        comp_stats[comp["id"]] = {
            "count": c_count,
            "val": c_val,
            "df": comp_df
        }
        
        sec = comp["sector"]
        if sec in sector_meta:
            sector_meta[sec]["count"] += c_count
            sector_meta[sec]["val"] += c_val

    bubbles_html_list = []
    keyframes_list = []
    hover_classes_list = []

    for comp in companies_meta:
        st = comp_stats.get(comp["id"], {"count": 0, "val": 0.0, "df": pd.DataFrame()})
        c_count = st["count"]
        if c_count == 0:
            continue

        c_val = st["val"]
        comp_df = st["df"]
        
        pct_count = (c_count / total_market_count * 100) if total_market_count > 0 else 0.0
        pct_val = (c_val / total_market_val * 100) if total_market_val > 0 else 0.0
        
        active_pct = pct_count if is_count_metric else pct_val
        active_fraction = active_pct / 100.0
        
        if active_fraction > 0:
            radius = int(48 + 76 * math.sqrt(active_fraction))
            radius = max(48, min(108, radius))
        else:
            radius = 48

        cx, cy = comp["base_cx"], comp["base_cy"]
        bubble_id = f"bubble-{comp['id']}"

        # Outer bubble slice & shadow
        slices = f'<g filter="url(#shadow)"><circle cx="{cx}" cy="{cy}" r="{radius}" fill="url(#{comp["scraped_grad"]})" stroke="rgba(255, 255, 255, 0.7)" stroke-width="2.5" /></g>'
        sheen = f'<circle cx="{cx}" cy="{cy}" r="{radius}" fill="none" stroke="rgba(255, 255, 255, 0.45)" stroke-width="2.5" />'
        
        hcx = cx - radius * 0.35
        hcy = cy - radius * 0.35
        hrx = radius * 0.4
        hry = radius * 0.25
        highlight = f'<ellipse cx="{hcx}" cy="{hcy}" rx="{hrx}" ry="{hry}" fill="url(#highlight-grad)" transform="rotate(-30, {hcx}, {hcy})" />'
        
        # Logo badge size
        logo_badge_sz = max(34, min(62, int(radius * 0.52)))
        logo_data_uri = get_company_logo_data_uri(comp["id"])

        title_size = max(10.5, int(radius * 0.125))
        text_size = max(8.0, int(radius * 0.085))
        badge_padding = "1.5px 6px" if radius > 60 else "1px 4px"
        badge_gap = "2px"
        margin_bottom = "2px" if radius > 60 else "1px"

        card_bg_color = "rgba(15, 23, 42, 0.60)" if is_dark_mode else "rgba(255, 255, 255, 0.7)"
        text_title_color = "#f8fafc" if is_dark_mode else "#0f172a"
        text_sub_color = "#94a3b8" if is_dark_mode else "#475569"
        text_val_color = "#ffffff" if is_dark_mode else "#0f172a"

        bubble_body = f"""
            <g class="bubble-group sector-bubble sector-{comp['sector']}" id="{bubble_id}">
                {slices}
                {sheen}
                {highlight}
                <foreignObject x="{cx - radius}" y="{cy - radius}" width="{2*radius}" height="{2*radius}">
                    <div style="width: 100%; height: 100%; display: flex; flex-direction: column; justify-content: center; align-items: center; text-align: center; font-family: 'Outfit', 'Sarabun', sans-serif; pointer-events: none; box-sizing: border-box; padding: 3px; line-height: 1.15; will-change: transform;">
                        <!-- Crisp White Circular Badge Background -->
                        <div style="background: rgba(255, 255, 255, 0.96); border-radius: 50%; width: {logo_badge_sz}px; height: {logo_badge_sz}px; display: flex; justify-content: center; align-items: center; box-shadow: 0 3px 10px rgba(0,0,0,0.18), 0 1px 3px rgba(0,0,0,0.1); border: 2px solid #ffffff; margin-bottom: 2px; overflow: hidden; padding: 2px; box-sizing: border-box;">
                            <img src="{logo_data_uri}" style="max-width: 90%; max-height: 90%; width: 90%; height: 90%; object-fit: contain;" alt="{comp['name']}" />
                        </div>
                        
                        <!-- Title -->
                        <div style="font-weight: 800; font-size: {title_size}px; color: {text_title_color}; letter-spacing: -0.3px; margin-bottom: 2px; text-transform: uppercase;">
                            {comp['name']}
                        </div>
                        
                        <!-- Stats: จำนวนทรัพย์ -->
                        <div style="background: {card_bg_color}; backdrop-filter: blur(4px); border-radius: 18px; padding: {badge_padding}; display: inline-flex; align-items: center; gap: {badge_gap}; margin-bottom: {margin_bottom}; border: 1px solid rgba(255, 255, 255, 0.4); box-shadow: 0 2px 4px rgba(0, 0, 0, 0.04);">
                            <span style="font-size: {text_size - 1.2}px; color: {text_sub_color}; font-weight: 600;">ทรัพย์สิน</span>
                            <span style="font-size: {text_size}px; color: {text_val_color}; font-weight: 800;">{c_count:,} <span style="color: #6366f1; font-weight: 700;">({pct_count:.1f}%)</span></span>
                        </div>
                        
                        <!-- Stats: มูลค่ารวม -->
                        <div style="background: {card_bg_color}; backdrop-filter: blur(4px); border-radius: 18px; padding: {badge_padding}; display: inline-flex; align-items: center; gap: {badge_gap}; border: 1px solid rgba(255, 255, 255, 0.4); box-shadow: 0 2px 4px rgba(0, 0, 0, 0.04);">
                            <span style="font-size: {text_size - 1.2}px; color: {text_sub_color}; font-weight: 600;">มูลค่า</span>
                            <span style="font-size: {text_size}px; color: {text_val_color}; font-weight: 800;">{format_price_thai(c_val)}</span>
                        </div>
                    </div>
                </foreignObject>
            </g>
        """

        bubbles_html_list.append(f"""
        <g class="float-wrapper float-{bubble_id}">
            {bubble_body}
        </g>
        """)

        hover_classes_list.append(f"#{bubble_id} {{ transform-origin: {cx}px {cy}px; }}")
        
        anim_name = f"float-{comp['id']}-anim"
        dx = 3 if comp["base_cx"] > 800 else -3
        dy = -5 if comp["base_cy"] > 350 else 5
        keyframes_list.append(f"""
        @keyframes {anim_name} {{
            0% {{ transform: translate(0px, 0px); }}
            50% {{ transform: translate({dx}px, {dy}px); }}
            100% {{ transform: translate(0px, 0px); }}
        }}
        .float-{bubble_id} {{
            animation: {anim_name} {comp['float_dur']} ease-in-out infinite;
        }}
        """)

    # Build 4 Sector Backdrop Panels (Pods)
    sector_pods_svg = []
    for s_key, s_data in sector_meta.items():
        s_cnt = s_data["count"]
        s_val = s_data["val"]
        s_pct_cnt = (s_cnt / total_market_count * 100) if total_market_count > 0 else 0.0
        s_pct_val = (s_val / total_market_val * 100) if total_market_val > 0 else 0.0
        
        stat_display = f"{s_cnt:,} รายการ ({s_pct_cnt:.1f}%)" if is_count_metric else f"{format_price_thai(s_val)} ({s_pct_val:.1f}%)"
        
        bg_card = "rgba(30, 41, 59, 0.45)" if is_dark_mode else "rgba(255, 255, 255, 0.65)"
        title_c = "#f8fafc" if is_dark_mode else "#0f172a"
        border_c = s_data["bg_border"]
        
        pod_svg = f"""
        <g class="sector-pod-group sector-pod-{s_key}" id="pod-{s_key}">
            <!-- Glassmorphic Pod Container Box -->
            <rect x="{s_data['x']}" y="{s_data['y']}" width="{s_data['w']}" height="{s_data['h']}" rx="24" ry="24" 
                  fill="{s_data['bg_tint']}" stroke="{border_c}" stroke-width="1.8" stroke-dasharray="none" />
                  
            <!-- Top Sector Header Tab -->
            <foreignObject x="{s_data['x']}" y="{s_data['y'] - 14}" width="{s_data['w']}" height="76">
                <div style="width: 100%; display: flex; flex-direction: column; align-items: center; text-align: center; font-family: 'Outfit', 'Sarabun', sans-serif; pointer-events: auto;">
                    <div style="background: {bg_card}; backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px); border: 1.5px solid {s_data['color']}; border-radius: 20px; padding: 4px 16px; box-shadow: 0 4px 16px {s_data['glow']}; display: inline-flex; align-items: center; gap: 8px;">
                        <span style="font-size: 16px;">{s_data['icon']}</span>
                        <div style="text-align: left;">
                            <div style="font-weight: 800; font-size: 13px; color: {title_c}; line-height: 1.15; letter-spacing: -0.2px;">
                                {s_data['title']}
                            </div>
                            <div style="font-size: 10px; color: {s_data['color']}; font-weight: 700;">
                                {stat_display}
                            </div>
                        </div>
                    </div>
                </div>
            </foreignObject>
        </g>
        """
        sector_pods_svg.append(pod_svg)

    svg_content = f"""
    <svg viewBox="0 0 1680 680" width="100%" height="100%" preserveAspectRatio="xMidYMid meet" xmlns="http://www.w3.org/2000/svg" style="background-color: transparent; max-width: 100%; height: auto;">
      <defs>
        <filter id="shadow" x="-30%" y="-30%" width="160%" height="160%">
          <feDropShadow dx="0" dy="8" stdDeviation="12" flood-color="#0f172a" flood-opacity="{'0.35' if is_dark_mode else '0.15'}"/>
        </filter>
        
        <linearGradient id="highlight-grad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="rgba(255, 255, 255, 0.75)"/>
          <stop offset="100%" stop-color="rgba(255, 255, 255, 0)"/>
        </linearGradient>
        
        <!-- LED Radial Gradient (Cyan/Teal) -->
        <radialGradient id="led-scraped" cx="50%" cy="50%" r="50%" fx="35%" fy="30%">
          <stop offset="0%" stop-color="#ecfeff"/>
          <stop offset="45%" stop-color="#22d3ee"/>
          <stop offset="100%" stop-color="#0891b2"/>
        </radialGradient>

        <!-- NaYoo Radial Gradients (Purple/Violet) -->
        <radialGradient id="nayoo-scraped" cx="50%" cy="50%" r="50%" fx="35%" fy="30%">
          <stop offset="0%" stop-color="#faf5ff"/>
          <stop offset="45%" stop-color="#c084fc"/>
          <stop offset="100%" stop-color="#7e22ce"/>
        </radialGradient>
        
        <!-- ZmyHome Radial Gradients (Pink/Rose) -->
        <radialGradient id="zmyhome-scraped" cx="50%" cy="50%" r="50%" fx="38%" fy="35%">
          <stop offset="0%" stop-color="#fff1f5"/>
          <stop offset="45%" stop-color="#f472b6"/>
          <stop offset="100%" stop-color="#be185d"/>
        </radialGradient>
        
        <!-- BAM Radial Gradients (Blue/Gold) -->
        <radialGradient id="bam-scraped" cx="50%" cy="50%" r="50%" fx="35%" fy="30%">
          <stop offset="0%" stop-color="#eff6ff"/>
          <stop offset="45%" stop-color="#60a5fa"/>
          <stop offset="100%" stop-color="#1d4ed8"/>
        </radialGradient>
        
        <!-- Baania Radial Gradients (Amber/Gold) -->
        <radialGradient id="baania-scraped" cx="50%" cy="50%" r="50%" fx="35%" fy="30%">
          <stop offset="0%" stop-color="#fffdf5"/>
          <stop offset="45%" stop-color="#fbbf24"/>
          <stop offset="100%" stop-color="#d97706"/>
        </radialGradient>
        
        <!-- SAM Radial Gradients (Emerald/Teal) -->
        <radialGradient id="sam-scraped" cx="50%" cy="50%" r="50%" fx="35%" fy="30%">
          <stop offset="0%" stop-color="#f0fdf4"/>
          <stop offset="45%" stop-color="#34d399"/>
          <stop offset="100%" stop-color="#047857"/>
        </radialGradient>

        <!-- Chayo555 Radial Gradients (Orange/Coral) -->
        <radialGradient id="chayo555-scraped" cx="50%" cy="50%" r="50%" fx="35%" fy="30%">
          <stop offset="0%" stop-color="#fff7ed"/>
          <stop offset="45%" stop-color="#fb923c"/>
          <stop offset="100%" stop-color="#ea580c"/>
        </radialGradient>

        <!-- KBANK Standalone Gradient (Green) -->
        <radialGradient id="kbank-scraped" cx="50%" cy="50%" r="50%" fx="35%" fy="30%">
          <stop offset="0%" stop-color="#ecfdf5"/>
          <stop offset="45%" stop-color="#34d399"/>
          <stop offset="100%" stop-color="#059669"/>
        </radialGradient>

        <!-- GHB Standalone Gradient (Gold/Yellow) -->
        <radialGradient id="ghb-scraped" cx="50%" cy="50%" r="50%" fx="35%" fy="30%">
          <stop offset="0%" stop-color="#fefce8"/>
          <stop offset="45%" stop-color="#fde047"/>
          <stop offset="100%" stop-color="#ca8a04"/>
        </radialGradient>

        <!-- SCB Standalone Gradient (Royal Purple) -->
        <radialGradient id="scb-scraped" cx="50%" cy="50%" r="50%" fx="35%" fy="30%">
          <stop offset="0%" stop-color="#faf5ff"/>
          <stop offset="45%" stop-color="#a855f7"/>
          <stop offset="100%" stop-color="#6b21a8"/>
        </radialGradient>

        <!-- KTB Standalone Gradient (Sky Blue) -->
        <radialGradient id="ktb-scraped" cx="50%" cy="50%" r="50%" fx="35%" fy="30%">
          <stop offset="0%" stop-color="#f0f9ff"/>
          <stop offset="45%" stop-color="#38bdf8"/>
          <stop offset="100%" stop-color="#0284c7"/>
        </radialGradient>

        <!-- GSB Standalone Gradient (Vivid Pink) -->
        <radialGradient id="gsb-scraped" cx="50%" cy="50%" r="50%" fx="35%" fy="30%">
          <stop offset="0%" stop-color="#fdf2f8"/>
          <stop offset="45%" stop-color="#f472b6"/>
          <stop offset="100%" stop-color="#db2777"/>
        </radialGradient>

        <!-- DDproperty Standalone Gradient (Purple/Violet) -->
        <radialGradient id="ddproperty-scraped" cx="50%" cy="50%" r="50%" fx="35%" fy="30%">
          <stop offset="0%" stop-color="#faf5ff"/>
          <stop offset="45%" stop-color="#c084fc"/>
          <stop offset="100%" stop-color="#9333ea"/>
        </radialGradient>

        <!-- Livinginsider Standalone Gradient (Teal) -->
        <radialGradient id="livinginsider-scraped" cx="50%" cy="50%" r="50%" fx="35%" fy="30%">
          <stop offset="0%" stop-color="#f0fdfa"/>
          <stop offset="45%" stop-color="#2dd4bf"/>
          <stop offset="100%" stop-color="#0d9488"/>
        </radialGradient>
      </defs>
      
      <!-- 4 Sector Glass Pods in Background -->
      {''.join(sector_pods_svg)}

      <!-- 3D Bubbles on Top of Pods -->
      {''.join(bubbles_html_list)}
    </svg>
    """

    hover_css = "\n".join(hover_classes_list)
    keyframes_css = "\n".join(keyframes_list)

    # Sector Filter Bar HTML for instantaneous interactive switching (4 sectors)
    filter_bar_html = f"""
    <div class="sector-filter-nav">
        <button class="nav-btn active" onclick="filterSector('all')">🏛️ แสดงทุกกลุ่ม ({total_market_count:,})</button>
        <button class="nav-btn btn-gov" onclick="filterSector('gov')">⚖️ หน่วยงานภาครัฐ ({sector_meta['gov']['count']:,})</button>
        <button class="nav-btn btn-amc" onclick="filterSector('amc')">🏢 บริษัทบริหารสินทรัพย์ AMC ({sector_meta['amc']['count']:,})</button>
        <button class="nav-btn btn-bank" onclick="filterSector('bank')">🏦 สถาบันการเงิน / ธนาคาร ({sector_meta['bank']['count']:,})</button>
        <button class="nav-btn btn-portal" onclick="filterSector('portal')">🌐 เว็บไซต์ / แพลตฟอร์ม ({sector_meta['portal']['count']:,})</button>
    </div>
    """

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@400;600;700;800;900&family=Sarabun:wght@400;600;700;800&display=swap');
        * {{
            box-sizing: border-box;
        }}
        html, body {{
            margin: 0;
            padding: 4px 10px 10px 10px;
            background: transparent;
            overflow: hidden;
            width: 100%;
            height: auto;
            user-select: none;
            display: flex;
            flex-direction: column;
            align-items: center;
        }}
        .sector-filter-nav {{
            display: flex;
            gap: 10px;
            margin-top: 2px;
            margin-bottom: 12px;
            z-index: 100;
            flex-wrap: wrap;
            justify-content: center;
            width: 100%;
        }}
        .nav-btn {{
            background: {'rgba(30, 41, 59, 0.7)' if is_dark_mode else 'rgba(255, 255, 255, 0.85)'};
            backdrop-filter: blur(8px);
            border: 1px solid {'#334155' if is_dark_mode else '#cbd5e1'};
            color: {'#cbd5e1' if is_dark_mode else '#475569'};
            border-radius: 20px;
            padding: 4px 14px;
            font-size: 12px;
            font-weight: 700;
            font-family: 'Outfit', 'Sarabun', sans-serif;
            cursor: pointer;
            transition: all 0.25s ease;
            box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        }}
        .nav-btn:hover {{
            transform: translateY(-1px);
            border-color: #6366f1;
            color: #6366f1;
        }}
        .nav-btn.active {{
            background: #2563eb;
            border-color: #2563eb;
            color: #ffffff;
            box-shadow: 0 4px 12px rgba(37, 99, 235, 0.3);
        }}
        .nav-btn.btn-amc.active {{
            background: #10b981;
            border-color: #10b981;
            box-shadow: 0 4px 12px rgba(16, 185, 129, 0.3);
        }}
        .nav-btn.btn-bank.active {{
            background: #3b82f6;
            border-color: #3b82f6;
            box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);
        }}
        .nav-btn.btn-portal.active {{
            background: #8b5cf6;
            border-color: #8b5cf6;
            box-shadow: 0 4px 12px rgba(139, 92, 246, 0.3);
        }}
        .nav-btn.btn-gov.active {{
            background: #0891b2;
            border-color: #0891b2;
            box-shadow: 0 4px 12px rgba(8, 145, 178, 0.3);
        }}
        .chart-container {{
            width: 100%;
            display: flex;
            justify-content: center;
            align-items: center;
            margin: 0 auto;
        }}
        svg {{
            width: 100%;
            height: auto;
            max-height: 680px;
            display: block;
            overflow: visible;
        }}
        .bubble-group {{
            cursor: pointer;
            transition: transform 0.4s cubic-bezier(0.34, 1.56, 0.64, 1), filter 0.3s ease, opacity 0.3s ease;
        }}
        .bubble-group:hover {{
            transform: scale(1.08);
            filter: brightness(1.08) drop-shadow(0 15px 25px rgba(0,0,0,0.25));
        }}
        .sector-pod-group {{
            transition: opacity 0.35s ease, transform 0.35s ease;
        }}
        .dimmed {{
            opacity: 0.18 !important;
            filter: grayscale(80%) !important;
            pointer-events: none !important;
        }}
        {hover_css}
        {keyframes_css}
    </style>
    <script>
        function filterSector(sec) {{
            document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
            event.target.classList.add('active');
            
            const pods = document.querySelectorAll('.sector-pod-group');
            const bubbles = document.querySelectorAll('.sector-bubble');
            
            if (sec === 'all') {{
                pods.forEach(p => p.classList.remove('dimmed'));
                bubbles.forEach(b => b.classList.remove('dimmed'));
            }} else {{
                pods.forEach(p => {{
                    if (p.classList.contains('sector-pod-' + sec)) {{
                        p.classList.remove('dimmed');
                    }} else {{
                        p.classList.add('dimmed');
                    }}
                }});
                bubbles.forEach(b => {{
                    if (b.classList.contains('sector-' + sec)) {{
                        b.classList.remove('dimmed');
                    }} else {{
                        b.classList.add('dimmed');
                    }}
                }});
            }}
        }}
    </script>
    </head>
    <body>
        {filter_bar_html}
        <div class="chart-container">
            {svg_content}
        </div>
    </body>
    </html>
    """
    return html_content

