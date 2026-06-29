"""Test 1: BAM only, Test 2: BAM small sample, Test 3: Check lat/lon ranges"""
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

df = pd.read_excel('all_assets.xlsx')
df = df.replace(["$undefined", "undefined", "nan", "NaN", "NAN"], np.nan)
df['ละติจูด'] = pd.to_numeric(df['ละติจูด'], errors='coerce')
df['ลองจิจูด'] = pd.to_numeric(df['ลองจิจูด'], errors='coerce')
df['ราคา'] = pd.to_numeric(df['ราคา'], errors='coerce')

bam = df[(df['บริษัท']=='BAM') & df['ละติจูด'].notna() & df['ลองจิจูด'].notna()].copy()

print(f"BAM points with coords: {len(bam)}")
print(f"Lat range: {bam['ละติจูด'].min():.6f} to {bam['ละติจูด'].max():.6f}")
print(f"Lon range: {bam['ลองจิจูด'].min():.6f} to {bam['ลองจิจูด'].max():.6f}")
print(f"Lat == 0: {(bam['ละติจูด']==0).sum()}")
print(f"Lon == 0: {(bam['ลองจิจูด']==0).sum()}")
print(f"Lat outside Thailand (5-21): {((bam['ละติจูด']<5)|(bam['ละติจูด']>21)).sum()}")
print(f"Lon outside Thailand (97-106): {((bam['ลองจิจูด']<97)|(bam['ลองจิจูด']>106)).sum()}")

# Check duplicate coords
dupes = bam.duplicated(subset=['ละติจูด','ลองจิจูด'], keep=False).sum()
print(f"Duplicate coordinates: {dupes}/{len(bam)}")

# Test with just 50 BAM points
bam_small = bam.head(50).copy()
bam_small['title'] = bam_small['ชื่อประกาศ'].fillna('N/A').astype(str).str[:50]

fig1 = px.scatter_mapbox(
    bam_small, lat="ละติจูด", lon="ลองจิจูด",
    hover_name="title",
    zoom=5, height=500,
)
fig1.update_layout(mapbox_style="open-street-map", margin={"r":0,"t":30,"l":0,"b":0}, title="Test 1: BAM 50 points only")
fig1.write_html("test_bam_50.html")
print("\nSaved test_bam_50.html")

# Test with ALL BAM points using go.Scattermapbox directly
fig2 = go.Figure(go.Scattermapbox(
    lat=bam['ละติจูด'].tolist(),
    lon=bam['ลองจิจูด'].tolist(),
    mode='markers',
    marker=dict(size=8, color='#3b82f6'),
    text=bam['ชื่อประกาศ'].fillna('N/A').astype(str).str[:50].tolist(),
    hoverinfo='text',
    name='BAM'
))
fig2.update_layout(
    mapbox_style="open-street-map",
    mapbox=dict(center=dict(lat=13.7, lon=100.5), zoom=5),
    margin={"r":0,"t":30,"l":0,"b":0},
    height=500,
    title="Test 2: BAM all points (go.Scattermapbox)"
)
fig2.write_html("test_bam_all.html")
print("Saved test_bam_all.html")

# Test with scatter_map (non-deprecated replacement)
try:
    fig3 = px.scatter_map(
        bam_small, lat="ละติจูด", lon="ลองจิจูด",
        hover_name="title",
        zoom=5, height=500,
    )
    fig3.update_layout(margin={"r":0,"t":30,"l":0,"b":0}, title="Test 3: scatter_map (new API)")
    fig3.write_html("test_bam_scatter_map.html")
    print("Saved test_bam_scatter_map.html")
except Exception as e:
    print(f"scatter_map failed: {e}")
