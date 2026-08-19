import math
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

def get_tnb_subinstitutions(df_tnb):
    """Extracts and summarizes sub-companies / banks / institutions inside Taladnudbaan with tightly packed sub-circles."""
    if df_tnb is None or df_tnb.empty:
        return []
    
    def parse_inst(u):
        if pd.isna(u): return "อื่นๆ"
        parts = str(u).split('/')
        if len(parts) >= 6:
            code = parts[5].strip().upper()
            mapping = {
                "LED": "LED",
                "GHB": "GHB",
                "KBANK": "KBANK",
                "EST": "EST",
                "JAM": "JAM",
                "KTB": "KTB",
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
    c_ghb = counts.get("GHB", 0)
    c_kbank = counts.get("KBANK", 0)
    c_others = total - (c_led + c_ghb + c_kbank)
    if c_others < 0: c_others = 0
    
    sub_data = [
        {
            "id": "sub-led",
            "name": "LED",
            "sub": "กรมบังคับคดี",
            "count": c_led,
            "pct": (c_led / total * 100) if total > 0 else 0,
            "rel_x": -78, "rel_y": 30, "r": 112,
            "grad": "sub-led-grad",
            "border": "#0891b2"
        },
        {
            "id": "sub-ghb",
            "name": "GHB",
            "sub": "ธนาคาร ธอส.",
            "count": c_ghb,
            "pct": (c_ghb / total * 100) if total > 0 else 0,
            "rel_x": 92, "rel_y": -78, "r": 70,
            "grad": "sub-ghb-grad",
            "border": "#d97706"
        },
        {
            "id": "sub-others",
            "name": "อื่นๆ",
            "sub": "JAM/KTB/BAY",
            "count": c_others,
            "pct": (c_others / total * 100) if total > 0 else 0,
            "rel_x": -27, "rel_y": -140, "r": 62,
            "grad": "sub-others-grad",
            "border": "#6366f1"
        },
        {
            "id": "sub-kbank",
            "name": "KBANK",
            "sub": "ธ.กสิกรไทย",
            "count": c_kbank,
            "pct": (c_kbank / total * 100) if total > 0 else 0,
            "rel_x": 89, "rel_y": 78, "r": 60,
            "grad": "sub-kbank-grad",
            "border": "#059669"
        }
    ]
    return sub_data

def generate_3d_glossy_bubble_chart_html(df_filtered, bubble_metric="สัดส่วนตามจำนวนทรัพย์สิน (Asset Count)", is_dark_mode=False):
    """
    Generates an interactive, responsive 3D Glossy Bubble Chart HTML component
    matching the AMC NPA Monitor style for the 6 active property companies,
    including enlarged, tightly packed 3D sub-bubbles inside Taladnudbaan.
    """
    companies_meta = [
        {
            "id": "taladnudbaan",
            "name": "Taladnudbaan",
            "label": "Taladnudbaan NPA",
            "base_cx": 460, "base_cy": 310,
            "scraped_grad": "taladnudbaan-outer-grad",
            "unscraped_grad": "taladnudbaan-unscraped",
            "float_dur": "7s",
            "color_hex": "#06b6d4",
            "is_tnb": True
        },
        {
            "id": "nayoo",
            "name": "NaYoo",
            "label": "NaYoo NPA",
            "base_cx": 830, "base_cy": 240,
            "scraped_grad": "nayoo-scraped",
            "unscraped_grad": "nayoo-unscraped",
            "float_dur": "6.5s",
            "color_hex": "#8b5cf6",
            "is_tnb": False
        },
        {
            "id": "zmyhome",
            "name": "ZmyHome",
            "label": "ZmyHome NPA",
            "base_cx": 160, "base_cy": 200,
            "scraped_grad": "zmyhome-scraped",
            "unscraped_grad": "zmyhome-unscraped",
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
            "unscraped_grad": "bam-unscraped",
            "float_dur": "6s",
            "color_hex": "#3b82f6",
            "is_tnb": False
        },
        {
            "id": "baania",
            "name": "Baania",
            "label": "Baania NPA",
            "base_cx": 780, "base_cy": 480,
            "scraped_grad": "baania-scraped",
            "unscraped_grad": "baania-unscraped",
            "float_dur": "7.5s",
            "color_hex": "#f59e0b",
            "is_tnb": False
        },
        {
            "id": "sam",
            "name": "SAM",
            "label": "SAM NPA",
            "base_cx": 1000, "base_cy": 150,
            "scraped_grad": "sam-scraped",
            "unscraped_grad": "sam-unscraped",
            "float_dur": "8.5s",
            "color_hex": "#10b981",
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
        c_prices = comp_df['ราคา'].dropna() if not comp_df.empty else pd.Series()
        c_val = c_prices.sum() if not c_prices.empty else 0.0
        
        pct_count = (c_count / total_market_count * 100) if total_market_count > 0 else 0.0
        pct_val = (c_val / total_market_val * 100) if total_market_val > 0 else 0.0
        
        active_pct = pct_count if is_count_metric else pct_val
        active_fraction = active_pct / 100.0
        
        if comp.get("is_tnb"):
            radius = 215
        else:
            if active_fraction > 0:
                radius = int(50 + 125 * math.sqrt(active_fraction))
                radius = max(50, min(150, radius))
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
        
        title_size = max(12, int(radius * 0.12))
        text_size = max(9.5, int(radius * 0.082))
        badge_padding = "3px 9px" if radius > 110 else "2px 6px"
        badge_gap = "4px" if radius > 110 else "2px"
        margin_bottom = "4px" if radius > 110 else "2px"

        card_bg_color = "rgba(15, 23, 42, 0.55)" if is_dark_mode else "rgba(255, 255, 255, 0.55)"
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
                
                # Sub-circle typography
                if sr >= 100:
                    # Giant LED sub-circle
                    s_title_sz = 16
                    s_sub_sz = 11.5
                    s_badge_sz = 14
                    s_pct_sz = 12.5
                elif sr >= 65:
                    s_title_sz = 13.5
                    s_sub_sz = 10
                    s_badge_sz = 11.5
                    s_pct_sz = 10.5
                else:
                    s_title_sz = 12
                    s_sub_sz = 9
                    s_badge_sz = 10.5
                    s_pct_sz = 9.5
                
                s_text = f"""
                <foreignObject x="{scx - sr}" y="{scy - sr}" width="{2*sr}" height="{2*sr}">
                    <div style="width: 100%; height: 100%; display: flex; flex-direction: column; justify-content: center; align-items: center; text-align: center; font-family: 'Outfit', 'Sarabun', sans-serif; pointer-events: none; box-sizing: border-box; line-height: 1.2; padding: 4px;">
                        <div style="font-weight: 800; font-size: {s_title_sz}px; color: #0f172a; text-transform: uppercase; letter-spacing: -0.3px;">
                            {sub['name']}
                        </div>
                        <div style="font-size: {s_sub_sz}px; color: #334155; font-weight: 600; margin-bottom: 2px;">
                            {sub['sub']}
                        </div>
                        <div style="background: rgba(255,255,255,0.85); backdrop-filter: blur(2px); border-radius: 12px; padding: 1px 8px; font-weight: 800; font-size: {s_badge_sz}px; color: #0f172a; box-shadow: 0 1px 4px rgba(0,0,0,0.08); border: 1px solid rgba(255,255,255,0.9);">
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
            
            bubble_body = f"""
                <g class="bubble-group" id="{bubble_id}">
                    {slices}
                    {sheen}
                    {highlight}
                    
                    <!-- 4 Nested Sub-Circles that fill the circle space -->
                    {''.join(nested_circles_svg)}
                    
                    <!-- Subtle Floating Tag for Taladnudbaan -->
                    <foreignObject x="{cx - 100}" y="{cy + radius - 28}" width="200" height="30">
                        <div style="width: 100%; display: flex; justify-content: center; align-items: center; text-align: center; font-family: 'Outfit', 'Sarabun', sans-serif; pointer-events: none;">
                            <div style="background: rgba(15, 23, 42, 0.85); backdrop-filter: blur(6px); color: #ffffff; border-radius: 20px; padding: 2px 12px; font-size: 11px; font-weight: 800; border: 1px solid rgba(255,255,255,0.3); box-shadow: 0 2px 6px rgba(0,0,0,0.25);">
                                TALADNUDBAAN: {c_count:,}
                            </div>
                        </div>
                    </foreignObject>
                </g>
            """
        else:
            # Standard single provider bubble layout
            bubble_body = f"""
                <g class="bubble-group" id="{bubble_id}">
                    {slices}
                    {sheen}
                    {highlight}
                    <foreignObject x="{cx - radius}" y="{cy - radius}" width="{2*radius}" height="{2*radius}">
                        <div style="width: 100%; height: 100%; display: flex; flex-direction: column; justify-content: center; align-items: center; text-align: center; font-family: 'Outfit', 'Sarabun', sans-serif; pointer-events: none; box-sizing: border-box; padding: 8px; line-height: 1.35; will-change: transform; transform: translate3d(0,0,0);">
                            <!-- Title -->
                            <div style="font-weight: 800; font-size: {title_size}px; color: {text_title_color}; letter-spacing: -0.3px; margin-bottom: 5px; text-transform: uppercase;">
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
        dx = 4 if comp["base_cx"] > 500 else -4
        dy = -6 if comp["base_cy"] > 300 else 6
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
    <svg viewBox="0 0 1120 640" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg" style="background-color: transparent;">
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
        
        <!-- GHB (Amber/Gold) -->
        <radialGradient id="sub-ghb-grad" cx="50%" cy="50%" r="50%" fx="35%" fy="30%">
          <stop offset="0%" stop-color="#ffffff"/>
          <stop offset="40%" stop-color="#fde68a"/>
          <stop offset="100%" stop-color="#d97706"/>
        </radialGradient>
        
        <!-- Others (Indigo/Purple) -->
        <radialGradient id="sub-others-grad" cx="50%" cy="50%" r="50%" fx="35%" fy="30%">
          <stop offset="0%" stop-color="#ffffff"/>
          <stop offset="40%" stop-color="#c7d2fe"/>
          <stop offset="100%" stop-color="#6366f1"/>
        </radialGradient>
        
        <!-- KBANK (Emerald/Green) -->
        <radialGradient id="sub-kbank-grad" cx="50%" cy="50%" r="50%" fx="35%" fy="30%">
          <stop offset="0%" stop-color="#ffffff"/>
          <stop offset="40%" stop-color="#a7f3d0"/>
          <stop offset="100%" stop-color="#059669"/>
        </radialGradient>
        
        <!-- NaYoo Radial Gradients (Purple) -->
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
      </defs>
      
      {''.join(bubbles_html_list)}
    </svg>
    """

    hover_css = "\n".join(hover_classes_list)
    keyframes_css = "\n".join(keyframes_list)

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@400;600;700;800&family=Sarabun:wght@400;600;700;800&display=swap');
        body {{
            margin: 0;
            padding: 0;
            background-color: transparent;
            overflow: hidden;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 640px;
        }}
        .bubble-container {{
            width: 100%;
            max-width: 1100px;
            height: auto;
            margin: 0 auto;
        }}
        svg {{
            text-rendering: geometricPrecision;
        }}
        .float-wrapper, .bubble-group, text {{
            will-change: transform;
            transform: translate3d(0, 0, 0);
            -webkit-font-smoothing: antialiased;
            -moz-osx-font-smoothing: grayscale;
        }}
        .bubble-group {{
            transition: transform 0.35s cubic-bezier(0.25, 0.8, 0.25, 1);
            cursor: pointer;
        }}
        
        .nested-sub-bubble {{
            transition: transform 0.25s cubic-bezier(0.25, 0.8, 0.25, 1);
            cursor: pointer;
        }}
        .nested-sub-bubble:hover {{
            transform: scale(1.09);
            transform-origin: center;
        }}
        
        {hover_css}
        
        .bubble-group:hover {{
            transform: scale(1.03);
        }}
        .bubble-group:hover circle {{
            filter: brightness(1.05);
        }}
        
        {keyframes_css}
    </style>
    </head>
    <body>
    <div class="bubble-container">
        {svg_content}
    </div>
    </body>
    </html>
    """
    return html_content
