import os
import math
import json
import numpy as np
import pandas as pd
import streamlit as st
from pathlib import Path
from PIL import Image
import io
import base64

_CACHED_ATLAS_URI = None
_CACHED_ICON_MAPPING = None
_LEAFLET_LOGO_CACHE = {}

def haversine_distance(lat1, lon1, lat2, lon2):
    """Haversine distance calculation between two points in km."""
    R = 6371  # Earth radius in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def haversine_distance_vectorized(lat1, lon1, lats, lons):
    """Vectorized Haversine distance computation using NumPy."""
    R = 6371.0  # Earth radius in km
    lat1_rad = np.radians(lat1)
    lon1_rad = np.radians(lon1)
    lats_rad = np.radians(lats)
    lons_rad = np.radians(lons)
    
    dlat = lats_rad - lat1_rad
    dlon = lons_rad - lon1_rad
    
    a = np.sin(dlat / 2.0) ** 2 + np.cos(lat1_rad) * np.cos(lats_rad) * np.sin(dlon / 2.0) ** 2
    c = 2.0 * np.arcsin(np.sqrt(np.clip(a, 0.0, 1.0)))
    return R * c

@st.cache_data
def get_thailand_clean_grid(ref_lat, ref_lng):
    """Cached multi-scale Thailand grid generator for instant clean map rendering."""
    u_lat, u_lng = np.meshgrid(
        np.linspace(ref_lat - 0.03, ref_lat + 0.03, 35),
        np.linspace(ref_lng - 0.03, ref_lng + 0.03, 35)
    )
    f_lat, f_lng = np.meshgrid(
        np.linspace(ref_lat - 0.15, ref_lat + 0.15, 25),
        np.linspace(ref_lng - 0.15, ref_lng + 0.15, 25)
    )
    m_lat, m_lng = np.meshgrid(
        np.linspace(ref_lat - 0.8, ref_lat + 0.8, 20),
        np.linspace(ref_lng - 0.8, ref_lng + 0.8, 20)
    )
    c_lat, c_lng = np.meshgrid(
        np.linspace(5.5, 20.5, 35),
        np.linspace(97.5, 105.5, 35)
    )

    all_lats = np.concatenate([u_lat.flatten(), f_lat.flatten(), m_lat.flatten(), c_lat.flatten()])
    all_lngs = np.concatenate([u_lng.flatten(), f_lng.flatten(), m_lng.flatten(), c_lng.flatten()])

    r1 = (all_lats >= 5.6) & (all_lats < 7.2) & (all_lngs >= 99.8) & (all_lngs <= 102.2)
    r2 = (all_lats >= 7.2) & (all_lats < 9.0) & (all_lngs >= 98.2) & (all_lngs <= 100.5)
    r3 = (all_lats >= 9.0) & (all_lats < 10.2) & (all_lngs >= 98.5) & (all_lngs <= 100.2)
    r4 = (all_lats >= 10.2) & (all_lats < 11.2) & (all_lngs >= 98.5) & (all_lngs <= 99.6)
    r5 = (all_lats >= 11.2) & (all_lats < 13.2) & (all_lngs >= 99.0) & (all_lngs <= 100.1)
    r6 = (all_lats >= 13.2) & (all_lats < 14.5) & (all_lngs >= 99.4) & (all_lngs <= 101.0)
    r7 = (all_lats >= 13.8) & (all_lats < 15.6) & (all_lngs >= 98.7) & (all_lngs <= 101.4)
    r8 = (all_lats >= 11.7) & (all_lats < 13.6) & (all_lngs >= 100.8) & (all_lngs <= 102.9)
    r9 = (all_lats >= 13.4) & (all_lats < 14.3) & (all_lngs >= 101.0) & (all_lngs <= 103.0)
    r10 = (all_lats >= 14.0) & (all_lats < 15.8) & (all_lngs >= 101.2) & (all_lngs <= 105.6)
    r11 = (all_lats >= 15.8) & (all_lats < 18.5) & (all_lngs >= 101.5) & (all_lngs <= 105.0)
    r12 = (all_lats >= 16.8) & (all_lats < 18.3) & (all_lngs >= 101.0) & (all_lngs <= 102.6)
    r13 = (all_lats >= 14.8) & (all_lats < 17.5) & (all_lngs >= 97.8) & (all_lngs <= 101.4)
    r14 = (all_lats >= 17.5) & (all_lats <= 20.46) & (all_lngs >= 97.35) & (all_lngs <= 101.4)

    mask = r1 | r2 | r3 | r4 | r5 | r6 | r7 | r8 | r9 | r10 | r11 | r12 | r13 | r14
    return all_lats[mask], all_lngs[mask]

def find_nearby_properties(input_lat, input_lon, df_all, radius_km, match_type=None, company=None):
    """Find properties within radius_km of the given coordinates (ultra-fast Bounding Box + Haversine)."""
    if df_all is None or df_all.empty:
        return pd.DataFrame()
    empty_res = df_all.head(0).copy()
    if input_lat is None or input_lon is None or pd.isna(input_lat) or pd.isna(input_lon):
        return empty_res
        
    lat_margin = (radius_km / 105.0) + 0.015
    lon_margin = (radius_km / 90.0) + 0.015
    
    mask = (
        df_all['ละติจูด'].notna() & 
        df_all['ลองจิจูด'].notna() & 
        df_all['ละติจูด'].between(input_lat - lat_margin, input_lat + lat_margin) & 
        df_all['ลองจิจูด'].between(input_lon - lon_margin, input_lon + lon_margin)
    )
    
    if company:
        mask &= (df_all['บริษัท'] == company)
        
    if match_type:
        if isinstance(match_type, (list, tuple, set)):
            clean_types = [str(t).strip() for t in match_type if str(t).strip() not in ['', 'nan', 'None']]
            if clean_types:
                mask &= (df_all['ประเภททรัพย์'].isin(clean_types))
        elif str(match_type).strip() not in ['', 'nan', 'None']:
            mask &= (df_all['ประเภททรัพย์'] == str(match_type).strip())
        
    df_sub = df_all[mask]
    if df_sub.empty:
        return empty_res
        
    lats = df_sub['ละติจูด'].to_numpy(dtype=float)
    lons = df_sub['ลองจิจูด'].to_numpy(dtype=float)
    
    distances = haversine_distance_vectorized(input_lat, input_lon, lats, lons)
    nearby_mask = distances <= radius_km
    
    if not np.any(nearby_mask):
        return empty_res
        
    df_result = df_sub[nearby_mask].copy()
    df_result['ระยะทาง (กม.)'] = np.round(distances[nearby_mask], 2)
    return df_result

def get_map_icon_atlas_and_mapping(icon_size=128):
    """Builds and caches a single high-resolution Retina sprite sheet atlas containing all company logo badges and property type pins."""
    global _CACHED_ATLAS_URI, _CACHED_ICON_MAPPING
    if _CACHED_ATLAS_URI is not None and _CACHED_ICON_MAPPING is not None:
        return _CACHED_ATLAS_URI, _CACHED_ICON_MAPPING
        
    companies = [
        "LED", "SAM", "BAM", "Chayo555", "GHB", "KBANK", "KTB", "SCB", "GSB",
        "DDproperty", "Livinginsider", "NaYoo", "ZmyHome", "Baania", "จุดอ้างอิง"
    ]
    
    company_colors_map = {
        "LED": (8, 145, 178, 255), "SAM": (16, 185, 129, 255), "BAM": (59, 130, 246, 255),
        "Chayo555": (249, 115, 22, 255), "Chayo": (249, 115, 22, 255), "GHB": (202, 138, 4, 255),
        "KBANK": (5, 150, 105, 255), "KTB": (2, 132, 199, 255), "SCB": (126, 34, 206, 255),
        "GSB": (235, 25, 133, 255), "DDproperty": (168, 85, 247, 255), "Livinginsider": (20, 184, 166, 255),
        "NaYoo": (139, 92, 246, 255), "ZmyHome": (236, 72, 153, 255), "Baania": (245, 158, 11, 255)
    }

    prop_types = [
        ("บ้านเดี่ยว", (59, 130, 246, 255), "บ้าน"),
        ("ห้องชุดพักอาศัย", (139, 92, 246, 255), "คอนโด"),
        ("คอนโด", (139, 92, 246, 255), "คอนโด"),
        ("คอนโดมิเนียม", (139, 92, 246, 255), "คอนโด"),
        ("ทาวน์เฮ้าส์", (16, 185, 129, 255), "ทาวน์"),
        ("ทาวน์โฮม", (16, 185, 129, 255), "ทาวน์"),
        ("ที่ดินเปล่า", (139, 69, 19, 255), "ที่ดิน"),
        ("ที่ดิน", (139, 69, 19, 255), "ที่ดิน"),
        ("ที่ดินพร้อมสิ่งปลูกสร้าง", (249, 115, 22, 255), "ที่ดิน+"),
        ("อาคารพาณิชย์", (245, 158, 11, 255), "พาณิชย์"),
        ("โรงงาน/โกดัง", (239, 68, 68, 255), "โรงงาน"),
        ("อพาร์ทเมนท์", (168, 85, 247, 255), "อพาร์ท"),
        ("บ้านแฝด", (14, 165, 233, 255), "แฝด"),
        ("อาคารสำนักงาน", (100, 116, 139, 255), "สำนักงาน"),
        ("โรงแรม/รีสอร์ท", (234, 179, 8, 255), "โรงแรม"),
        ("วิลล่า", (217, 70, 239, 255), "วิลล่า"),
        ("อื่นๆ", (100, 116, 139, 255), "อื่นๆ")
    ]
    
    total_slots = len(companies) + len(prop_types)
    atlas_width = total_slots * icon_size
    atlas_height = icon_size
    
    try:
        from PIL import ImageDraw
        atlas = Image.new("RGBA", (atlas_width, atlas_height), (0, 0, 0, 0))
        icon_mapping = {}
        margin = 4
        border_w = max(5, int(icon_size * 0.065))
        
        # 1. Render Company Badges
        for i, name in enumerate(companies):
            x_offset = i * icon_size
            cell = Image.new("RGBA", (icon_size, icon_size), (0, 0, 0, 0))
            draw = ImageDraw.Draw(cell)
            
            if name == "จุดอ้างอิง":
                draw.ellipse([margin, margin, icon_size - margin, icon_size - margin], fill=(239, 68, 68, 255), outline=(255, 255, 255, 255), width=border_w)
                c_mid = icon_size // 2
                draw.ellipse([c_mid - 24, c_mid - 24, c_mid + 24, c_mid + 24], fill=(255, 255, 255, 255))
                draw.ellipse([c_mid - 12, c_mid - 12, c_mid + 12, c_mid + 12], fill=(239, 68, 68, 255))
            else:
                b_col = company_colors_map.get(name, (59, 130, 246, 255))
                draw.ellipse([margin, margin, icon_size - margin, icon_size - margin], fill=(255, 255, 255, 255), outline=b_col, width=border_w)
                
                logo_path = None
                for base in [name, name.lower(), name.upper(), name.capitalize(), name.title()]:
                    for ext in ['.png', '.jpg', '.jpeg', '.webp']:
                        p = os.path.join("logo", "logos", f"{base}{ext}")
                        if not os.path.exists(p):
                            p = os.path.join("assets", "logos", f"{base}{ext}")
                        if os.path.exists(p):
                            logo_path = p
                            break
                    if logo_path:
                        break
                
                if logo_path:
                    try:
                        logo = Image.open(logo_path).convert("RGBA")
                        bbox = logo.getbbox()
                        if bbox:
                            logo = logo.crop(bbox)
                        inner_max = int((icon_size - margin * 2) * 0.72)
                        logo.thumbnail((inner_max, inner_max), Image.Resampling.LANCZOS)
                        off_x = (icon_size - logo.width) // 2
                        off_y = (icon_size - logo.height) // 2
                        cell.paste(logo, (off_x, off_y), logo)
                    except Exception:
                        draw.text((icon_size // 2, icon_size // 2), name[:4].upper(), fill=(15, 23, 42, 255), anchor="mm")
                else:
                    draw.text((icon_size // 2, icon_size // 2), name[:4].upper(), fill=(15, 23, 42, 255), anchor="mm")
                    
            atlas.paste(cell, (x_offset, 0), cell)
            
            icon_mapping[name] = {
                "x": x_offset, "y": 0, "width": icon_size, "height": icon_size,
                "mask": False, "anchorX": icon_size // 2, "anchorY": icon_size // 2
            }
            icon_mapping[name.lower()] = icon_mapping[name]
            icon_mapping[name.upper()] = icon_mapping[name]
            
        # 2. Render Property Type Badges
        start_idx = len(companies)
        for j, (p_type, p_col, p_short) in enumerate(prop_types):
            x_offset = (start_idx + j) * icon_size
            cell = Image.new("RGBA", (icon_size, icon_size), (0, 0, 0, 0))
            draw = ImageDraw.Draw(cell)
            draw.ellipse([margin, margin, icon_size - margin, icon_size - margin], fill=p_col, outline=(255, 255, 255, 255), width=border_w)
            
            c = icon_size // 2
            if "บ้าน" in p_type or p_type == "วิลล่า":
                draw.polygon([(c, c - 26), (c - 28, c - 2), (c + 28, c - 2)], fill=(255, 255, 255, 255))
                draw.rectangle([c - 20, c - 2, c + 20, c + 24], fill=(255, 255, 255, 255))
                draw.rectangle([c - 7, c + 6, c + 7, c + 24], fill=p_col)
            elif "คอนโด" in p_type or "ห้องชุด" in p_type:
                draw.rectangle([c - 22, c - 28, c + 22, c + 28], fill=(255, 255, 255, 255))
                for wy in [-18, -6, 6, 18]:
                    for wx in [-14, 2]:
                        draw.rectangle([c + wx, c + wy, c + wx + 9, c + wy + 8], fill=p_col)
            elif "ทาวน์" in p_type:
                draw.polygon([(c - 16, c - 24), (c - 32, c - 6), (c, c - 6)], fill=(255, 255, 255, 255))
                draw.rectangle([c - 28, c - 6, c - 4, c + 24], fill=(255, 255, 255, 255))
                draw.polygon([(c + 16, c - 24), (c, c - 6), (c + 32, c - 6)], fill=(255, 255, 255, 255))
                draw.rectangle([c + 4, c - 6, c + 28, c + 24], fill=(255, 255, 255, 255))
            elif "ที่ดิน" in p_type:
                draw.polygon([(c, c - 26), (c - 24, c + 4), (c + 24, c + 4)], fill=(255, 255, 255, 255))
                draw.polygon([(c, c - 14), (c - 20, c + 14), (c + 20, c + 14)], fill=(255, 255, 255, 255))
                draw.rectangle([c - 5, c + 14, c + 5, c + 26], fill=(255, 255, 255, 255))
            elif "พาณิชย์" in p_type:
                draw.rectangle([c - 25, c - 18, c + 25, c + 25], fill=(255, 255, 255, 255))
                draw.polygon([(c, c - 28), (c - 28, c - 18), (c + 28, c - 18)], fill=(255, 255, 255, 255))
                draw.rectangle([c - 16, c - 2, c - 3, c + 12], fill=p_col)
                draw.rectangle([c + 3, c - 2, c + 16, c + 12], fill=p_col)
                draw.rectangle([c - 8, c + 14, c + 8, c + 25], fill=p_col)
            elif "โรงงาน" in p_type:
                draw.polygon([(c - 26, c - 6), (c - 10, c - 20), (c - 10, c - 6), (c + 8, c - 20), (c + 8, c - 6), (c + 24, c - 6), (c + 24, c + 24), (c - 26, c + 24)], fill=(255, 255, 255, 255))
                draw.rectangle([c + 14, c - 26, c + 20, c - 6], fill=(255, 255, 255, 255))
            else:
                draw.ellipse([c - 16, c - 16, c + 16, c + 16], fill=(255, 255, 255, 255))
                
            atlas.paste(cell, (x_offset, 0), cell)
            icon_mapping[p_type] = {
                "x": x_offset, "y": 0, "width": icon_size, "height": icon_size,
                "mask": False, "anchorX": icon_size // 2, "anchorY": icon_size // 2
            }
            
        buf = io.BytesIO()
        atlas.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
        data_uri = f"data:image/png;base64,{b64}"
        
        _CACHED_ATLAS_URI = data_uri
        _CACHED_ICON_MAPPING = icon_mapping
        return data_uri, icon_mapping
    except Exception:
        fallback = "https://raw.githubusercontent.com/visgl/deck.gl-data/master/website/icon-atlas.png"
        return fallback, {}

def create_map_circle_coords(lat, lon, radius_km, num_points=64):
    """Generates lat/lon coordinates for a smooth circular polygon on Plotly map."""
    angles = np.linspace(0, 2 * np.pi, num_points)
    d_lat = (radius_km / 111.32) * np.sin(angles)
    d_lon = (radius_km / (111.32 * np.cos(np.radians(lat)))) * np.cos(angles)
    return lat + d_lat, lon + d_lon

def get_leaflet_logo_dict(size=72):
    """Generates optimized base64 dictionary of all company logos for Leaflet pins with healthy margin."""
    global _LEAFLET_LOGO_CACHE
    if _LEAFLET_LOGO_CACHE:
        return _LEAFLET_LOGO_CACHE
        
    base_dir = Path(os.getcwd())
    logo_dir = base_dir / "logo" / "logos"
    if not logo_dir.exists():
        logo_dir = Path("logo/logos")
    if not logo_dir.exists():
        logo_dir = base_dir / "assets" / "logos"
    if not logo_dir.exists():
        logo_dir = Path("assets/logos")
        
    logo_dict = {}
    if not logo_dir.exists():
        _LEAFLET_LOGO_CACHE = logo_dict
        return logo_dict
        
    for fname in os.listdir(logo_dir):
        if fname.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
            path = logo_dir / fname
            base_name = os.path.splitext(fname)[0].strip()
            try:
                im = Image.open(path).convert("RGBA")
                bbox = im.getbbox()
                if bbox:
                    im = im.crop(bbox)
                max_side = max(im.width, im.height)
                square = Image.new("RGBA", (max_side, max_side), (0, 0, 0, 0))
                ox = (max_side - im.width) // 2
                oy = (max_side - im.height) // 2
                square.paste(im, (ox, oy), im)
                square = square.resize((size, size), Image.Resampling.LANCZOS)
                buf = io.BytesIO()
                square.save(buf, format="PNG", optimize=True)
                b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
                data_uri = f"data:image/png;base64,{b64}"
                
                logo_dict[base_name] = data_uri
                logo_dict[base_name.lower()] = data_uri
                logo_dict[base_name.upper()] = data_uri
                clean_name = base_name.replace("logo", "").replace(" ", "").strip()
                if clean_name:
                    logo_dict[clean_name] = data_uri
                    logo_dict[clean_name.lower()] = data_uri
                    logo_dict[clean_name.upper()] = data_uri
            except Exception:
                pass
                
    _LEAFLET_LOGO_CACHE = logo_dict
    return logo_dict

@st.cache_data(show_spinner=False)
def load_raw_districts_geojson():
    path = os.path.join("data", "districts.geojson")
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None
    return None

@st.cache_data(show_spinner=False)
def load_raw_subdistricts_geojson():
    path = os.path.join("data", "subdistricts.geojson")
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None
    return None

def _calc_polygon_centroid(geometry):
    if not geometry or 'coordinates' not in geometry:
        return None
    coords = geometry['coordinates']
    lons, lats = [], []
    def _extract(c):
        if isinstance(c, (list, tuple)):
            if len(c) >= 2 and isinstance(c[0], (int, float)) and isinstance(c[1], (int, float)):
                lons.append(float(c[0]))
                lats.append(float(c[1]))
            else:
                for item in c:
                    _extract(item)
    _extract(coords)
    if lons and lats:
        avg_lon = (min(lons) + max(lons)) / 2.0
        avg_lat = (min(lats) + max(lats)) / 2.0
        return (avg_lon, avg_lat)
    return None

def get_boundary_geojson_features(prov_list=None, dist_list=None, subdist_list=None):
    """Filters districts or subdistricts GeoJSON to get boundary frames, dashed district lines, and labels."""
    if not prov_list and not dist_list and not subdist_list:
        return None

    clean_dists = set()
    if dist_list:
        for d in dist_list:
            d_str = str(d).strip()
            clean_dists.add(d_str.split(" (")[0].strip())
            clean_dists.add(d_str)

    clean_provs = set(str(p).strip() for p in (prov_list or []))
    clean_subdists = set(str(s).strip() for s in (subdist_list or []))
    district_labels = []

    # Case 1: Subdistrict selected
    if clean_subdists:
        sd_data = load_raw_subdistricts_geojson()
        if sd_data and 'features' in sd_data:
            matched = []
            for feat in sd_data['features']:
                props = feat.get('properties', {})
                tam_th = str(props.get('tam_th', '')).strip()
                amp_th = str(props.get('amp_th', '')).strip()
                pro_th = str(props.get('pro_th', '')).strip()
                if tam_th in clean_subdists:
                    if clean_dists and amp_th not in clean_dists:
                        continue
                    if clean_provs and pro_th not in clean_provs:
                        continue
                    matched.append(feat)
                    centroid = _calc_polygon_centroid(feat.get('geometry'))
                    if centroid:
                        district_labels.append({"name": tam_th, "lon": centroid[0], "lat": centroid[1]})
            if matched:
                return {"type": "FeatureCollection", "level": "single_subdistrict", "features": matched, "district_labels": district_labels}

    # Case 2: District selected
    if clean_dists:
        sd_data = load_raw_subdistricts_geojson()
        if sd_data and 'features' in sd_data:
            matched = []
            for feat in sd_data['features']:
                props = feat.get('properties', {})
                tam_th = str(props.get('tam_th', '')).strip()
                amp_th = str(props.get('amp_th', '')).strip()
                pro_th = str(props.get('pro_th', '')).strip()
                if amp_th in clean_dists:
                    if clean_provs and pro_th not in clean_provs:
                        continue
                    matched.append(feat)
                    centroid = _calc_polygon_centroid(feat.get('geometry'))
                    if centroid:
                        district_labels.append({"name": tam_th, "lon": centroid[0], "lat": centroid[1]})
            if matched:
                return {
                    "type": "FeatureCollection",
                    "level": "subdistrict",
                    "features": matched,
                    "district_labels": district_labels
                }

        dist_data = load_raw_districts_geojson()
        if dist_data and 'features' in dist_data:
            matched = []
            for feat in dist_data['features']:
                props = feat.get('properties', {})
                amp_th = str(props.get('amp_th', '')).strip()
                pro_th = str(props.get('pro_th', '')).strip()
                if amp_th in clean_dists:
                    if clean_provs and pro_th not in clean_provs:
                        continue
                    matched.append(feat)
                    centroid = _calc_polygon_centroid(feat.get('geometry'))
                    if centroid:
                        district_labels.append({"name": amp_th, "lon": centroid[0], "lat": centroid[1]})
            if matched:
                return {
                    "type": "FeatureCollection",
                    "level": "district",
                    "features": matched,
                    "district_labels": district_labels
                }

    # Case 3: Province selected
    if clean_provs:
        dist_data = load_raw_districts_geojson()
        if dist_data and 'features' in dist_data:
            matched = []
            for feat in dist_data['features']:
                props = feat.get('properties', {})
                pro_th = str(props.get('pro_th', '')).strip()
                amp_th = str(props.get('amp_th', '')).strip()
                if pro_th in clean_provs:
                    matched.append(feat)
                    centroid = _calc_polygon_centroid(feat.get('geometry'))
                    if centroid:
                        district_labels.append({"name": amp_th, "lon": centroid[0], "lat": centroid[1]})
            if matched:
                return {"type": "FeatureCollection", "level": "district", "features": matched, "district_labels": district_labels}

    return None

@st.cache_data(show_spinner=False)
def get_official_gis_reference():
    gis_candidates = [
        os.path.join(os.getcwd(), "references", "thailand_provinces_districts_subdistricts.json"),
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "references", "thailand_provinces_districts_subdistricts.json"),
    ]
    gis_path = next((p for p in gis_candidates if os.path.exists(p)), None)
    if not gis_path:
        return set(), set(), set()
    try:
        with open(gis_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        pairs = {(item['อำเภอ/เขต (ไทย)'].strip(), item['จังหวัด (ไทย)'].strip()) for item in data if 'อำเภอ/เขต (ไทย)' in item and 'จังหวัด (ไทย)' in item}
        provs = {item['จังหวัด (ไทย)'].strip() for item in data if 'จังหวัด (ไทย)' in item}
        dists = {item['อำเภอ/เขต (ไทย)'].strip() for item in data if 'อำเภอ/เขต (ไทย)' in item}
        return pairs, provs, dists
    except Exception:
        return set(), set(), set()
