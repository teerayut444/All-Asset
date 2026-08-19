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
    alias_map = {
        'sub-led': 'led',
        'sub-est': 'taladnudbaan',
        'sub-jam': 'bay',
        'sub-others': 'bay'
    }
    target = alias_map.get(comp_id, comp_id).lower()
    
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

def get_tnb_subinstitutions(df_tnb):
    """Extracts and summarizes sub-companies / institutions inside Taladnudbaan with accurately computed sub-circles."""
    if df_tnb is None or df_tnb.empty:
        return []
    
    def parse_inst(u):
        if pd.isna(u): return "อื่นๆ"
        parts = str(u).split('/')
        if len(parts) >= 6:
            code = parts[5].strip().upper()
            mapping = {
                "LED": "LED",
                "EST": "EST",
                "JAM": "JAM",
                "BAY": "BAY",
                "TTB": "TTB",
                "SWP": "SWP",
                "ALPHA": "ALPHA",
                "PAMCO": "PAMCO",
                "GSB": "GSB",
                "IBANK": "IBANK",
                "IAM": "IAM",
                "SME": "SME"
            }
            return mapping.get(code, code)
        return "อื่นๆ"
    
    inst_series = df_tnb['ลิงก์'].apply(parse_inst)
    counts = inst_series.value_counts()
    total = len(df_tnb)
    
    c_led = counts.get("LED", 0)
    c_est = counts.get("EST", 0)
    c_jam = counts.get("JAM", 0)
    c_others = total - (c_led + c_est + c_jam)
    if c_others < 0: c_others = 0
    
    sub_data = [
        {
            "id": "sub-led",
            "name": "LED",
            "sub": "กรมบังคับคดี",
            "count": c_led,
            "pct": (c_led / total * 100) if total > 0 else 0,
            "rel_x": -68, "rel_y": 26, "r": 96,
            "grad": "sub-led-grad",
            "border": "#0891b2"
        },
        {
            "id": "sub-est",
            "name": "EST",
            "sub": "อสังหาฯ/นายหน้า",
            "count": c_est,
            "pct": (c_est / total * 100) if total > 0 else 0,
            "rel_x": 78, "rel_y": -65, "r": 60,
            "grad": "sub-est-grad",
            "border": "#059669"
        },
        {
            "id": "sub-others",
            "name": "อื่นๆ",
            "sub": "BAY/TTB/AMC",
            "count": c_others,
            "pct": (c_others / total * 100) if total > 0 else 0,
            "rel_x": -22, "rel_y": -118, "r": 54,
            "grad": "sub-others-grad",
            "border": "#d97706"
        },
        {
            "id": "sub-jam",
            "name": "JAM",
            "sub": "บส. เจ เอ็ม ที",
            "count": c_jam,
            "pct": (c_jam / total * 100) if total > 0 else 0,
            "rel_x": 76, "rel_y": 66, "r": 54,
            "grad": "sub-jam-grad",
            "border": "#7c3aed"
        }
    ]
    return sub_data

def generate_3d_glossy_bubble_chart_html(df_filtered, bubble_metric="สัดส่วนตามจำนวนทรัพย์สิน (Asset Count)", is_dark_mode=False):
    """
    Generates an interactive, responsive 3D Glossy Bubble Chart HTML component
    matching the AMC NPA Monitor style for all active property companies & financial institutions,
    featuring updated high-definition official logo badges.
    """
    companies_meta = [
        {
            "id": "taladnudbaan",
            "name": "Taladnudbaan",
            "label": "Taladnudbaan NPA",
            "base_cx": 560, "base_cy": 330,
            "scraped_grad": "taladnudbaan-outer-grad",
            "float_dur": "7s",
            "color_hex": "#06b6d4",
            "is_tnb": True
        },
        {
            "id": "zmyhome",
            "name": "ZmyHome",
            "label": "ZmyHome NPA",
            "base_cx": 160, "base_cy": 200,
            "scraped_grad": "zmyhome-scraped",
            "float_dur": "8s",
            "color_hex": "#ec4899",
            "is_tnb": False
        },
        {
            "id": "bam",
            "name": "BAM",
            "label": "BAM NPA",
            "base_cx": 170, "base_cy": 470,
            "scraped_grad": "bam-scraped",
            "float_dur": "6s",
            "color_hex": "#3b82f6",
            "is_tnb": False
        },
        {
            "id": "kbank",
            "name": "KBANK",
            "label": "KBANK NPA",
            "base_cx": 360, "base_cy": 110,
            "scraped_grad": "kbank-scraped",
            "float_dur": "7.2s",
            "color_hex": "#059669",
            "is_tnb": False
        },
        {
            "id": "nayoo",
            "name": "NaYoo",
            "label": "NaYoo NPA",
            "base_cx": 950, "base_cy": 180,
            "scraped_grad": "nayoo-scraped",
            "float_dur": "6.5s",
            "color_hex": "#8b5cf6",
            "is_tnb": False
        },
        {
            "id": "baania",
            "name": "Baania",
            "label": "Baania NPA",
            "base_cx": 860, "base_cy": 490,
            "scraped_grad": "baania-scraped",
            "float_dur": "7.5s",
            "color_hex": "#f59e0b",
            "is_tnb": False
        },
        {
            "id": "sam",
            "name": "SAM",
            "label": "SAM NPA",
            "base_cx": 1070, "base_cy": 330,
            "scraped_grad": "sam-scraped",
            "float_dur": "8.5s",
            "color_hex": "#10b981",
            "is_tnb": False
        },
        {
            "id": "chayo555",
            "name": "Chayo555",
            "label": "Chayo555 NPA",
            "base_cx": 1040, "base_cy": 500,
            "scraped_grad": "chayo555-scraped",
            "float_dur": "7.8s",
            "color_hex": "#f97316",
            "is_tnb": False
        },
        {
            "id": "ghb",
            "name": "GHB",
            "label": "GHB NPA",
            "base_cx": 740, "base_cy": 110,
            "scraped_grad": "ghb-scraped",
            "float_dur": "6.8s",
            "color_hex": "#ca8a04",
            "is_tnb": False
        },
        {
            "id": "scb",
            "name": "SCB",
            "label": "SCB NPA",
            "base_cx": 930, "base_cy": 350,
            "scraped_grad": "scb-scraped",
            "float_dur": "7.0s",
            "color_hex": "#7e22ce",
            "is_tnb": False
        },
        {
            "id": "ktb",
            "name": "KTB",
            "label": "KTB NPA",
            "base_cx": 370, "base_cy": 530,
            "scraped_grad": "ktb-scraped",
            "float_dur": "6.2s",
            "color_hex": "#0284c7",
            "is_tnb": False
        }
    ]

    total_market_count = len(df_filtered) if df_filtered is not None else 0
    valid_prices = df_filtered['ราคา'].dropna() if df_filtered is not None and not df_filtered.empty else pd.Series()
    total_market_val = valid_prices.sum() if not valid_prices.empty else 0.0

    is_count_metric = ("จำนวน" in str(bubble_metric))

    bubbles_html_list = []
    keyframes_list = []
    hover_classes_list = []

    for comp in companies_meta:
        comp_name = comp["name"]
        comp_df = df_filtered[df_filtered['บริษัท'] == comp_name] if df_filtered is not None and not df_filtered.empty else pd.DataFrame()
        
        c_count = len(comp_df)
        if c_count == 0:
            continue

        c_prices = comp_df['ราคา'].dropna() if not comp_df.empty else pd.Series()
        c_val = c_prices.sum() if not c_prices.empty else 0.0
        
        pct_count = (c_count / total_market_count * 100) if total_market_count > 0 else 0.0
        pct_val = (c_val / total_market_val * 100) if total_market_val > 0 else 0.0
        
        active_pct = pct_count if is_count_metric else pct_val
        active_fraction = active_pct / 100.0
        
        if comp.get("is_tnb"):
            radius = 185
        else:
            if active_fraction > 0:
                radius = int(48 + 95 * math.sqrt(active_fraction))
                radius = max(48, min(118, radius))
            else:
                radius = 45

        cx, cy = comp["base_cx"], comp["base_cy"]
        bubble_id = f"bubble-{comp['id']}"

        # Outer bubble slice & shadow
        slices = f'<g filter="url(#shadow)"><circle cx="{cx}" cy="{cy}" r="{radius}" fill="url(#{comp["scraped_grad"]})" stroke="rgba(255, 255, 255, 0.6)" stroke-width="2.5" /></g>'
        sheen = f'<circle cx="{cx}" cy="{cy}" r="{radius}" fill="none" stroke="rgba(255, 255, 255, 0.45)" stroke-width="2.5" />'
        
        hcx = cx - radius * 0.35
        hcy = cy - radius * 0.35
        hrx = radius * 0.4
        hry = radius * 0.25
        highlight = f'<ellipse cx="{hcx}" cy="{hcy}" rx="{hrx}" ry="{hry}" fill="url(#highlight-grad)" transform="rotate(-30, {hcx}, {hcy})" />'
        
        # Significantly enlarged logo badge size
        logo_badge_sz = max(36, min(68, int(radius * 0.54)))
        logo_data_uri = get_company_logo_data_uri(comp["id"])

        title_size = max(11, int(radius * 0.115))
        text_size = max(8.5, int(radius * 0.08))
        badge_padding = "1.5px 7px" if radius > 70 else "1px 5px"
        badge_gap = "3px" if radius > 70 else "2px"
        margin_bottom = "2px" if radius > 70 else "1px"

        card_bg_color = "rgba(15, 23, 42, 0.55)" if is_dark_mode else "rgba(255, 255, 255, 0.60)"
        text_title_color = "#f8fafc" if is_dark_mode else "#0f172a"
        text_sub_color = "#94a3b8" if is_dark_mode else "#475569"
        text_val_color = "#ffffff" if is_dark_mode else "#0f172a"

        # If this is Taladnudbaan, build tightly packed large 3D sub-bubbles inside!
        if comp.get("is_tnb") and c_count > 0:
            tnb_subs = get_tnb_subinstitutions(comp_df)
            
            nested_circles_svg = []
            for sub in tnb_subs:
                scx = cx + sub['rel_x']
                scy = cy + sub['rel_y']
                sr = sub['r']
                
                # 3D Glossy Sub-Circle
                s_slice = f'<g filter="url(#sub-shadow)"><circle cx="{scx}" cy="{scy}" r="{sr}" fill="url(#{sub["grad"]})" stroke="{sub["border"]}" stroke-width="2" /></g>'
                s_sheen = f'<circle cx="{scx}" cy="{scy}" r="{sr}" fill="none" stroke="rgba(255, 255, 255, 0.7)" stroke-width="2" />'
                
                shcx = scx - sr * 0.35
                shcy = scy - sr * 0.35
                shrx = sr * 0.4
                shry = sr * 0.25
                s_highlight = f'<ellipse cx="{shcx}" cy="{shcy}" rx="{shrx}" ry="{shry}" fill="url(#highlight-grad)" transform="rotate(-30, {shcx}, {shcy})" />'
                
                sub_badge_sz = max(26, min(50, int(sr * 0.48)))
                sub_logo_data = get_company_logo_data_uri(sub["id"])

                # Sub-circle typography
                if sr >= 90:
                    s_title_sz = 13.5
                    s_sub_sz = 9.5
                    s_badge_sz = 11.5
                    s_pct_sz = 10.5
                elif sr >= 58:
                    s_title_sz = 11.5
                    s_sub_sz = 8.5
                    s_badge_sz = 10
                    s_pct_sz = 9
                else:
                    s_title_sz = 10
                    s_sub_sz = 7.5
                    s_badge_sz = 9
                    s_pct_sz = 8
                
                s_text = f"""
                <foreignObject x="{scx - sr}" y="{scy - sr}" width="{2*sr}" height="{2*sr}">
                    <div style="width: 100%; height: 100%; display: flex; flex-direction: column; justify-content: center; align-items: center; text-align: center; font-family: 'Outfit', 'Sarabun', sans-serif; pointer-events: none; box-sizing: border-box; line-height: 1.12; padding: 2px;">
                        <!-- Enlarged Sub-Circle Logo Badge -->
                        <div style="background: rgba(255, 255, 255, 0.96); border-radius: 50%; width: {sub_badge_sz}px; height: {sub_badge_sz}px; display: flex; justify-content: center; align-items: center; box-shadow: 0 2px 8px rgba(0,0,0,0.18); border: 2px solid #ffffff; margin-bottom: 2px; overflow: hidden; padding: 2px; box-sizing: border-box;">
                            <img src="{sub_logo_data}" style="max-width: 90%; max-height: 90%; width: 90%; height: 90%; object-fit: contain;" alt="{sub['name']}" />
                        </div>
                        <div style="font-weight: 800; font-size: {s_title_sz}px; color: #0f172a; text-transform: uppercase; letter-spacing: -0.3px;">
                            {sub['name']}
                        </div>
                        <div style="font-size: {s_sub_sz}px; color: #334155; font-weight: 600; margin-bottom: 1.5px;">
                            {sub['sub']}
                        </div>
                        <div style="background: rgba(255,255,255,0.85); backdrop-filter: blur(2px); border-radius: 12px; padding: 1px 6px; font-weight: 800; font-size: {s_badge_sz}px; color: #0f172a; box-shadow: 0 1px 4px rgba(0,0,0,0.08); border: 1px solid rgba(255,255,255,0.9);">
                            {sub['count']:,}
                        </div>
                        <div style="font-size: {s_pct_sz}px; color: #0284c7; font-weight: 800; margin-top: 1px;">
                            ({sub['pct']:.1f}%)
                        </div>
                    </div>
                </foreignObject>
                """
                
                nested_circles_svg.append(f"""
                <g class="nested-sub-bubble">
                    {s_slice}
                    {s_sheen}
                    {s_highlight}
                    {s_text}
                </g>
                """)
            
            tnb_logo = get_company_logo_data_uri('taladnudbaan')
            bubble_body = f"""
                <g class="bubble-group" id="{bubble_id}">
                    {slices}
                    {sheen}
                    {highlight}
                    
                    <!-- 4 Nested Sub-Circles that fill the circle space -->
                    {''.join(nested_circles_svg)}
                    
                    <!-- Subtle Floating Tag for Taladnudbaan with Logo Badge -->
                    <foreignObject x="{cx - 120}" y="{cy + radius - 26}" width="240" height="28">
                        <div style="width: 100%; display: flex; justify-content: center; align-items: center; text-align: center; font-family: 'Outfit', 'Sarabun', sans-serif; pointer-events: none;">
                            <div style="background: rgba(15, 23, 42, 0.88); backdrop-filter: blur(6px); color: #ffffff; border-radius: 20px; padding: 2px 14px; font-size: 11px; font-weight: 800; border: 1px solid rgba(255,255,255,0.3); box-shadow: 0 2px 6px rgba(0,0,0,0.25); display: inline-flex; align-items: center; gap: 7px;">
                                <div style="background: #ffffff; border-radius: 50%; width: 18px; height: 18px; display: flex; justify-content: center; align-items: center; overflow: hidden; padding: 1.5px; box-sizing: border-box;">
                                    <img src="{tnb_logo}" style="width: 100%; height: 100%; object-fit: contain;" alt="TNB" />
                                </div>
                                TALADNUDBAAN: {c_count:,}
                            </div>
                        </div>
                    </foreignObject>
                </g>
            """
        else:
            # Standard single provider bubble layout with Extra Large Frosted Glass White Background Badge
            bubble_body = f"""
                <g class="bubble-group" id="{bubble_id}">
                    {slices}
                    {sheen}
                    {highlight}
                    <foreignObject x="{cx - radius}" y="{cy - radius}" width="{2*radius}" height="{2*radius}">
                        <div style="width: 100%; height: 100%; display: flex; flex-direction: column; justify-content: center; align-items: center; text-align: center; font-family: 'Outfit', 'Sarabun', sans-serif; pointer-events: none; box-sizing: border-box; padding: 4px; line-height: 1.2; will-change: transform; transform: translate3d(0,0,0);">
                            <!-- Extra Large Logo with Crisp White Circular Badge Background -->
                            <div style="background: rgba(255, 255, 255, 0.96); border-radius: 50%; width: {logo_badge_sz}px; height: {logo_badge_sz}px; display: flex; justify-content: center; align-items: center; box-shadow: 0 4px 12px rgba(0,0,0,0.20), 0 1px 3px rgba(0,0,0,0.12); border: 2.5px solid #ffffff; margin-bottom: 2.5px; overflow: hidden; padding: 2px; box-sizing: border-box; filter: drop-shadow(0 2px 6px rgba(0,0,0,0.15));">
                                <img src="{logo_data_uri}" style="max-width: 90%; max-height: 90%; width: 90%; height: 90%; object-fit: contain;" alt="{comp['name']}" />
                            </div>
                            
                            <!-- Title -->
                            <div style="font-weight: 800; font-size: {title_size}px; color: {text_title_color}; letter-spacing: -0.3px; margin-bottom: 2.5px; text-transform: uppercase;">
                                {comp['name']}
                            </div>
                            
                            <!-- Stats: จำนวนทรัพย์ -->
                            <div style="background: {card_bg_color}; backdrop-filter: blur(4px); border-radius: 20px; padding: {badge_padding}; display: inline-flex; align-items: center; gap: {badge_gap}; margin-bottom: {margin_bottom}; border: 1px solid rgba(255, 255, 255, 0.4); box-shadow: 0 2px 5px rgba(0, 0, 0, 0.05);">
                                <span style="font-size: {text_size - 1.5}px; color: {text_sub_color}; font-weight: 600;">ทรัพย์สิน</span>
                                <span style="font-size: {text_size}px; color: {text_val_color}; font-weight: 800;">{c_count:,} <span style="color: #6366f1; font-weight: 700;">({pct_count:.1f}%)</span></span>
                            </div>
                            
                            <!-- Stats: มูลค่ารวม -->
                            <div style="background: {card_bg_color}; backdrop-filter: blur(4px); border-radius: 20px; padding: {badge_padding}; display: inline-flex; align-items: center; gap: {badge_gap}; border: 1px solid rgba(255, 255, 255, 0.4); box-shadow: 0 2px 5px rgba(0, 0, 0, 0.05);">
                                <span style="font-size: {text_size - 1.5}px; color: {text_sub_color}; font-weight: 600;">มูลค่า</span>
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
        dx = 4 if comp["base_cx"] > 560 else -4
        dy = -6 if comp["base_cy"] > 330 else 6
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

    svg_content = f"""
    <svg viewBox="0 0 1180 650" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg" style="background-color: transparent;">
      <defs>
        <filter id="shadow" x="-30%" y="-30%" width="160%" height="160%">
          <feDropShadow dx="0" dy="10" stdDeviation="14" flood-color="#0f172a" flood-opacity="{'0.35' if is_dark_mode else '0.15'}"/>
        </filter>
        <filter id="sub-shadow" x="-30%" y="-30%" width="160%" height="160%">
          <feDropShadow dx="0" dy="5" stdDeviation="7" flood-color="#0f172a" flood-opacity="0.2"/>
        </filter>
        
        <linearGradient id="highlight-grad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="rgba(255, 255, 255, 0.75)"/>
          <stop offset="100%" stop-color="rgba(255, 255, 255, 0)"/>
        </linearGradient>
        
        <!-- Taladnudbaan Outer Background Gradient -->
        <radialGradient id="taladnudbaan-outer-grad" cx="50%" cy="50%" r="50%" fx="35%" fy="30%">
          <stop offset="0%" stop-color="#f0fdfa"/>
          <stop offset="60%" stop-color="#ccfbf1"/>
          <stop offset="100%" stop-color="#99f6e4"/>
        </radialGradient>

        <!-- Nested Sub-Gradients for Taladnudbaan (Vivid 3D) -->
        <!-- LED (Teal/Cyan) -->
        <radialGradient id="sub-led-grad" cx="50%" cy="50%" r="50%" fx="35%" fy="30%">
          <stop offset="0%" stop-color="#ffffff"/>
          <stop offset="40%" stop-color="#67e8f9"/>
          <stop offset="100%" stop-color="#0891b2"/>
        </radialGradient>
        
        <!-- EST (Emerald/Green) -->
        <radialGradient id="sub-est-grad" cx="50%" cy="50%" r="50%" fx="35%" fy="30%">
          <stop offset="0%" stop-color="#ffffff"/>
          <stop offset="40%" stop-color="#a7f3d0"/>
          <stop offset="100%" stop-color="#059669"/>
        </radialGradient>
        
        <!-- Others (Amber/Gold) -->
        <radialGradient id="sub-others-grad" cx="50%" cy="50%" r="50%" fx="35%" fy="30%">
          <stop offset="0%" stop-color="#ffffff"/>
          <stop offset="40%" stop-color="#fed7aa"/>
          <stop offset="100%" stop-color="#d97706"/>
        </radialGradient>
        
        <!-- JAM (Purple/Violet) -->
        <radialGradient id="sub-jam-grad" cx="50%" cy="50%" r="50%" fx="35%" fy="30%">
          <stop offset="0%" stop-color="#ffffff"/>
          <stop offset="40%" stop-color="#ddd6fe"/>
          <stop offset="100%" stop-color="#7c3aed"/>
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
      </defs>
      
      {'\n'.join(bubbles_html_list)}
    </svg>
    """

    hover_css = "\n".join(hover_classes_list)
    keyframes_css = "\n".join(keyframes_list)

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@400;600;700;800;900&family=Sarabun:wght@400;600;700;800&display=swap');
        body {{
            margin: 0;
            padding: 0;
            background: transparent;
            overflow: hidden;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            width: 100vw;
            user-select: none;
        }}
        .bubble-group {{
            cursor: pointer;
            transition: transform 0.4s cubic-bezier(0.34, 1.56, 0.64, 1), filter 0.3s ease;
        }}
        .bubble-group:hover {{
            transform: scale(1.08);
            filter: brightness(1.08) drop-shadow(0 15px 25px rgba(0,0,0,0.25));
        }}
        .nested-sub-bubble {{
            cursor: pointer;
            transition: transform 0.3s cubic-bezier(0.34, 1.56, 0.64, 1), filter 0.25s ease;
        }}
        .nested-sub-bubble:hover {{
            transform: scale(1.12);
            filter: brightness(1.12) drop-shadow(0 6px 12px rgba(0,0,0,0.2));
        }}
        {hover_css}
        {keyframes_css}
    </style>
    </head>
    <body>
        {svg_content}
    </body>
    </html>
    """
    return html_content
