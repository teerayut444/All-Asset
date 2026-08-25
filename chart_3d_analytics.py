"""
chart_3d_analytics.py - 3D Interactive Analytics Visualizations for Competitor & Market Analysis.
Provides high-performance, aesthetically rich 3D charts for Tab 2 using Plotly WebGL 3D & 3D styling.
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

# Curated Company Color Palette matching Dashboard Standard
COMPANY_COLORS_3D = {
    "SAM": "#10b981",
    "BAM": "#3b82f6",
    "Chayo555": "#f97316",
    "Chayo": "#f97316",
    "Chayo NPA": "#f97316",
    "Baania": "#f59e0b",
    "NaYoo": "#8b5cf6",
    "Taladnudbaan": "#06b6d4",
    "ZmyHome": "#ec4899",
    "KBANK": "#059669",
    "GHB": "#ca8a04",
    "SCB": "#7e22ce",
    "KTB": "#0284c7",
    "GSB": "#eb1985"
}

TYPE_COLORS_3D = {
    "บ้านเดี่ยว": "#3b82f6",
    "ทาวน์เฮ้าส์": "#10b981",
    "ห้องชุดพักอาศัย": "#f59e0b",
    "คอนโด": "#f59e0b",
    "ที่ดินเปล่า": "#06b6d4",
    "อาคารพาณิชย์": "#8b5cf6",
    "โรงงาน/โกดัง": "#ec4899",
    "บ้านแฝด": "#14b8a6",
    "อื่นๆ": "#94a3b8"
}

def get_3d_scene_layout(is_dark_mode=False, aspectratio=dict(x=1.2, y=1.2, z=0.8), camera_eye=dict(x=1.6, y=-1.6, z=1.2)):
    """Returns standardized sleek glassmorphic 3D scene lighting, grid, and camera settings."""
    bg_color = "rgba(15, 23, 42, 0.0)" if is_dark_mode else "rgba(255, 255, 255, 0.0)"
    grid_color = "rgba(148, 163, 184, 0.25)" if is_dark_mode else "rgba(100, 116, 139, 0.2)"
    axis_line_color = "#64748b" if is_dark_mode else "#94a3b8"
    font_color = "#f8fafc" if is_dark_mode else "#0f172a"

    axis_common = dict(
        backgroundcolor=bg_color,
        gridcolor=grid_color,
        showbackground=True,
        zerolinecolor=axis_line_color,
        linecolor=axis_line_color,
        tickfont=dict(size=11, family="Outfit, Sarabun, sans-serif", color=font_color)
    )

    return dict(
        xaxis=dict(**axis_common),
        yaxis=dict(**axis_common),
        zaxis=dict(**axis_common),
        aspectmode='manual',
        aspectratio=aspectratio,
        camera=dict(
            eye=camera_eye,
            projection=dict(type='perspective')
        )
    )

# -----------------------------------------------------------------------------
# 1. 3D Multi-Dimensional Scatter Space (เนื้อที่ x ราคาเริ่มต้น x ราคาต่อ ตร.ว.)
# -----------------------------------------------------------------------------
def render_3d_scatter_price_area(df_filtered, is_dark_mode=False):
    """
    Builds a 3D Scatter Space visualizing Area (X), Price (Y), and Price/Sq.Wah (Z).
    Allows full 360-degree rotation, zoom, and multi-company inspection.
    """
    def map_type(t):
        t_str = str(t).strip()
        if 'คอนโด' in t_str or 'ห้องชุด' in t_str: return np.nan
        elif 'ที่ดิน' in t_str: return 'ที่ดินเปล่า'
        elif 'บ้านเดี่ยว' in t_str or 'บ้านแฝด' in t_str or 'พูลวิลล่า' in t_str or 'บ้าน' in t_str: return 'บ้านเดี่ยว'
        elif 'ทาวน์โฮม' in t_str or 'ทาวน์เฮ้าส์' in t_str or 'ทาวน์เฮาส์' in t_str: return 'ทาวน์เฮ้าส์'
        elif 'อาคารพาณิชย์' in t_str or 'ตึกแถว' in t_str: return 'อาคารพาณิชย์'
        return np.nan

    df_plot = df_filtered[
        (df_filtered['พื้นที่_ตารางวา'].notna()) & 
        (df_filtered['พื้นที่_ตารางวา'] > 0) & 
        (df_filtered['พื้นที่_ตารางวา'] <= 1000) & 
        (df_filtered['ราคา'].notna()) & 
        (df_filtered['ราคา'] > 0) & 
        (df_filtered['ราคา'] <= 60000000)
    ].copy()

    df_plot['ประเภท_กลุ่ม'] = df_plot['ประเภททรัพย์'].apply(map_type)
    df_plot = df_plot[df_plot['ประเภท_กลุ่ม'].notna()]
    
    if df_plot.empty:
        return None

    # Calculate Price per Sq.Wah
    df_plot['ราคาต่อ_ตรว'] = df_plot['ราคา'] / df_plot['พื้นที่_ตารางวา']
    df_plot['ราคา_ล้านบาท'] = df_plot['ราคา'] / 1e6
    df_plot['ราคาต่อ_ตรว_พัน'] = df_plot['ราคาต่อ_ตรว'] / 1e3

    # Sample to 6,000 points max for smooth 60fps 3D rendering
    if len(df_plot) > 6000:
        df_plot = df_plot.sample(n=6000, random_state=42)

    fig = go.Figure()

    # Add traces grouped by Property Type
    types = df_plot['ประเภท_กลุ่ม'].unique()
    for ptype in types:
        sub = df_plot[df_plot['ประเภท_กลุ่ม'] == ptype]
        c = TYPE_COLORS_3D.get(ptype, "#6366f1")

        hover_txt = [
            f"<b>{row.get('ชื่อประกาศ', '')}</b><br>"
            f"🏢 บริษัท: <b>{row.get('บริษัท', '')}</b><br>"
            f"🏠 ประเภท: {ptype}<br>"
            f"📍 ทำเล: {row.get('อำเภอ', '')}, {row.get('จังหวัด', '')}<br>"
            f"📐 เนื้อที่: <b>{row['พื้นที่_ตารางวา']:,.1f} ตร.ว.</b><br>"
            f"💰 ราคา: <b>฿{row['ราคา']:,.0f} บาท</b> ({row['ราคา_ล้านบาท']:.2f} ล้าน)<br>"
            f"⚡ ราคา/ตร.ว.: <b>฿{row['ราคาต่อ_ตรว']:,.0f} บาท</b>"
            for _, row in sub.iterrows()
        ]

        fig.add_trace(go.Scatter3d(
            x=sub['พื้นที่_ตารางวา'],
            y=sub['ราคา_ล้านบาท'],
            z=sub['ราคาต่อ_ตรว_พัน'],
            mode='markers',
            name=ptype,
            hoverinfo='text',
            hovertext=hover_txt,
            marker=dict(
                size=5,
                color=c,
                opacity=0.82,
                symbol='circle',
                line=dict(color='rgba(255,255,255,0.6)', width=0.5)
            )
        ))

    f_color = "#f8fafc" if is_dark_mode else "#0f172a"
    scene = get_3d_scene_layout(is_dark_mode, aspectratio=dict(x=1.3, y=1.3, z=0.9), camera_eye=dict(x=1.7, y=-1.5, z=1.3))
    scene['xaxis']['title'] = dict(text='เนื้อที่ (ตร.ว.)', font=dict(size=12, family="Outfit, Sarabun", color=f_color))
    scene['yaxis']['title'] = dict(text='ราคาเริ่มต้น (ล้านบาท)', font=dict(size=12, family="Outfit, Sarabun", color=f_color))
    scene['zaxis']['title'] = dict(text='ราคา/ตร.ว. (พันบาท)', font=dict(size=12, family="Outfit, Sarabun", color=f_color))

    fig.update_layout(
        title=dict(
            text='🌐 แผนภูมิ 3 มิติ: เนื้อที่ (ตร.ว.) x ราคาเริ่มต้น x ราคาเฉลี่ยต่อ ตร.ว.',
            font=dict(size=14, family="Outfit, Sarabun, sans-serif")
        ),
        scene=scene,
        margin=dict(l=10, r=10, t=40, b=10),
        height=580,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="center",
            x=0.5,
            font=dict(size=11, family="Outfit, Sarabun")
        ),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)'
    )
    return fig

# -----------------------------------------------------------------------------
# 2. 3D Market Landscape Surface (ภูมิประเทศความหนาแน่นและระดับราคา 3D Surface)
# -----------------------------------------------------------------------------
def render_3d_market_surface(df_filtered, is_dark_mode=False):
    """
    Creates a 3D Elevation Surface showing market asset density and pricing distribution across price tiers and property types.
    """
    df_clean = df_filtered[(df_filtered['ราคา'].notna()) & (df_filtered['ราคา'] > 0) & (df_filtered['ราคา'] <= 30000000)].copy()
    if df_clean.empty:
        return None

    def map_simplified_type(t):
        t_str = str(t).strip()
        if 'ที่ดิน' in t_str: return 'ที่ดินเปล่า'
        elif 'คอนโด' in t_str or 'ห้องชุด' in t_str: return 'ห้องชุด'
        elif 'บ้านเดี่ยว' in t_str or 'บ้านแฝด' in t_str or 'พูลวิลล่า' in t_str or 'บ้าน' in t_str: return 'บ้านเดี่ยว'
        elif 'ทาวน์โฮม' in t_str or 'ทาวน์เฮ้าส์' in t_str or 'ทาวน์เฮาส์' in t_str: return 'ทาวน์เฮ้าส์'
        elif 'อาคารพาณิชย์' in t_str or 'ตึกแถว' in t_str: return 'อาคารพาณิชย์'
        return 'อื่นๆ'

    df_clean['Type_Group'] = df_clean['ประเภททรัพย์'].apply(map_simplified_type)
    
    # 10 Price Bins (0 to 30 Million)
    price_bins = [0, 1.5e6, 3e6, 5e6, 7.5e6, 10e6, 15e6, 20e6, 25e6, 30e6]
    bin_labels = ['<1.5M', '1.5-3M', '3-5M', '5-7.5M', '7.5-10M', '10-15M', '15-20M', '20-25M', '25-30M']
    df_clean['Price_Bin'] = pd.cut(df_clean['ราคา'], bins=price_bins, labels=bin_labels, right=True)

    types_order = ['บ้านเดี่ยว', 'ทาวน์เฮ้าส์', 'ห้องชุด', 'ที่ดินเปล่า', 'อาคารพาณิชย์']
    df_clean = df_clean[df_clean['Type_Group'].isin(types_order)]

    pivot = df_clean.groupby(['Type_Group', 'Price_Bin'], observed=False).size().unstack(fill_value=0).reindex(types_order)

    z_data = pivot.values
    x_data = bin_labels
    y_data = types_order

    fig = go.Figure()

    fig.add_trace(go.Surface(
        z=z_data,
        x=x_data,
        y=y_data,
        colorscale='Viridis' if is_dark_mode else 'Turbo',
        contours=dict(
            z=dict(show=True, usecolormap=True, highlightcolor="limegreen", project_z=True),
            x=dict(show=True, color="rgba(255,255,255,0.3)"),
            y=dict(show=True, color="rgba(255,255,255,0.3)")
        ),
        lighting=dict(ambient=0.65, diffuse=0.85, specular=0.4, roughness=0.5),
        colorbar=dict(
            title=dict(text="จำนวนทรัพย์ (รายการ)", side="right", font=dict(size=11, family="Outfit, Sarabun")),
            len=0.75,
            thickness=15
        ),
        hovertemplate="<b>ประเภท: %{y}</b><br>ช่วงราคา: %{x}<br>จำนวน: <b>%{z:,} รายการ</b><extra></extra>"
    ))

    f_color = "#f8fafc" if is_dark_mode else "#0f172a"
    scene = get_3d_scene_layout(is_dark_mode, aspectratio=dict(x=1.5, y=1.0, z=0.7), camera_eye=dict(x=1.8, y=-1.4, z=1.1))
    scene['xaxis']['title'] = dict(text='ช่วงราคาเริ่มต้น (บาท)', font=dict(size=12, family="Outfit, Sarabun", color=f_color))
    scene['yaxis']['title'] = dict(text='ประเภททรัพย์', font=dict(size=12, family="Outfit, Sarabun", color=f_color))
    scene['zaxis']['title'] = dict(text='ความหนาแน่น (รายการ)', font=dict(size=12, family="Outfit, Sarabun", color=f_color))

    fig.update_layout(
        title=dict(
            text='🏔️ ภูมิประเทศ 3 มิติ: ความหนาแน่นของราคาทรัพย์สินในตลาด (3D Price Surface)',
            font=dict(size=14, family="Outfit, Sarabun, sans-serif")
        ),
        scene=scene,
        margin=dict(l=10, r=10, t=40, b=10),
        height=520,
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)'
    )
    return fig

# -----------------------------------------------------------------------------
# 3. 3D Bar Columns: Total Assets by Company
# -----------------------------------------------------------------------------
def render_3d_company_assets_bars(comp_counts_df, is_dark_mode=False):
    """
    Renders a 3D-styled perspective bar chart of Total Asset Volume per company.
    """
    fig = go.Figure()
    
    comps = comp_counts_df['บริษัท'].tolist()
    counts = comp_counts_df['จำนวนทรัพย์สิน'].tolist()
    colors = [COMPANY_COLORS_3D.get(c, "#3b82f6") for c in comps]

    fig.add_trace(go.Bar(
        x=comps,
        y=counts,
        marker=dict(
            color=colors,
            line=dict(width=2, color='rgba(255,255,255,0.7)')
        ),
        text=[f"<b>{v:,}</b>" for v in counts],
        textposition='outside',
        textfont=dict(size=12, family="Outfit, Sarabun", color="#f8fafc" if is_dark_mode else "#0f172a"),
        hovertemplate="🏢 <b>%{x}</b><br>จำนวนทรัพย์สิน: <b>%{y:,} รายการ</b><extra></extra>"
    ))

    fig.update_layout(
        title=dict(text='🏛️ แผนภูมิเปรียบเทียบจำนวนรายการทรัพย์สินแต่ละบริษัท (3D Styled Volume)', font=dict(size=14, family="Outfit, Sarabun")),
        xaxis=dict(title='บริษัท', tickfont=dict(family="Outfit, Sarabun", size=11), showgrid=False),
        yaxis=dict(title='จำนวนทรัพย์สิน (รายการ)', showgrid=True, gridcolor='rgba(148,163,184,0.15)'),
        height=420,
        margin=dict(l=40, r=20, t=50, b=40),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)'
    )
    return fig

# -----------------------------------------------------------------------------
# 4. 3D Isometric Donut: Distribution of Property Types
# -----------------------------------------------------------------------------
def render_3d_property_type_donut(type_counts_df, is_dark_mode=False):
    """
    Renders an isometric 3D Donut Chart with pull-out effects and clean typography.
    """
    labels = type_counts_df['ประเภททรัพย์'].tolist()
    values = type_counts_df['จำนวนประกาศ'].tolist()
    colors = [TYPE_COLORS_3D.get(l, px.colors.qualitative.Pastel[i % len(px.colors.qualitative.Pastel)]) for i, l in enumerate(labels)]

    fig = go.Figure(data=[go.Pie(
        labels=labels,
        values=values,
        hole=0.48,
        pull=[0.05 if i == 0 else 0.02 for i in range(len(labels))],
        marker=dict(colors=colors, line=dict(color='#ffffff' if not is_dark_mode else '#1e293b', width=2.5)),
        textinfo='label+percent',
        textposition='outside',
        textfont=dict(size=11, family="Outfit, Sarabun", color="#f8fafc" if is_dark_mode else "#0f172a"),
        hovertemplate="🏠 <b>%{label}</b><br>จำนวนประกาศ: <b>%{value:,}</b> (%{percent})<extra></extra>"
    )])

    fig.update_layout(
        title=dict(text='🍩 สัดส่วนประเภททรัพย์สินหลัก (3D Isometric Donut)', font=dict(size=14, family="Outfit, Sarabun")),
        showlegend=False,
        height=420,
        margin=dict(l=30, r=30, t=50, b=30),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)'
    )
    return fig

# -----------------------------------------------------------------------------
# 5. 3D Bar Elevation: Median Price by Company
# -----------------------------------------------------------------------------
def render_3d_median_price_bars(median_price_df, is_dark_mode=False):
    """
    Renders 3D Elevated Median Price bars.
    """
    comps = median_price_df['บริษัท'].tolist()
    prices = median_price_df['ราคากลาง Median (บาท)'].tolist()
    colors = [COMPANY_COLORS_3D.get(c, "#3b82f6") for c in comps]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=comps,
        y=prices,
        marker=dict(color=colors, line=dict(width=2, color='rgba(255,255,255,0.7)')),
        text=[f"฿{v/1e6:.1f}M" if v >= 1e6 else f"฿{v/1e3:.0f}k" for v in prices],
        textposition='outside',
        textfont=dict(size=11, family="Outfit, Sarabun", color="#f8fafc" if is_dark_mode else "#0f172a"),
        hovertemplate="🏢 <b>%{x}</b><br>ราคากลาง Median: <b>฿%{y:,.0f} บาท</b><extra></extra>"
    ))

    fig.update_layout(
        title=dict(text='💰 ราคากลาง (Median) จำแนกตามบริษัททรัพย์สิน (3D Elevation)', font=dict(size=14, family="Outfit, Sarabun")),
        xaxis=dict(title='บริษัท', tickfont=dict(family="Outfit, Sarabun", size=11), showgrid=False),
        yaxis=dict(title='ราคากลาง (บาท)', showgrid=True, gridcolor='rgba(148,163,184,0.15)'),
        height=420,
        margin=dict(l=40, r=20, t=50, b=40),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)'
    )
    return fig

# -----------------------------------------------------------------------------
# 6. 3D Horizontal Bars: Top 10 Provinces
# -----------------------------------------------------------------------------
def render_3d_top_provinces(top_prov_df, is_dark_mode=False):
    """
    Renders 3D Horizontal bars for top provinces.
    """
    provs = top_prov_df['จังหวัด'].tolist()
    counts = top_prov_df['จำนวนทรัพย์'].tolist()

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=counts,
        y=provs,
        orientation='h',
        marker=dict(
            color=counts,
            colorscale='Viridis' if is_dark_mode else 'Blues',
            line=dict(color='rgba(255,255,255,0.6)', width=1.5)
        ),
        text=[f"<b>{c:,}</b>" for c in counts],
        textposition='outside',
        textfont=dict(size=11, family="Outfit, Sarabun", color="#f8fafc" if is_dark_mode else "#0f172a"),
        hovertemplate="📍 <b>%{y}</b><br>จำนวนทรัพย์: <b>%{x:,} รายการ</b><extra></extra>"
    ))

    fig.update_layout(
        title=dict(text='📍 10 อันดับจังหวัดที่มีทรัพย์สินเยอะที่สุด (3D Provincial Elevation)', font=dict(size=14, family="Outfit, Sarabun")),
        xaxis=dict(title='จำนวนทรัพย์ (รายการ)', showgrid=True, gridcolor='rgba(148,163,184,0.15)'),
        yaxis=dict(autorange="reversed", tickfont=dict(family="Outfit, Sarabun", size=11)),
        height=420,
        margin=dict(l=40, r=30, t=50, b=40),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)'
    )
    return fig

# -----------------------------------------------------------------------------
# 7. 3D Competitor Asset Matrix Grid (Sub-Tab 2: บริษัท x ประเภททรัพย์ x มูลค่า/จำนวน)
# -----------------------------------------------------------------------------
def render_3d_company_asset_matrix(comp_type_df, value_col, is_val_metric=False, is_dark_mode=False):
    """
    Renders an interactive 3D Matrix Space comparing all companies across all property types.
    X-axis: บริษัท (Companies)
    Y-axis: ประเภททรัพย์ (Property Types)
    Z-axis: จำนวนทรัพย์ (รายการ) หรือ มูลค่ารวม (ล้านบาท)
    """
    if comp_type_df.empty:
        return None

    PREFERRED_COMPANY_ORDER = ["SAM", "BAM", "Chayo555", "Chayo", "Chayo NPA", "Baania", "NaYoo", "Taladnudbaan", "ZmyHome", "KBANK", "GHB", "SCB", "KTB"]
    TOP_TYPES = ['บ้านเดี่ยว', 'ห้องชุดพักอาศัย', 'ทาวน์เฮ้าส์', 'ที่ดินเปล่า', 'อาคารพาณิชย์', 'โรงงาน/โกดัง', 'บ้านแฝด']

    df_matrix = comp_type_df.copy()
    
    # Clean types
    def clean_t(t):
        t_str = str(t).strip()
        for valid_t in TOP_TYPES:
            if valid_t in t_str:
                return valid_t
        return 'อื่นๆ'

    df_matrix['Type_Clean'] = df_matrix['ประเภททรัพย์'].apply(clean_t)
    
    # Filter and group
    grouped = df_matrix.groupby(['บริษัท', 'Type_Clean'])[value_col].sum().reset_index()

    comps = sorted(
        grouped['บริษัท'].unique(),
        key=lambda c: (PREFERRED_COMPANY_ORDER.index(c) if c in PREFERRED_COMPANY_ORDER else 999, c)
    )
    types = [t for t in TOP_TYPES if t in grouped['Type_Clean'].unique()] + (['อื่นๆ'] if 'อื่นๆ' in grouped['Type_Clean'].unique() else [])

    fig = go.Figure()

    for comp in comps:
        sub = grouped[grouped['บริษัท'] == comp]
        c_color = COMPANY_COLORS_3D.get(comp, "#3b82f6")

        x_vals = []
        y_vals = []
        z_vals = []
        hover_txt = []
        sizes = []

        for ptype in types:
            val_match = sub[sub['Type_Clean'] == ptype]
            v = val_match[value_col].values[0] if not val_match.empty else 0
            
            x_vals.append(comp)
            y_vals.append(ptype)
            
            display_z = (v / 1e6) if is_val_metric else v
            z_vals.append(display_z)
            
            # Marker size based on magnitude
            sz = max(6, min(24, int(8 + 14 * np.sqrt(display_z / (grouped[value_col].max() / 1e6 if is_val_metric else grouped[value_col].max() + 1e-5)))))
            sizes.append(sz)

            val_str = f"฿{v:,.0f} บาท ({v/1e6:,.1f}M)" if is_val_metric else f"{v:,} รายการ"
            hover_txt.append(
                f"🏢 บริษัท: <b>{comp}</b><br>"
                f"🏠 ประเภททรัพย์: <b>{ptype}</b><br>"
                f"{'💰 มูลค่ารวม' if is_val_metric else '👥 จำนวนทรัพย์'}: <b>{val_str}</b>"
            )

        # 3D scatter towers for each company
        fig.add_trace(go.Scatter3d(
            x=x_vals,
            y=y_vals,
            z=z_vals,
            mode='markers+lines',
            name=comp,
            hoverinfo='text',
            hovertext=hover_txt,
            marker=dict(
                size=sizes,
                color=c_color,
                opacity=0.88,
                symbol='diamond',
                line=dict(color='rgba(255,255,255,0.7)', width=1)
            ),
            line=dict(color=c_color, width=3)
        ))

    z_label = "มูลค่ารวม (ล้านบาท)" if is_val_metric else "จำนวนทรัพย์สิน (รายการ)"
    f_color = "#f8fafc" if is_dark_mode else "#0f172a"
    scene = get_3d_scene_layout(is_dark_mode, aspectratio=dict(x=1.4, y=1.2, z=0.9), camera_eye=dict(x=1.7, y=-1.5, z=1.2))
    scene['xaxis']['title'] = dict(text='บริษัท (Company)', font=dict(size=12, family="Outfit, Sarabun", color=f_color))
    scene['yaxis']['title'] = dict(text='ประเภททรัพย์ (Asset Type)', font=dict(size=12, family="Outfit, Sarabun", color=f_color))
    scene['zaxis']['title'] = dict(text=z_label, font=dict(size=12, family="Outfit, Sarabun", color=f_color))

    fig.update_layout(
        title=dict(
            text=f'📊 3D Market Matrix: สัดส่วนความเชี่ยวชาญสินค้าของแต่ละบริษัท ({z_label})',
            font=dict(size=14, family="Outfit, Sarabun, sans-serif")
        ),
        scene=scene,
        margin=dict(l=10, r=10, t=40, b=10),
        height=620,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="center",
            x=0.5,
            font=dict(size=11, family="Outfit, Sarabun")
        ),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)'
    )
    return fig

# -----------------------------------------------------------------------------
# 8. 3D SAM Price Tier Pyramid (Sub-Tab 3)
# -----------------------------------------------------------------------------
def render_3d_sam_price_pyramid(tier_df, is_dark_mode=False):
    """
    Renders a 3D Tiered Stepped Pyramid of SAM's price brackets showing Asset Counts and Total Portfolio Value.
    """
    tiers = tier_df['Price_Tier'].tolist()
    counts = tier_df['count'].tolist()
    vals_m = tier_df['val_million'].tolist()

    fig = go.Figure()

    # Base counts 3D Bars
    fig.add_trace(go.Bar(
        x=tiers,
        y=counts,
        name='จำนวนทรัพย์ (รายการ)',
        marker=dict(
            color='#10b981',
            line=dict(color='rgba(255,255,255,0.7)', width=2)
        ),
        text=[f"<b>{c:,}</b>" for c in counts],
        textposition='auto',
        yaxis='y'
    ))

    # Total value 3D scatter elevation curve
    fig.add_trace(go.Scatter(
        x=tiers,
        y=vals_m,
        name='มูลค่ารวม (ล้านบาท)',
        marker=dict(size=12, color='#3b82f6', symbol='diamond', line=dict(color='#ffffff', width=2)),
        mode='lines+markers+text',
        text=[f"฿{v:,.0f}M" for v in vals_m],
        textposition='top center',
        yaxis='y2',
        line=dict(width=4, color='#3b82f6')
    ))

    fig.update_layout(
        title=dict(text='🏛️ การกระจายตัวตามช่วงราคา SAM (3D Price Tier Pyramid)', font=dict(size=14, family="Outfit, Sarabun")),
        yaxis=dict(title='จำนวนทรัพย์ (รายการ)', showgrid=False),
        yaxis2=dict(title='มูลค่ารวม (ล้านบาท)', overlaying='y', side='right', showgrid=False),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        height=450,
        margin=dict(t=40, b=10, l=10, r=10),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)'
    )
    return fig

# -----------------------------------------------------------------------------
# 9. 3D SAM Price Dispersion (Sub-Tab 3)
# -----------------------------------------------------------------------------
def render_3d_sam_price_dispersion(box_data, is_dark_mode=False):
    """
    Renders a 3D-styled Box Plot of SAM's top 6 property types with logarithmic depth.
    """
    fig = px.box(
        box_data,
        x='ประเภททรัพย์',
        y='val_million',
        color='ประเภททรัพย์',
        title='📦 การกระจายราคา 6 ประเภททรัพย์หลัก SAM (3D Dispersion Plot)',
        points=False,
        color_discrete_sequence=px.colors.qualitative.Pastel
    )

    fig.update_traces(
        marker=dict(line=dict(width=2, color='rgba(255,255,255,0.8)')),
        line=dict(width=2)
    )

    fig.update_layout(
        title_font=dict(size=14, family="Outfit, Sarabun"),
        height=450, 
        showlegend=False, 
        yaxis_type="log",
        yaxis_title="ราคา (ล้านบาท - สเกล Log)",
        margin=dict(t=40, b=10, l=10, r=10),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)'
    )
    return fig
