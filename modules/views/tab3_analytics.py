import json
import numpy as np
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
import plotly.graph_objects as go
import plotly.express as px

from modules.config.constants import (
    COMPANY_COLORS,
    COMP_BRAND_COLORS,
    COMP_GRADIENT_PALETTES,
    get_gradient_palette,
    get_price_tier,
    PRICE_TIER_ORDER
)
from modules.config.theme import style_plotly_fig

def render_tab3_analytics_view(df_filtered, df_raw, is_dark_mode):
    """
    Renders Tab 3: Competitor & Market Analytics:
    - Sub-tab 1: Market Overview (Market share, 3D Asset Share donut, Top 10 locations, Price histogram)
    - Sub-tab 2: Asset Type Focus (3D Donuts per company by count or total valuation)
    - Sub-tab 3: Portfolio Deep Dive (Single company mode or Head-to-Head 2-company comparison)
    """
    st.markdown("### <i class='fa-solid fa-chart-line' style='color:#059669; margin-right:8px;'></i>วิเคราะห์เชิงลึกและเปรียบเทียบสถิติของคู่แข่ง", unsafe_allow_html=True)
    
    if df_filtered is None or df_filtered.empty:
        st.warning("ไม่มีข้อมูลสำหรับจัดทำแผนภูมิวิเคราะห์สถิติ")
        return

    plotly_template = "plotly_dark" if is_dark_mode else "plotly_white"

    # Create sub-tabs inside Tab 3
    sub_tab1, sub_tab2, sub_tab3 = st.tabs([
        "ภาพรวมตลาด (Market Overview)",
        "สัดส่วนสินค้าคู่แข่ง (Asset Type Focus)",
        "การกระจายตัวพอร์ตโฟลิโอรายบริษัท (Portfolio Deep Dive)"
    ])
    
    # =========================================================================
    # SUB-TAB 1: MARKET OVERVIEW
    # =========================================================================
    with sub_tab1:
        def get_comp_hex_color(c_name):
            if not c_name or pd.isna(c_name):
                return '#3b82f6'
            return COMP_BRAND_COLORS.get(str(c_name).strip(), '#3b82f6')
        
        col_c1, col_c2 = st.columns(2)
        
        # 1. Total Assets by Company with Brand Colors & % Share Badges
        with col_c1:
            with st.container(border=True):
                comp_counts = df_filtered['บริษัท'].value_counts().reset_index()
                comp_counts.columns = ['บริษัท', 'จำนวนทรัพย์สิน']
                tot_units_all = comp_counts['จำนวนทรัพย์สิน'].sum() if not comp_counts.empty else 1
                comp_counts['pct_share'] = (comp_counts['จำนวนทรัพย์สิน'] / tot_units_all) * 100
                
                fig_comp = go.Figure(go.Bar(
                    x=comp_counts['บริษัท'],
                    y=comp_counts['จำนวนทรัพย์สิน'],
                    marker=dict(
                        color=[get_comp_hex_color(c) for c in comp_counts['บริษัท']],
                        cornerradius=10,
                        line=dict(width=1.2, color='rgba(255, 255, 255, 0.4)')
                    ),
                    text=[f"<b>{c:,}</b><br><span style='font-size:9.5px;color:#94a3b8;'>({p:.1f}%)</span>" for c, p in zip(comp_counts['จำนวนทรัพย์สิน'], comp_counts['pct_share'])],
                    textposition='outside',
                    textfont=dict(size=10.5, family="Noto Sans Thai, Inter, sans-serif"),
                    hovertemplate="<b>%{x}</b><br>จำนวนทรัพย์: <b>%{y:,}</b> รายการ<extra></extra>"
                ))
                fig_comp.update_layout(
                    title=dict(text='จำนวนรายการทรัพย์สินเปรียบเทียบแต่ละบริษัท (Market Share)', font=dict(size=14, family="Noto Sans Thai, Inter, sans-serif")),
                    yaxis=dict(title='จำนวนทรัพย์ (รายการ)', showgrid=True, gridcolor='rgba(255,255,255,0.06)' if is_dark_mode else 'rgba(0,0,0,0.05)', zeroline=False),
                    xaxis=dict(showgrid=False),
                    height=450,
                    margin=dict(t=50, b=20, l=10, r=10),
                    template=plotly_template,
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)'
                )
                st.plotly_chart(style_plotly_fig(fig_comp), width="stretch", theme=None)
            
        # 2. Distribution of Property Type in 3D Donut Chart
        with col_c2:
            with st.container(border=True):
                type_counts = df_filtered['ประเภททรัพย์'].value_counts().head(8).reset_index()
                type_counts.columns = ['ประเภททรัพย์', 'จำนวนประกาศ']
                
                vibrant_donut_colors = ['#10b981', '#3b82f6', '#f59e0b', '#06b6d4', '#8b5cf6', '#ec4899', '#14b8a6', '#64748b']
                c2_series_data = [
                    {"name": row['ประเภททรัพย์'], "y": int(row['จำนวนประกาศ']), "color": vibrant_donut_colors[i % len(vibrant_donut_colors)]}
                    for i, (_, row) in enumerate(type_counts.iterrows())
                ]
                
                text_color = "#f8fafc" if is_dark_mode else "#0f172a"
                label_color = "#cbd5e1" if is_dark_mode else "#334155"
                
                html_c2 = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <meta charset="utf-8">
                    <link rel="preconnect" href="https://fonts.googleapis.com">
                    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
                    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=Noto+Sans+Thai:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
                    <script src="https://cdnjs.cloudflare.com/ajax/libs/highcharts/11.4.3/highcharts.js"></script>
                    <script src="https://cdnjs.cloudflare.com/ajax/libs/highcharts/11.4.3/highcharts-3d.js"></script>
                    <style>
                        * {{ 
                            box-sizing: border-box; 
                            font-family: 'Noto Sans Thai', 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif !important;
                        }}
                        body {{
                            background: transparent;
                            margin: 0;
                            padding: 4px;
                            font-family: 'Noto Sans Thai', 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                            color: {text_color};
                            overflow: hidden;
                        }}
                        #chart_type_3d {{
                            height: 430px;
                            width: 100%;
                        }}
                    </style>
                </head>
                <body>
                    <div id="chart_type_3d"></div>
                    <script>
                        Highcharts.setOptions({{
                            chart: {{
                                style: {{
                                    fontFamily: "'Noto Sans Thai', 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
                                }}
                            }}
                        }});
                        Highcharts.chart('chart_type_3d', {{
                            chart: {{
                                type: 'pie',
                                options3d: {{
                                    enabled: true,
                                    alpha: 50,
                                    depth: 38
                                }},
                                backgroundColor: 'transparent',
                                margin: [45, 10, 10, 10]
                            }},
                            title: {{
                                text: 'สัดส่วนประเภททรัพย์หลัก (3D Asset Share)',
                                align: 'left',
                                style: {{ color: '{text_color}', fontSize: '14px', fontFamily: "'Noto Sans Thai', 'Inter', sans-serif", fontWeight: '700' }}
                            }},
                            subtitle: {{
                                text: 'รวมทั้งหมด: <b style="color:#047857;">{tot_units_all:,} รายการ</b>',
                                align: 'left',
                                style: {{ color: '#64748b', fontSize: '12px', fontFamily: "'Noto Sans Thai', 'Inter', sans-serif" }}
                            }},
                            tooltip: {{
                                headerFormat: '',
                                pointFormat: '<b>{{point.name}}</b>: <b>{{point.y:,.0f}} รายการ</b> ({{point.percentage:.1f}}%)',
                                style: {{ fontSize: '13px', fontFamily: "'Noto Sans Thai', 'Inter', sans-serif" }}
                            }},
                            plotOptions: {{
                                pie: {{
                                    innerSize: 0,
                                    depth: 38,
                                    size: '72%',
                                    center: ['50%', '52%'],
                                    dataLabels: {{
                                        enabled: true,
                                        format: '{{point.name}}<br><b>{{point.percentage:.1f}}%</b>',
                                        distance: 14,
                                        style: {{
                                            color: '{label_color}',
                                            textOutline: 'none',
                                            fontSize: '12px',
                                            fontFamily: "'Noto Sans Thai', 'Inter', sans-serif",
                                            fontWeight: '600'
                                        }}
                                    }}
                                }}
                            }},
                            series: [{{
                                name: 'สัดส่วน',
                                data: {json.dumps(c2_series_data)}
                            }}],
                            credits: {{ enabled: false }}
                        }});
                    </script>
                </body>
                </html>
                """
                components.html(html_c2, height=450, scrolling=False)
            
        st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)
        col_c3, col_c4 = st.columns(2)
        
        # 3. Top 10 Provinces with Cyber Gradient Horizontal Bars
        with col_c3:
            with st.container(border=True):
                top_prov = df_filtered['จังหวัด'].value_counts().head(10).reset_index()
                top_prov.columns = ['จังหวัด', 'จำนวนทรัพย์']
                prov_tot = df_filtered['จังหวัด'].count() if not df_filtered.empty else 1
                top_prov['pct'] = (top_prov['จำนวนทรัพย์'] / prov_tot) * 100
                
                fig_prov = go.Figure(go.Bar(
                    x=top_prov['จำนวนทรัพย์'],
                    y=top_prov['จังหวัด'],
                    orientation='h',
                    marker=dict(
                        color=top_prov['จำนวนทรัพย์'],
                        colorscale=[[0, '#06b6d4'], [0.45, '#3b82f6'], [1, '#4f46e5']],
                        cornerradius=10,
                        line=dict(width=1.5, color='rgba(255, 255, 255, 0.5)')
                    ),
                    text=[f"{c:,} ({p:.1f}%)" for c, p in zip(top_prov['จำนวนทรัพย์'], top_prov['pct'])],
                    textposition='outside',
                    textfont=dict(size=10.5, family="Noto Sans Thai, Inter, sans-serif", weight="bold"),
                    hovertemplate="จังหวัด: <b>%{y}</b><br>จำนวนทรัพย์: <b>%{x:,}</b> รายการ<extra></extra>"
                ))
                fig_prov.update_layout(
                    yaxis=dict(autorange="reversed"),
                    xaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.06)' if is_dark_mode else 'rgba(0,0,0,0.05)', zeroline=False),
                    title=dict(text='10 อันดับจังหวัดที่มีทรัพย์สินหนาแน่นที่สุด (Top 10 Locations)', font=dict(size=14, family="Noto Sans Thai, Inter, sans-serif")),
                    height=500,
                    margin=dict(t=50, b=20, l=10, r=10),
                    template=plotly_template,
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)'
                )
                st.plotly_chart(style_plotly_fig(fig_prov), width="stretch", theme=None)
            
        # 4. Price Distribution (Capped at 25 Million Baht)
        with col_c4:
            with st.container(border=True):
                df_price_capped = df_filtered[(df_filtered['ราคา'].notna()) & (df_filtered['ราคา'] <= 25000000)].copy()
                
                def map_simplified_type(t):
                    t_str = str(t).strip()
                    if 'ที่ดิน' in t_str:
                        return 'ที่ดินเปล่า'
                    elif 'คอนโด' in t_str or 'ห้องชุด' in t_str:
                        return 'ห้องชุดพักอาศัย'
                    elif 'บ้านเดี่ยว' in t_str or 'บ้านแฝด' in t_str or 'พูลวิลล่า' in t_str or 'บ้าน' in t_str:
                        return 'บ้านเดี่ยว'
                    elif 'ทาวน์โฮม' in t_str or 'ทาวน์เฮ้าส์' in t_str or 'ทาวน์เฮาส์' in t_str:
                        return 'ทาวน์เฮ้าส์'
                    return np.nan
                
                df_price_capped['ประเภททรัพย์_กลุ่ม'] = df_price_capped['ประเภททรัพย์'].apply(map_simplified_type)
                df_price_capped = df_price_capped[df_price_capped['ประเภททรัพย์_กลุ่ม'].notna()]
                
                df_hist_data = df_price_capped[['ราคา', 'ประเภททรัพย์_กลุ่ม']]
                if len(df_hist_data) > 50000:
                    df_hist_data = df_hist_data.sample(n=50000, random_state=42)
                
                color_map_dist = {
                    "ที่ดินเปล่า": "#06b6d4",
                    "บ้านเดี่ยว": "#10b981", 
                    "ห้องชุดพักอาศัย": "#3b82f6",
                    "คอนโด": "#3b82f6", 
                    "ทาวน์เฮ้าส์": "#f59e0b"
                }
                
                fig_price_dist = px.histogram(
                    df_hist_data,
                    x='ราคา',
                    color='ประเภททรัพย์_กลุ่ม',
                    nbins=40,
                    title='การกระจายตัวของราคาทรัพย์สิน (ไม่เกิน 25 ล้านบาท)',
                    labels={'ราคา': 'ราคาเริ่มต้น (บาท)', 'ประเภททรัพย์_กลุ่ม': 'ประเภททรัพย์'},
                    color_discrete_map=color_map_dist,
                    template=plotly_template,
                    marginal="box",
                    barmode="stack"
                )
                fig_price_dist.update_traces(
                    marker=dict(line=dict(width=0.8, color='rgba(255, 255, 255, 0.4)'), opacity=0.88)
                )
                fig_price_dist.update_layout(
                    title_font=dict(size=14, family="Noto Sans Thai, Inter, sans-serif"), 
                    yaxis_title="จำนวนรายการ",
                    xaxis_title="ราคาเริ่มต้น (บาท)",
                    height=500,
                    margin=dict(l=60, r=40, t=50, b=90),
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)'
                )
                st.plotly_chart(style_plotly_fig(fig_price_dist), width="stretch", theme=None)

    # =========================================================================
    # SUB-TAB 2: ASSET TYPE FOCUS (3D DONUTS)
    # =========================================================================
    with sub_tab2:
        st.markdown("#### <i class='fa-solid fa-home-user' style='color:#059669; margin-right:6px;'></i>สัดส่วนประเภททรัพย์สินคู่แข่งเชิงลึก (Asset Type Focus)", unsafe_allow_html=True)
        
        st.markdown(
            f"<div style='font-size: 0.9rem; font-weight: 700; color: {'#f8fafc' if is_dark_mode else '#0f172a'}; margin-bottom: 4px; display: flex; align-items: center; gap: 6px;'>"
            f"<i class='fa-solid fa-sliders' style='color: #059669;'></i> เลือกเกณฑ์การวิเคราะห์:"
            f"</div>",
            unsafe_allow_html=True
        )
        focus_metric = st.radio(
            "เลือกเกณฑ์การวิเคราะห์", 
            ["จำนวนทรัพย์สิน (Asset Count)", "มูลค่าทรัพย์สินรวม (Total Value)"], 
            horizontal=True, 
            label_visibility="collapsed",
            key="focus_metric_type"
        )
        
        is_val_metric = (focus_metric == "มูลค่าทรัพย์สินรวม (Total Value)")
        
        if is_val_metric:
            value_col = 'มูลค่าทรัพย์สินรวม'
            comp_type_df = df_filtered.groupby(['บริษัท', 'ประเภททรัพย์'])['ราคา'].sum().reset_index(name=value_col)
            comp_type_df = comp_type_df[comp_type_df[value_col] > 0]
        else:
            value_col = 'จำนวนทรัพย์สิน'
            comp_type_df = df_filtered.groupby(['บริษัท', 'ประเภททรัพย์']).size().reset_index(name=value_col)
            
        PROPERTY_TYPE_COLORS = {
            'บ้านเดี่ยว': '#059669',
            'ห้องชุดพักอาศัย': '#2563eb',
            'ทาวน์เฮ้าส์': '#f59e0b',
            'ที่ดินเปล่า': '#06b6d4',
            'อาคารพาณิชย์': '#8b5cf6',
            'โรงงาน/โกดัง': '#ec4899',
            'บ้านแฝด': '#14b8a6',
            'อื่นๆ': '#94a3b8'
        }
        other_color = '#94a3b8'

        PREFERRED_COMPANY_ORDER = ["LED", "SAM", "BAM", "Chayo555", "Chayo", "Chayo NPA", "GHB", "KBANK", "KTB", "SCB", "GSB", "DDproperty", "Livinginsider", "NaYoo", "ZmyHome", "Baania"]
        all_comps = list(comp_type_df['บริษัท'].unique())
        companies = sorted(
            all_comps, 
            key=lambda c: (PREFERRED_COMPANY_ORDER.index(c) if c in PREFERRED_COMPANY_ORDER else 999, c)
        )

        if len(companies) > 0:
            companies_3d_data = []
            for comp in companies:
                comp_color = COMPANY_COLORS.get(comp, '#3b82f6')
                cdf = comp_type_df[comp_type_df['บริษัท'] == comp].sort_values(value_col, ascending=False)
                total = cdf[value_col].sum()
                if total <= 0:
                    continue
                
                cdf = cdf.copy()
                cdf['pct'] = (cdf[value_col] / total) * 100
                major = cdf[cdf['pct'] >= 3.0]
                minor = cdf[cdf['pct'] < 3.0]
                
                series_data = []
                for _, r in major.iterrows():
                    t_name = r['ประเภททรัพย์']
                    t_pct = round(float(r['pct']), 1)
                    t_c = PROPERTY_TYPE_COLORS.get(t_name, '#6366f1')
                    series_data.append({"name": t_name, "y": t_pct, "color": t_c})
                    
                if not minor.empty:
                    other_pct = round(float(minor['pct'].sum()), 1)
                    series_data.append({"name": "อื่นๆ", "y": other_pct, "color": other_color})
                    
                total_display = f"฿{total/1e6:,.0f}M" if is_val_metric and total >= 1e6 else (f"{int(total):,} รายการ" if not is_val_metric else f"฿{total:,.0f}")
                
                pills = []
                for _, r in cdf.head(3).iterrows():
                    t_name = r['ประเภททรัพย์']
                    t_pct = r['pct']
                    t_c = PROPERTY_TYPE_COLORS.get(t_name, '#6366f1')
                    pills.append({"name": t_name, "pct": t_pct, "color": t_c})
                    
                companies_3d_data.append({
                    "company": comp,
                    "color": comp_color,
                    "total_str": total_display,
                    "pills": pills,
                    "series_data": series_data
                })
            
            card_bg = "rgba(15, 23, 42, 0.82)" if is_dark_mode else "linear-gradient(135deg, #ffffff 0%, #f8fafc 100%)"
            card_border = "rgba(255, 255, 255, 0.12)" if is_dark_mode else "rgba(226, 232, 240, 0.9)"
            text_color = "#f8fafc" if is_dark_mode else "#0f172a"
            label_color = "#e2e8f0" if is_dark_mode else "#1e293b"
            
            cards_html = ""
            js_init = ""
            for idx, item in enumerate(companies_3d_data):
                comp = item['company']
                comp_color = item['color']
                total_str = item['total_str']
                top_pills_html = "".join([
                    f"<span style='display:inline-block;background:{p['color']}18;color:{p['color']};border:1px solid {p['color']}40;border-radius:6px;padding:3px 8px;font-size:12px;font-weight:700;margin:2px 3px;'>{p['name']} {p['pct']:.0f}%</span>"
                    for p in item['pills']
                ])
                
                cards_html += f"""
                <div class="donut-card" style="border-top: 4px solid {comp_color};">
                    <div class="card-header">
                        <span style="color: {comp_color}; font-weight: 800; font-size: 18px;"><i class="fa-solid fa-building" style="margin-right:6px; font-size:15px;"></i>{comp}</span>
                        <span style="color: #64748b; font-weight: 700; font-size: 14.5px;">รวม: <b style="color:{text_color};">{total_str}</b></span>
                    </div>
                    <div style="text-align:center; margin-top:4px; margin-bottom: 6px;">{top_pills_html}</div>
                    <div id="chart3d_{idx}" class="chart-box"></div>
                </div>
                """
                
                series_json = json.dumps(item['series_data'])
                js_init += f"""
                Highcharts.chart('chart3d_{idx}', {{
                    chart: {{
                        type: 'pie',
                        options3d: {{
                            enabled: true,
                            alpha: 48,
                            beta: 0,
                            depth: 36
                        }},
                        backgroundColor: 'transparent',
                        margin: [10, 24, 10, 24]
                    }},
                    title: {{ text: null }},
                    tooltip: {{
                        headerFormat: '',
                        pointFormat: '<b>{{point.name}}</b>: <b>{{point.y:.1f}}%</b>',
                        style: {{ fontSize: '13px', fontFamily: 'Noto Sans Thai' }}
                    }},
                    plotOptions: {{
                        pie: {{
                            innerSize: 0,
                            depth: 36,
                            size: '64%',
                            center: ['50%', '50%'],
                            dataLabels: {{
                                enabled: true,
                                crop: false,
                                overflow: 'allow',
                                distance: 10,
                                connectorPadding: 2,
                                connectorWidth: 1.2,
                                formatter: function() {{
                                    var n = this.point.name;
                                    if (n === 'ที่ดินพร้อมสิ่งปลูกสร้าง') n = 'ที่ดิน+สิ่งปลูกสร้าง';
                                    return n + '<br><b>' + this.point.y.toFixed(1) + '%</b>';
                                }},
                                style: {{
                                    color: '{label_color}',
                                    textOutline: 'none',
                                    fontSize: '11.5px',
                                    fontWeight: '700',
                                    fontFamily: 'Noto Sans Thai, Inter, sans-serif'
                                }}
                            }}
                        }}
                    }},
                    series: [{{
                        name: 'สัดส่วน',
                        data: {series_json}
                    }}],
                    credits: {{ enabled: false }}
                }});
                """
            
            n_items = len(companies_3d_data)
            est_rows = (n_items + 1) // 2
            total_height = max(580, est_rows * 520 + 40)
            
            full_html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <link rel="preconnect" href="https://fonts.googleapis.com">
                <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
                <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=Noto+Sans+Thai:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
                <script src="https://cdnjs.cloudflare.com/ajax/libs/highcharts/11.4.3/highcharts.js"></script>
                <script src="https://cdnjs.cloudflare.com/ajax/libs/highcharts/11.4.3/highcharts-3d.js"></script>
                <style>
                    * {{ 
                        box-sizing: border-box; 
                        font-family: 'Noto Sans Thai', 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif !important;
                    }}
                    body {{
                        background: transparent;
                        margin: 0;
                        padding: 4px;
                        font-family: 'Noto Sans Thai', 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                        color: {text_color};
                    }}
                    .grid-container {{
                        display: grid;
                        grid-template-columns: repeat(auto-fill, minmax(460px, 1fr));
                        gap: 20px;
                        width: 100%;
                    }}
                    .donut-card {{
                        background: {card_bg};
                        border: 1px solid {card_border};
                        border-radius: 16px;
                        padding: 18px 10px 12px 10px;
                        box-shadow: 0 8px 24px rgba(0,0,0,0.08);
                        display: flex;
                        flex-direction: column;
                        justify-content: space-between;
                        min-width: 0;
                        transition: transform 0.2s ease, box-shadow 0.2s ease;
                    }}
                    .donut-card:hover {{
                        transform: translateY(-3px);
                        box-shadow: 0 12px 30px rgba(0,0,0,0.14);
                    }}
                    .card-header {{
                        display: flex;
                        justify-content: space-between;
                        align-items: center;
                        margin-bottom: 8px;
                    }}
                    .chart-box {{
                        height: 390px;
                        width: 100%;
                    }}
                </style>
            </head>
            <body>
                <div class="grid-container">
                    {cards_html}
                </div>
                <script>
                    Highcharts.setOptions({{
                        chart: {{
                            style: {{
                                fontFamily: "'Noto Sans Thai', 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
                            }}
                        }}
                    }});
                    {js_init}
                    
                    function notifyResize() {{
                        try {{
                            const docH = Math.max(
                                document.body.scrollHeight, 
                                document.documentElement.scrollHeight,
                                document.body.offsetHeight,
                                document.documentElement.offsetHeight
                            );
                            if (window.frameElement) {{
                                window.frameElement.style.height = (docH + 25) + 'px';
                            }}
                            window.parent.postMessage({{
                                type: 'streamlit:setFrameHeight',
                                height: docH + 25
                            }}, '*');
                        }} catch(e) {{}}
                    }}

                    window.addEventListener('DOMContentLoaded', notifyResize);
                    window.addEventListener('load', function() {{
                        notifyResize();
                        setTimeout(notifyResize, 250);
                        setTimeout(notifyResize, 600);
                    }});
                    window.addEventListener('resize', function() {{
                        if (window.Highcharts && Highcharts.charts) {{
                            Highcharts.charts.forEach(function(c) {{
                                if (c) c.reflow();
                            }});
                        }}
                        notifyResize();
                    }});
                    if (window.ResizeObserver) {{
                        new ResizeObserver(function() {{
                            notifyResize();
                        }}).observe(document.body);
                    }}
                </script>
            </body>
            </html>
            """
            components.html(full_html, height=total_height, scrolling=False)

    # =========================================================================
    # SUB-TAB 3: PORTFOLIO DEEP DIVE (SINGLE OR 2-COMPANY COMPARISON)
    # =========================================================================
    with sub_tab3:
        col_head1, col_head2, col_head3 = st.columns([1.8, 1.1, 1.1])
        with col_head1:
            st.markdown("#### <i class='fa-solid fa-scale-balanced' style='color:#059669; margin-right:6px;'></i>การกระจายตัวเชิงลึกของพอร์ตโฟลิโอรายบริษัท", unsafe_allow_html=True)
            st.caption("วิเคราะห์และเปรียบเทียบการกระจายตัวตามช่วงราคา และประเภททรัพย์สินหลักระหว่างบริษัท")
        
        comp_list_avail = []
        if not df_filtered.empty:
            comp_list_avail = list(df_filtered['บริษัท'].dropna().unique())
        elif df_raw is not None and not df_raw.empty:
            comp_list_avail = list(df_raw['บริษัท'].dropna().unique())
            
        PREFERRED_COMPANY_ORDER = ["LED", "SAM", "BAM", "Chayo555", "Chayo", "Chayo NPA", "GHB", "KBANK", "KTB", "SCB", "GSB", "DDproperty", "Livinginsider", "NaYoo", "ZmyHome", "Baania"]
        comp_options = sorted(
            comp_list_avail, 
            key=lambda c: (PREFERRED_COMPANY_ORDER.index(c) if c in PREFERRED_COMPANY_ORDER else 999, c)
        )
        
        default_idx1 = comp_options.index("SAM") if "SAM" in comp_options else 0
        
        with col_head2:
            st.markdown(
                f"<div style='font-size: 0.9rem; font-weight: 700; color: {'#f8fafc' if is_dark_mode else '#0f172a'}; margin-bottom: 4px; display: flex; align-items: center; gap: 6px;'>"
                f"<i class='fa-solid fa-building' style='color: #059669;'></i> บริษัทหลัก (Company 1):"
                f"</div>",
                unsafe_allow_html=True
            )
            selected_company = st.selectbox(
                "บริษัทหลัก (Company 1):",
                options=comp_options,
                index=default_idx1,
                label_visibility="collapsed",
                key="tab2_subtab3_selected_company"
            )
            
        comp_2_options = ["(ไม่เปรียบเทียบ - ดูบริษัทเดียว)"] + [c for c in comp_options if c != selected_company]
        if selected_company == "SAM" and "BAM" in comp_2_options:
            def_idx2 = comp_2_options.index("BAM")
        elif selected_company == "BAM" and "SAM" in comp_2_options:
            def_idx2 = comp_2_options.index("SAM")
        elif len(comp_2_options) > 1:
            def_idx2 = 1
        else:
            def_idx2 = 0

        with col_head3:
            st.markdown(
                f"<div style='font-size: 0.9rem; font-weight: 700; color: {'#f8fafc' if is_dark_mode else '#0f172a'}; margin-bottom: 4px; display: flex; align-items: center; gap: 6px;'>"
                f"<i class='fa-solid fa-arrows-left-right' style='color: #059669;'></i> เปรียบเทียบกับ (Company 2):"
                f"</div>",
                unsafe_allow_html=True
            )
            compare_company = st.selectbox(
                "เปรียบเทียบกับ (Company 2):",
                options=comp_2_options,
                index=def_idx2,
                label_visibility="collapsed",
                key="tab2_subtab3_compare_company"
            )
            
        comp_bar_color = COMP_BRAND_COLORS.get(selected_company, "#10b981")
        comp2_bar_color = COMP_BRAND_COLORS.get(compare_company, "#3b82f6")

        comp_df_tab2 = df_filtered[df_filtered['บริษัท'] == selected_company].copy() if not df_filtered.empty else pd.DataFrame()
        if comp_df_tab2.empty and df_raw is not None:
            comp_df_tab2 = df_raw[df_raw['บริษัท'] == selected_company].copy()

        is_comparing = (compare_company != "(ไม่เปรียบเทียบ - ดูบริษัทเดียว)")
        comp_df_2 = pd.DataFrame()
        if is_comparing:
            comp_df_2 = df_filtered[df_filtered['บริษัท'] == compare_company].copy() if not df_filtered.empty else pd.DataFrame()
            if comp_df_2.empty and df_raw is not None:
                comp_df_2 = df_raw[df_raw['บริษัท'] == compare_company].copy()

        if comp_df_tab2.empty and (not is_comparing or comp_df_2.empty):
            st.warning(f"ไม่พบข้อมูลทรัพย์สินของ {selected_company} ในตัวกรองปัจจุบัน")
        elif is_comparing and not comp_df_2.empty:
            # ==========================================
            # COMPARISON MODE: Company 1 vs Company 2
            # ==========================================
            comp_df_tab2['Price_Tier'] = comp_df_tab2['ราคา'].apply(get_price_tier)
            comp_df_2['Price_Tier'] = comp_df_2['ราคา'].apply(get_price_tier)

            c1_cnt, c2_cnt = len(comp_df_tab2), len(comp_df_2)
            c1_val, c2_val = comp_df_tab2['ราคา'].sum() / 1e6, comp_df_2['ราคา'].sum() / 1e6
            c1_avg, c2_avg = (comp_df_tab2['ราคา'].mean() / 1e6) if c1_cnt > 0 else 0, (comp_df_2['ราคา'].mean() / 1e6) if c2_cnt > 0 else 0
            c1_med, c2_med = (comp_df_tab2['ราคา'].median() / 1e6) if c1_cnt > 0 else 0, (comp_df_2['ราคา'].median() / 1e6) if c2_cnt > 0 else 0

            card_bg = 'rgba(15, 23, 42, 0.75)' if is_dark_mode else 'linear-gradient(135deg, #ffffff 0%, #f8fafc 100%)'
            card_border = 'rgba(255, 255, 255, 0.1)' if is_dark_mode else 'rgba(226, 232, 240, 0.8)'

            st.markdown(f"""
            <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin-top: 6px; margin-bottom: 20px;">
                <div style="background: {card_bg}; border: 1px solid {card_border}; border-left: 4px solid {comp_bar_color}; border-radius: 12px; padding: 14px 16px; box-shadow: 0 4px 16px rgba(0,0,0,0.06);">
                    <div style="font-size: 0.78rem; font-weight: 700; color: #64748b; margin-bottom: 6px;"><i class="fa fa-boxes"></i> จำนวนทรัพย์รวม (Units)</div>
                    <div style="display: flex; justify-content: space-between; align-items: baseline; margin-top: 4px;">
                        <span style="font-size: 1.05rem; font-weight: 800; color: {comp_bar_color};">{selected_company}: <b>{c1_cnt:,}</b></span>
                        <span style="font-size: 1.05rem; font-weight: 800; color: {comp2_bar_color};">{compare_company}: <b>{c2_cnt:,}</b></span>
                    </div>
                </div>
                <div style="background: {card_bg}; border: 1px solid {card_border}; border-left: 4px solid #f59e0b; border-radius: 12px; padding: 14px 16px; box-shadow: 0 4px 16px rgba(0,0,0,0.06);">
                    <div style="font-size: 0.78rem; font-weight: 700; color: #64748b; margin-bottom: 6px;"><i class="fa fa-coins"></i> มูลค่าพอร์ตโฟลิโอรวม (MB)</div>
                    <div style="display: flex; justify-content: space-between; align-items: baseline; margin-top: 4px;">
                        <span style="font-size: 1.05rem; font-weight: 800; color: {comp_bar_color};">{selected_company}: <b>฿{c1_val:,.0f}M</b></span>
                        <span style="font-size: 1.05rem; font-weight: 800; color: {comp2_bar_color};">{compare_company}: <b>฿{c2_val:,.0f}M</b></span>
                    </div>
                </div>
                <div style="background: {card_bg}; border: 1px solid {card_border}; border-left: 4px solid #8b5cf6; border-radius: 12px; padding: 14px 16px; box-shadow: 0 4px 16px rgba(0,0,0,0.06);">
                    <div style="font-size: 0.78rem; font-weight: 700; color: #64748b; margin-bottom: 6px;"><i class="fa fa-tag"></i> ราคาเฉลี่ยต่อยูนิต (Avg Price)</div>
                    <div style="display: flex; justify-content: space-between; align-items: baseline; margin-top: 4px;">
                        <span style="font-size: 1.05rem; font-weight: 800; color: {comp_bar_color};">{selected_company}: <b>฿{c1_avg:,.2f}M</b></span>
                        <span style="font-size: 1.05rem; font-weight: 800; color: {comp2_bar_color};">{compare_company}: <b>฿{c2_avg:,.2f}M</b></span>
                    </div>
                </div>
                <div style="background: {card_bg}; border: 1px solid {card_border}; border-left: 4px solid #06b6d4; border-radius: 12px; padding: 14px 16px; box-shadow: 0 4px 16px rgba(0,0,0,0.06);">
                    <div style="font-size: 0.78rem; font-weight: 700; color: #64748b; margin-bottom: 6px;"><i class="fa fa-balance-scale"></i> ราคามัธยฐาน (Median Price)</div>
                    <div style="display: flex; justify-content: space-between; align-items: baseline; margin-top: 4px;">
                        <span style="font-size: 1.05rem; font-weight: 800; color: {comp_bar_color};">{selected_company}: <b>฿{c1_med:,.2f}M</b></span>
                        <span style="font-size: 1.05rem; font-weight: 800; color: {comp2_bar_color};">{compare_company}: <b>฿{c2_med:,.2f}M</b></span>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            col_c1, col_c2 = st.columns(2)
            with col_c1:
                tier1 = comp_df_tab2.groupby('Price_Tier', observed=False).agg(count=('ราคา', 'count'), val=('ราคา', 'sum')).reindex(PRICE_TIER_ORDER).reset_index().fillna(0)
                tier2 = comp_df_2.groupby('Price_Tier', observed=False).agg(count=('ราคา', 'count'), val=('ราคา', 'sum')).reindex(PRICE_TIER_ORDER).reset_index().fillna(0)
                tier1['val_million'] = tier1['val'] / 1e6
                tier2['val_million'] = tier2['val'] / 1e6

                grad1 = get_gradient_palette(selected_company, len(PRICE_TIER_ORDER))
                grad2 = get_gradient_palette(compare_company, len(PRICE_TIER_ORDER))

                fig_tier_comp = go.Figure()
                fig_tier_comp.add_trace(go.Bar(
                    x=tier1['Price_Tier'],
                    y=tier1['count'],
                    name=f'{selected_company} (จำนวนทรัพย์)',
                    yaxis='y',
                    marker=dict(
                        color=grad1,
                        cornerradius=8,
                        line=dict(width=1.2, color='rgba(255, 255, 255, 0.4)')
                    ),
                    text=[f"{int(c):,}" for c in tier1['count']],
                    textposition='outside',
                    textfont=dict(size=11, family="Noto Sans Thai", weight="bold"),
                    hovertemplate=f"<b>{selected_company}</b><br>ช่วงราคา: %{{x}}<br>จำนวนทรัพย์: <b>%{{y:,}}</b> รายการ<extra></extra>"
                ))
                fig_tier_comp.add_trace(go.Bar(
                    x=tier2['Price_Tier'],
                    y=tier2['count'],
                    name=f'{compare_company} (จำนวนทรัพย์)',
                    yaxis='y',
                    marker=dict(
                        color=grad2,
                        cornerradius=8,
                        line=dict(width=1.2, color='rgba(255, 255, 255, 0.4)')
                    ),
                    text=[f"{int(c):,}" for c in tier2['count']],
                    textposition='outside',
                    textfont=dict(size=11, family="Noto Sans Thai", weight="bold"),
                    hovertemplate=f"<b>{compare_company}</b><br>ช่วงราคา: %{{x}}<br>จำนวนทรัพย์: <b>%{{y:,}}</b> รายการ<extra></extra>"
                ))
                fig_tier_comp.add_trace(go.Scatter(
                    x=tier1['Price_Tier'],
                    y=tier1['val_million'],
                    name=f'{selected_company} (มูลค่ารวม MB)',
                    yaxis='y2',
                    mode='lines+markers+text',
                    line=dict(width=3, color=comp_bar_color, shape='spline'),
                    marker=dict(size=8, color=comp_bar_color, line=dict(width=2, color='#ffffff')),
                    text=[f"฿{v:,.0f}M" if v > 0 else "" for v in tier1['val_million']],
                    textposition='top center',
                    textfont=dict(size=10, family="Noto Sans Thai", color=comp_bar_color, weight="bold"),
                    hovertemplate=f"มูลค่ารวม {selected_company}: <b>฿%{{y:,.1f}}M</b><extra></extra>"
                ))
                fig_tier_comp.add_trace(go.Scatter(
                    x=tier2['Price_Tier'],
                    y=tier2['val_million'],
                    name=f'{compare_company} (มูลค่ารวม MB)',
                    yaxis='y2',
                    mode='lines+markers+text',
                    line=dict(width=3, color=comp2_bar_color, shape='spline', dash='dot'),
                    marker=dict(size=8, color=comp2_bar_color, line=dict(width=2, color='#ffffff')),
                    text=[f"฿{v:,.0f}M" if v > 0 else "" for v in tier2['val_million']],
                    textposition='top center',
                    textfont=dict(size=10, family="Noto Sans Thai", color=comp2_bar_color, weight="bold"),
                    hovertemplate=f"มูลค่ารวม {compare_company}: <b>฿%{{y:,.1f}}M</b><extra></extra>"
                ))

                fig_tier_comp.update_layout(
                    title=dict(text=f'เปรียบเทียบจำนวนทรัพย์และมูลค่าตามช่วงราคา ({selected_company} vs {compare_company})', font=dict(size=14, family="Noto Sans Thai")),
                    barmode='group',
                    bargroupgap=0.1,
                    bargap=0.25,
                    yaxis=dict(title='จำนวนทรัพย์ (รายการ)', showgrid=True, gridcolor='rgba(255,255,255,0.06)' if is_dark_mode else 'rgba(0,0,0,0.05)', zeroline=False),
                    yaxis2=dict(title='มูลค่ารวม (ล้านบาท)', overlaying='y', side='right', showgrid=False, zeroline=False),
                    xaxis=dict(showgrid=False),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(family="Noto Sans Thai", size=11)),
                    height=480,
                    margin=dict(t=60, b=20, l=10, r=10),
                    template=plotly_template,
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)'
                )
                st.plotly_chart(style_plotly_fig(fig_tier_comp), width="stretch", theme=None)

            with col_c2:
                top_types1 = comp_df_tab2['ประเภททรัพย์'].value_counts().head(6).index.tolist()
                top_types2 = comp_df_2['ประเภททรัพย์'].value_counts().head(6).index.tolist()
                combined_top = list(dict.fromkeys(top_types1 + top_types2))[:6]

                box_df = pd.concat([comp_df_tab2, comp_df_2], ignore_index=True)
                box_df = box_df[box_df['ประเภททรัพย์'].isin(combined_top) & (box_df['ราคา'] > 0)]
                box_df['val_million'] = box_df['ราคา'] / 1e6

                fig_box = px.box(
                    box_df,
                    x='ประเภททรัพย์',
                    y='val_million',
                    color='บริษัท',
                    color_discrete_map={selected_company: comp_bar_color, compare_company: comp2_bar_color},
                    title=f'เปรียบเทียบการกระจายราคาของ 6 ประเภททรัพย์หลัก ({selected_company} vs {compare_company})',
                    template=plotly_template,
                    points=False
                )
                fig_box.update_traces(
                    boxmean=True,
                    line=dict(width=1.5),
                    marker=dict(opacity=0.85)
                )
                fig_box.update_layout(
                    title_font=dict(size=14, family="Noto Sans Thai"),
                    height=460, 
                    yaxis_type="log",
                    yaxis_title="ราคา (ล้านบาท - สเกล Log)",
                    yaxis=dict(
                        showgrid=True, 
                        gridcolor='rgba(255,255,255,0.06)' if is_dark_mode else 'rgba(0,0,0,0.05)',
                        tickmode='array',
                        tickvals=[0.5, 1, 2, 5, 10, 20, 50, 100],
                        ticktext=['฿0.5M', '฿1M', '฿2M', '฿5M', '฿10M', '฿20M', '฿50M', '฿100M']
                    ),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(family="Noto Sans Thai", size=12)),
                    margin=dict(t=50, b=20, l=10, r=10),
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)'
                )
                st.plotly_chart(style_plotly_fig(fig_box), width="stretch", theme=None)

            col_c3, col_c4 = st.columns(2)
            with col_c3:
                t_share1 = comp_df_tab2['ประเภททรัพย์'].value_counts(normalize=True).head(6).reset_index()
                t_share1.columns = ['ประเภททรัพย์', 'pct']
                t_share1['pct'] = t_share1['pct'] * 100
                t_share1['บริษัท'] = selected_company

                t_share2 = comp_df_2['ประเภททรัพย์'].value_counts(normalize=True).head(6).reset_index()
                t_share2.columns = ['ประเภททรัพย์', 'pct']
                t_share2['pct'] = t_share2['pct'] * 100
                t_share2['บริษัท'] = compare_company

                common_types = list(dict.fromkeys(t_share1['ประเภททรัพย์'].tolist() + t_share2['ประเภททรัพย์'].tolist()))[:6]
                t_share1_full = t_share1.set_index('ประเภททรัพย์').reindex(common_types).fillna(0).reset_index()
                t_share2_full = t_share2.set_index('ประเภททรัพย์').reindex(common_types).fillna(0).reset_index()

                grad_share1 = get_gradient_palette(selected_company, len(common_types))
                grad_share2 = get_gradient_palette(compare_company, len(common_types))

                fig_share = go.Figure()
                fig_share.add_trace(go.Bar(
                    y=common_types,
                    x=t_share1_full['pct'],
                    name=f'{selected_company}',
                    orientation='h',
                    marker=dict(
                        color=grad_share1,
                        cornerradius=8,
                        line=dict(width=1.2, color='rgba(255, 255, 255, 0.4)')
                    ),
                    text=[f"{p:.1f}%" if p > 0 else "" for p in t_share1_full['pct']],
                    textposition='outside',
                    textfont=dict(size=11, family="Noto Sans Thai", weight="bold"),
                    hovertemplate=f"<b>{selected_company}</b><br>ประเภท: %{{y}}<br>สัดส่วน: <b>%{{x:.1f}}%</b><extra></extra>"
                ))
                fig_share.add_trace(go.Bar(
                    y=common_types,
                    x=t_share2_full['pct'],
                    name=f'{compare_company}',
                    orientation='h',
                    marker=dict(
                        color=grad_share2,
                        cornerradius=8,
                        line=dict(width=1.2, color='rgba(255, 255, 255, 0.4)')
                    ),
                    text=[f"{p:.1f}%" if p > 0 else "" for p in t_share2_full['pct']],
                    textposition='outside',
                    textfont=dict(size=11, family="Noto Sans Thai", weight="bold"),
                    hovertemplate=f"<b>{compare_company}</b><br>ประเภท: %{{y}}<br>สัดส่วน: <b>%{{x:.1f}}%</b><extra></extra>"
                ))
                fig_share.update_layout(
                    title=dict(text=f'สัดส่วนประเภททรัพย์ในพอร์ตโฟลิโอ (% Share)', font=dict(size=14, family="Noto Sans Thai")),
                    barmode='group',
                    bargroupgap=0.1,
                    bargap=0.25,
                    xaxis_title="สัดส่วนในพอร์ตโฟลิโอ (%)",
                    xaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.06)' if is_dark_mode else 'rgba(0,0,0,0.05)', zeroline=False),
                    yaxis_title="",
                    yaxis=dict(autorange="reversed"),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(family="Noto Sans Thai", size=12)),
                    height=440,
                    margin=dict(t=50, b=20, l=10, r=10),
                    template=plotly_template,
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)'
                )
                st.plotly_chart(style_plotly_fig(fig_share), width="stretch", theme=None)

            with col_c4:
                if 'ภาค' in comp_df_tab2.columns and 'ภาค' in comp_df_2.columns:
                    regions_all = ["ภาคกลาง", "ภาคเหนือ", "ภาคตะวันออกเฉียงเหนือ", "ภาคตะวันออก", "ภาคใต้", "ภาคตะวันตก"]
                    r1 = comp_df_tab2['ภาค'].value_counts().reindex(regions_all).fillna(0).reset_index()
                    r1.columns = ['ภาค', 'count']
                    r2 = comp_df_2['ภาค'].value_counts().reindex(regions_all).fillna(0).reset_index()
                    r2.columns = ['ภาค', 'count']

                    grad_reg1 = get_gradient_palette(selected_company, len(regions_all))
                    grad_reg2 = get_gradient_palette(compare_company, len(regions_all))

                    fig_region = go.Figure()
                    fig_region.add_trace(go.Bar(
                        x=regions_all,
                        y=r1['count'],
                        name=f'{selected_company}',
                        marker=dict(
                            color=grad_reg1,
                            cornerradius=8,
                            line=dict(width=1.2, color='rgba(255, 255, 255, 0.4)')
                        ),
                        text=[f"{int(c):,}" if c > 0 else "" for c in r1['count']],
                        textposition='outside',
                        textfont=dict(size=11, family="Noto Sans Thai", weight="bold"),
                        hovertemplate=f"<b>{selected_company}</b><br>ภูมิภาค: %{{x}}<br>จำนวน: <b>%{{y:,}}</b> รายการ<extra></extra>"
                    ))
                    fig_region.add_trace(go.Bar(
                        x=regions_all,
                        y=r2['count'],
                        name=f'{compare_company}',
                        marker=dict(
                            color=grad_reg2,
                            cornerradius=8,
                            line=dict(width=1.2, color='rgba(255, 255, 255, 0.4)')
                        ),
                        text=[f"{int(c):,}" if c > 0 else "" for c in r2['count']],
                        textposition='outside',
                        textfont=dict(size=11, family="Noto Sans Thai", weight="bold"),
                        hovertemplate=f"<b>{compare_company}</b><br>ภูมิภาค: %{{x}}<br>จำนวน: <b>%{{y:,}}</b> รายการ<extra></extra>"
                    ))
                    fig_region.update_layout(
                        title=dict(text=f'เปรียบเทียบการกระจายตัวตามภูมิภาค ({selected_company} vs {compare_company})', font=dict(size=14, family="Noto Sans Thai")),
                        barmode='group',
                        bargroupgap=0.1,
                        bargap=0.25,
                        xaxis_title="ภูมิภาค",
                        xaxis=dict(showgrid=False),
                        yaxis_title="จำนวนทรัพย์ (รายการ)",
                        yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.06)' if is_dark_mode else 'rgba(0,0,0,0.05)', zeroline=False),
                        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(family="Noto Sans Thai", size=12)),
                        height=440,
                        margin=dict(t=50, b=20, l=10, r=10),
                        template=plotly_template,
                        plot_bgcolor='rgba(0,0,0,0)',
                        paper_bgcolor='rgba(0,0,0,0)'
                    )
                    st.plotly_chart(style_plotly_fig(fig_region), width="stretch", theme=None)
        else:
            # ==========================================
            # SINGLE COMPANY MODE
            # ==========================================
            comp_df_tab2['Price_Tier'] = comp_df_tab2['ราคา'].apply(get_price_tier)

            col_s1, col_s2 = st.columns(2)
            with col_s1:
                tier_df = comp_df_tab2.groupby('Price_Tier', observed=False).agg(
                    count=('รหัสทรัพย์', 'count') if 'รหัสทรัพย์' in comp_df_tab2.columns else ('ราคา', 'count'),
                    total_val=('ราคา', 'sum')
                ).reindex(PRICE_TIER_ORDER).reset_index()
                tier_df['count'] = tier_df['count'].fillna(0)
                tier_df['val_million'] = tier_df['total_val'].fillna(0) / 1e6

                single_grad = get_gradient_palette(selected_company, len(PRICE_TIER_ORDER))

                fig_tier = go.Figure()
                fig_tier.add_trace(go.Bar(
                    x=tier_df['Price_Tier'],
                    y=tier_df['count'],
                    name='จำนวนทรัพย์ (รายการ)',
                    marker=dict(
                        color=single_grad,
                        cornerradius=8,
                        line=dict(width=1.2, color='rgba(255, 255, 255, 0.45)')
                    ),
                    yaxis='y',
                    text=tier_df['count'].astype(int),
                    textposition='outside',
                    textfont=dict(size=11, family="Noto Sans Thai", weight="bold"),
                    hovertemplate=f"<b>{selected_company}</b><br>ช่วงราคา: %{{x}}<br>จำนวนทรัพย์: <b>%{{y:,}}</b> รายการ<extra></extra>"
                ))
                fig_tier.add_trace(go.Scatter(
                    x=tier_df['Price_Tier'],
                    y=tier_df['val_million'],
                    name='มูลค่ารวม (ล้านบาท)',
                    mode='lines+markers+text',
                    text=[f"฿{v:,.0f}M" for v in tier_df['val_million']],
                    textposition='top center',
                    textfont=dict(size=11, family="Noto Sans Thai", color="#3b82f6", weight="bold"),
                    yaxis='y2',
                    line=dict(width=3.5, color='#3b82f6', shape='spline'),
                    marker=dict(size=9, color='#3b82f6', line=dict(width=2, color='#ffffff')),
                    fill='tozeroy',
                    fillcolor='rgba(59, 130, 246, 0.08)',
                    hovertemplate="มูลค่ารวม: <b>฿%{y:,.1f}M</b><extra></extra>"
                ))
                fig_tier.update_layout(
                    title=dict(text=f'การกระจายตัวตามช่วงราคา {selected_company} (Price Tier Pyramid)', font=dict(size=14, family="Noto Sans Thai")),
                    yaxis=dict(title='จำนวนทรัพย์ (รายการ)', showgrid=True, gridcolor='rgba(255,255,255,0.06)' if is_dark_mode else 'rgba(0,0,0,0.05)', zeroline=False),
                    yaxis2=dict(title='มูลค่ารวม (ล้านบาท)', overlaying='y', side='right', showgrid=False),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(family="Noto Sans Thai", size=12)),
                    height=460,
                    margin=dict(t=50, b=20, l=10, r=10),
                    template=plotly_template,
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)'
                )
                st.plotly_chart(style_plotly_fig(fig_tier), width="stretch", theme=None)

            with col_s2:
                top_types = comp_df_tab2['ประเภททรัพย์'].value_counts().head(6).index.tolist()
                box_data = comp_df_tab2[comp_df_tab2['ประเภททรัพย์'].isin(top_types) & (comp_df_tab2['ราคา'] > 0)].copy()
                box_data['val_million'] = box_data['ราคา'] / 1e6
                
                fig_box = px.box(
                    box_data,
                    x='ประเภททรัพย์',
                    y='val_million',
                    color='ประเภททรัพย์',
                    title=f'การกระจายราคาของ 6 ประเภททรัพย์หลัก {selected_company} (Box Plot - ล้านบาท)',
                    template=plotly_template,
                    color_discrete_sequence=get_gradient_palette(selected_company, len(top_types)),
                    points=False
                )
                fig_box.update_traces(
                    boxmean=True,
                    line=dict(width=1.5),
                    marker=dict(opacity=0.85)
                )
                fig_box.update_layout(
                    title_font=dict(size=14, family="Noto Sans Thai"),
                    height=460, 
                    showlegend=False, 
                    yaxis_type="log",
                    yaxis_title="ราคา (ล้านบาท - สเกล Log)",
                    yaxis=dict(
                        showgrid=True, 
                        gridcolor='rgba(255,255,255,0.06)' if is_dark_mode else 'rgba(0,0,0,0.05)',
                        tickmode='array',
                        tickvals=[0.5, 1, 2, 5, 10, 20, 50, 100],
                        ticktext=['฿0.5M', '฿1M', '฿2M', '฿5M', '฿10M', '฿20M', '฿50M', '฿100M']
                    ),
                    margin=dict(t=50, b=20, l=10, r=10),
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)'
                )
                st.plotly_chart(style_plotly_fig(fig_box), width="stretch", theme=None)
